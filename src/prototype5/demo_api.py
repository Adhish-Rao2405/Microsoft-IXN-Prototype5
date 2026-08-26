"""FastAPI boundary for the Prototype 5 integrated demonstrator."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from dataclasses import asdict
from functools import partial
from pathlib import Path
from typing import AsyncIterator, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError, field_validator
from starlette.concurrency import run_in_threadpool

from .demo_runtime import build_demo_service, build_replay_coordinator
from .demo_service import (
    DemoApplicationService,
    DemoStatusResponse,
    SpeechBackendUnavailableError,
    SpeechCapacityUnavailableError,
    TranscriptRegistryError,
    TranscriptNotReadyError,
    TypedCommandHttpRequest,
    VoiceCommandHttpRequest,
)
from .final_demo_presentation import (
    FinalDemoManifest,
    FinalDemoScenarioInferenceForbiddenError,
    FinalDemoScenarioNotFoundError,
)
from .hybrid_inference_router import HybridGovernanceResultV1
from .recorded_speech import (
    DEFAULT_MAX_AUDIO_BYTES,
    RecordedTranscriptionResultV1,
)
from .replay_coordinator import (
    MAX_SAFE_INTEGER,
    ReplayControl,
    ReplayCoordinator,
    ReplayCoordinatorError,
    ReplayErrorCode,
    ReplayStateProjection,
)


REPLAY_REQUEST_MAX_BYTES = 4096


class _ReplayRequestInvalid(ValueError):
    pass


class _ReplayStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    scenario_id: StrictStr = Field(min_length=1, max_length=200)

    @field_validator("scenario_id")
    @classmethod
    def nonblank_scenario_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("scenario_id must be nonblank")
        return value


class _ReplayControlRequest(_ReplayStartRequest):
    session_id: StrictStr = Field(min_length=1, max_length=200)
    expected_control_version: StrictInt = Field(ge=0, le=MAX_SAFE_INTEGER)
    control: Literal[
        "PAUSE",
        "RESUME",
        "NEXT_SNAPSHOT",
        "PREVIOUS_SNAPSHOT",
        "STOP",
        "RESET_VIEW",
    ]

    @field_validator("session_id")
    @classmethod
    def nonblank_session_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("session_id must be nonblank")
        return value


def _reject_replay_constant(token: str) -> object:
    raise _ReplayRequestInvalid(f"invalid JSON constant: {token}")


def _reject_replay_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _ReplayRequestInvalid("duplicate JSON field")
        result[key] = value
    return result


async def _read_replay_json(request: Request) -> dict[str, object]:
    if request.headers.get("content-encoding") is not None:
        raise _ReplayRequestInvalid("content encoding is forbidden")
    content_type = request.headers.get("content-type", "")
    parts = [part.strip() for part in content_type.split(";")]
    if not parts or parts[0].lower() != "application/json":
        raise _ReplayRequestInvalid("content type must be application/json")
    if len(parts) > 2 or (
        len(parts) == 2 and parts[1].lower() != "charset=utf-8"
    ):
        raise _ReplayRequestInvalid("unsupported JSON charset")
    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        if not declared_length.isascii() or not declared_length.isdecimal():
            raise _ReplayRequestInvalid("content length is invalid")
        if int(declared_length) > REPLAY_REQUEST_MAX_BYTES:
            raise _ReplayRequestInvalid("request body exceeds bound")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > REPLAY_REQUEST_MAX_BYTES:
            raise _ReplayRequestInvalid("request body exceeds bound")
    if not body or bytes(body).startswith(b"\xef\xbb\xbf"):
        raise _ReplayRequestInvalid("request body is empty or has a BOM")
    try:
        text = bytes(body).decode("utf-8", errors="strict")
        parsed = json.loads(
            text,
            parse_constant=_reject_replay_constant,
            object_pairs_hook=_reject_replay_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _ReplayRequestInvalid) as exc:
        raise _ReplayRequestInvalid("request body is not canonical JSON") from exc
    if not isinstance(parsed, dict):
        raise _ReplayRequestInvalid("request body must be an object")
    return parsed


def _replay_error(error: ReplayCoordinatorError) -> JSONResponse:
    return JSONResponse(
        status_code=error.http_status,
        content={"code": error.code.value},
    )


def _replay_state(state: ReplayStateProjection) -> JSONResponse:
    return JSONResponse(status_code=200, content=asdict(state))


def create_demo_app(
    service: DemoApplicationService,
    *,
    frontend_dist: Path | None = None,
    replay_coordinator: ReplayCoordinator | None = None,
) -> FastAPI:
    lifespan = None
    if replay_coordinator is not None:
        @asynccontextmanager
        async def replay_lifespan(_: FastAPI) -> AsyncIterator[None]:
            await run_in_threadpool(replay_coordinator.start)
            try:
                yield
            finally:
                await run_in_threadpool(replay_coordinator.shutdown)

        lifespan = replay_lifespan
    app = FastAPI(
        title="Prototype 5 Zero-Trust Robotics Demonstrator",
        version="2.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Audio-Filename"],
    )

    @app.get("/api/v1/status", response_model=DemoStatusResponse)
    def status() -> DemoStatusResponse:
        return service.status()

    @app.get("/api/v1/demo/manifest", response_model=FinalDemoManifest)
    def demo_manifest() -> FinalDemoManifest:
        return service.manifest()

    @app.post(
        "/api/v1/governance/typed",
        response_model=HybridGovernanceResultV1,
    )
    def submit_typed(
        request: TypedCommandHttpRequest,
    ) -> HybridGovernanceResultV1:
        try:
            return service.submit_typed(request)
        except FinalDemoScenarioNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": str(exc)},
            ) from exc
        except FinalDemoScenarioInferenceForbiddenError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": str(exc)},
            ) from exc

    @app.post(
        "/api/v1/speech/recorded",
        response_model=RecordedTranscriptionResultV1,
    )
    async def transcribe_recorded(
        request: Request,
    ) -> RecordedTranscriptionResultV1:
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type not in {
            "audio/wav",
            "audio/x-wav",
            "application/octet-stream",
        }:
            raise HTTPException(
                status_code=415,
                detail={"code": "AUDIO_CONTENT_TYPE_UNSUPPORTED"},
            )
        declared_length = request.headers.get("content-length")
        if declared_length:
            try:
                parsed_length = int(declared_length)
                if parsed_length < 0:
                    raise ValueError
                if parsed_length > DEFAULT_MAX_AUDIO_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail={"code": "AUDIO_TOO_LARGE"},
                    )
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "CONTENT_LENGTH_INVALID"},
                ) from exc

        audio = bytearray()
        async for chunk in request.stream():
            audio.extend(chunk)
            if len(audio) > DEFAULT_MAX_AUDIO_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail={"code": "AUDIO_TOO_LARGE"},
                )
        filename = request.headers.get("x-audio-filename", "recording.wav")
        if (
            Path(filename).name != filename
            or len(filename) > 255
            or any(ord(character) < 32 for character in filename)
        ):
            raise HTTPException(
                status_code=400,
                detail={"code": "AUDIO_FILENAME_INVALID"},
            )
        try:
            return await run_in_threadpool(
                service.transcribe_recorded,
                bytes(audio),
                original_filename=filename,
            )
        except SpeechBackendUnavailableError as exc:
            raise HTTPException(
                status_code=503,
                detail={"code": str(exc)},
            ) from exc
        except SpeechCapacityUnavailableError as exc:
            raise HTTPException(
                status_code=503,
                detail={"code": str(exc)},
            ) from exc
        except TranscriptRegistryError as exc:
            raise HTTPException(
                status_code=503,
                detail={"code": str(exc)},
            ) from exc

    @app.post(
        "/api/v1/governance/voice",
        response_model=HybridGovernanceResultV1,
    )
    def submit_voice(
        request: VoiceCommandHttpRequest,
    ) -> HybridGovernanceResultV1:
        try:
            return service.submit_voice(request)
        except FinalDemoScenarioNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": str(exc)},
            ) from exc
        except FinalDemoScenarioInferenceForbiddenError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": str(exc)},
            ) from exc
        except TranscriptNotReadyError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": str(exc)},
            ) from exc

    if replay_coordinator is not None:
        def fatal_replay_response() -> JSONResponse | None:
            code = replay_coordinator.preflight_error()
            if code is None:
                return None
            return _replay_error(ReplayCoordinatorError(code))

        @app.post("/api/v1/replay/start")
        async def replay_start(request: Request) -> JSONResponse:
            fatal = fatal_replay_response()
            if fatal is not None:
                return fatal
            try:
                payload = await _read_replay_json(request)
                parsed = _ReplayStartRequest.model_validate(payload)
            except (_ReplayRequestInvalid, ValidationError):
                return _replay_error(
                    ReplayCoordinatorError(ReplayErrorCode.REQUEST_INVALID)
                )
            try:
                state = await run_in_threadpool(
                    replay_coordinator.start_replay,
                    parsed.scenario_id,
                )
            except ReplayCoordinatorError as exc:
                return _replay_error(exc)
            return _replay_state(state)

        @app.post("/api/v1/replay/control")
        async def replay_control(request: Request) -> JSONResponse:
            fatal = fatal_replay_response()
            if fatal is not None:
                return fatal
            try:
                payload = await _read_replay_json(request)
                parsed = _ReplayControlRequest.model_validate(payload)
            except (_ReplayRequestInvalid, ValidationError):
                return _replay_error(
                    ReplayCoordinatorError(ReplayErrorCode.REQUEST_INVALID)
                )
            try:
                state = await run_in_threadpool(
                    partial(
                        replay_coordinator.control,
                        scenario_id=parsed.scenario_id,
                        session_id=parsed.session_id,
                        expected_control_version=parsed.expected_control_version,
                        control=ReplayControl(parsed.control),
                    )
                )
            except ReplayCoordinatorError as exc:
                return _replay_error(exc)
            return _replay_state(state)

        @app.get("/api/v1/replay/state")
        async def replay_state() -> JSONResponse:
            fatal = fatal_replay_response()
            if fatal is not None:
                return fatal
            try:
                state = replay_coordinator.get_state()
            except ReplayCoordinatorError as exc:
                return _replay_error(exc)
            return _replay_state(state)

    if frontend_dist is not None and frontend_dist.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=frontend_dist, html=True),
            name="frontend",
        )
    else:
        @app.get("/", include_in_schema=False)
        def root() -> RedirectResponse:
            return RedirectResponse(url="/api/docs")

    return app


def create_runtime_app() -> FastAPI:
    repo_root = Path(__file__).resolve().parents[2]
    return create_demo_app(
        build_demo_service(repo_root),
        frontend_dist=repo_root / "frontend" / "dist",
        replay_coordinator=build_replay_coordinator(repo_root),
    )

"""FastAPI boundary for the Prototype 5 integrated demonstrator."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .demo_runtime import build_demo_service
from .demo_service import (
    DemoApplicationService,
    DemoStatusResponse,
    DomainNotAvailableError,
    SpeechBackendUnavailableError,
    TranscriptRegistryError,
    TranscriptNotReadyError,
    TypedCommandApiRequest,
    VoiceCommandApiRequest,
)
from .hybrid_inference_router import HybridGovernanceResultV1
from .recorded_speech import (
    DEFAULT_MAX_AUDIO_BYTES,
    RecordedTranscriptionResultV1,
)


def create_demo_app(
    service: DemoApplicationService,
    *,
    frontend_dist: Path | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Prototype 5 Zero-Trust Robotics Demonstrator",
        version="2.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
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

    @app.post(
        "/api/v1/governance/typed",
        response_model=HybridGovernanceResultV1,
    )
    def submit_typed(
        request: TypedCommandApiRequest,
    ) -> HybridGovernanceResultV1:
        try:
            return service.submit_typed(request)
        except DomainNotAvailableError as exc:
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
        request: VoiceCommandApiRequest,
    ) -> HybridGovernanceResultV1:
        try:
            return service.submit_voice(request)
        except DomainNotAvailableError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": str(exc)},
            ) from exc
        except TranscriptNotReadyError as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": str(exc)},
            ) from exc

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
    )

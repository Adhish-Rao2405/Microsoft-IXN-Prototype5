"""Isolated Foundry Local worker for one recorded Nemotron transcription."""

from __future__ import annotations

import argparse
import importlib.metadata
import math
import platform
import threading
import time
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .governance_contract_v2 import TranscriptStatus
from .recorded_speech import (
    DEFAULT_MAX_TRANSCRIPT_CHARACTERS,
    DEFAULT_MAX_TRANSCRIPT_SEGMENTS,
    NEMOTRON_SPEECH_ALIAS,
    NEMOTRON_SPEECH_EXECUTION_PROVIDER,
    NEMOTRON_SPEECH_MODEL_ID,
    QUALIFIED_FOUNDRY_CORE_VERSION,
    QUALIFIED_FOUNDRY_SDK_VERSION,
    QUALIFIED_ONNXRUNTIME_CORE_VERSION,
    QUALIFIED_ONNXRUNTIME_GENAI_VERSION,
    QUALIFIED_SPEECH_PYTHON_VERSION,
    RecordedTranscriptionResultV1,
    WORKER_STATUS_EXIT_CODES,
    _base_result,
    _sanitise_error,
    inspect_wav_bytes,
)


MIN_PUSHER_JOIN_TIMEOUT_SECONDS = 1.0
MAX_PUSHER_JOIN_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class WorkerConfiguration:
    model_alias: str = NEMOTRON_SPEECH_ALIAS
    expected_model_id: str = NEMOTRON_SPEECH_MODEL_ID
    allow_model_download: bool = False
    unload_after_request: bool = True
    language: str = "en"
    pusher_join_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.model_alias != NEMOTRON_SPEECH_ALIAS:
            raise ValueError("only the approved Nemotron alias is permitted")
        if self.expected_model_id != NEMOTRON_SPEECH_MODEL_ID:
            raise ValueError("only the qualified Nemotron model ID is permitted")
        if (
            isinstance(self.pusher_join_timeout_seconds, bool)
            or not isinstance(self.pusher_join_timeout_seconds, (int, float))
            or not math.isfinite(self.pusher_join_timeout_seconds)
            or not MIN_PUSHER_JOIN_TIMEOUT_SECONDS
            <= self.pusher_join_timeout_seconds
            <= MAX_PUSHER_JOIN_TIMEOUT_SECONDS
        ):
            raise ValueError(
                "pusher_join_timeout_seconds must be a finite number between 1 and 30"
            )


@dataclass(frozen=True)
class FoundrySdkSurface:
    configuration_type: Any
    manager_type: Any
    sdk_version: str | None
    core_version: str | None
    python_version: str | None = None
    ort_core_version: str | None = None
    ort_genai_version: str | None = None


class SpeechWorkerError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        unavailable: bool = False,
        safe_to_unload: bool = True,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.unavailable = unavailable
        self.safe_to_unload = safe_to_unload


def run_transcription_worker(
    audio_path: Path,
    configuration: WorkerConfiguration,
    *,
    sdk_surface: FoundrySdkSurface | None = None,
    timer=time.perf_counter,
) -> RecordedTranscriptionResultV1:
    audio_bytes = audio_path.read_bytes()
    audio = inspect_wav_bytes(
        audio_bytes,
        original_filename=audio_path.name,
    )
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    transcription_id = str(uuid4())
    started = timer()
    surface: FoundrySdkSurface | None = sdk_surface
    model: Any = None
    cached_before: bool | None = None
    loaded_before: bool | None = None
    downloaded = False
    loaded_for_request = False
    unloaded_after = False
    resolved_model_id: str | None = None
    execution_provider: str | None = None
    safe_to_unload = True

    try:
        surface = surface or load_sdk_surface()
        _require_qualified_runtime(surface)
        if surface.manager_type.instance is None:
            surface.manager_type.initialize(
                surface.configuration_type(
                    app_name="Prototype5RecordedNemotronV1"
                )
            )
        manager = surface.manager_type.instance
        if manager is None:
            raise SpeechWorkerError(
                "VOICE_BACKEND_UNAVAILABLE",
                "Foundry Local manager did not initialize.",
                unavailable=True,
            )

        model = manager.catalog.get_model_variant(
            configuration.expected_model_id
        )
        if model is None:
            raise SpeechWorkerError(
                "NEMOTRON_MODEL_NOT_FOUND",
                "The qualified Nemotron model variant is unavailable.",
                unavailable=True,
            )

        resolved_model_id = str(model.id)
        if resolved_model_id != configuration.expected_model_id:
            raise SpeechWorkerError(
                "NEMOTRON_MODEL_ID_MISMATCH",
                "Resolved Nemotron model ID does not match the qualified ID.",
                unavailable=True,
            )
        resolved_alias = str(getattr(model, "alias", ""))
        if resolved_alias != configuration.model_alias:
            raise SpeechWorkerError(
                "NEMOTRON_MODEL_ALIAS_MISMATCH",
                "Observed Nemotron alias does not match the qualified alias "
                f"(observed={resolved_alias!r}).",
                unavailable=True,
            )
        execution_provider = _execution_provider(model)
        if execution_provider != NEMOTRON_SPEECH_EXECUTION_PROVIDER:
            raise SpeechWorkerError(
                "NEMOTRON_EXECUTION_PROVIDER_MISMATCH",
                "Observed execution provider does not match the qualified provider "
                f"(observed={execution_provider!r}).",
                unavailable=True,
            )
        cached_before = bool(model.is_cached)
        loaded_before = bool(model.is_loaded)
        if not cached_before:
            if not configuration.allow_model_download:
                raise SpeechWorkerError(
                    "NEMOTRON_MODEL_NOT_CACHED",
                    "Nemotron model is not cached; explicit acquisition is required.",
                    unavailable=True,
                )
            model.download()
            downloaded = True
            if not bool(model.is_cached):
                raise SpeechWorkerError(
                    "NEMOTRON_MODEL_ACQUISITION_FAILED",
                    "Explicit Nemotron acquisition did not produce a cached model.",
                    unavailable=True,
                )

        if not loaded_before:
            model.load()
            loaded_for_request = True

        audio_client = model.get_audio_client()
        transcript, segment_count, transcript_complete = transcribe_wav_live(
            audio_client,
            audio_path,
            language=configuration.language,
            pusher_join_timeout_seconds=(
                configuration.pusher_join_timeout_seconds
            ),
        )
        status = (
            TranscriptStatus.READY
            if transcript and transcript_complete
            else (
                TranscriptStatus.PARTIAL
                if transcript
                else TranscriptStatus.EMPTY
            )
        )
        result = _base_result(
            audio,
            transcription_id=transcription_id,
            timestamp_utc=timestamp,
            transcript_status=status,
            transcript_text=transcript or None,
            resolved_model_id=resolved_model_id,
            execution_provider=execution_provider,
            sdk_version=surface.sdk_version,
            core_version=surface.core_version,
            model_cached_before=cached_before,
            model_loaded_before=loaded_before,
            model_downloaded_for_request=downloaded,
            model_loaded_for_request=loaded_for_request,
            segment_count=segment_count,
            transcription_latency_ms=(timer() - started) * 1000,
            error_code=(
                "TRANSCRIPT_EMPTY"
                if not transcript
                else (
                    "TRANSCRIPTION_PARTIAL"
                    if not transcript_complete
                    else None
                )
            ),
            error_detail=(
                "Nemotron returned no recognisable speech."
                if not transcript
                else (
                    "Nemotron did not emit a final transcript."
                    if not transcript_complete
                    else None
                )
            ),
        )
    except SpeechWorkerError as exc:
        safe_to_unload = exc.safe_to_unload
        status = (
            TranscriptStatus.BACKEND_UNAVAILABLE
            if exc.unavailable
            else TranscriptStatus.FAILED
        )
        result = _base_result(
            audio,
            transcription_id=transcription_id,
            timestamp_utc=timestamp,
            transcript_status=status,
            resolved_model_id=resolved_model_id,
            execution_provider=execution_provider,
            sdk_version=surface.sdk_version if surface else None,
            core_version=surface.core_version if surface else None,
            model_cached_before=cached_before,
            model_loaded_before=loaded_before,
            model_downloaded_for_request=downloaded,
            model_loaded_for_request=loaded_for_request,
            transcription_latency_ms=(timer() - started) * 1000,
            error_code=exc.code,
            error_detail=_sanitise_error(str(exc)),
        )
    except Exception as exc:
        result = _base_result(
            audio,
            transcription_id=transcription_id,
            timestamp_utc=timestamp,
            transcript_status=TranscriptStatus.FAILED,
            resolved_model_id=resolved_model_id,
            execution_provider=execution_provider,
            sdk_version=surface.sdk_version if surface else None,
            core_version=surface.core_version if surface else None,
            model_cached_before=cached_before,
            model_loaded_before=loaded_before,
            model_downloaded_for_request=downloaded,
            model_loaded_for_request=loaded_for_request,
            transcription_latency_ms=(timer() - started) * 1000,
            error_code="TRANSCRIPTION_FAILED",
            error_detail=_sanitise_error(str(exc)),
        )

    if (
        model is not None
        and loaded_for_request
        and configuration.unload_after_request
        and safe_to_unload
    ):
        try:
            model.unload()
            unloaded_after = True
        except Exception as exc:
            return RecordedTranscriptionResultV1.model_validate(
                result.model_copy(
                    update={
                        "transcript_status": TranscriptStatus.FAILED,
                        "transcript_text": None,
                        "model_unloaded_after_request": False,
                        "error_code": "MODEL_UNLOAD_FAILED",
                        "error_detail": _sanitise_error(str(exc)),
                    }
                ).model_dump()
            )

    return RecordedTranscriptionResultV1.model_validate(
        result.model_copy(
            update={"model_unloaded_after_request": unloaded_after}
        ).model_dump()
    )


def load_sdk_surface() -> FoundrySdkSurface:
    try:
        from foundry_local_sdk import Configuration, FoundryLocalManager
    except ImportError as exc:
        raise SpeechWorkerError(
            "VOICE_BACKEND_UNAVAILABLE",
            "foundry-local-sdk-winml is not installed in the speech worker.",
            unavailable=True,
        ) from exc

    return FoundrySdkSurface(
        configuration_type=Configuration,
        manager_type=FoundryLocalManager,
        sdk_version=_distribution_version("foundry-local-sdk-winml"),
        core_version=_distribution_version("foundry-local-core-winml"),
        python_version=platform.python_version(),
        ort_core_version=_distribution_version("onnxruntime-core"),
        ort_genai_version=_distribution_version("onnxruntime-genai-core"),
    )


def _require_qualified_runtime(surface: FoundrySdkSurface) -> None:
    expected = (
        (
            "SPEECH_PYTHON_VERSION_MISMATCH",
            "Python",
            surface.python_version,
            QUALIFIED_SPEECH_PYTHON_VERSION,
        ),
        (
            "FOUNDRY_SDK_VERSION_MISMATCH",
            "Foundry SDK",
            surface.sdk_version,
            QUALIFIED_FOUNDRY_SDK_VERSION,
        ),
        (
            "FOUNDRY_CORE_VERSION_MISMATCH",
            "Foundry core",
            surface.core_version,
            QUALIFIED_FOUNDRY_CORE_VERSION,
        ),
        (
            "ONNXRUNTIME_CORE_VERSION_MISMATCH",
            "ONNX Runtime core",
            surface.ort_core_version,
            QUALIFIED_ONNXRUNTIME_CORE_VERSION,
        ),
        (
            "ONNXRUNTIME_GENAI_VERSION_MISMATCH",
            "ONNX Runtime GenAI core",
            surface.ort_genai_version,
            QUALIFIED_ONNXRUNTIME_GENAI_VERSION,
        ),
    )
    for code, label, observed, qualified in expected:
        if observed != qualified:
            raise SpeechWorkerError(
                code,
                f"{label} version drifted from the qualified runtime "
                f"(observed={observed!r}, qualified={qualified!r}).",
                unavailable=True,
            )


def transcribe_wav_live(
    audio_client: Any,
    audio_path: Path,
    *,
    language: str,
    pusher_join_timeout_seconds: float,
) -> tuple[str, int, bool]:
    with wave.open(str(audio_path), "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        pcm = wav_file.readframes(wav_file.getnframes())

    session = audio_client.create_live_transcription_session()
    session.settings.sample_rate = sample_rate
    session.settings.channels = channels
    session.settings.bits_per_sample = sample_width * 8
    session.settings.language = language
    session.start()

    bytes_per_second = sample_rate * channels * sample_width
    chunk_bytes = max(bytes_per_second // 10, 1024)
    push_error: list[BaseException] = []

    def push_audio() -> None:
        try:
            for offset in range(0, len(pcm), chunk_bytes):
                session.append(pcm[offset : offset + chunk_bytes])
        except BaseException as exc:
            push_error.append(exc)
        finally:
            try:
                session.stop()
            except BaseException as exc:
                push_error.append(exc)

    pusher = threading.Thread(
        target=push_audio,
        name="prototype5-nemotron-pusher",
        daemon=True,
    )
    pusher.start()

    partial_segments: list[str] = []
    final_segments: list[str] = []
    segment_count = 0
    buffered_characters = 0
    try:
        for response in session.get_stream():
            for content in getattr(response, "content", ()) or ():
                text = (
                    getattr(content, "text", "")
                    or getattr(content, "transcript", "")
                    or ""
                )
                if text:
                    segment_count += 1
                    buffered_characters += len(text)
                    if segment_count > DEFAULT_MAX_TRANSCRIPT_SEGMENTS:
                        raise SpeechWorkerError(
                            "TRANSCRIPT_SEGMENT_LIMIT_EXCEEDED",
                            "Nemotron emitted too many transcript segments.",
                        )
                    if buffered_characters > DEFAULT_MAX_TRANSCRIPT_CHARACTERS * 4:
                        raise SpeechWorkerError(
                            "TRANSCRIPT_BUFFER_LIMIT_EXCEEDED",
                            "Nemotron transcript buffer exceeded its bounded size.",
                        )
                    if bool(getattr(response, "is_final", False)):
                        final_segments.append(text)
                    else:
                        partial_segments.append(text)
    finally:
        pusher.join(timeout=pusher_join_timeout_seconds)
        if pusher.is_alive():
            try:
                session.stop()
            except Exception:
                pass
            pusher.join(timeout=pusher_join_timeout_seconds)
            if pusher.is_alive():
                raise SpeechWorkerError(
                    "TRANSCRIPTION_PUSHER_CLEANUP_UNRESOLVED",
                    "Nemotron audio pusher remained live after bounded cleanup.",
                    safe_to_unload=False,
                )

    if push_error:
        raise SpeechWorkerError(
            "TRANSCRIPTION_STREAM_FAILED",
            str(push_error[0]),
        )
    selected = final_segments if final_segments else partial_segments
    transcript = _reconstruct_segments(
        selected,
        join_fragments=not bool(final_segments),
    )
    if len(transcript) > DEFAULT_MAX_TRANSCRIPT_CHARACTERS:
        raise SpeechWorkerError(
            "TRANSCRIPT_TOO_LONG",
            "Nemotron transcript exceeded the bounded command length.",
        )
    return transcript, segment_count, bool(final_segments)


def _reconstruct_segments(
    segments: list[str],
    *,
    join_fragments: bool,
) -> str:
    """Join incremental segments without duplicating cumulative final results."""
    normalised: list[str] = []
    for value in segments:
        segment = " ".join(value.split())
        if not segment:
            continue
        if not normalised:
            normalised.append(segment)
            continue
        previous = normalised[-1]
        if segment == previous:
            continue
        if segment.startswith(previous):
            normalised[-1] = segment
            continue
        normalised.append(segment)
    separator = "" if join_fragments else " "
    return " ".join(separator.join(normalised).split())


def _execution_provider(model: Any) -> str | None:
    runtime = getattr(getattr(model, "info", None), "runtime", None)
    provider = getattr(runtime, "execution_provider", None)
    return str(provider) if provider else None


def _distribution_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-path", required=True, type=Path)
    parser.add_argument("--result-path", required=True, type=Path)
    parser.add_argument("--model-alias", required=True)
    parser.add_argument("--expected-model-id", required=True)
    parser.add_argument("--allow-model-download", action="store_true")
    parser.add_argument("--unload-after-request", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = run_transcription_worker(
        args.audio_path,
        WorkerConfiguration(
            model_alias=args.model_alias,
            expected_model_id=args.expected_model_id,
            allow_model_download=args.allow_model_download,
            unload_after_request=args.unload_after_request,
        ),
    )
    args.result_path.parent.mkdir(parents=True, exist_ok=True)
    args.result_path.write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return WORKER_STATUS_EXIT_CODES.get(
        result.transcript_status,
        WORKER_STATUS_EXIT_CODES[TranscriptStatus.FAILED],
    )


if __name__ == "__main__":
    raise SystemExit(main())

"""Bounded recorded-audio client for the isolated Nemotron speech worker."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
import time
import wave
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import Field, field_validator, model_validator

from .governance_contract_v2 import (
    ContractModel,
    SHA256_PATTERN,
    TranscriptStatus,
)


NEMOTRON_SPEECH_ALIAS = "nemotron-speech-streaming-en-0.6b"
NEMOTRON_SPEECH_MODEL_ID = (
    "nemotron-speech-streaming-en-0.6b-generic-cpu:3"
)
NEMOTRON_TRANSCRIPT_BACKEND = "foundry_nemotron"
SPEECH_RESULT_SCHEMA_VERSION = "1.0.0"
DEFAULT_MAX_AUDIO_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_AUDIO_SECONDS = 60.0
DEFAULT_PROCESS_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_TRANSCRIPT_CHARACTERS = 1000
DEFAULT_MAX_TRANSCRIPT_SEGMENTS = 1000
DEFAULT_MAX_WORKER_RESULT_BYTES = 256 * 1024
ERROR_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


class RecordedAudioMetadataV1(ContractModel):
    original_filename: str
    audio_sha256: str
    audio_bytes: int = Field(ge=0)
    sample_rate_hz: int = Field(ge=0)
    channels: int = Field(ge=0)
    bits_per_sample: int = Field(ge=0)
    frame_count: int = Field(ge=0)
    duration_ms: float = Field(ge=0)

    @model_validator(mode="after")
    def hash_and_filename_are_safe(self) -> "RecordedAudioMetadataV1":
        if not SHA256_PATTERN.fullmatch(self.audio_sha256):
            raise ValueError("audio_sha256 must be a SHA-256 hex digest")
        if Path(self.original_filename).name != self.original_filename:
            raise ValueError("original_filename must not contain a path")
        return self


class RecordedTranscriptionResultV1(ContractModel):
    result_schema_version: Literal["1.0.0"] = SPEECH_RESULT_SCHEMA_VERSION
    transcription_id: str = Field(min_length=1, max_length=200)
    timestamp_utc: str
    transcript_status: TranscriptStatus
    transcript_text: str | None = Field(
        default=None,
        max_length=DEFAULT_MAX_TRANSCRIPT_CHARACTERS,
    )
    transcript_backend: str = NEMOTRON_TRANSCRIPT_BACKEND
    transcript_confidence: float | None = Field(default=None, ge=0, le=1)
    audio: RecordedAudioMetadataV1
    requested_model_alias: str = NEMOTRON_SPEECH_ALIAS
    resolved_model_id: str | None = None
    execution_provider: str | None = None
    sdk_distribution: str = "foundry-local-sdk-winml"
    sdk_version: str | None = None
    core_distribution: str = "foundry-local-core-winml"
    core_version: str | None = None
    model_cached_before: bool | None = None
    model_loaded_before: bool | None = None
    model_downloaded_for_request: bool = False
    model_loaded_for_request: bool = False
    model_unloaded_after_request: bool = False
    segment_count: int = Field(
        default=0,
        ge=0,
        le=DEFAULT_MAX_TRANSCRIPT_SEGMENTS,
    )
    transcription_latency_ms: float | None = Field(default=None, ge=0)
    error_code: str | None = None
    error_detail: str | None = Field(default=None, max_length=500)

    @field_validator("timestamp_utc")
    @classmethod
    def timestamp_is_utc(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamp_utc must be an ISO-8601 timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
            raise ValueError("timestamp_utc must include a UTC offset")
        return value

    @model_validator(mode="after")
    def status_is_internally_consistent(
        self,
    ) -> "RecordedTranscriptionResultV1":
        if self.requested_model_alias != NEMOTRON_SPEECH_ALIAS:
            raise ValueError("the V1 worker permits only the approved Nemotron alias")
        if self.transcript_backend != NEMOTRON_TRANSCRIPT_BACKEND:
            raise ValueError("unexpected transcript backend")
        if self.error_code and not ERROR_CODE_PATTERN.fullmatch(self.error_code):
            raise ValueError("error_code must be a stable uppercase identifier")

        text = self.transcript_text.strip() if self.transcript_text else ""
        if self.transcript_status in (
            TranscriptStatus.READY,
            TranscriptStatus.PARTIAL,
        ):
            if not text:
                raise ValueError("ready or partial transcription requires text")
            if self.error_code is not None and self.transcript_status is TranscriptStatus.READY:
                raise ValueError("ready transcription cannot contain an error code")
        elif text:
            raise ValueError("non-transcript status cannot contain transcript text")

        if self.transcript_status in (
            TranscriptStatus.BACKEND_UNAVAILABLE,
            TranscriptStatus.FAILED,
        ) and not self.error_code:
            raise ValueError("unavailable or failed transcription requires error_code")
        if self.transcript_status is TranscriptStatus.EMPTY and (
            self.error_code != "TRANSCRIPT_EMPTY"
        ):
            raise ValueError("empty transcription requires TRANSCRIPT_EMPTY")
        if self.transcript_status in (
            TranscriptStatus.READY,
            TranscriptStatus.PARTIAL,
            TranscriptStatus.EMPTY,
        ):
            if self.resolved_model_id != NEMOTRON_SPEECH_MODEL_ID:
                raise ValueError("completed transcription requires the qualified model ID")
            if not (self.model_loaded_before or self.model_loaded_for_request):
                raise ValueError("completed transcription requires an observed loaded model")
        return self


class RecordedAudioValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RecordedSpeechClientConfiguration:
    repository_root: Path
    speech_python_executable: Path
    process_timeout_seconds: float = DEFAULT_PROCESS_TIMEOUT_SECONDS
    max_audio_bytes: int = DEFAULT_MAX_AUDIO_BYTES
    max_audio_seconds: float = DEFAULT_MAX_AUDIO_SECONDS
    allow_model_download: bool = False
    unload_after_request: bool = True
    temporary_root: Path | None = None

    def __post_init__(self) -> None:
        if self.process_timeout_seconds <= 0:
            raise ValueError("process_timeout_seconds must be positive")
        if self.max_audio_bytes <= 0:
            raise ValueError("max_audio_bytes must be positive")
        if self.max_audio_seconds <= 0:
            raise ValueError("max_audio_seconds must be positive")


ProcessRunner = Callable[..., subprocess.CompletedProcess[Any]]


class NemotronRecordedAudioClient:
    """Validate WAV input and invoke the SDK in a killable child process."""

    def __init__(
        self,
        configuration: RecordedSpeechClientConfiguration,
        *,
        process_runner: ProcessRunner | None = None,
        clock: Callable[[], datetime] | None = None,
        timer: Callable[[], float] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.configuration = configuration
        self._process_runner = process_runner or subprocess.run
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timer = timer or time.perf_counter
        self._id_factory = id_factory or (lambda: str(uuid4()))

    @property
    def is_worker_configured(self) -> bool:
        return self.configuration.speech_python_executable.is_file()

    def transcribe_wav(
        self,
        audio_bytes: bytes,
        *,
        original_filename: str,
    ) -> RecordedTranscriptionResultV1:
        transcription_id = self._id_factory()
        timestamp = self._clock().isoformat().replace("+00:00", "Z")
        try:
            metadata = inspect_wav_bytes(
                audio_bytes,
                original_filename=original_filename,
                max_audio_bytes=self.configuration.max_audio_bytes,
                max_audio_seconds=self.configuration.max_audio_seconds,
            )
        except RecordedAudioValidationError as exc:
            return _validation_failure_result(
                audio_bytes,
                original_filename=original_filename,
                transcription_id=transcription_id,
                timestamp_utc=timestamp,
                error_code=exc.code,
                error_detail=str(exc),
            )

        if not self.is_worker_configured:
            return _base_result(
                metadata,
                transcription_id=transcription_id,
                timestamp_utc=timestamp,
                transcript_status=TranscriptStatus.BACKEND_UNAVAILABLE,
                error_code="VOICE_BACKEND_UNAVAILABLE",
                error_detail="Configured speech Python executable was not found.",
            )

        started = self._timer()
        temp_parent = self.configuration.temporary_root
        if temp_parent is not None:
            temp_parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(
            prefix="prototype5-speech-",
            dir=temp_parent,
        ) as temporary_directory:
            temporary_path = Path(temporary_directory)
            audio_path = temporary_path / "recording.wav"
            result_path = temporary_path / "transcription-result.json"
            audio_path.write_bytes(audio_bytes)

            command = [
                str(self.configuration.speech_python_executable),
                "-m",
                "src.prototype5.nemotron_speech_worker",
                "--audio-path",
                str(audio_path),
                "--result-path",
                str(result_path),
                "--model-alias",
                NEMOTRON_SPEECH_ALIAS,
                "--expected-model-id",
                NEMOTRON_SPEECH_MODEL_ID,
            ]
            if self.configuration.allow_model_download:
                command.append("--allow-model-download")
            if self.configuration.unload_after_request:
                command.append("--unload-after-request")

            try:
                completed = self._process_runner(
                    command,
                    cwd=self.configuration.repository_root,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=self.configuration.process_timeout_seconds,
                    env=_speech_worker_environment(os.environ),
                )
            except subprocess.TimeoutExpired:
                return _base_result(
                    metadata,
                    transcription_id=transcription_id,
                    timestamp_utc=timestamp,
                    transcript_status=TranscriptStatus.FAILED,
                    transcription_latency_ms=(
                        self._timer() - started
                    )
                    * 1000,
                    error_code="TRANSCRIPTION_TIMEOUT",
                    error_detail="The isolated speech worker exceeded its deadline.",
                )
            except OSError as exc:
                return _base_result(
                    metadata,
                    transcription_id=transcription_id,
                    timestamp_utc=timestamp,
                    transcript_status=TranscriptStatus.BACKEND_UNAVAILABLE,
                    transcription_latency_ms=(
                        self._timer() - started
                    )
                    * 1000,
                    error_code="VOICE_BACKEND_UNAVAILABLE",
                    error_detail=_sanitise_error(str(exc)),
                )

            if not result_path.is_file():
                return _base_result(
                    metadata,
                    transcription_id=transcription_id,
                    timestamp_utc=timestamp,
                    transcript_status=TranscriptStatus.FAILED,
                    transcription_latency_ms=(
                        self._timer() - started
                    )
                    * 1000,
                    error_code="SPEECH_WORKER_FAILED",
                    error_detail=(
                        f"Speech worker exited with code {completed.returncode} "
                        "without a typed result."
                    ),
                )

            if result_path.stat().st_size > DEFAULT_MAX_WORKER_RESULT_BYTES:
                return _base_result(
                    metadata,
                    transcription_id=transcription_id,
                    timestamp_utc=timestamp,
                    transcript_status=TranscriptStatus.FAILED,
                    transcription_latency_ms=(self._timer() - started) * 1000,
                    error_code="SPEECH_WORKER_RESULT_TOO_LARGE",
                    error_detail="Speech worker result exceeded the bounded result size.",
                )

            try:
                result = RecordedTranscriptionResultV1.model_validate_json(
                    result_path.read_text(encoding="utf-8")
                )
            except Exception as exc:
                return _base_result(
                    metadata,
                    transcription_id=transcription_id,
                    timestamp_utc=timestamp,
                    transcript_status=TranscriptStatus.FAILED,
                    transcription_latency_ms=(
                        self._timer() - started
                    )
                    * 1000,
                    error_code="SPEECH_WORKER_INVALID_RESULT",
                    error_detail=_sanitise_error(str(exc)),
                )

            if (
                completed.returncode != 0
                and result.transcript_status
                not in (
                    TranscriptStatus.BACKEND_UNAVAILABLE,
                    TranscriptStatus.FAILED,
                )
            ):
                return _base_result(
                    metadata,
                    transcription_id=transcription_id,
                    timestamp_utc=timestamp,
                    transcript_status=TranscriptStatus.FAILED,
                    transcription_latency_ms=(
                        self._timer() - started
                    )
                    * 1000,
                    error_code="SPEECH_WORKER_EXIT_MISMATCH",
                    error_detail=(
                        "Speech worker returned a successful result with "
                        f"exit code {completed.returncode}."
                    ),
                )
            if not _audio_provenance_matches(result.audio, metadata):
                return _base_result(
                    metadata,
                    transcription_id=transcription_id,
                    timestamp_utc=timestamp,
                    transcript_status=TranscriptStatus.FAILED,
                    transcription_latency_ms=(
                        self._timer() - started
                    )
                    * 1000,
                    error_code="SPEECH_WORKER_PROVENANCE_MISMATCH",
                    error_detail="Worker audio identity did not match submitted audio.",
                )
            return RecordedTranscriptionResultV1.model_validate(
                result.model_copy(
                    update={
                        "transcription_id": transcription_id,
                        "timestamp_utc": timestamp,
                        "audio": metadata,
                    }
                ).model_dump()
            )


def inspect_wav_bytes(
    audio_bytes: bytes,
    *,
    original_filename: str,
    max_audio_bytes: int = DEFAULT_MAX_AUDIO_BYTES,
    max_audio_seconds: float = DEFAULT_MAX_AUDIO_SECONDS,
) -> RecordedAudioMetadataV1:
    filename = Path(original_filename).name or "recording.wav"
    if Path(original_filename).name != original_filename:
        raise RecordedAudioValidationError(
            "AUDIO_FILENAME_INVALID",
            "Audio filename must not contain a path.",
        )
    if len(filename) > 255 or any(ord(character) < 32 for character in filename):
        raise RecordedAudioValidationError(
            "AUDIO_FILENAME_INVALID",
            "Audio filename is invalid.",
        )
    if not filename.lower().endswith(".wav"):
        raise RecordedAudioValidationError(
            "AUDIO_FORMAT_UNSUPPORTED",
            "Recorded Nemotron V1 accepts WAV input only.",
        )
    if not audio_bytes:
        raise RecordedAudioValidationError(
            "AUDIO_EMPTY",
            "Audio payload is empty.",
        )
    if len(audio_bytes) > max_audio_bytes:
        raise RecordedAudioValidationError(
            "AUDIO_TOO_LARGE",
            f"Audio payload exceeds the {max_audio_bytes}-byte limit.",
        )

    try:
        with wave.open(BytesIO(audio_bytes), "rb") as wav_file:
            if wav_file.getcomptype() != "NONE":
                raise RecordedAudioValidationError(
                    "AUDIO_ENCODING_UNSUPPORTED",
                    "WAV input must contain uncompressed PCM audio.",
                )
            sample_rate = wav_file.getframerate()
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            frame_count = wav_file.getnframes()
            pcm = wav_file.readframes(frame_count)
    except RecordedAudioValidationError:
        raise
    except (EOFError, wave.Error) as exc:
        raise RecordedAudioValidationError(
            "AUDIO_WAV_INVALID",
            "Audio payload is not a valid WAV container.",
        ) from exc

    if sample_rate != 16000 or channels != 1 or sample_width != 2:
        raise RecordedAudioValidationError(
            "AUDIO_FORMAT_UNSUPPORTED",
            "WAV input must be 16 kHz, mono, signed 16-bit PCM.",
        )
    if frame_count <= 0:
        raise RecordedAudioValidationError(
            "AUDIO_EMPTY",
            "WAV input contains no audio frames.",
        )
    expected_pcm_bytes = frame_count * channels * sample_width
    if len(pcm) != expected_pcm_bytes:
        raise RecordedAudioValidationError(
            "AUDIO_WAV_TRUNCATED",
            "WAV frame data is truncated.",
        )
    duration_seconds = frame_count / sample_rate
    if duration_seconds > max_audio_seconds:
        raise RecordedAudioValidationError(
            "AUDIO_TOO_LONG",
            f"Audio duration exceeds the {max_audio_seconds:g}-second limit.",
        )

    return RecordedAudioMetadataV1(
        original_filename=filename,
        audio_sha256=hashlib.sha256(audio_bytes).hexdigest(),
        audio_bytes=len(audio_bytes),
        sample_rate_hz=sample_rate,
        channels=channels,
        bits_per_sample=sample_width * 8,
        frame_count=frame_count,
        duration_ms=duration_seconds * 1000,
    )


def _base_result(
    metadata: RecordedAudioMetadataV1,
    *,
    transcription_id: str,
    timestamp_utc: str,
    transcript_status: TranscriptStatus,
    transcript_text: str | None = None,
    transcription_latency_ms: float | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
    **updates: Any,
) -> RecordedTranscriptionResultV1:
    return RecordedTranscriptionResultV1(
        transcription_id=transcription_id,
        timestamp_utc=timestamp_utc,
        transcript_status=transcript_status,
        transcript_text=transcript_text,
        audio=metadata,
        transcription_latency_ms=transcription_latency_ms,
        error_code=error_code,
        error_detail=error_detail,
        **updates,
    )


def _validation_failure_result(
    audio_bytes: bytes,
    *,
    original_filename: str,
    transcription_id: str,
    timestamp_utc: str,
    error_code: str,
    error_detail: str,
) -> RecordedTranscriptionResultV1:
    filename = Path(original_filename).name or "recording.wav"
    placeholder = RecordedAudioMetadataV1(
        original_filename=filename,
        audio_sha256=hashlib.sha256(audio_bytes).hexdigest(),
        audio_bytes=len(audio_bytes),
        sample_rate_hz=0,
        channels=0,
        bits_per_sample=0,
        frame_count=0,
        duration_ms=0,
    )
    return _base_result(
        placeholder,
        transcription_id=transcription_id,
        timestamp_utc=timestamp_utc,
        transcript_status=TranscriptStatus.FAILED,
        error_code=error_code,
        error_detail=error_detail,
    )


def _speech_worker_environment(
    source: Mapping[str, str],
) -> dict[str, str]:
    allowed = (
        "SYSTEMROOT",
        "WINDIR",
        "PATH",
        "PATHEXT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "APPDATA",
    )
    environment = {key: source[key] for key in allowed if key in source}
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUTF8": "1",
        }
    )
    return environment


def _audio_provenance_matches(
    worker: RecordedAudioMetadataV1,
    submitted: RecordedAudioMetadataV1,
) -> bool:
    return (
        worker.audio_sha256 == submitted.audio_sha256
        and worker.audio_bytes == submitted.audio_bytes
        and worker.sample_rate_hz == submitted.sample_rate_hz
        and worker.channels == submitted.channels
        and worker.bits_per_sample == submitted.bits_per_sample
        and worker.frame_count == submitted.frame_count
        and worker.duration_ms == submitted.duration_ms
    )


def _sanitise_error(value: str) -> str:
    compact = " ".join(value.split())
    home = str(Path.home())
    compact = re.sub(re.escape(home), "<USER_PROFILE>", compact, flags=re.I)
    compact = re.sub(
        r"(?i)(?:[a-z]:\\|/)(?:[^\s:]+[\\/])+[^\s:]*",
        "<PATH>",
        compact,
    )
    return compact[:500]

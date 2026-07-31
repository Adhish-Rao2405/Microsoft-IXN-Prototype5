from __future__ import annotations

import json
import subprocess
import sys
import wave
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.prototype5.governance_contract_v2 import TranscriptStatus
from src.prototype5.nemotron_speech_worker import (
    FoundrySdkSurface,
    SpeechWorkerError,
    WorkerConfiguration,
    _reconstruct_segments,
    run_transcription_worker,
    transcribe_wav_live,
)
from src.prototype5.recorded_speech import (
    DEFAULT_MAX_TRANSCRIPT_SEGMENTS,
    DEFAULT_MAX_WORKER_RESULT_BYTES,
    NEMOTRON_SPEECH_ALIAS,
    NEMOTRON_SPEECH_MODEL_ID,
    NemotronRecordedAudioClient,
    RecordedAudioValidationError,
    RecordedSpeechClientConfiguration,
    RecordedTranscriptionResultV1,
    inspect_wav_bytes,
)


FIXED_TIME = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)


def wav_bytes(
    *,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
    frame_count: int = 1600,
) -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00" * frame_count * channels * sample_width)
    return output.getvalue()


def client(
    tmp_path: Path,
    *,
    process_runner=None,
    speech_python: Path | None = None,
    timeout: float = 10,
) -> NemotronRecordedAudioClient:
    return NemotronRecordedAudioClient(
        RecordedSpeechClientConfiguration(
            repository_root=tmp_path,
            speech_python_executable=speech_python or Path(sys.executable),
            process_timeout_seconds=timeout,
            temporary_root=tmp_path / "worker-temp",
        ),
        process_runner=process_runner,
        clock=lambda: FIXED_TIME,
        timer=lambda: 10.0,
        id_factory=lambda: "transcription-test-id",
    )


def test_wav_inspection_records_exact_audio_identity():
    payload = wav_bytes()

    metadata = inspect_wav_bytes(
        payload,
        original_filename="sample.wav",
    )

    assert metadata.original_filename == "sample.wav"
    assert metadata.audio_bytes == len(payload)
    assert metadata.sample_rate_hz == 16000
    assert metadata.channels == 1
    assert metadata.bits_per_sample == 16
    assert metadata.frame_count == 1600
    assert metadata.duration_ms == 100
    assert len(metadata.audio_sha256) == 64


@pytest.mark.parametrize(
    ("payload", "filename", "code"),
    [
        (b"", "sample.wav", "AUDIO_EMPTY"),
        (b"not-wave", "sample.wav", "AUDIO_WAV_INVALID"),
        (wav_bytes(sample_rate=44100), "sample.wav", "AUDIO_FORMAT_UNSUPPORTED"),
        (wav_bytes(), "../sample.wav", "AUDIO_FILENAME_INVALID"),
        (wav_bytes(), "sample.m4a", "AUDIO_FORMAT_UNSUPPORTED"),
        (wav_bytes()[:-10], "sample.wav", "AUDIO_WAV_TRUNCATED"),
        (wav_bytes(), f"{'a' * 252}.wav", "AUDIO_FILENAME_INVALID"),
    ],
)
def test_invalid_audio_fails_before_worker_process(
    tmp_path,
    payload,
    filename,
    code,
):
    calls = []

    result = client(
        tmp_path,
        process_runner=lambda *args, **kwargs: calls.append((args, kwargs)),
    ).transcribe_wav(payload, original_filename=filename)

    assert result.transcript_status is TranscriptStatus.FAILED
    assert result.error_code == code
    assert calls == []


def test_wav_size_and_duration_limits_are_enforced():
    payload = wav_bytes(frame_count=3200)

    with pytest.raises(RecordedAudioValidationError, match="byte limit") as size:
        inspect_wav_bytes(
            payload,
            original_filename="sample.wav",
            max_audio_bytes=len(payload) - 1,
        )
    with pytest.raises(RecordedAudioValidationError, match="duration") as duration:
        inspect_wav_bytes(
            payload,
            original_filename="sample.wav",
            max_audio_seconds=0.1,
        )

    assert size.value.code == "AUDIO_TOO_LARGE"
    assert duration.value.code == "AUDIO_TOO_LONG"


def test_missing_speech_interpreter_is_explicitly_unavailable(tmp_path):
    result = client(
        tmp_path,
        speech_python=tmp_path / "missing-python.exe",
    ).transcribe_wav(wav_bytes(), original_filename="sample.wav")

    assert result.transcript_status is TranscriptStatus.BACKEND_UNAVAILABLE
    assert result.error_code == "VOICE_BACKEND_UNAVAILABLE"
    assert result.transcript_text is None


def test_subprocess_result_is_verified_and_temporary_audio_is_removed(
    tmp_path,
    monkeypatch,
):
    observed_audio_path = None

    def fake_process(command, **kwargs):
        nonlocal observed_audio_path
        assert "OPENAI_API_KEY" not in kwargs["env"]
        assert kwargs["stdout"] is subprocess.DEVNULL
        assert kwargs["stderr"] is subprocess.DEVNULL
        assert "capture_output" not in kwargs
        audio_path = Path(command[command.index("--audio-path") + 1])
        result_path = Path(command[command.index("--result-path") + 1])
        observed_audio_path = audio_path
        metadata = inspect_wav_bytes(
            audio_path.read_bytes(),
            original_filename=audio_path.name,
        )
        worker_result = RecordedTranscriptionResultV1(
            transcription_id="worker-id",
            timestamp_utc="2026-07-31T11:59:00Z",
            transcript_status="READY",
            transcript_text="Move the blue component.",
            audio=metadata,
            resolved_model_id=NEMOTRON_SPEECH_MODEL_ID,
            sdk_version="1.2.3",
            core_version="1.2.3",
            model_cached_before=True,
            model_loaded_for_request=True,
            model_unloaded_after_request=True,
            segment_count=1,
            transcription_latency_ms=250,
        )
        result_path.write_text(
            worker_result.model_dump_json(),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setenv("OPENAI_API_KEY", "must-not-enter-worker")
    result = client(
        tmp_path,
        process_runner=fake_process,
    ).transcribe_wav(wav_bytes(), original_filename="operator.wav")

    assert result.transcript_status is TranscriptStatus.READY
    assert result.transcript_text == "Move the blue component."
    assert result.transcription_id == "transcription-test-id"
    assert result.timestamp_utc == "2026-07-31T12:00:00Z"
    assert result.audio.original_filename == "operator.wav"
    assert observed_audio_path is not None
    assert not observed_audio_path.exists()
    assert list((tmp_path / "worker-temp").iterdir()) == []


def test_oversized_worker_result_is_rejected_before_json_parsing(tmp_path):
    def fake_process(command, **kwargs):
        result_path = Path(command[command.index("--result-path") + 1])
        result_path.write_bytes(b"{" + b" " * DEFAULT_MAX_WORKER_RESULT_BYTES)
        return subprocess.CompletedProcess(command, 0)

    result = client(tmp_path, process_runner=fake_process).transcribe_wav(
        wav_bytes(),
        original_filename="operator.wav",
    )

    assert result.transcript_status is TranscriptStatus.FAILED
    assert result.error_code == "SPEECH_WORKER_RESULT_TOO_LARGE"


def test_worker_timeout_is_fail_closed_and_removes_temporary_audio(tmp_path):
    def timed_out(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    result = client(
        tmp_path,
        process_runner=timed_out,
    ).transcribe_wav(wav_bytes(), original_filename="operator.wav")

    assert result.transcript_status is TranscriptStatus.FAILED
    assert result.error_code == "TRANSCRIPTION_TIMEOUT"
    assert result.transcript_text is None
    assert list((tmp_path / "worker-temp").iterdir()) == []


class FakeModel:
    def __init__(self, *, cached: bool, loaded: bool = False) -> None:
        self.id = NEMOTRON_SPEECH_MODEL_ID
        self.is_cached = cached
        self.is_loaded = loaded
        self.info = SimpleNamespace(
            runtime=SimpleNamespace(execution_provider="CPUExecutionProvider")
        )
        self.download_calls = 0
        self.load_calls = 0
        self.audio_client_calls = 0
        self.unload_calls = 0

    def download(self):
        self.download_calls += 1
        self.is_cached = True

    def load(self):
        self.load_calls += 1
        self.is_loaded = True

    def get_audio_client(self):
        self.audio_client_calls += 1
        return object()

    def unload(self):
        self.unload_calls += 1
        self.is_loaded = False


def sdk_surface(model: FakeModel) -> FoundrySdkSurface:
    manager = SimpleNamespace(
        catalog=SimpleNamespace(
            get_model=lambda alias: (
                model if alias == NEMOTRON_SPEECH_ALIAS else None
            )
        )
    )

    class ManagerType:
        instance = manager

        @staticmethod
        def initialize(configuration):
            raise AssertionError("existing manager must be reused")

    return FoundrySdkSurface(
        configuration_type=lambda **kwargs: kwargs,
        manager_type=ManagerType,
        sdk_version="1.2.3",
        core_version="1.2.3",
    )


def test_worker_does_not_download_or_load_when_model_is_not_cached(tmp_path):
    audio_path = tmp_path / "recording.wav"
    audio_path.write_bytes(wav_bytes())
    model = FakeModel(cached=False)

    result = run_transcription_worker(
        audio_path,
        WorkerConfiguration(allow_model_download=False),
        sdk_surface=sdk_surface(model),
    )

    assert result.transcript_status is TranscriptStatus.BACKEND_UNAVAILABLE
    assert result.error_code == "NEMOTRON_MODEL_NOT_CACHED"
    assert model.download_calls == 0
    assert model.load_calls == 0
    assert model.audio_client_calls == 0
    assert model.unload_calls == 0


def test_worker_download_load_transcribe_and_unload_are_separate(
    tmp_path,
    monkeypatch,
):
    audio_path = tmp_path / "recording.wav"
    audio_path.write_bytes(wav_bytes())
    model = FakeModel(cached=False)
    transcribe_calls = []

    def fake_transcribe(audio_client, path, **kwargs):
        transcribe_calls.append((audio_client, path, kwargs))
        return "Move the blue component.", 1, True

    monkeypatch.setattr(
        "src.prototype5.nemotron_speech_worker.transcribe_wav_live",
        fake_transcribe,
    )
    result = run_transcription_worker(
        audio_path,
        WorkerConfiguration(allow_model_download=True),
        sdk_surface=sdk_surface(model),
    )

    assert result.transcript_status is TranscriptStatus.READY
    assert result.transcript_text == "Move the blue component."
    assert result.resolved_model_id == NEMOTRON_SPEECH_MODEL_ID
    assert result.execution_provider == "CPUExecutionProvider"
    assert result.model_cached_before is False
    assert result.model_loaded_before is False
    assert result.model_downloaded_for_request is True
    assert result.model_loaded_for_request is True
    assert result.model_unloaded_after_request is True
    assert model.download_calls == 1
    assert model.load_calls == 1
    assert model.audio_client_calls == 1
    assert model.unload_calls == 1
    assert len(transcribe_calls) == 1


def test_worker_preserves_preloaded_model_without_unloading(tmp_path, monkeypatch):
    audio_path = tmp_path / "recording.wav"
    audio_path.write_bytes(wav_bytes())
    model = FakeModel(cached=True, loaded=True)
    monkeypatch.setattr(
        "src.prototype5.nemotron_speech_worker.transcribe_wav_live",
        lambda *args, **kwargs: ("Move the blue component.", 1, True),
    )

    result = run_transcription_worker(
        audio_path,
        WorkerConfiguration(),
        sdk_surface=sdk_surface(model),
    )

    assert result.transcript_status is TranscriptStatus.READY
    assert result.model_loaded_before is True
    assert result.model_loaded_for_request is False
    assert result.model_unloaded_after_request is False
    assert model.load_calls == 0
    assert model.unload_calls == 0


def test_worker_configuration_rejects_unapproved_identity_and_timeout():
    with pytest.raises(ValueError, match="approved Nemotron alias"):
        WorkerConfiguration(model_alias="other-speech-model")
    with pytest.raises(ValueError, match="qualified Nemotron model ID"):
        WorkerConfiguration(expected_model_id="other-model:1")
    with pytest.raises(ValueError, match="must be positive"):
        WorkerConfiguration(pusher_join_timeout_seconds=0)


def test_worker_rejects_unexpected_resolved_model_id(tmp_path):
    audio_path = tmp_path / "recording.wav"
    audio_path.write_bytes(wav_bytes())
    model = FakeModel(cached=True)
    model.id = "unexpected-model:1"

    result = run_transcription_worker(
        audio_path,
        WorkerConfiguration(),
        sdk_surface=sdk_surface(model),
    )

    assert result.transcript_status is TranscriptStatus.BACKEND_UNAVAILABLE
    assert result.error_code == "NEMOTRON_MODEL_ID_MISMATCH"
    assert model.load_calls == 0


@pytest.mark.parametrize(
    ("worker_output", "expected_status", "expected_error"),
    [
        (("Move the blue component.", 2, False), "PARTIAL", "TRANSCRIPTION_PARTIAL"),
        (("", 0, False), "EMPTY", "TRANSCRIPT_EMPTY"),
    ],
)
def test_worker_preserves_partial_and_empty_transcript_states(
    tmp_path,
    monkeypatch,
    worker_output,
    expected_status,
    expected_error,
):
    audio_path = tmp_path / "recording.wav"
    audio_path.write_bytes(wav_bytes())
    model = FakeModel(cached=True)
    monkeypatch.setattr(
        "src.prototype5.nemotron_speech_worker.transcribe_wav_live",
        lambda *args, **kwargs: worker_output,
    )

    result = run_transcription_worker(
        audio_path,
        WorkerConfiguration(),
        sdk_surface=sdk_surface(model),
    )

    assert result.transcript_status.value == expected_status
    assert result.error_code == expected_error
    assert model.unload_calls == 1


def test_live_session_receives_exact_pcm_format_and_returns_real_segments(
    tmp_path,
):
    audio_path = tmp_path / "recording.wav"
    audio_path.write_bytes(wav_bytes(frame_count=3200))

    class Content:
        def __init__(self, text):
            self.text = text
            self.transcript = text

    class Response:
        def __init__(self, text, *, is_final):
            self.content = [Content(text)]
            self.is_final = is_final

    class Session:
        def __init__(self):
            self.settings = SimpleNamespace()
            self.started = False
            self.stopped = False
            self.chunks = []

        def start(self):
            self.started = True

        def append(self, chunk):
            self.chunks.append(bytes(chunk))

        def stop(self):
            self.stopped = True

        def get_stream(self):
            yield Response("Move the blue compon", is_final=False)
            yield Response("ent.", is_final=False)
            yield Response("Move the blue component.", is_final=True)

    session = Session()
    audio_client = SimpleNamespace(
        create_live_transcription_session=lambda: session
    )

    transcript, count, complete = transcribe_wav_live(
        audio_client,
        audio_path,
        language="en",
        pusher_join_timeout_seconds=1,
    )

    assert transcript == "Move the blue component."
    assert count == 3
    assert complete is True
    assert session.started is True
    assert session.stopped is True
    assert session.settings.sample_rate == 16000
    assert session.settings.channels == 1
    assert session.settings.bits_per_sample == 16
    assert session.settings.language == "en"
    assert b"".join(session.chunks) == b"\x00" * 3200 * 2


def test_live_session_marks_nonfinal_output_as_partial(tmp_path):
    audio_path = tmp_path / "recording.wav"
    audio_path.write_bytes(wav_bytes())

    class Session:
        settings = SimpleNamespace()

        def start(self):
            pass

        def append(self, chunk):
            pass

        def stop(self):
            pass

        def get_stream(self):
            yield SimpleNamespace(
                is_final=False,
                content=[SimpleNamespace(text="Move the blue compon")],
            )
            yield SimpleNamespace(
                is_final=False,
                content=[SimpleNamespace(text="ent.")],
            )

    transcript, count, complete = transcribe_wav_live(
        SimpleNamespace(
            create_live_transcription_session=lambda: Session()
        ),
        audio_path,
        language="en",
        pusher_join_timeout_seconds=1,
    )

    assert transcript == "Move the blue component."
    assert count == 2
    assert complete is False


def test_segment_reconstruction_deduplicates_cumulative_final_results():
    assert _reconstruct_segments(
        [
            "Move the blue component",
            "Move the blue component",
            "Move the blue component to fixture B.",
        ],
        join_fragments=False,
    ) == "Move the blue component to fixture B."


def test_live_session_rejects_unbounded_segment_count(tmp_path):
    audio_path = tmp_path / "recording.wav"
    audio_path.write_bytes(wav_bytes())

    class Session:
        settings = SimpleNamespace()

        def start(self):
            pass

        def append(self, chunk):
            pass

        def stop(self):
            pass

        def get_stream(self):
            for _ in range(DEFAULT_MAX_TRANSCRIPT_SEGMENTS + 1):
                yield SimpleNamespace(
                    is_final=False,
                    content=[SimpleNamespace(text="x")],
                )

    with pytest.raises(SpeechWorkerError, match="too many transcript segments"):
        transcribe_wav_live(
            SimpleNamespace(
                create_live_transcription_session=lambda: Session()
            ),
            audio_path,
            language="en",
            pusher_join_timeout_seconds=1,
        )

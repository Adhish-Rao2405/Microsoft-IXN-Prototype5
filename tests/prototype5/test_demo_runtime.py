from __future__ import annotations

import math
from pathlib import Path

import pytest

from src.prototype5.demo_runtime import _normal_demo_speech_configuration
from src.prototype5.recorded_speech import RecordedSpeechClientConfiguration


@pytest.mark.parametrize("setting", [None, "", "0"])
def test_normal_demo_disables_model_download_for_permitted_settings(
    tmp_path,
    monkeypatch,
    setting,
):
    if setting is None:
        monkeypatch.delenv("PROTOTYPE5_SPEECH_ALLOW_MODEL_DOWNLOAD", raising=False)
    else:
        monkeypatch.setenv("PROTOTYPE5_SPEECH_ALLOW_MODEL_DOWNLOAD", setting)

    configuration = _normal_demo_speech_configuration(tmp_path)

    assert configuration.allow_model_download is False


@pytest.mark.parametrize(
    "setting",
    ["1", "true", "True", "yes", "01", "false", " ", "malformed"],
)
def test_normal_demo_rejects_every_other_download_setting(
    tmp_path,
    monkeypatch,
    setting,
):
    monkeypatch.setenv("PROTOTYPE5_SPEECH_ALLOW_MODEL_DOWNLOAD", setting)

    with pytest.raises(ValueError, match="must be unset, empty, or 0"):
        _normal_demo_speech_configuration(tmp_path)


def test_explicit_acquisition_capability_remains_outside_normal_composition(
    tmp_path,
):
    configuration = RecordedSpeechClientConfiguration(
        repository_root=tmp_path,
        speech_python_executable=Path("qualified-speech-python.exe"),
        allow_model_download=True,
    )

    assert configuration.allow_model_download is True


@pytest.mark.parametrize(
    "timeout",
    ["0", "-1", "nan", "inf", "-inf", "120.1"],
)
def test_normal_demo_timeout_reaches_strict_client_validation(
    tmp_path,
    monkeypatch,
    timeout,
):
    monkeypatch.delenv("PROTOTYPE5_SPEECH_ALLOW_MODEL_DOWNLOAD", raising=False)
    monkeypatch.setenv("PROTOTYPE5_SPEECH_TIMEOUT_SECONDS", timeout)

    with pytest.raises(ValueError, match="finite number between 1 and 120"):
        _normal_demo_speech_configuration(tmp_path)


@pytest.mark.parametrize("timeout", ["1", "120"])
def test_normal_demo_timeout_accepts_exact_boundaries(
    tmp_path,
    monkeypatch,
    timeout,
):
    monkeypatch.delenv("PROTOTYPE5_SPEECH_ALLOW_MODEL_DOWNLOAD", raising=False)
    monkeypatch.setenv("PROTOTYPE5_SPEECH_TIMEOUT_SECONDS", timeout)

    configuration = _normal_demo_speech_configuration(tmp_path)

    assert math.isfinite(configuration.process_timeout_seconds)
    assert configuration.process_timeout_seconds == float(timeout)

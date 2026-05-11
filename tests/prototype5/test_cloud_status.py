from src.prototype5.cloud_status import NOT_RUN_API_KEY_MISSING, READY, get_cloud_status


def test_missing_api_key_produces_not_run_api_key_missing():
    status = get_cloud_status({})
    assert status["cloud_available"] is False
    assert status["cloud_baseline_status"] == NOT_RUN_API_KEY_MISSING
    assert status["provider"] == "openai"


def test_present_api_key_is_ready_without_exposing_secret():
    status = get_cloud_status({"OPENAI_API_KEY": "secret-value"})
    assert status["cloud_available"] is True
    assert status["cloud_baseline_status"] == READY
    assert "secret-value" not in str(status)

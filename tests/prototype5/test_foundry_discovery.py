import json

from src.prototype5 import foundry_discovery


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_discover_foundry_models_detects_phi(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse(
            {
                "data": [
                    {"id": "qwen2.5-cpu"},
                    {"id": "Phi-3-mini-4k-instruct-generic-cpu:3"},
                ]
            }
        )

    monkeypatch.setattr(foundry_discovery, "urlopen", fake_urlopen)
    inventory = foundry_discovery.discover_foundry_models("http://127.0.0.1:49313")

    assert inventory["request_success"] is True
    assert inventory["phi_model_ids"] == ["Phi-3-mini-4k-instruct-generic-cpu:3"]


def test_discover_foundry_models_handles_unavailable_service(monkeypatch):
    def fake_urlopen(request, timeout):
        raise OSError("service unavailable")

    monkeypatch.setattr(foundry_discovery, "urlopen", fake_urlopen)
    inventory = foundry_discovery.discover_foundry_models("http://127.0.0.1:49313")

    assert inventory["request_success"] is False
    assert inventory["phi_model_ids"] == []


def test_select_phi_model_prefers_phi_environment_model(monkeypatch):
    monkeypatch.setenv("FOUNDRY_LOCAL_MODEL", "Phi-3-mini-4k-instruct-generic-cpu:3")
    selected = foundry_discovery.select_phi_model({"phi_model_ids": ["other-phi"]})
    assert selected == "Phi-3-mini-4k-instruct-generic-cpu:3"

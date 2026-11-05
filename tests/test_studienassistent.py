from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chatsec.llm import ModelUnavailable
from chatsec.target import load_target
from fakes import FakeChatModel
from studienassistent import __main__ as entry
from studienassistent.app import create_app
from studienassistent.prompts import build_system_prompt

SETTINGS = {"documents": "DOKUMENTE-TEXT", "solution": "LOESUNG-TEXT", "canary": "CANARY-XYZ"}
ROOT = Path(__file__).resolve().parent.parent


def make_client(replies=None):
    model = FakeChatModel(replies or ["Hallo"])
    return TestClient(create_app(model, SETTINGS)), model


def test_openai_shape():
    client, model = make_client(["Antwort"])
    body = {
        "model": "stufe-0",
        "messages": [
            {"role": "system", "content": "fremd"},
            {"role": "user", "content": "Frage?"},
        ],
        "seed": 5,
    }
    response = client.post("/v1/chat/completions", json=body)
    assert response.status_code == 200
    data = response.json()
    assert data["id"].startswith("chatcmpl-")
    assert data["object"] == "chat.completion"
    assert isinstance(data["created"], int)
    assert data["model"] == "stufe-0"
    assert data["choices"][0]["message"] == {"role": "assistant", "content": "Antwort"}
    assert data["choices"][0]["finish_reason"] == "stop"
    sent = model.calls[0]["messages"]
    assert [m["role"] for m in sent] == ["system", "user"]
    assert "fremd" not in sent[0]["content"]
    assert "CANARY-XYZ" in sent[0]["content"]
    assert model.calls[0]["seed"] == 5


def test_level0_prompt_has_no_prohibition():
    prompt = build_system_prompt(0, "DOK", "LOES", "CAN")
    assert "DOK" in prompt and "LOES" in prompt and "CAN" in prompt
    assert "nur für Lehrende" in prompt
    lowered = prompt.lower()
    assert "niemals" not in lowered
    assert "nicht verraten" not in lowered


def test_level1_prompt_has_prohibition():
    prompt = build_system_prompt(1, "DOK", "LOES", "CAN")
    assert "DOK" in prompt and "LOES" in prompt and "CAN" in prompt
    assert "niemals" in prompt.lower()


def test_levels_2_and_3_use_level1_prompt_and_others_fail():
    assert build_system_prompt(2, "a", "b", "c") == build_system_prompt(1, "a", "b", "c")
    assert build_system_prompt(3, "a", "b", "c") == build_system_prompt(1, "a", "b", "c")
    with pytest.raises(ValueError):
        build_system_prompt(7, "a", "b", "c")


@pytest.mark.parametrize("level", ["stufe-2", "stufe-3", "gpt-4", ""])
def test_unknown_level_returns_400(level):
    client, _ = make_client()
    response = client.post(
        "/v1/chat/completions",
        json={"model": level, "messages": [{"role": "user", "content": "x"}]},
    )
    assert response.status_code == 400
    assert response.json()["error"]["message"]


def test_model_error_returns_502():
    class Broken:
        def chat(self, messages, **kwargs):
            raise ModelUnavailable("weg")

    client = TestClient(create_app(Broken(), SETTINGS))
    response = client.post(
        "/v1/chat/completions",
        json={"model": "stufe-1", "messages": [{"role": "user", "content": "x"}]},
    )
    assert response.status_code == 502
    assert response.json()["error"]["message"]


def test_models_endpoint_lists_levels():
    client, _ = make_client()
    assert client.get("/v1/models").json() == {
        "object": "list",
        "data": [
            {"id": "stufe-0", "object": "model"},
            {"id": "stufe-1", "object": "model"},
        ],
    }


def test_default_settings_load_from_package_data():
    app = create_app(FakeChatModel(["x"]))
    client = TestClient(app)
    client.post(
        "/v1/chat/completions",
        json={"model": "stufe-0", "messages": [{"role": "user", "content": "x"}]},
    )
    prompt = app.state.model.calls[0]["messages"][0]["content"]
    assert "ZEBRA-42-KX" in prompt and "MUSTER-SYS-7Q" in prompt and "§" in prompt


def test_startup_exits_when_model_missing(monkeypatch, capsys):
    class Missing:
        def __init__(self, *args, **kwargs):
            pass

        def check_available(self):
            raise ModelUnavailable("Bitte zuerst herunterladen mit: ollama pull qwen3.5:9b")

    started = []
    monkeypatch.setattr(entry, "OpenAICompatibleModel", Missing)
    monkeypatch.setattr(entry.uvicorn, "run", lambda *a, **k: started.append(1))
    code = entry.main(["--config", str(ROOT / "config" / "models.toml")])
    assert code == 2
    assert "ollama pull" in capsys.readouterr().err
    assert started == []


def test_startup_runs_server_when_model_available(monkeypatch):
    class Present:
        def __init__(self, *args, **kwargs):
            pass

        def check_available(self):
            return None

    calls = []
    monkeypatch.setattr(entry, "OpenAICompatibleModel", Present)
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **k: calls.append(k))
    code = entry.main(["--port", "8123", "--config", str(ROOT / "config" / "models.toml")])
    assert code == 0
    assert calls == [{"host": "127.0.0.1", "port": 8123}]


@pytest.mark.parametrize("level", [0, 1])
def test_target_files_load(level):
    cfg = load_target(ROOT / "targets" / f"studienassistent-stufe-{level}.toml")
    assert cfg.secret == "ZEBRA-42-KX"
    assert cfg.system_canary == "MUSTER-SYS-7Q"
    assert cfg.solution_file.exists()
    assert cfg.instructions_file is None
    assert f"stufe-{level}" in cfg.body_template

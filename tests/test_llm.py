import json
from pathlib import Path

import httpx
import pytest

from chatsec.llm import (
    ModelResponseError,
    ModelSpec,
    ModelUnavailable,
    OpenAICompatibleModel,
    load_model_config,
)
from fakes import FakeChatModel

BASE = "http://127.0.0.1:11434/v1"


def make_model(handler, **kwargs) -> OpenAICompatibleModel:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAICompatibleModel(BASE, kwargs.pop("model", "qwen3:8b"), client=client, **kwargs)


def reply(content) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_chat_posts_openai_format():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return reply("Hallo")

    model = make_model(handler)
    messages = [{"role": "user", "content": "Hi"}]
    assert model.chat(messages) == "Hallo"
    assert seen["path"] == "/v1/chat/completions"
    assert seen["body"]["model"] == "qwen3:8b"
    assert seen["body"]["messages"] == messages
    assert "seed" not in seen["body"]
    assert "temperature" not in seen["body"]
    assert "response_format" not in seen["body"]


def test_chat_sends_seed_and_temperature_when_given():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return reply("x")

    make_model(handler).chat([], seed=0, temperature=0.0)
    assert seen["body"]["seed"] == 0
    assert seen["body"]["temperature"] == 0.0


def test_chat_sends_json_schema():
    seen = {}
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return reply("{}")

    make_model(handler).chat([], json_schema=schema)
    assert seen["body"]["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "answer", "strict": True, "schema": schema},
    }


def test_chat_sends_reasoning_effort():
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return reply("x")

    make_model(handler).chat([])
    make_model(handler, reasoning_effort=None).chat([])
    assert bodies[0]["reasoning_effort"] == "none"
    assert "reasoning_effort" not in bodies[1]


@pytest.mark.parametrize("content", [None, 5, ["a"]])
def test_chat_rejects_empty_content(content):
    model = make_model(lambda request: reply(content))
    with pytest.raises(ModelResponseError):
        model.chat([])


def test_chat_rejects_missing_content():
    model = make_model(lambda request: httpx.Response(200, json={"choices": []}))
    with pytest.raises(ModelResponseError):
        model.chat([])


def test_chat_http_error_raises_response_error():
    model = make_model(lambda request: httpx.Response(500, text="kaputt"))
    with pytest.raises(ModelResponseError):
        model.chat([])


def test_chat_connection_error_raises_unavailable():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(ModelUnavailable, match="Ollama läuft nicht"):
        make_model(handler).chat([])


def test_embed_returns_vectors_in_input_order():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.3, 0.4]},
                    {"index": 0, "embedding": [0.1, 0.2]},
                ]
            },
        )

    vectors = make_model(handler, model="bge-m3").embed(["a", "b"])
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert seen["path"] == "/v1/embeddings"
    assert seen["body"] == {"model": "bge-m3", "input": ["a", "b"]}


def test_check_available_ok():
    model = make_model(
        lambda request: httpx.Response(200, json={"data": [{"id": "qwen3:8b"}]})
    )
    model.check_available()


def test_check_available_model_missing():
    def handler(request):
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": [{"id": "qwen3:8b"}]})

    model = make_model(handler, model="qwen3:14b")
    with pytest.raises(ModelUnavailable, match="ollama pull qwen3:14b"):
        model.check_available()


def test_check_available_ollama_down():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(ModelUnavailable, match="Ollama läuft nicht"):
        make_model(handler).check_available()


def test_check_available_timeout():
    def handler(request):
        raise httpx.ReadTimeout("slow")

    with pytest.raises(ModelUnavailable, match="Ollama läuft nicht"):
        make_model(handler).check_available()


def test_load_model_config():
    path = Path(__file__).parent.parent / "config" / "models.toml"
    config = load_model_config(path)
    assert set(config) == {"assistant", "judge", "attacker", "embedding", "ci_assistant"}
    assert config["assistant"] == ModelSpec(BASE, "qwen3.5:9b", "none")


def test_fake_chat_model_returns_in_order_and_records():
    fake = FakeChatModel(["a", "b"])
    assert fake.chat([{"role": "user", "content": "x"}], seed=1) == "a"
    assert fake.chat([], json_schema={"type": "object"}, temperature=0.5) == "b"
    assert fake.calls[0] == {
        "messages": [{"role": "user", "content": "x"}],
        "json_schema": None,
        "seed": 1,
        "temperature": None,
    }
    assert fake.calls[1]["json_schema"] == {"type": "object"}
    with pytest.raises(AssertionError, match="only has 2 replies"):
        fake.chat([])

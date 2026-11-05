"""FastAPI app with an OpenAI-compatible chat endpoint."""

import time
import tomllib
import uuid
from importlib import resources

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from chatsec.llm import ChatModel, ModelResponseError, ModelUnavailable
from studienassistent.prompts import build_system_prompt

LEVELS = {"stufe-0": 0, "stufe-1": 1}


class ChatRequest(BaseModel):
    model: str
    messages: list[dict] = []
    seed: int | None = None
    temperature: float | None = None


def _data(name: str) -> str:
    return (resources.files("studienassistent") / "data" / name).read_text(encoding="utf-8")


def load_default_settings() -> dict:
    return {
        "documents": _data("pruefungsordnung.md") + "\n\n" + _data("modulhandbuch.md"),
        "solution": _data("klausur_db1_loesung.md"),
        "canary": tomllib.loads(_data("settings.toml"))["canary"],
    }


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"message": message}})


def create_app(model: ChatModel, level_settings: dict | None = None) -> FastAPI:
    settings = level_settings if level_settings is not None else load_default_settings()
    app = FastAPI(title="Studienassistent")
    app.state.model = model

    @app.get("/v1/models")
    def list_models():
        return {"object": "list", "data": [{"id": name, "object": "model"} for name in LEVELS]}

    @app.post("/v1/chat/completions")
    def chat_completions(request: ChatRequest):
        if request.model not in LEVELS:
            return _error(
                400,
                f"Unbekannte Stufe '{request.model}'. Verfügbar: {', '.join(LEVELS)}.",
            )
        system = build_system_prompt(
            LEVELS[request.model], settings["documents"], settings["solution"], settings["canary"]
        )
        messages = [{"role": "system", "content": system}] + [
            m for m in request.messages if m.get("role") != "system"
        ]
        try:
            text = model.chat(messages, seed=request.seed, temperature=request.temperature)
        except (ModelUnavailable, ModelResponseError) as error:
            return _error(502, str(error))
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
        }

    return app

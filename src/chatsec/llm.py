"""OpenAI-compatible client: every LLM call in the project goes through here."""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx


class ModelUnavailable(Exception):
    """Ollama is not running or the model is not installed."""


class ModelResponseError(Exception):
    """The model server answered, but the answer is unusable."""


class ChatModel(Protocol):
    def chat(
        self,
        messages: list[dict],
        *,
        json_schema: dict | None = None,
        seed: int | None = None,
        temperature: float | None = None,
    ) -> str: ...


@dataclass
class ModelSpec:
    base_url: str
    model: str
    reasoning_effort: str | None = "none"


def load_model_config(path: Path) -> dict[str, ModelSpec]:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return {role: ModelSpec(**values) for role, values in data.items()}


class OpenAICompatibleModel:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 120.0,
        client: httpx.Client | None = None,
        reasoning_effort: str | None = "none",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.reasoning_effort = reasoning_effort
        self._client = client if client is not None else httpx.Client(timeout=timeout)

    def _down_message(self) -> str:
        return (
            f"Ollama läuft nicht oder ist unter {self.base_url} nicht erreichbar. "
            "Bitte Ollama starten und es noch einmal versuchen."
        )

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = self._client.request(method, f"{self.base_url}{path}", **kwargs)
        except httpx.TransportError as error:
            raise ModelUnavailable(self._down_message()) from error
        if response.status_code >= 400:
            raise ModelResponseError(
                f"Das Modell {self.model} hat mit Fehler {response.status_code} geantwortet: "
                f"{response.text[:200]}"
            )
        return response

    def chat(
        self,
        messages: list[dict],
        *,
        json_schema: dict | None = None,
        seed: int | None = None,
        temperature: float | None = None,
    ) -> str:
        body: dict = {"model": self.model, "messages": messages}
        if json_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "answer", "strict": True, "schema": json_schema},
            }
        if seed is not None:
            body["seed"] = seed
        if temperature is not None:
            body["temperature"] = temperature
        if self.reasoning_effort is not None:
            body["reasoning_effort"] = self.reasoning_effort
        response = self._request("POST", "/chat/completions", json=body)
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            content = None
        if not isinstance(content, str):
            raise ModelResponseError(
                f"Das Modell {self.model} hat keine brauchbare Textantwort geliefert."
            )
        return content

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._request("POST", "/embeddings", json={"model": self.model, "input": texts})
        try:
            items = sorted(response.json()["data"], key=lambda item: item["index"])
            return [item["embedding"] for item in items]
        except (ValueError, KeyError, TypeError) as error:
            raise ModelResponseError(
                f"Das Modell {self.model} hat keine brauchbaren Vektoren geliefert."
            ) from error

    def check_available(self) -> None:
        response = self._request("GET", "/models")
        try:
            names = {item["id"] for item in response.json()["data"]}
        except (ValueError, KeyError, TypeError) as error:
            raise ModelResponseError("Die Modell-Liste von Ollama ist nicht lesbar.") from error
        if self.model not in names:
            raise ModelUnavailable(
                f"Das Modell {self.model} ist nicht installiert. "
                f"Bitte zuerst herunterladen mit: ollama pull {self.model}"
            )

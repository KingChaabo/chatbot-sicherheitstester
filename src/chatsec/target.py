"""Configurable connection to any chatbot API."""

import json
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
MAX_TRIES = 3


class TargetError(Exception):
    """The chatbot could not be reached or answered in an unusable way."""


class PermissionMissing(Exception):
    """The target is not local and the operator's permission is not confirmed."""


@dataclass
class TargetConfig:
    name: str
    url: str
    headers: dict[str, str]
    body_template: str
    response_path: str
    secret: str | None
    system_canary: str | None
    solution_file: Path | None
    instructions_file: Path | None
    permission_confirmed: bool
    permission_note: str
    timeout: float = 60.0
    max_rate: float = 2.0


def _require(table: dict, key: str, label: str):
    if key not in table:
        raise ValueError(f"In der Anbindungsdatei fehlt der Eintrag '{label}'.")
    return table[key]


def load_target(path: Path) -> TargetConfig:
    path = Path(path)
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    request = data.get("request", {})
    response = data.get("response", {})
    secrets = data.get("secrets", {})
    permission = data.get("permission", {})

    def resolve(key: str) -> Path | None:
        value = secrets.get(key)
        return (path.parent / value).resolve() if value else None

    return TargetConfig(
        name=_require(data, "name", "name"),
        url=_require(data, "url", "url"),
        headers=dict(request.get("headers", {})),
        body_template=_require(request, "body", "request.body"),
        response_path=_require(response, "path", "response.path"),
        secret=secrets.get("secret"),
        system_canary=secrets.get("system_canary"),
        solution_file=resolve("solution_file"),
        instructions_file=resolve("instructions_file"),
        permission_confirmed=bool(permission.get("confirmed", False)),
        permission_note=permission.get("note", ""),
        timeout=float(data.get("timeout", 60.0)),
        max_rate=float(data.get("max_rate", 2.0)),
    )


def check_permission(cfg: TargetConfig) -> None:
    host = urlsplit(cfg.url).hostname
    if host in LOCAL_HOSTS or cfg.permission_confirmed:
        return
    raise PermissionMissing(
        f"Das Ziel '{host}' liegt nicht auf diesem Rechner. Getestet wird es nur mit "
        "ausdrücklicher schriftlicher Erlaubnis des Betreibers. Setze in der "
        "Anbindungsdatei unter [permission] erst dann confirmed = true, wenn du diese Erlaubnis hast."
    )


def _extract(data, path: str):
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise TargetError(f"In der Antwort des Chatbots fehlt der Pfad '{path}'.")
    return current


class Target:
    def __init__(self, cfg: TargetConfig, client: httpx.Client | None = None,
                 sleep=time.sleep, clock=time.monotonic):
        self.cfg = cfg
        self.client = client or httpx.Client(timeout=cfg.timeout)
        self._sleep = sleep
        self._clock = clock
        self._last_start: float | None = None

    def _build_body(self, messages: list[dict]):
        last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        text = self.cfg.body_template.replace('"{{messages}}"', json.dumps(messages))
        text = text.replace('"{{last_message}}"', json.dumps(last_user))
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise TargetError(f"Die Anfrage-Vorlage ergibt kein gültiges JSON: {exc}") from exc

    def _wait_for_rate_limit(self) -> None:
        if self._last_start is not None:
            wait = self._last_start + 1 / self.cfg.max_rate - self._clock()
            if wait > 0:
                self._sleep(wait)
        self._last_start = self._clock()

    def send(self, messages: list[dict]) -> str:
        body = self._build_body(messages)
        reason = ""
        for attempt in range(MAX_TRIES):
            if attempt:
                self._sleep(attempt)
            self._wait_for_rate_limit()
            try:
                response = self.client.post(self.cfg.url, json=body, headers=self.cfg.headers)
            except httpx.TransportError as exc:
                reason = f"Verbindungsfehler ({exc.__class__.__name__}: {exc})"
                continue
            except (httpx.HTTPError, httpx.InvalidURL) as exc:
                raise TargetError(
                    f"Die Anfrage an den Chatbot ist fehlgeschlagen ({exc.__class__.__name__}: {exc})."
                ) from exc
            status = response.status_code
            if status == 429 or status >= 500:
                reason = f"Der Chatbot antwortete mit Status {status}"
                continue
            if status >= 400:
                raise TargetError(f"Der Chatbot lehnte die Anfrage ab (Status {status}).")
            return self._read_answer(response)
        raise TargetError(f"Der Chatbot ist nach {MAX_TRIES} Versuchen nicht erreichbar: {reason}.")

    def _read_answer(self, response: httpx.Response) -> str:
        path = self.cfg.response_path
        try:
            data = response.json()
        except ValueError as exc:
            raise TargetError("Die Antwort des Chatbots ist kein gültiges JSON.") from exc
        value = _extract(data, path)
        if value is None:
            raise TargetError(f"Der Wert am Pfad '{path}' ist leer (null).")
        if not isinstance(value, str):
            raise TargetError(f"Der Wert am Pfad '{path}' ist kein Text, sondern {type(value).__name__}.")
        return value

    def ping(self) -> None:
        self.send([{"role": "user", "content": "Hallo"}])

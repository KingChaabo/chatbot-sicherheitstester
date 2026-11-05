import json
from pathlib import Path

import httpx
import pytest

from chatsec.target import (
    PermissionMissing,
    Target,
    TargetConfig,
    TargetError,
    check_permission,
    load_target,
)

TEMPLATE = Path(__file__).resolve().parents[1] / "targets" / "openai-vorlage.toml"


def make_cfg(**overrides) -> TargetConfig:
    values = dict(
        name="Test",
        url="http://127.0.0.1:8100/v1/chat/completions",
        headers={},
        body_template='{"messages": "{{messages}}"}',
        response_path="choices.0.message.content",
        secret=None,
        system_canary=None,
        solution_file=None,
        instructions_file=None,
        permission_confirmed=False,
        permission_note="",
        max_rate=1000.0,
    )
    values.update(overrides)
    return TargetConfig(**values)


class FakeTime:
    def __init__(self):
        self.now = 100.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_target(handler, cfg=None, fake=None):
    fake = fake or FakeTime()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return Target(cfg or make_cfg(), client=client, sleep=fake.sleep, clock=fake.clock), fake


def ok(text="Hallo"):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


USER_X = [{"role": "user", "content": "x"}]


def test_send_fills_template_and_reads_path():
    cfg = load_target(TEMPLATE)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["url"] = str(request.url)
        return ok("Antwort")

    target, _ = make_target(handler, cfg)
    messages = [{"role": "user", "content": 'Frage mit "Anführungszeichen"'}]
    assert target.send(messages) == "Antwort"
    assert seen["body"] == {"model": "MODELLNAME", "messages": messages}
    assert seen["url"] == cfg.url


def test_load_target_template_values():
    cfg = load_target(TEMPLATE)
    assert cfg.url == "http://127.0.0.1:8000/v1/chat/completions"
    assert cfg.response_path == "choices.0.message.content"
    assert cfg.permission_confirmed is False
    assert cfg.timeout == 60.0 and cfg.max_rate == 2.0
    assert cfg.secret is None and cfg.solution_file is None


def test_load_target_secrets_and_missing_keys(tmp_path):
    (tmp_path / "t.toml").write_text(
        'name = "X"\nurl = "http://localhost/x"\n'
        '[request]\nbody = "{}"\n[response]\npath = "a"\n'
        '[secrets]\nsecret = "S"\nsolution_file = "../l.md"\n'
        '[permission]\nconfirmed = true\nnote = "ok"\n',
        encoding="utf-8",
    )
    cfg = load_target(tmp_path / "t.toml")
    assert cfg.secret == "S" and cfg.instructions_file is None
    assert cfg.solution_file == (tmp_path / "../l.md").resolve()
    assert cfg.solution_file.is_absolute()
    assert cfg.permission_confirmed is True and cfg.permission_note == "ok"
    (tmp_path / "bad.toml").write_text('name = "X"\nurl = "u"\n[response]\npath = "a"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="request.body"):
        load_target(tmp_path / "bad.toml")


def test_last_message_placeholder():
    cfg = make_cfg(body_template='{"frage": "{{last_message}}"}', response_path="antwort")
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"antwort": "Hi"})

    target, _ = make_target(handler, cfg)
    messages = [
        {"role": "user", "content": "erste"},
        {"role": "assistant", "content": "x"},
        {"role": "user", "content": 'zweite "Frage"'},
    ]
    assert target.send(messages) == "Hi"
    assert seen["body"] == {"frage": 'zweite "Frage"'}


def test_invalid_template_raises_target_error():
    target, _ = make_target(lambda r: ok(), make_cfg(body_template='{"a": '))
    with pytest.raises(TargetError, match="JSON"):
        target.send(USER_X)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"choices": [{"message": {"content": None}}]}),
        httpx.Response(200, json={"choices": [{"message": {}}]}),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"message": {"content": ["a", "b"]}}]}),
        httpx.Response(200, text="<html>kein JSON</html>"),
    ],
)
def test_unexpected_response_shapes(response):
    target, _ = make_target(lambda r: response)
    with pytest.raises(TargetError) as info:
        target.send(USER_X)
    assert str(info.value)


def test_unexpected_shape_names_path():
    target, _ = make_target(lambda r: httpx.Response(200, json={"x": 1}))
    with pytest.raises(TargetError, match="choices.0.message.content"):
        target.send(USER_X)


def test_empty_string_is_valid_answer():
    target, _ = make_target(lambda r: ok(""))
    assert target.send(USER_X) == ""


def test_retries_then_fails():
    responses = iter([httpx.Response(503), httpx.Response(503), ok("spät")])
    target, fake = make_target(lambda r: next(responses))
    assert target.send(USER_X) == "spät"
    assert fake.sleeps == [1, 2]

    target, fake = make_target(lambda r: httpx.Response(503))
    with pytest.raises(TargetError, match="503"):
        target.send(USER_X)
    assert fake.sleeps == [1, 2]


def test_retries_on_transport_error_and_429():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectTimeout("zu langsam", request=request)
        if len(calls) == 2:
            return httpx.Response(429)
        return ok("da")

    target, fake = make_target(handler)
    assert target.send(USER_X) == "da"
    assert fake.sleeps == [1, 2]


def test_client_error_is_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401)

    target, fake = make_target(handler)
    with pytest.raises(TargetError, match="401"):
        target.send(USER_X)
    assert len(calls) == 1 and fake.sleeps == []


def test_rate_limit():
    starts = []
    fake = FakeTime()

    def handler(request):
        starts.append(fake.now)
        return ok()

    target, _ = make_target(handler, make_cfg(max_rate=2.0), fake)
    for _ in range(3):
        target.send(USER_X)
    assert starts[1] - starts[0] >= 0.5
    assert starts[2] - starts[1] >= 0.5


def test_ping():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return ok()

    target, _ = make_target(handler)
    target.ping()
    assert seen["body"]["messages"] == [{"role": "user", "content": "Hallo"}]
    bad, _ = make_target(lambda r: httpx.Response(401))
    with pytest.raises(TargetError):
        bad.ping()


def test_permission():
    check_permission(make_cfg(url="http://127.0.0.1:8100/v1/chat/completions"))
    check_permission(make_cfg(url="http://[::1]:8100/x"))
    check_permission(make_cfg(url="http://localhost/x"))
    with pytest.raises(PermissionMissing, match="example.com"):
        check_permission(make_cfg(url="https://example.com/v1/chat/completions"))
    check_permission(make_cfg(url="https://example.com/v1/chat/completions", permission_confirmed=True))


def test_other_httpx_errors_become_target_error():
    def handler(request):
        raise httpx.DecodingError("kaputtes gzip", request=request)

    target, fake = make_target(handler)
    with pytest.raises(TargetError, match="fehlgeschlagen"):
        target.send(USER_X)
    assert fake.sleeps == []


def test_secret_paths_are_absolute_and_normalised(tmp_path, monkeypatch):
    (tmp_path / "ziele").mkdir()
    (tmp_path / "ziele" / "t.toml").write_text(
        'name = "X"\nurl = "http://localhost/x"\n'
        '[request]\nbody = "{}"\n[response]\npath = "a"\n'
        '[secrets]\nsolution_file = "../x/l.md"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    cfg = load_target(Path("ziele/t.toml"))
    assert cfg.solution_file.is_absolute()
    assert ".." not in cfg.solution_file.parts
    assert cfg.solution_file == (tmp_path / "x" / "l.md").resolve()

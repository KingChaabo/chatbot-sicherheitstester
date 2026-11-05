import json

import pytest

from chatsec.models import Attack, Category, Judgement, Verdict
from chatsec.runner import TargetUnreachable, run_attacks
from chatsec.target import TargetError


class _Cfg:
    name = "fake"


class FakeTarget:
    def __init__(self, answers=None, ping_error=None):
        self.cfg = _Cfg()
        self.answers = list(answers or [])
        self.ping_error = ping_error
        self.calls = []

    def ping(self):
        if self.ping_error:
            raise self.ping_error

    def send(self, messages):
        self.calls.append([dict(m) for m in messages])
        item = self.answers.pop(0) if self.answers else "ok"
        if isinstance(item, BaseException):
            raise item
        return item


class FakeEvaluator:
    def evaluate(self, attack, response, error):
        if response is None:
            return Judgement(Verdict.NOT_EVALUATED, "keiner", "keine Antwort")
        if "GEHEIM" in response:
            return Judgement(Verdict.SUCCESS, "regel:test", "gefunden")
        return Judgement(Verdict.BLOCKED, "regel:test", "nichts")


def attack(id_, turns=("Hallo",)):
    return Attack(id=id_, category=Category.K1, language="de", turns=tuple(turns), goal="x")


def lines(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def test_writes_one_line_per_attempt(tmp_path):
    out = tmp_path / "run" / "attempts.jsonl"
    progress = []
    result = run_attacks(FakeTarget(), [attack("a"), attack("b")], FakeEvaluator(),
                         out_file=out, run_id="r1", on_progress=lambda d, t: progress.append((d, t)))
    assert result == out
    rows = lines(out)
    assert rows[0]["type"] == "run" and rows[0]["attempts"] == 3 and rows[0]["attack_count"] == 2
    assert rows[0]["target_name"] == "fake" and rows[0]["run_id"] == "r1"
    assert [r["type"] for r in rows[1:-1]] == ["attempt"] * 6
    assert rows[-1]["type"] == "end" and "finished" in rows[-1]
    assert progress[-1] == (6, 6) and len(progress) == 6


def test_ping_fails_raises_before_writing(tmp_path):
    out = tmp_path / "run" / "attempts.jsonl"
    with pytest.raises(TargetUnreachable):
        run_attacks(FakeTarget(ping_error=TargetError("kaputt")), [attack("a")], FakeEvaluator(),
                    out_file=out, run_id="r1")
    assert not out.exists()


def test_three_consecutive_errors_abort(tmp_path):
    out = tmp_path / "attempts.jsonl"
    target = FakeTarget(["ok", TargetError("x"), TargetError("x"), TargetError("x")])
    run_attacks(target, [attack("a"), attack("b")], FakeEvaluator(), out_file=out, run_id="r1")
    rows = lines(out)
    assert [r["type"] for r in rows] == ["run", "attempt", "attempt", "attempt", "attempt", "abort"]
    assert rows[-1]["reason"] == "Chatbot antwortet nicht mehr"
    assert rows[2]["response"] is None and rows[2]["judgement"]["verdict"] == "nicht_bewertet"


def test_keyboard_interrupt_writes_abort(tmp_path):
    out = tmp_path / "attempts.jsonl"
    target = FakeTarget(["ok", "ok", KeyboardInterrupt()])
    with pytest.raises(KeyboardInterrupt):
        run_attacks(target, [attack("a")], FakeEvaluator(), out_file=out, run_id="r1")
    rows = lines(out)
    assert [r["type"] for r in rows] == ["run", "attempt", "attempt", "abort"]
    assert rows[-1]["reason"] == "abgebrochen durch Nutzer"


def test_multi_turn_stops_on_success(tmp_path):
    out = tmp_path / "attempts.jsonl"
    target = FakeTarget(["nein", "GEHEIM da", "nein", "nein"])
    run_attacks(target, [attack("a", ("eins", "zwei", "drei"))], FakeEvaluator(),
                attempts=1, out_file=out, run_id="r1")
    row = lines(out)[1]
    assert len(target.calls) == 2 and len(target.calls[1]) == 3
    assert row["judgement"]["verdict"] == "geklappt"
    assert [m["role"] for m in row["messages"]] == ["user", "assistant", "user", "assistant"]
    assert row["response"] == "GEHEIM da"


def test_multi_turn_runs_all_turns_without_success(tmp_path):
    out = tmp_path / "attempts.jsonl"
    target = FakeTarget(["a", "b", "c"])
    run_attacks(target, [attack("a", ("1", "2", "3"))], FakeEvaluator(),
                attempts=1, out_file=out, run_id="r1")
    row = lines(out)[1]
    assert len(row["messages"]) == 6 and row["response"] == "c"
    assert row["judgement"]["verdict"] == "abgewehrt"

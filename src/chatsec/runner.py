"""Sends every attack several times, evaluates each answer and streams results to JSON lines."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from chatsec.judge import Evaluator
from chatsec.models import Attack, AttemptRecord, Judgement, Verdict
from chatsec.target import Target, TargetError

MAX_CONSECUTIVE_FAILURES = 3


class TargetUnreachable(Exception):
    """The chatbot did not answer the first test message."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _write(handle, data: dict) -> None:
    handle.write(json.dumps(data, ensure_ascii=False) + "\n")
    handle.flush()


def _run_attempt(target: Target, attack: Attack, evaluator: Evaluator, run_id: str,
                 number: int) -> tuple[AttemptRecord, bool]:
    """Run one conversation. Returns the record and whether the chatbot answered."""
    messages: list[dict] = []
    response: str | None = None
    judgement: Judgement | None = None
    error: str | None = None
    try:
        for turn in attack.turns:
            messages.append({"role": "user", "content": turn})
            response = target.send(messages)
            judgement = evaluator.evaluate(attack, response, None)
            messages.append({"role": "assistant", "content": response})
            if judgement.verdict is Verdict.SUCCESS:
                break
    except TargetError as exc:
        error = f"Der Chatbot hat nicht geantwortet: {exc}"
        response = None
        judgement = evaluator.evaluate(attack, None, error)
    record = AttemptRecord(
        run_id=run_id, target_name=target.cfg.name, attack_id=attack.id,
        category=attack.category, attempt=number, messages=messages, response=response,
        error=error, judgement=judgement, timestamp=_now(),
    )
    return record, error is None


def run_attacks(target: Target, attacks: list[Attack], evaluator: Evaluator, *,
                attempts: int = 3, out_file: Path, run_id: str,
                on_progress: Callable[[int, int], None] | None = None) -> Path:
    try:
        target.ping()
    except TargetError as exc:
        raise TargetUnreachable(f"Der Chatbot ist nicht erreichbar: {exc}") from exc

    out_file = Path(out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    total = len(attacks) * attempts
    done = 0
    failures = 0
    with out_file.open("w", encoding="utf-8", newline="") as handle:
        _write(handle, {"type": "run", "run_id": run_id, "target_name": target.cfg.name,
                        "started": _now(), "attempts": attempts, "attack_count": len(attacks)})
        try:
            for attack in attacks:
                for number in range(1, attempts + 1):
                    record, answered = _run_attempt(target, attack, evaluator, run_id, number)
                    _write(handle, {"type": "attempt", **json.loads(record.to_json())})
                    done += 1
                    if on_progress:
                        on_progress(done, total)
                    failures = 0 if answered else failures + 1
                    if failures >= MAX_CONSECUTIVE_FAILURES:
                        _write(handle, {"type": "abort", "reason": "Chatbot antwortet nicht mehr",
                                        "finished": _now()})
                        return out_file
        except KeyboardInterrupt:
            _write(handle, {"type": "abort", "reason": "abgebrochen durch Nutzer",
                            "finished": _now()})
            raise
        _write(handle, {"type": "end", "finished": _now()})
    return out_file

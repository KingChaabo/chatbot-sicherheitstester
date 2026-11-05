"""Helper to build small result files for scoring and comparison tests."""

import json
from pathlib import Path

from chatsec.models import AttemptRecord, Category, Judgement, Verdict


def j(verdict: Verdict) -> Judgement:
    return Judgement(verdict, "rule", "test")


def write_run(
    run_dir: Path,
    attempts: list[tuple[str, Category, Verdict]],
    *,
    run_id: str = "20261101-100000-bot",
    target: str = "bot",
    end: dict | None = None,
    raw_tail: str = "",
) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {
                "type": "run",
                "run_id": run_id,
                "target_name": target,
                "started": "2026-11-01T10:00:00",
                "attempts": 3,
                "attack_count": len({a[0] for a in attempts}),
            }
        )
    ]
    counter: dict[str, int] = {}
    for attack_id, category, verdict in attempts:
        counter[attack_id] = counter.get(attack_id, 0) + 1
        rec = AttemptRecord(
            run_id, target, attack_id, category, counter[attack_id],
            [{"role": "user", "content": "x"}], "antwort", None, j(verdict),
            "2026-11-01T10:00:01",
        )
        data = json.loads(rec.to_json())
        data["type"] = "attempt"
        lines.append(json.dumps(data, ensure_ascii=False))
    if end is not None:
        lines.append(json.dumps(end))
    text = "\n".join(lines) + "\n" + raw_tail
    (run_dir / "attempts.jsonl").write_text(text, encoding="utf-8")
    return run_dir

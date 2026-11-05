"""Compare a run with the previous one of the same target."""

from __future__ import annotations

from pathlib import Path

from chatsec.models import Category, RunSummary
from chatsec.scoring import RESULT_FILE, has_end_line, load_run


def find_previous_run(results_dir: Path, target_name: str, before_run_id: str) -> Path | None:
    best: tuple[str, Path] | None = None
    for run_dir in Path(results_dir).iterdir():
        if not (run_dir / RESULT_FILE).is_file():
            continue
        try:
            header, _, abort = load_run(run_dir)
        except (ValueError, KeyError, OSError):
            continue
        run_id = header.get("run_id")
        if header.get("target_name") != target_name or abort is not None:
            continue
        if not has_end_line(run_dir):
            continue
        if not isinstance(run_id, str) or run_id >= before_run_id:
            continue
        if best is None or run_id > best[0]:
            best = (run_id, run_dir)
    return best[1] if best else None


def compare(current: RunSummary, previous: RunSummary) -> dict[Category | None, float | None]:
    def diff(now: float | None, before: float | None) -> float | None:
        if now is None or before is None:
            return None
        return round(now - before, 1)

    result: dict[Category | None, float | None] = {
        None: diff(current.overall.defense_rate, previous.overall.defense_rate)
    }
    for category, score in current.per_category.items():
        old = previous.per_category.get(category)
        result[category] = diff(score.defense_rate, old.defense_rate if old else None)
    return result

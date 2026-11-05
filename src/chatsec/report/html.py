"""Render a run into one self-contained HTML file."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from chatsec.compare import compare
from chatsec.models import AttemptRecord, Category, Verdict
from chatsec.report.tips import CATEGORY_NAMES, TIPS
from chatsec.scoring import load_run, summarize

MAX_RESPONSE_CHARS = 4000
REPORT_FILE = "report.html"
LIGHT_WORDS = {"gruen": "Grün", "gelb": "Gelb", "rot": "Rot", "grau": "Grau"}


def _rate(value: float | None) -> str:
    if value is None:
        return "keine"
    return f"{value:.1f}".replace(".", ",") + " %"


def _local_time(value: str | None) -> str:
    """ISO timestamp to local German format; the raw text if it cannot be parsed."""
    if not value:
        return ""
    try:
        moment = datetime.fromisoformat(value).astimezone()
    except (ValueError, TypeError):
        return value
    return moment.strftime("%d.%m.%Y, %H:%M") + " Uhr"


def _delta(value: float | None) -> str:
    if value is None:
        return "neu"
    return f"{value:+.1f}".replace(".", ",") + " Pp"


def _clip(text: str | None) -> str:
    if text is None:
        return ""
    if len(text) > MAX_RESPONSE_CHARS:
        return text[:MAX_RESPONSE_CHARS] + "… (gekürzt)"
    return text


def _first_successes(records: list[AttemptRecord]) -> dict[Category, AttemptRecord]:
    found: dict[Category, AttemptRecord] = {}
    for rec in records:
        if rec.judgement.verdict is Verdict.SUCCESS and rec.category not in found:
            found[rec.category] = rec
    return found


def _example_view(rec: AttemptRecord) -> dict:
    return {
        "attack_id": rec.attack_id,
        "user_messages": [m.get("content", "") for m in rec.messages if m.get("role") == "user"],
        "response": _clip(rec.response),
        "verdict": rec.judgement.verdict.value,
        "decided_by": rec.judgement.decided_by,
        "reason": rec.judgement.reason,
    }


def render_report(run_dir: Path, previous: Path | None = None) -> Path:
    run_dir = Path(run_dir)
    summary = summarize(run_dir)
    _, records, _ = load_run(run_dir)
    deltas = compare(summary, summarize(Path(previous))) if previous is not None else {}
    successes = _first_successes(records)

    rows = []
    for category, score in summary.per_category.items():
        is_red = score.light == "rot"
        example = successes.get(category) if is_red else None
        rows.append(
            {
                "name": f"{category.value} {CATEGORY_NAMES[category]}",
                "score": score,
                "rate": _rate(score.defense_rate),
                "light_word": LIGHT_WORDS[score.light],
                "delta": _delta(deltas.get(category)),
                "example": _example_view(example) if example else None,
                "tip": TIPS[category] if is_red else None,
            }
        )

    env = Environment(loader=FileSystemLoader(Path(__file__).parent), autoescape=True)
    page = env.get_template("template.html.j2").render(
        summary=summary,
        overall_rate=_rate(summary.overall.defense_rate),
        overall_light=summary.overall.light,
        overall_light_word=LIGHT_WORDS[summary.overall.light],
        overall_delta=_delta(deltas.get(None)),
        started=_local_time(summary.started),
        finished=_local_time(summary.finished),
        rows=rows,
    )
    out = run_dir / REPORT_FILE
    out.write_text(page, encoding="utf-8")
    return out

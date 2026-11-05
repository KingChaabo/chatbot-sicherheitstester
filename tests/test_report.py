import json

from runfiles import write_run

from chatsec.models import Category, Verdict
from chatsec.report.html import render_report
from chatsec.report.tips import CATEGORY_NAMES, TIPS

S, B = Verdict.SUCCESS, Verdict.BLOCKED
K1, K2 = Category.K1, Category.K2


def set_response(run_dir, text):
    path = run_dir / "attempts.jsonl"
    path.write_text(
        path.read_text(encoding="utf-8").replace('"antwort"', json.dumps(text)),
        encoding="utf-8",
    )


def test_tips_cover_every_category():
    assert set(TIPS) == set(Category) == set(CATEGORY_NAMES)
    assert "Stufe 2" in TIPS[K1]
    assert all("—" not in t and "–" not in t for t in TIPS.values())


def test_report_shows_scores_and_light(tmp_path):
    run = write_run(
        tmp_path / "r",
        [("a1", K1, B), ("a2", K1, B), ("a3", K1, B), ("a4", K1, S), ("b1", K2, B)],
    )
    html = render_report(run).read_text(encoding="utf-8")
    assert (run / "report.html").is_file()
    assert "75,0 %" in html and "100,0 %" in html
    assert "Grün" in html and "Gelb" in html
    assert "Regeln aushebeln" in html
    assert "<script" not in html and "http" not in html


def test_report_gives_example_and_tip_for_red_category(tmp_path):
    run = write_run(tmp_path / "r", [("a1", K1, S), ("a2", K1, B)])
    html = render_report(run).read_text(encoding="utf-8")
    assert "Rot" in html and "Eingangsprüfung (Stufe 2)" in html
    assert "entschieden durch rule" in html


def test_report_escapes_html(tmp_path):
    run = write_run(tmp_path / "r", [("a1", K1, S)])
    set_response(run, "<script>alert(1)</script>")
    html = render_report(run).read_text(encoding="utf-8")
    assert "&lt;script&gt;" in html
    assert "<script>alert" not in html


def test_report_truncates_long_answer(tmp_path):
    run = write_run(tmp_path / "r", [("a1", K1, S)])
    set_response(run, "x" * 5000)
    html = render_report(run).read_text(encoding="utf-8")
    assert "x" * 4000 + "… (gekürzt)" in html
    assert "x" * 4001 not in html


def test_report_marks_aborted_run(tmp_path):
    end = {"type": "abort", "reason": "Ziel nicht erreichbar", "finished": "2026-11-01T10:05:00"}
    run = write_run(tmp_path / "r", [("a1", K1, B)], end=end)
    html = render_report(run).read_text(encoding="utf-8")
    assert "Lauf abgebrochen: Ziel nicht erreichbar" in html


def test_report_shows_delta_to_previous(tmp_path):
    old = write_run(
        tmp_path / "old", [("a1", K1, B), ("a2", K1, S)], run_id="20261101-090000-bot"
    )
    new = write_run(tmp_path / "new", [("a1", K1, B), ("a2", K1, B), ("a3", K1, B), ("a4", K1, S)])
    html = render_report(new, previous=old).read_text(encoding="utf-8")
    assert "+25,0 Pp" in html

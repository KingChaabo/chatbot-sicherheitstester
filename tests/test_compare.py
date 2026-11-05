from chatsec.compare import compare, find_previous_run
from chatsec.models import Category, Verdict
from chatsec.scoring import summarize
from tests.test_scoring import write_run

B, S = Verdict.BLOCKED, Verdict.SUCCESS
END = {"type": "end", "finished": "2026-11-01T11:00:00"}


def make(results, run_id, target, attempts, end=END):
    return write_run(results / run_id, attempts, run_id=run_id, target=target, end=end)


def test_compare_and_find_previous(tmp_path):
    k1 = Category.K1
    old = make(tmp_path, "20261101-100000-bot", "bot", [("a", k1, B)] * 3 + [("b", k1, S)] * 3)
    make(tmp_path, "20261102-100000-bot", "bot", [("a", k1, B)] * 3,
         end={"type": "abort", "reason": "x", "finished": "f"})
    make(tmp_path, "20261102-110000-other", "other", [("a", k1, B)] * 3)
    cur = make(tmp_path, "20261103-100000-bot", "bot",
               [("a", k1, B)] * 3 + [("b", k1, B)] * 3 + [("c", Category.K2, B)] * 3)
    (tmp_path / "leer").mkdir()
    (tmp_path / "20261101-090000-bot").mkdir()

    prev = find_previous_run(tmp_path, "bot", cur.name)
    assert prev == old
    assert find_previous_run(tmp_path, "bot", old.name) is None
    assert find_previous_run(tmp_path, "unbekannt", cur.name) is None

    diff = compare(summarize(cur), summarize(prev))
    assert diff[None] == 50.0
    assert diff[k1] == 50.0
    assert diff[Category.K2] is None

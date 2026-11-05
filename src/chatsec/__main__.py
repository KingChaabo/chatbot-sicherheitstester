"""Command line: python -m chatsec run|report."""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

from chatsec.catalog import CatalogError, load_catalog
from chatsec.compare import find_previous_run
from chatsec.judge import Evaluator, Secrets
from chatsec.models import Category
from chatsec.report.html import LIGHT_WORDS, render_report
from chatsec.runner import TargetUnreachable, run_attacks
from chatsec.scoring import load_run, summarize
from chatsec.target import PermissionMissing, Target, check_permission, load_target

_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _slug(name: str) -> str:
    text = name.lower().translate(_UMLAUTS)
    out = []
    for char in text:
        if char.isascii() and char.isalnum():
            out.append(char)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chatsec", description="Sicherheitstest für Chatbots")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Angriffe gegen einen Chatbot ausführen")
    run.add_argument("--target", required=True, type=Path, help="Anbindungsdatei (.toml)")
    run.add_argument("--attempts", type=int, default=3)
    run.add_argument("--categories", help="z. B. K1,K2")
    run.add_argument("--ci-only", action="store_true")
    run.add_argument("--no-judge", action="store_true")
    run.add_argument("--catalog", type=Path, default=Path("catalog"))
    run.add_argument("--results", type=Path, default=Path("results"))
    report = sub.add_parser("report", help="Bericht für einen Lauf neu erzeugen")
    report.add_argument("run_dir", type=Path)
    report.add_argument("--previous", type=Path)
    return parser


def _error(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def _read_text(path: Path | None) -> str | None:
    return path.read_text(encoding="utf-8") if path else None


def _parse_categories(text: str | None) -> set[Category] | None:
    if not text:
        return None
    result = set()
    for part in text.split(","):
        try:
            result.add(Category(part.strip().upper()))
        except ValueError:
            raise ValueError(f"Unbekannte Kategorie '{part.strip()}'. Erlaubt sind K1 bis K6.") from None
    return result


def _print_summary(run_dir: Path, report: Path) -> None:
    summary = summarize(run_dir)
    overall = summary.overall
    rate = "keine" if overall.defense_rate is None else f"{overall.defense_rate:.1f} %".replace(".", ",")
    print(f"Abwehrquote: {rate} ({LIGHT_WORDS[overall.light]})")
    print(f"geklappt: {overall.success}, abgewehrt: {overall.blocked}, "
          f"unklar: {overall.unclear}, nicht bewertet: {overall.not_evaluated}")
    print(f"Bericht: {report}")


def _run(ns: argparse.Namespace, client: httpx.Client | None, sleep) -> int:
    try:
        cfg = load_target(ns.target)
    except (ValueError, OSError) as exc:
        return _error(f"Die Anbindungsdatei konnte nicht gelesen werden: {exc}")
    try:
        check_permission(cfg)
    except PermissionMissing as exc:
        return _error(str(exc))
    if ns.attempts < 1:
        return _error("Die Zahl der Versuche muss mindestens 1 sein.")
    try:
        categories = _parse_categories(ns.categories)
        attacks = load_catalog(ns.catalog, categories=categories, ci_only=ns.ci_only)
    except (ValueError, CatalogError) as exc:
        return _error(str(exc))
    if not attacks:
        return _error("Die Auswahl enthält keine Angriffe.")
    try:
        secrets = Secrets(cfg.secret, cfg.system_canary,
                          _read_text(cfg.solution_file), _read_text(cfg.instructions_file))
    except OSError as exc:
        return _error(f"Eine Datei aus [secrets] konnte nicht gelesen werden: {exc}")

    run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{_slug(cfg.name)}"
    run_dir = ns.results / run_id
    out_file = run_dir / "attempts.jsonl"
    target = Target(cfg, client, sleep=sleep)

    def progress(done: int, total: int) -> None:
        print(f"\rVersuch {done}/{total}", end="", file=sys.stderr, flush=True)

    interrupted = False
    try:
        run_attacks(target, attacks, Evaluator(secrets), attempts=ns.attempts,
                    out_file=out_file, run_id=run_id, on_progress=progress)
    except TargetUnreachable as exc:
        return _error(str(exc))
    except KeyboardInterrupt:
        interrupted = True
    print(file=sys.stderr)

    previous = find_previous_run(ns.results, cfg.name, run_id)
    report = render_report(run_dir, previous)
    _print_summary(run_dir, report)
    if interrupted:
        print("Der Lauf wurde abgebrochen. Der Bericht zeigt den bisherigen Stand.")
        return 130
    summary = summarize(run_dir)
    if summary.aborted:
        print(f"Der Lauf wurde abgebrochen: {summary.abort_reason}")
        return 1
    return 0


def _report(ns: argparse.Namespace) -> int:
    try:
        header, _, _ = load_run(ns.run_dir)
        previous = ns.previous or find_previous_run(
            ns.run_dir.parent, header["target_name"], header["run_id"])
        report = render_report(ns.run_dir, previous)
    except (ValueError, OSError) as exc:
        return _error(f"Der Bericht konnte nicht erstellt werden: {exc}")
    _print_summary(ns.run_dir, report)
    return 0


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None,
         sleep=time.sleep) -> int:
    ns = _parser().parse_args(argv)
    if ns.command == "run":
        return _run(ns, client, sleep)
    return _report(ns)


if __name__ == "__main__":
    raise SystemExit(main())

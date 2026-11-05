"""Loads the attack catalog from YAML files."""

from __future__ import annotations

from pathlib import Path

import yaml

from chatsec.judge.rules import compact
from chatsec.models import Attack, Category


class CatalogError(Exception):
    """Raised for an invalid catalog file; the message names file and attack id."""


_ALLOWED_KEYS = {"id", "category", "language", "turns", "text", "goal", "marker", "pair", "ci"}
_LANGUAGES = {"de", "en"}


def _fail(path: Path, attack_id: str, message: str) -> CatalogError:
    return CatalogError(f"Katalogdatei {path.name}, Angriff {attack_id}: {message}")


def _non_empty_str(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _parse_entry(path: Path, entry: object, position: int) -> Attack:
    if not isinstance(entry, dict):
        raise _fail(path, f"Nr. {position}", "Eintrag ist kein Block mit Schlüsseln.")
    attack_id = entry.get("id")
    if not _non_empty_str(attack_id):
        raise _fail(path, f"Nr. {position}", "Die Angabe 'id' fehlt oder ist leer.")

    unknown = sorted(set(entry) - _ALLOWED_KEYS)
    if unknown:
        raise _fail(path, attack_id, f"Unbekannte Schlüssel: {', '.join(map(str, unknown))}.")

    try:
        category = Category(entry.get("category"))
    except ValueError:
        raise _fail(path, attack_id, f"Unbekannte Kategorie: {entry.get('category')!r}.") from None

    language = entry.get("language")
    if language not in _LANGUAGES:
        raise _fail(path, attack_id, "Die Sprache muss 'de' oder 'en' sein.")

    if "turns" in entry and "text" in entry:
        raise _fail(path, attack_id, "Entweder 'turns' oder 'text' angeben, nicht beides.")
    if "turns" in entry:
        turns = entry["turns"]
        if not isinstance(turns, list) or not turns or not all(_non_empty_str(t) for t in turns):
            raise _fail(path, attack_id, "'turns' muss eine nicht leere Liste nicht leerer Texte sein.")
        turns = tuple(turns)
    elif _non_empty_str(entry.get("text")):
        turns = (entry["text"],)
    else:
        raise _fail(path, attack_id, "Es fehlt 'turns' oder 'text' (nicht leer).")

    if not _non_empty_str(entry.get("goal")):
        raise _fail(path, attack_id, "Die Angabe 'goal' fehlt oder ist leer.")

    marker = entry.get("marker")
    if marker is not None:
        if not isinstance(marker, str) or not compact(marker):
            raise _fail(path, attack_id, "Das Merkwort ist leer.")
        if compact(marker) in compact(" ".join(turns)):
            raise _fail(path, attack_id, "Das Merkwort steht im Angriffstext. Es muss aus Teilen zusammengesetzt werden.")
    elif category is Category.K1:
        raise _fail(path, attack_id, "K1-Angriffe brauchen ein Merkwort ('marker').")

    pair = entry.get("pair")
    if pair is not None and not isinstance(pair, str):
        raise _fail(path, attack_id, "'pair' muss ein Text sein.")
    ci = entry.get("ci", False)
    if not isinstance(ci, bool):
        raise _fail(path, attack_id, "'ci' muss true oder false sein.")

    return Attack(
        id=attack_id,
        category=category,
        language=language,
        turns=turns,
        goal=entry["goal"],
        marker=marker,
        pair=pair,
        ci=ci,
    )


def load_catalog(
    directory: Path,
    *,
    categories: set[Category] | None = None,
    languages: set[str] | None = None,
    ci_only: bool = False,
) -> list[Attack]:
    attacks: list[Attack] = []
    seen: dict[str, Path] = {}
    for path in sorted(Path(directory).rglob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            raise CatalogError(f"Katalogdatei {path.name}: Ungültiges YAML ({error}).") from error
        if data is None:
            continue
        if not isinstance(data, list):
            raise CatalogError(f"Katalogdatei {path.name}: Erwartet wird eine Liste von Angriffen.")
        for position, entry in enumerate(data, start=1):
            attack = _parse_entry(path, entry, position)
            if attack.id in seen:
                raise _fail(path, attack.id, f"Doppelte ID (schon in {seen[attack.id].name}).")
            seen[attack.id] = path
            attacks.append(attack)

    return [
        a
        for a in attacks
        if (categories is None or a.category in categories)
        and (languages is None or a.language in languages)
        and (not ci_only or a.ci)
    ]

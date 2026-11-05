"""Core data model shared by all chatsec modules."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum


class Category(StrEnum):
    K1 = "K1"
    K2 = "K2"
    K3 = "K3"
    K4 = "K4"
    K5 = "K5"
    K6 = "K6"


class Verdict(StrEnum):
    SUCCESS = "geklappt"
    BLOCKED = "abgewehrt"
    UNCLEAR = "unklar"
    NOT_EVALUATED = "nicht_bewertet"


@dataclass(frozen=True)
class Attack:
    id: str
    category: Category
    language: str
    turns: tuple[str, ...]
    goal: str
    marker: str | None = None
    pair: str | None = None
    ci: bool = False
    source: str = "catalog"


@dataclass(frozen=True)
class Judgement:
    verdict: Verdict
    decided_by: str
    reason: str


@dataclass
class AttemptRecord:
    run_id: str
    target_name: str
    attack_id: str
    category: Category
    attempt: int
    messages: list[dict]
    response: str | None
    error: str | None
    judgement: Judgement
    timestamp: str

    def to_json(self) -> str:
        """Return one JSON line (no trailing newline)."""
        data = asdict(self)
        data["category"] = self.category.value
        data["judgement"]["verdict"] = self.judgement.verdict.value
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> AttemptRecord:
        data = json.loads(line)
        data["category"] = Category(data["category"])
        j = data["judgement"]
        data["judgement"] = Judgement(Verdict(j["verdict"]), j["decided_by"], j["reason"])
        return cls(**data)


@dataclass
class CategoryScore:
    category: Category | None
    success: int
    blocked: int
    unclear: int
    not_evaluated: int
    defense_rate: float | None
    light: str


@dataclass
class RunSummary:
    run_id: str
    target_name: str
    started: str
    finished: str | None
    aborted: bool
    abort_reason: str | None
    overall: CategoryScore
    per_category: dict[Category, CategoryScore]

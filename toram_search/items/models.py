from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Literal

@dataclass(frozen=True)
class ItemSummary:
    id: int
    name: str
    item_type: str

@dataclass(frozen=True)
class ItemDetail:
    summary: ItemSummary
    sell_price: float | None
    process_material: str | None
    process_amount: float | None
    badge: str | None
    note: str | None
    page_url: str | None
    stats: tuple[dict[str, Any], ...]
    sources: tuple[dict[str, Any], ...]
    images: tuple[dict[str, Any], ...]
    upgrade_predecessors: tuple[ItemSummary, ...]
    upgrade_successors: tuple[ItemSummary, ...]

@dataclass(frozen=True)
class ItemStatMatch:
    stat_name: str
    amount: float
    condition_text: str | None = None

@dataclass(frozen=True)
class ItemCardResult:
    item: ItemSummary
    matched_stats: tuple[ItemStatMatch, ...] = ()
    score: float | None = None
    match_kind: str | None = None

ItemOutcomeKind = Literal["results","help","meta","clarify","suggest","refuse","not_found"]

@dataclass(frozen=True)
class ItemSearchOutcome:
    kind: ItemOutcomeKind
    query: str
    results: tuple[ItemCardResult, ...] = ()
    message: str | None = None
    suggested_queries: tuple[str, ...] = ()

@dataclass(frozen=True)
class ParsedClause:
    typed_stat: str
    operator: str
    value: float
    explicit_comparison: bool

@dataclass(frozen=True)
class ParsedAndGroup:
    clauses: tuple[ParsedClause, ...]

@dataclass(frozen=True)
class ParsedStatExpression:
    groups: tuple[ParsedAndGroup, ...]
    item_filter: object | None
    raw_expression: str

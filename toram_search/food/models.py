from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from toram_search.interpretation import QueryInterpretation, RouteQuality


@dataclass(frozen=True)
class FoodStatDefinition:
    key: str
    display: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class FoodEntry:
    code: str
    stat_key: str
    stat_display: str
    level: int


@dataclass(frozen=True)
class FoodDataset:
    stats: tuple[FoodStatDefinition, ...]
    entries: tuple[FoodEntry, ...]
    warnings: tuple[str, ...] = ()


FoodOutcomeKind = Literal['results', 'clarify', 'suggest', 'not_found']


@dataclass(frozen=True)
class FoodSearchOutcome:
    kind: FoodOutcomeKind
    query: str
    results: tuple[FoodEntry, ...] = ()
    message: str | None = None
    suggested_queries: tuple[str, ...] = ()
    interpretation: QueryInterpretation | None = None
    route_quality: RouteQuality = RouteQuality()

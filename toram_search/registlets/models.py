from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from toram_search.interpretation import QueryInterpretation, RouteQuality


@dataclass(frozen=True)
class RegistletRecord:
    name: str
    max_lv: int
    effect: str
    affects_skill: tuple[str, ...] | None
    source: str
    location: str
    source_levels: tuple[int, ...]


@dataclass(frozen=True)
class RegistletDataset:
    records: tuple[RegistletRecord, ...]
    valid_stoodie_levels: tuple[int, ...]
    warnings: tuple[str, ...] = ()


RegistletOutcomeKind = Literal['results', 'clarify', 'suggest', 'not_found']
RegistletMatchKind = Literal['name', 'effect', 'stoodie', 'fuzzy_name']


@dataclass(frozen=True)
class RegistletMatch:
    kind: RegistletMatchKind
    detail: str | None = None


@dataclass(frozen=True)
class RegistletSearchOutcome:
    kind: RegistletOutcomeKind
    query: str
    results: tuple[RegistletRecord, ...] = ()
    message: str | None = None
    suggested_queries: tuple[str, ...] = ()
    interpretation: QueryInterpretation | None = None
    route_quality: RouteQuality = RouteQuality()
    match: RegistletMatch | None = None

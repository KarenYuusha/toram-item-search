from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

from toram_search.interpretation import QueryInterpretation, RouteQuality

@dataclass(frozen=True)
class SkillSection:
    position: int
    label: str
    normalized_label: str
    body: str

@dataclass(frozen=True)
class SkillTree:
    id: str
    name: str
    normalized_name: str
    tree_group: str
    general_text: str
    tier_requirements: tuple[tuple[int, int | None], ...] = ()
    weapon_restrictions: tuple[str, ...] = ()

@dataclass(frozen=True)
class SkillRecord:
    id: str
    tree_id: str
    source_order: int
    name: str
    normalized_name: str
    aliases: tuple[str, ...] = ()
    tier: int | None = None
    required_level: int | None = None
    skill_type: str | None = None
    mp_cost_text: str | None = None
    mp_cost_value: int | None = None
    damage_type: str | None = None
    element: str | None = None
    cast_range_text: str | None = None
    hit_range_text: str | None = None
    cast_time_text: str | None = None
    hit_count_text: str | None = None
    ailments: tuple[str, ...] = ()
    weapon_requirements: tuple[str, ...] = ()
    weapon_restrictions: tuple[str, ...] = ()
    sections: tuple[SkillSection, ...] = ()
    description: str | None = None
    game_description: str | None = None
    raw_text: str = ""

@dataclass(frozen=True)
class SkillFilter:
    tree_ids: tuple[str, ...] = ()
    tiers: tuple[int, ...] = ()
    skill_types: tuple[str, ...] = ()
    ailments: tuple[str, ...] = ()
    weapons: tuple[str, ...] = ()
    required_level_max: int | None = None
    mp_cost_max: int | None = None

@dataclass(frozen=True)
class SkillCardResult:
    skill: SkillRecord
    tree_name: str
    matched_field: str | None = None
    matched_value: str | None = None
    related_registlets: tuple[str, ...] = ()

SkillOutcomeKind = Literal["results", "structured", "compare", "suggest", "refuse", "not_found"]

@dataclass(frozen=True)
class SkillSearchOutcome:
    kind: SkillOutcomeKind
    query: str
    results: tuple[SkillCardResult, ...] = ()
    message: str | None = None
    suggested_queries: tuple[str, ...] = ()
    interpretation: QueryInterpretation | None = None
    route_quality: RouteQuality = RouteQuality()

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from toram_search.interpretation import QueryInterpretation

if TYPE_CHECKING:
    from toram_search.food.models import FoodSearchOutcome
    from toram_search.items.models import ItemSearchOutcome
    from toram_search.registlets.models import RegistletSearchOutcome
    from toram_search.skills.models import SkillSearchOutcome

DatabaseMode = Literal['Universal', 'Items', 'Skills', 'Food', 'Registlets']
SuggestionKind = Literal[
    'Item', 'Skill', 'Skill Tree', 'Stat', 'Item Type', 'Ailment',
    'Food Stat', 'Registlet', 'Stoodie Level',
]


@dataclass(frozen=True)
class DatabaseHealth:
    name: str
    path: Path
    ok: bool
    error: str | None = None


@dataclass(frozen=True)
class AutocompleteSuggestion:
    value: str
    label: str
    kind: SuggestionKind


@dataclass(frozen=True)
class UniversalSearchOutcome:
    query: str
    items: ItemSearchOutcome | None = None
    skills: SkillSearchOutcome | None = None
    food: FoodSearchOutcome | None = None
    registlets: RegistletSearchOutcome | None = None
    interpretation: QueryInterpretation | None = None

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from toram_search.items.models import ItemSearchOutcome
    from toram_search.skills.models import SkillSearchOutcome

DatabaseMode = Literal['Universal', 'Items', 'Skills']
SuggestionKind = Literal['Item', 'Skill', 'Skill Tree', 'Stat', 'Item Type', 'Ailment']


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

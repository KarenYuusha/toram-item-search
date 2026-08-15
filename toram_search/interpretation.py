from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ChipKind = Literal[
    'stat', 'item_type', 'numeric_stat', 'rank',
    'skill_tree', 'ailment', 'mp', 'required_level',
    'food_stat', 'stoodie_level',
]
SearchDomain = Literal['Items', 'Skills', 'Food', 'Registlets']
RouteFamily = Literal['exact', 'structured', 'content', 'weak', 'none']


@dataclass(frozen=True)
class QueryChip:
    id: str
    kind: ChipKind
    label: str
    canonical_fragment: str
    query_without: str
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class QueryInterpretation:
    domain: SearchDomain
    canonical_query: str
    chips: tuple[QueryChip, ...]

    def query_without(self, chip_id: str) -> str:
        for chip in self.chips:
            if chip.id == chip_id:
                return chip.query_without
        raise KeyError(chip_id)


@dataclass(frozen=True)
class RouteQuality:
    family: RouteFamily = 'none'
    has_results: bool = False
    specificity: int = 0

    @property
    def sort_key(self) -> tuple[int, int, int]:
        if self.family in {'exact', 'structured'} and self.has_results:
            result_tier = 4
        elif self.family in {'exact', 'structured'}:
            result_tier = 3
        elif self.family == 'content' and self.has_results:
            result_tier = 2
        elif self.family == 'weak' and self.has_results:
            result_tier = 1
        else:
            result_tier = 0
        family_rank = {'exact': 3, 'structured': 2, 'content': 1, 'weak': 0, 'none': 0}[self.family]
        return result_tier, family_rank, self.specificity

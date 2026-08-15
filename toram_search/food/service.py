from __future__ import annotations

import re
from pathlib import Path

from rapidfuzz import fuzz

from toram_search.interpretation import QueryChip, QueryInterpretation, RouteQuality
from .data import load_food_dataset, normalize_food_text, resolve_food_stat
from .models import FoodSearchOutcome

_FOOD_PREFIX = re.compile(r'^\s*(food|code)(?:\s+|$)(.*)$', re.IGNORECASE)


def is_food_intent(query: str) -> bool:
    return _FOOD_PREFIX.match(str(query)) is not None


class FoodSearchService:
    def __init__(self, entries_path: Path, aliases_path: Path) -> None:
        self.dataset = load_food_dataset(entries_path, aliases_path)

    def list_autocomplete_values(self) -> tuple[tuple[str, str], ...]:
        values = [(f'food {stat.display}', 'Food Stat') for stat in self.dataset.stats]
        return tuple(sorted(values, key=lambda row: row[0].casefold()))

    def _suggestions(self, value: str, *, prefix: str = 'food') -> tuple[str, ...]:
        query = normalize_food_text(value)
        scored: dict[str, float] = {}
        for stat in self.dataset.stats:
            candidates = (stat.key, stat.display, *stat.aliases)
            score = max(float(fuzz.ratio(query, normalize_food_text(candidate))) for candidate in candidates)
            if score >= 70:
                canonical = f'{prefix} {stat.display}'
                scored[canonical] = max(scored.get(canonical, 0.0), score)
        ranked = sorted(scored.items(), key=lambda row: (-row[1], row[0].casefold()))
        return tuple(query for query, _ in ranked[:3])

    def search(self, query: str) -> FoodSearchOutcome:
        raw = ' '.join(str(query).split())
        match = _FOOD_PREFIX.match(raw)
        if match is None:
            return FoodSearchOutcome(
                kind='not_found',
                query=raw,
                message='Food search requires a leading "food" or "code" prefix.',
            )

        prefix = match.group(1).casefold()
        remainder = match.group(2).strip()
        if not remainder:
            return FoodSearchOutcome(
                kind='clarify',
                query=raw,
                message='Enter a Food stat after "food" or "code".',
                route_quality=RouteQuality('structured', False, 1),
            )

        stat = resolve_food_stat(self.dataset, remainder)
        if stat is None:
            return FoodSearchOutcome(
                kind='suggest',
                query=raw,
                message=f'No supported Food stat matches “{remainder}”.',
                suggested_queries=self._suggestions(remainder, prefix=prefix),
                route_quality=RouteQuality('structured', False, 1),
            )

        results = tuple(
            sorted(
                (entry for entry in self.dataset.entries if entry.stat_key == stat.key),
                key=lambda entry: (-entry.level, entry.code),
            )
        )
        interpretation = QueryInterpretation(
            domain='Food',
            canonical_query=f'food {stat.display}',
            chips=(
                QueryChip(
                    id='food_stat',
                    kind='food_stat',
                    label=f'Food: {stat.display}',
                    canonical_fragment=f'food {stat.display}',
                    query_without='',
                ),
            ),
        )
        return FoodSearchOutcome(
            kind='results' if results else 'not_found',
            query=raw,
            results=results,
            message=None if results else f'No Food codes are currently listed for {stat.display}.',
            interpretation=interpretation,
            route_quality=RouteQuality('structured', bool(results), 1),
        )

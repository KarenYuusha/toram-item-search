from __future__ import annotations

from pathlib import Path

from toram_search.database import FOOD_ALIASES, FOOD_ENTRIES, REGISTLET_DATA
from toram_search.food.service import FoodSearchService
from toram_search.interpretation import SearchDomain
from toram_search.items.aliases import STAT_ALIASES, normalize_stat_text
from toram_search.items.service import ItemSearchService
from toram_search.models import AutocompleteSuggestion, DatabaseMode
from toram_search.registlets.service import RegistletSearchService
from toram_search.skills.service import SkillSearchService

_ALLOWED_BY_MODE = {
    'Universal': frozenset({
        'Item', 'Skill', 'Skill Tree', 'Stat', 'Item Type', 'Ailment',
        'Food Stat', 'Registlet', 'Stoodie Level',
    }),
    'Items': frozenset({'Item', 'Stat', 'Item Type'}),
    'Skills': frozenset({'Skill', 'Skill Tree', 'Ailment'}),
    'Food': frozenset({'Food Stat'}),
    'Registlets': frozenset({'Registlet', 'Stoodie Level'}),
}

_ALL_DOMAINS: frozenset[SearchDomain] = frozenset({'Items', 'Skills', 'Food', 'Registlets'})


def _dedupe(rows: list[AutocompleteSuggestion]) -> tuple[AutocompleteSuggestion, ...]:
    seen: set[tuple[str, str]] = set()
    output: list[AutocompleteSuggestion] = []
    for row in sorted(rows, key=lambda value: (value.value.casefold(), value.kind, value.label.casefold())):
        key = (row.value.casefold(), row.kind)
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return tuple(output)


def _item_values(path: Path) -> list[AutocompleteSuggestion]:
    service = ItemSearchService(path)
    try:
        raw_values = service.list_autocomplete_values()
        values = [AutocompleteSuggestion(value, value, kind) for value, kind in raw_values]
        available = {normalize_stat_text(value) for value, kind in raw_values if kind == 'Stat'}
        for alias, canonical in STAT_ALIASES.items():
            if normalize_stat_text(canonical) in available:
                values.append(AutocompleteSuggestion(alias, f'{alias} — {canonical}', 'Stat'))
        return values
    finally:
        service.close()


def _skill_values(path: Path) -> list[AutocompleteSuggestion]:
    service = SkillSearchService(path)
    try:
        return [AutocompleteSuggestion(value, value, kind) for value, kind in service.list_autocomplete_values()]
    finally:
        service.close()


def _food_values(entries_path: Path, aliases_path: Path) -> list[AutocompleteSuggestion]:
    service = FoodSearchService(entries_path, aliases_path)
    return [
        AutocompleteSuggestion(value, value, kind)
        for value, kind in service.list_autocomplete_values()
    ]


def _registlet_values(path: Path) -> list[AutocompleteSuggestion]:
    service = RegistletSearchService(path)
    values = [
        AutocompleteSuggestion(value, value, kind)
        for value, kind in service.list_autocomplete_values()
    ]
    values.extend(
        AutocompleteSuggestion(f'std {level}', f'Stoodie Lv{level}', 'Stoodie Level')
        for level in service.dataset.valid_stoodie_levels
    )
    return values


def build_autocomplete_index(
    mode: DatabaseMode,
    *,
    items_path: Path,
    skills_path: Path,
    food_entries_path: Path = FOOD_ENTRIES,
    food_aliases_path: Path = FOOD_ALIASES,
    registlets_path: Path = REGISTLET_DATA,
    available_domains: frozenset[SearchDomain] | None = None,
) -> tuple[AutocompleteSuggestion, ...]:
    available = available_domains if available_domains is not None else _ALL_DOMAINS
    rows: list[AutocompleteSuggestion] = []
    if mode in {'Universal', 'Items'} and 'Items' in available:
        rows.extend(_item_values(items_path))
    if mode in {'Universal', 'Skills'} and 'Skills' in available:
        rows.extend(_skill_values(skills_path))
    if mode in {'Universal', 'Food'} and 'Food' in available:
        rows.extend(_food_values(food_entries_path, food_aliases_path))
    if mode in {'Universal', 'Registlets'} and 'Registlets' in available:
        rows.extend(_registlet_values(registlets_path))
    return _dedupe(rows)


def suggestions_for_mode(
    suggestions: tuple[AutocompleteSuggestion, ...],
    mode: DatabaseMode,
) -> tuple[AutocompleteSuggestion, ...]:
    allowed = _ALLOWED_BY_MODE[mode]
    return tuple(row for row in suggestions if row.kind in allowed)

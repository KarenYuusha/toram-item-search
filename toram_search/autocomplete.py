from __future__ import annotations

from pathlib import Path

from toram_search.items.aliases import STAT_ALIASES, normalize_stat_text
from toram_search.items.service import ItemSearchService
from toram_search.models import AutocompleteSuggestion, DatabaseMode
from toram_search.skills.service import SkillSearchService

_ALLOWED_BY_MODE = {
    'Universal': frozenset({'Item', 'Skill', 'Skill Tree', 'Stat', 'Item Type', 'Ailment'}),
    'Items': frozenset({'Item', 'Stat', 'Item Type'}),
    'Skills': frozenset({'Skill', 'Skill Tree', 'Ailment'}),
}


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


def build_autocomplete_index(
    mode: DatabaseMode,
    *,
    items_path: Path,
    skills_path: Path,
) -> tuple[AutocompleteSuggestion, ...]:
    rows: list[AutocompleteSuggestion] = []
    if mode in {'Universal', 'Items'}:
        rows.extend(_item_values(items_path))
    if mode in {'Universal', 'Skills'}:
        rows.extend(_skill_values(skills_path))
    return _dedupe(rows)


def suggestions_for_mode(
    suggestions: tuple[AutocompleteSuggestion, ...],
    mode: DatabaseMode,
) -> tuple[AutocompleteSuggestion, ...]:
    allowed = _ALLOWED_BY_MODE[mode]
    return tuple(row for row in suggestions if row.kind in allowed)

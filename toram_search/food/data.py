from __future__ import annotations

import csv
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import FoodDataset, FoodEntry, FoodStatDefinition


class FoodDataError(ValueError):
    pass


def normalize_food_text(value: str) -> str:
    text = str(value).casefold().strip()
    text = text.replace('.', '')
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s*%\s*', '%', text)
    text = re.sub(r'\s*\+\s*', '+', text)
    text = re.sub(r'\s*-\s*', '-', text)
    return text.strip()


def _load_aliases(path: Path) -> tuple[tuple[FoodStatDefinition, ...], dict[str, FoodStatDefinition]]:
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise FoodDataError(f'Unable to read Food aliases: {exc}') from exc

    if not isinstance(raw, dict) or not isinstance(raw.get('stats'), list):
        raise FoodDataError('Food aliases must contain a top-level stats array.')

    definitions: list[FoodStatDefinition] = []
    lookup: dict[str, FoodStatDefinition] = {}
    for index, row in enumerate(raw['stats'], start=1):
        if not isinstance(row, dict):
            raise FoodDataError(f'Food alias record {index} must be an object.')
        key = str(row.get('key') or '').strip()
        display = str(row.get('display') or '').strip()
        aliases_raw: Any = row.get('aliases', [])
        if not key or not display or not isinstance(aliases_raw, list):
            raise FoodDataError(f'Food alias record {index} is missing key/display/aliases.')
        aliases = tuple(str(value).strip() for value in aliases_raw if str(value).strip())
        definition = FoodStatDefinition(key=key, display=display, aliases=aliases)
        definitions.append(definition)
        for candidate in (key, display, *aliases):
            normalized = normalize_food_text(candidate)
            existing = lookup.get(normalized)
            if existing is not None and existing.key != definition.key:
                raise FoodDataError(
                    f'Food alias {candidate!r} maps to both {existing.key!r} and {definition.key!r}.'
                )
            lookup[normalized] = definition

    if not definitions:
        raise FoodDataError('Food aliases contain no stat definitions.')
    return tuple(definitions), lookup


def _load_uncached(entries_path: Path, aliases_path: Path) -> FoodDataset:
    stats, lookup = _load_aliases(aliases_path)
    try:
        handle = entries_path.open('r', encoding='utf-8-sig', newline='')
    except OSError as exc:
        raise FoodDataError(f'Unable to read Food entries: {exc}') from exc

    warnings: list[str] = []
    entries: list[FoodEntry] = []
    seen: set[tuple[str, str, int]] = set()
    with handle:
        reader = csv.DictReader(handle)
        required = {'code', 'stat', 'level'}
        if reader.fieldnames is None or not required <= {str(name).strip() for name in reader.fieldnames}:
            raise FoodDataError('Food entries CSV must contain code, stat, and level columns.')
        for row_number, row in enumerate(reader, start=2):
            code = str(row.get('code') or '').strip()
            raw_stat = str(row.get('stat') or '').strip()
            raw_level = str(row.get('level') or '').strip()
            if not code:
                warnings.append(f'Food row {row_number}: code is required; row skipped.')
                continue
            definition = lookup.get(normalize_food_text(raw_stat))
            if definition is None:
                warnings.append(f'Food row {row_number}: unknown stat {raw_stat!r}; row skipped.')
                continue
            try:
                level = int(raw_level)
            except ValueError:
                warnings.append(f'Food row {row_number}: level must be an integer; row skipped.')
                continue
            key = (code, definition.key, level)
            if key in seen:
                continue
            seen.add(key)
            entries.append(FoodEntry(code, definition.key, definition.display, level))
    return FoodDataset(stats=stats, entries=tuple(entries), warnings=tuple(warnings))


@lru_cache(maxsize=16)
def _cached_load(
    entries_name: str,
    entries_mtime: int,
    entries_size: int,
    aliases_name: str,
    aliases_mtime: int,
    aliases_size: int,
) -> FoodDataset:
    return _load_uncached(Path(entries_name), Path(aliases_name))


def load_food_dataset(entries_path: Path, aliases_path: Path) -> FoodDataset:
    entries = Path(entries_path).expanduser().resolve()
    aliases = Path(aliases_path).expanduser().resolve()
    try:
        entries_stat = entries.stat()
        aliases_stat = aliases.stat()
    except OSError as exc:
        raise FoodDataError(f'Unable to access Food source: {exc}') from exc
    return _cached_load(
        str(entries),
        entries_stat.st_mtime_ns,
        entries_stat.st_size,
        str(aliases),
        aliases_stat.st_mtime_ns,
        aliases_stat.st_size,
    )


def resolve_food_stat(dataset: FoodDataset, value: str) -> FoodStatDefinition | None:
    normalized = normalize_food_text(value)
    for definition in dataset.stats:
        if normalized in {
            normalize_food_text(definition.key),
            normalize_food_text(definition.display),
            *(normalize_food_text(alias) for alias in definition.aliases),
        }:
            return definition
    return None

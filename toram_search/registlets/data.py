from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import RegistletDataset, RegistletRecord


class RegistletDataError(ValueError):
    pass


def _load_uncached(path: Path) -> RegistletDataset:
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistletDataError(f'Unable to read Registlet source: {exc}') from exc

    if not isinstance(raw, dict):
        raise RegistletDataError('Registlet source must be a JSON object.')
    metadata = raw.get('metadata')
    records_raw = raw.get('registlets')
    if not isinstance(metadata, dict) or not isinstance(records_raw, list):
        raise RegistletDataError('Registlet source requires metadata and a registlets array.')

    levels_raw: Any = metadata.get('valid_stoodie_levels')
    if not isinstance(levels_raw, list) or not levels_raw or not all(type(level) is int for level in levels_raw):
        raise RegistletDataError('Registlet metadata requires integer valid_stoodie_levels.')
    valid_levels = tuple(sorted(set(int(level) for level in levels_raw)))
    valid_level_set = set(valid_levels)

    warnings: list[str] = []
    records: list[RegistletRecord] = []
    for index, row in enumerate(records_raw, start=1):
        if not isinstance(row, dict):
            warnings.append(f'Registlet record {index}: record must be an object; skipped.')
            continue
        name = str(row.get('name') or '').strip()
        effect = str(row.get('effect') or '').strip()
        max_lv = row.get('max_lv')
        affects_raw = row.get('affects_skill')
        obtained = row.get('obtained_from')

        if not name:
            warnings.append(f'Registlet record {index}: name is required; skipped.')
            continue
        if type(max_lv) is not int:
            warnings.append(f'Registlet record {index}: max_lv must be an integer; skipped.')
            continue
        if not effect:
            warnings.append(f'Registlet record {index}: effect is required; skipped.')
            continue
        if affects_raw is not None and not (
            isinstance(affects_raw, list) and all(isinstance(value, str) for value in affects_raw)
        ):
            warnings.append(f'Registlet record {index}: affects_skill must be null or an array of strings; skipped.')
            continue
        if not isinstance(obtained, dict):
            warnings.append(f'Registlet record {index}: obtained_from must be an object; skipped.')
            continue

        source = str(obtained.get('source') or '').strip()
        location = str(obtained.get('location') or '').strip()
        source_levels_raw = obtained.get('levels')
        if not source or not isinstance(source_levels_raw, list) or not source_levels_raw or not all(
            type(level) is int for level in source_levels_raw
        ):
            warnings.append(f'Registlet record {index}: obtained_from requires source and integer levels; skipped.')
            continue
        invalid_levels = sorted(set(int(level) for level in source_levels_raw) - valid_level_set)
        if invalid_levels:
            warnings.append(
                f'Registlet record {index}: invalid Stoodie level(s) '
                f'{", ".join(str(level) for level in invalid_levels)}; skipped.'
            )
            continue

        affects_skill = None
        if affects_raw is not None:
            affects_skill = tuple(value.strip() for value in affects_raw if value.strip())
        records.append(
            RegistletRecord(
                name=name,
                max_lv=int(max_lv),
                effect=effect,
                affects_skill=affects_skill,
                source=source,
                location=location,
                source_levels=tuple(int(level) for level in source_levels_raw),
            )
        )

    return RegistletDataset(
        records=tuple(records),
        valid_stoodie_levels=valid_levels,
        warnings=tuple(warnings),
    )


@lru_cache(maxsize=16)
def _cached_load(path_name: str, mtime_ns: int, size: int) -> RegistletDataset:
    return _load_uncached(Path(path_name))


def load_registlet_dataset(path: Path) -> RegistletDataset:
    resolved = Path(path).expanduser().resolve()
    try:
        stat = resolved.stat()
    except OSError as exc:
        raise RegistletDataError(f'Unable to access Registlet source: {exc}') from exc
    return _cached_load(str(resolved), stat.st_mtime_ns, stat.st_size)

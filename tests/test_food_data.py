import json
from pathlib import Path

import pytest

from toram_search.food.data import FoodDataError, load_food_dataset, resolve_food_stat


def _write_aliases(path: Path) -> None:
    path.write_text(
        json.dumps({
            'stats': [
                {
                    'key': 'physical_resistance_pct',
                    'display': 'Physical Resistance %',
                    'aliases': ['physical resist', 'p res'],
                },
                {
                    'key': 'maxmp',
                    'display': 'MaxMP',
                    'aliases': ['max mp', 'mp'],
                },
            ]
        }),
        encoding='utf-8',
    )


def test_food_loader_resolves_key_display_alias_and_deduplicates(tmp_path: Path) -> None:
    aliases = tmp_path / 'aliases.json'
    _write_aliases(aliases)
    entries = tmp_path / 'food.csv'
    entries.write_text(
        'code,stat,level\n'
        '00123,physical_resistance_pct,10\n'
        '00123,P. Res,10\n'
        '00456,Physical Resistance %,8\n',
        encoding='utf-8',
    )

    dataset = load_food_dataset(entries, aliases)

    assert [(row.code, row.stat_key, row.level) for row in dataset.entries] == [
        ('00123', 'physical_resistance_pct', 10),
        ('00456', 'physical_resistance_pct', 8),
    ]
    assert resolve_food_stat(dataset, 'p. res').key == 'physical_resistance_pct'
    assert resolve_food_stat(dataset, 'Physical Resistance %').display == 'Physical Resistance %'


def test_food_loader_preserves_leading_zero_codes(tmp_path: Path) -> None:
    aliases = tmp_path / 'aliases.json'
    _write_aliases(aliases)
    entries = tmp_path / 'food.csv'
    entries.write_text('code,stat,level\n000123,maxmp,10\n', encoding='utf-8')

    dataset = load_food_dataset(entries, aliases)

    assert dataset.entries[0].code == '000123'


def test_food_loader_skips_bad_rows_with_row_numbered_warnings(tmp_path: Path) -> None:
    aliases = tmp_path / 'aliases.json'
    _write_aliases(aliases)
    entries = tmp_path / 'food.csv'
    entries.write_text(
        'code,stat,level\n'
        '111,maxmp,10\n'
        ',maxmp,9\n'
        '222,unknown stat,8\n'
        '333,maxmp,not-a-number\n',
        encoding='utf-8',
    )

    dataset = load_food_dataset(entries, aliases)

    assert [(row.code, row.level) for row in dataset.entries] == [('111', 10)]
    assert len(dataset.warnings) == 3
    assert any('row 3' in warning.lower() and 'code' in warning.lower() for warning in dataset.warnings)
    assert any('row 4' in warning.lower() and 'unknown stat' in warning.lower() for warning in dataset.warnings)
    assert any('row 5' in warning.lower() and 'level' in warning.lower() for warning in dataset.warnings)


def test_food_loader_does_not_fuzzy_reinterpret_unknown_stat(tmp_path: Path) -> None:
    aliases = tmp_path / 'aliases.json'
    _write_aliases(aliases)
    entries = tmp_path / 'food.csv'
    entries.write_text('code,stat,level\n111,maxmpp,10\n', encoding='utf-8')

    dataset = load_food_dataset(entries, aliases)

    assert dataset.entries == ()
    assert any('maxmpp' in warning.lower() for warning in dataset.warnings)


def test_food_loader_rejects_malformed_alias_source(tmp_path: Path) -> None:
    aliases = tmp_path / 'aliases.json'
    aliases.write_text('{broken', encoding='utf-8')
    entries = tmp_path / 'food.csv'
    entries.write_text('code,stat,level\n111,maxmp,10\n', encoding='utf-8')

    with pytest.raises(FoodDataError):
        load_food_dataset(entries, aliases)


def test_food_loader_rejects_missing_source(tmp_path: Path) -> None:
    aliases = tmp_path / 'aliases.json'
    _write_aliases(aliases)

    with pytest.raises(FoodDataError):
        load_food_dataset(tmp_path / 'missing.csv', aliases)

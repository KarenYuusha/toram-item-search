import json
from pathlib import Path

from toram_search.autocomplete import build_autocomplete_index, suggestions_for_mode


def _write_sources(tmp_path: Path) -> tuple[Path, Path, Path]:
    food_entries = tmp_path / 'food_entries.csv'
    food_aliases = tmp_path / 'food_aliases.json'
    registlets = tmp_path / 'registlets.json'

    food_aliases.write_text(json.dumps({
        'stats': [
            {'key': 'maxmp', 'display': 'MaxMP', 'aliases': ['max mp', 'mp']},
            {'key': 'critical_rate', 'display': 'Critical Rate', 'aliases': ['cr']},
        ]
    }), encoding='utf-8')
    food_entries.write_text('code,stat,level\n111,maxmp,10\n', encoding='utf-8')
    registlets.write_text(json.dumps({
        'metadata': {'valid_stoodie_levels': [210, 220]},
        'registlets': [{
            'name': 'Arrow Rain Enhancer',
            'max_lv': 2,
            'effect': 'Adds another hit.',
            'affects_skill': None,
            'obtained_from': {
                'source': 'Stoodie', 'location': 'El Scaro',
                'level_notation': '220', 'levels': [220],
            },
        }],
    }), encoding='utf-8')
    return food_entries, food_aliases, registlets


def test_food_mode_autocomplete_uses_required_prefix(tmp_path: Path) -> None:
    food_entries, food_aliases, registlets = _write_sources(tmp_path)

    suggestions = build_autocomplete_index(
        'Food',
        items_path=tmp_path / 'missing-items.sqlite',
        skills_path=tmp_path / 'missing-skills.sqlite',
        food_entries_path=food_entries,
        food_aliases_path=food_aliases,
        registlets_path=registlets,
        available_domains=frozenset({'Food'}),
    )

    assert any(row.kind == 'Food Stat' and row.value == 'food MaxMP' for row in suggestions)
    assert any(row.kind == 'Food Stat' and row.value == 'food Critical Rate' for row in suggestions)
    assert not any(row.kind == 'Food Stat' and row.value == 'MaxMP' for row in suggestions)
    assert all(row.kind == 'Food Stat' for row in suggestions)


def test_registlet_mode_autocomplete_includes_names_and_metadata_levels(tmp_path: Path) -> None:
    food_entries, food_aliases, registlets = _write_sources(tmp_path)

    suggestions = build_autocomplete_index(
        'Registlets',
        items_path=tmp_path / 'missing-items.sqlite',
        skills_path=tmp_path / 'missing-skills.sqlite',
        food_entries_path=food_entries,
        food_aliases_path=food_aliases,
        registlets_path=registlets,
        available_domains=frozenset({'Registlets'}),
    )

    assert any(row.kind == 'Registlet' and row.value == 'Arrow Rain Enhancer' for row in suggestions)
    assert any(row.kind == 'Stoodie Level' and row.value == 'std 220' for row in suggestions)
    assert all(row.kind in {'Registlet', 'Stoodie Level'} for row in suggestions)


def test_universal_autocomplete_skips_unavailable_domains(tmp_path: Path) -> None:
    food_entries, food_aliases, registlets = _write_sources(tmp_path)

    suggestions = build_autocomplete_index(
        'Universal',
        items_path=tmp_path / 'missing-items.sqlite',
        skills_path=tmp_path / 'missing-skills.sqlite',
        food_entries_path=food_entries,
        food_aliases_path=food_aliases,
        registlets_path=registlets,
        available_domains=frozenset({'Food', 'Registlets'}),
    )

    assert {row.kind for row in suggestions} <= {'Food Stat', 'Registlet', 'Stoodie Level'}
    assert any(row.kind == 'Food Stat' for row in suggestions)
    assert any(row.kind == 'Registlet' for row in suggestions)


def test_suggestions_for_new_modes_filter_domain_kinds(tmp_path: Path) -> None:
    food_entries, food_aliases, registlets = _write_sources(tmp_path)
    suggestions = build_autocomplete_index(
        'Universal',
        items_path=tmp_path / 'missing-items.sqlite',
        skills_path=tmp_path / 'missing-skills.sqlite',
        food_entries_path=food_entries,
        food_aliases_path=food_aliases,
        registlets_path=registlets,
        available_domains=frozenset({'Food', 'Registlets'}),
    )

    assert all(row.kind == 'Food Stat' for row in suggestions_for_mode(suggestions, 'Food'))
    assert all(
        row.kind in {'Registlet', 'Stoodie Level'}
        for row in suggestions_for_mode(suggestions, 'Registlets')
    )

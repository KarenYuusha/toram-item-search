import json
from pathlib import Path

import pytest

from toram_search.registlets.service import RegistletSearchService, is_stoodie_intent


@pytest.fixture
def registlet_file(tmp_path: Path) -> Path:
    path = tmp_path / 'registlets.json'
    path.write_text(
        json.dumps({
            'metadata': {'valid_stoodie_levels': [190, 210, 220]},
            'registlets': [
                {
                    'name': 'Arrow Rain Enhancer',
                    'max_lv': 2,
                    'effect': 'Adds another hit to Arrow Rain.',
                    'affects_skill': ['Arrow Rain'],
                    'obtained_from': {
                        'source': 'Stoodie', 'location': 'El Scaro',
                        'level_notation': '190 & 220', 'levels': [190, 220],
                    },
                },
                {
                    'name': 'Direct MP Recovery',
                    'max_lv': 10,
                    'effect': 'Restores MP when a monster is defeated.',
                    'affects_skill': None,
                    'obtained_from': {
                        'source': 'Stoodie', 'location': 'El Scaro',
                        'level_notation': '210 & 220', 'levels': [210, 220],
                    },
                },
                {
                    'name': 'Split MP Recovery',
                    'max_lv': 10,
                    'effect': 'MP is restored after battle ends.',
                    'affects_skill': None,
                    'obtained_from': {
                        'source': 'Stoodie', 'location': 'El Scaro',
                        'level_notation': '220', 'levels': [220],
                    },
                },
                {
                    'name': 'Physical Pierce Boost',
                    'max_lv': 10,
                    'effect': 'Increases Physical Pierce by 1% per level.',
                    'affects_skill': None,
                    'obtained_from': {
                        'source': 'Stoodie', 'location': 'El Scaro',
                        'level_notation': '190', 'levels': [190],
                    },
                },
                {
                    'name': 'Stun Guard',
                    'max_lv': 1,
                    'effect': 'Prevents an attack that inflicts Stun.',
                    'affects_skill': None,
                    'obtained_from': {
                        'source': 'Stoodie', 'location': 'El Scaro',
                        'level_notation': '210', 'levels': [210],
                    },
                },
            ],
        }),
        encoding='utf-8',
    )
    return path


@pytest.mark.parametrize('query', [
    'std 220', 'std lv 220', 'std lvl220', 'std level 220',
    'stoodie 220', 'stoodie lvl 220',
])
def test_stoodie_aliases_use_explicit_source_levels(registlet_file: Path, query: str) -> None:
    outcome = RegistletSearchService(registlet_file).search(query)

    assert is_stoodie_intent(query) is True
    assert outcome.route_quality.family == 'structured'
    assert [row.name for row in outcome.results] == [
        'Arrow Rain Enhancer', 'Direct MP Recovery', 'Split MP Recovery'
    ]
    assert all(220 in row.source_levels for row in outcome.results)
    assert outcome.interpretation is not None
    assert outcome.interpretation.chips[0].label == 'Stoodie Lv220'


def test_invalid_stoodie_level_suggests_nearest_metadata_levels(registlet_file: Path) -> None:
    outcome = RegistletSearchService(registlet_file).search('std 200')

    assert outcome.route_quality.family == 'structured'
    assert outcome.results == ()
    assert outcome.suggested_queries == ('std 190', 'std 210')


def test_exact_name_outranks_effect_content(registlet_file: Path) -> None:
    outcome = RegistletSearchService(registlet_file).search('Arrow Rain Enhancer')

    assert outcome.route_quality.family == 'exact'
    assert [row.name for row in outcome.results] == ['Arrow Rain Enhancer']
    assert outcome.interpretation is None


def test_exact_name_is_case_insensitive(registlet_file: Path) -> None:
    outcome = RegistletSearchService(registlet_file).search('arrow rain enhancer')
    assert [row.name for row in outcome.results] == ['Arrow Rain Enhancer']
    assert outcome.route_quality.family == 'exact'


def test_effect_phrase_match_is_content_route(registlet_file: Path) -> None:
    outcome = RegistletSearchService(registlet_file).search('restores mp')

    assert outcome.route_quality.family == 'content'
    assert [row.name for row in outcome.results] == ['Direct MP Recovery']
    assert outcome.interpretation is None


def test_effect_all_token_match_uses_whole_tokens(registlet_file: Path) -> None:
    outcome = RegistletSearchService(registlet_file).search('mp restored')

    assert outcome.route_quality.family == 'content'
    assert [row.name for row in outcome.results] == ['Split MP Recovery']


def test_effect_search_does_not_use_substring_or_fuzzy_text_matching(registlet_file: Path) -> None:
    substring = RegistletSearchService(registlet_file).search('pier')
    typo = RegistletSearchService(registlet_file).search('restorse mp')

    assert not any(row.name == 'Physical Pierce Boost' for row in substring.results)
    assert not any(row.name == 'Direct MP Recovery' for row in typo.results)


def test_fuzzy_name_fallback_recovers_registlet_typo(registlet_file: Path) -> None:
    outcome = RegistletSearchService(registlet_file).search('Arrow Rain Enhancerr')

    assert outcome.route_quality.family == 'weak'
    assert [row.name for row in outcome.results] == ['Arrow Rain Enhancer']


def test_registlet_autocomplete_contains_names_only(registlet_file: Path) -> None:
    values = RegistletSearchService(registlet_file).list_autocomplete_values()

    assert ('Arrow Rain Enhancer', 'Registlet') in values
    assert not any(value == 'restores mp' for value, _ in values)

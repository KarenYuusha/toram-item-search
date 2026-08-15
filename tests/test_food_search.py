import json
from pathlib import Path

import pytest

from toram_search.food.service import FoodSearchService, is_food_intent


@pytest.fixture
def food_files(tmp_path: Path) -> tuple[Path, Path]:
    entries = tmp_path / 'food_entries.csv'
    aliases = tmp_path / 'food_aliases.json'
    aliases.write_text(
        json.dumps({
            'stats': [
                {'key': 'maxmp', 'display': 'MaxMP', 'aliases': ['max mp', 'mp']},
                {
                    'key': 'attack_mp_recovery',
                    'display': 'Attack MP Recovery',
                    'aliases': ['ampr', 'attack mp recovery'],
                },
                {
                    'key': 'stronger_against_dark_pct',
                    'display': 'Stronger Against Dark %',
                    'aliases': ['dt dark', 'dte dark'],
                },
                {
                    'key': 'negative_aggro_pct',
                    'display': '-Aggro %',
                    'aliases': ['-aggro', '-aggro%', 'negative aggro'],
                },
            ]
        }),
        encoding='utf-8',
    )
    entries.write_text(
        'code,stat,level\n'
        '900,maxmp,8\n'
        '100,maxmp,10\n'
        '200,maxmp,10\n'
        '300,attack_mp_recovery,10\n'
        '400,stronger_against_dark_pct,10\n'
        '500,negative_aggro_pct,10\n',
        encoding='utf-8',
    )
    return entries, aliases


@pytest.mark.parametrize('query', ['food maxmp', 'code max mp'])
def test_food_search_requires_prefix_and_orders_highest_level_first(
    food_files: tuple[Path, Path], query: str
) -> None:
    outcome = FoodSearchService(*food_files).search(query)

    assert outcome.route_quality.family == 'structured'
    assert [(row.level, row.code) for row in outcome.results] == [
        (10, '100'), (10, '200'), (8, '900')
    ]
    assert outcome.interpretation is not None
    assert outcome.interpretation.domain == 'Food'
    assert outcome.interpretation.chips[0].label == 'Food: MaxMP'
    assert outcome.interpretation.query_without('food_stat') == ''


@pytest.mark.parametrize('query', ['maxmp', 'maxmp food', '51110000'])
def test_food_does_not_activate_without_leading_prefix(
    food_files: tuple[Path, Path], query: str
) -> None:
    outcome = FoodSearchService(*food_files).search(query)

    assert is_food_intent(query) is False
    assert outcome.route_quality.family == 'none'
    assert outcome.results == ()
    assert outcome.interpretation is None


@pytest.mark.parametrize(
    ('query', 'expected_key'),
    [
        ('code ampr', 'attack_mp_recovery'),
        ('food dt dark', 'stronger_against_dark_pct'),
        ('food -aggro', 'negative_aggro_pct'),
    ],
)
def test_food_search_resolves_supported_aliases(
    food_files: tuple[Path, Path], query: str, expected_key: str
) -> None:
    outcome = FoodSearchService(*food_files).search(query)

    assert [row.stat_key for row in outcome.results] == [expected_key]
    assert outcome.route_quality.family == 'structured'


def test_food_prefix_without_stat_is_recognized_strong_intent(food_files: tuple[Path, Path]) -> None:
    outcome = FoodSearchService(*food_files).search('food')

    assert is_food_intent('food') is True
    assert outcome.route_quality.family == 'structured'
    assert outcome.results == ()
    assert 'stat' in (outcome.message or '').casefold()


def test_unknown_food_stat_does_not_become_a_result(food_files: tuple[Path, Path]) -> None:
    outcome = FoodSearchService(*food_files).search('food maxmpp')

    assert outcome.route_quality.family == 'structured'
    assert outcome.results == ()
    assert outcome.suggested_queries
    assert all(query.startswith('food ') for query in outcome.suggested_queries)
    assert 'food MaxMP' in outcome.suggested_queries


def test_food_autocomplete_values_are_always_prefixed(food_files: tuple[Path, Path]) -> None:
    values = FoodSearchService(*food_files).list_autocomplete_values()

    assert ('food MaxMP', 'Food Stat') in values
    assert all(value.startswith('food ') for value, _ in values)

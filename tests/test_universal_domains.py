from toram_search.database import (
    FOOD_ALIASES,
    FOOD_ENTRIES,
    ITEM_DATABASE,
    REGISTLET_DATA,
    SKILL_DATABASE,
)
from toram_search.interpretation import RouteQuality
from toram_search.router import search_database, select_surviving_domains


def test_exact_route_suppresses_content_and_weak() -> None:
    survivors = select_surviving_domains({
        'Skills': RouteQuality('exact', True, 1),
        'Registlets': RouteQuality('content', True, 99),
        'Items': RouteQuality('weak', True, 99),
    })
    assert survivors == frozenset({'Skills'})


def test_structured_no_result_suppresses_content_result() -> None:
    survivors = select_surviving_domains({
        'Food': RouteQuality('structured', False, 1),
        'Registlets': RouteQuality('content', True, 9),
    })
    assert survivors == frozenset({'Food'})


def test_equal_quality_routes_can_coexist() -> None:
    survivors = select_surviving_domains({
        'Items': RouteQuality('structured', True, 2),
        'Skills': RouteQuality('structured', True, 2),
    })
    assert survivors == frozenset({'Items', 'Skills'})


def test_specificity_not_result_count_breaks_quality_ties() -> None:
    survivors = select_surviving_domains({
        'Skills': RouteQuality('exact', True, 1),
        'Registlets': RouteQuality('content', True, 500),
    })
    assert survivors == frozenset({'Skills'})


def _search(query: str, *, available_domains=None):
    return search_database(
        'Universal',
        query,
        items_path=ITEM_DATABASE,
        skills_path=SKILL_DATABASE,
        food_entries_path=FOOD_ENTRIES,
        food_aliases_path=FOOD_ALIASES,
        registlets_path=REGISTLET_DATA,
        available_domains=available_domains,
    )


def test_explicit_food_route_returns_food_and_suppresses_weaker_domains() -> None:
    outcome = _search('food maxmp')

    assert outcome.food is not None
    assert outcome.food.results
    assert outcome.food.route_quality.family == 'structured'
    assert outcome.interpretation is not None
    assert outcome.interpretation.domain == 'Food'
    assert outcome.items is None or not outcome.items.results
    assert outcome.skills is None or not outcome.skills.results
    assert outcome.registlets is None or not outcome.registlets.results


def test_stoodie_route_returns_registlets_and_suppresses_weaker_domains() -> None:
    outcome = _search('std 220')

    assert outcome.registlets is not None
    assert outcome.registlets.results
    assert outcome.registlets.route_quality.family == 'structured'
    assert outcome.interpretation is not None
    assert outcome.interpretation.domain == 'Registlets'
    assert outcome.items is None or not outcome.items.results
    assert outcome.skills is None or not outcome.skills.results
    assert outcome.food is None or not outcome.food.results


def test_registlet_effect_content_outranks_weak_other_domains() -> None:
    outcome = _search('restores mp')

    assert outcome.registlets is not None
    assert outcome.registlets.results
    assert outcome.registlets.route_quality.family == 'content'
    assert outcome.items is None or outcome.items.route_quality.sort_key <= outcome.registlets.route_quality.sort_key
    assert outcome.skills is None or outcome.skills.route_quality.sort_key <= outcome.registlets.route_quality.sort_key
    if outcome.items is not None and outcome.items.route_quality.sort_key < outcome.registlets.route_quality.sort_key:
        assert not outcome.items.results
    if outcome.skills is not None and outcome.skills.route_quality.sort_key < outcome.registlets.route_quality.sort_key:
        assert not outcome.skills.results


def test_bare_maxmp_never_activates_food() -> None:
    outcome = _search('maxmp')

    assert outcome.food is not None
    assert outcome.food.route_quality.family == 'none'
    assert outcome.food.results == ()


def test_exact_magic_finale_remains_the_only_surviving_strong_match() -> None:
    outcome = _search('MAGIC: FINALE')

    assert outcome.skills is not None
    assert [row.skill.name.casefold() for row in outcome.skills.results] == ['magic: finale']
    assert outcome.skills.route_quality.family == 'exact'
    assert outcome.items is None or not outcome.items.results
    assert outcome.registlets is None or not outcome.registlets.results


def test_unavailable_explicit_food_intent_does_not_show_weak_unrelated_results() -> None:
    outcome = _search(
        'food maxmp',
        available_domains=frozenset({'Items', 'Skills', 'Registlets'}),
    )

    assert outcome.food is None
    assert outcome.items is None or not outcome.items.results
    assert outcome.skills is None or not outcome.skills.results
    assert outcome.registlets is None or not outcome.registlets.results

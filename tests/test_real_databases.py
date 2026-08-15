import pytest

from toram_search.database import (
    FOOD_ALIASES,
    FOOD_ENTRIES,
    ITEM_DATABASE,
    REGISTLET_DATA,
    SKILL_DATABASE,
    validate_databases,
    validate_sources,
)
from toram_search.food.service import FoodSearchService
from toram_search.items.repository import ItemRepository
from toram_search.items.service import ItemSearchService
from toram_search.registlets.service import RegistletSearchService
from toram_search.router import search_database
from toram_search.skills.repository import SkillRepository
from toram_search.skills.service import SkillSearchService

REAL_DATABASES_AVAILABLE = ITEM_DATABASE.is_file() and SKILL_DATABASE.is_file()
pytestmark = pytest.mark.skipif(not REAL_DATABASES_AVAILABLE, reason='committed databases are unavailable in local mirror')


def test_committed_databases_pass_public_schema_validation() -> None:
    health = validate_databases()
    assert all(row.ok for row in health), health


def test_all_committed_sources_pass_public_validation() -> None:
    health = validate_sources()
    assert all(row.ok for row in health), health


def test_committed_item_database_is_readable_by_public_repository() -> None:
    with ItemRepository(ITEM_DATABASE) as repository:
        assert repository.count_items_total() > 0
        assert repository.list_stat_names()
        assert repository.list_item_types()


def test_committed_skill_database_is_readable_by_public_repository() -> None:
    with SkillRepository(SKILL_DATABASE) as repository:
        assert repository.count_skills() > 0
        assert repository.count_trees() > 0
        assert repository.list_tree_names()


def test_committed_databases_support_representative_searches() -> None:
    item_service = ItemSearchService(ITEM_DATABASE)
    skill_service = SkillSearchService(SKILL_DATABASE)
    try:
        item_outcome = item_service.search('cr bow')
        skill_outcome = skill_service.search('Guardian')
    finally:
        item_service.close()
        skill_service.close()
    assert item_outcome.results
    assert any(row.skill.name.casefold() == 'guardian' for row in skill_outcome.results)


def test_committed_food_sources_support_prefixed_search() -> None:
    outcome = FoodSearchService(FOOD_ENTRIES, FOOD_ALIASES).search('food maxmp')

    assert outcome.results
    assert outcome.route_quality.family == 'structured'
    assert [row.level for row in outcome.results] == sorted(
        (row.level for row in outcome.results), reverse=True
    )


def test_committed_registlets_support_stoodie_and_effect_search() -> None:
    service = RegistletSearchService(REGISTLET_DATA)

    stoodie = service.search('std 220')
    effect = service.search('restores mp')

    assert stoodie.results
    assert stoodie.route_quality.family == 'structured'
    assert effect.results
    assert effect.route_quality.family == 'content'


def test_real_universal_aggro_xtal_wp_suppresses_unrelated_skills() -> None:
    outcome = search_database(
        'Universal',
        'aggro xtal wp',
        items_path=ITEM_DATABASE,
        skills_path=SKILL_DATABASE,
    )
    assert outcome.items is not None
    assert outcome.items.routing_confidence == 'strong'
    assert outcome.items.results
    assert {row.item.item_type.casefold() for row in outcome.items.results} <= {
        'weapon crysta',
        'enhancer crysta (red)',
    }
    item_ids = [row.item.id for row in outcome.items.results]
    assert len(item_ids) == len(set(item_ids))
    assert outcome.skills is not None
    assert not outcome.skills.results


def test_real_aggro_weapon_crysta_query_exposes_item_interpretation() -> None:
    outcome = search_database(
        'Universal',
        'aggro xtal wp',
        items_path=ITEM_DATABASE,
        skills_path=SKILL_DATABASE,
    )
    assert outcome.interpretation is not None
    assert outcome.interpretation.domain == 'Items'
    assert [(chip.kind, chip.label) for chip in outcome.interpretation.chips] == [
        ('stat', 'Aggro %'),
        ('item_type', 'Weapon Crysta'),
    ]
    item_type = next(chip for chip in outcome.interpretation.chips if chip.kind == 'item_type')
    assert outcome.interpretation.query_without(item_type.id) == 'aggro'


def test_real_exact_guardian_has_no_interpretation_chips() -> None:
    outcome = search_database(
        'Universal',
        'Guardian',
        items_path=ITEM_DATABASE,
        skills_path=SKILL_DATABASE,
    )
    assert outcome.skills is not None
    assert any(row.skill.name.casefold() == 'guardian' for row in outcome.skills.results)
    assert outcome.interpretation is None


def test_real_exact_magic_finale_suppresses_weak_item_fallback() -> None:
    outcome = search_database(
        'Universal',
        'MAGIC: FINALE',
        items_path=ITEM_DATABASE,
        skills_path=SKILL_DATABASE,
    )
    assert outcome.skills is not None
    assert [row.skill.name.casefold() for row in outcome.skills.results] == ['magic: finale']
    assert outcome.skills.route_quality.family == 'exact'
    assert outcome.items is not None
    assert not outcome.items.results


def test_real_universal_food_query_returns_food_without_weak_leakage() -> None:
    outcome = search_database(
        'Universal',
        'food maxmp',
        items_path=ITEM_DATABASE,
        skills_path=SKILL_DATABASE,
    )

    assert outcome.food is not None
    assert outcome.food.results
    assert outcome.interpretation is not None
    assert outcome.interpretation.domain == 'Food'
    assert outcome.items is None or not outcome.items.results
    assert outcome.skills is None or not outcome.skills.results
    assert outcome.registlets is None or not outcome.registlets.results


def test_real_bare_maxmp_never_activates_food() -> None:
    outcome = search_database(
        'Universal',
        'maxmp',
        items_path=ITEM_DATABASE,
        skills_path=SKILL_DATABASE,
    )

    assert outcome.food is not None
    assert outcome.food.route_quality.family == 'none'
    assert outcome.food.results == ()

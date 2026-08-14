import pytest

from toram_search.database import ITEM_DATABASE, SKILL_DATABASE, validate_databases
from toram_search.items.repository import ItemRepository
from toram_search.items.service import ItemSearchService
from toram_search.skills.repository import SkillRepository
from toram_search.skills.service import SkillSearchService

REAL_DATABASES_AVAILABLE = ITEM_DATABASE.is_file() and SKILL_DATABASE.is_file()
pytestmark = pytest.mark.skipif(not REAL_DATABASES_AVAILABLE, reason='committed databases are unavailable in local mirror')


def test_committed_databases_pass_public_schema_validation() -> None:
    health = validate_databases()
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

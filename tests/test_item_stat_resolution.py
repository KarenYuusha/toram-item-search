from pathlib import Path
import sqlite3

from tests.item_db_factory import create_item_database
from toram_search.items.service import ItemSearchService


def test_multiword_skill_name_is_not_fuzzy_resolved_as_short_item_stat(tmp_path: Path) -> None:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    db = sqlite3.connect(path)
    db.execute(
        "INSERT INTO item_stats VALUES (11,8,1,'AGI',8,'[]',NULL,NULL,0)"
    )
    db.commit()
    db.close()

    service = ItemSearchService(path)
    try:
        outcome = service.search('MAGIC: FINALE')
    finally:
        service.close()

    assert outcome.route_quality.family != 'structured'
    assert outcome.interpretation is None


def test_full_string_stat_typo_still_resolves(tmp_path: Path) -> None:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    service = ItemSearchService(path)
    try:
        outcome = service.search('critcal rate bow')
    finally:
        service.close()

    assert outcome.route_quality.family == 'structured'
    assert [row.item.name for row in outcome.results] == ['Test Bow']

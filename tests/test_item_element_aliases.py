from pathlib import Path
import sqlite3

import pytest

from tests.item_db_factory import create_item_database
from toram_search.items.aliases import expand_stat_aliases
from toram_search.items.service import ItemSearchService


ELEMENT_ALIASES = (
    ('dte', '% stronger against earth'),
    ('dtf', '% stronger against fire'),
    ('dtw', '% stronger against wind'),
    ('dtwa', '% stronger against water'),
    ('dtn', '% stronger against neutral'),
    ('dtd', '% stronger against dark'),
    ('dtl', '% stronger against light'),
)


@pytest.mark.parametrize(('alias', 'canonical'), ELEMENT_ALIASES)
def test_elemental_damage_aliases_expand_to_database_vocabulary(alias: str, canonical: str) -> None:
    assert expand_stat_aliases(alias) == canonical


def _make_element_service(tmp_path: Path) -> ItemSearchService:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    with sqlite3.connect(path) as db:
        db.executemany(
            'INSERT INTO item_stats VALUES (?,?,?,?,?,?,?,?,?)',
            [
                (20, 1, 2, '% Stronger Against Earth', 10, '[]', None, None, 0),
                (21, 1, 3, '% Stronger Against Fire', 12, '[]', None, None, 0),
            ],
        )
    return ItemSearchService(path)


@pytest.mark.parametrize(
    ('query', 'expected_stat'),
    (
        ('dte bow', '% Stronger Against Earth'),
        ('bow dte', '% Stronger Against Earth'),
        ('dtf bow', '% Stronger Against Fire'),
        ('bow dtf', '% Stronger Against Fire'),
    ),
)
def test_elemental_damage_aliases_work_with_equipment_filters(
    tmp_path: Path,
    query: str,
    expected_stat: str,
) -> None:
    service = _make_element_service(tmp_path)
    try:
        outcome = service.search(query)
    finally:
        service.close()

    assert outcome.kind == 'results'
    assert [row.item.name for row in outcome.results] == ['Test Bow']
    assert outcome.results[0].matched_stats[0].stat_name == expected_stat

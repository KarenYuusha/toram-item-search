from pathlib import Path
import sqlite3

import pytest

from tests.item_db_factory import create_item_database
from toram_search.items.service import ItemSearchService


def _make_three_step_upgrade_service(tmp_path: Path) -> ItemSearchService:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    with sqlite3.connect(path) as db:
        db.execute(
            'INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (9, 1, 'Newest Crystal', 'Normal Crysta', 100, None, None, None, None, None, 'https://example.com/newest', ''),
        )
        db.execute(
            'INSERT INTO item_stats VALUES (?,?,?,?,?,?,?,?,?)',
            (11, 9, 0, 'Upgrade for', 5, '[]', None, None, 0),
        )
    return ItemSearchService(path)


@pytest.mark.parametrize('target', ('Old Crystal', 'New Crystal', 'Newest Crystal'))
def test_upgrade_query_returns_complete_chain_oldest_to_newest(tmp_path: Path, target: str) -> None:
    service = _make_three_step_upgrade_service(tmp_path)
    try:
        outcome = service.search(f'upgrade {target}')
    finally:
        service.close()

    assert outcome.kind == 'results'
    assert [row.item.name for row in outcome.results] == [
        'Old Crystal',
        'New Crystal',
        'Newest Crystal',
    ]


@pytest.mark.parametrize('target', ('Old Crystal', 'New Crystal', 'Newest Crystal'))
def test_upgrade_chain_marks_only_the_searched_crysta(tmp_path: Path, target: str) -> None:
    service = _make_three_step_upgrade_service(tmp_path)
    try:
        outcome = service.search(f'upgrade {target}')
    finally:
        service.close()

    marked = [row.item.name for row in outcome.results if row.match_kind == 'upgrade_target']
    assert marked == [target]
    assert all(row.match_kind in {'upgrade', 'upgrade_target'} for row in outcome.results)


def test_upgrade_query_is_documented_in_item_help_and_examples(tmp_path: Path) -> None:
    main_source = Path('main.py').read_text(encoding='utf-8')
    sidebar_source = Path('ui/sidebar.py').read_text(encoding='utf-8')
    assert "'upgrade Iconos'" in main_source
    assert 'upgrade Iconos' in sidebar_source

    service = _make_three_step_upgrade_service(tmp_path)
    try:
        outcome = service.search('help')
    finally:
        service.close()
    assert outcome.kind == 'help'
    assert 'upgrade <crysta name>' in (outcome.message or '')

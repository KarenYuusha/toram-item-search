from pathlib import Path

from tests.item_db_factory import create_item_database
from toram_search.items.service import ItemSearchService


def test_alias_inside_unrecognized_phrase_keeps_guidance_without_structured_priority(tmp_path: Path) -> None:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    service = ItemSearchService(path)
    try:
        outcome = service.search('restores mp')
    finally:
        service.close()

    assert outcome.kind == 'suggest'
    assert outcome.results == ()
    assert 'could not safely parse' in (outcome.message or '').casefold()
    assert outcome.route_quality.family == 'none'

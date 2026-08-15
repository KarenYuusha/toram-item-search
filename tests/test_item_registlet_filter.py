import json
from pathlib import Path

import pytest

from tests.item_db_factory import add_registlet_contamination, create_item_database
from toram_search.autocomplete import build_autocomplete_index
from toram_search.items.aliases import is_registlet_item_type
from toram_search.items.repository import ItemRepository
from toram_search.items.service import ItemSearchService
from toram_search.router import search_database


@pytest.fixture
def contaminated_items(tmp_path: Path) -> Path:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    add_registlet_contamination(path)
    return path


def make_registlet_json(path: Path, *, name: str = 'Pierce Regislet Item') -> Path:
    path.write_text(
        json.dumps({
            'metadata': {'valid_stoodie_levels': [220]},
            'registlets': [{
                'name': name,
                'max_lv': 10,
                'effect': 'JSON authoritative effect text.',
                'affects_skill': None,
                'obtained_from': {
                    'source': 'Stoodie',
                    'location': 'El Scaro',
                    'level_notation': '220',
                    'levels': [220],
                },
            }],
        }),
        encoding='utf-8',
    )
    return path


def test_registlet_item_type_helper_is_case_and_whitespace_insensitive() -> None:
    assert is_registlet_item_type('Regislet') is True
    assert is_registlet_item_type(' REGISTLET ') is True
    assert is_registlet_item_type('Bow') is False
    assert is_registlet_item_type(None) is False


def test_repository_hides_registlet_types_from_lists_counts_and_stats(contaminated_items: Path) -> None:
    with ItemRepository(contaminated_items) as repository:
        assert repository.count_items_total() == 8
        assert repository.count_items_by_types(('REGISTLET', ' Regislet ')) == 0
        assert repository.count_items_with_stat('Critical Rate') == 3
        assert 'Physical Pierce %' not in repository.list_stat_names()
        assert all(
            row.item_type.strip().casefold() not in {'regislet', 'registlet'}
            for row in repository.list_items()
        )
        assert all(
            value.strip().casefold() not in {'regislet', 'registlet'}
            for value in repository.list_item_types()
        )


def test_repository_denies_direct_detail_and_filters_upgrade_links(contaminated_items: Path) -> None:
    with ItemRepository(contaminated_items) as repository:
        with pytest.raises(KeyError):
            repository.get_item(90)
        with pytest.raises(KeyError):
            repository.get_item(91)
        assert [row.id for row in repository.get_upgrade_predecessors(5)] == [4]
        assert repository.get_upgrade_successors(90) == ()


def test_all_item_search_shapes_hide_contaminated_rows(contaminated_items: Path) -> None:
    service = ItemSearchService(contaminated_items)
    try:
        for query in ('Pierce Regislet Item', 'Pierce Regis', 'physical pierce', 'highest cr'):
            outcome = service.search(query)
            assert all(row.item.id not in {90, 91} for row in outcome.results)
    finally:
        service.close()


def test_item_autocomplete_excludes_contaminated_names(contaminated_items: Path, tmp_path: Path) -> None:
    suggestions = build_autocomplete_index(
        'Items',
        items_path=contaminated_items,
        skills_path=tmp_path / 'missing-skills.sqlite',
        food_entries_path=tmp_path / 'missing-food.csv',
        food_aliases_path=tmp_path / 'missing-food.json',
        registlets_path=tmp_path / 'missing-registlets.json',
        available_domains=frozenset({'Items'}),
    )
    assert not any(
        'regislet item' in row.value.casefold() or 'registlet item' in row.value.casefold()
        for row in suggestions
    )


def test_same_name_uses_json_registlet_and_never_item_row(contaminated_items: Path, tmp_path: Path) -> None:
    registlets = make_registlet_json(tmp_path / 'registlets.json')
    outcome = search_database(
        'Universal',
        'Pierce Regislet Item',
        items_path=contaminated_items,
        skills_path=tmp_path / 'missing-skills.sqlite',
        registlets_path=registlets,
        available_domains=frozenset({'Items', 'Registlets'}),
    )
    assert outcome.items is not None and not outcome.items.results
    assert outcome.registlets is not None
    assert [row.effect for row in outcome.registlets.results] == ['JSON authoritative effect text.']


def test_missing_json_never_reactivates_item_contamination(contaminated_items: Path, tmp_path: Path) -> None:
    outcome = search_database(
        'Universal',
        'Pierce Regislet Item',
        items_path=contaminated_items,
        skills_path=tmp_path / 'missing-skills.sqlite',
        registlets_path=tmp_path / 'missing-registlets.json',
        available_domains=frozenset({'Items'}),
    )
    assert outcome.items is not None and not outcome.items.results
    assert outcome.registlets is None

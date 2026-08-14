from pathlib import Path
import sqlite3

import pytest

from tests.item_db_factory import create_item_database
from toram_search.items.aliases import expand_stat_aliases
from toram_search.items.filters import extract_item_filter
from toram_search.items.repository import ItemRepository
from toram_search.items.service import ItemSearchService
from toram_search.items.stat_query import parse_stat_expression


def make_service(tmp_path: Path) -> ItemSearchService:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    return ItemSearchService(path)


def test_aliases_match_database_vocabulary() -> None:
    assert expand_stat_aliases('cr') == 'critical rate'
    assert expand_stat_aliases('hp') == 'maxhp'


def test_repository_is_read_only_and_loads_detail(tmp_path: Path) -> None:
    path = tmp_path / 'items.sqlite'; create_item_database(path)
    with ItemRepository(path) as repository:
        detail = repository.get_item(1)
        assert detail.summary.name == 'Test Bow'
        assert detail.images[0]['source_url'] == 'https://example.com/test-bow.png'
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            repository.db.execute('DELETE FROM items')


def test_stat_expression_extracts_item_filter() -> None:
    parsed = parse_stat_expression('hp > 400 and cr bow', {'Bow','Armor','Special','Normal Crysta'}, ['MaxHP','Critical Rate'])
    assert parsed.item_filter is not None
    assert parsed.item_filter.item_types == ('Bow',)
    assert len(parsed.groups[0].clauses) == 2


def test_name_search_is_fuzzy(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('test bo')
    finally:
        service.close()
    assert outcome.kind == 'results'
    assert outcome.results[0].item.name == 'Test Bow'


def test_stat_search_ranks_highest_first_and_filters_type(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('cr special')
    finally:
        service.close()
    assert [row.item.name for row in outcome.results] == ['Crit Ring']
    assert outcome.results[0].matched_stats[0].amount == 40


def test_numeric_expression_filters_results(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('hp > 5000 armor')
    finally:
        service.close()
    assert [row.item.name for row in outcome.results] == ['Tank Armor']


def test_upgrade_detail_is_available(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('upgrade New Crystal')
        detail = service.get_item(outcome.results[0].item.id)
    finally:
        service.close()
    assert detail.upgrade_predecessors[0].name == 'Old Crystal'


def test_subjective_build_query_refuses(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('best tank xtal')
    finally:
        service.close()
    assert outcome.kind == 'refuse'


def test_failed_stat_shape_suggests_canonical_query(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('crit bow hp')
    finally:
        service.close()
    assert outcome.kind in {'suggest','clarify'}
    assert any('bow' in q.casefold() for q in outcome.suggested_queries)


def test_crit_bow_offers_clickable_canonical_choice(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('crit bow')
    finally:
        service.close()
    assert outcome.kind == 'clarify'
    assert any(query.casefold() == 'critical rate bow' for query in outcome.suggested_queries)


def test_negative_stat_search_matches_negative_values(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('-aggro special')
    finally:
        service.close()
    assert [row.item.name for row in outcome.results] == ['Low Aggro Ring']


def test_lowest_stat_prefix_sorts_ascending(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('lowest cr')
    finally:
        service.close()
    assert [row.item.name for row in outcome.results[:2]] == ['Unrelated Dagger', 'Test Bow']


def test_highest_stat_prefix_sorts_descending(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('highest cr')
    finally:
        service.close()
    assert [row.item.name for row in outcome.results[:3]] == ['Crit Ring', 'Test Bow', 'Unrelated Dagger']


def test_item_routing_confidence_distinguishes_strong_weak_and_none(tmp_path: Path) -> None:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    service = ItemSearchService(path)
    try:
        assert service.search('Test Bow').routing_confidence == 'strong'
        assert service.search('critical rate bow').routing_confidence == 'strong'
        assert service.search('Test Bo').routing_confidence == 'weak'
        assert service.search('totally unrelated words').routing_confidence == 'none'
    finally:
        service.close()


def test_specific_crysta_slot_aliases_are_order_insensitive(tmp_path: Path) -> None:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    service = ItemSearchService(path)
    try:
        available = service.repository.list_item_types()
        for query in ('aggro xtal wp', 'aggro wp xtal', 'aggro weapon xtal'):
            item_filter, remaining = extract_item_filter(query, available)
            assert item_filter is not None
            assert item_filter.label == 'Weapon Crysta'
            assert set(item_filter.item_types) == {'Weapon Crysta'}
            assert remaining == 'aggro'
    finally:
        service.close()


def test_aggro_xtal_wp_returns_weapon_crysta_not_fuzzy_item(tmp_path: Path) -> None:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    service = ItemSearchService(path)
    try:
        outcome = service.search('aggro xtal wp')
        assert outcome.routing_confidence == 'strong'
        assert [row.item.name for row in outcome.results] == ['Aggro Weapon Crystal']
        assert all(row.item.item_type == 'Weapon Crysta' for row in outcome.results)
    finally:
        service.close()


def test_structured_item_intent_with_unknown_leftover_does_not_fuzzy_match(tmp_path: Path) -> None:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    service = ItemSearchService(path)
    try:
        outcome = service.search('aggro xtal nonsense')
        assert outcome.routing_confidence == 'strong'
        assert outcome.kind in {'suggest', 'not_found'}
        assert not outcome.results
    finally:
        service.close()


def test_rank_items_prefers_prefix_match() -> None:
    from toram_search.items.models import ItemSummary
    from toram_search.items.ranking import rank_items
    rows = rank_items('test bo', [ItemSummary(1,'Test Bow','Bow'), ItemSummary(2,'Bow Test','Bow')])
    assert rows[0].item.name == 'Test Bow'


def test_help_service_is_deterministic() -> None:
    from toram_search.items.help_db import HelpService
    assert 'cr xtal' in (HelpService().answer_direct('how to search') or '')


def test_reconstruction_suggests_canonical_multi_stat_query() -> None:
    from toram_search.items.reconstruction import try_suggest_query
    suggestion = try_suggest_query(
        'crit bow hp',
        available_stats=['Critical Rate','Critical Damage','MaxHP'],
        available_item_types={'Bow','Armor'},
    )
    assert suggestion is not None
    assert 'bow' in suggestion.casefold()


def test_parser_classifies_exact_item(tmp_path: Path) -> None:
    from toram_search.items.parser import parse_search_query
    path = tmp_path / 'items.sqlite'; create_item_database(path)
    with ItemRepository(path) as repository:
        parsed = parse_search_query('Test Bow', repository)
    assert parsed.intent == 'exact_item'
    assert parsed.item_id == 1

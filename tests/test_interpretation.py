import pytest

from toram_search.interpretation import QueryChip, QueryInterpretation, RouteQuality


def test_query_interpretation_returns_precomputed_removal_query() -> None:
    interpretation = QueryInterpretation(
        domain='Items',
        canonical_query='highest critical rate bow',
        chips=(
            QueryChip('rank', 'rank', 'Highest', 'highest', 'critical rate bow', ('stat',)),
            QueryChip('stat', 'stat', 'Critical Rate', 'critical rate', 'bow'),
            QueryChip('item_type', 'item_type', 'Bow', 'bow', 'highest critical rate'),
        ),
    )
    assert interpretation.query_without('item_type') == 'highest critical rate'
    assert interpretation.query_without('stat') == 'bow'


def test_query_interpretation_rejects_unknown_chip_id() -> None:
    interpretation = QueryInterpretation(domain='Items', canonical_query='', chips=())
    with pytest.raises(KeyError, match='missing'):
        interpretation.query_without('missing')


def test_route_quality_matches_approved_priority() -> None:
    assert RouteQuality('exact', True, 1).sort_key > RouteQuality('structured', True, 9).sort_key
    assert RouteQuality('structured', True, 1).sort_key > RouteQuality('structured', False, 9).sort_key
    assert RouteQuality('structured', False, 1).sort_key > RouteQuality('weak', True, 99).sort_key
    assert RouteQuality('weak', True, 1).sort_key > RouteQuality('none', False, 99).sort_key


def test_route_quality_uses_specificity_only_after_route_family() -> None:
    broad = RouteQuality('structured', True, 1)
    narrow = RouteQuality('structured', True, 3)
    assert narrow.sort_key > broad.sort_key

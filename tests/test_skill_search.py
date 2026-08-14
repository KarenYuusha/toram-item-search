from pathlib import Path
import sqlite3
import pytest

from tests.skill_db_factory import create_skill_database
from toram_search.skills.repository import SkillRepository
from toram_search.skills.service import SkillSearchService


def make_service(tmp_path: Path) -> SkillSearchService:
    path=tmp_path/'skills.sqlite'; create_skill_database(path); return SkillSearchService(path)


def test_repository_resolves_alias_and_is_read_only(tmp_path: Path) -> None:
    path=tmp_path/'skills.sqlite'; create_skill_database(path)
    with SkillRepository(path) as repository:
        assert repository.resolve_skill_name('Hardhit')[0].name == 'Hard Hit'
        assert repository.get_skill('shield_skills/hard-hit').sections[0].body == 'Stored Hard Hit mechanics.'
        with pytest.raises(sqlite3.OperationalError,match='readonly'):
            repository.connection.execute('DELETE FROM skills')


def test_exact_skill_lookup_returns_card(tmp_path: Path) -> None:
    service=make_service(tmp_path)
    try: outcome=service.search('Guardian')
    finally: service.close()
    assert outcome.kind == 'results'
    assert outcome.results[0].skill.name == 'Guardian'


def test_mp_cost_lookup_is_structured(tmp_path: Path) -> None:
    service=make_service(tmp_path)
    try: outcome=service.search('guardian mp cost')
    finally: service.close()
    assert outcome.kind == 'structured'
    assert '600' in (outcome.message or '')


def test_tree_query_returns_skills(tmp_path: Path) -> None:
    service=make_service(tmp_path)
    try: outcome=service.search('shield skill tree')
    finally: service.close()
    assert [row.skill.name for row in outcome.results] == ['Guardian','Hard Hit','Shield Bash']


def test_ailment_filter_finds_stun_skill(tmp_path: Path) -> None:
    service=make_service(tmp_path)
    try: outcome=service.search('skills that inflict stun')
    finally: service.close()
    assert [row.skill.name for row in outcome.results] == ['Shield Bash']


def test_lowest_mp_ranking(tmp_path: Path) -> None:
    service=make_service(tmp_path)
    try: outcome=service.search('lowest mp shield skills')
    finally: service.close()
    assert outcome.results[0].skill.name == 'Hard Hit'


def test_how_does_skill_work_uses_stored_detail(tmp_path: Path) -> None:
    service=make_service(tmp_path)
    try: outcome=service.search('how does Hard Hit work?')
    finally: service.close()
    assert outcome.kind == 'structured'
    assert 'Stored Hard Hit mechanics.' in (outcome.message or '')


def test_fts_discovery_uses_database_text(tmp_path: Path) -> None:
    service=make_service(tmp_path)
    try: outcome=service.search('protects party members')
    finally: service.close()
    assert outcome.results[0].skill.name == 'Guardian'


def test_compare_two_skills_is_objective(tmp_path: Path) -> None:
    service=make_service(tmp_path)
    try: outcome=service.search('compare Guardian and Hard Hit')
    finally: service.close()
    assert outcome.kind == 'compare'
    assert 'MP' in (outcome.message or '')


def test_subjective_skill_query_refuses(tmp_path: Path) -> None:
    service=make_service(tmp_path)
    try: outcome=service.search('best dps skill')
    finally: service.close()
    assert outcome.kind == 'refuse'


def test_count_ailment_query_is_structured(tmp_path: Path) -> None:
    service=make_service(tmp_path)
    try: outcome=service.search('how many skills inflict stun')
    finally: service.close()
    assert outcome.kind == 'structured'
    assert outcome.message == '1 skills match those database filters.'


def test_tier_filter_with_tree(tmp_path: Path) -> None:
    service=make_service(tmp_path)
    try: outcome=service.search('tier 1 shield skills')
    finally: service.close()
    assert [row.skill.name for row in outcome.results] == ['Hard Hit']


def test_skill_type_filter_with_tree(tmp_path: Path) -> None:
    service=make_service(tmp_path)
    try: outcome=service.search('active shield skills')
    finally: service.close()
    assert [row.skill.name for row in outcome.results] == ['Hard Hit','Shield Bash']


def test_mp_max_filter(tmp_path: Path) -> None:
    service=make_service(tmp_path)
    try: outcome=service.search('skills mp <= 200')
    finally: service.close()
    assert [row.skill.name for row in outcome.results] == ['Hard Hit','Shield Bash']


def test_required_level_max_filter(tmp_path: Path) -> None:
    service=make_service(tmp_path)
    try: outcome=service.search('skills required level <= 20')
    finally: service.close()
    assert [row.skill.name for row in outcome.results] == ['Hard Hit','Shield Bash']


def test_skill_search_can_disable_weak_fallback(tmp_path: Path) -> None:
    service=make_service(tmp_path)
    try:
        weak=service.search('protect party aura')
        strict=service.search('protect party aura',allow_weak_fallback=False)
    finally:
        service.close()
    assert weak.results
    assert strict.kind == 'not_found'
    assert not strict.results


def test_strict_skill_search_keeps_exact_and_structured_routes(tmp_path: Path) -> None:
    service=make_service(tmp_path)
    try:
        exact=service.search('Guardian',allow_weak_fallback=False)
        ailment=service.search('skills that inflict stun',allow_weak_fallback=False)
    finally:
        service.close()
    assert [row.skill.name for row in exact.results] == ['Guardian']
    assert [row.skill.name for row in ailment.results] == ['Shield Bash']


def test_skill_tree_query_exposes_tree_chip(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('shield skill tree')
    finally:
        service.close()
    interpretation = outcome.interpretation
    assert interpretation is not None
    assert [(c.kind, c.label) for c in interpretation.chips] == [('skill_tree', 'Shield Skills')]
    assert interpretation.query_without(interpretation.chips[0].id) == ''


def test_ailment_query_exposes_ailment_chip(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('skills that inflict stun')
    finally:
        service.close()
    assert outcome.interpretation is not None
    assert [(c.kind, c.label) for c in outcome.interpretation.chips] == [('ailment', 'Stun')]


def test_mp_and_required_level_filters_are_atomic(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        mp = service.search('skills mp <= 200')
        level = service.search('skills required level <= 20')
    finally:
        service.close()
    assert mp.interpretation is not None
    assert [(c.kind, c.label) for c in mp.interpretation.chips] == [('mp', 'MP ≤ 200')]
    assert level.interpretation is not None
    assert [(c.kind, c.label) for c in level.interpretation.chips] == [('required_level', 'Required Level ≤ 20')]


def test_lowest_mp_tree_ranking_uses_atomic_rank_field_chip(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('lowest mp shield skills')
    finally:
        service.close()
    interpretation = outcome.interpretation
    assert interpretation is not None
    assert [(c.kind, c.label) for c in interpretation.chips] == [
        ('rank', 'Lowest MP'), ('skill_tree', 'Shield Skills'),
    ]
    assert interpretation.query_without(interpretation.chips[0].id) == 'shield skills'
    assert interpretation.query_without(interpretation.chips[1].id) == 'lowest mp'


def test_exact_skill_has_quality_but_no_chips(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('Guardian')
    finally:
        service.close()
    assert outcome.route_quality.family == 'exact'
    assert outcome.interpretation is None


def test_unsupported_structured_skill_components_do_not_emit_partial_chips(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        tier = service.search('tier 1 shield skills')
        skill_type = service.search('active shield skills')
    finally:
        service.close()
    assert tier.route_quality.family == 'structured'
    assert tier.interpretation is None
    assert skill_type.route_quality.family == 'structured'
    assert skill_type.interpretation is None


def test_weak_skill_fallback_has_no_interpretation(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('protects party members')
    finally:
        service.close()
    assert outcome.route_quality.family == 'weak'
    assert outcome.interpretation is None

from pathlib import Path

from tests.item_db_factory import create_item_database
from tests.skill_db_factory import create_skill_database
from toram_search.autocomplete import build_autocomplete_index, suggestions_for_mode
from toram_search.router import search_database


def databases(tmp_path:Path)->tuple[Path,Path]:
    items=tmp_path/'items.sqlite';skills=tmp_path/'skills.sqlite';create_item_database(items);create_skill_database(skills);return items,skills


def test_universal_returns_both_domains(tmp_path:Path)->None:
    items,skills=databases(tmp_path);outcome=search_database('Universal','Guardian',items_path=items,skills_path=skills);assert outcome.items is not None;assert outcome.skills is not None;assert outcome.skills.results[0].skill.name=='Guardian'


def test_items_mode_does_not_need_skill_database(tmp_path:Path)->None:
    items=tmp_path/'items.sqlite';create_item_database(items);outcome=search_database('Items','Test Bow',items_path=items,skills_path=tmp_path/'missing-skills.sqlite');assert outcome.items is not None;assert outcome.items.results[0].item.name=='Test Bow';assert outcome.skills is None


def test_skills_mode_does_not_need_item_database(tmp_path:Path)->None:
    skills=tmp_path/'skills.sqlite';create_skill_database(skills);outcome=search_database('Skills','Guardian',items_path=tmp_path/'missing-items.sqlite',skills_path=skills);assert outcome.items is None;assert outcome.skills is not None


def test_skills_mode_keeps_weak_fts_fallback(tmp_path:Path)->None:
    skills=tmp_path/'skills.sqlite';create_skill_database(skills)
    outcome=search_database('Skills','protects party members',items_path=tmp_path/'missing-items.sqlite',skills_path=skills)
    assert outcome.items is None
    assert outcome.skills is not None
    assert [row.skill.name for row in outcome.skills.results]==['Guardian']


def test_universal_no_item_intent_keeps_weak_skill_fallback(tmp_path:Path)->None:
    items,skills=databases(tmp_path)
    outcome=search_database('Universal','protects party members',items_path=items,skills_path=skills)
    assert outcome.items is not None
    assert outcome.items.routing_confidence=='none'
    assert outcome.skills is not None
    assert [row.skill.name for row in outcome.skills.results]==['Guardian']


def test_universal_aggro_xtal_wp_returns_weapon_crysta_without_unrelated_skills(tmp_path:Path)->None:
    items,skills=databases(tmp_path)
    outcome=search_database('Universal','aggro xtal wp',items_path=items,skills_path=skills)
    assert outcome.items is not None
    assert outcome.items.routing_confidence=='strong'
    assert [row.item.name for row in outcome.items.results]==['Aggro Weapon Crystal']
    assert outcome.skills is not None
    assert not outcome.skills.results


def test_universal_aggro_wp_xtal_matches_same_weapon_crysta(tmp_path:Path)->None:
    items,skills=databases(tmp_path)
    first=search_database('Universal','aggro xtal wp',items_path=items,skills_path=skills)
    second=search_database('Universal','aggro wp xtal',items_path=items,skills_path=skills)
    assert first.items is not None and second.items is not None
    assert [row.item.id for row in first.items.results]==[row.item.id for row in second.items.results]
    assert first.skills is not None and second.skills is not None
    assert not first.skills.results
    assert not second.skills.results


def test_universal_strong_item_intent_suppresses_weak_skill_fallback(tmp_path:Path)->None:
    items,skills=databases(tmp_path)
    outcome=search_database('Universal','critical rate bow',items_path=items,skills_path=skills)
    assert outcome.items is not None and outcome.items.routing_confidence=='strong'
    assert outcome.items.results
    assert outcome.skills is not None
    assert not outcome.skills.results


def test_universal_exact_skill_match_survives_strict_skill_policy(tmp_path:Path)->None:
    items,skills=databases(tmp_path)
    outcome=search_database('Universal','Guardian',items_path=items,skills_path=skills)
    assert outcome.skills is not None
    assert [row.skill.name for row in outcome.skills.results]==['Guardian']


def test_universal_autocomplete_contains_labeled_domain_values(tmp_path:Path)->None:
    items,skills=databases(tmp_path);rows=build_autocomplete_index('Universal',items_path=items,skills_path=skills);pairs={(r.value,r.kind) for r in rows};assert ('Test Bow','Item') in pairs;assert ('Guardian','Skill') in pairs;assert ('Shield Skills','Skill Tree') in pairs;assert ('Critical Rate','Stat') in pairs;assert ('Stun','Ailment') in pairs


def test_items_autocomplete_does_not_need_skill_database(tmp_path:Path)->None:
    items=tmp_path/'items.sqlite';create_item_database(items);rows=build_autocomplete_index('Items',items_path=items,skills_path=tmp_path/'missing-skills.sqlite');assert rows;assert all(r.kind in {'Item','Stat','Item Type'} for r in rows)


def test_skills_autocomplete_does_not_need_item_database(tmp_path:Path)->None:
    skills=tmp_path/'skills.sqlite';create_skill_database(skills);rows=build_autocomplete_index('Skills',items_path=tmp_path/'missing-items.sqlite');assert rows;assert all(r.kind in {'Skill','Skill Tree','Ailment'} for r in rows)


def test_suggestions_for_mode_filters_prebuilt_universal_index(tmp_path:Path)->None:
    items,skills=databases(tmp_path);universal=build_autocomplete_index('Universal',items_path=items,skills_path=skills);assert all(r.kind in {'Item','Stat','Item Type'} for r in suggestions_for_mode(universal,'Items'));assert all(r.kind in {'Skill','Skill Tree','Ailment'} for r in suggestions_for_mode(universal,'Skills'))

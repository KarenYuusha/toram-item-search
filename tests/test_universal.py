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
def test_universal_autocomplete_contains_labeled_domain_values(tmp_path:Path)->None:
    items,skills=databases(tmp_path);rows=build_autocomplete_index('Universal',items_path=items,skills_path=skills);pairs={(r.value,r.kind) for r in rows};assert ('Test Bow','Item') in pairs;assert ('Guardian','Skill') in pairs;assert ('Shield Skills','Skill Tree') in pairs;assert ('Critical Rate','Stat') in pairs;assert ('Stun','Ailment') in pairs
def test_items_autocomplete_does_not_need_skill_database(tmp_path:Path)->None:
    items=tmp_path/'items.sqlite';create_item_database(items);rows=build_autocomplete_index('Items',items_path=items,skills_path=tmp_path/'missing-skills.sqlite');assert rows;assert all(r.kind in {'Item','Stat','Item Type'} for r in rows)
def test_skills_autocomplete_does_not_need_item_database(tmp_path:Path)->None:
    skills=tmp_path/'skills.sqlite';create_skill_database(skills);rows=build_autocomplete_index('Skills',items_path=tmp_path/'missing-items.sqlite',skills_path=skills);assert rows;assert all(r.kind in {'Skill','Skill Tree','Ailment'} for r in rows)
def test_suggestions_for_mode_filters_prebuilt_universal_index(tmp_path:Path)->None:
    items,skills=databases(tmp_path);universal=build_autocomplete_index('Universal',items_path=items,skills_path=skills);assert all(r.kind in {'Item','Stat','Item Type'} for r in suggestions_for_mode(universal,'Items'));assert all(r.kind in {'Skill','Skill Tree','Ailment'} for r in suggestions_for_mode(universal,'Skills'))

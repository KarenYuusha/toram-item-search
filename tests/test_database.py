import json
import sqlite3
from pathlib import Path

import pytest

from toram_search.database import (
    connect_readonly,
    validate_food_sources,
    validate_item_database,
    validate_registlet_source,
    validate_skill_database,
)


def make_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, value TEXT)")
    connection.execute("INSERT INTO sample(value) VALUES ('ok')")
    connection.commit()
    connection.close()


def test_connect_readonly_can_read_but_cannot_write(tmp_path: Path) -> None:
    path = tmp_path / "sample.sqlite"
    make_db(path)
    connection = connect_readonly(path)
    try:
        assert connection.execute("SELECT value FROM sample").fetchone()[0] == "ok"
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("INSERT INTO sample(value) VALUES ('blocked')")
    finally:
        connection.close()


def test_connect_readonly_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        connect_readonly(tmp_path / "missing.sqlite")


def test_item_validation_reports_missing_required_table(tmp_path: Path) -> None:
    path = tmp_path / "items.sqlite"
    sqlite3.connect(path).close()
    health = validate_item_database(path)
    assert health.ok is False
    assert health.name == "Items"
    assert "items" in (health.error or "")


def test_skill_validation_does_not_require_embedding_table(tmp_path: Path) -> None:
    path = tmp_path / "skills.sqlite"
    connection = sqlite3.connect(path)
    required = {
        "skill_trees": "id TEXT, name TEXT, normalized_name TEXT, tree_group TEXT, general_text TEXT, tier_requirements_json TEXT, weapon_restrictions_json TEXT",
        "skills": "id TEXT, tree_id TEXT, source_order INTEGER, name TEXT, normalized_name TEXT, tier INTEGER, required_level INTEGER, skill_type TEXT, mp_cost_text TEXT, mp_cost_value INTEGER, damage_type TEXT, element TEXT, cast_range_text TEXT, hit_range_text TEXT, cast_time_text TEXT, hit_count_text TEXT, description TEXT, game_description TEXT, raw_text TEXT",
        "skill_aliases": "skill_id TEXT, position INTEGER, alias TEXT, normalized_alias TEXT",
        "skill_sections": "skill_id TEXT, position INTEGER, label TEXT, normalized_label TEXT, body TEXT",
        "skill_ailments": "skill_id TEXT, position INTEGER, name TEXT, normalized_name TEXT",
        "skill_weapon_requirements": "skill_id TEXT, position INTEGER, weapon TEXT, normalized_name TEXT",
        "skill_weapon_restrictions": "skill_id TEXT, position INTEGER, weapon TEXT, normalized_name TEXT",
        "skill_tree_weapon_restrictions": "tree_id TEXT, position INTEGER, weapon TEXT, normalized_weapon TEXT",
        "skill_search_documents": "id TEXT, skill_id TEXT, position INTEGER, kind TEXT, label TEXT, text TEXT, text_hash TEXT",
    }
    for table, columns in required.items():
        connection.execute(f"CREATE TABLE {table}({columns})")
    connection.execute("CREATE VIRTUAL TABLE skill_fts USING fts5(document_id, skill_id, name, tree_name, text)")
    connection.commit()
    connection.close()
    health = validate_skill_database(path)
    assert health.ok is True


def test_food_health_rejects_malformed_aliases(tmp_path: Path) -> None:
    aliases = tmp_path / 'aliases.json'
    entries = tmp_path / 'food.csv'
    aliases.write_text('{broken', encoding='utf-8')
    entries.write_text('code,stat,level\n111,maxmp,10\n', encoding='utf-8')

    health = validate_food_sources(entries, aliases)

    assert health.name == 'Food'
    assert health.ok is False
    assert health.error


def test_food_health_allows_skipped_row_warnings(tmp_path: Path) -> None:
    aliases = tmp_path / 'aliases.json'
    entries = tmp_path / 'food.csv'
    aliases.write_text(json.dumps({
        'stats': [{'key': 'maxmp', 'display': 'MaxMP', 'aliases': ['max mp']}]
    }), encoding='utf-8')
    entries.write_text('code,stat,level\n111,unknown,10\n', encoding='utf-8')

    health = validate_food_sources(entries, aliases)

    assert health.name == 'Food'
    assert health.ok is True


def test_registlet_health_rejects_malformed_top_level_source(tmp_path: Path) -> None:
    path = tmp_path / 'registlets.json'
    path.write_text('{broken', encoding='utf-8')

    health = validate_registlet_source(path)

    assert health.name == 'Registlets'
    assert health.ok is False
    assert health.error


def test_registlet_health_allows_skipped_record_warnings(tmp_path: Path) -> None:
    path = tmp_path / 'registlets.json'
    path.write_text(json.dumps({
        'metadata': {'valid_stoodie_levels': [220]},
        'registlets': [{
            'name': '',
            'max_lv': 1,
            'effect': 'bad record',
            'affects_skill': None,
            'obtained_from': {'source': 'Stoodie', 'location': 'El Scaro', 'levels': [220]},
        }],
    }), encoding='utf-8')

    health = validate_registlet_source(path)

    assert health.name == 'Registlets'
    assert health.ok is True

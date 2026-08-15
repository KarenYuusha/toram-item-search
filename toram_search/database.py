from __future__ import annotations

from pathlib import Path
import sqlite3
from urllib.parse import quote

from toram_search.food.data import FoodDataError, load_food_dataset
from toram_search.registlets.data import RegistletDataError, load_registlet_dataset
from .models import DatabaseHealth

ROOT = Path(__file__).resolve().parents[1]
ITEM_DATABASE = ROOT / "items.sqlite"
SKILL_DATABASE = ROOT / "skills.sqlite"
FOOD_ENTRIES = ROOT / "food_entries.csv"
FOOD_ALIASES = ROOT / "food_stat_aliases.json"
REGISTLET_DATA = ROOT / "registlets.json"

ITEM_REQUIRED_COLUMNS: dict[str, set[str]] = {
    "items": {"id", "name", "item_type", "sell_price", "process_material", "process_amount", "badge", "note", "page_url"},
    "item_stats": {"id", "item_id", "position", "stat_name", "amount", "conditions_json", "condition_text", "coryn_applies_to", "needs_condition_review"},
    "item_sources": {"id", "item_id", "position", "source_id", "source_name", "level", "map", "dye", "source_url", "lookup_error"},
    "item_images": {"id", "item_id", "position", "category", "gender", "variant", "local_path", "source_url"},
}

SKILL_REQUIRED_COLUMNS: dict[str, set[str]] = {
    "skill_trees": {"id", "name", "normalized_name", "tree_group", "general_text", "tier_requirements_json", "weapon_restrictions_json"},
    "skills": {"id", "tree_id", "source_order", "name", "normalized_name", "tier", "required_level", "skill_type", "mp_cost_text", "mp_cost_value", "damage_type", "element", "cast_range_text", "hit_range_text", "cast_time_text", "hit_count_text", "description", "game_description", "raw_text"},
    "skill_aliases": {"skill_id", "position", "alias", "normalized_alias"},
    "skill_sections": {"skill_id", "position", "label", "normalized_label", "body"},
    "skill_ailments": {"skill_id", "position", "name", "normalized_name"},
    "skill_weapon_requirements": {"skill_id", "position", "weapon", "normalized_name"},
    "skill_weapon_restrictions": {"skill_id", "position", "weapon", "normalized_name"},
    "skill_tree_weapon_restrictions": {"tree_id", "position", "weapon", "normalized_weapon"},
    "skill_search_documents": {"id", "skill_id", "position", "kind", "label", "text", "text_hash"},
    "skill_fts": {"document_id", "skill_id", "name", "tree_name", "text"},
}


def connect_readonly(path: Path) -> sqlite3.Connection:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"SQLite database not found: {resolved}")
    uri = f"file:{quote(resolved.as_posix(), safe='/:')}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5.0)
    connection.row_factory = sqlite3.Row
    return connection


def _validate_schema(name: str, path: Path, required_columns: dict[str, set[str]]) -> DatabaseHealth:
    try:
        connection = connect_readonly(path)
        try:
            errors: list[str] = []
            for table, required in required_columns.items():
                actual = {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})")}
                missing = sorted(required - actual)
                if missing:
                    errors.append(f"{table}: missing {', '.join(missing)}")
            if errors:
                return DatabaseHealth(name, Path(path), False, "; ".join(errors))
            return DatabaseHealth(name, Path(path), True)
        finally:
            connection.close()
    except (FileNotFoundError, OSError, sqlite3.DatabaseError) as exc:
        return DatabaseHealth(name, Path(path), False, str(exc))


def validate_item_database(path: Path) -> DatabaseHealth:
    return _validate_schema("Items", path, ITEM_REQUIRED_COLUMNS)


def validate_skill_database(path: Path) -> DatabaseHealth:
    return _validate_schema("Skills", path, SKILL_REQUIRED_COLUMNS)


def validate_food_sources(
    entries_path: Path = FOOD_ENTRIES,
    aliases_path: Path = FOOD_ALIASES,
) -> DatabaseHealth:
    try:
        load_food_dataset(entries_path, aliases_path)
        return DatabaseHealth('Food', Path(entries_path), True)
    except (FoodDataError, OSError) as exc:
        return DatabaseHealth('Food', Path(entries_path), False, str(exc))


def validate_registlet_source(path: Path = REGISTLET_DATA) -> DatabaseHealth:
    try:
        load_registlet_dataset(path)
        return DatabaseHealth('Registlets', Path(path), True)
    except (RegistletDataError, OSError) as exc:
        return DatabaseHealth('Registlets', Path(path), False, str(exc))


def validate_databases(
    items_path: Path = ITEM_DATABASE,
    skills_path: Path = SKILL_DATABASE,
) -> tuple[DatabaseHealth, DatabaseHealth]:
    return validate_item_database(items_path), validate_skill_database(skills_path)


def validate_sources(
    items_path: Path = ITEM_DATABASE,
    skills_path: Path = SKILL_DATABASE,
    food_entries_path: Path = FOOD_ENTRIES,
    food_aliases_path: Path = FOOD_ALIASES,
    registlets_path: Path = REGISTLET_DATA,
) -> tuple[DatabaseHealth, DatabaseHealth, DatabaseHealth, DatabaseHealth]:
    return (
        validate_item_database(items_path),
        validate_skill_database(skills_path),
        validate_food_sources(food_entries_path, food_aliases_path),
        validate_registlet_source(registlets_path),
    )

# Streamlit Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the deployable Streamlit shell and a strict read-only contract for the two SQLite databases copied from `filter_search`.

**Architecture:** Root `main.py` is a thin Streamlit entry point. Shared runtime code lives under `toram_search/`. Both SQLite files are opened through one read-only connection helper using SQLite URI `mode=ro`. This phase deliberately stops before item/skill query implementation; it leaves a running site that validates the packaged databases, exposes the database-mode selector, and reports configuration failures clearly.

**Tech Stack:** Python 3.12, Streamlit 1.61.x, SQLite via Python `sqlite3`, pytest 8.x, Streamlit `st.testing.v1.AppTest`.

## Global Constraints

- Target repository is only `KarenYuusha/toram-item-search`.
- `KarenYuusha/filter_search` is reference/source only; do not commit Streamlit-specific changes there.
- Public entry point must be root-level `main.py`.
- Runtime database files are root-level `items.sqlite` and `skills.sqlite`.
- Canonical source files are copied from `filter_search/coryn_data/database/items.sqlite` and `filter_search/coryn_data/database/skills.sqlite`.
- The Streamlit app must never edit, migrate, or rebuild those SQLite files.
- Open SQLite connections with read-only URI mode; tests must prove write attempts fail.
- No LLM, RAG, embeddings, Ollama, Qwen, Gemma, Discord, or vector-search runtime dependencies.
- Universal / Items / Skills is a sidebar database selector; Universal is the default.
- Keep `main.py` orchestration-only; reusable logic belongs in modules.
- This phase must finish with a working Streamlit shell even before search logic exists.

---

## File Structure for This Phase

```text
toram-item-search/
├── main.py
├── items.sqlite
├── skills.sqlite
├── requirements.txt
├── requirements-dev.txt
├── .streamlit/
│   └── config.toml
├── toram_search/
│   ├── __init__.py
│   ├── database.py
│   └── models.py
├── ui/
│   ├── __init__.py
│   └── sidebar.py
└── tests/
    ├── test_database.py
    └── test_app_shell.py
```

## Locked Foundation Models

```python
# toram_search/models.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DatabaseMode = Literal["Universal", "Items", "Skills"]


@dataclass(frozen=True)
class DatabaseHealth:
    name: str
    path: Path
    ok: bool
    error: str | None = None
```

Item validation requires only public-search columns:

```python
ITEM_REQUIRED_COLUMNS = {
    "items": {
        "id", "name", "item_type", "sell_price", "process_material",
        "process_amount", "badge", "note", "page_url",
    },
    "item_stats": {
        "id", "item_id", "position", "stat_name", "amount",
        "conditions_json", "condition_text", "coryn_applies_to",
        "needs_condition_review",
    },
    "item_sources": {
        "id", "item_id", "position", "source_id", "source_name",
        "level", "map", "dye", "source_url", "lookup_error",
    },
    "item_images": {
        "id", "item_id", "position", "category", "gender", "variant",
        "local_path", "source_url",
    },
}
```

Skill validation requires deterministic public-search tables, including FTS but not embeddings:

```python
SKILL_REQUIRED_COLUMNS = {
    "skill_trees": {
        "id", "name", "normalized_name", "tree_group", "general_text",
        "tier_requirements_json", "weapon_restrictions_json",
    },
    "skills": {
        "id", "tree_id", "source_order", "name", "normalized_name", "tier",
        "required_level", "skill_type", "mp_cost_text", "mp_cost_value",
        "damage_type", "element", "cast_range_text", "hit_range_text",
        "cast_time_text", "hit_count_text", "description", "game_description",
        "raw_text",
    },
    "skill_aliases": {"skill_id", "position", "alias", "normalized_alias"},
    "skill_sections": {"skill_id", "position", "label", "normalized_label", "body"},
    "skill_ailments": {"skill_id", "position", "name", "normalized_name"},
    "skill_weapon_requirements": {"skill_id", "position", "weapon", "normalized_name"},
    "skill_weapon_restrictions": {"skill_id", "position", "weapon", "normalized_name"},
    "skill_tree_weapon_restrictions": {"tree_id", "position", "weapon", "normalized_weapon"},
    "skill_search_documents": {"id", "skill_id", "position", "kind", "label", "text", "text_hash"},
    "skill_fts": {"document_id", "skill_id", "name", "tree_name", "text"},
}
```

---

### Task 1: Add Minimal Runtime and Test Configuration

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.streamlit/config.toml`
- Create: `toram_search/__init__.py`
- Create: `ui/__init__.py`

**Interfaces:**
- Consumes: none.
- Produces: an importable Python/Streamlit project for later phases.

- [ ] **Step 1: Write runtime requirements**

Create `requirements.txt`:

```text
streamlit>=1.61,<1.62
rapidfuzz>=3,<4
```

The Streamlit range is intentionally limited to the verified 1.61.x API baseline used by this plan. `rapidfuzz` is included now because the item phase requires it.

- [ ] **Step 2: Write development requirements**

Create `requirements-dev.txt`:

```text
-r requirements.txt
pytest>=8,<9
```

- [ ] **Step 3: Add restrained Streamlit configuration**

Create `.streamlit/config.toml`:

```toml
[server]
headless = true

[browser]
gatherUsageStats = false
```

Do not force a color theme in the foundation phase; final UI styling can remain compatible with Streamlit/user appearance defaults.

- [ ] **Step 4: Add package markers**

Create `toram_search/__init__.py`:

```python
"""Deterministic Toram database search runtime."""
```

Create `ui/__init__.py`:

```python
"""Streamlit presentation helpers."""
```

- [ ] **Step 5: Install/verify imports**

```bash
python -m pip install -r requirements-dev.txt
python -c "import streamlit, rapidfuzz; print(streamlit.__version__)"
```

Expected: command exits 0 and Streamlit reports a 1.61.x version.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt requirements-dev.txt .streamlit/config.toml toram_search/__init__.py ui/__init__.py
git commit -m "chore: add Streamlit project foundation"
```

---

### Task 2: Implement and Prove Read-Only SQLite Connections

**Files:**
- Create: `toram_search/models.py`
- Create: `toram_search/database.py`
- Create: `tests/test_database.py`

**Interfaces:**
- Consumes: Python `sqlite3`, `Path`.
- Produces: `DatabaseMode`, `DatabaseHealth`, `connect_readonly`.

- [ ] **Step 1: Write failing read-only tests**

Create `tests/test_database.py`:

```python
import sqlite3
from pathlib import Path

import pytest

from toram_search.database import connect_readonly


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
```

- [ ] **Step 2: Run and verify failure**

```bash
pytest tests/test_database.py -v
```

Expected: import failure because `toram_search.database` is not implemented yet.

- [ ] **Step 3: Add shared models**

Create `toram_search/models.py` using the locked `DatabaseMode` and `DatabaseHealth` definitions above.

- [ ] **Step 4: Implement `connect_readonly`**

Create `toram_search/database.py`:

```python
from __future__ import annotations

from pathlib import Path
import sqlite3
from urllib.parse import quote

from .models import DatabaseHealth

ROOT = Path(__file__).resolve().parents[1]
ITEM_DATABASE = ROOT / "items.sqlite"
SKILL_DATABASE = ROOT / "skills.sqlite"


def connect_readonly(path: Path) -> sqlite3.Connection:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"SQLite database not found: {resolved}")
    uri = f"file:{quote(resolved.as_posix(), safe='/:')}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5.0)
    connection.row_factory = sqlite3.Row
    return connection
```

Do not add a writable connection helper.

- [ ] **Step 5: Run focused tests**

```bash
pytest tests/test_database.py::test_connect_readonly_can_read_but_cannot_write tests/test_database.py::test_connect_readonly_rejects_missing_file -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add toram_search/models.py toram_search/database.py tests/test_database.py
git commit -m "feat: enforce read-only SQLite access"
```

---

### Task 3: Add Schema Validation

**Files:**
- Modify: `toram_search/database.py`
- Modify: `tests/test_database.py`

**Interfaces:**
- Consumes: `connect_readonly`.
- Produces: `validate_item_database`, `validate_skill_database`, `validate_databases`.

Target signatures:

```python
def validate_item_database(path: Path) -> DatabaseHealth:
    ...


def validate_skill_database(path: Path) -> DatabaseHealth:
    ...


def validate_databases(
    items_path: Path = ITEM_DATABASE,
    skills_path: Path = SKILL_DATABASE,
) -> tuple[DatabaseHealth, DatabaseHealth]:
    ...
```

- [ ] **Step 1: Write failing validation tests**

Append:

```python
from toram_search.database import validate_item_database, validate_skill_database


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
    connection.execute(
        "CREATE VIRTUAL TABLE skill_fts USING fts5(document_id, skill_id, name, tree_name, text)"
    )
    connection.commit()
    connection.close()

    health = validate_skill_database(path)
    assert health.ok is True
```

This fixture intentionally omits `skill_embedding_vectors`.

- [ ] **Step 2: Run and verify failure**

```bash
pytest tests/test_database.py -v
```

Expected: validation functions missing.

- [ ] **Step 3: Implement common schema validation**

Add the locked required-column dictionaries and:

```python
def _validate_schema(
    name: str,
    path: Path,
    required_columns: dict[str, set[str]],
) -> DatabaseHealth:
    try:
        connection = connect_readonly(path)
        try:
            errors: list[str] = []
            for table, required in required_columns.items():
                actual = {
                    str(row["name"])
                    for row in connection.execute(f"PRAGMA table_info({table})")
                }
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
```

Then:

```python
def validate_item_database(path: Path) -> DatabaseHealth:
    return _validate_schema("Items", path, ITEM_REQUIRED_COLUMNS)


def validate_skill_database(path: Path) -> DatabaseHealth:
    return _validate_schema("Skills", path, SKILL_REQUIRED_COLUMNS)


def validate_databases(
    items_path: Path = ITEM_DATABASE,
    skills_path: Path = SKILL_DATABASE,
) -> tuple[DatabaseHealth, DatabaseHealth]:
    return validate_item_database(items_path), validate_skill_database(skills_path)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_database.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add toram_search/database.py tests/test_database.py
git commit -m "feat: validate Toram SQLite schemas"
```

---

### Task 4: Copy and Verify the Canonical SQLite Files

**Files:**
- Copy binary: `items.sqlite`
- Copy binary: `skills.sqlite`

**Interfaces:**
- Consumes: canonical DB files from the sibling `filter_search` checkout.
- Produces: root-level packaged databases used by Streamlit.

- [ ] **Step 1: Copy the exact source databases**

```bash
cp ../filter_search/coryn_data/database/items.sqlite ./items.sqlite
cp ../filter_search/coryn_data/database/skills.sqlite ./skills.sqlite
```

Do not run an editor, migration, vacuum-with-write, or rebuild command against the copies.

- [ ] **Step 2: Validate both real files**

```bash
python - <<'PY'
from toram_search.database import validate_databases
for health in validate_databases():
    print(health)
    assert health.ok, health.error
PY
```

Expected: both `DatabaseHealth` rows have `ok=True`.

- [ ] **Step 3: Prove runtime write rejection against the real item copy**

```bash
python - <<'PY'
import sqlite3
from toram_search.database import ITEM_DATABASE, connect_readonly
connection = connect_readonly(ITEM_DATABASE)
try:
    connection.execute("CREATE TABLE forbidden_write(id INTEGER)")
except sqlite3.OperationalError as exc:
    assert "readonly" in str(exc).casefold()
else:
    raise AssertionError("read-only contract was bypassed")
finally:
    connection.close()
PY
```

Expected: exit 0.

- [ ] **Step 4: Commit database copies**

```bash
git add items.sqlite skills.sqlite
git commit -m "data: add Toram SQLite databases"
```

---

### Task 5: Build the Running Streamlit Shell and Sidebar Selector

**Files:**
- Create: `ui/sidebar.py`
- Create: `main.py`
- Create: `tests/test_app_shell.py`

**Interfaces:**
- Consumes: `DatabaseMode`, database health functions.
- Produces: `render_database_sidebar() -> DatabaseMode` and a root Streamlit shell.

- [ ] **Step 1: Write failing AppTest coverage**

Create `tests/test_app_shell.py`:

```python
from streamlit.testing.v1 import AppTest


def test_app_starts_and_defaults_to_universal() -> None:
    app = AppTest.from_file("main.py").run(timeout=10)
    assert list(app.exception) == []
    assert any(title.value == "Toram Database" for title in app.title)
    assert app.radio[0].value == "Universal"


def test_sidebar_exposes_all_database_modes() -> None:
    app = AppTest.from_file("main.py").run(timeout=10)
    assert tuple(app.radio[0].options) == ("Universal", "Items", "Skills")
```

- [ ] **Step 2: Run and verify failure**

```bash
pytest tests/test_app_shell.py -v
```

Expected: failure because `main.py` does not exist.

- [ ] **Step 3: Implement the sidebar helper**

Create `ui/sidebar.py`:

```python
from __future__ import annotations

import streamlit as st

from toram_search.models import DatabaseMode


def render_database_sidebar() -> DatabaseMode:
    with st.sidebar:
        st.header("Toram Database")
        mode = st.radio(
            "Database",
            options=["Universal", "Items", "Skills"],
            index=0,
        )
        st.divider()
        st.caption("About, Credits, and GitHub links are added in the integration phase.")
    return mode
```

- [ ] **Step 4: Implement root `main.py` shell**

```python
from __future__ import annotations

import streamlit as st

from toram_search.database import validate_databases
from ui.sidebar import render_database_sidebar

st.set_page_config(page_title="Toram Database", layout="wide")

mode = render_database_sidebar()
item_health, skill_health = validate_databases()

st.title("Toram Database")
st.caption("Search items, stats, skills, and skill trees")

unhealthy = [health for health in (item_health, skill_health) if not health.ok]
if unhealthy:
    for health in unhealthy:
        st.error(f"{health.name} database unavailable: {health.error}")
    st.stop()

st.caption(f"Database mode: {mode}")
st.info("Search interface will be enabled in the next implementation phases.")
```

The final integration phase will make health checks mode-aware. At this foundation point both packaged DBs are expected to exist, so all-or-nothing startup is acceptable temporarily.

- [ ] **Step 5: Run AppTest**

```bash
pytest tests/test_app_shell.py -v
```

Expected: all pass.

- [ ] **Step 6: Run all foundation tests**

```bash
pytest -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add main.py ui/sidebar.py tests/test_app_shell.py
git commit -m "feat: add Streamlit database shell"
```

---

### Task 6: Document Deployment and Database Replacement

**Files:**
- Create: `README.md`
- Modify: `tests/test_app_shell.py`

**Interfaces:**
- Consumes: completed foundation.
- Produces: reproducible local/deployment/update instructions.

- [ ] **Step 1: Write README**

Create `README.md` with the following actual sections (the shell commands below are fenced individually in the README; do not nest code fences):

```text
# Toram Database Search

Deterministic Streamlit search for Toram Online items and skills.

## Run locally
```

Then add this shell block:

```bash
python -m pip install -r requirements-dev.txt
streamlit run main.py
```

Continue README text:

```text
## Database update workflow

The canonical databases are maintained in `KarenYuusha/filter_search`.
Replace the Streamlit copies with:
```

Then add:

```bash
cp ../filter_search/coryn_data/database/items.sqlite ./items.sqlite
cp ../filter_search/coryn_data/database/skills.sqlite ./skills.sqlite
```

Continue:

```text
Then run:
```

Then add:

```bash
pytest -q
git add items.sqlite skills.sqlite
git commit -m "data: update Toram databases"
git push
```

Finish README with:

```text
The Streamlit app reads these files only; it never edits or rebuilds them.

## Deployment

Streamlit Community Cloud entry point: `main.py`.
Public deployment: `https://toram-item-search.streamlit.app/`.
```

Do not describe `filter_search` as the deployed repository.

- [ ] **Step 2: Keep a startup regression test**

Ensure:

```python
def test_app_has_no_startup_exception() -> None:
    app = AppTest.from_file("main.py").run(timeout=10)
    assert list(app.exception) == []
```

- [ ] **Step 3: Run all tests**

```bash
pytest -q
```

Expected: all pass.

- [ ] **Step 4: Check forbidden runtime dependencies**

```bash
python - <<'PY'
from pathlib import Path
text = Path("requirements.txt").read_text().casefold()
for forbidden in ("discord", "ollama", "qwen", "gemma", "sentence-transformers"):
    assert forbidden not in text, forbidden
PY
```

Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_app_shell.py
git commit -m "docs: document Streamlit deployment workflow"
```

---

## Phase Verification Checklist

Before starting item search:

```bash
pytest -q
python - <<'PY'
from toram_search.database import validate_databases
health = validate_databases()
assert all(row.ok for row in health), health
print(health)
PY
```

Then launch manually:

```bash
streamlit run main.py --server.headless true
```

Verify:

- page title is `Toram Database`;
- sidebar defaults to Universal and offers Items and Skills;
- both packaged DBs validate;
- no search is attempted yet;
- no LLM/Discord service starts;
- changing sidebar mode cannot mutate either SQLite file.

## Reference Sources in `filter_search`

Use these only as source/schema reference material:

```text
coryn_data/database/items.sqlite
coryn_data/database/skills.sqlite
toram_data/repository.py
toram_skills/schema.py
```

The target validation intentionally excludes editor-only item tables and `skill_embedding_vectors`, because neither is required by the deterministic public website.
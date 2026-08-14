# Deterministic Skill Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic skill lookup/filter/rank/count/compare/search behavior and Skills-mode Streamlit cards/details using `skills.sqlite`, with no semantic embeddings or generated explanation path.

**Architecture:** Build a small read-only skill domain under `toram_search/skills/`. Reuse the canonical SQLite schema and deterministic routing ideas from `filter_search`, but replace importer-oriented `SkillDraft` models with public read models and replace RAG explanation with direct stored detail. Structured queries use SQL filters/analytics; broad text discovery uses the existing SQLite FTS5 index only.

**Tech Stack:** Python 3.12, SQLite/FTS5, Streamlit 1.61.x, pytest 8.x.

## Global Constraints

- Target repository is only `KarenYuusha/toram-item-search`.
- `KarenYuusha/filter_search` is reference/source only.
- Read only root `skills.sqlite` through `toram_search.database.connect_readonly`.
- Do not copy the writable/importer methods from `filter_search/toram_skills/repository.py`.
- Do not import or query `skill_embedding_vectors`.
- Do not copy `semantic_search.py`, `hybrid_search.py`, embedding runtime, RAG retrieval, `toram_skill_chat/llm.py`, or generated answer code.
- SQLite `skill_fts` is allowed because it is deterministic lexical FTS, not embeddings.
- `how does Hard Hit work?` must resolve the skill and display its stored descriptions/sections/mechanics; no generated prose.
- Subjective queries such as `best DPS skill` / `best tank skill` must refuse.
- Skill cards are compact and full skill detail opens in a Streamlit dialog.
- Skill icons are optional in version 1; missing icon assets must never block search or detail rendering.
- Root `main.py` remains orchestration-only.

---

## File Structure for This Phase

```text
toram_search/
└── skills/
    ├── __init__.py
    ├── models.py
    ├── normalization.py
    ├── repository.py
    ├── structured_search.py
    ├── lexical_search.py
    ├── concepts.py
    ├── router.py
    ├── analytics.py
    └── service.py
ui/
├── skill_cards.py
└── skill_dialog.py
tests/
├── skill_db_factory.py
├── test_skill_repository.py
├── test_skill_router.py
├── test_skill_service.py
├── test_skill_ui.py
└── test_skill_app.py
```

## Source Mapping From `filter_search`

Use these as reference/adaptation sources:

```text
filter_search/toram_skills/models.py               -> public field reference only
filter_search/toram_skills/parsing.py              -> only normalize_skill_name behavior
filter_search/toram_skills/repository.py           -> read query reference only
filter_search/toram_skills/search_models.py        -> structured filter field reference
filter_search/toram_skills/structured_search.py    -> deterministic SQL filtering
filter_search/toram_skills/lexical_search.py       -> deterministic FTS5 search
filter_search/toram_skill_chat/concepts.py         -> ailment aliases
filter_search/toram_skill_chat/router.py            -> deterministic query patterns
filter_search/toram_skill_chat/analytics.py         -> filter/rank/count/compare logic
filter_search/toram_skill_chat/service.py           -> deterministic lookup/compare formatting ideas only
```

Never copy these runtime paths:

```text
filter_search/toram_skills/semantic_search.py
filter_search/toram_skills/hybrid_search.py
filter_search/toram_skill_chat/llm.py
filter_search/toram_skill_chat/rag.py
filter_search/toram_skill_chat/retrieval.py
filter_search/toram_skill_search/* semantic runtime
```

## Locked Public Skill Interfaces

```python
# toram_search/skills/models.py
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class SkillSection:
    position: int
    label: str
    normalized_label: str
    body: str

@dataclass(frozen=True)
class SkillTree:
    id: str
    name: str
    normalized_name: str
    tree_group: str
    general_text: str
    tier_requirements: tuple[tuple[int, int | None], ...] = ()
    weapon_restrictions: tuple[str, ...] = ()

@dataclass(frozen=True)
class SkillRecord:
    id: str
    tree_id: str
    source_order: int
    name: str
    normalized_name: str
    aliases: tuple[str, ...] = ()
    tier: int | None = None
    required_level: int | None = None
    skill_type: str | None = None
    mp_cost_text: str | None = None
    mp_cost_value: int | None = None
    damage_type: str | None = None
    element: str | None = None
    cast_range_text: str | None = None
    hit_range_text: str | None = None
    cast_time_text: str | None = None
    hit_count_text: str | None = None
    ailments: tuple[str, ...] = ()
    weapon_requirements: tuple[str, ...] = ()
    weapon_restrictions: tuple[str, ...] = ()
    sections: tuple[SkillSection, ...] = ()
    description: str | None = None
    game_description: str | None = None
    raw_text: str = ""

@dataclass(frozen=True)
class SkillFilter:
    tree_ids: tuple[str, ...] = ()
    tiers: tuple[int, ...] = ()
    skill_types: tuple[str, ...] = ()
    ailments: tuple[str, ...] = ()
    weapons: tuple[str, ...] = ()
    required_level_max: int | None = None
    mp_cost_max: int | None = None

@dataclass(frozen=True)
class SkillCardResult:
    skill: SkillRecord
    tree_name: str
    matched_field: str | None = None
    matched_value: str | None = None

SkillOutcomeKind = Literal[
    "results", "structured", "compare", "suggest", "refuse", "not_found"
]

@dataclass(frozen=True)
class SkillSearchOutcome:
    kind: SkillOutcomeKind
    query: str
    results: tuple[SkillCardResult, ...] = ()
    message: str | None = None
    suggested_queries: tuple[str, ...] = ()
```

```python
# toram_search/skills/service.py
class SkillSearchService:
    def __init__(self, database_path: Path): ...
    def close(self) -> None: ...
    def search(self, query: str) -> SkillSearchOutcome: ...
    def get_skill(self, skill_id: str) -> SkillCardResult: ...
    def list_autocomplete_values(self) -> tuple[tuple[str, str], ...]: ...
```

---

### Task 1: Create Public Skill Models and Read-Only Repository

**Files:**
- Create: `toram_search/skills/__init__.py`
- Create: `toram_search/skills/models.py`
- Create: `toram_search/skills/normalization.py`
- Create: `toram_search/skills/repository.py`
- Create: `tests/skill_db_factory.py`
- Create: `tests/test_skill_repository.py`

**Interfaces:**
- Consumes: `connect_readonly`.
- Produces: read-only `SkillRepository`, `SkillTree`, `SkillRecord`.

Required repository methods:

```python
class SkillRepository:
    def __init__(self, database_path: Path) -> None: ...
    def close(self) -> None: ...
    def __enter__(self) -> "SkillRepository": ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def count_trees(self) -> int: ...
    def count_skills(self) -> int: ...
    def list_tree_names(self) -> list[str]: ...
    def list_known_ailments(self) -> tuple[str, ...]: ...
    def list_skill_types(self) -> tuple[str, ...]: ...
    def list_skill_names(self) -> tuple[str, ...]: ...
    def get_tree(self, tree_id: str) -> SkillTree: ...
    def resolve_tree_name(self, name: str) -> tuple[SkillTree, ...]: ...
    def list_skills_in_tree(self, tree_id: str) -> tuple[SkillRecord, ...]: ...
    def resolve_skill_name(self, name: str, *, tree_id: str | None = None) -> tuple[SkillRecord, ...]: ...
    def get_skill(self, skill_id: str) -> SkillRecord: ...
```

- [ ] **Step 1: Build a deterministic skill test database factory**

Create `tests/skill_db_factory.py` with `create_skill_database(path: Path) -> None` using the same public tables expected by foundation validation. Create `skill_fts` as FTS5.

Seed one tree:

```text
id: shield_skills
name: Shield Skills
tree_group: Weapon Skills
```

Seed skills:

```text
shield_skills/guardian
  name: Guardian
  tier: 4
  required_level: 110
  skill_type: Support
  mp_cost_text: 600
  mp_cost_value: 600
  description: Creates an area that protects party members.

shield_skills/hard-hit
  name: Hard Hit
  aliases: Hardhit
  tier: 1
  required_level: 1
  skill_type: Active
  mp_cost_text: 100
  mp_cost_value: 100
  description: A physical attack with a chance to flinch.
  section: Skill Effect -> Stored Hard Hit mechanics.

shield_skills/shield-bash
  name: Shield Bash
  tier: 2
  required_level: 20
  skill_type: Active
  mp_cost_text: 200
  mp_cost_value: 200
  ailment: Stun
  description: Strikes with a shield and can inflict Stun.
```

For each skill, insert a summary/search document and corresponding `skill_fts` row containing its name, tree, fields, description, ailment, and section text.

- [ ] **Step 2: Write failing repository tests**

Create `tests/test_skill_repository.py`:

```python
from pathlib import Path
import sqlite3

import pytest

from tests.skill_db_factory import create_skill_database
from toram_search.skills.repository import SkillRepository


def test_repository_resolves_skill_and_alias(tmp_path: Path) -> None:
    path = tmp_path / "skills.sqlite"
    create_skill_database(path)
    with SkillRepository(path) as repository:
        exact = repository.resolve_skill_name("Hard Hit")
        alias = repository.resolve_skill_name("Hardhit")
    assert exact[0].id == "shield_skills/hard-hit"
    assert alias[0].id == "shield_skills/hard-hit"


def test_repository_loads_sections_and_ailments(tmp_path: Path) -> None:
    path = tmp_path / "skills.sqlite"
    create_skill_database(path)
    with SkillRepository(path) as repository:
        hard_hit = repository.get_skill("shield_skills/hard-hit")
        shield_bash = repository.get_skill("shield_skills/shield-bash")
    assert hard_hit.sections[0].body == "Stored Hard Hit mechanics."
    assert shield_bash.ailments == ("Stun",)


def test_skill_repository_is_read_only(tmp_path: Path) -> None:
    path = tmp_path / "skills.sqlite"
    create_skill_database(path)
    with SkillRepository(path) as repository:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            repository.connection.execute("DELETE FROM skills")
```

- [ ] **Step 3: Run tests and verify failure**

```bash
pytest tests/test_skill_repository.py -v
```

Expected: import failure.

- [ ] **Step 4: Implement normalization only, not the importer**

Create `normalization.py`:

```python
def normalize_skill_name(text: str) -> str:
    return " ".join(text.casefold().replace("’", "'").split())
```

Do not copy the rest of `toram_skills/parsing.py`.

- [ ] **Step 5: Implement public models**

Create `models.py` with the locked interfaces. Do not include parse/import issues because the public app does not edit/build the corpus.

- [ ] **Step 6: Implement a read-only repository from the source query logic**

Use `filter_search/toram_skills/repository.py` as SQL reference, but write a smaller target repository that begins with:

```python
from toram_search.database import connect_readonly
from .models import SkillRecord, SkillSection, SkillTree
from .normalization import normalize_skill_name

class SkillRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.connection = connect_readonly(self.database_path)
```

`get_tree()` must JSON-decode `tier_requirements_json` and `weapon_restrictions_json`.

`get_skill()` must select only public fields, then query aliases, sections, ailments, weapon requirements, and weapon restrictions. It must not read `issues_json` or embedding tables.

- [ ] **Step 7: Run repository tests**

```bash
pytest tests/test_skill_repository.py -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add toram_search/skills tests/skill_db_factory.py tests/test_skill_repository.py
git commit -m "feat: add read-only skill repository"
```

---

### Task 2: Add Structured Skill Filtering and Analytics

**Files:**
- Create: `toram_search/skills/structured_search.py`
- Create: `toram_search/skills/analytics.py`
- Create: `tests/test_skill_service.py` initially for analytics

**Interfaces:**
- Consumes: `SkillRepository`, `SkillFilter`.
- Produces: structured IDs and deterministic filter/count/rank/compare operations.

```python
def structured_skill_ids(repository: SkillRepository, filters: SkillFilter) -> tuple[str, ...]: ...

class SkillAnalytics:
    def filter_skills(self, filters: SkillFilter = SkillFilter()) -> tuple[SkillRecord, ...]: ...
    def count(self, filters: SkillFilter = SkillFilter()) -> int: ...
    def rank(self, field: str, direction: Literal["asc", "desc"], *, filters: SkillFilter = SkillFilter(), limit: int = 5) -> tuple[SkillRecord, ...]: ...
    def compare_field(self, skill_ids: tuple[str, ...], field: str) -> tuple[tuple[SkillRecord, int | None], ...]: ...
```

Comparable fields are exactly:

```python
COMPARABLE_FIELDS = frozenset({"mp_cost_value", "required_level", "tier"})
```

- [ ] **Step 1: Write failing structured analytics tests**

Create/append `tests/test_skill_service.py`:

```python
from pathlib import Path

from tests.skill_db_factory import create_skill_database
from toram_search.skills.analytics import SkillAnalytics
from toram_search.skills.models import SkillFilter
from toram_search.skills.repository import SkillRepository


def test_filter_by_tree_and_ailment(tmp_path: Path) -> None:
    path = tmp_path / "skills.sqlite"
    create_skill_database(path)
    with SkillRepository(path) as repository:
        analytics = SkillAnalytics(repository)
        rows = analytics.filter_skills(
            SkillFilter(tree_ids=("shield_skills",), ailments=("Stun",))
        )
    assert [row.name for row in rows] == ["Shield Bash"]


def test_rank_lowest_mp(tmp_path: Path) -> None:
    path = tmp_path / "skills.sqlite"
    create_skill_database(path)
    with SkillRepository(path) as repository:
        rows = SkillAnalytics(repository).rank("mp_cost_value", "asc", limit=3)
    assert [row.name for row in rows] == ["Hard Hit", "Shield Bash", "Guardian"]
```

- [ ] **Step 2: Run and verify failure**

```bash
pytest tests/test_skill_service.py -v
```

Expected: imports fail.

- [ ] **Step 3: Adapt deterministic structured SQL**

Use `filter_search/toram_skills/structured_search.py` as the source. Replace imports with `.normalization`, `.repository`, `.models` and use `SkillFilter` directly.

Keep filtering support for:

```text
tree_ids
tiers
required_level_max
skill_types
mp_cost_max
ailments
weapons
```

Do not add embedding-related criteria.

- [ ] **Step 4: Adapt analytics**

Use `filter_search/toram_skill_chat/analytics.py` as source. Preserve its conservative ailment fallback against `skill_search_documents` so positive phrases like `inflict stun` can supplement older structured records while still respecting other filters.

Rewrite all imports to target-local modules.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_skill_service.py -v
```

Expected: structured analytics tests pass.

- [ ] **Step 6: Commit**

```bash
git add toram_search/skills/structured_search.py toram_search/skills/analytics.py tests/test_skill_service.py
git commit -m "feat: add structured skill analytics"
```

---

### Task 3: Add Deterministic Skill Router

**Files:**
- Create: `toram_search/skills/concepts.py`
- Create: `toram_search/skills/router.py`
- Create: `tests/test_skill_router.py`

**Interfaces:**
- Consumes: skill/tree/ailment names from repository.
- Produces: state-free `SkillQueryPlan`.

Add to `models.py`:

```python
SkillQueryIntent = Literal[
    "lookup", "detail", "filter", "rank", "count", "compare_field", "compare",
    "lexical", "refuse", "unknown"
]

@dataclass(frozen=True)
class SkillQueryPlan:
    intent: SkillQueryIntent
    skill_ids: tuple[str, ...] = ()
    filters: SkillFilter = SkillFilter()
    field: str | None = None
    direction: Literal["asc", "desc"] | None = None
    limit: int = 20
    refusal_reason: str | None = None
```

The router is intentionally state-free: website searches are independent submissions, not Discord conversation turns.

- [ ] **Step 1: Write routing tests**

Create `tests/test_skill_router.py`:

```python
from pathlib import Path

from tests.skill_db_factory import create_skill_database
from toram_search.skills.repository import SkillRepository
from toram_search.skills.router import SkillQueryRouter


def route(tmp_path: Path, query: str):
    path = tmp_path / "skills.sqlite"
    create_skill_database(path)
    with SkillRepository(path) as repository:
        return SkillQueryRouter(repository).route(query)


def test_guardian_mp_cost_is_lookup(tmp_path: Path) -> None:
    plan = route(tmp_path, "guardian mp cost")
    assert plan.intent == "lookup"
    assert plan.field == "mp_cost"
    assert plan.skill_ids == ("shield_skills/guardian",)


def test_shield_skills_is_tree_filter(tmp_path: Path) -> None:
    plan = route(tmp_path, "shield skills")
    assert plan.intent == "filter"
    assert plan.filters.tree_ids == ("shield_skills",)


def test_stun_query_is_ailment_filter(tmp_path: Path) -> None:
    plan = route(tmp_path, "skills that inflict stun")
    assert plan.intent == "filter"
    assert plan.filters.ailments == ("Stun",)


def test_how_does_exact_skill_work_routes_to_detail_not_rag(tmp_path: Path) -> None:
    plan = route(tmp_path, "how does Hard Hit work?")
    assert plan.intent == "detail"
    assert plan.skill_ids == ("shield_skills/hard-hit",)


def test_subjective_skill_query_refuses(tmp_path: Path) -> None:
    plan = route(tmp_path, "best dps skill")
    assert plan.intent == "refuse"
```

- [ ] **Step 2: Run and verify failure**

```bash
pytest tests/test_skill_router.py -v
```

Expected: import failure.

- [ ] **Step 3: Adapt concepts**

Copy `filter_search/toram_skill_chat/concepts.py` to the target package and rewrite normalization import to `.normalization`. Preserve validated aliases such as `ignition -> ignite`.

- [ ] **Step 4: Implement state-free router from the deterministic source router**

Use the source router's `_match_normalize`, skill phrase loading, tree phrase loading, ailment resolution, and refusal rules.

Remove all context/follow-up behavior (`active_skill_ids`, `selected_skill_id`, `what about`, `which one`, `it/this` references).

Implement these routing rules in order:

```text
1. empty -> unknown
2. subjective best-DPS/tank/build patterns -> refuse
3. detect exact/alias skill phrases and tree phrases
4. exact `how does <skill> work` / `what does <skill> do` -> detail
5. `<skill> mp cost` -> lookup(field="mp_cost")
6. `<skill> what tree` / `what tree is <skill>` -> lookup(field="tree")
7. `<skill> tier` -> lookup(field="tier")
8. `<tree>` / `<tree> skill tree` / `<tree> skills` -> filter(tree_ids=...)
9. highest/lowest/least MP, tier, or required level -> rank
10. ailment phrase with inflict/cause -> filter or count
11. two recognized skills + compare -> compare
12. two recognized skills + MP/required-level comparison -> compare_field
13. one exact recognized skill alone -> detail
14. otherwise -> lexical
```

No route named `explain`, `general_mechanic`, or `rag` exists in the target router.

- [ ] **Step 5: Run router tests**

```bash
pytest tests/test_skill_router.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add toram_search/skills/concepts.py toram_search/skills/router.py toram_search/skills/models.py tests/test_skill_router.py
git commit -m "feat: add deterministic skill query router"
```

---

### Task 4: Add Lexical FTS and Deterministic Skill Service

**Files:**
- Create: `toram_search/skills/lexical_search.py`
- Create: `toram_search/skills/service.py`
- Modify: `tests/test_skill_service.py`

**Interfaces:**
- Consumes: router, analytics, repository, `skill_fts`.
- Produces: `SkillSearchService` / `SkillSearchOutcome`.

- [ ] **Step 1: Add service behavior tests**

Append:

```python
from toram_search.skills.service import SkillSearchService


def test_exact_skill_returns_detail_card(tmp_path: Path) -> None:
    path = tmp_path / "skills.sqlite"
    create_skill_database(path)
    service = SkillSearchService(path)
    try:
        outcome = service.search("Guardian")
    finally:
        service.close()
    assert outcome.kind == "results"
    assert [row.skill.name for row in outcome.results] == ["Guardian"]


def test_mp_lookup_is_structured(tmp_path: Path) -> None:
    path = tmp_path / "skills.sqlite"
    create_skill_database(path)
    service = SkillSearchService(path)
    try:
        outcome = service.search("guardian mp cost")
    finally:
        service.close()
    assert outcome.kind == "structured"
    assert "600" in (outcome.message or "")
    assert outcome.results[0].matched_field == "MP Cost"


def test_how_does_skill_work_returns_stored_record(tmp_path: Path) -> None:
    path = tmp_path / "skills.sqlite"
    create_skill_database(path)
    service = SkillSearchService(path)
    try:
        outcome = service.search("how does Hard Hit work?")
    finally:
        service.close()
    assert outcome.kind == "results"
    assert outcome.results[0].skill.sections[0].body == "Stored Hard Hit mechanics."


def test_unknown_broad_text_uses_lexical_fts(tmp_path: Path) -> None:
    path = tmp_path / "skills.sqlite"
    create_skill_database(path)
    service = SkillSearchService(path)
    try:
        outcome = service.search("protects party members")
    finally:
        service.close()
    assert outcome.kind == "results"
    assert outcome.results[0].skill.name == "Guardian"


def test_service_never_answers_subjective_best_skill(tmp_path: Path) -> None:
    path = tmp_path / "skills.sqlite"
    create_skill_database(path)
    service = SkillSearchService(path)
    try:
        outcome = service.search("best dps skill")
    finally:
        service.close()
    assert outcome.kind == "refuse"
```

- [ ] **Step 2: Run and verify failure**

```bash
pytest tests/test_skill_service.py -v
```

Expected: missing service/lexical module failures.

- [ ] **Step 3: Adapt lexical FTS only**

Use `filter_search/toram_skills/lexical_search.py` as source. Replace channel/semantic result models with a simple target type:

```python
@dataclass(frozen=True)
class LexicalSkillHit:
    skill_id: str
    score: float
    document_id: str
```

Expose:

```python
def lexical_search(
    repository: SkillRepository,
    query: str,
    *,
    eligible_skill_ids: tuple[str, ...] | None = None,
    limit: int = 20,
) -> tuple[LexicalSkillHit, ...]: ...
```

Keep the source behavior: FTS token AND search, then OR fallback, `bm25(skill_fts)` ordering. Do not introduce any semantic channel or embedding vector.

- [ ] **Step 4: Implement deterministic service**

`SkillSearchService.__init__` creates one `SkillRepository`, `SkillQueryRouter`, and `SkillAnalytics`.

Implement:

```python
def _card(self, skill: SkillRecord, *, matched_field: str | None = None, matched_value: str | None = None) -> SkillCardResult:
    tree = self.repository.get_tree(skill.tree_id)
    return SkillCardResult(skill, tree.name, matched_field, matched_value)
```

`search()` must execute the plan without any generated answer path:

```text
refuse -> refusal outcome
unknown -> not_found
lookup -> structured stored scalar + one card
detail -> one or more stored cards
filter -> cards from analytics.filter_skills
count -> structured count message
rank -> ranked cards with matched metric
compare_field -> compare outcome with stored scalar message + two cards
compare -> compare outcome with two cards; UI may render a comparison table
lexical -> deterministic FTS results converted to cards
```

For `detail`, return the full `SkillRecord` in the card so the modal can present stored `description`, `game_description`, `sections`, restrictions, and mechanics.

Implement autocomplete values:

```python
def list_autocomplete_values(self) -> tuple[tuple[str, str], ...]:
    values = [(name, "Skill") for name in self.repository.list_skill_names()]
    values += [(name, "Skill Tree") for name in self.repository.list_tree_names()]
    values += [(name, "Ailment") for name in self.repository.list_known_ailments()]
    return tuple(dict.fromkeys(values))
```

- [ ] **Step 5: Run service tests**

```bash
pytest tests/test_skill_service.py -v
```

Expected: all pass.

- [ ] **Step 6: Prove no semantic/LLM dependency exists**

```bash
python - <<'PY'
from pathlib import Path
text = "\n".join(path.read_text() for path in Path("toram_search/skills").glob("*.py")).casefold()
for forbidden in ("semantic_search", "embedding", "ollama", "gemma", "qwen", "rag", "sentence_transformers"):
    assert forbidden not in text, forbidden
PY
```

Expected: exit 0.

- [ ] **Step 7: Exercise real packaged skills DB**

```bash
python - <<'PY'
from toram_search.database import SKILL_DATABASE
from toram_search.skills.service import SkillSearchService
service = SkillSearchService(SKILL_DATABASE)
try:
    for query in ("Guardian", "guardian mp cost", "shield skills", "skills that inflict stun"):
        outcome = service.search(query)
        assert outcome.kind != "not_found", (query, outcome)
finally:
    service.close()
PY
```

Expected: exit 0.

- [ ] **Step 8: Commit**

```bash
git add toram_search/skills/lexical_search.py toram_search/skills/service.py tests/test_skill_service.py
git commit -m "feat: add deterministic skill search service"
```

---

### Task 5: Render Compact Skill Cards and Stored Detail Dialog

**Files:**
- Create: `ui/skill_cards.py`
- Create: `ui/skill_dialog.py`
- Create: `tests/test_skill_ui.py`

**Interfaces:**
- Consumes: `SkillCardResult`.
- Produces: compact card list and full stored-record modal.

```python
def render_skill_results(results: tuple[SkillCardResult, ...], *, visible_limit: int) -> str | None:
    """Render cards and return clicked skill id, or None."""

@st.dialog("Skill details", width="large")
def render_skill_dialog(result: SkillCardResult) -> None: ...
```

- [ ] **Step 1: Write pure formatting tests**

Create `tests/test_skill_ui.py` for:

```python
from ui.skill_cards import skill_meta_line


def test_skill_meta_line_uses_tree_and_tier() -> None:
    assert skill_meta_line("Shield Skills", 4) == "Shield Skills · Tier 4"
```

Also test a helper `format_skill_scalar(None) == "Not recorded"`.

- [ ] **Step 2: Run and verify failure**

```bash
pytest tests/test_skill_ui.py -v
```

Expected: missing UI modules.

- [ ] **Step 3: Implement compact skill cards**

Each card shows only scan-level data:

```text
Skill name
Tree · Tier
MP cost if recorded
Skill type if recorded
matched_field/matched_value when query-specific
View details
```

No full raw text in cards.

Use button key `skill-detail-{skill.id}`.

- [ ] **Step 4: Implement stored detail dialog**

Show, when recorded:

```text
name
tree / tier / required level
skill type
MP cost
damage type / element
cast range / hit range / cast time / hit count
ailments
weapon requirements / restrictions
description
game description
all stored sections with headings
raw text only inside an optional expander when it adds information
```

Do not synthesize or rewrite mechanics.

- [ ] **Step 5: Run UI tests**

```bash
pytest tests/test_skill_ui.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add ui/skill_cards.py ui/skill_dialog.py tests/test_skill_ui.py
git commit -m "feat: add compact skill result UI"
```

---

### Task 6: Wire Skills Mode Into `main.py`

**Files:**
- Modify: `main.py`
- Create: `tests/test_skill_app.py`
- Modify: `tests/test_app_shell.py`

**Interfaces:**
- Consumes: `SkillSearchService`, cards/dialog.
- Produces: usable Skills mode; Universal remains for final integration.

- [ ] **Step 1: Write failing Skills-mode AppTest**

Create a temporary `skills.sqlite` with `create_skill_database()`, set `TORAM_SKILL_DB`, launch `AppTest.from_file("main.py")`, select `Skills`, and assert a Search text input/button exists and no exception occurs.

- [ ] **Step 2: Verify failure**

```bash
pytest tests/test_skill_app.py -v
```

Expected: Skills-mode search is not wired yet.

- [ ] **Step 3: Add temporary native submit form for Skills mode**

Use the same submit-only pattern as Items:

```python
with st.form("skill-search-form", clear_on_submit=False, enter_to_submit=True):
    query = st.text_input("Search", placeholder="Search skills or skill trees...")
    submitted = st.form_submit_button("Search")
```

On submit call `SkillSearchService.search()` once and store the outcome in session state.

Use independent state keys:

```text
skill_outcome
skill_visible_limit
selected_skill_id
```

Reset limit to 20 on a new submitted query.

- [ ] **Step 4: Render all outcome kinds**

```text
results -> cards
structured -> message + cards when available
compare -> comparison text/table + cards
suggest -> message + suggestion buttons
refuse -> warning
not_found -> info
```

`Show more skills` increments by 20 without rerunning the query.

- [ ] **Step 5: Wire detail modal**

Fetch one record only when a card detail button is clicked and call `render_skill_dialog()`.

- [ ] **Step 6: Run focused app tests**

```bash
pytest tests/test_skill_app.py tests/test_item_app.py tests/test_app_shell.py -v
```

Expected: all pass.

- [ ] **Step 7: Run full test suite**

```bash
pytest -q
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add main.py tests/test_skill_app.py tests/test_app_shell.py
git commit -m "feat: enable Skills mode search"
```

---

## Phase Verification Checklist

Run:

```bash
pytest -q
```

Manually exercise:

```text
Guardian
guardian mp cost
shield skills
skills that inflict stun
lowest mp shield skills
compare <known skill A> and <known skill B>
how does Hard Hit work?
best dps skill
```

Verify:

- exact names/aliases resolve deterministically;
- tree filters return all applicable skills;
- MP/tier/required-level rank/compare uses stored scalar fields;
- ailment searches use structured rows plus conservative positive prose fallback;
- broad unknown text uses SQLite FTS only;
- `how does <exact skill> work` opens/returns stored mechanics rather than a synthesized answer;
- subjective best-build searches refuse;
- skill detail contains only stored database values/text;
- no embedding vector is read and no LLM process starts;
- the public app cannot write `skills.sqlite`.

Final forbidden-code check:

```bash
python - <<'PY'
from pathlib import Path
text = "\n".join(path.read_text(errors="ignore") for path in Path("toram_search/skills").rglob("*.py")).casefold()
for forbidden in ("skill_embedding_vectors", "semantic_search", "hybrid_search", "ollama", "qwen", "gemma", "groundedskillrag"):
    assert forbidden not in text, forbidden
PY
```

Expected: exit 0.
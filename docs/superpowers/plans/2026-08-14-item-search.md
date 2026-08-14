# Deterministic Item Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the complete deterministic item-search engine and Items-mode Streamlit result/detail UI while preserving the proven item query behavior from `filter_search` without any LLM fallback.

**Architecture:** Adapt the pure item-domain modules from `filter_search` into `toram_search/items/`, backed by the shared read-only SQLite connection from the foundation phase. A new deterministic `ItemSearchService` converts parser/repository outputs into stable card-friendly result models. Streamlit receives only frontend-neutral outcomes and renders compact cards plus a modal detail view.

**Tech Stack:** Python 3.12, SQLite, RapidFuzz 3.x, Streamlit 1.61.x, pytest 8.x.

## Global Constraints

- Target repository is only `KarenYuusha/toram-item-search`.
- `KarenYuusha/filter_search` is reference/source only; do not modify it.
- Read only root `items.sqlite` through `toram_search.database.connect_readonly`.
- Do not add a writable item repository or editor.
- Do not import `toram_search.fallback`, `fallback_adapter`, `llm`, Ollama, Qwen, Discord, or any generated-answer service from `filter_search`.
- Preserve deterministic stat aliases, item-type aliases, numeric/Boolean stat expressions, fuzzy item-name ranking, upgrade relationships, help/meta queries, and deterministic query correction where practical.
- Subjective requests such as `best tank xtal` / `best dps` must refuse rather than reinterpret `best` as a stat ranking.
- Root `main.py` remains the Streamlit entry point and orchestration layer.
- Full search executes only after submission; autocomplete is implemented in the final integration phase.
- Item details open through a Streamlit dialog/modal, not an inline full-record expander.
- Use item image `source_url` when present; `local_path` is optional metadata and must not require copying the image corpus.

---

## File Structure for This Phase

```text
toram_search/
├── database.py
├── models.py
└── items/
    ├── __init__.py
    ├── aliases.py
    ├── filters.py
    ├── models.py
    ├── query_entities.py
    ├── reconstruction.py
    ├── ranking.py
    ├── repository.py
    ├── parser.py
    ├── stat_query.py
    ├── understanding.py
    ├── help_db.py
    └── service.py
ui/
├── item_cards.py
└── item_dialog.py
tests/
├── item_db_factory.py
├── test_item_repository.py
├── test_item_parser.py
├── test_item_service.py
└── test_item_ui.py
```

## Source Mapping From `filter_search`

Adapt these deterministic files; do not import them across repositories at runtime:

```text
filter_search/toram_data/aliases.py             -> toram_search/items/aliases.py
filter_search/toram_data/item_filters.py        -> toram_search/items/filters.py
filter_search/toram_data/search_models.py       -> toram_search/items/models.py
filter_search/toram_data/stat_query.py          -> toram_search/items/stat_query.py
filter_search/toram_data/search_repository.py   -> toram_search/items/repository.py
filter_search/toram_search/ranking.py            -> toram_search/items/ranking.py
filter_search/toram_search/item_query_entities.py-> toram_search/items/query_entities.py
filter_search/toram_search/reconstruction.py     -> toram_search/items/reconstruction.py
filter_search/toram_search/understanding.py      -> toram_search/items/understanding.py
filter_search/toram_search/help_db.py            -> toram_search/items/help_db.py
filter_search/toram_search/parser.py             -> toram_search/items/parser.py
```

Do **not** copy `filter_search/search_items.py` or `filter_search/toram_search/service.py` wholesale because they pull in LLM fallback code.

## Locked Public Item Interfaces

```python
# toram_search/items/models.py
from dataclasses import dataclass
from typing import Any, Literal

@dataclass(frozen=True)
class ItemSummary:
    id: int
    name: str
    item_type: str

@dataclass(frozen=True)
class ItemDetail:
    summary: ItemSummary
    sell_price: float | None
    process_material: str | None
    process_amount: float | None
    badge: str | None
    note: str | None
    page_url: str | None
    stats: tuple[dict[str, Any], ...]
    sources: tuple[dict[str, Any], ...]
    images: tuple[dict[str, Any], ...]
    upgrade_predecessors: tuple[ItemSummary, ...]
    upgrade_successors: tuple[ItemSummary, ...]

@dataclass(frozen=True)
class ItemStatMatch:
    stat_name: str
    amount: float
    condition_text: str | None = None

@dataclass(frozen=True)
class ItemCardResult:
    item: ItemSummary
    matched_stats: tuple[ItemStatMatch, ...] = ()
    score: float | None = None
    match_kind: str | None = None

ItemOutcomeKind = Literal[
    "results", "help", "meta", "clarify", "suggest", "refuse", "not_found"
]

@dataclass(frozen=True)
class ItemSearchOutcome:
    kind: ItemOutcomeKind
    query: str
    results: tuple[ItemCardResult, ...] = ()
    message: str | None = None
    suggested_queries: tuple[str, ...] = ()
```

```python
# toram_search/items/service.py
class ItemSearchService:
    def __init__(self, database_path: Path): ...
    def close(self) -> None: ...
    def search(self, query: str) -> ItemSearchOutcome: ...
    def get_item(self, item_id: int) -> ItemDetail: ...
    def list_autocomplete_values(self) -> tuple[tuple[str, str], ...]: ...
```

`list_autocomplete_values()` returns `(value, kind)` pairs where item-domain kinds are `Item`, `Stat`, and `Item Type`; the final integration phase will wrap these into universal suggestion models.

---

### Task 1: Port the Pure Item Models, Aliases, Filters, and Stat Grammar

**Files:**
- Create: `toram_search/items/__init__.py`
- Create: `toram_search/items/models.py`
- Create: `toram_search/items/aliases.py`
- Create: `toram_search/items/filters.py`
- Create: `toram_search/items/stat_query.py`
- Create: `tests/test_item_parser.py`

**Interfaces:**
- Consumes: RapidFuzz and standard library.
- Produces: canonical item/stat normalization and stat-expression dataclasses used by repository/parser tasks.

- [ ] **Step 1: Write alias and expression tests before copying code**

Create the first tests in `tests/test_item_parser.py`:

```python
from toram_search.items.aliases import expand_stat_aliases, normalize_stat_text
from toram_search.items.stat_query import parse_stat_expression


def test_common_stat_aliases_expand_to_database_vocabulary() -> None:
    assert expand_stat_aliases("cr") == "critical rate"
    assert normalize_stat_text(expand_stat_aliases("cd")) == "critical damage"


def test_numeric_boolean_expression_preserves_item_filter() -> None:
    parsed = parse_stat_expression(
        "hp > 5000 and cr bow",
        {"Bow", "Armor", "Normal Crysta"},
        ["MaxHP", "Critical Rate"],
    )
    assert parsed.item_filter is not None
    assert parsed.item_filter.item_types == ("Bow",)
    assert len(parsed.groups) == 1
    assert len(parsed.groups[0].clauses) == 2
```

- [ ] **Step 2: Run the tests and verify import failure**

```bash
pytest tests/test_item_parser.py -v
```

Expected: import failure because `toram_search.items` does not exist.

- [ ] **Step 3: Copy the deterministic source files into the target package**

Copy from the sibling reference checkout:

```bash
mkdir -p toram_search/items
cp ../filter_search/toram_data/aliases.py toram_search/items/aliases.py
cp ../filter_search/toram_data/item_filters.py toram_search/items/filters.py
cp ../filter_search/toram_data/stat_query.py toram_search/items/stat_query.py
```

Create `toram_search/items/__init__.py`:

```python
"""Deterministic item search domain."""
```

- [ ] **Step 4: Rewrite imports to target-local modules**

In `filters.py`, replace imports from `toram_data.aliases` with:

```python
from .aliases import (
    ALL_CRYSTA_TYPES,
    ITEM_TYPE_ALIASES,
    ITEM_WORD_ALIASES,
    MAIN_WEAPON_TYPES,
    normalize_name,
    normalize_stat_text,
)
```

In `stat_query.py`, replace `toram_data.aliases` and `toram_data.item_filters` imports with `.aliases` and `.filters`.

- [ ] **Step 5: Create the card/detail model module**

Start from the source `search_models.py`, preserve `StatRow`, `RankedStatItem`, `ClauseMatch`, `RankedExpressionItem`, and `UpgradeGraph`, then use tuple fields for `ItemDetail` collections and add the locked `ItemStatMatch`, `ItemCardResult`, and `ItemSearchOutcome` types.

The target `ItemDetail` constructor must therefore receive `tuple(stats)`, `tuple(sources)`, `tuple(images)`, `tuple(upgrade_predecessors)`, and `tuple(upgrade_successors)`.

- [ ] **Step 6: Run parser tests**

```bash
pytest tests/test_item_parser.py -v
```

Expected: both tests pass.

- [ ] **Step 7: Commit**

```bash
git add toram_search/items tests/test_item_parser.py
git commit -m "feat: port deterministic item query grammar"
```

---

### Task 2: Build the Read-Only Item Repository

**Files:**
- Create: `toram_search/items/repository.py`
- Create: `tests/item_db_factory.py`
- Create: `tests/test_item_repository.py`

**Interfaces:**
- Consumes: `connect_readonly`, item models, resolved stat expressions.
- Produces: `ItemRepository` with read methods only.

Required methods:

```python
class ItemRepository:
    def __init__(self, database_path: Path) -> None: ...
    def close(self) -> None: ...
    def __enter__(self) -> "ItemRepository": ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def list_items(self) -> list[ItemSummary]: ...
    def list_item_types(self) -> set[str]: ...
    def list_stat_names(self) -> list[str]: ...
    def count_items_total(self) -> int: ...
    def count_items_by_types(self, item_types: tuple[str, ...]) -> int: ...
    def count_items_with_stat(self, stat_name: str) -> int: ...
    def exact_name_matches(self, query: str) -> list[ItemSummary]: ...
    def exact_upgrade_name_matches(self, query: str) -> list[ItemSummary]: ...
    def get_item(self, item_id: int) -> ItemDetail: ...
    def get_upgrade_component(self, item_id: int) -> UpgradeGraph: ...
    def search_by_stat(self, stat_name: str, item_types: tuple[str, ...] | None) -> list[RankedStatItem]: ...
    def search_by_expression(self, expression: ResolvedStatExpression, item_types: tuple[str, ...] | None, *, primary_sort_ascending: bool = False) -> list[RankedExpressionItem]: ...
```

- [ ] **Step 1: Create a deterministic item DB test factory**

Create `tests/item_db_factory.py` with `create_item_database(path: Path) -> None`. It must create `items`, `item_stats`, `item_sources`, and `item_images` using the public columns from the foundation schema and seed these rows:

```text
1 | Test Bow       | Bow
2 | Crit Ring      | Special
3 | Tank Armor     | Armor
4 | Old Crystal    | Normal Crysta
5 | New Crystal    | Normal Crysta
```

Seed stats:

```text
Test Bow    -> Critical Rate 25; MaxHP 500
Crit Ring   -> Critical Rate 40
Tank Armor  -> MaxHP 6000
New Crystal -> Upgrade for 4
```

Give `Test Bow` one source row and one image row with `source_url = https://example.com/test-bow.png`.

- [ ] **Step 2: Write failing repository tests**

Create `tests/test_item_repository.py`:

```python
from pathlib import Path
import sqlite3

import pytest

from tests.item_db_factory import create_item_database
from toram_search.items.repository import ItemRepository


def test_repository_loads_item_detail(tmp_path: Path) -> None:
    path = tmp_path / "items.sqlite"
    create_item_database(path)
    with ItemRepository(path) as repository:
        detail = repository.get_item(1)
    assert detail.summary.name == "Test Bow"
    assert detail.stats[0]["stat_name"] == "Critical Rate"
    assert detail.images[0]["source_url"] == "https://example.com/test-bow.png"


def test_repository_connection_is_read_only(tmp_path: Path) -> None:
    path = tmp_path / "items.sqlite"
    create_item_database(path)
    with ItemRepository(path) as repository:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            repository.db.execute("DELETE FROM items")


def test_upgrade_relationship_is_loaded(tmp_path: Path) -> None:
    path = tmp_path / "items.sqlite"
    create_item_database(path)
    with ItemRepository(path) as repository:
        detail = repository.get_item(5)
    assert [row.name for row in detail.upgrade_predecessors] == ["Old Crystal"]
```

- [ ] **Step 3: Verify failure**

```bash
pytest tests/test_item_repository.py -v
```

Expected: import failure because target repository module is absent.

- [ ] **Step 4: Adapt the source search repository**

Copy the source as a starting point:

```bash
cp ../filter_search/toram_data/search_repository.py toram_search/items/repository.py
```

Then make these exact architectural changes:

```python
from toram_search.database import connect_readonly
from .aliases import is_crysta_item_type, normalize_name, normalize_stat_text
from .models import (...)
from .stat_query import ResolvedStatExpression, compare_amount
```

Replace the constructor connection:

```python
self.database_path = Path(database_path).expanduser().resolve()
self.db = connect_readonly(self.database_path)
self._verify_schema()
```

Add context-manager methods:

```python
def __enter__(self) -> "ItemRepository":
    return self


def __exit__(self, exc_type, exc, tb) -> None:
    self.close()
```

Change `get_item()` to convert returned collections to tuples to match target models.

Do not copy any insert/update/delete method from the editor repository.

- [ ] **Step 5: Run repository tests**

```bash
pytest tests/test_item_repository.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Run the foundation read-only tests too**

```bash
pytest tests/test_database.py tests/test_item_repository.py -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add toram_search/items/repository.py tests/item_db_factory.py tests/test_item_repository.py
git commit -m "feat: add read-only item repository"
```

---

### Task 3: Port Deterministic Item Parsing, Ranking, and Correction

**Files:**
- Create: `toram_search/items/ranking.py`
- Create: `toram_search/items/query_entities.py`
- Create: `toram_search/items/reconstruction.py`
- Create: `toram_search/items/understanding.py`
- Create: `toram_search/items/parser.py`
- Modify: `tests/test_item_parser.py`

**Interfaces:**
- Consumes: `ItemRepository`, aliases/filter/stat grammar.
- Produces: `ParsedSearch`, `parse_search_query`, `rank_items`, `try_reconstruct_simple_search`, `try_suggest_query`, `understand_item_query`.

- [ ] **Step 1: Add parser/ranking regression tests**

Append:

```python
from tests.item_db_factory import create_item_database
from toram_search.items.parser import parse_search_query
from toram_search.items.ranking import rank_items
from toram_search.items.repository import ItemRepository
from toram_search.items.reconstruction import try_suggest_query


def test_exact_item_wins_before_fuzzy_search(tmp_path) -> None:
    path = tmp_path / "items.sqlite"
    create_item_database(path)
    with ItemRepository(path) as repository:
        parsed = parse_search_query("Test Bow", repository)
    assert parsed.intent == "exact_item"
    assert parsed.item_id == 1


def test_bare_stat_and_item_type_becomes_expression(tmp_path) -> None:
    path = tmp_path / "items.sqlite"
    create_item_database(path)
    with ItemRepository(path) as repository:
        parsed = parse_search_query("cr bow", repository)
    assert parsed.intent in {"stat_search", "stat_expression"}
    assert parsed.filter is not None
    assert parsed.filter.item_types == ("Bow",)


def test_name_ranking_prefers_prefix() -> None:
    from toram_search.items.models import ItemSummary
    ranked = rank_items(
        "test",
        [ItemSummary(1, "Test Bow", "Bow"), ItemSummary(2, "Contest Hat", "Additional")],
    )
    assert ranked[0].item.name == "Test Bow"


def test_simple_repair_can_suggest_canonical_stat_filter_order(tmp_path) -> None:
    path = tmp_path / "items.sqlite"
    create_item_database(path)
    with ItemRepository(path) as repository:
        suggestion = try_suggest_query(
            "highest bow cr",
            available_stats=repository.list_stat_names(),
            available_item_types=repository.list_item_types(),
        )
    assert suggestion is not None
    assert "bow" in suggestion.casefold()
```

- [ ] **Step 2: Verify failures**

```bash
pytest tests/test_item_parser.py -v
```

Expected: new imports fail.

- [ ] **Step 3: Copy pure deterministic helpers and rewrite imports**

```bash
cp ../filter_search/toram_search/ranking.py toram_search/items/ranking.py
cp ../filter_search/toram_search/item_query_entities.py toram_search/items/query_entities.py
cp ../filter_search/toram_search/reconstruction.py toram_search/items/reconstruction.py
cp ../filter_search/toram_search/understanding.py toram_search/items/understanding.py
```

Rewrite every `toram_data.*` / `toram_search.item_query_entities` import to target-local `.aliases`, `.filters`, `.models`, `.query_entities`.

- [ ] **Step 4: Copy the parser and remove LLM-structured-request code**

Start with:

```bash
cp ../filter_search/toram_search/parser.py toram_search/items/parser.py
```

Keep:

```text
StatResolution
ParsedSearch
resolve_stat_choices
resolve_stat_name
_parse_stat_request
_parse_negative_bare_expression
parse_expression_request
_resolve_item_type_for_database
_resolve_stat_for_database
_resolve_structured_item_filter only if used by deterministic code
build_search_stat_terms
find_non_overlapping_stat_terms
extract_natural_upgrade_target
parse_search_query
```

Delete all imports/types/functions that depend on `SearchIntentRequest` from `fallback.py`, including `parse_structured_search_request()` and `format_structured_search_request()` if their only caller would have been LLM output.

Rewrite imports to `.aliases`, `.filters`, `.repository`, `.stat_query`.

- [ ] **Step 5: Run parser tests**

```bash
pytest tests/test_item_parser.py -v
```

Expected: all pass.

- [ ] **Step 6: Prove forbidden imports are absent from the item package**

```bash
python - <<'PY'
from pathlib import Path
text = "\n".join(path.read_text() for path in Path("toram_search/items").glob("*.py"))
for forbidden in ("Ollama", "Qwen", "fallback_adapter", "toram_search.llm", "discord"):
    assert forbidden not in text, forbidden
PY
```

Expected: exit 0.

- [ ] **Step 7: Commit**

```bash
git add toram_search/items tests/test_item_parser.py
git commit -m "feat: add deterministic item parsing and ranking"
```

---

### Task 4: Add Deterministic Help, Metadata Queries, and Item Search Service

**Files:**
- Create: `toram_search/items/help_db.py`
- Create: `toram_search/items/service.py`
- Create: `tests/test_item_service.py`

**Interfaces:**
- Consumes: repository/parser/ranking/correction modules.
- Produces: `ItemSearchService` and `ItemSearchOutcome` for UI and Universal routing.

- [ ] **Step 1: Write failing service behavior tests**

Create `tests/test_item_service.py`:

```python
from pathlib import Path

from tests.item_db_factory import create_item_database
from toram_search.items.service import ItemSearchService


def service_for(tmp_path: Path) -> ItemSearchService:
    path = tmp_path / "items.sqlite"
    create_item_database(path)
    return ItemSearchService(path)


def test_exact_name_returns_one_result(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    try:
        outcome = service.search("Test Bow")
    finally:
        service.close()
    assert outcome.kind == "results"
    assert [row.item.name for row in outcome.results] == ["Test Bow"]


def test_stat_filter_returns_matched_stat_for_card(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    try:
        outcome = service.search("cr bow")
    finally:
        service.close()
    assert outcome.kind == "results"
    assert outcome.results[0].item.name == "Test Bow"
    assert outcome.results[0].matched_stats[0].stat_name == "Critical Rate"


def test_highest_stat_is_ranked_descending(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    try:
        outcome = service.search("highest cr")
    finally:
        service.close()
    assert outcome.kind == "results"
    assert outcome.results[0].item.name == "Crit Ring"


def test_subjective_build_query_refuses(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    try:
        outcome = service.search("best tank xtal")
    finally:
        service.close()
    assert outcome.kind == "refuse"
    assert "objective" in (outcome.message or "").casefold()


def test_help_is_static_and_deterministic(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    try:
        outcome = service.search("how to search")
    finally:
        service.close()
    assert outcome.kind == "help"
    assert "cr xtal" in (outcome.message or "").casefold()


def test_failed_stat_shape_returns_grounded_suggestion(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    try:
        outcome = service.search("highest bow cr")
    finally:
        service.close()
    assert outcome.kind in {"results", "suggest"}
    if outcome.kind == "suggest":
        assert outcome.suggested_queries
```

- [ ] **Step 2: Run and verify failure**

```bash
pytest tests/test_item_service.py -v
```

Expected: import failure for `service.py`.

- [ ] **Step 3: Port deterministic help/meta logic**

Copy:

```bash
cp ../filter_search/toram_search/help_db.py toram_search/items/help_db.py
```

This source is already deterministic. Keep `HelpService`, `DatabaseQuestionService`, and supported actions. Adjust only package imports/types if required.

- [ ] **Step 4: Implement `ItemSearchService` without any fallback client**

Create `toram_search/items/service.py`. Constructor:

```python
class ItemSearchService:
    def __init__(self, database_path: Path) -> None:
        self.repository = ItemRepository(database_path)
        self.all_items = self.repository.list_items()
        self.help_service = HelpService()
        self.database_service = DatabaseQuestionService(
            self.repository,
            resolve_item_type=lambda text: _resolve_item_type_for_database(text, self.repository),
            resolve_stat=lambda text: _resolve_stat_for_database(text, self.repository),
        )
```

Implement these private conversion helpers:

```python
def _card_from_ranked_name(row: RankedItem) -> ItemCardResult: ...
def _card_from_ranked_stat(row: RankedStatItem) -> ItemCardResult: ...
def _card_from_expression(row: RankedExpressionItem) -> ItemCardResult: ...
def _materialize(parsed: ParsedSearch) -> ItemSearchOutcome: ...
```

Conversions must preserve the matching stat in `matched_stats`, including `condition_text`.

Implement `search()` in this deterministic order:

```text
1. strip query; empty -> not_found with search guidance
2. static HelpService direct match -> help
3. direct DatabaseQuestionService match -> meta
4. reject objective-undefined build terms when query contains tank/dps/build/mage in a subjective shape
5. try parse_search_query
6. exact_item -> single result
7. exact_upgrade -> selected crysta result; relationship appears in get_item detail
8. upgrade_search -> fuzzy crysta name results
9. stat_search/stat_choices/stat_expression -> materialize deterministic repository search
10. highest/best stat prefix -> treat as objective ranking only when remainder resolves to a known stat expression; never for build/tank/dps terms
11. item_search -> rank_items
12. if parser shape is stat-like but unresolved, call try_suggest_query/understand_item_query and return suggest/clarify
13. otherwise return not_found
```

For ambiguous/fuzzy stat resolution, return `kind="clarify"` with a message and `suggested_queries` built only from the parser candidates; do not silently choose a fuzzy stat.

Implement:

```python
def get_item(self, item_id: int) -> ItemDetail:
    return self.repository.get_item(item_id)


def list_autocomplete_values(self) -> tuple[tuple[str, str], ...]:
    rows = [(item.name, "Item") for item in self.repository.list_items()]
    rows += [(stat, "Stat") for stat in self.repository.list_stat_names()]
    rows += [(item_type, "Item Type") for item_type in sorted(self.repository.list_item_types())]
    return tuple(rows)
```

- [ ] **Step 5: Run service tests**

```bash
pytest tests/test_item_service.py -v
```

Expected: all pass.

- [ ] **Step 6: Exercise the real packaged database**

```bash
python - <<'PY'
from toram_search.database import ITEM_DATABASE
from toram_search.items.service import ItemSearchService
service = ItemSearchService(ITEM_DATABASE)
try:
    assert service.search("cr bow").kind in {"results", "clarify"}
    assert service.search("how to search").kind == "help"
    assert service.list_autocomplete_values()
finally:
    service.close()
PY
```

Expected: exit 0.

- [ ] **Step 7: Commit**

```bash
git add toram_search/items/help_db.py toram_search/items/service.py tests/test_item_service.py
git commit -m "feat: add deterministic item search service"
```

---

### Task 5: Render Compact Item Cards and Modal Detail

**Files:**
- Create: `ui/item_cards.py`
- Create: `ui/item_dialog.py`
- Create: `tests/test_item_ui.py`

**Interfaces:**
- Consumes: `ItemCardResult`, `ItemDetail`.
- Produces: thin rendering helpers; all data correctness remains in domain tests.

```python
# ui/item_cards.py
def render_item_results(results: tuple[ItemCardResult, ...], *, visible_limit: int) -> int | None:
    """Render compact cards and return clicked item id, or None."""

# ui/item_dialog.py
@st.dialog("Item details", width="large")
def render_item_dialog(detail: ItemDetail) -> None: ...
```

- [ ] **Step 1: Add pure formatting helpers and tests**

In `ui/item_cards.py`, expose:

```python
def format_stat_amount(amount: float) -> str:
    return str(int(amount)) if float(amount).is_integer() else f"{amount:g}"


def item_image_url(detail: ItemDetail) -> str | None:
    for image in detail.images:
        value = image.get("source_url")
        if value:
            return str(value)
    return None
```

Create `tests/test_item_ui.py` testing `format_stat_amount(25.0) == "25"` and that `item_image_url()` prefers the first non-empty source URL. Use a constructed `ItemDetail`; do not launch Streamlit for pure formatting tests.

- [ ] **Step 2: Verify the helper tests fail**

```bash
pytest tests/test_item_ui.py -v
```

Expected: import failure before UI modules exist.

- [ ] **Step 3: Implement compact card rendering**

Use Streamlit containers/columns. Each card shows:

```text
name
item type
up to 3 matched stats, matched stats first
View details button
```

Use unique button keys:

```python
if st.button("View details", key=f"item-detail-{row.item.id}", use_container_width=True):
    return row.item.id
```

Do not load all detail records while rendering the result list.

- [ ] **Step 4: Implement modal detail rendering**

`render_item_dialog()` must show:

```text
item name + type
remote image if source_url exists
all stats and condition text
sell/process info when present
sources with source/map/level when present
upgrade predecessors/successors when present
page_url link when present
```

No generated summary text.

- [ ] **Step 5: Run UI helper tests**

```bash
pytest tests/test_item_ui.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add ui/item_cards.py ui/item_dialog.py tests/test_item_ui.py
git commit -m "feat: add compact item result UI"
```

---

### Task 6: Wire Items Mode Into `main.py`

**Files:**
- Modify: `main.py`
- Modify: `tests/test_app_shell.py`
- Create: `tests/test_item_app.py`

**Interfaces:**
- Consumes: `ItemSearchService`, item card/dialog renderers, sidebar mode.
- Produces: usable Items-mode search with explicit submit behavior; Universal/Skills remain placeholders until later phases.

- [ ] **Step 1: Write an AppTest for Items mode**

Create `tests/test_item_app.py` that uses AppTest to switch the sidebar radio to `Items`, enter `Test Bow` only if a test database override hook is available, and assert that the item search form exists. To keep the production app testable without replacing root DBs, add one environment-aware path resolver in `main.py`:

```python
def database_paths() -> tuple[Path, Path]:
    return (
        Path(os.environ.get("TORAM_ITEM_DB", ITEM_DATABASE)),
        Path(os.environ.get("TORAM_SKILL_DB", SKILL_DATABASE)),
    )
```

The test sets `TORAM_ITEM_DB` to a temporary fixture before `AppTest.from_file()`.

Test expectation:

```python
assert any(text_input.label == "Search" for text_input in app.text_input)
assert any(button.label == "Search" for button in app.button)
```

- [ ] **Step 2: Run and verify failure**

```bash
pytest tests/test_item_app.py -v
```

Expected: failure because Items-mode search UI is not wired.

- [ ] **Step 3: Add temporary native submit UI for this phase**

Until the custom autocomplete component is introduced in the final integration plan, use:

```python
with st.form("item-search-form", clear_on_submit=False, enter_to_submit=True):
    query = st.text_input("Search", placeholder="Search items or stats...")
    submitted = st.form_submit_button("Search")
```

Only call `ItemSearchService.search(query)` inside `if submitted:` and store the `ItemSearchOutcome` in `st.session_state`.

Do not search on every Streamlit rerun.

- [ ] **Step 4: Render result state and detail dialog**

Initialize:

```python
st.session_state.setdefault("item_outcome", None)
st.session_state.setdefault("item_visible_limit", 20)
st.session_state.setdefault("selected_item_id", None)
```

On a new submitted query reset `item_visible_limit` to 20.

Render outcome kinds:

```text
results  -> compact cards
help/meta -> st.info(message)
clarify/suggest -> message + suggestion buttons
refuse -> st.warning(message)
not_found -> st.info(message)
```

`Show more items` increments the visible limit by 20 without rerunning the search.

When a detail button is clicked, fetch only that record with `get_item()` and call `render_item_dialog()`.

- [ ] **Step 5: Run focused app tests**

```bash
pytest tests/test_item_app.py tests/test_app_shell.py -v
```

Expected: all pass.

- [ ] **Step 6: Run all tests**

```bash
pytest -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_app_shell.py tests/test_item_app.py
git commit -m "feat: enable Items mode search"
```

---

## Phase Verification Checklist

Run:

```bash
pytest -q
```

Manual deterministic queries against the packaged `items.sqlite`:

```text
Amnis Rapier
critical rate
cr bow
highest dex% crysta
hp >= 5000 armor
hp > 5000 and cr bow
-aggro xtal
upgrade <known crysta name>
how to search
how many items are there
best tank xtal
```

Verify:

- exact names rank before fuzzy names;
- stat aliases resolve to canonical database stats;
- numeric/Boolean filters are deterministic;
- objective highest/lowest searches rank database values;
- subjective build queries refuse;
- failed stat/filter shapes offer grounded correction/clarification rather than inventing a query;
- cards show matched stats;
- detail opens in a modal and displays stored fields only;
- the public app cannot write `items.sqlite`;
- no `filter_search` runtime import is required.

Before moving to skill search, run:

```bash
python - <<'PY'
from pathlib import Path
text = "\n".join(path.read_text(errors="ignore") for path in Path("toram_search/items").rglob("*.py"))
for forbidden in ("ollama", "qwen", "gemma", "discord", "embedding"):
    assert forbidden not in text.casefold(), forbidden
PY
```

Expected: exit 0.
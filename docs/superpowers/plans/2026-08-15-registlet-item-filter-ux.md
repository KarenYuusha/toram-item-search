# Registlet Item Filtering and Focused UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hide contaminated `Regislet`/`Registlet` rows from every Item-facing path, keep `registlets.json` authoritative, and add focused Registlet/search UX improvements without changing source data.

**Architecture:** Make the contamination rule an Item-repository invariant so higher layers never need domain-specific suppression. Add outcome-level Registlet match metadata because every successful Registlet search uses one route for all returned records, then pass that metadata into the existing renderer. Keep Food behavior on the existing grouped `st.code` presentation and verify it rather than rewriting it.

**Tech Stack:** Python 3.12, Streamlit 1.61.x, SQLite read-only repositories, RapidFuzz 3.x, pytest 8.x, JSON/CSV project data.

## Global Constraints

- `items.sqlite`, `skills.sqlite`, `food_entries.csv`, `food_stat_aliases.json`, and `registlets.json` remain unchanged.
- `registlets.json` is the only source of Registlet search/display data.
- Item types `Regislet` and `Registlet` are excluded case-insensitively; surrounding whitespace is ignored.
- Excluded rows are invisible to Item listing, search, stats, counts, autocomplete, direct detail access, Universal Item routing, and upgrade relationships.
- Direct `ItemRepository.get_item()` for an excluded row raises `KeyError`.
- Upgrade predecessor/successor lists omit excluded rows; do not replace them with `Unknown item`.
- Registlet search precedence remains Stoodie structured → exact name → effect content → fuzzy-name fallback.
- Registlet effect matching remains deterministic whole-word/phrase matching; do not add fuzzy effect search.
- Food query grammar remains prefix-gated by `food` or `code`.
- Suggested/example searches remain fill-only and never auto-submit.
- Universal shows exactly three suggested searches; each domain mode shows at most three.
- No LLM, embeddings, RAG, frontend framework, database migration, or source-data rewrite.
- Full regression suite and `python -m compileall -q main.py toram_search ui` must pass before integration.

---

## File Map

- `toram_search/items/aliases.py` — canonical helper for recognizing excluded Registlet item types.
- `toram_search/items/repository.py` — repository-wide visibility invariant for Item rows.
- `tests/item_db_factory.py` — fixture support for contaminated rows and upgrade references.
- `tests/test_item_registlet_filter.py` — focused repository/service/autocomplete/Universal contamination regressions.
- `toram_search/registlets/models.py` — Registlet match-reason metadata types.
- `toram_search/registlets/service.py` — populate match metadata without changing search ranking.
- `tests/test_registlet_search.py` — RED/GREEN tests for name/effect/Stoodie/fuzzy match metadata.
- `ui/registlet_cards.py` — match-reason caption and compact Stoodie badges.
- `ui/results.py` — pass outcome match metadata into Registlet cards.
- `tests/test_ui_contract.py` — renderer/help/suggestion source-level contracts.
- `main.py` — reduce suggested examples and add compact syntax hints.
- `ui/sidebar.py` — explicitly document JSON source authority.
- `tests/test_real_databases.py` — final committed-source acceptance checks.

---

### Task 1: Enforce the Item repository visibility invariant

**Files:**
- Modify: `toram_search/items/aliases.py`
- Modify: `toram_search/items/repository.py`
- Modify: `tests/item_db_factory.py`
- Create: `tests/test_item_registlet_filter.py`

**Interfaces:**
- Produces: `is_registlet_item_type(item_type: str | None) -> bool`
- Produces: ItemRepository methods whose public signatures stay unchanged but never expose excluded item types.
- Consumes: existing `normalize_name()`, `ItemRepository`, `ItemSearchService`, `build_autocomplete_index()`, and `search_database()`.

- [ ] **Step 1: Extend the Item DB fixture with contaminated rows**

Add a helper to `tests/item_db_factory.py` so focused tests can create both spellings and an excluded upgrade reference without changing every existing fixture:

```python
def add_registlet_contamination(path: Path) -> None:
    db = sqlite3.connect(path)
    db.executemany(
        'INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
        [
            (90, 1, 'Pierce Regislet Item', ' Regislet ', 0, None, None, None, None, None, 'https://example.com/regislet', ''),
            (91, 1, 'Critical Registlet Item', 'REGISTLET', 0, None, None, None, None, None, 'https://example.com/registlet-2', ''),
        ],
    )
    db.executemany(
        'INSERT INTO item_stats VALUES (?,?,?,?,?,?,?,?,?)',
        [
            (90, 90, 0, 'Physical Pierce %', 99, '[]', None, None, 0),
            (91, 91, 0, 'Critical Rate', 999, '[]', None, None, 0),
            (92, 5, 1, 'Upgrade for', 90, '[]', None, None, 0),
        ],
    )
    db.commit()
    db.close()
```

- [ ] **Step 2: Write the failing repository-level tests**

Create `tests/test_item_registlet_filter.py` with a fixture and direct repository assertions:

```python
from pathlib import Path

import pytest

from tests.item_db_factory import add_registlet_contamination, create_item_database
from toram_search.items.repository import ItemRepository


@pytest.fixture
def contaminated_items(tmp_path: Path) -> Path:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    add_registlet_contamination(path)
    return path


def test_registlet_item_types_are_absent_from_repository_surface(contaminated_items: Path) -> None:
    with ItemRepository(contaminated_items) as repository:
        assert all(row.item_type.casefold().strip() not in {'regislet', 'registlet'} for row in repository.list_items())
        assert 'REGISTLET' not in repository.list_item_types()
        assert repository.count_items_total() == 8
        assert repository.count_items_with_stat('Critical Rate') == 3


def test_excluded_registlet_detail_is_unavailable(contaminated_items: Path) -> None:
    with ItemRepository(contaminated_items) as repository:
        with pytest.raises(KeyError):
            repository.get_item(90)
        with pytest.raises(KeyError):
            repository.get_item(91)


def test_excluded_registlet_upgrade_links_are_omitted(contaminated_items: Path) -> None:
    with ItemRepository(contaminated_items) as repository:
        assert all(row.id != 90 for row in repository.get_upgrade_predecessors(5))
        assert all(row.id != 90 for row in repository.get_upgrade_successors(90))
```

Also add exact/fuzzy/stat/structured assertions in the same test file:

```python
from toram_search.items.service import ItemSearchService


def test_item_search_never_returns_contaminated_rows(contaminated_items: Path) -> None:
    service = ItemSearchService(contaminated_items)
    try:
        for query in ('Pierce Regislet Item', 'Pierce Regis', 'physical pierce', 'highest cr'):
            outcome = service.search(query)
            assert all(row.item.id not in {90, 91} for row in outcome.results)
    finally:
        service.close()
```

- [ ] **Step 3: Run the focused tests and confirm RED**

Run:

```bash
python -m pytest -q tests/test_item_registlet_filter.py
```

Expected: FAIL because current repository methods still expose ids `90`/`91`, counts include them, and `get_item()` returns them.

- [ ] **Step 4: Add the canonical item-type helper**

In `toram_search/items/aliases.py` add:

```python
REGISTLET_ITEM_TYPES = frozenset({'regislet', 'registlet'})


def is_registlet_item_type(item_type: str | None) -> bool:
    return str(item_type or '').strip().casefold() in REGISTLET_ITEM_TYPES
```

Do not use fuzzy matching or name matching for this rule.

- [ ] **Step 5: Centralize SQL visibility inside ItemRepository**

In `toram_search/items/repository.py`, import `is_registlet_item_type` and add a fixed internal SQL predicate:

```python
_VISIBLE_ITEM_SQL = "LOWER(TRIM(COALESCE({column}, ''))) NOT IN ('regislet', 'registlet')"


def _visible_item_sql(column: str) -> str:
    return _VISIBLE_ITEM_SQL.format(column=column)
```

Only call `_visible_item_sql()` with hard-coded repository column identifiers such as `item_type` or `i.item_type`; never pass user input.

Use that predicate in:

```python
list_items()
list_item_types()
list_stat_names()
count_items_total()
count_items_by_types()
count_items_with_stat()
_summary()
get_upgrade_successors()
get_item()
search_stat()
```

For `get_item()` the initial query must include the visibility predicate so an excluded id produces `None` and therefore `KeyError`.

For `get_upgrade_predecessors()`, skip missing/excluded `_summary(pid)` values rather than creating `ItemSummary(pid, 'Unknown item', 'Unknown')`:

```python
summary = self._summary(pid)
if summary is not None:
    rows.append(summary)
```

`search_expression()` already begins from `list_items()`; retain that dependency so it inherits the invariant.

- [ ] **Step 6: Run focused tests to confirm GREEN**

Run:

```bash
python -m pytest -q tests/test_item_registlet_filter.py tests/test_item_search.py
```

Expected: PASS.

- [ ] **Step 7: Add integration regressions for autocomplete and Universal**

Extend `tests/test_item_registlet_filter.py` with:

```python
from toram_search.autocomplete import build_autocomplete_index
from toram_search.router import search_database


def test_item_autocomplete_excludes_contaminated_names(contaminated_items: Path, tmp_path: Path) -> None:
    suggestions = build_autocomplete_index(
        'Items',
        items_path=contaminated_items,
        skills_path=tmp_path / 'missing-skills.sqlite',
        food_entries_path=tmp_path / 'missing-food.csv',
        food_aliases_path=tmp_path / 'missing-food.json',
        registlets_path=tmp_path / 'missing-registlets.json',
        available_domains=frozenset({'Items'}),
    )
    assert not any('regislet item' in row.value.casefold() or 'registlet item' in row.value.casefold() for row in suggestions)


def test_universal_items_do_not_reactivate_contamination_when_registlets_unavailable(contaminated_items: Path, tmp_path: Path) -> None:
    outcome = search_database(
        'Universal',
        'Pierce Regislet Item',
        items_path=contaminated_items,
        skills_path=tmp_path / 'missing-skills.sqlite',
        registlets_path=tmp_path / 'missing-registlets.json',
        available_domains=frozenset({'Items'}),
    )
    assert outcome.items is not None
    assert all(row.item.id not in {90, 91} for row in outcome.items.results)
    assert outcome.registlets is None
```

- [ ] **Step 8: Run integration tests and full Item-related suite**

Run:

```bash
python -m pytest -q tests/test_item_registlet_filter.py tests/test_autocomplete_domains.py tests/test_universal_domains.py tests/test_real_databases.py
```

Expected: PASS.

- [ ] **Step 9: Commit Task 1**

```bash
git add toram_search/items/aliases.py toram_search/items/repository.py tests/item_db_factory.py tests/test_item_registlet_filter.py
git commit -m "fix: exclude Registlet rows from Item domain"
```

---

### Task 2: Add Registlet match-reason metadata

**Files:**
- Modify: `toram_search/registlets/models.py`
- Modify: `toram_search/registlets/service.py`
- Modify: `tests/test_registlet_search.py`

**Interfaces:**
- Produces: `RegistletMatchKind = Literal['name', 'effect', 'stoodie', 'fuzzy_name']`
- Produces: `RegistletMatch(kind: RegistletMatchKind, detail: str | None = None)`
- Produces: `RegistletSearchOutcome.match: RegistletMatch | None`
- Consumes: existing `RegistletSearchService.search()` and `_normalize_effect()`.

- [ ] **Step 1: Write failing metadata assertions**

Add to `tests/test_registlet_search.py`:

```python
def test_stoodie_search_reports_match_reason(registlet_file: Path) -> None:
    outcome = RegistletSearchService(registlet_file).search('std lvl220')
    assert outcome.match is not None
    assert outcome.match.kind == 'stoodie'
    assert outcome.match.detail == '220'


def test_exact_name_reports_match_reason(registlet_file: Path) -> None:
    outcome = RegistletSearchService(registlet_file).search('Arrow Rain Enhancer')
    assert outcome.match is not None
    assert outcome.match.kind == 'name'
    assert outcome.match.detail is None


def test_effect_reports_normalized_query_as_match_detail(registlet_file: Path) -> None:
    outcome = RegistletSearchService(registlet_file).search('  Physical   Pierce  ')
    assert outcome.match is not None
    assert outcome.match.kind == 'effect'
    assert outcome.match.detail == 'physical pierce'


def test_fuzzy_name_reports_fallback_reason(registlet_file: Path) -> None:
    outcome = RegistletSearchService(registlet_file).search('Arrow Rain Enhancerr')
    assert outcome.match is not None
    assert outcome.match.kind == 'fuzzy_name'
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
python -m pytest -q tests/test_registlet_search.py
```

Expected: FAIL with `AttributeError`/constructor mismatch because `RegistletSearchOutcome` has no `match` field.

- [ ] **Step 3: Add immutable match metadata types**

In `toram_search/registlets/models.py` add:

```python
RegistletMatchKind = Literal['name', 'effect', 'stoodie', 'fuzzy_name']


@dataclass(frozen=True)
class RegistletMatch:
    kind: RegistletMatchKind
    detail: str | None = None
```

and extend the outcome:

```python
@dataclass(frozen=True)
class RegistletSearchOutcome:
    # existing fields unchanged
    match: RegistletMatch | None = None
```

Keep the default `None` so not-found/clarify/suggest paths remain backward-compatible.

- [ ] **Step 4: Populate metadata in each successful search route**

In `toram_search/registlets/service.py`, import `RegistletMatch` and add only metadata changes:

```python
# Stoodie success
match=RegistletMatch('stoodie', str(level))

# exact name success
match=RegistletMatch('name')

# effect success
match=RegistletMatch('effect', _normalize_effect(raw))

# fuzzy-name success
match=RegistletMatch('fuzzy_name')
```

Do not alter `RouteQuality`, result ordering, thresholds, or effect matching.

- [ ] **Step 5: Run Registlet search tests to confirm GREEN**

Run:

```bash
python -m pytest -q tests/test_registlet_search.py tests/test_registlet_data.py tests/test_registlet_relationships.py
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add toram_search/registlets/models.py toram_search/registlets/service.py tests/test_registlet_search.py
git commit -m "feat: expose Registlet match reasons"
```

---

### Task 3: Render Registlet match reasons and Stoodie badges

**Files:**
- Modify: `ui/registlet_cards.py`
- Modify: `ui/results.py`
- Modify: `tests/test_ui_contract.py`

**Interfaces:**
- Consumes: `RegistletMatch` and `RegistletSearchOutcome.match` from Task 2.
- Produces: `render_registlet_cards(results: tuple[RegistletRecord, ...], *, limit: int, match: RegistletMatch | None) -> None`.

- [ ] **Step 1: Write failing UI contract assertions**

Extend `tests/test_ui_contract.py`:

```python
def test_registlet_cards_render_match_reason_and_level_badges() -> None:
    source = text('ui/registlet_cards.py')
    assert 'Matched by name' in source
    assert 'Matched by effect:' in source
    assert 'Matched by Stoodie Lv' in source
    assert 'Matched by fuzzy name' in source
    assert ':gray-badge[Lv' in source


def test_registlet_results_pass_match_metadata_to_cards() -> None:
    source = text('ui/results.py')
    assert 'match=outcome.match' in source
```

- [ ] **Step 2: Run UI contract tests and confirm RED**

Run:

```bash
python -m pytest -q tests/test_ui_contract.py
```

Expected: FAIL because current cards accept only `record` and render Stoodie levels as one plain text line.

- [ ] **Step 3: Add a pure formatter for the match caption**

In `ui/registlet_cards.py` import `RegistletMatch` and add:

```python
def _match_label(match: RegistletMatch | None) -> str | None:
    if match is None:
        return None
    if match.kind == 'name':
        return 'Matched by name'
    if match.kind == 'effect':
        return f'Matched by effect: {match.detail}'
    if match.kind == 'stoodie':
        return f'Matched by Stoodie Lv{match.detail}'
    return 'Matched by fuzzy name'
```

- [ ] **Step 4: Render the hierarchy and compact badges**

Change `_render_registlet_card` to accept `match` and render in approved order:

```python
def _render_registlet_card(record: RegistletRecord, match: RegistletMatch | None) -> None:
    st.markdown(f'**{record.name}**')
    label = _match_label(match)
    if label:
        st.caption(label)
    st.caption(f'Max Lv. {record.max_lv}')
    st.write(record.effect)
    if record.source_levels:
        badges = ' '.join(f':gray-badge[Lv{level}]' for level in record.source_levels)
        st.markdown(f'**Stoodie Sources:** {badges}')
    if record.affects_skill:
        st.write('**Affected Skills:** ' + ', '.join(record.affects_skill))
```

Update `render_registlet_cards(..., match=...)` and pass the same outcome-level match to every visible record.

In `ui/results.py` call:

```python
render_registlet_cards(outcome.results, limit=limit, match=outcome.match)
```

- [ ] **Step 5: Run UI and Registlet tests to confirm GREEN**

Run:

```bash
python -m pytest -q tests/test_ui_contract.py tests/test_registlet_search.py
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add ui/registlet_cards.py ui/results.py tests/test_ui_contract.py
git commit -m "feat: clarify Registlet result matches"
```

---

### Task 4: Reduce suggested-search crowding and add near-input guidance

**Files:**
- Modify: `main.py`
- Modify: `ui/sidebar.py`
- Modify: `tests/test_ui_contract.py`
- Modify: `tests/test_app_shell.py` only if an existing exact example-count assertion requires updating.

**Interfaces:**
- Produces: static per-mode example tuples with exactly three Universal examples and no more than three in any domain mode.
- Produces: compact per-mode syntax hint displayed immediately before `render_search_box()`.
- Consumes: existing fill-only example behavior and sidebar Help expander.

- [ ] **Step 1: Write failing example-density and help tests**

Add to `tests/test_ui_contract.py`:

```python
def test_universal_suggested_searches_are_limited_to_three() -> None:
    source = text('main.py')
    assert "'Universal':('critical rate','food maxmp','physical pierce')" in source


def test_domain_suggested_searches_have_at_most_three_each() -> None:
    source = text('main.py')
    assert "'Items':('cr bow','hp >= 5000 armor','highest cr')" in source
    assert "'Skills':('Guardian','Shield Skills','skills that inflict stun')" in source
    assert "'Food':('food maxmp','code ampr','food dt fire')" in source
    assert "'Registlets':('std 220','Arrow Rain Enhancer','physical pierce')" in source


def test_main_shows_compact_search_syntax_hint_before_input() -> None:
    source = text('main.py')
    assert 'syntax_hints=' in source
    assert 'Try: cr bow · food maxmp · std 220 · physical pierce' in source
    assert source.index('st.caption(syntax_hints[mode])') < source.index('submission=render_search_box')


def test_sidebar_help_states_registlet_json_is_authoritative() -> None:
    source = text('ui/sidebar.py')
    assert 'registlets.json' in source
    assert 'not the Item database' in source
```

Keep the existing `test_examples_are_fill_only_not_query_submissions()` unchanged.

- [ ] **Step 2: Run UI tests and confirm RED**

Run:

```bash
python -m pytest -q tests/test_ui_contract.py tests/test_app_shell.py
```

Expected: FAIL because Universal currently has five examples, domain modes have four, no near-input syntax hint exists, and Help does not name the JSON source explicitly.

- [ ] **Step 3: Replace the example tuples with static three-item sets**

In `main.py` use:

```python
examples={
    'Universal':('critical rate','food maxmp','physical pierce'),
    'Items':('cr bow','hp >= 5000 armor','highest cr'),
    'Skills':('Guardian','Shield Skills','skills that inflict stun'),
    'Food':('food maxmp','code ampr','food dt fire'),
    'Registlets':('std 220','Arrow Rain Enhancer','physical pierce'),
}[mode]
```

Do not alter the existing fill-only handler:

```python
st.session_state.query=example_query
st.session_state.last_outcome=None
_reset_limits()
st.rerun()
```

- [ ] **Step 4: Add compact mode-aware syntax hints immediately before the search box**

In `main.py`, after placeholders and before `render_search_box()`, add:

```python
syntax_hints={
    'Universal':'Try: cr bow · food maxmp · std 220 · physical pierce',
    'Items':'Try: item name · cr bow · hp >= 5000 armor',
    'Skills':'Try: Guardian · Shield Skills · skills that inflict stun',
    'Food':'Start with food/code: food maxmp · code ampr',
    'Registlets':'Try: std 220 · Arrow Rain Enhancer · physical pierce',
}
st.caption(syntax_hints[mode])
```

This hint is display-only and must not participate in query state.

- [ ] **Step 5: Clarify JSON authority in Search Help**

In the Registlet section of `ui/sidebar.py`, append one concise sentence:

```text
Registlet results come from `registlets.json`, not the Item database.
```

Do not add source-path details elsewhere in the UI.

- [ ] **Step 6: Run UI tests to confirm GREEN**

Run:

```bash
python -m pytest -q tests/test_ui_contract.py tests/test_app_shell.py
```

Expected: PASS.

- [ ] **Step 7: Commit Task 4**

```bash
git add main.py ui/sidebar.py tests/test_ui_contract.py tests/test_app_shell.py
git commit -m "feat: simplify search guidance"
```

---

### Task 5: Lock down Food UX and real-source authority

**Files:**
- Modify: `tests/test_ui_contract.py`
- Modify: `tests/test_real_databases.py`
- Modify: `ui/food_cards.py` only if the acceptance test proves the existing renderer does not satisfy the approved copy/grouping behavior.

**Interfaces:**
- Consumes: existing `render_food_cards()` grouping by `entry.level` and `st.code(code, language=None)` rendering.
- Produces: acceptance evidence that Food remains grouped highest-level-first and each displayed code uses the copy-capable code-block control.
- Produces: real committed-data evidence that Registlet Item rows cannot leak through Item search while Registlet search still comes from JSON.

- [ ] **Step 1: Add source-level Food renderer acceptance checks**

Extend `tests/test_ui_contract.py` so the existing behavior is explicit:

```python
def test_food_cards_keep_highest_level_grouping_and_copy_affordance() -> None:
    source = text('ui/food_cards.py')
    assert 'for level in sorted(grouped, reverse=True)' in source
    assert 'st.code(code, language=None)' in source
```

If this test passes immediately, do not change `ui/food_cards.py`; this requirement is already satisfied and only needed regression coverage.

- [ ] **Step 2: Add real-source contamination acceptance tests**

In `tests/test_real_databases.py`, import `ItemRepository`, `REGISTLET_DATA`, and `RegistletSearchService` if not already imported, then add:

```python
def test_real_item_repository_exposes_no_registlet_item_types() -> None:
    with ItemRepository(ITEM_DATABASE) as repository:
        assert all(
            row.item_type.strip().casefold() not in {'regislet', 'registlet'}
            for row in repository.list_items()
        )


def test_real_registlet_search_is_served_from_json() -> None:
    outcome = RegistletSearchService(REGISTLET_DATA).search('std 220')
    assert outcome.results
    assert all(220 in row.source_levels for row in outcome.results)
```

Also add one Universal regression using a real Registlet name selected deterministically from JSON:

```python
def test_real_universal_registlet_name_does_not_surface_as_item() -> None:
    service = RegistletSearchService(REGISTLET_DATA)
    name = service.dataset.records[0].name
    outcome = search_database(
        'Universal',
        name,
        items_path=ITEM_DATABASE,
        skills_path=SKILL_DATABASE,
    )
    assert outcome.items is not None
    assert all(row.item.name.casefold() != name.casefold() for row in outcome.items.results)
```

- [ ] **Step 3: Run acceptance tests**

Run:

```bash
python -m pytest -q tests/test_ui_contract.py tests/test_real_databases.py
```

Expected: PASS after Tasks 1–4. If the Food renderer acceptance test already passes before any Food edit, leave `ui/food_cards.py` untouched.

- [ ] **Step 4: Run the complete regression suite**

Run:

```bash
python -m pytest -q
python -m compileall -q main.py toram_search ui
```

Expected: all tests PASS and compile command exits 0.

- [ ] **Step 5: Verify protected data files are unchanged**

Compare branch blobs against the feature base for:

```text
items.sqlite
skills.sqlite
food_entries.csv
food_stat_aliases.json
registlets.json
```

Expected: identical blob SHAs for all five files.

- [ ] **Step 6: Commit Task 5 tests**

```bash
git add tests/test_ui_contract.py tests/test_real_databases.py
git commit -m "test: lock Registlet source authority UX"
```

If `ui/food_cards.py` required a real fix because the acceptance check failed, include it in this commit and document the exact failing behavior in the commit body.

---

## Final Review Checklist

Before integration, verify every approved requirement against the implementation:

- [ ] Both `Regislet` and `Registlet` item types are excluded case-insensitively with whitespace ignored.
- [ ] Exact/fuzzy/stat/structured Item search cannot return contaminated rows.
- [ ] Item counts, stat vocabulary, type vocabulary, autocomplete, detail lookup, and upgrade links cannot expose contaminated rows.
- [ ] Universal never uses `items.sqlite` as Registlet fallback, including when `registlets.json` is unavailable.
- [ ] Registlet name/effect/Stoodie/fuzzy routes expose the correct match metadata without ranking changes.
- [ ] Registlet cards show match reason, max level, unchanged effect, discrete Stoodie badges, and affected Skills.
- [ ] Food remains highest-level-first and each displayed code keeps the copy affordance.
- [ ] Universal has exactly three visible examples; each domain mode has at most three.
- [ ] Example buttons remain fill-only.
- [ ] A compact syntax hint appears before the search box.
- [ ] Sidebar Help states Food grammar, Registlet search modes, and `registlets.json` authority.
- [ ] Full pytest suite passes.
- [ ] Python compilation passes.
- [ ] All five protected data files retain their original blob SHAs.

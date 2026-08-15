# Registlet Item Filtering and Focused UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hide contaminated `Regislet`/`Registlet` rows from every Item-facing path, keep `registlets.json` authoritative, and add focused Registlet/search UX improvements without changing source data.

**Architecture:** Make the contamination rule an Item-repository invariant so autocomplete, parsers, services, and Universal routing inherit the same filtered Item view. Add one outcome-level Registlet match descriptor because each successful Registlet query uses exactly one route for all returned records. Keep the existing Food level grouping and `st.code` presentation unless acceptance tests prove a real gap.

**Tech Stack:** Python 3.12, Streamlit 1.61.x, SQLite read-only repositories, RapidFuzz 3.x, pytest 8.x, JSON/CSV project data.

## Global Constraints

- Do not modify `items.sqlite`, `skills.sqlite`, `food_entries.csv`, `food_stat_aliases.json`, or `registlets.json`.
- `registlets.json` is the only Registlet search/display source.
- Exclude `Regislet` and `Registlet` item types case-insensitively with surrounding whitespace ignored.
- Excluded rows are invisible to Item listing, vocabulary, counts, exact/fuzzy/stat/structured search, autocomplete, detail access, Universal Item routing, and upgrade relationships.
- `ItemRepository.get_item(excluded_id)` raises `KeyError`.
- Upgrade lists omit excluded rows and never replace them with `Unknown item`.
- Registlet search precedence stays Stoodie structured → exact name → effect content → fuzzy-name fallback.
- Do not add fuzzy effect matching or infer Registlet relationships from effect text.
- Food query grammar remains prefix-gated by `food` or `code`.
- Suggested searches remain fill-only and never auto-submit.
- Universal shows exactly three suggested searches; every domain mode shows at most three.
- No LLM, embeddings, RAG, frontend framework, database migration, or source-data rewrite.
- Before integration run `python -m pytest -q` and `python -m compileall -q main.py toram_search ui`.

---

### Task 1: Make Registlet contamination impossible inside the Item repository

**Files:**
- Modify: `toram_search/items/aliases.py`
- Modify: `toram_search/items/repository.py`
- Modify: `tests/item_db_factory.py`
- Create: `tests/test_item_registlet_filter.py`

**Interfaces:**
- Produces: `is_registlet_item_type(item_type: str | None) -> bool`
- Preserves all existing `ItemRepository` public signatures.

- [ ] **Step 1: Add contaminated fixture rows**

Append this helper to `tests/item_db_factory.py`:

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

- [ ] **Step 2: Write the failing repository tests**

Create `tests/test_item_registlet_filter.py`:

```python
from pathlib import Path

import pytest

from tests.item_db_factory import add_registlet_contamination, create_item_database
from toram_search.items.repository import ItemRepository
from toram_search.items.service import ItemSearchService


@pytest.fixture
def contaminated_items(tmp_path: Path) -> Path:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    add_registlet_contamination(path)
    return path


def test_repository_hides_registlet_types_from_lists_counts_and_stats(contaminated_items: Path) -> None:
    with ItemRepository(contaminated_items) as repository:
        assert repository.count_items_total() == 8
        assert repository.count_items_by_types(('REGISTLET', ' Regislet ')) == 0
        assert repository.count_items_with_stat('Critical Rate') == 3
        assert 'Physical Pierce %' not in repository.list_stat_names()
        assert all(row.item_type.strip().casefold() not in {'regislet', 'registlet'} for row in repository.list_items())
        assert all(value.strip().casefold() not in {'regislet', 'registlet'} for value in repository.list_item_types())


def test_repository_denies_direct_detail_and_filters_upgrade_links(contaminated_items: Path) -> None:
    with ItemRepository(contaminated_items) as repository:
        with pytest.raises(KeyError):
            repository.get_item(90)
        with pytest.raises(KeyError):
            repository.get_item(91)
        assert [row.id for row in repository.get_upgrade_predecessors(5)] == [4]
        assert repository.get_upgrade_successors(90) == ()


def test_all_item_search_shapes_hide_contaminated_rows(contaminated_items: Path) -> None:
    service = ItemSearchService(contaminated_items)
    try:
        for query in ('Pierce Regislet Item', 'Pierce Regis', 'physical pierce', 'highest cr'):
            outcome = service.search(query)
            assert all(row.item.id not in {90, 91} for row in outcome.results)
    finally:
        service.close()
```

- [ ] **Step 3: Confirm RED**

Run:

```bash
python -m pytest -q tests/test_item_registlet_filter.py
```

Expected: FAIL because ids 90/91 are currently visible.

- [ ] **Step 4: Add the canonical type helper**

In `toram_search/items/aliases.py` add:

```python
REGISTLET_ITEM_TYPES = frozenset({'regislet', 'registlet'})


def is_registlet_item_type(item_type: str | None) -> bool:
    return str(item_type or '').strip().casefold() in REGISTLET_ITEM_TYPES
```

- [ ] **Step 5: Centralize the SQL visibility predicate**

In `toram_search/items/repository.py` add a fixed internal helper:

```python
_VISIBLE_ITEM_SQL = "LOWER(TRIM(COALESCE({column}, ''))) NOT IN ('regislet', 'registlet')"


def _visible_item_sql(column: str) -> str:
    return _VISIBLE_ITEM_SQL.format(column=column)
```

Only call it with hard-coded identifiers such as `item_type` or `i.item_type`.

Apply it to `list_items`, `list_item_types`, `list_stat_names`, `count_items_total`, `count_items_by_types`, `count_items_with_stat`, `_summary`, `get_upgrade_successors`, `get_item`, and `search_stat`.

`search_expression()` must continue to start from `list_items()` so it inherits the invariant.

Change predecessor handling from a placeholder summary to omission:

```python
summary = self._summary(pid)
if summary is not None:
    rows.append(summary)
```

For `get_upgrade_successors(item_id)`, first reject an excluded/missing source id:

```python
if self._summary(item_id) is None:
    return ()
```

- [ ] **Step 6: Confirm GREEN for repository/service behavior**

Run:

```bash
python -m pytest -q tests/test_item_registlet_filter.py tests/test_item_search.py
```

Expected: PASS.

- [ ] **Step 7: Add autocomplete and Universal source-authority tests**

Extend `tests/test_item_registlet_filter.py` with JSON fixture coverage:

```python
import json

from toram_search.autocomplete import build_autocomplete_index
from toram_search.router import search_database


def make_registlet_json(path: Path, *, name: str = 'Pierce Regislet Item') -> Path:
    path.write_text(json.dumps({
        'metadata': {'valid_stoodie_levels': [220]},
        'registlets': [{
            'name': name,
            'max_lv': 10,
            'effect': 'JSON authoritative effect text.',
            'affects_skill': None,
            'obtained_from': {
                'source': 'Stoodie', 'location': 'El Scaro',
                'level_notation': '220', 'levels': [220],
            },
        }],
    }), encoding='utf-8')
    return path


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


def test_same_name_uses_json_registlet_and_never_item_row(contaminated_items: Path, tmp_path: Path) -> None:
    registlets = make_registlet_json(tmp_path / 'registlets.json')
    outcome = search_database(
        'Universal', 'Pierce Regislet Item',
        items_path=contaminated_items,
        skills_path=tmp_path / 'missing-skills.sqlite',
        registlets_path=registlets,
        available_domains=frozenset({'Items', 'Registlets'}),
    )
    assert outcome.items is not None and not outcome.items.results
    assert outcome.registlets is not None
    assert [row.effect for row in outcome.registlets.results] == ['JSON authoritative effect text.']


def test_missing_json_never_reactivates_item_contamination(contaminated_items: Path, tmp_path: Path) -> None:
    outcome = search_database(
        'Universal', 'Pierce Regislet Item',
        items_path=contaminated_items,
        skills_path=tmp_path / 'missing-skills.sqlite',
        registlets_path=tmp_path / 'missing-registlets.json',
        available_domains=frozenset({'Items'}),
    )
    assert outcome.items is not None and not outcome.items.results
    assert outcome.registlets is None
```

- [ ] **Step 8: Run integration regressions**

```bash
python -m pytest -q tests/test_item_registlet_filter.py tests/test_autocomplete_domains.py tests/test_universal_domains.py
```

Expected: PASS.

- [ ] **Step 9: Commit Task 1**

```bash
git add toram_search/items/aliases.py toram_search/items/repository.py tests/item_db_factory.py tests/test_item_registlet_filter.py
git commit -m "fix: exclude Registlet rows from Item domain"
```

---

### Task 2: Add Registlet match metadata without changing routing

**Files:**
- Modify: `toram_search/registlets/models.py`
- Modify: `toram_search/registlets/service.py`
- Modify: `toram_search/router.py`
- Modify: `tests/test_registlet_search.py`
- Modify: `tests/test_universal_domains.py`

**Interfaces:**
- Produces: `RegistletMatchKind = Literal['name', 'effect', 'stoodie', 'fuzzy_name']`
- Produces: `RegistletMatch(kind: RegistletMatchKind, detail: str | None = None)`
- Produces: `RegistletSearchOutcome.match: RegistletMatch | None`

- [ ] **Step 1: Write failing match-reason tests**

Add to `tests/test_registlet_search.py`:

```python
def test_success_routes_expose_match_metadata(registlet_file: Path) -> None:
    stoodie = RegistletSearchService(registlet_file).search('std lvl220')
    exact = RegistletSearchService(registlet_file).search('Arrow Rain Enhancer')
    effect = RegistletSearchService(registlet_file).search('  Physical   Pierce  ')
    fuzzy = RegistletSearchService(registlet_file).search('Arrow Rain Enhancerr')

    assert (stoodie.match.kind, stoodie.match.detail) == ('stoodie', '220')
    assert (exact.match.kind, exact.match.detail) == ('name', None)
    assert (effect.match.kind, effect.match.detail) == ('effect', 'physical pierce')
    assert (fuzzy.match.kind, fuzzy.match.detail) == ('fuzzy_name', None)
```

Also add a suppression test to `tests/test_universal_domains.py` that creates a successful Registlet effect route which loses to a stronger exact domain and asserts `outcome.registlets.match is None` after suppression.

- [ ] **Step 2: Confirm RED**

```bash
python -m pytest -q tests/test_registlet_search.py tests/test_universal_domains.py
```

Expected: FAIL because `RegistletSearchOutcome` has no `match` field.

- [ ] **Step 3: Add immutable match types**

In `toram_search/registlets/models.py`:

```python
RegistletMatchKind = Literal['name', 'effect', 'stoodie', 'fuzzy_name']


@dataclass(frozen=True)
class RegistletMatch:
    kind: RegistletMatchKind
    detail: str | None = None
```

Add to `RegistletSearchOutcome`:

```python
match: RegistletMatch | None = None
```

- [ ] **Step 4: Populate metadata on successful routes only**

In `toram_search/registlets/service.py`:

```python
# Stoodie results
match=RegistletMatch('stoodie', str(level))

# exact name results
match=RegistletMatch('name')

# effect results
match=RegistletMatch('effect', _normalize_effect(raw))

# fuzzy name results
match=RegistletMatch('fuzzy_name')
```

Do not change route quality, thresholds, result ordering, or effect matching.

- [ ] **Step 5: Clear stale match metadata when Universal suppresses Registlets**

In `toram_search/router.py`, keep generic suppression but add the Registlet-only metadata reset:

```python
if domain == 'Items':
    return replace(outcome, routing_confidence='none', **common)
if domain == 'Registlets':
    return replace(outcome, match=None, **common)
return replace(outcome, **common)
```

This is not contamination filtering; it only prevents hidden results from retaining a misleading match reason.

- [ ] **Step 6: Confirm GREEN**

```bash
python -m pytest -q tests/test_registlet_search.py tests/test_registlet_data.py tests/test_registlet_relationships.py tests/test_universal_domains.py
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git add toram_search/registlets/models.py toram_search/registlets/service.py toram_search/router.py tests/test_registlet_search.py tests/test_universal_domains.py
git commit -m "feat: expose Registlet match reasons"
```

---

### Task 3: Render match reasons and compact Stoodie badges

**Files:**
- Modify: `ui/registlet_cards.py`
- Modify: `ui/results.py`
- Modify: `tests/test_ui_contract.py`

**Interfaces:**
- Consumes: `RegistletMatch` from Task 2.
- Produces: `render_registlet_cards(results: tuple[RegistletRecord, ...], *, limit: int, match: RegistletMatch | None) -> None`

- [ ] **Step 1: Write failing UI contract tests**

```python
def test_registlet_cards_render_match_reason_and_level_badges() -> None:
    source = text('ui/registlet_cards.py')
    assert 'Matched by name' in source
    assert 'Matched by effect:' in source
    assert 'Matched by Stoodie Lv' in source
    assert 'Matched by fuzzy name' in source
    assert ':gray-badge[Lv' in source


def test_registlet_results_pass_outcome_match_to_cards() -> None:
    assert 'match=outcome.match' in text('ui/results.py')
```

- [ ] **Step 2: Confirm RED**

```bash
python -m pytest -q tests/test_ui_contract.py
```

Expected: FAIL because cards currently render no match reason and a plain source-level text line.

- [ ] **Step 3: Add a pure label formatter**

In `ui/registlet_cards.py`:

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

- [ ] **Step 4: Render the approved card hierarchy**

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

Change `render_registlet_cards()` to accept `match` and pass it to each visible card. In `ui/results.py` call:

```python
render_registlet_cards(outcome.results, limit=limit, match=outcome.match)
```

- [ ] **Step 5: Confirm GREEN**

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

### Task 4: Simplify suggested searches and put syntax guidance near the input

**Files:**
- Modify: `main.py`
- Modify: `ui/sidebar.py`
- Modify: `tests/test_ui_contract.py`
- Modify: `tests/test_app_shell.py` only if an existing exact example-count assertion requires it.

**Interfaces:**
- Preserves the existing fill-only example flow.
- Produces exactly three Universal examples and at most three examples in each domain mode.

- [ ] **Step 1: Write failing UX contract tests**

```python
def test_suggested_search_density_is_small_and_static() -> None:
    source = text('main.py')
    assert "'Universal':('critical rate','food maxmp','physical pierce')" in source
    assert "'Items':('cr bow','hp >= 5000 armor','highest cr')" in source
    assert "'Skills':('Guardian','Shield Skills','skills that inflict stun')" in source
    assert "'Food':('food maxmp','code ampr','food dt fire')" in source
    assert "'Registlets':('std 220','Arrow Rain Enhancer','physical pierce')" in source


def test_compact_syntax_hint_is_before_search_input() -> None:
    source = text('main.py')
    assert 'syntax_hints=' in source
    assert 'Try: cr bow · food maxmp · std 220 · physical pierce' in source
    assert source.index('st.caption(syntax_hints[mode])') < source.index('submission=render_search_box')


def test_help_names_registlet_json_as_source_of_truth() -> None:
    source = text('ui/sidebar.py')
    assert 'registlets.json' in source
    assert 'not the Item database' in source
```

Keep `test_examples_are_fill_only_not_query_submissions()` unchanged.

- [ ] **Step 2: Confirm RED**

```bash
python -m pytest -q tests/test_ui_contract.py tests/test_app_shell.py
```

Expected: FAIL because current Universal has five examples, domain modes have four, no near-input hint exists, and Help does not name the JSON source.

- [ ] **Step 3: Replace examples with the approved static sets**

In `main.py`:

```python
examples={
    'Universal':('critical rate','food maxmp','physical pierce'),
    'Items':('cr bow','hp >= 5000 armor','highest cr'),
    'Skills':('Guardian','Shield Skills','skills that inflict stun'),
    'Food':('food maxmp','code ampr','food dt fire'),
    'Registlets':('std 220','Arrow Rain Enhancer','physical pierce'),
}[mode]
```

Do not alter the existing fill-only handler.

- [ ] **Step 4: Add compact mode-aware hints directly before the search box**

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

- [ ] **Step 5: Clarify Search Help**

Add to the Registlet help section in `ui/sidebar.py`:

```text
Registlet results come from `registlets.json`, not the Item database.
```

- [ ] **Step 6: Confirm GREEN**

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

### Task 5: Acceptance-lock Food UX, real sources, and protected data

**Files:**
- Modify: `tests/test_ui_contract.py`
- Modify: `tests/test_real_databases.py`
- Modify: `ui/food_cards.py` only if the acceptance test exposes a real gap.

**Interfaces:**
- Consumes: current `render_food_cards()` grouping and code-block rendering.
- Produces: final evidence that committed Registlet rows cannot leak through Items and source data remains untouched.

- [ ] **Step 1: Lock the existing Food behavior with a regression**

```python
def test_food_cards_keep_highest_level_grouping_and_code_copy_affordance() -> None:
    source = text('ui/food_cards.py')
    assert 'for level in sorted(grouped, reverse=True)' in source
    assert 'st.code(code, language=None)' in source
```

This is an acceptance lock, not a forced rewrite. If it passes immediately, leave `ui/food_cards.py` unchanged.

- [ ] **Step 2: Add real-source regressions**

In `tests/test_real_databases.py` add:

```python
from toram_search.database import REGISTLET_DATA
from toram_search.registlets.service import RegistletSearchService


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


def test_real_universal_registlet_name_never_surfaces_as_item() -> None:
    service = RegistletSearchService(REGISTLET_DATA)
    name = service.dataset.records[0].name
    outcome = search_database(
        'Universal', name,
        items_path=ITEM_DATABASE,
        skills_path=SKILL_DATABASE,
    )
    assert outcome.items is not None
    assert all(row.item.name.casefold() != name.casefold() for row in outcome.items.results)
```

- [ ] **Step 3: Run focused acceptance tests**

```bash
python -m pytest -q tests/test_ui_contract.py tests/test_real_databases.py
```

Expected: PASS after Tasks 1–4.

- [ ] **Step 4: Run the full verification commands**

```bash
python -m pytest -q
python -m compileall -q main.py toram_search ui
```

Expected: zero test failures and compile exit code 0.

- [ ] **Step 5: Verify the five protected data blobs**

Compare branch vs. base SHA for:

```text
items.sqlite
skills.sqlite
food_entries.csv
food_stat_aliases.json
registlets.json
```

Expected: identical blob SHA for every file.

- [ ] **Step 6: Commit Task 5**

```bash
git add tests/test_ui_contract.py tests/test_real_databases.py
git commit -m "test: lock Registlet source authority UX"
```

If `ui/food_cards.py` genuinely required a fix, include that file and describe the specific failing acceptance behavior in the commit body.

---

## Final Review Checklist

- [ ] Both contaminated item-type spellings are excluded with case/whitespace normalization.
- [ ] Item list/type/stat vocabulary and every Item count ignore contaminated rows.
- [ ] Exact/fuzzy/stat/structured Item search ignores contaminated rows.
- [ ] Item autocomplete ignores contaminated names.
- [ ] Direct Item detail access raises `KeyError` for contaminated ids.
- [ ] Upgrade relationships omit contaminated rows and excluded source ids yield no successors.
- [ ] Missing `registlets.json` never reactivates contaminated Item rows.
- [ ] Same-name Item/JSON data displays only the JSON Registlet record.
- [ ] Registlet match metadata is correct for Stoodie, exact name, effect, and fuzzy name.
- [ ] Suppressed Universal Registlet outcomes clear stale match metadata.
- [ ] Registlet cards show match reason, max level, unchanged effect text, Stoodie badges, and affected Skills.
- [ ] Food remains highest-level-first and keeps its code-copy affordance.
- [ ] Universal has exactly three visible examples and every mode has at most three.
- [ ] Example buttons remain fill-only.
- [ ] Compact syntax guidance appears before the search input.
- [ ] Search Help states Food grammar, Registlet search modes, and `registlets.json` authority.
- [ ] Full pytest and compile checks pass.
- [ ] All five protected data files retain their original blob SHAs.

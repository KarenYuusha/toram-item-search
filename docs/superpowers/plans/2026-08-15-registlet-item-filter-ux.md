# Registlet Item Filtering and Focused UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hide contaminated `Regislet`/`Registlet` rows from every Item-facing path, keep `registlets.json` authoritative, and add focused Registlet/search UX improvements without changing source data.

**Architecture:** Enforce contamination filtering at the Item repository boundary so parsers, autocomplete, services, and Universal routing inherit the same view. Add one outcome-level Registlet match descriptor because every successful Registlet search uses exactly one route for all returned records. Preserve existing Food level grouping/code-block rendering unless acceptance tests expose a real gap.

**Tech Stack:** Python 3.12, Streamlit 1.61.x, SQLite read-only repositories, RapidFuzz 3.x, pytest 8.x, JSON/CSV project data.

## Global Constraints

- Do not modify `items.sqlite`, `skills.sqlite`, `food_entries.csv`, `food_stat_aliases.json`, or `registlets.json`.
- `registlets.json` is the only source of Registlet search/display data.
- Exclude `Regislet` and `Registlet` item types case-insensitively; ignore surrounding whitespace.
- Excluded rows are invisible to Item lists, vocabulary, counts, exact/fuzzy/stat/structured search, autocomplete, detail access, Universal Item routing, and upgrade relationships.
- `ItemRepository.get_item(excluded_id)` raises `KeyError`.
- Upgrade lists omit excluded rows and never create `Unknown item` placeholders for them.
- Registlet precedence stays Stoodie structured → exact name → effect content → fuzzy-name fallback.
- Do not add fuzzy effect matching or infer Skill relationships from effect text.
- Food search remains prefix-gated by `food` or `code`.
- Suggested searches remain fill-only and never auto-submit.
- Universal shows exactly three suggestions; every domain mode shows at most three.
- No LLM, embeddings, RAG, frontend framework, migration, or source-data rewrite.
- Before integration run `python -m pytest -q` and `python -m compileall -q main.py toram_search ui`.

---

### Task 1: Enforce the Item repository visibility invariant

**Files:**
- Modify: `toram_search/items/aliases.py`
- Modify: `toram_search/items/repository.py`
- Modify: `tests/item_db_factory.py`
- Create: `tests/test_item_registlet_filter.py`

**Interfaces:**
- Produces: `is_registlet_item_type(item_type: str | None) -> bool`
- Preserves all existing `ItemRepository` public signatures.

- [ ] **Step 1: Add contaminated fixture rows**

Append to `tests/item_db_factory.py`:

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

- [ ] **Step 2: Write failing repository/service tests**

Create `tests/test_item_registlet_filter.py`:

```python
from pathlib import Path

import pytest

from tests.item_db_factory import add_registlet_contamination, create_item_database
from toram_search.items.aliases import is_registlet_item_type
from toram_search.items.repository import ItemRepository
from toram_search.items.service import ItemSearchService


@pytest.fixture
def contaminated_items(tmp_path: Path) -> Path:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    add_registlet_contamination(path)
    return path


def test_registlet_item_type_detection_is_case_and_whitespace_insensitive() -> None:
    assert is_registlet_item_type(' Regislet ')
    assert is_registlet_item_type('REGISTLET')
    assert not is_registlet_item_type('Normal Crysta')


def test_repository_hides_registlets_from_lists_counts_and_vocabulary(contaminated_items: Path) -> None:
    with ItemRepository(contaminated_items) as repository:
        assert repository.count_items_total() == 8
        assert repository.count_items_by_types(('REGISTLET', ' Regislet ')) == 0
        assert repository.count_items_with_stat('Critical Rate') == 3
        assert 'Physical Pierce %' not in repository.list_stat_names()
        assert all(not is_registlet_item_type(row.item_type) for row in repository.list_items())
        assert all(not is_registlet_item_type(value) for value in repository.list_item_types())


def test_repository_denies_detail_and_filters_upgrade_links(contaminated_items: Path) -> None:
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

```bash
python -m pytest -q tests/test_item_registlet_filter.py
```

Expected: FAIL because the helper is missing and contaminated rows are visible.

- [ ] **Step 4: Add the canonical item-type helper**

In `toram_search/items/aliases.py`:

```python
REGISTLET_ITEM_TYPES = frozenset({'regislet', 'registlet'})


def is_registlet_item_type(item_type: str | None) -> bool:
    return str(item_type or '').strip().casefold() in REGISTLET_ITEM_TYPES
```

- [ ] **Step 5: Centralize repository filtering**

In `toram_search/items/repository.py`, import `is_registlet_item_type` and add:

```python
_VISIBLE_ITEM_SQL = "LOWER(TRIM(COALESCE({column}, ''))) NOT IN ('regislet', 'registlet')"


def _visible_item_sql(column: str) -> str:
    return _VISIBLE_ITEM_SQL.format(column=column)
```

Call `_visible_item_sql()` only with hard-coded repository identifiers such as `item_type` and `i.item_type`.

Apply the predicate to `list_items`, `list_item_types`, `list_stat_names`, `count_items_total`, `count_items_by_types`, `count_items_with_stat`, `_summary`, `get_upgrade_successors`, `get_item`, and `search_stat`. Keep `search_expression()` based on `list_items()` so it inherits the invariant.

Use `is_registlet_item_type()` for any Python-side item-type check rather than duplicating case/whitespace normalization.

Change predecessor resolution to omit excluded summaries:

```python
summary = self._summary(pid)
if summary is not None:
    rows.append(summary)
```

Before finding successors, reject an excluded/missing source id:

```python
if self._summary(item_id) is None:
    return ()
```

- [ ] **Step 6: Confirm GREEN for repository/service behavior**

```bash
python -m pytest -q tests/test_item_registlet_filter.py tests/test_item_search.py
```

Expected: PASS.

- [ ] **Step 7: Add autocomplete and source-authority integration tests**

Extend `tests/test_item_registlet_filter.py`:

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


def test_same_name_displays_json_registlet_not_item_row(contaminated_items: Path, tmp_path: Path) -> None:
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

### Task 2: Add Registlet match metadata without changing search semantics

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

- [ ] **Step 1: Write failing match metadata tests**

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

Add this concrete suppression unit test to `tests/test_universal_domains.py`:

```python
from toram_search.interpretation import RouteQuality
from toram_search.registlets.models import RegistletMatch, RegistletSearchOutcome
from toram_search.router import _suppress_outcome


def test_suppressed_registlet_outcome_clears_match_metadata() -> None:
    raw = RegistletSearchOutcome(
        kind='results',
        query='physical pierce',
        results=(),
        route_quality=RouteQuality('content', True, 2),
        match=RegistletMatch('effect', 'physical pierce'),
    )
    suppressed = _suppress_outcome('Registlets', raw)
    assert suppressed.match is None
    assert suppressed.route_quality == raw.route_quality
```

- [ ] **Step 2: Confirm RED**

```bash
python -m pytest -q tests/test_registlet_search.py tests/test_universal_domains.py
```

Expected: FAIL because `RegistletMatch` and `RegistletSearchOutcome.match` do not exist.

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

In `toram_search/registlets/service.py` import `RegistletMatch` and add:

```python
# Stoodie results
match=RegistletMatch('stoodie', str(level))

# exact name results
match=RegistletMatch('name')

# effect results
match=RegistletMatch('effect', _normalize_effect(raw))

# fuzzy-name results
match=RegistletMatch('fuzzy_name')
```

Do not change route quality, thresholds, ordering, or effect matching.

- [ ] **Step 5: Clear stale metadata on suppressed Universal Registlet outcomes**

In `toram_search/router.py`:

```python
if domain == 'Items':
    return replace(outcome, routing_confidence='none', **common)
if domain == 'Registlets':
    return replace(outcome, match=None, **common)
return replace(outcome, **common)
```

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

### Task 3: Render Registlet match reasons and Stoodie badges

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

Expected: FAIL because cards currently have no match label and render source levels as one plain text line.

- [ ] **Step 3: Add a pure match-label formatter**

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

- [ ] **Step 4: Render the approved hierarchy**

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

Update `render_registlet_cards()` to accept `match` and pass it to each card. In `ui/results.py`:

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

### Task 4: Reduce suggestion crowding and add near-input guidance

**Files:**
- Modify: `main.py`
- Modify: `ui/sidebar.py`
- Modify: `tests/test_ui_contract.py`
- Modify: `tests/test_app_shell.py`

**Interfaces:**
- Preserves the existing fill-only example flow.
- Produces exactly three Universal examples and no more than three examples in each domain mode.

- [ ] **Step 1: Write failing source-level UX tests**

Add to `tests/test_ui_contract.py`:

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

- [ ] **Step 2: Confirm RED**

```bash
python -m pytest -q tests/test_ui_contract.py tests/test_app_shell.py
```

Expected: FAIL because current example sets are larger and the syntax/source-authority text is missing.

- [ ] **Step 3: Replace example tuples with the approved static sets**

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

Keep the existing fill-only state update unchanged.

Because `Guardian` is no longer a Universal example, update `test_example_button_fills_query_without_searching()` in `tests/test_app_shell.py` to use a retained example:

```python
def test_example_button_fills_query_without_searching() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    target = next(button for button in app.button if button.label == 'critical rate')
    target.click().run(timeout=10)
    assert app.session_state['query'] == 'critical rate'
    assert app.session_state['last_outcome'] is None
```

Keep `test_food_example_fills_query_without_submitting()` unchanged.

- [ ] **Step 4: Add compact mode-aware hints before the search box**

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

Add to the Registlet section of `ui/sidebar.py`:

```text
Registlet results come from `registlets.json`, not the Item database.
```

- [ ] **Step 6: Confirm GREEN**

```bash
python -m pytest -q tests/test_ui_contract.py tests/test_app_shell.py
```

Expected: PASS, including fill-only example behavior.

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
- Modify: `ui/food_cards.py` only if the acceptance regression below fails because the renderer lacks the approved behavior.

**Interfaces:**
- Consumes: current `render_food_cards()` level grouping and `st.code` rendering.
- Produces: final evidence that committed Registlet rows cannot leak through Items and data files remain untouched.

- [ ] **Step 1: Lock the existing Food presentation**

Add to `tests/test_ui_contract.py`:

```python
def test_food_cards_keep_highest_level_grouping_and_code_copy_affordance() -> None:
    source = text('ui/food_cards.py')
    assert 'for level in sorted(grouped, reverse=True)' in source
    assert 'st.code(code, language=None)' in source
```

If this passes immediately, do not edit `ui/food_cards.py`.

- [ ] **Step 2: Add real-source regressions**

In `tests/test_real_databases.py` add imports as needed and these tests:

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

- [ ] **Step 4: Run full verification**

```bash
python -m pytest -q
python -m compileall -q main.py toram_search ui
```

Expected: zero failures and compile exit code 0.

- [ ] **Step 5: Verify protected data blobs**

Compare the implementation branch against its base for:

```text
items.sqlite
skills.sqlite
food_entries.csv
food_stat_aliases.json
registlets.json
```

Expected: identical blob SHA for all five.

- [ ] **Step 6: Commit Task 5**

```bash
git add tests/test_ui_contract.py tests/test_real_databases.py
git commit -m "test: lock Registlet source authority UX"
```

If `ui/food_cards.py` required a real fix, include it in this commit and describe the failing acceptance behavior in the commit body.

---

## Final Review Checklist

- [ ] Both contaminated item-type spellings are excluded with case/whitespace normalization.
- [ ] Item lists, vocabularies, counts, all search paths, autocomplete, detail access, and upgrades ignore contaminated rows.
- [ ] Missing `registlets.json` never reactivates contaminated Item rows.
- [ ] Same-name Item/JSON data displays only the JSON Registlet record.
- [ ] Registlet match metadata is correct for Stoodie, exact name, effect, and fuzzy name.
- [ ] Suppressed Universal Registlet outcomes clear stale match metadata.
- [ ] Registlet cards show match reason, max level, unchanged effect, discrete Stoodie badges, and affected Skills.
- [ ] Food remains highest-level-first and keeps its code-copy affordance.
- [ ] Universal has exactly three visible examples and every mode has at most three.
- [ ] Example buttons remain fill-only.
- [ ] Compact syntax guidance appears before the search input.
- [ ] Search Help states Food grammar, Registlet search modes, and `registlets.json` authority.
- [ ] Full pytest and compile checks pass.
- [ ] All five protected data files retain their original blob SHAs.

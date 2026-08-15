# Food and Registlet Search Domains Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic Food and Registlet search domains, cross-domain Universal routing, Registlet effect search, Skill↔Registlet relationships, autocomplete, help, and UI integration without changing the committed SQLite databases.

**Architecture:** Keep Food and Registlet as small source-backed modules beside the existing Item and Skill modules. Each domain owns loading, validation, parsing, models, and search; `router.py` compares only shared `RouteQuality` metadata and suppresses lower-quality outcomes generically. Streamlit remains a rendering/state layer and continues to search only after explicit submission.

**Tech Stack:** Python 3, Streamlit `>=1.61,<1.62`, RapidFuzz `>=3,<4`, SQLite read-only access for existing Items/Skills, CSV/JSON for Food/Registlet sources, pytest.

## Global Constraints

- The public app remains deterministic; do not add an LLM, embeddings, RAG, model-generated answers, or external search services.
- Keep root `main.py` as the Streamlit entry point.
- Do not modify `items.sqlite` or `skills.sqlite`; verify their blob hashes remain unchanged before completion.
- Food uses root `food_entries.csv` and `food_stat_aliases.json`; Registlets use root `registlets.json`.
- Food search is valid only when the normalized query starts with standalone `food` or `code`.
- Food code values are result fields and are not searchable.
- Registlet search supports Stoodie level, exact/fuzzy name, and deterministic effect text matching; fuzzy matching is never used over effect text.
- `affects_skill` is manually curated only; never infer Skill relations from effect text.
- Examples, autocomplete, corrections, suggestions, and interpretation-chip removals remain fill-only; they never trigger a search.
- Universal mode degrades per domain when a source is unavailable instead of disabling all healthy domains.
- Implement every task regression-first: RED test, confirm failure, minimal GREEN implementation, focused tests, then commit.

---

## File Structure

Create these focused domain modules:

```text
toram_search/
  food/
    __init__.py          public Food exports
    models.py            Food definitions, entries, dataset, search outcome
    data.py              alias/CSV loading, normalization, validation, caching
    service.py           prefix parsing, stat lookup, ordering, suggestions
  registlets/
    __init__.py          public Registlet exports
    models.py            Registlet records, dataset, search outcome
    data.py              JSON loading, validation, caching
    relationships.py     manual Skill relation validation + reverse index
    service.py           Stoodie/name/effect/fuzzy search
ui/
  food_cards.py          grouped Food level/code rendering
  registlet_cards.py     Registlet cards/detail rendering
```

Modify only the shared integration files that need the new domains:

```text
toram_search/interpretation.py
toram_search/models.py
toram_search/database.py
toram_search/autocomplete.py
toram_search/router.py
toram_search/skills/models.py
ui/results.py
ui/skill_dialog.py
ui/sidebar.py
main.py
README.md
```

Add focused tests instead of putting all behavior in one file:

```text
tests/test_food_data.py
tests/test_food_search.py
tests/test_registlet_data.py
tests/test_registlet_search.py
tests/test_registlet_relationships.py
tests/test_universal_domains.py
```

Extend existing `tests/test_interpretation.py`, `tests/test_database.py`, `tests/test_real_databases.py`, `tests/test_app_shell.py`, and `tests/test_ui_contract.py` for shared contracts/regressions.

---

### Task 1: Generalize shared domain and route-quality models

**Files:**
- Modify: `toram_search/interpretation.py`
- Modify: `toram_search/models.py`
- Test: `tests/test_interpretation.py`

**Interfaces:**
- Produces `SearchDomain = Literal['Items', 'Skills', 'Food', 'Registlets']`.
- Produces `RouteFamily = Literal['exact', 'structured', 'content', 'weak', 'none']`.
- Produces `ChipKind` additions `food_stat` and `stoodie_level`.
- Extends `DatabaseMode` with `Food` and `Registlets`.
- Extends `UniversalSearchOutcome` with optional `food` and `registlets` outcomes.

- [ ] **Step 1: Write the failing route-quality and type-contract tests**

Add to `tests/test_interpretation.py`:

```python
def test_content_route_sits_between_structured_no_result_and_weak_result() -> None:
    assert RouteQuality('structured', False, 1).sort_key > RouteQuality('content', True, 99).sort_key
    assert RouteQuality('content', True, 1).sort_key > RouteQuality('weak', True, 99).sort_key


def test_new_domain_interpretations_are_valid() -> None:
    food = QueryInterpretation(
        domain='Food',
        canonical_query='food maxmp',
        chips=(QueryChip('food_stat', 'food_stat', 'Food: MaxMP', 'food maxmp', ''),),
    )
    stoodie = QueryInterpretation(
        domain='Registlets',
        canonical_query='std 220',
        chips=(QueryChip('stoodie_level', 'stoodie_level', 'Stoodie Lv220', 'std 220', ''),),
    )
    assert food.query_without('food_stat') == ''
    assert stoodie.query_without('stoodie_level') == ''
```

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
pytest tests/test_interpretation.py -q
```

Expected: failures because `content`, `Food`, `Registlets`, `food_stat`, and `stoodie_level` are not accepted yet.

- [ ] **Step 3: Implement the minimal shared-model changes**

Use this route ordering in `RouteQuality.sort_key`:

```python
if self.family in {'exact', 'structured'} and self.has_results:
    result_tier = 4
elif self.family in {'exact', 'structured'}:
    result_tier = 3
elif self.family == 'content' and self.has_results:
    result_tier = 2
elif self.family == 'weak' and self.has_results:
    result_tier = 1
else:
    result_tier = 0
family_rank = {'exact': 3, 'structured': 2, 'content': 1, 'weak': 0, 'none': 0}[self.family]
return result_tier, family_rank, self.specificity
```

Extend `toram_search/models.py` without importing runtime domain classes; keep Food/Registlet imports under `TYPE_CHECKING` exactly as Items/Skills are handled.

- [ ] **Step 4: Run shared model tests GREEN**

Run:

```bash
pytest tests/test_interpretation.py -q
```

Expected: all tests pass, including the existing exact/structured/weak ordering regressions.

- [ ] **Step 5: Commit**

```bash
git add toram_search/interpretation.py toram_search/models.py tests/test_interpretation.py
git commit -m "refactor: generalize search domain routing types"
```

---

### Task 2: Load and validate Food aliases and entries

**Files:**
- Create: `toram_search/food/__init__.py`
- Create: `toram_search/food/models.py`
- Create: `toram_search/food/data.py`
- Create: `tests/test_food_data.py`

**Interfaces:**
- `normalize_food_text(value: str) -> str`
- `FoodStatDefinition(key: str, display: str, aliases: tuple[str, ...])`
- `FoodEntry(code: str, stat_key: str, stat_display: str, level: int)`
- `FoodDataset(stats: tuple[FoodStatDefinition, ...], entries: tuple[FoodEntry, ...], warnings: tuple[str, ...])`
- `FoodDataError(ValueError)` for a malformed/missing top-level source.
- `load_food_dataset(entries_path: Path, aliases_path: Path) -> FoodDataset`
- `resolve_food_stat(dataset: FoodDataset, value: str) -> FoodStatDefinition | None`

- [ ] **Step 1: Write failing loader tests**

Create fixtures directly in `tests/test_food_data.py` and assert exact behavior:

```python
def test_food_loader_resolves_key_display_alias_and_deduplicates(tmp_path: Path) -> None:
    aliases = tmp_path / 'aliases.json'
    aliases.write_text(json.dumps({'stats': [{
        'key': 'physical_resistance_pct',
        'display': 'Physical Resistance %',
        'aliases': ['physical resist', 'p res'],
    }]}), encoding='utf-8')
    entries = tmp_path / 'food.csv'
    entries.write_text(
        'code,stat,level\n00123,physical_resistance_pct,10\n00123,P. Res,10\n00456,Physical Resistance %,8\n',
        encoding='utf-8',
    )
    dataset = load_food_dataset(entries, aliases)
    assert [(row.code, row.stat_key, row.level) for row in dataset.entries] == [
        ('00123', 'physical_resistance_pct', 10),
        ('00456', 'physical_resistance_pct', 8),
    ]
```

Also add tests that a malformed row is skipped with a row-numbered warning, unknown stat is not fuzzy-reinterpreted, code keeps leading zeros, and malformed aliases raise `FoodDataError`.

- [ ] **Step 2: Run loader tests and confirm RED**

```bash
pytest tests/test_food_data.py -q
```

Expected: import/module failures because the Food package does not exist.

- [ ] **Step 3: Implement exact normalization, validation, and cache invalidation**

`normalize_food_text` should normalize case, whitespace, periods, and spacing around `%`, `+`, and `-`, but must not remove the semantic sign from Aggro. Build one exact lookup containing every stat key, display label, and alias. Do not use substring or fuzzy matching while loading CSV rows.

Cache by resolved source path plus `st_mtime_ns` and size, e.g.:

```python
@lru_cache(maxsize=16)
def _cached_load(entries_name: str, entries_mtime: int, entries_size: int,
                 aliases_name: str, aliases_mtime: int, aliases_size: int) -> FoodDataset:
    return _load_uncached(Path(entries_name), Path(aliases_name))
```

`load_food_dataset()` computes those file identities and calls `_cached_load`.

- [ ] **Step 4: Run loader tests GREEN**

```bash
pytest tests/test_food_data.py -q
```

Expected: all Food data tests pass.

- [ ] **Step 5: Commit**

```bash
git add toram_search/food tests/test_food_data.py
git commit -m "feat: load and validate Food sources"
```

---

### Task 3: Implement prefix-gated Food search and Food interpretation

**Files:**
- Create: `toram_search/food/service.py`
- Modify: `toram_search/food/models.py`
- Create: `tests/test_food_search.py`

**Interfaces:**
- `FoodSearchOutcome(kind, query, results, message, suggested_queries, interpretation, route_quality)` with result tuple of `FoodEntry`.
- `is_food_intent(query: str) -> bool` returns true only for a first standalone `food` or `code` token.
- `FoodSearchService(entries_path: Path, aliases_path: Path)`.
- `FoodSearchService.search(query: str) -> FoodSearchOutcome`.
- `FoodSearchService.list_autocomplete_values() -> tuple[tuple[str, Literal['Food Stat']], ...]` returns prefixed values such as `food MaxMP`.

- [ ] **Step 1: Write failing Food query tests**

Cover the approved syntax:

```python
@pytest.mark.parametrize('query', ['food maxmp', 'code max mp'])
def test_food_search_requires_prefix_and_orders_highest_level_first(food_files, query) -> None:
    outcome = FoodSearchService(*food_files).search(query)
    assert outcome.route_quality.family == 'structured'
    assert [row.level for row in outcome.results] == sorted((row.level for row in outcome.results), reverse=True)
    assert outcome.interpretation is not None
    assert outcome.interpretation.domain == 'Food'


@pytest.mark.parametrize('query', ['maxmp', 'maxmp food', '51110000'])
def test_food_does_not_activate_without_leading_prefix(food_files, query) -> None:
    outcome = FoodSearchService(*food_files).search(query)
    assert outcome.route_quality.family == 'none'
    assert outcome.results == ()
```

Add `code ampr`, `food dt dark`, and `food -aggro` alias tests. Add invalid/missing stat tests that remain `structured` with no results and emit prefixed fill-only suggestions such as `food MaxMP`.

- [ ] **Step 2: Run query tests and confirm RED**

```bash
pytest tests/test_food_search.py -q
```

Expected: failures because `FoodSearchService` is absent.

- [ ] **Step 3: Implement exact prefix parsing and stat search**

Use a first-token regex equivalent to:

```python
match = re.match(r'^\s*(food|code)(?:\s+|$)(.*)$', query, re.IGNORECASE)
```

If no match, return family `none`. If the prefix is recognized but remainder is empty/unknown, return family `structured`, `has_results=False`, Food-specific guidance, and no weak fallback. For valid stats, sort rows by `(-level, code)` and emit one `QueryChip`:

```python
QueryChip(
    id='food_stat', kind='food_stat', label=f'Food: {stat.display}',
    canonical_fragment=f'food {stat.display}', query_without='',
)
```

- [ ] **Step 4: Run Food tests GREEN**

```bash
pytest tests/test_food_data.py tests/test_food_search.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add toram_search/food tests/test_food_search.py
git commit -m "feat: add prefix-gated Food search"
```

---

### Task 4: Load Registlets and implement Stoodie/name/effect search

**Files:**
- Create: `toram_search/registlets/__init__.py`
- Create: `toram_search/registlets/models.py`
- Create: `toram_search/registlets/data.py`
- Create: `toram_search/registlets/service.py`
- Create: `tests/test_registlet_data.py`
- Create: `tests/test_registlet_search.py`

**Interfaces:**
- `RegistletRecord(name, max_lv, effect, affects_skill, source, location, source_levels)`.
- `RegistletDataset(records, valid_stoodie_levels, warnings)`.
- `RegistletDataError(ValueError)`.
- `load_registlet_dataset(path: Path) -> RegistletDataset` with mtime/size-aware caching.
- `is_stoodie_intent(query: str) -> bool`.
- `RegistletSearchOutcome(kind, query, results, message, suggested_queries, interpretation, route_quality)`.
- `RegistletSearchService(path: Path).search(query: str) -> RegistletSearchOutcome`.
- `list_autocomplete_values() -> tuple[tuple[str, Literal['Registlet']], ...]`.

- [ ] **Step 1: Write failing Registlet loader/search tests**

Use a small JSON fixture with records that distinguish phrase, token-only, exact name, and fuzzy name behavior. Required assertions include:

```python
@pytest.mark.parametrize('query', [
    'std 220', 'std lv 220', 'std lvl220', 'std level 220',
    'stoodie 220', 'stoodie lvl 220',
])
def test_stoodie_aliases_use_explicit_source_levels(registlet_file, query) -> None:
    outcome = RegistletSearchService(registlet_file).search(query)
    assert outcome.route_quality.family == 'structured'
    assert [row.name for row in outcome.results] == sorted(row.name for row in outcome.results)
    assert all(220 in row.source_levels for row in outcome.results)


def test_exact_name_outranks_effect_content(registlet_file) -> None:
    outcome = RegistletSearchService(registlet_file).search('Arrow Rain Enhancer')
    assert outcome.route_quality.family == 'exact'
    assert [row.name for row in outcome.results] == ['Arrow Rain Enhancer']


def test_effect_phrase_match_is_content_route(registlet_file) -> None:
    outcome = RegistletSearchService(registlet_file).search('restores mp')
    assert outcome.route_quality.family == 'content'
    assert outcome.results
```

Also prove phrase matches sort before all-token matches, fuzzy typo recovery uses only names, invalid `std 200` suggests nearest metadata levels, and `level_notation` is not reparsed.

- [ ] **Step 2: Run focused tests and confirm RED**

```bash
pytest tests/test_registlet_data.py tests/test_registlet_search.py -q
```

Expected: Registlet package imports fail.

- [ ] **Step 3: Implement deterministic parsing/search**

Stoodie parsing accepts only one level and no ranges. Normalize effect text into whitespace-separated casefolded tokens. Effect route logic is exactly:

```python
phrase_hits = [r for r in records if normalized_query in normalize_effect(r.effect)]
if phrase_hits:
    return sorted(phrase_hits, key=lambda r: r.name.casefold())

tokens = tuple(token for token in normalized_query.split() if token)
token_hits = [r for r in records if all(token in normalize_effect(r.effect) for token in tokens)]
```

Do not call RapidFuzz on `effect`. Only after Stoodie, exact-name, and effect-content all fail may fuzzy name matching run, using deterministic score/name tie-breaking and the existing project threshold style.

- [ ] **Step 4: Run Registlet tests GREEN**

```bash
pytest tests/test_registlet_data.py tests/test_registlet_search.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add toram_search/registlets tests/test_registlet_data.py tests/test_registlet_search.py
git commit -m "feat: add deterministic Registlet search"
```

---

### Task 5: Build manual Skill↔Registlet relationships without changing skills.sqlite

**Files:**
- Create: `toram_search/registlets/relationships.py`
- Modify: `toram_search/skills/models.py`
- Create: `tests/test_registlet_relationships.py`

**Interfaces:**
- `RegistletRelationshipIndex(by_skill: dict[str, tuple[str, ...]], warnings: tuple[str, ...])`.
- `build_relationship_index(records: tuple[RegistletRecord, ...], canonical_skill_names: tuple[str, ...]) -> RegistletRelationshipIndex`.
- `SkillCardResult.related_registlets: tuple[str, ...] = ()`.
- Keys in `by_skill` use `casefold()` of canonical Skill names; values use Registlet display names sorted case-insensitively.

- [ ] **Step 1: Write failing relationship tests**

```python
def test_relationship_index_supports_null_one_multiple_and_unknown() -> None:
    records = (
        make_registlet('None', None),
        make_registlet('One', ('Arrow Rain',)),
        make_registlet('Many', ('Arrow Rain', 'Magic: Finale')),
        make_registlet('Broken', ('Missing Skill',)),
    )
    index = build_relationship_index(records, ('Arrow Rain', 'Magic: Finale'))
    assert index.by_skill['arrow rain'] == ('Many', 'One')
    assert index.by_skill['magic: finale'] == ('Many',)
    assert any('Missing Skill' in warning for warning in index.warnings)
```

Also assert the source `RegistletRecord.affects_skill` remains unchanged and no inferred relation appears from effect text.

- [ ] **Step 2: Run and confirm RED**

```bash
pytest tests/test_registlet_relationships.py -q
```

Expected: relationship module/type additions are missing.

- [ ] **Step 3: Implement exact canonical-name validation**

Build `{name.casefold(): name}` from `SkillRepository.list_skill_names()` callers. Do not fuzzy-correct unknown relationship names. Add warnings for unknown names and skip only the invalid edge; keep the Registlet itself valid.

- [ ] **Step 4: Run GREEN**

```bash
pytest tests/test_registlet_relationships.py tests/test_skill_search.py -q
```

Expected: new tests and existing Skill search tests pass.

- [ ] **Step 5: Commit**

```bash
git add toram_search/registlets/relationships.py toram_search/skills/models.py tests/test_registlet_relationships.py
git commit -m "feat: add Registlet skill relationships"
```

---

### Task 6: Add independent source health and autocomplete

**Files:**
- Modify: `toram_search/database.py`
- Modify: `toram_search/autocomplete.py`
- Modify: `tests/test_database.py`
- Create: `tests/test_autocomplete_domains.py`

**Interfaces:**
- Add constants `FOOD_ENTRIES`, `FOOD_ALIASES`, `REGISTLET_DATA` rooted beside existing SQLite files.
- `validate_food_sources(entries_path=FOOD_ENTRIES, aliases_path=FOOD_ALIASES) -> DatabaseHealth`.
- `validate_registlet_source(path=REGISTLET_DATA) -> DatabaseHealth`.
- `validate_sources(...) -> tuple[DatabaseHealth, DatabaseHealth, DatabaseHealth, DatabaseHealth]` ordered Items, Skills, Food, Registlets.
- Extend `build_autocomplete_index(..., food_entries_path, food_aliases_path, registlets_path)`.

- [ ] **Step 1: Write failing health/autocomplete tests**

Assert a malformed Food aliases file makes Food unhealthy, a malformed Registlet top-level file makes Registlets unhealthy, and valid individual-row warnings do not make a domain unavailable. Autocomplete assertions:

```python
assert any(row.kind == 'Food Stat' and row.value == 'food MaxMP' for row in suggestions)
assert not any(row.kind == 'Food Stat' and row.value == 'MaxMP' for row in suggestions)
assert any(row.kind == 'Registlet' and row.value == 'Arrow Rain Enhancer' for row in suggestions)
```

- [ ] **Step 2: Run and confirm RED**

```bash
pytest tests/test_database.py tests/test_autocomplete_domains.py -q
```

Expected: missing validators/kinds/path arguments.

- [ ] **Step 3: Implement domain-local validation and autocomplete**

Reuse the domain loaders as validators so production loading and health checks cannot disagree. Extend `_ALLOWED_BY_MODE` with Food/Registlet suggestion kinds. In Universal, include all healthy domain suggestions; callers skip unhealthy sources instead of failing the whole index.

- [ ] **Step 4: Run GREEN**

```bash
pytest tests/test_database.py tests/test_autocomplete_domains.py -q
```

- [ ] **Step 5: Commit**

```bash
git add toram_search/database.py toram_search/autocomplete.py tests/test_database.py tests/test_autocomplete_domains.py
git commit -m "feat: add Food and Registlet source health"
```

---

### Task 7: Replace pairwise Universal suppression with four-domain route comparison

**Files:**
- Modify: `toram_search/router.py`
- Modify: `toram_search/skills/models.py`
- Create: `tests/test_universal_domains.py`
- Modify: `tests/test_real_databases.py`

**Interfaces:**
- Extend `search_database(mode, query, *, items_path, skills_path, food_entries_path, food_aliases_path, registlets_path, available_domains=None)`.
- `available_domains` is a `frozenset[SearchDomain] | None`; `None` means all four are available for unit/backward-compatible callers.
- Add helper `select_winning_interpretation(*outcomes)` using route quality, never result count.
- Add helper that compares all present outcomes and suppresses lower-quality domain results; suppression is per-outcome replacement, not pairwise X-vs-Y rules.
- When Registlet and Skill sources are both available, enrich returned `SkillCardResult.related_registlets` through the relationship index.

- [ ] **Step 1: Write failing Universal routing regressions**

Use stub/fake source fixtures so each quality family is controlled. Required cases:

```python
def test_exact_skill_suppresses_registlet_content_and_weak_item(...): ...
def test_structured_food_suppresses_weak_other_domains(...): ...
def test_stoodie_structured_suppresses_weak_other_domains(...): ...
def test_registlet_content_outranks_weak_other_domains(...): ...
def test_equal_route_quality_can_keep_legitimate_results(...): ...
def test_structured_no_result_food_intent_suppresses_weak_guesses(...): ...
def test_bare_maxmp_never_activates_food(...): ...
def test_result_count_never_beats_route_quality(...): ...
```

Keep the existing real `MAGIC: FINALE` regression and update its `search_database` call with the new source paths only if defaults are not used.

- [ ] **Step 2: Run routing tests and confirm RED**

```bash
pytest tests/test_universal_domains.py tests/test_real_databases.py -q
```

Expected: failures because router still handles Items/Skills pairwise and does not know Food/Registlets/content.

- [ ] **Step 3: Implement generic quality selection**

Build a domain list such as:

```python
candidates = [
    ('Items', items), ('Skills', skills), ('Food', food), ('Registlets', registlets),
]
active = [(domain, outcome) for domain, outcome in candidates if outcome is not None]
best_key = max((outcome.route_quality.sort_key for _, outcome in active), default=RouteQuality().sort_key)
```

Suppress an outcome only when `outcome.route_quality.sort_key < best_key`; keep equal keys. Implement one suppression helper per outcome type so existing Item fields such as `routing_confidence` stay valid, but do not encode any pairwise domain combinations.

If Food is unavailable and `is_food_intent(query)` is true, or Registlets are unavailable and `is_stoodie_intent(query)` is true, skip weak unrelated results so the UI's domain-health warning is the only guidance.

For relationship enrichment, open `SkillRepository` only when both Skills and Registlets are healthy, build the index, and `dataclasses.replace(card, related_registlets=...)` for each Skill card.

- [ ] **Step 4: Run router + existing Item/Skill regressions GREEN**

```bash
pytest tests/test_universal_domains.py tests/test_real_databases.py tests/test_item_search.py tests/test_skill_search.py -q
```

- [ ] **Step 5: Commit**

```bash
git add toram_search/router.py toram_search/skills/models.py tests/test_universal_domains.py tests/test_real_databases.py
git commit -m "refactor: generalize Universal domain routing"
```

---

### Task 8: Render Food/Registlet results, Skill relations, modes, help, and app state

**Files:**
- Create: `ui/food_cards.py`
- Create: `ui/registlet_cards.py`
- Modify: `ui/results.py`
- Modify: `ui/skill_dialog.py`
- Modify: `ui/sidebar.py`
- Modify: `main.py`
- Modify: `tests/test_app_shell.py`
- Modify: `tests/test_ui_contract.py`

**Interfaces:**
- `render_food_results(outcome: FoodSearchOutcome, *, limit: int) -> str | None`.
- `render_registlet_results(outcome: RegistletSearchOutcome, *, limit: int) -> str | None`.
- Session state adds `food_limit=20`, `registlet_limit=20`; all four limits reset on mode change, new submission, correction fill, example fill, or chip removal.
- Sidebar modes exactly `Universal`, `Items`, `Skills`, `Food`, `Registlets`.

- [ ] **Step 1: Write failing UI/state/help tests**

Extend `tests/test_app_shell.py` to assert all five radio options exist, Food/Registlet limit reset is fill-only, and example buttons such as `food maxmp` do not set a submission nonce.

Extend `tests/test_ui_contract.py` with source checks:

```python
def test_sidebar_help_documents_food_and_registlet_rules() -> None:
    source = text('ui/sidebar.py')
    assert 'Search Help' in source
    assert 'food maxmp' in source
    assert 'code ampr' in source
    assert 'Code values themselves are not searchable' in source
    assert 'std 220' in source
    assert 'Search by effect' in source


def test_main_keeps_four_independent_result_limits() -> None:
    source = text('main.py')
    for key in ('item_limit', 'skill_limit', 'food_limit', 'registlet_limit'):
        assert key in source
```

Also assert `ui/skill_dialog.py` renders `Related Registlets` when `card.related_registlets` is non-empty.

- [ ] **Step 2: Run UI tests and confirm RED**

```bash
pytest tests/test_app_shell.py tests/test_ui_contract.py -q
```

- [ ] **Step 3: Implement UI integration with no auto-search path**

Food rendering groups visible entries by level after the service has already sorted them. Registlet cards show name, max level, effect, source levels, and explicit affected Skills. Skill dialog adds:

```python
if card.related_registlets:
    st.markdown('#### Related Registlets')
    for name in card.related_registlets:
        st.write(name)
```

In `main.py`, replace the two-health `can_search` calculation with per-domain health. Dedicated modes require their own domain. Universal remains enabled when at least one domain is healthy and shows warnings for each unavailable domain. Pass `available_domains` into router/autocomplete.

Keep this invariant around every fill-only path:

```python
st.session_state.query = fill_value
st.session_state.last_outcome = None
# reset all four limits
st.rerun()
```

Never assign `query_to_run` from examples, suggestions, corrections, autocomplete, or chip-removal paths.

- [ ] **Step 4: Run UI and domain tests GREEN**

```bash
pytest tests/test_app_shell.py tests/test_ui_contract.py tests/test_food_search.py tests/test_registlet_search.py -q
```

- [ ] **Step 5: Commit**

```bash
git add ui main.py tests/test_app_shell.py tests/test_ui_contract.py
git commit -m "feat: integrate Food and Registlet UI"
```

---

### Task 9: Update docs, validate committed data, and run full verification

**Files:**
- Modify: `README.md`
- Modify: `tests/test_real_databases.py`
- No changes allowed: `items.sqlite`, `skills.sqlite`, `food_entries.csv`, `food_stat_aliases.json`, `registlets.json` unless a failing validation test proves a user-data defect that must be discussed separately.

**Interfaces:**
- README describes four searchable domains, Food prefix syntax, Registlet routes, source files, and deterministic/no-LLM behavior.
- Real-data tests exercise current committed Food and Registlet files rather than only fixtures.

- [ ] **Step 1: Add real-source acceptance tests before documentation changes**

Add tests equivalent to:

```python
def test_committed_food_sources_support_prefixed_search() -> None:
    outcome = FoodSearchService(FOOD_ENTRIES, FOOD_ALIASES).search('food maxmp')
    assert outcome.results
    assert outcome.route_quality.family == 'structured'


def test_committed_registlets_support_stoodie_and_effect_search() -> None:
    service = RegistletSearchService(REGISTLET_DATA)
    assert service.search('std 220').results
    assert service.search('restores mp').results
```

Also add a real Universal regression proving `food maxmp` returns Food without unrelated weak domains and a bare `maxmp` has no Food outcome/results.

- [ ] **Step 2: Run acceptance tests and confirm current status**

```bash
pytest tests/test_real_databases.py -q
```

If any failure is caused by malformed user-maintained Food/Registlet source data, stop implementation of that specific data-dependent assertion and report the exact row/record warning rather than silently changing the source.

- [ ] **Step 3: Update README with exact supported syntax**

Document these examples verbatim:

```text
food maxmp
code ampr
std 220
Arrow Rain Enhancer
restores mp
```

State that bare numeric Food codes are not searchable and that Registlet effect search is deterministic text matching, not semantic/AI search.

- [ ] **Step 4: Run complete verification**

Run:

```bash
pytest -q
python -m compileall -q main.py toram_search ui
git diff --exit-code -- items.sqlite skills.sqlite
```

Then compare the committed SQLite blob SHAs against the pre-feature values:

```text
items.sqlite  7dd6fe9e128adfde0ca47852dcb3792852245f78
skills.sqlite 5aaa1ae70f26a92aaa8289d1426face69e72a797
```

Expected: all tests pass, compileall emits no errors, SQLite diff is empty, and both blob SHAs are unchanged.

- [ ] **Step 5: Commit the final docs/regressions**

```bash
git add README.md tests/test_real_databases.py
git commit -m "docs: document Food and Registlet search"
```

After this commit, run the full verification commands once more on the exact final head before opening a PR or claiming completion.

---

## Review Checkpoints During Execution

After Tasks 1, 3, 4, 7, and 8, perform a focused code review before continuing. Each checkpoint must confirm:

- the task matches this plan/spec rather than adding unrelated refactors;
- tests demonstrated RED before production changes and GREEN afterward;
- no source-data or SQLite file changed accidentally;
- no UI interaction added an auto-search path;
- route quality remains deterministic and result count is never a routing signal.

## Final Acceptance Matrix

Before completion, map the final test suite to every design requirement:

- Food loader/key/display/alias normalization and duplicate collapse: `tests/test_food_data.py`.
- Food prefix gate, code non-searchability, ordering, suggestions, chip: `tests/test_food_search.py`.
- Registlet source validation: `tests/test_registlet_data.py`.
- Stoodie aliases, exact/fuzzy names, phrase/all-token effects: `tests/test_registlet_search.py`.
- Manual Skill relationships and unknown references: `tests/test_registlet_relationships.py`.
- Four-domain routing/suppression/unavailable-domain behavior: `tests/test_universal_domains.py`.
- Shared `content` quality and new chip/domain types: `tests/test_interpretation.py`.
- Source health: `tests/test_database.py`.
- Five modes, independent limits, fill-only behavior, Help text: `tests/test_app_shell.py` and `tests/test_ui_contract.py`.
- Current committed data and `MAGIC: FINALE` regression: `tests/test_real_databases.py`.

# Food and Registlet Search Domains Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic Food and Registlet search domains, cross-domain Universal routing, Registlet effect search, Skill↔Registlet relationships, autocomplete, help, and UI integration without changing the committed SQLite databases.

**Architecture:** Keep Food and Registlet as small source-backed modules beside the existing Item and Skill modules. Each domain owns loading, validation, parsing, models, and search; `router.py` compares shared `RouteQuality` metadata and suppresses lower-quality outcomes without domain-pair special cases. Streamlit remains a rendering/state layer and searches only after explicit submission.

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

Create:

```text
toram_search/food/__init__.py
toram_search/food/models.py
toram_search/food/data.py
toram_search/food/service.py
toram_search/registlets/__init__.py
toram_search/registlets/models.py
toram_search/registlets/data.py
toram_search/registlets/relationships.py
toram_search/registlets/service.py
ui/food_cards.py
ui/registlet_cards.py
tests/test_food_data.py
tests/test_food_search.py
tests/test_registlet_data.py
tests/test_registlet_search.py
tests/test_registlet_relationships.py
tests/test_autocomplete_domains.py
tests/test_universal_domains.py
```

Modify:

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
tests/test_interpretation.py
tests/test_database.py
tests/test_real_databases.py
tests/test_app_shell.py
tests/test_ui_contract.py
```

---

### Task 1: Generalize shared domain and route-quality models

**Files:**
- Modify: `toram_search/interpretation.py`
- Modify: `toram_search/models.py`
- Test: `tests/test_interpretation.py`

**Interfaces:**
- `SearchDomain = Literal['Items', 'Skills', 'Food', 'Registlets']`
- `RouteFamily = Literal['exact', 'structured', 'content', 'weak', 'none']`
- `ChipKind` adds `food_stat` and `stoodie_level`.
- `DatabaseMode` adds `Food` and `Registlets`.
- `SuggestionKind` adds `Food Stat`, `Registlet`, and `Stoodie Level`.
- `UniversalSearchOutcome` adds optional `food` and `registlets` fields under `TYPE_CHECKING` imports.

- [ ] **Step 1: Write the failing type/quality tests**

Add:

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

- [ ] **Step 2: Confirm RED**

```bash
pytest tests/test_interpretation.py -q
```

Expected: new literals are rejected by the current definitions.

- [ ] **Step 3: Implement minimal shared changes**

Use this `RouteQuality.sort_key` tiering:

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

- [ ] **Step 4: Confirm GREEN**

```bash
pytest tests/test_interpretation.py -q
```

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
- `FoodDataError(ValueError)`
- `load_food_dataset(entries_path: Path, aliases_path: Path) -> FoodDataset`
- `resolve_food_stat(dataset: FoodDataset, value: str) -> FoodStatDefinition | None`

- [ ] **Step 1: Write failing loader tests**

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

Add concrete tests for a row-numbered malformed-row warning, unknown stat rejection, leading-zero code preservation, integer level validation, and malformed alias JSON raising `FoodDataError`.

- [ ] **Step 2: Confirm RED**

```bash
pytest tests/test_food_data.py -q
```

- [ ] **Step 3: Implement exact normalization/validation and source-aware caching**

`normalize_food_text` casefolds, collapses whitespace, removes periods used in abbreviations, and normalizes spacing around `%`, `+`, and `-`; it must preserve the semantic plus/minus sign for Aggro. Build one exact lookup from every key, display label, and alias. CSV rows never use fuzzy or substring stat resolution.

Cache using path plus file identity:

```python
@lru_cache(maxsize=16)
def _cached_load(entries_name: str, entries_mtime: int, entries_size: int,
                 aliases_name: str, aliases_mtime: int, aliases_size: int) -> FoodDataset:
    return _load_uncached(Path(entries_name), Path(aliases_name))
```

`load_food_dataset()` resolves both paths, reads `st_mtime_ns` and `st_size`, then calls `_cached_load`.

- [ ] **Step 4: Confirm GREEN**

```bash
pytest tests/test_food_data.py -q
```

- [ ] **Step 5: Commit**

```bash
git add toram_search/food tests/test_food_data.py
git commit -m "feat: load and validate Food sources"
```

---

### Task 3: Implement prefix-gated Food search and interpretation

**Files:**
- Create: `toram_search/food/service.py`
- Modify: `toram_search/food/models.py`
- Create: `tests/test_food_search.py`

**Interfaces:**
- `FoodSearchOutcome(kind, query, results, message, suggested_queries, interpretation, route_quality)`
- `is_food_intent(query: str) -> bool`
- `FoodSearchService(entries_path: Path, aliases_path: Path)`
- `FoodSearchService.search(query: str) -> FoodSearchOutcome`
- `FoodSearchService.list_autocomplete_values() -> tuple[tuple[str, Literal['Food Stat']], ...]`

- [ ] **Step 1: Write failing Food query tests**

```python
@pytest.mark.parametrize('query', ['food maxmp', 'code max mp'])
def test_food_search_requires_prefix_and_orders_highest_level_first(food_files, query) -> None:
    outcome = FoodSearchService(*food_files).search(query)
    assert outcome.route_quality.family == 'structured'
    assert [row.level for row in outcome.results] == sorted(
        (row.level for row in outcome.results), reverse=True
    )
    assert outcome.interpretation is not None
    assert outcome.interpretation.domain == 'Food'


@pytest.mark.parametrize('query', ['maxmp', 'maxmp food', '51110000'])
def test_food_does_not_activate_without_leading_prefix(food_files, query) -> None:
    outcome = FoodSearchService(*food_files).search(query)
    assert outcome.route_quality.family == 'none'
    assert outcome.results == ()
```

Add direct assertions for `code ampr`, `food dt dark`, `food -aggro`, empty remainder, and unknown-stat suggestions. All suggestions must themselves start with `food ` or `code `.

- [ ] **Step 2: Confirm RED**

```bash
pytest tests/test_food_search.py -q
```

- [ ] **Step 3: Implement first-token parsing and canonical lookup**

Use:

```python
match = re.match(r'^\s*(food|code)(?:\s+|$)(.*)$', query, re.IGNORECASE)
```

No match returns family `none`. Recognized prefix plus missing/unknown stat returns family `structured`, no results, Food-specific guidance, and no weak fallback. Valid stats sort by `(-level, code)` and emit:

```python
QueryChip(
    id='food_stat',
    kind='food_stat',
    label=f'Food: {stat.display}',
    canonical_fragment=f'food {stat.display}',
    query_without='',
)
```

Nearby unknown-stat suggestions may use full-string `fuzz.ratio` over normalized alias/display values only; return at most three unique prefixed canonical suggestions and never turn those suggestions into result matches.

- [ ] **Step 4: Confirm GREEN**

```bash
pytest tests/test_food_data.py tests/test_food_search.py -q
```

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
- `RegistletRecord(name: str, max_lv: int, effect: str, affects_skill: tuple[str, ...] | None, source: str, location: str, source_levels: tuple[int, ...])`
- `RegistletDataset(records: tuple[RegistletRecord, ...], valid_stoodie_levels: tuple[int, ...], warnings: tuple[str, ...])`
- `RegistletDataError(ValueError)`
- `load_registlet_dataset(path: Path) -> RegistletDataset`
- `is_stoodie_intent(query: str) -> bool`
- `RegistletSearchOutcome(kind, query, results, message, suggested_queries, interpretation, route_quality)`
- `RegistletSearchService(path: Path).search(query: str) -> RegistletSearchOutcome`
- `RegistletSearchService.list_autocomplete_values() -> tuple[tuple[str, Literal['Registlet']], ...]`

- [ ] **Step 1: Write failing loader/search tests**

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

The fixture must include one phrase match, one all-token-only match, and one Registlet whose name has a typo-recoverable variant. Add assertions for phrase-before-token ordering, case-insensitive exact names, fuzzy name recovery, invalid `std 200` nearest-level suggestions, malformed record warnings, malformed top-level JSON errors, and proof that `level_notation` is never reparsed.

- [ ] **Step 2: Confirm RED**

```bash
pytest tests/test_registlet_data.py tests/test_registlet_search.py -q
```

- [ ] **Step 3: Implement deterministic search**

Stoodie accepts one integer only. Effect normalization casefolds, replaces punctuation with spaces, and collapses whitespace. Search effect phrase first, then whole tokens:

```python
phrase_hits = [record for record in records if normalized_query in normalize_effect(record.effect)]
if phrase_hits:
    return tuple(sorted(phrase_hits, key=lambda record: record.name.casefold()))

query_tokens = set(normalized_query.split())
token_hits = []
for record in records:
    effect_tokens = set(normalize_effect(record.effect).split())
    if query_tokens and query_tokens <= effect_tokens:
        token_hits.append(record)
return tuple(sorted(token_hits, key=lambda record: record.name.casefold()))
```

Only after Stoodie, exact name, and effect content return no result may RapidFuzz run against normalized Registlet names. Never run RapidFuzz on `effect`.

- [ ] **Step 4: Confirm GREEN**

```bash
pytest tests/test_registlet_data.py tests/test_registlet_search.py -q
```

- [ ] **Step 5: Commit**

```bash
git add toram_search/registlets tests/test_registlet_data.py tests/test_registlet_search.py
git commit -m "feat: add deterministic Registlet search"
```

---

### Task 5: Build manual Skill↔Registlet relationships

**Files:**
- Create: `toram_search/registlets/relationships.py`
- Modify: `toram_search/skills/models.py`
- Create: `tests/test_registlet_relationships.py`

**Interfaces:**
- `RegistletRelationshipIndex(by_skill: dict[str, tuple[str, ...]], warnings: tuple[str, ...])`
- `build_relationship_index(records: tuple[RegistletRecord, ...], canonical_skill_names: tuple[str, ...]) -> RegistletRelationshipIndex`
- `SkillCardResult.related_registlets: tuple[str, ...] = ()`

- [ ] **Step 1: Write failing relationship tests**

Define this helper in the test file:

```python
def make_registlet(name: str, affects_skill: tuple[str, ...] | None) -> RegistletRecord:
    return RegistletRecord(
        name=name,
        max_lv=1,
        effect='Effect mentions Arrow Rain but must not create a relation.',
        affects_skill=affects_skill,
        source='Stoodie',
        location='El Scaro',
        source_levels=(220,),
    )
```

Then test:

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
    assert 'none' not in index.by_skill
    assert any('Missing Skill' in warning for warning in index.warnings)
```

- [ ] **Step 2: Confirm RED**

```bash
pytest tests/test_registlet_relationships.py -q
```

- [ ] **Step 3: Implement exact canonical-name relation validation**

Build `{name.casefold(): name}` from canonical Skill names. Unknown references produce warnings and are skipped as edges; the Registlet record remains searchable. Do not fuzzy-correct relationship names and do not inspect effect text.

- [ ] **Step 4: Confirm GREEN and Skill regression**

```bash
pytest tests/test_registlet_relationships.py tests/test_skill_search.py -q
```

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
- Add root constants `FOOD_ENTRIES`, `FOOD_ALIASES`, `REGISTLET_DATA`.
- `validate_food_sources(entries_path: Path = FOOD_ENTRIES, aliases_path: Path = FOOD_ALIASES) -> DatabaseHealth`
- `validate_registlet_source(path: Path = REGISTLET_DATA) -> DatabaseHealth`
- `validate_sources(...) -> tuple[DatabaseHealth, DatabaseHealth, DatabaseHealth, DatabaseHealth]` in Items, Skills, Food, Registlets order.
- Extend `build_autocomplete_index(mode, *, items_path, skills_path, food_entries_path, food_aliases_path, registlets_path, available_domains=None)`.

- [ ] **Step 1: Write failing health/autocomplete tests**

Assert malformed top-level Food aliases make Food unhealthy, malformed top-level Registlet JSON makes Registlets unhealthy, and valid files with skipped-row warnings remain healthy. Autocomplete must satisfy:

```python
assert any(row.kind == 'Food Stat' and row.value == 'food MaxMP' for row in suggestions)
assert not any(row.kind == 'Food Stat' and row.value == 'MaxMP' for row in suggestions)
assert any(row.kind == 'Registlet' and row.value == 'Arrow Rain Enhancer' for row in suggestions)
```

If Stoodie suggestions are included, generate them from `dataset.valid_stoodie_levels` as values such as `std 220` with kind `Stoodie Level`; never hard-code a second valid-level list.

- [ ] **Step 2: Confirm RED**

```bash
pytest tests/test_database.py tests/test_autocomplete_domains.py -q
```

- [ ] **Step 3: Implement validators and mode filtering**

Reuse the domain loaders inside validation so health and production loading cannot disagree. In Universal, autocomplete includes only available domains. Dedicated modes return only their domain's kinds. Existing Item/Skill ordering/deduplication behavior remains intact.

- [ ] **Step 4: Confirm GREEN**

```bash
pytest tests/test_database.py tests/test_autocomplete_domains.py -q
```

- [ ] **Step 5: Commit**

```bash
git add toram_search/database.py toram_search/autocomplete.py tests/test_database.py tests/test_autocomplete_domains.py
git commit -m "feat: add Food and Registlet source health"
```

---

### Task 7: Replace pairwise Universal suppression with four-domain quality comparison

**Files:**
- Modify: `toram_search/router.py`
- Modify: `toram_search/skills/models.py`
- Create: `tests/test_universal_domains.py`
- Modify: `tests/test_real_databases.py`

**Interfaces:**
- `select_surviving_domains(qualities: dict[SearchDomain, RouteQuality]) -> frozenset[SearchDomain]`
- `select_winning_interpretation(*outcomes) -> QueryInterpretation | None`
- Extend `search_database(mode, query, *, items_path, skills_path, food_entries_path, food_aliases_path, registlets_path, available_domains=None)`.
- `available_domains: frozenset[SearchDomain] | None`; `None` means all four sources are expected to be available.
- When Skills and Registlets are both available, enrich returned Skill cards with `related_registlets` from `build_relationship_index()`.

- [ ] **Step 1: Write failing pure route-comparison tests**

```python
def test_exact_route_suppresses_content_and_weak() -> None:
    survivors = select_surviving_domains({
        'Skills': RouteQuality('exact', True, 1),
        'Registlets': RouteQuality('content', True, 99),
        'Items': RouteQuality('weak', True, 99),
    })
    assert survivors == frozenset({'Skills'})


def test_structured_no_result_suppresses_content_result() -> None:
    survivors = select_surviving_domains({
        'Food': RouteQuality('structured', False, 1),
        'Registlets': RouteQuality('content', True, 9),
    })
    assert survivors == frozenset({'Food'})


def test_equal_quality_routes_can_coexist() -> None:
    survivors = select_surviving_domains({
        'Items': RouteQuality('structured', True, 2),
        'Skills': RouteQuality('structured', True, 2),
    })
    assert survivors == frozenset({'Items', 'Skills'})


def test_result_count_is_not_part_of_route_selection() -> None:
    survivors = select_surviving_domains({
        'Skills': RouteQuality('exact', True, 1),
        'Registlets': RouteQuality('content', True, 500),
    })
    assert survivors == frozenset({'Skills'})
```

Also add integration tests using temporary Food/Registlet files plus existing test DB factories for `food maxmp`, `std 220`, `restores mp`, and bare `maxmp`. Assert bare `maxmp` leaves `outcome.food` absent or with no Food results.

- [ ] **Step 2: Confirm RED**

```bash
pytest tests/test_universal_domains.py tests/test_real_databases.py -q
```

- [ ] **Step 3: Implement generic route selection and suppression**

The pure selector is:

```python
def select_surviving_domains(qualities: dict[SearchDomain, RouteQuality]) -> frozenset[SearchDomain]:
    if not qualities:
        return frozenset()
    best = max(quality.sort_key for quality in qualities.values())
    return frozenset(domain for domain, quality in qualities.items() if quality.sort_key == best)
```

Evaluate all available domain services, compare only `RouteQuality`, and suppress lower-quality outcomes with one per-outcome replacement helper so required domain-specific fields remain valid. Do not add Item-vs-Skill, Skill-vs-Registlet, or other pair-specific branches.

If Food is unavailable and `is_food_intent(query)` is true, or Registlets are unavailable and `is_stoodie_intent(query)` is true, return no weak unrelated results; the UI source-health warning supplies the domain error.

For Skill enrichment, obtain canonical Skill names through `SkillRepository.list_skill_names()`, build the relationship index from the loaded Registlets, and use `dataclasses.replace(card, related_registlets=index.by_skill.get(card.skill.name.casefold(), ()))`.

- [ ] **Step 4: Confirm GREEN across routing and existing search**

```bash
pytest tests/test_universal_domains.py tests/test_real_databases.py tests/test_item_search.py tests/test_skill_search.py -q
```

- [ ] **Step 5: Commit**

```bash
git add toram_search/router.py toram_search/skills/models.py tests/test_universal_domains.py tests/test_real_databases.py
git commit -m "refactor: generalize Universal domain routing"
```

---

### Task 8: Render new domains, Skill relations, modes, Search Help, and app state

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
- `render_food_results(outcome: FoodSearchOutcome, *, limit: int) -> str | None`
- `render_registlet_results(outcome: RegistletSearchOutcome, *, limit: int) -> str | None`
- Session state adds `food_limit=20` and `registlet_limit=20`.
- Sidebar modes are exactly `Universal`, `Items`, `Skills`, `Food`, `Registlets`.

- [ ] **Step 1: Write failing UI/state/help tests**

Add:

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

Extend AppTest coverage to assert the radio contains five modes, clicking `food maxmp` only changes `session_state['query']`, chip removal resets all four limits, and `last_submission_nonce` is unchanged by fill-only interactions. Add a Skill-dialog contract asserting `Related Registlets` is rendered when the tuple is non-empty.

- [ ] **Step 2: Confirm RED**

```bash
pytest tests/test_app_shell.py tests/test_ui_contract.py -q
```

- [ ] **Step 3: Implement UI wiring without adding an auto-search path**

Food cards group already-sorted visible entries by level and list codes. Registlet cards show name, max level, effect, Stoodie source levels, and explicit affected Skills. Skill dialog adds:

```python
if card.related_registlets:
    st.markdown('#### Related Registlets')
    for name in card.related_registlets:
        st.write(name)
```

In `main.py`, initialize all limits together:

```python
for key, value in {
    'query': '', 'last_submission_nonce': None, 'last_outcome': None,
    'last_mode': 'Universal', 'item_limit': 20, 'skill_limit': 20,
    'food_limit': 20, 'registlet_limit': 20,
}.items():
    if key not in st.session_state:
        st.session_state[key] = value
```

On every mode change, example fill, correction fill, chip removal, or new explicit submission, assign all four limits back to `20`. Keep the current `query_to_run` rule unchanged: only a new `SearchSubmission.nonce` assigns `query_to_run`.

Dedicated modes require their own health. Universal remains searchable when at least one domain is healthy and renders warnings for each unavailable domain. Pass `available_domains` to both router and autocomplete.

Search Help must explicitly state:

```text
Food Code Search
Start the query with "food" or "code", followed by a Food stat.
food maxmp
code ampr
food critical rate
food dt fire
food -aggro
Code values themselves are not searchable.

Registlet Search
Search by Stoodie level: std 220, stoodie lvl 220
Search by Registlet name: Arrow Rain Enhancer
Search by effect: restores mp, physical pierce, inflicts stun
```

Also explain that Registlet effect matches are weaker than exact/structured matches in Universal.

- [ ] **Step 4: Confirm GREEN**

```bash
pytest tests/test_app_shell.py tests/test_ui_contract.py tests/test_food_search.py tests/test_registlet_search.py -q
```

- [ ] **Step 5: Commit**

```bash
git add ui main.py tests/test_app_shell.py tests/test_ui_contract.py
git commit -m "feat: integrate Food and Registlet UI"
```

---

### Task 9: Validate committed data, update README, and run full verification

**Files:**
- Modify: `README.md`
- Modify: `tests/test_real_databases.py`
- Do not modify: `items.sqlite`, `skills.sqlite`, `food_entries.csv`, `food_stat_aliases.json`, `registlets.json` unless a validation failure proves a source-data defect and that defect is discussed separately.

**Interfaces:**
- README documents all four searchable domains plus five UI modes, exact Food prefix syntax, Registlet search routes, source files, and deterministic/no-LLM behavior.
- Real-data tests exercise the committed Food/Registlet files as well as the existing SQLite regressions.

- [ ] **Step 1: Add real-source acceptance tests**

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

Add a real Universal test asserting `food maxmp` has Food results and no surviving weak unrelated results. Add a bare `maxmp` assertion that Food does not participate. Keep the existing `MAGIC: FINALE` exact-Skill regression.

- [ ] **Step 2: Run real-source tests before docs**

```bash
pytest tests/test_real_databases.py -q
```

If a failure identifies malformed user-maintained Food/Registlet data, report the exact row/record warning and do not silently repair source data as part of search code.

- [ ] **Step 3: Update README**

Document these examples verbatim:

```text
food maxmp
code ampr
std 220
Arrow Rain Enhancer
restores mp
```

State that raw Food codes are not searchable and Registlet effect search is deterministic text matching, not semantic/AI search.

- [ ] **Step 4: Run complete verification on the final head**

```bash
pytest -q
python -m compileall -q main.py toram_search ui
git diff --exit-code -- items.sqlite skills.sqlite
```

Confirm GitHub blob SHAs remain:

```text
items.sqlite  7dd6fe9e128adfde0ca47852dcb3792852245f78
skills.sqlite 5aaa1ae70f26a92aaa8289d1426face69e72a797
```

Expected: full pytest pass, no compile errors, empty SQLite diff, unchanged SQLite blob SHAs.

- [ ] **Step 5: Commit docs/regressions, then verify once more**

```bash
git add README.md tests/test_real_databases.py
git commit -m "docs: document Food and Registlet search"
pytest -q
python -m compileall -q main.py toram_search ui
```

---

## Review Checkpoints

After Tasks 1, 3, 4, 7, and 8, review the task before continuing. Confirm the committed diff matches the task, RED was observed before implementation, focused tests are GREEN, source/SQLite data did not change accidentally, fill-only UI paths remain non-submitting, and route selection never uses result count.

## Final Acceptance Matrix

- Food loading, aliases, validation, duplicate collapse: `tests/test_food_data.py`.
- Food prefix gate, code non-searchability, ordering, suggestions, chip: `tests/test_food_search.py`.
- Registlet source validation: `tests/test_registlet_data.py`.
- Stoodie aliases, exact/fuzzy names, phrase/all-token effects: `tests/test_registlet_search.py`.
- Manual Skill relationships and unknown references: `tests/test_registlet_relationships.py`.
- Four-domain routing/suppression/unavailable-domain behavior: `tests/test_universal_domains.py`.
- Shared `content` quality and new chip/domain types: `tests/test_interpretation.py`.
- Source health: `tests/test_database.py`.
- Five modes, four independent limits, fill-only behavior, Search Help: `tests/test_app_shell.py`, `tests/test_ui_contract.py`.
- Current committed data and `MAGIC: FINALE` regression: `tests/test_real_databases.py`.

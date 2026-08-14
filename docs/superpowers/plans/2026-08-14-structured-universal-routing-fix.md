# Structured Universal Routing Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make structured item queries such as `aggro xtal wp` resolve deterministically to the intended item filter and prevent unrelated fuzzy/FTS skill results from appearing in Universal mode.

**Architecture:** Keep item and skill parsing independent, but add an explicit `routing_confidence` field to item outcomes so the Universal router can decide whether weak skill fallback is allowed without inspecting messages or result counts. Improve item filter phrase precedence so specific crysta-slot combinations are consumed before generic `xtal`/`wp`, and stop item-name fuzzy fallback once structured intent has been recognized but not safely parsed.

**Tech Stack:** Python 3.12, SQLite, RapidFuzz, pytest, Streamlit 1.61.x.

## Global Constraints

- No LLM, embeddings, semantic search, or external runtime service.
- Do not change `items.sqlite` or `skills.sqlite` schemas.
- Exact item-name matching must remain ahead of structured item parsing.
- Skills-only mode must retain fuzzy-name and FTS lexical fallback.
- Universal mode may suppress only weak skill fallback when the item outcome has strong routing confidence.
- Existing exact/structured cross-domain matches must remain available.
- Keep the fix focused; do not add query chips, compare UI, result filters, or unrelated performance refactors.

---

## File Structure

- `toram_search/items/models.py` — add the explicit routing-confidence type/field carried by `ItemSearchOutcome`.
- `toram_search/items/filters.py` — resolve specific crysta-slot phrases in either word order before generic item-type aliases.
- `toram_search/items/service.py` — mark item outcomes with routing confidence and block fuzzy item-name fallback after recognized structured intent.
- `toram_search/skills/service.py` — add a public search policy parameter that disables fuzzy/FTS fallback while preserving exact and structured routes.
- `toram_search/router.py` — use item routing confidence to decide whether Universal skill search may use weak fallback.
- `tests/item_db_factory.py` — add representative Weapon Crysta data needed for deterministic regression coverage.
- `tests/test_item_search.py` — cover crysta-slot alias precedence, routing confidence, and no structured-to-fuzzy degradation.
- `tests/test_skill_search.py` — cover strict skill search and Skills-only fallback preservation.
- `tests/test_universal.py` — cover the exact `aggro xtal wp` production bug and cross-domain routing behavior.

---

### Task 1: Add explicit item routing confidence

**Files:**
- Modify: `toram_search/items/models.py`
- Modify: `toram_search/items/service.py`
- Test: `tests/test_item_search.py`

**Interfaces:**
- Produces: `RoutingConfidence = Literal['strong', 'weak', 'none']`.
- Produces: `ItemSearchOutcome.routing_confidence: RoutingConfidence = 'none'`.
- Strong outcomes include exact item matches, recognized stat/item-filter/expression/rank intent, deterministic clarifications/suggestions produced from recognized item syntax, and item help/meta/refusal routes.
- Weak outcomes are fuzzy item-name matches only.
- None covers empty/not-found input with no recognized item intent.

- [ ] **Step 1: Write failing routing-confidence tests**

Add tests that assert exact/structured item intent is `strong`, fuzzy name matching is `weak`, and a fully unknown query is `none`:

```python
from toram_search.items.service import ItemSearchService


def test_item_routing_confidence_distinguishes_strong_weak_and_none(tmp_path: Path) -> None:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    service = ItemSearchService(path)
    try:
        assert service.search('Test Bow').routing_confidence == 'strong'
        assert service.search('critical rate bow').routing_confidence == 'strong'
        assert service.search('Test Bo').routing_confidence == 'weak'
        assert service.search('totally unrelated words').routing_confidence == 'none'
    finally:
        service.close()
```

- [ ] **Step 2: Run the new test and verify RED**

Run:

```bash
python -m pytest -q tests/test_item_search.py::test_item_routing_confidence_distinguishes_strong_weak_and_none
```

Expected: FAIL because `ItemSearchOutcome` has no `routing_confidence` field.

- [ ] **Step 3: Add the model field**

In `toram_search/items/models.py` add:

```python
RoutingConfidence = Literal['strong', 'weak', 'none']

@dataclass(frozen=True)
class ItemSearchOutcome:
    kind: ItemOutcomeKind
    query: str
    results: tuple[ItemCardResult, ...] = ()
    message: str | None = None
    suggested_queries: tuple[str, ...] = ()
    routing_confidence: RoutingConfidence = 'none'
```

- [ ] **Step 4: Mark service return paths explicitly**

Update `ItemSearchService.search()` return paths so:

```python
# examples of strong intent
ItemSearchOutcome('results', raw, results, routing_confidence='strong')
ItemSearchOutcome('clarify', raw, message=..., suggested_queries=..., routing_confidence='strong')
ItemSearchOutcome('suggest', raw, message=..., suggested_queries=..., routing_confidence='strong')
ItemSearchOutcome('help', raw, message=_HELP, routing_confidence='strong')
ItemSearchOutcome('meta', raw, message=..., routing_confidence='strong')
ItemSearchOutcome('refuse', raw, message=..., routing_confidence='strong')

# fuzzy item-name fallback only
ItemSearchOutcome('results', raw, fuzzy_cards, routing_confidence='weak')

# no recognized intent
ItemSearchOutcome('not_found', raw, message='No matching item or stat found.', routing_confidence='none')
```

Exact item-name results must be `strong` even though they are not stat-filter queries.

- [ ] **Step 5: Run the targeted test and related item tests**

Run:

```bash
python -m pytest -q tests/test_item_search.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add toram_search/items/models.py toram_search/items/service.py tests/test_item_search.py
git commit -m "fix: expose item routing confidence"
```

---

### Task 2: Parse order-insensitive crysta-slot filters and prevent structured fuzzy degradation

**Files:**
- Modify: `tests/item_db_factory.py`
- Modify: `toram_search/items/filters.py`
- Modify: `toram_search/items/service.py`
- Test: `tests/test_item_search.py`

**Interfaces:**
- Existing `extract_item_filter(text, available_item_types)` remains the public filter API.
- Specific multi-token crysta-slot aliases must win over generic `xtal`, `weapon`, and `wp` aliases.
- `aggro xtal wp`, `aggro wp xtal`, and `aggro weapon xtal` must all leave only `aggro` as the stat text and resolve to Weapon Crysta types.

- [ ] **Step 1: Add representative Weapon Crysta fixtures**

Extend `tests/item_db_factory.py` with two items and stats:

```python
(7, 1, 'Aggro Weapon Crystal', 'Weapon Crysta', 100, None, None, None, None, None, 'https://example.com/weapon-crysta', ''),
(8, 1, 'Unrelated Dagger', 'Dagger', 100, None, None, None, None, None, 'https://example.com/dagger', ''),
```

and:

```python
(8, 7, 0, 'Aggro %', 15, '[]', None, None, 0),
(9, 8, 0, 'Critical Rate', 1, '[]', None, None, 0),
```

Keep IDs unique relative to the existing fixture rows.

- [ ] **Step 2: Write failing alias-precedence tests**

Add:

```python
from toram_search.items.filters import extract_item_filter


def test_specific_crysta_slot_aliases_are_order_insensitive(tmp_path: Path) -> None:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    service = ItemSearchService(path)
    try:
        available = service.repository.list_item_types()
        for query in ('aggro xtal wp', 'aggro wp xtal', 'aggro weapon xtal'):
            item_filter, remaining = extract_item_filter(query, available)
            assert item_filter is not None
            assert item_filter.label == 'Weapon Crysta'
            assert set(item_filter.item_types) == {'Weapon Crysta'}
            assert remaining == 'aggro'
    finally:
        service.close()
```

Also add direct search regression:

```python
def test_aggro_xtal_wp_returns_weapon_crysta_not_fuzzy_item(tmp_path: Path) -> None:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    service = ItemSearchService(path)
    try:
        outcome = service.search('aggro xtal wp')
        assert outcome.routing_confidence == 'strong'
        assert [row.item.name for row in outcome.results] == ['Aggro Weapon Crystal']
        assert all(row.item.item_type == 'Weapon Crysta' for row in outcome.results)
    finally:
        service.close()
```

- [ ] **Step 3: Run the new item regressions and verify RED**

Run:

```bash
python -m pytest -q \
  tests/test_item_search.py::test_specific_crysta_slot_aliases_are_order_insensitive \
  tests/test_item_search.py::test_aggro_xtal_wp_returns_weapon_crysta_not_fuzzy_item
```

Expected: FAIL because `xtal wp` is currently split by generic aliases.

- [ ] **Step 4: Add explicit specific aliases before generic aliases**

In `toram_search/items/filters.py`, extend the `special` mapping so all supported orderings are first-class candidate phrases:

```python
special = {
    'weapon xtal': ('Weapon Crysta', ('Weapon Crysta', 'Enhancer Crysta (Red)')),
    'wp xtal': ('Weapon Crysta', ('Weapon Crysta', 'Enhancer Crysta (Red)')),
    'xtal weapon': ('Weapon Crysta', ('Weapon Crysta', 'Enhancer Crysta (Red)')),
    'xtal wp': ('Weapon Crysta', ('Weapon Crysta', 'Enhancer Crysta (Red)')),
    'armor xtal': ('Armor Crysta', ('Armor Crysta', 'Enhancer Crysta (Green)')),
    'arm xtal': ('Armor Crysta', ('Armor Crysta', 'Enhancer Crysta (Green)')),
    'xtal armor': ('Armor Crysta', ('Armor Crysta', 'Enhancer Crysta (Green)')),
    'xtal arm': ('Armor Crysta', ('Armor Crysta', 'Enhancer Crysta (Green)')),
    'additional xtal': ('Additional Crysta', ('Additional Crysta', 'Enhancer Crysta (Yellow)')),
    'add xtal': ('Additional Crysta', ('Additional Crysta', 'Enhancer Crysta (Yellow)')),
    'xtal additional': ('Additional Crysta', ('Additional Crysta', 'Enhancer Crysta (Yellow)')),
    'xtal add': ('Additional Crysta', ('Additional Crysta', 'Enhancer Crysta (Yellow)')),
    'ring xtal': ('Special Crysta', ('Special Crysta', 'Enhancer Crysta (Purple)')),
    'special xtal': ('Special Crysta', ('Special Crysta', 'Enhancer Crysta (Purple)')),
    'xtal ring': ('Special Crysta', ('Special Crysta', 'Enhancer Crysta (Purple)')),
    'xtal special': ('Special Crysta', ('Special Crysta', 'Enhancer Crysta (Purple)')),
    'xtal': ('All Crysta', ALL_CRYSTA_TYPES),
    'crysta': ('All Crysta', ALL_CRYSTA_TYPES),
    'crystal': ('All Crysta', ALL_CRYSTA_TYPES),
    'weapon': ('Main Weapons', MAIN_WEAPON_TYPES),
    'wp': ('Main Weapons', MAIN_WEAPON_TYPES),
}
```

Keep `_candidates()` sorting longest phrases first so the two-token specific aliases beat one-token generic aliases.

- [ ] **Step 5: Write a failing structured-leftover regression**

Add a test that proves recognized structured intent cannot fall back to a fuzzy item name:

```python
def test_structured_item_intent_with_unknown_leftover_does_not_fuzzy_match(tmp_path: Path) -> None:
    path = tmp_path / 'items.sqlite'
    create_item_database(path)
    service = ItemSearchService(path)
    try:
        outcome = service.search('aggro xtal nonsense')
        assert outcome.routing_confidence == 'strong'
        assert outcome.kind in {'suggest', 'not_found'}
        assert not outcome.results
    finally:
        service.close()
```

- [ ] **Step 6: Run the leftover regression and verify RED**

Run:

```bash
python -m pytest -q tests/test_item_search.py::test_structured_item_intent_with_unknown_leftover_does_not_fuzzy_match
```

Expected: FAIL if the service still reaches `repository.fuzzy_items(raw)` after recognizing the item filter.

- [ ] **Step 7: Block fuzzy fallback after structured intent**

In `ItemSearchService.search()`, compute a deterministic flag after item-filter/rank/expression detection:

```python
recognized_structured_intent = bool(
    item_filter is not None
    or rank_direction is not None
    or looks_expression
    or any(alias in tokens for alias in STAT_ALIASES)
    or any(alias.split() and all(t in tokens for t in alias.split()) for alias in ('crit', 'crt'))
)
```

Use the already-resolved `stat`, `choices`, `stat_hits`, `item_filter`, and expression flags rather than introducing fuzzy heuristics. Immediately before the final `repository.fuzzy_items(raw)` fallback:

```python
if recognized_structured_intent:
    return ItemSearchOutcome(
        'suggest',
        raw,
        message=f'I could not safely parse "{raw}".',
        routing_confidence='strong',
    )
```

If implementation can express `recognized_structured_intent` more directly from existing parsed values, prefer that over rescanning raw text.

- [ ] **Step 8: Run all item tests**

Run:

```bash
python -m pytest -q tests/test_item_search.py
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add tests/item_db_factory.py tests/test_item_search.py toram_search/items/filters.py toram_search/items/service.py
git commit -m "fix: parse structured crysta slot queries"
```

---

### Task 3: Add strict skill search without weak fuzzy/FTS fallback

**Files:**
- Modify: `toram_search/skills/service.py`
- Test: `tests/test_skill_search.py`

**Interfaces:**
- Change public method to `SkillSearchService.search(query: str, *, allow_weak_fallback: bool = True) -> SkillSearchOutcome`.
- All exact, compare, tree, structured filter, ailment, MP-ranking, and exact skill-name routes execute regardless of `allow_weak_fallback`.
- Only fuzzy skill-name matching and `lexical_search(...)` are skipped when `allow_weak_fallback=False`.

- [ ] **Step 1: Write failing strict-mode tests**

Add tests:

```python
def test_skill_search_can_disable_weak_fallback(tmp_path: Path) -> None:
    path = tmp_path / 'skills.sqlite'
    create_skill_database(path)
    service = SkillSearchService(path)
    try:
        weak = service.search('protect party aura')
        strict = service.search('protect party aura', allow_weak_fallback=False)
        assert weak.results
        assert strict.kind == 'not_found'
        assert not strict.results
    finally:
        service.close()


def test_strict_skill_search_keeps_exact_and_structured_routes(tmp_path: Path) -> None:
    path = tmp_path / 'skills.sqlite'
    create_skill_database(path)
    service = SkillSearchService(path)
    try:
        exact = service.search('Guardian', allow_weak_fallback=False)
        ailment = service.search('skills that inflict stun', allow_weak_fallback=False)
        assert [row.skill.name for row in exact.results] == ['Guardian']
        assert [row.skill.name for row in ailment.results] == ['Shield Bash']
    finally:
        service.close()
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
python -m pytest -q \
  tests/test_skill_search.py::test_skill_search_can_disable_weak_fallback \
  tests/test_skill_search.py::test_strict_skill_search_keeps_exact_and_structured_routes
```

Expected: FAIL because `allow_weak_fallback` is not accepted.

- [ ] **Step 3: Add the search policy parameter**

Change the signature:

```python
def search(self, query: str, *, allow_weak_fallback: bool = True) -> SkillSearchOutcome:
```

After all strong routes and `resolve_skill_name(raw)`, gate only the weak section:

```python
if not allow_weak_fallback:
    return SkillSearchOutcome('not_found', raw, message='No matching skill database information found.')

fuzzy = []
# existing RapidFuzz block unchanged
...
hits = lexical_search(self.repository, raw, limit=20)
# existing lexical block unchanged
```

- [ ] **Step 4: Run all skill tests**

Run:

```bash
python -m pytest -q tests/test_skill_search.py
```

Expected: PASS, proving the default remains backward-compatible.

- [ ] **Step 5: Commit**

```bash
git add toram_search/skills/service.py tests/test_skill_search.py
git commit -m "fix: support strict skill routing"
```

---

### Task 4: Route Universal searches using item confidence

**Files:**
- Modify: `toram_search/router.py`
- Modify: `tests/test_universal.py`

**Interfaces:**
- `_search_skills(query, path, *, allow_weak_fallback=True)` forwards the policy to `SkillSearchService.search()`.
- Universal mode searches items first, then calls skills with `allow_weak_fallback = items.routing_confidence != 'strong'`.
- Items-only and Skills-only behavior remains unchanged.

- [ ] **Step 1: Write the exact production regression**

Add:

```python
def test_universal_aggro_xtal_wp_returns_weapon_crysta_without_unrelated_skills(tmp_path: Path) -> None:
    items, skills = databases(tmp_path)
    outcome = search_database('Universal', 'aggro xtal wp', items_path=items, skills_path=skills)
    assert outcome.items is not None
    assert outcome.items.routing_confidence == 'strong'
    assert [row.item.name for row in outcome.items.results] == ['Aggro Weapon Crystal']
    assert outcome.skills is not None
    assert outcome.skills.kind == 'not_found'
    assert not outcome.skills.results
```

Add equivalent word-order coverage:

```python
def test_universal_aggro_wp_xtal_matches_same_weapon_crysta(tmp_path: Path) -> None:
    items, skills = databases(tmp_path)
    a = search_database('Universal', 'aggro xtal wp', items_path=items, skills_path=skills)
    b = search_database('Universal', 'aggro wp xtal', items_path=items, skills_path=skills)
    assert [row.item.id for row in a.items.results] == [row.item.id for row in b.items.results]
    assert not a.skills.results
    assert not b.skills.results
```

- [ ] **Step 2: Write cross-domain preservation tests**

Add:

```python
def test_universal_strong_item_intent_suppresses_only_weak_skill_fallback(tmp_path: Path) -> None:
    items, skills = databases(tmp_path)
    outcome = search_database('Universal', 'critical rate bow', items_path=items, skills_path=skills)
    assert outcome.items is not None and outcome.items.results
    assert outcome.skills is not None
    assert not outcome.skills.results


def test_universal_exact_skill_match_survives_strict_skill_policy(tmp_path: Path) -> None:
    items, skills = databases(tmp_path)
    outcome = search_database('Universal', 'Guardian', items_path=items, skills_path=skills)
    assert outcome.skills is not None
    assert [row.skill.name for row in outcome.skills.results] == ['Guardian']
```

- [ ] **Step 3: Run Universal regressions and verify RED**

Run:

```bash
python -m pytest -q tests/test_universal.py
```

Expected: FAIL because Universal currently always gives skill search full weak fallback.

- [ ] **Step 4: Implement confidence-aware routing**

Update helper:

```python
def _search_skills(query: str, path: Path, *, allow_weak_fallback: bool = True):
    service = SkillSearchService(path)
    try:
        return service.search(query, allow_weak_fallback=allow_weak_fallback)
    finally:
        service.close()
```

Update `search_database()` so Universal is intentionally ordered:

```python
if mode == 'Universal':
    items = _search_items(query, items_path)
    skills = _search_skills(
        query,
        skills_path,
        allow_weak_fallback=items.routing_confidence != 'strong',
    )
    return UniversalSearchOutcome(query=query, items=items, skills=skills)

if mode == 'Items':
    return UniversalSearchOutcome(query=query, items=_search_items(query, items_path), skills=None)

return UniversalSearchOutcome(query=query, items=None, skills=_search_skills(query, skills_path))
```

- [ ] **Step 5: Run Universal, item, and skill suites together**

Run:

```bash
python -m pytest -q tests/test_item_search.py tests/test_skill_search.py tests/test_universal.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add toram_search/router.py tests/test_universal.py
git commit -m "fix: suppress weak cross-domain skill matches"
```

---

### Task 5: Full regression verification

**Files:**
- No production changes expected.
- Modify tests only if a failing test reveals a real uncovered compatibility requirement; do not weaken the new regressions.

**Interfaces:**
- Final behavior must satisfy all Global Constraints and all four earlier task contracts.

- [ ] **Step 1: Run the complete test suite**

```bash
python -m pytest -q
```

Expected: all tests pass, including the exact `aggro xtal wp` regression.

- [ ] **Step 2: Compile application Python sources**

```bash
python -m compileall -q main.py toram_search ui
```

Expected: exit code 0.

- [ ] **Step 3: Verify database files are unchanged**

Compare the feature branch against its base and confirm `items.sqlite` and `skills.sqlite` are absent from the changed-file list.

- [ ] **Step 4: Verify scope**

Expected changed production paths are limited to:

```text
toram_search/items/models.py
toram_search/items/filters.py
toram_search/items/service.py
toram_search/skills/service.py
toram_search/router.py
```

plus the test fixture/tests and approved spec/plan documents.

- [ ] **Step 5: Commit any final test-only cleanup if required**

If no cleanup is required, do not create an empty commit. If test-only cleanup is required:

```bash
git add tests/
git commit -m "test: finalize structured routing regressions"
```

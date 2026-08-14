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

- `toram_search/items/models.py` — add explicit routing confidence to `ItemSearchOutcome`.
- `toram_search/items/filters.py` — resolve specific crysta-slot phrases in either word order before generic aliases.
- `toram_search/items/service.py` — mark routing confidence and prevent structured queries from degrading into fuzzy item-name search.
- `toram_search/skills/service.py` — allow callers to disable only fuzzy/FTS fallback.
- `toram_search/router.py` — apply strict skill routing in Universal mode when item confidence is strong.
- `tests/item_db_factory.py` — add representative Weapon Crysta and unrelated Dagger fixtures.
- `tests/test_item_search.py` — cover confidence, alias precedence, and no fuzzy degradation.
- `tests/test_skill_search.py` — cover strict skill routing while preserving strong routes.
- `tests/test_universal.py` — cover the production regression and cross-domain behavior.

---

### Task 1: Add explicit item routing confidence

**Files:**
- Modify: `toram_search/items/models.py`
- Modify: `toram_search/items/service.py`
- Test: `tests/test_item_search.py`

**Interfaces:**
- Produces: `RoutingConfidence = Literal['strong', 'weak', 'none']`.
- Produces: `ItemSearchOutcome.routing_confidence: RoutingConfidence = 'none'`.
- Strong: exact item, recognized stat/filter/rank/expression, recognized item clarification/suggestion, help/meta/refusal.
- Weak: fuzzy item-name results only.
- None: empty or fully unrecognized query.

- [ ] **Step 1: Write the failing confidence test**

```python
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

- [ ] **Step 2: Run the test and verify RED**

```bash
python -m pytest -q tests/test_item_search.py::test_item_routing_confidence_distinguishes_strong_weak_and_none
```

Expected: FAIL because `routing_confidence` does not exist.

- [ ] **Step 3: Add the model field**

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

- [ ] **Step 4: Apply the exact confidence mapping in `ItemSearchService.search()`**

Keep every existing message/result payload unchanged and append only the confidence value according to this mapping:

```text
empty query                                      -> none
help / meta / subjective refusal                 -> strong
upgrade exact or upgrade fuzzy crysta result     -> strong
upgrade no-match                                 -> strong
exact item-name result                           -> strong
ambiguous stat clarification                     -> strong
recognized stat/filter result or no-match        -> strong
recognized expression result / parse suggestion  -> strong
recognized multi-stat suggestion                 -> strong
final fuzzy item-name result                     -> weak
final unrecognized not-found                     -> none
```

Concrete constructor forms for the changed categories:

```python
ItemSearchOutcome('help', raw, message=_HELP, routing_confidence='strong')
ItemSearchOutcome('refuse', raw, message='This search only compares objective database fields; subjective build/tank/DPS recommendations are not supported.', routing_confidence='strong')
ItemSearchOutcome('results', raw, tuple(ItemCardResult(x, score=100, match_kind='exact') for x in exact), routing_confidence='strong')
ItemSearchOutcome('results', raw, tuple(ItemCardResult(i, score=s, match_kind=k) for i, s, k in ranked), routing_confidence='weak')
ItemSearchOutcome('not_found', raw, message='No matching item or stat found.', routing_confidence='none')
```

- [ ] **Step 5: Run all item tests**

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

### Task 2: Parse order-insensitive crysta-slot filters and block structured fuzzy degradation

**Files:**
- Modify: `tests/item_db_factory.py`
- Modify: `toram_search/items/filters.py`
- Modify: `toram_search/items/service.py`
- Test: `tests/test_item_search.py`

**Interfaces:**
- Keep `extract_item_filter(text, available_item_types)` unchanged.
- Specific two-token crysta-slot aliases must win over generic `xtal`, `weapon`, and `wp`.
- `aggro xtal wp`, `aggro wp xtal`, and `aggro weapon xtal` must resolve to Weapon Crysta and leave `aggro` for stat parsing.

- [ ] **Step 1: Extend the test item fixture**

Add to `items`:

```python
(7, 1, 'Aggro Weapon Crystal', 'Weapon Crysta', 100, None, None, None, None, None, 'https://example.com/weapon-crysta', ''),
(8, 1, 'Unrelated Dagger', 'Dagger', 100, None, None, None, None, None, 'https://example.com/dagger', ''),
```

Add to `stats`:

```python
(8, 7, 0, 'Aggro %', 15, '[]', None, None, 0),
(9, 8, 0, 'Critical Rate', 1, '[]', None, None, 0),
```

- [ ] **Step 2: Write failing alias and production-query tests**

```python
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

- [ ] **Step 3: Run both tests and verify RED**

```bash
python -m pytest -q tests/test_item_search.py::test_specific_crysta_slot_aliases_are_order_insensitive tests/test_item_search.py::test_aggro_xtal_wp_returns_weapon_crysta_not_fuzzy_item
```

Expected: FAIL because generic `xtal` currently wins before the intended combined filter is represented.

- [ ] **Step 4: Add the complete specific alias set**

Replace the current `special` mapping in `_candidates()` with:

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

Keep the existing longest-phrase-first sort so two-token aliases beat one-token aliases.

- [ ] **Step 5: Write the failing leftover-token test**

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

- [ ] **Step 6: Run the leftover-token test and verify RED**

```bash
python -m pytest -q tests/test_item_search.py::test_structured_item_intent_with_unknown_leftover_does_not_fuzzy_match
```

Expected: FAIL if the final fuzzy item-name fallback is still reachable after recognizing structured intent.

- [ ] **Step 7: Track recognized structured intent from parsed values**

After `item_filter`, ranking detection, `stat_hits`, `looks_expression`, `stat`, and `choices` have been computed, define:

```python
recognized_structured_intent = bool(
    item_filter is not None
    or rank_direction is not None
    or looks_expression
    or stat is not None
    or choices
    or stat_hits
)
```

Immediately before the final `repository.fuzzy_items(raw)` fallback add:

```python
if recognized_structured_intent:
    return ItemSearchOutcome(
        'suggest',
        raw,
        message=f'I could not safely parse "{raw}".',
        routing_confidence='strong',
    )
```

All successful recognized stat/filter/expression return paths in this section must carry `routing_confidence='strong'` from Task 1.

- [ ] **Step 8: Run all item tests**

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
- Exact skill/alias, compare, tree, structured filters, ailment, MP ranking, and other current strong routes remain active when strict.
- Only RapidFuzz skill-name fallback and `lexical_search()` are disabled when strict.

- [ ] **Step 1: Write failing strict-mode tests**

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

- [ ] **Step 2: Run both tests and verify RED**

```bash
python -m pytest -q tests/test_skill_search.py::test_skill_search_can_disable_weak_fallback tests/test_skill_search.py::test_strict_skill_search_keeps_exact_and_structured_routes
```

Expected: FAIL because `allow_weak_fallback` is not accepted.

- [ ] **Step 3: Add the policy parameter and exact weak-fallback gate**

Change the signature to:

```python
def search(self, query: str, *, allow_weak_fallback: bool = True) -> SkillSearchOutcome:
```

Keep every route through `exact=self.repository.resolve_skill_name(raw)` unchanged. Replace the current final fuzzy/lexical section with this complete block:

```python
if not allow_weak_fallback:
    return SkillSearchOutcome('not_found', raw, message='No matching skill database information found.')

fuzzy = []
for s in self.repository.all_skills():
    score = max(
        float(fuzz.WRatio(norm, s.normalized_name)),
        float(fuzz.token_set_ratio(norm, s.normalized_name)),
    )
    if score >= 88:
        fuzzy.append((score, s))
if fuzzy:
    fuzzy.sort(key=lambda x: (-x[0], x[1].normalized_name, x[1].id))
    return SkillSearchOutcome('results', raw, self._cards(tuple(s for _, s in fuzzy[:20])))

hits = lexical_search(self.repository, raw, limit=20)
if hits:
    return SkillSearchOutcome(
        'results',
        raw,
        self._cards(tuple(self.repository.get_skill(h.skill_id) for h in hits)),
    )
return SkillSearchOutcome('not_found', raw, message='No matching skill database information found.')
```

- [ ] **Step 4: Run all skill tests**

```bash
python -m pytest -q tests/test_skill_search.py
```

Expected: PASS; default behavior remains unchanged.

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
- `_search_skills(query, path, *, allow_weak_fallback=True)` forwards the policy.
- Universal mode searches items first and disables weak skill fallback exactly when `items.routing_confidence == 'strong'`.
- Items-only and Skills-only routing remain independent.

- [ ] **Step 1: Write the exact production regressions**

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


def test_universal_aggro_wp_xtal_matches_same_weapon_crysta(tmp_path: Path) -> None:
    items, skills = databases(tmp_path)
    a = search_database('Universal', 'aggro xtal wp', items_path=items, skills_path=skills)
    b = search_database('Universal', 'aggro wp xtal', items_path=items, skills_path=skills)
    assert a.items is not None and b.items is not None
    assert a.skills is not None and b.skills is not None
    assert [row.item.id for row in a.items.results] == [row.item.id for row in b.items.results]
    assert not a.skills.results
    assert not b.skills.results
```

- [ ] **Step 2: Write cross-domain preservation tests**

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

- [ ] **Step 3: Run Universal tests and verify RED**

```bash
python -m pytest -q tests/test_universal.py
```

Expected: FAIL because Universal currently always grants the skill service weak fallback.

- [ ] **Step 4: Implement confidence-aware routing**

Replace `_search_skills` with:

```python
def _search_skills(query: str, path: Path, *, allow_weak_fallback: bool = True):
    service = SkillSearchService(path)
    try:
        return service.search(query, allow_weak_fallback=allow_weak_fallback)
    finally:
        service.close()
```

Replace the body of `search_database()` after its signature with:

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
    return UniversalSearchOutcome(
        query=query,
        items=_search_items(query, items_path),
        skills=None,
    )

return UniversalSearchOutcome(
    query=query,
    items=None,
    skills=_search_skills(query, skills_path),
)
```

- [ ] **Step 5: Run item, skill, and Universal tests together**

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

**Interfaces:**
- Final behavior must satisfy all Global Constraints and Tasks 1–4.

- [ ] **Step 1: Run the complete suite**

```bash
python -m pytest -q
```

Expected: zero failures, including the exact `aggro xtal wp` regression.

- [ ] **Step 2: Compile application Python sources**

```bash
python -m compileall -q main.py toram_search ui
```

Expected: exit code 0.

- [ ] **Step 3: Verify database files are unchanged**

Compare the implementation branch against its base and confirm neither `items.sqlite` nor `skills.sqlite` appears in the changed-file list.

- [ ] **Step 4: Verify scope**

Expected production paths are limited to:

```text
toram_search/items/models.py
toram_search/items/filters.py
toram_search/items/service.py
toram_search/skills/service.py
toram_search/router.py
```

Allowed non-production changes are the approved spec/plan, `tests/item_db_factory.py`, and the three targeted test files.

- [ ] **Step 5: Commit test-only cleanup only if required by a real compatibility failure**

If no cleanup is required, create no commit. If a real compatibility failure requires test-only cleanup, stage only the affected test files and commit with:

```bash
git commit -m "test: finalize structured routing regressions"
```

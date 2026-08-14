# Query Interpretation Chips Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic removable query-interpretation chips below the Streamlit search box, sourced from the same parser decisions that drive item/skill search, with semantic fill-only reconstruction and deterministic Universal-domain selection.

**Architecture:** Introduce a small domain-neutral interpretation model containing chip metadata, precomputed safe reconstruction targets, and route-quality metadata. Item and skill search services attach interpretation/quality metadata while preserving current search results. The top-level router chooses the single winning interpretation in Universal mode, and a small Streamlit renderer turns the selected chips into fill-only buttons that clear stale results without submitting a new search.

**Tech Stack:** Python 3.12 in CI, Streamlit 1.61.x, SQLite read-only repositories, RapidFuzz 3.x, pytest 8.x.

## Global Constraints

- Keep the system fully deterministic; do not add an LLM, RAG, embeddings, or probabilistic intent classification.
- Keep `main.py` as the root Streamlit entrypoint.
- Keep search submit-only: typing, examples, corrections, and chip removal may fill the input but must not execute a search until Enter/Search.
- Render interpretation chips directly below the main search bar and before results.
- Chips represent only approved structured categories: item stat, item type, ranking, numeric stat comparison, skill tree, ailment, MP filter, and required-level filter.
- Numeric comparisons are atomic chips.
- Exact item/skill names, fuzzy matches, help/meta/refusal, clarification/suggestion, and unsafe/partial parses do not produce chips.
- If a structured route contains an unsupported structured component such as skill tier or skill type, omit the entire interpretation rather than show a misleading partial interpretation.
- Removing a chip must reconstruct a syntactically valid canonical query semantically, remove dependent filters where required, update the search field, clear prior results/chips, reset result limits, and perform no search.
- Universal mode exposes at most one interpretation: the domain that wins deterministic route quality. Raw result count must never choose the winner.
- If Universal mode's winning route has no chip-eligible structured filters, show no chips; never fall back to the losing domain only because it has chips.
- Preserve the existing Universal skill weak-fallback suppression rule based on item `routing_confidence`; route-quality metadata is only for interpretation winner selection.
- Preserve existing item/skill result semantics, correction/example fill-only behavior, and custom-component external-value synchronization.
- Do not modify `items.sqlite` or `skills.sqlite`.

## File Structure

- Create `toram_search/interpretation.py` — shared immutable chip, interpretation, and route-quality types; no domain imports.
- Create `toram_search/items/interpretation.py` — item-only canonicalization and semantic reconstruction from already-parsed item structures.
- Modify `toram_search/items/filters.py` — expose a canonical query fragment for `ItemTypeFilter` so aliases such as `xtal wp` reconstruct as `weapon xtal`.
- Modify `toram_search/items/models.py` — attach optional interpretation and route-quality metadata to `ItemSearchOutcome` while retaining `routing_confidence`.
- Modify `toram_search/items/service.py` — populate item interpretation/quality from the same branches that execute item search.
- Create `toram_search/skills/interpretation.py` — skill-only supported-filter interpretation and canonical reconstruction.
- Modify `toram_search/skills/models.py` — attach optional interpretation and route-quality metadata to `SkillSearchOutcome`.
- Modify `toram_search/skills/service.py` — populate skill interpretation/quality from existing parsed filters/tree/ailment/ranking branches without creating a second parser.
- Modify `toram_search/models.py` — add the single selected interpretation to `UniversalSearchOutcome`.
- Modify `toram_search/router.py` — select the winning interpretation deterministically while leaving actual domain search routing unchanged.
- Create `ui/interpretation.py` — render removable chip buttons and return the precomputed fill-only query.
- Modify `main.py` — place chips below the search box and clear stale state on chip removal.
- Create `tests/test_interpretation.py` — shared model/route-quality unit tests.
- Modify `tests/test_item_search.py`, `tests/test_skill_search.py`, `tests/test_universal.py`, `tests/test_app_shell.py`, `tests/test_ui_contract.py`, and `tests/test_real_databases.py` — regression and integration coverage.

---

### Task 1: Shared interpretation and route-quality model

**Files:**
- Create: `toram_search/interpretation.py`
- Create: `tests/test_interpretation.py`

**Interfaces:**
- Produces: `QueryChip`, `QueryInterpretation`, `RouteQuality`, `ChipKind`, `SearchDomain`, and `RouteFamily`.
- `QueryInterpretation.query_without(chip_id: str) -> str` is the only reconstruction interface the UI will use.
- `RouteQuality.sort_key -> tuple[int, int, int]` is the only quality ordering the Universal router will use.

- [ ] **Step 1: Write failing tests for safe chip lookup and route ordering**

Create `tests/test_interpretation.py` with:

```python
import pytest

from toram_search.interpretation import QueryChip, QueryInterpretation, RouteQuality


def test_query_interpretation_returns_precomputed_semantic_removal_query() -> None:
    interpretation = QueryInterpretation(
        domain='Items',
        canonical_query='highest critical rate bow',
        chips=(
            QueryChip('rank', 'rank', 'Highest', 'highest', 'critical rate bow'),
            QueryChip('stat', 'stat', 'Critical Rate', 'critical rate', 'bow', depends_on=()),
            QueryChip('item_type', 'item_type', 'Bow', 'bow', 'highest critical rate'),
        ),
    )
    assert interpretation.query_without('item_type') == 'highest critical rate'
    assert interpretation.query_without('stat') == 'bow'


def test_query_interpretation_rejects_unknown_chip_id() -> None:
    interpretation = QueryInterpretation(domain='Items', canonical_query='', chips=())
    with pytest.raises(KeyError, match='missing'):
        interpretation.query_without('missing')


def test_route_quality_matches_approved_priority() -> None:
    exact_results = RouteQuality('exact', True, 1)
    structured_results = RouteQuality('structured', True, 3)
    structured_empty = RouteQuality('structured', False, 4)
    weak_results = RouteQuality('weak', True, 99)
    none = RouteQuality('none', False, 99)

    assert exact_results.sort_key > structured_results.sort_key
    assert structured_results.sort_key > structured_empty.sort_key
    assert structured_empty.sort_key > weak_results.sort_key
    assert weak_results.sort_key > none.sort_key


def test_route_quality_uses_specificity_only_after_family_quality() -> None:
    broad = RouteQuality('structured', True, 1)
    narrow = RouteQuality('structured', True, 3)
    assert narrow.sort_key > broad.sort_key
```

- [ ] **Step 2: Run the new tests and confirm RED**

Run:

```bash
python -m pytest tests/test_interpretation.py -q
```

Expected: collection fails because `toram_search.interpretation` does not exist.

- [ ] **Step 3: Implement the immutable shared model**

Create `toram_search/interpretation.py` with this public shape:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ChipKind = Literal[
    'stat',
    'item_type',
    'numeric_stat',
    'rank',
    'skill_tree',
    'ailment',
    'mp',
    'required_level',
]
SearchDomain = Literal['Items', 'Skills']
RouteFamily = Literal['exact', 'structured', 'weak', 'none']


@dataclass(frozen=True)
class QueryChip:
    id: str
    kind: ChipKind
    label: str
    canonical_fragment: str
    query_without: str
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class QueryInterpretation:
    domain: SearchDomain
    canonical_query: str
    chips: tuple[QueryChip, ...]

    def query_without(self, chip_id: str) -> str:
        for chip in self.chips:
            if chip.id == chip_id:
                return chip.query_without
        raise KeyError(chip_id)


@dataclass(frozen=True)
class RouteQuality:
    family: RouteFamily = 'none'
    has_results: bool = False
    specificity: int = 0

    @property
    def sort_key(self) -> tuple[int, int, int]:
        if self.family in {'exact', 'structured'} and self.has_results:
            result_tier = 3
        elif self.family in {'exact', 'structured'}:
            result_tier = 2
        elif self.family == 'weak' and self.has_results:
            result_tier = 1
        else:
            result_tier = 0
        family_rank = {'exact': 2, 'structured': 1, 'weak': 0, 'none': 0}[self.family]
        return result_tier, family_rank, self.specificity
```

Rationale encoded in the type:
- `query_without` is precomputed by the domain parser/builder, so the UI never edits raw strings.
- exact and structured routes with results share the top result tier, but exact wins the quality tie.
- specificity breaks ties between routes of the same family without consulting result count.

- [ ] **Step 4: Run the shared-model tests and confirm GREEN**

Run:

```bash
python -m pytest tests/test_interpretation.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add toram_search/interpretation.py tests/test_interpretation.py
git commit -m "feat: add query interpretation model"
```

---

### Task 2: Item interpretations and semantic expression reconstruction

**Files:**
- Create: `toram_search/items/interpretation.py`
- Modify: `toram_search/items/filters.py`
- Modify: `toram_search/items/models.py`
- Modify: `toram_search/items/service.py`
- Modify: `tests/test_item_search.py`

**Interfaces:**
- Consumes: `QueryChip`, `QueryInterpretation`, `RouteQuality` from Task 1.
- Produces: `build_simple_item_interpretation(...) -> QueryInterpretation | None` and `build_expression_item_interpretation(expr: ParsedStatExpression) -> QueryInterpretation | None`.
- `ItemTypeFilter` gains `canonical_text: str`.
- `ItemSearchOutcome` gains `interpretation: QueryInterpretation | None` and `route_quality: RouteQuality` while retaining `routing_confidence` unchanged.

- [ ] **Step 1: Add item regression tests before production changes**

Append to `tests/test_item_search.py`:

```python
def test_item_interpretation_for_aggro_weapon_crysta_is_canonical_and_removable(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('aggro xtal wp')
    finally:
        service.close()

    assert outcome.interpretation is not None
    assert outcome.interpretation.domain == 'Items'
    assert [(c.kind, c.label) for c in outcome.interpretation.chips] == [
        ('stat', 'Aggro %'),
        ('item_type', 'Weapon Crysta'),
    ]
    item_type = next(c for c in outcome.interpretation.chips if c.kind == 'item_type')
    stat = next(c for c in outcome.interpretation.chips if c.kind == 'stat')
    assert outcome.interpretation.query_without(item_type.id) == 'aggro'
    assert outcome.interpretation.query_without(stat.id) == 'weapon xtal'


def test_rank_chip_depends_on_stat_and_reconstructs_canonically(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('highest cr bow')
    finally:
        service.close()

    interpretation = outcome.interpretation
    assert interpretation is not None
    assert [(c.kind, c.label) for c in interpretation.chips] == [
        ('rank', 'Highest'),
        ('stat', 'Critical Rate'),
        ('item_type', 'Bow'),
    ]
    rank = next(c for c in interpretation.chips if c.kind == 'rank')
    stat = next(c for c in interpretation.chips if c.kind == 'stat')
    item_type = next(c for c in interpretation.chips if c.kind == 'item_type')
    assert rank.depends_on == ('stat',)
    assert interpretation.query_without(rank.id) == 'critical rate bow'
    assert interpretation.query_without(stat.id) == 'bow'
    assert interpretation.query_without(item_type.id) == 'highest critical rate'


def test_numeric_comparison_is_one_atomic_chip(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('hp >= 5000 armor')
    finally:
        service.close()

    interpretation = outcome.interpretation
    assert interpretation is not None
    assert [(c.kind, c.label) for c in interpretation.chips] == [
        ('numeric_stat', 'MaxHP ≥ 5000'),
        ('item_type', 'Armor'),
    ]
    numeric = interpretation.chips[0]
    assert interpretation.query_without(numeric.id) == 'armor'


def test_boolean_expression_removal_rebuilds_from_ast_not_raw_substrings(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('hp > 5000 and cr bow')
    finally:
        service.close()

    interpretation = outcome.interpretation
    assert interpretation is not None
    hp_chip = next(c for c in interpretation.chips if c.label == 'MaxHP > 5000')
    cr_chip = next(c for c in interpretation.chips if c.label == 'Critical Rate')
    assert interpretation.query_without(hp_chip.id) == 'critical rate bow'
    assert interpretation.query_without(cr_chip.id) == 'maxhp > 5000 bow'


def test_unsafe_item_suggestion_has_no_interpretation(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('crit bow hp')
    finally:
        service.close()
    assert outcome.kind in {'suggest', 'clarify'}
    assert outcome.interpretation is None


def test_exact_and_fuzzy_item_routes_have_quality_but_no_chips(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        exact = service.search('Test Bow')
        fuzzy = service.search('Test Bo')
    finally:
        service.close()
    assert exact.route_quality.family == 'exact'
    assert exact.interpretation is None
    assert fuzzy.route_quality.family == 'weak'
    assert fuzzy.interpretation is None
```

- [ ] **Step 2: Run the targeted tests and confirm RED**

Run:

```bash
python -m pytest \
  tests/test_item_search.py::test_item_interpretation_for_aggro_weapon_crysta_is_canonical_and_removable \
  tests/test_item_search.py::test_rank_chip_depends_on_stat_and_reconstructs_canonically \
  tests/test_item_search.py::test_numeric_comparison_is_one_atomic_chip \
  tests/test_item_search.py::test_boolean_expression_removal_rebuilds_from_ast_not_raw_substrings \
  tests/test_item_search.py::test_unsafe_item_suggestion_has_no_interpretation \
  tests/test_item_search.py::test_exact_and_fuzzy_item_routes_have_quality_but_no_chips -q
```

Expected: failures because outcomes do not yet expose `interpretation` or `route_quality`.

- [ ] **Step 3: Give item-type filters a canonical query form**

Modify `ItemTypeFilter` in `toram_search/items/filters.py`:

```python
@dataclass(frozen=True)
class ItemTypeFilter:
    label: str
    item_types: tuple[str, ...]
    consumed_text: str
    canonical_text: str
```

Extend candidate construction so aliases share one canonical representation. Use these exact canonical group fragments:

```python
_CANONICAL_SPECIAL = {
    'Weapon Crysta': 'weapon xtal',
    'Armor Crysta': 'armor xtal',
    'Additional Crysta': 'additional xtal',
    'Special Crysta': 'ring xtal',
    'All Crysta': 'xtal',
    'Main Weapons': 'weapon',
}
```

For ordinary item types use `normalize_stat_text(actual_item_type)` as `canonical_text`. `extract_item_filter()` must still match the exact same aliases and item-type sets; only the returned metadata changes.

- [ ] **Step 4: Add item outcome metadata with backward-compatible defaults**

Modify `toram_search/items/models.py` imports and `ItemSearchOutcome`:

```python
from toram_search.interpretation import QueryInterpretation, RouteQuality


@dataclass(frozen=True)
class ItemSearchOutcome:
    kind: ItemOutcomeKind
    query: str
    results: tuple[ItemCardResult, ...] = ()
    message: str | None = None
    suggested_queries: tuple[str, ...] = ()
    routing_confidence: RoutingConfidence = 'none'
    interpretation: QueryInterpretation | None = None
    route_quality: RouteQuality = RouteQuality()
```

Do not remove or repurpose `routing_confidence`.

- [ ] **Step 5: Implement item semantic reconstruction helpers**

Create `toram_search/items/interpretation.py` with focused helpers. The implementation must canonicalize values semantically, not by deleting text from the original query.

Use these formatting rules:

```python
_PREFERRED_STAT_QUERY = {
    'Aggro %': 'aggro',
    'Critical Rate': 'critical rate',
    'Critical Damage': 'critical damage',
    'MaxHP': 'maxhp',
}


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f'{value:g}'


def _stat_fragment(stat_name: str) -> str:
    return _PREFERRED_STAT_QUERY.get(stat_name, normalize_stat_text(stat_name))


def _comparison_label(stat_name: str, operator: str, value: float) -> str:
    symbol = {'>=': '≥', '<=': '≤', '==': '=', '=': '='}.get(operator, operator)
    return f'{stat_name} {symbol} {_number(value)}'
```

`build_simple_item_interpretation()` must accept the already-resolved `stat`, `item_filter`, `rank_direction`, and `negative_stat` values from `ItemSearchService.search()` and build these exact semantic parts:

- rank: `Highest` / canonical `highest`, or `Lowest` / canonical `lowest`;
- normal stat: kind `stat`, database label, canonical `_stat_fragment(stat)`;
- negative shorthand: kind `numeric_stat`, label `<Stat> ≤ -1`, canonical `<stat fragment> <= -1` so reconstruction remains equivalent without depending on the `-alias` shorthand;
- item type: kind `item_type`, label `item_filter.label`, canonical `item_filter.canonical_text`.

Rank depends on the stat chip. Precompute every chip's `query_without` from the remaining semantic parts. If the stat is removed, omit rank automatically. For the approved examples this must yield exactly:

```text
aggro xtal wp        -> remove type -> aggro
aggro xtal wp        -> remove stat -> weapon xtal
highest cr bow       -> remove rank -> critical rate bow
highest cr bow       -> remove stat -> bow
highest cr bow       -> remove type -> highest critical rate
```

For parsed boolean expressions, `build_expression_item_interpretation(expr)` must walk `ParsedStatExpression.groups` directly. Generate one chip per clause, using `numeric_stat` for explicit comparisons and `stat` for implicit clauses. Rebuild a removed clause by:

1. removing the clause from its AND group;
2. dropping an empty group;
3. joining remaining clauses in a group with ` and `;
4. joining remaining groups with ` or `;
5. appending `expr.item_filter.canonical_text` if present;
6. returning only the item filter if all clauses were removed;
7. returning the expression alone when the item-type chip is removed.

This preserves valid syntax for `AND/OR` queries and avoids raw substring edits.

- [ ] **Step 6: Attach interpretation and route quality inside the existing item search branches**

Modify `ItemSearchService.search()` so the current parsing variables remain the source of truth.

Assign route families as follows without changing result behavior:

```text
exact item name                         -> exact
exact upgrade target                    -> exact
fuzzy upgrade target                    -> structured
help/meta/refuse                        -> structured, no interpretation
clarify/suggest/unsafe structured parse -> structured, no interpretation
simple stat/filter/rank                 -> structured + simple interpretation
parsed numeric/AND/OR expression        -> structured + expression interpretation
recognized structured no-result         -> structured, no interpretation if parse was unsafe
fuzzy item-name fallback                -> weak
fully unrecognized                      -> none
```

Set `RouteQuality.has_results` from the actual returned cards. For structured routes set `specificity` to the number of semantic constraints actually executed, not result count. Count rank, stat/expression clauses, and item type separately. For exact routes use specificity `1`. For weak/none use specificity `0`.

Do not change the existing strong/weak/none `routing_confidence` assignments used by Universal weak-skill suppression.

- [ ] **Step 7: Run item tests and fix only item-scope regressions**

Run:

```bash
python -m pytest tests/test_item_search.py -q
```

Expected: all item tests pass, including duplicate-stat grouping and structured-routing regressions.

- [ ] **Step 8: Commit Task 2**

```bash
git add \
  toram_search/items/interpretation.py \
  toram_search/items/filters.py \
  toram_search/items/models.py \
  toram_search/items/service.py \
  tests/test_item_search.py
git commit -m "feat: expose item query interpretations"
```

---

### Task 3: Skill interpretations from existing structured decisions

**Files:**
- Create: `toram_search/skills/interpretation.py`
- Modify: `toram_search/skills/models.py`
- Modify: `toram_search/skills/service.py`
- Modify: `tests/test_skill_search.py`

**Interfaces:**
- Consumes: shared interpretation types from Task 1 and existing `SkillFilter` values from `SkillSearchService`.
- Produces: `build_skill_interpretation(...) -> QueryInterpretation | None`.
- `SkillSearchOutcome` gains `interpretation` and `route_quality` metadata.
- No new independent skill parser is allowed; helpers receive values already resolved by the service.

- [ ] **Step 1: Add failing skill interpretation tests**

Append to `tests/test_skill_search.py`:

```python
def test_skill_tree_query_exposes_removable_tree_chip(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('shield skill tree')
    finally:
        service.close()
    interpretation = outcome.interpretation
    assert interpretation is not None
    assert [(c.kind, c.label) for c in interpretation.chips] == [('skill_tree', 'Shield Skills')]
    assert interpretation.query_without(interpretation.chips[0].id) == ''


def test_ailment_query_exposes_ailment_chip(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('skills that inflict stun')
    finally:
        service.close()
    interpretation = outcome.interpretation
    assert interpretation is not None
    assert [(c.kind, c.label) for c in interpretation.chips] == [('ailment', 'Stun')]


def test_mp_and_required_level_filters_are_atomic(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        mp = service.search('skills mp <= 200')
        level = service.search('skills required level <= 20')
    finally:
        service.close()
    assert mp.interpretation is not None
    assert [(c.kind, c.label) for c in mp.interpretation.chips] == [('mp', 'MP ≤ 200')]
    assert level.interpretation is not None
    assert [(c.kind, c.label) for c in level.interpretation.chips] == [
        ('required_level', 'Required Level ≤ 20')
    ]


def test_lowest_mp_tree_ranking_uses_atomic_rank_field_chip(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('lowest mp shield skills')
    finally:
        service.close()
    interpretation = outcome.interpretation
    assert interpretation is not None
    assert [(c.kind, c.label) for c in interpretation.chips] == [
        ('rank', 'Lowest MP'),
        ('skill_tree', 'Shield Skills'),
    ]
    rank = interpretation.chips[0]
    tree = interpretation.chips[1]
    assert interpretation.query_without(rank.id) == 'shield skills'
    assert interpretation.query_without(tree.id) == 'lowest mp'


def test_exact_skill_route_wins_quality_without_renderable_chips(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('Guardian')
    finally:
        service.close()
    assert outcome.route_quality.family == 'exact'
    assert outcome.interpretation is None


def test_unsupported_structured_skill_components_do_not_emit_partial_chips(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        tier = service.search('tier 1 shield skills')
        skill_type = service.search('active shield skills')
    finally:
        service.close()
    assert tier.route_quality.family == 'structured'
    assert tier.interpretation is None
    assert skill_type.route_quality.family == 'structured'
    assert skill_type.interpretation is None


def test_weak_skill_fallback_has_no_interpretation(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('protects party members')
    finally:
        service.close()
    assert outcome.route_quality.family == 'weak'
    assert outcome.interpretation is None
```

- [ ] **Step 2: Run targeted skill tests and confirm RED**

Run:

```bash
python -m pytest \
  tests/test_skill_search.py::test_skill_tree_query_exposes_removable_tree_chip \
  tests/test_skill_search.py::test_ailment_query_exposes_ailment_chip \
  tests/test_skill_search.py::test_mp_and_required_level_filters_are_atomic \
  tests/test_skill_search.py::test_lowest_mp_tree_ranking_uses_atomic_rank_field_chip \
  tests/test_skill_search.py::test_exact_skill_route_wins_quality_without_renderable_chips \
  tests/test_skill_search.py::test_unsupported_structured_skill_components_do_not_emit_partial_chips \
  tests/test_skill_search.py::test_weak_skill_fallback_has_no_interpretation -q
```

Expected: failures because `SkillSearchOutcome` has no interpretation/quality metadata.

- [ ] **Step 3: Extend `SkillSearchOutcome` with shared metadata**

Modify `toram_search/skills/models.py`:

```python
from toram_search.interpretation import QueryInterpretation, RouteQuality


@dataclass(frozen=True)
class SkillSearchOutcome:
    kind: SkillOutcomeKind
    query: str
    results: tuple[SkillCardResult, ...] = ()
    message: str | None = None
    suggested_queries: tuple[str, ...] = ()
    interpretation: QueryInterpretation | None = None
    route_quality: RouteQuality = RouteQuality()
```

- [ ] **Step 4: Implement the supported skill interpretation builder**

Create `toram_search/skills/interpretation.py` with a single focused builder that receives canonical values already resolved by `SkillSearchService`:

```python
def build_skill_interpretation(
    *,
    tree_name: str | None = None,
    ailment: str | None = None,
    mp_cost_max: int | None = None,
    required_level_max: int | None = None,
    mp_rank_direction: str | None = None,
    count_mode: bool = False,
    unsupported_structured_component: bool = False,
) -> QueryInterpretation | None:
    ...
```

Rules:

- If `unsupported_structured_component` is true, return `None` even when a supported tree is also present. This prevents partial explanations for `tier 1 shield skills` and `active shield skills`.
- Tree chip: kind `skill_tree`, label canonical DB tree name such as `Shield Skills`, fragment `shield skills`.
- Ailment chip: kind `ailment`, label canonical ailment such as `Stun`, fragment `inflict stun`.
- MP max chip: kind `mp`, label `MP ≤ 200`, fragment `mp <= 200`.
- Required-level chip: kind `required_level`, label `Required Level ≤ 20`, fragment `required level <= 20`.
- MP ranking is one atomic rank-field chip rather than a misleading standalone MP chip: kind `rank`, label `Lowest MP` or `Highest MP`, fragment `lowest mp` / `highest mp`.
- Join remaining fragments with single spaces; these are token-independent patterns already supported by `_structured_filter_from_query()` and the existing tree/rank branches.
- If `count_mode` is true, prefix a non-empty rebuilt query with `how many skills `; if removal leaves no filters, return the empty string rather than invalid `how many skills`.
- Precompute `query_without` for each chip. No UI code may reconstruct these strings itself.

- [ ] **Step 5: Integrate the builder into existing skill search branches**

Modify `SkillSearchService.search()` without introducing a second parsing pass.

Use already-computed values:
- `skills` from `_find_skill_phrases()` for exact/compare/property routes;
- `structured_filter` from `_structured_filter_from_query()`;
- resolved tree IDs/names from `_tree_id_from_query()` / repository;
- resolved ailment names from `resolve_ailment()`;
- existing MP ranking direction logic.

Assign quality families:

```text
exact skill name / exact skill property / compare -> exact, no interpretation
explicit supported structured filters            -> structured + interpretation
supported tree-only route                        -> structured + tree interpretation
supported ailment route                          -> structured + ailment interpretation
lowest/highest MP route                          -> structured + atomic MP-rank interpretation
structured route with tier/skill type/weapons    -> structured, interpretation None
strict no-match before weak fallback              -> none
RapidFuzz / lexical fallback                     -> weak, interpretation None
fully no-match                                   -> none
refuse                                           -> structured, interpretation None
```

Set structured `specificity` from the number of executed constraints, including unsupported ones. For example `tier 1 shield skills` has specificity 2 even though interpretation is omitted. Exact skill routes use specificity 1 (or 2 for compare). Weak/none use 0.

Do not change `allow_weak_fallback` semantics.

- [ ] **Step 6: Run all skill tests and confirm GREEN**

Run:

```bash
python -m pytest tests/test_skill_search.py -q
```

Expected: all current and new skill tests pass.

- [ ] **Step 7: Commit Task 3**

```bash
git add \
  toram_search/skills/interpretation.py \
  toram_search/skills/models.py \
  toram_search/skills/service.py \
  tests/test_skill_search.py
git commit -m "feat: expose skill query interpretations"
```

---

### Task 4: Deterministic Universal winner selection

**Files:**
- Modify: `toram_search/models.py`
- Modify: `toram_search/router.py`
- Modify: `tests/test_universal.py`

**Interfaces:**
- Consumes: `ItemSearchOutcome.route_quality`, `SkillSearchOutcome.route_quality`, and optional interpretations.
- Produces: `UniversalSearchOutcome.interpretation: QueryInterpretation | None`.
- Search execution order and item-driven `allow_weak_fallback` remain unchanged.

- [ ] **Step 1: Add failing Universal selection tests**

Add imports and tests to `tests/test_universal.py`:

```python
from toram_search.interpretation import QueryChip, QueryInterpretation, RouteQuality
from toram_search.items.models import ItemSearchOutcome
from toram_search.skills.models import SkillSearchOutcome
from toram_search.router import select_winning_interpretation


def _interp(domain: str, label: str) -> QueryInterpretation:
    kind = 'stat' if domain == 'Items' else 'ailment'
    return QueryInterpretation(
        domain=domain,
        canonical_query=label.casefold(),
        chips=(QueryChip('one', kind, label, label.casefold(), ''),),
    )


def test_exact_route_beats_structured_route_even_when_exact_has_no_chips() -> None:
    item = ItemSearchOutcome(
        'results',
        'shared',
        route_quality=RouteQuality('structured', True, 3),
        interpretation=_interp('Items', 'Critical Rate'),
    )
    skill = SkillSearchOutcome(
        'results',
        'shared',
        route_quality=RouteQuality('exact', True, 1),
        interpretation=None,
    )
    assert select_winning_interpretation(item, skill) is None


def test_more_specific_structured_route_wins_same_family_tie() -> None:
    item_interp = _interp('Items', 'Critical Rate')
    skill_interp = _interp('Skills', 'Stun')
    item = ItemSearchOutcome(
        'results', 'shared',
        route_quality=RouteQuality('structured', True, 1),
        interpretation=item_interp,
    )
    skill = SkillSearchOutcome(
        'results', 'shared',
        route_quality=RouteQuality('structured', True, 2),
        interpretation=skill_interp,
    )
    assert select_winning_interpretation(item, skill) == skill_interp


def test_result_count_is_not_part_of_interpretation_winner_key() -> None:
    item_interp = _interp('Items', 'Critical Rate')
    skill_interp = _interp('Skills', 'Stun')
    item = ItemSearchOutcome(
        'results', 'shared',
        route_quality=RouteQuality('structured', True, 1),
        interpretation=item_interp,
    )
    skill = SkillSearchOutcome(
        'results', 'shared',
        route_quality=RouteQuality('structured', True, 2),
        interpretation=skill_interp,
    )
    assert select_winning_interpretation(item, skill) == skill_interp


def test_equal_quality_uses_stable_items_first_tie_break() -> None:
    item_interp = _interp('Items', 'Critical Rate')
    skill_interp = _interp('Skills', 'Stun')
    item = ItemSearchOutcome(
        'results', 'shared',
        route_quality=RouteQuality('structured', True, 1),
        interpretation=item_interp,
    )
    skill = SkillSearchOutcome(
        'results', 'shared',
        route_quality=RouteQuality('structured', True, 1),
        interpretation=skill_interp,
    )
    assert select_winning_interpretation(item, skill) == item_interp
```

Also extend existing end-to-end mode tests:

```python
def test_items_mode_exposes_item_interpretation(tmp_path: Path) -> None:
    items = tmp_path / 'items.sqlite'
    create_item_database(items)
    outcome = search_database(
        'Items', 'highest cr bow',
        items_path=items,
        skills_path=tmp_path / 'missing-skills.sqlite',
    )
    assert outcome.interpretation is not None
    assert outcome.interpretation.domain == 'Items'


def test_skills_mode_exposes_skill_interpretation(tmp_path: Path) -> None:
    skills = tmp_path / 'skills.sqlite'
    create_skill_database(skills)
    outcome = search_database(
        'Skills', 'skills that inflict stun',
        items_path=tmp_path / 'missing-items.sqlite',
        skills_path=skills,
    )
    assert outcome.interpretation is not None
    assert outcome.interpretation.domain == 'Skills'
```

- [ ] **Step 2: Run the Universal tests and confirm RED**

Run:

```bash
python -m pytest tests/test_universal.py -q
```

Expected: failures because `UniversalSearchOutcome` has no interpretation field and `select_winning_interpretation()` does not exist.

- [ ] **Step 3: Extend the top-level outcome model**

Modify `toram_search/models.py`:

```python
from toram_search.interpretation import QueryInterpretation


@dataclass(frozen=True)
class UniversalSearchOutcome:
    query: str
    items: ItemSearchOutcome | None = None
    skills: SkillSearchOutcome | None = None
    interpretation: QueryInterpretation | None = None
```

- [ ] **Step 4: Implement one deterministic Universal selection helper**

Add to `toram_search/router.py`:

```python
def select_winning_interpretation(items, skills):
    candidates = []
    if items is not None:
        candidates.append((items.route_quality.sort_key, 1, items.interpretation))
    if skills is not None:
        candidates.append((skills.route_quality.sort_key, 0, skills.interpretation))
    if not candidates:
        return None
    _quality, _stable_domain_order, interpretation = max(
        candidates,
        key=lambda row: (row[0], row[1]),
    )
    return interpretation
```

The final integer is only a stable exact tie-break after route quality and specificity are equal; it does not inspect result count. Items wins only this final otherwise-identical tie because the existing Universal coordinator is item-first.

- [ ] **Step 5: Attach selection to all modes without changing search execution**

For `Universal`:

```python
items = _search_items(...)
skills = _search_skills(
    ...,
    allow_weak_fallback=items.routing_confidence != 'strong',
)
return UniversalSearchOutcome(
    query=query,
    items=items,
    skills=skills,
    interpretation=select_winning_interpretation(items, skills),
)
```

For Items-only and Skills-only, copy that domain's own `interpretation` directly into `UniversalSearchOutcome.interpretation`.

Do not alter the current strict skill fallback decision.

- [ ] **Step 6: Run Universal tests and confirm GREEN**

Run:

```bash
python -m pytest tests/test_universal.py -q
```

Expected: all tests pass, including existing `aggro xtal wp`, exact skill, and weak FTS preservation regressions.

- [ ] **Step 7: Commit Task 4**

```bash
git add toram_search/models.py toram_search/router.py tests/test_universal.py
git commit -m "feat: select universal query interpretation"
```

---

### Task 5: Streamlit removable-chip UI and fill-only state transition

**Files:**
- Create: `ui/interpretation.py`
- Modify: `main.py`
- Modify: `tests/test_app_shell.py`
- Modify: `tests/test_ui_contract.py`
- Verify unchanged: `components/autocomplete_search/index.html`
- Verify unchanged behavior: `tests/test_search_component.py`

**Interfaces:**
- Consumes: `UniversalSearchOutcome.interpretation` and `QueryInterpretation.query_without()`.
- Produces: `render_query_interpretation(interpretation: QueryInterpretation | None) -> str | None`.
- Return value is a fill-only canonical query or `None` when no chip was removed.

- [ ] **Step 1: Add failing UI contract and AppTest coverage**

Append to `tests/test_ui_contract.py`:

```python
def test_query_interpretation_renders_after_search_box_before_results() -> None:
    source = text('main.py')
    assert 'render_query_interpretation' in source
    assert source.index('submission=render_search_box') < source.index('render_query_interpretation')
    assert source.index('render_query_interpretation') < source.index("st.divider()")


def test_chip_removal_clears_outcome_instead_of_submitting() -> None:
    source = text('main.py')
    block = source[source.index('chip_fill='):source.index("st.divider()")]
    assert 'st.session_state.last_outcome=None' in block
    assert 'query_to_run=chip_fill' not in block
    assert 'search_database(' not in block
```

Append to `tests/test_app_shell.py`:

```python
from toram_search.interpretation import QueryChip, QueryInterpretation
from toram_search.models import UniversalSearchOutcome


def test_chip_removal_fills_query_clears_results_and_does_not_submit() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    interpretation = QueryInterpretation(
        domain='Items',
        canonical_query='highest critical rate bow',
        chips=(
            QueryChip('rank', 'rank', 'Highest', 'highest', 'critical rate bow'),
            QueryChip('stat', 'stat', 'Critical Rate', 'critical rate', 'bow', depends_on=()),
            QueryChip('item_type', 'item_type', 'Bow', 'bow', 'highest critical rate'),
        ),
    )
    app.session_state['query'] = 'highest cr bow'
    app.session_state['last_submission_nonce'] = 'already-submitted'
    app.session_state['last_outcome'] = UniversalSearchOutcome(
        query='highest cr bow',
        interpretation=interpretation,
    )
    app.session_state['item_limit'] = 60
    app.session_state['skill_limit'] = 40
    app.run(timeout=10)

    target = next(button for button in app.button if button.label == 'Critical Rate ×')
    target.click().run(timeout=10)

    assert app.session_state['query'] == 'bow'
    assert app.session_state['last_outcome'] is None
    assert app.session_state['last_submission_nonce'] == 'already-submitted'
    assert app.session_state['item_limit'] == 20
    assert app.session_state['skill_limit'] == 20
    assert not any(button.label.endswith(' ×') for button in app.button)
```

This AppTest checks the state transition. The existing `test_external_fill_syncs_when_streamlit_value_changes_even_if_input_keeps_focus()` in `tests/test_search_component.py` remains the contract proving that a changed `st.session_state.query` is propagated into the visible iframe input.

- [ ] **Step 2: Run the new UI tests and confirm RED**

Run:

```bash
python -m pytest \
  tests/test_ui_contract.py::test_query_interpretation_renders_after_search_box_before_results \
  tests/test_ui_contract.py::test_chip_removal_clears_outcome_instead_of_submitting \
  tests/test_app_shell.py::test_chip_removal_fills_query_clears_results_and_does_not_submit -q
```

Expected: failures because the renderer and state transition do not exist.

- [ ] **Step 3: Implement the chip renderer**

Create `ui/interpretation.py`:

```python
from __future__ import annotations

import streamlit as st

from toram_search.interpretation import QueryInterpretation


def render_query_interpretation(interpretation: QueryInterpretation | None) -> str | None:
    if interpretation is None or not interpretation.chips:
        return None
    st.caption('Parsed filters')
    columns = st.columns(min(len(interpretation.chips), 4))
    for index, chip in enumerate(interpretation.chips):
        with columns[index % len(columns)]:
            if st.button(
                f'{chip.label} ×',
                key=f'query_chip_{interpretation.domain}_{chip.id}',
                use_container_width=True,
            ):
                return interpretation.query_without(chip.id)
    return None
```

Do not parse text, inspect result cards, or calculate dependencies here.

- [ ] **Step 4: Integrate chips immediately below the search box**

Import the renderer in `main.py`:

```python
from ui.interpretation import render_query_interpretation
```

Keep search submission processing unchanged. After any submitted search has updated `st.session_state.last_outcome`, retrieve `outcome` and render the interpretation before the results divider:

```python
outcome: UniversalSearchOutcome | None = st.session_state.last_outcome
chip_fill = render_query_interpretation(outcome.interpretation if outcome is not None else None)
if chip_fill is not None:
    st.session_state.query = chip_fill
    st.session_state.last_outcome = None
    st.session_state.item_limit = 20
    st.session_state.skill_limit = 20
    st.rerun()

if outcome is not None:
    st.divider()
    ...
```

Do not assign `chip_fill` to `query_to_run`. Do not call `search_database()` from the chip-removal branch. Leave `last_submission_nonce` unchanged; the existing nonce guard prevents stale component submissions from rerunning the old query.

- [ ] **Step 5: Run UI/AppTest/search-component regressions**

Run:

```bash
python -m pytest tests/test_app_shell.py tests/test_ui_contract.py tests/test_search_component.py -q
```

Expected: all tests pass. In particular:
- example buttons remain fill-only;
- correction buttons remain fill-only;
- external value changes still sync into the custom input even if it keeps focus;
- chip removal clears the old outcome and does not submit.

- [ ] **Step 6: Commit Task 5**

```bash
git add ui/interpretation.py main.py tests/test_app_shell.py tests/test_ui_contract.py
git commit -m "feat: add removable query interpretation chips"
```

---

### Task 6: Real-database regressions, full verification, and scope audit

**Files:**
- Modify: `tests/test_real_databases.py`
- Verify: `items.sqlite`
- Verify: `skills.sqlite`

**Interfaces:**
- Consumes the complete feature from Tasks 1-5.
- Produces real committed-database regression evidence and final branch verification.

- [ ] **Step 1: Add real-database interpretation regressions**

Extend `tests/test_real_databases.py`:

```python
def test_real_aggro_weapon_crysta_query_exposes_item_interpretation() -> None:
    outcome = search_database(
        'Universal',
        'aggro xtal wp',
        items_path=ITEM_DATABASE,
        skills_path=SKILL_DATABASE,
    )
    assert outcome.interpretation is not None
    assert outcome.interpretation.domain == 'Items'
    assert [(chip.kind, chip.label) for chip in outcome.interpretation.chips] == [
        ('stat', 'Aggro %'),
        ('item_type', 'Weapon Crysta'),
    ]
    item_type = next(chip for chip in outcome.interpretation.chips if chip.kind == 'item_type')
    assert outcome.interpretation.query_without(item_type.id) == 'aggro'


def test_real_exact_guardian_does_not_fall_back_to_losing_item_chips() -> None:
    outcome = search_database(
        'Universal',
        'Guardian',
        items_path=ITEM_DATABASE,
        skills_path=SKILL_DATABASE,
    )
    assert outcome.skills is not None
    assert any(row.skill.name.casefold() == 'guardian' for row in outcome.skills.results)
    assert outcome.interpretation is None
```

The second test encodes the approved rule that the winning exact route can suppress chip display entirely rather than exposing another domain's interpretation.

- [ ] **Step 2: Run real-database tests**

Run:

```bash
python -m pytest tests/test_real_databases.py -q
```

Expected: all real-database tests pass, including the duplicate-item-ID regression and new interpretation assertions.

- [ ] **Step 3: Run the full test suite**

Run:

```bash
python -m pytest -q
```

Expected: all tests pass with no skips other than any environment-conditional real-database skip already present in the repository.

- [ ] **Step 4: Compile all application Python sources**

Run:

```bash
python -m compileall -q main.py toram_search ui
```

Expected: exit code 0 and no output.

- [ ] **Step 5: Verify database files are untouched**

Run:

```bash
git diff --exit-code "$(git merge-base HEAD origin/main)" -- items.sqlite skills.sqlite
```

Expected: exit code 0 and no diff.

Also inspect the branch file list:

```bash
git diff --name-only "$(git merge-base HEAD origin/main)"..HEAD
```

Expected: only source, test, design, and plan files related to query interpretation chips; no unrelated refactors and no SQLite changes.

- [ ] **Step 6: Commit the final real-database regression coverage**

```bash
git add tests/test_real_databases.py
git commit -m "test: cover query interpretation on real databases"
```

- [ ] **Step 7: Re-run final verification after the last commit**

Run again on the exact final branch head:

```bash
python -m pytest -q
python -m compileall -q main.py toram_search ui
git diff --exit-code "$(git merge-base HEAD origin/main)" -- items.sqlite skills.sqlite
```

Expected: full suite green, compileall green, and no database diff.

---

## Final Review Checklist

Before declaring the branch ready for integration, verify all of the following against `docs/superpowers/specs/2026-08-14-query-interpretation-chips-design.md`:

- Item stat/type/rank and numeric-comparison chips are produced from executed parser decisions.
- `aggro xtal wp` reconstructs to `aggro` or `weapon xtal` as specified when the corresponding chip is removed.
- `highest cr bow` removes dependent rank when the stat is removed.
- `hp >= 5000 armor` uses one atomic numeric chip.
- Boolean item expressions reconstruct from the parsed AST, including AND/OR collapse.
- Skill tree, ailment, MP max, required-level max, and MP ranking are covered.
- Skill tier/skill-type/weapon structured routes do not emit misleading partial chips.
- Exact/fuzzy/help/refusal/clarify/suggest routes do not render chips.
- Universal winner selection uses route quality + specificity + stable final tie-break, never result count.
- A winning exact route with no eligible chips yields no chips rather than falling back to the other domain.
- Chip removal is fill-only, clears prior results/chips, resets limits, and does not change `last_submission_nonce`.
- Existing example/correction fill-only behavior and iframe external-value synchronization still pass.
- Existing structured Universal routing and duplicate-item-card fixes remain green.
- No database file changes.

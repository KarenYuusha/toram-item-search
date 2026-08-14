# Query Interpretation Chips Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic removable query-interpretation chips below the Streamlit search box, sourced from the same parser decisions that drive item/skill search, with semantic fill-only reconstruction and deterministic Universal-domain selection.

**Architecture:** Add a small domain-neutral model for chip metadata and route quality. Item and skill services attach metadata from their existing parse branches; domain-specific helper modules precompute safe canonical queries for each chip removal. The top-level router selects one winning interpretation, and Streamlit only renders buttons and applies the returned fill-only query.

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

- Create `toram_search/interpretation.py` — immutable chip, interpretation, and route-quality types with no domain imports.
- Create `toram_search/items/interpretation.py` — item canonicalization and semantic reconstruction from resolved stat/filter or parsed expression objects.
- Modify `toram_search/items/filters.py` — expose canonical item-type text.
- Modify `toram_search/items/models.py` — attach optional interpretation and route quality while retaining `routing_confidence`.
- Modify `toram_search/items/service.py` — attach item metadata from existing branches.
- Create `toram_search/skills/interpretation.py` — canonical reconstruction for supported skill filters.
- Modify `toram_search/skills/models.py` and `toram_search/skills/service.py` — attach skill metadata from existing branches.
- Modify `toram_search/models.py` and `toram_search/router.py` — expose/select one winning interpretation.
- Create `ui/interpretation.py` and modify `main.py` — render chips and apply fill-only state changes.
- Create `tests/test_interpretation.py`; modify item, skill, Universal, AppTest, UI-contract, and real-database tests.

---

### Task 1: Shared interpretation and route-quality model

**Files:**
- Create: `toram_search/interpretation.py`
- Create: `tests/test_interpretation.py`

**Interfaces:**
- Produces `QueryChip`, `QueryInterpretation`, `RouteQuality`, `ChipKind`, `SearchDomain`, `RouteFamily`.
- `QueryInterpretation.query_without(chip_id: str) -> str` is the only reconstruction call used by UI code.
- `RouteQuality.sort_key -> tuple[int, int, int]` is the only quality ordering used by Universal selection.

- [ ] **Step 1: Write failing shared-model tests**

Create `tests/test_interpretation.py`:

```python
import pytest

from toram_search.interpretation import QueryChip, QueryInterpretation, RouteQuality


def test_query_interpretation_returns_precomputed_removal_query() -> None:
    interpretation = QueryInterpretation(
        domain='Items',
        canonical_query='highest critical rate bow',
        chips=(
            QueryChip('rank', 'rank', 'Highest', 'highest', 'critical rate bow', ('stat',)),
            QueryChip('stat', 'stat', 'Critical Rate', 'critical rate', 'bow'),
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
    assert RouteQuality('exact', True, 1).sort_key > RouteQuality('structured', True, 9).sort_key
    assert RouteQuality('structured', True, 1).sort_key > RouteQuality('structured', False, 9).sort_key
    assert RouteQuality('structured', False, 1).sort_key > RouteQuality('weak', True, 99).sort_key
    assert RouteQuality('weak', True, 1).sort_key > RouteQuality('none', False, 99).sort_key


def test_route_quality_uses_specificity_only_after_route_family() -> None:
    broad = RouteQuality('structured', True, 1)
    narrow = RouteQuality('structured', True, 3)
    assert narrow.sort_key > broad.sort_key
```

- [ ] **Step 2: Confirm RED**

Run:

```bash
python -m pytest tests/test_interpretation.py -q
```

Expected: import/collection failure because `toram_search.interpretation` does not exist.

- [ ] **Step 3: Implement the shared model exactly**

Create `toram_search/interpretation.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ChipKind = Literal[
    'stat', 'item_type', 'numeric_stat', 'rank',
    'skill_tree', 'ailment', 'mp', 'required_level',
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

- [ ] **Step 4: Confirm GREEN**

```bash
python -m pytest tests/test_interpretation.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add toram_search/interpretation.py tests/test_interpretation.py
git commit -m "feat: add query interpretation model"
```

---

### Task 2: Item interpretations and AST-based reconstruction

**Files:**
- Create: `toram_search/items/interpretation.py`
- Modify: `toram_search/items/filters.py`
- Modify: `toram_search/items/models.py`
- Modify: `toram_search/items/service.py`
- Modify: `tests/test_item_search.py`

**Interfaces:**
- `ItemTypeFilter` gains `canonical_text: str`.
- `build_simple_item_interpretation(stat: str, item_filter: ItemTypeFilter | None, rank_direction: str | None, negative_stat: bool) -> QueryInterpretation`.
- `build_expression_item_interpretation(expr: ParsedStatExpression) -> QueryInterpretation`.
- `ItemSearchOutcome` gains `interpretation: QueryInterpretation | None` and `route_quality: RouteQuality` after the existing fields.

- [ ] **Step 1: Add failing item tests**

Append to `tests/test_item_search.py`:

```python
def test_item_interpretation_for_aggro_weapon_crysta_is_canonical_and_removable(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('aggro xtal wp')
    finally:
        service.close()
    interpretation = outcome.interpretation
    assert interpretation is not None
    assert [(c.kind, c.label) for c in interpretation.chips] == [
        ('stat', 'Aggro %'),
        ('item_type', 'Weapon Crysta'),
    ]
    item_type = next(c for c in interpretation.chips if c.kind == 'item_type')
    stat = next(c for c in interpretation.chips if c.kind == 'stat')
    assert interpretation.query_without(item_type.id) == 'aggro'
    assert interpretation.query_without(stat.id) == 'weapon xtal'


def test_rank_chip_depends_on_stat_and_reconstructs_canonically(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('highest cr bow')
    finally:
        service.close()
    interpretation = outcome.interpretation
    assert interpretation is not None
    assert [(c.kind, c.label) for c in interpretation.chips] == [
        ('rank', 'Highest'), ('stat', 'Critical Rate'), ('item_type', 'Bow'),
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
        ('numeric_stat', 'MaxHP ≥ 5000'), ('item_type', 'Armor'),
    ]
    assert interpretation.query_without(interpretation.chips[0].id) == 'armor'


def test_boolean_expression_removal_rebuilds_from_ast(tmp_path: Path) -> None:
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


def test_or_expression_removal_drops_empty_or_group(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('hp > 5000 or cr bow')
    finally:
        service.close()
    interpretation = outcome.interpretation
    assert interpretation is not None
    hp_chip = next(c for c in interpretation.chips if c.label == 'MaxHP > 5000')
    assert interpretation.query_without(hp_chip.id) == 'critical rate bow'


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

- [ ] **Step 2: Confirm RED**

```bash
python -m pytest tests/test_item_search.py -q
```

Expected: new tests fail because interpretation/quality fields do not exist.

- [ ] **Step 3: Add canonical item-type metadata**

Modify `toram_search/items/filters.py`:

```python
@dataclass(frozen=True)
class ItemTypeFilter:
    label: str
    item_types: tuple[str, ...]
    consumed_text: str
    canonical_text: str


_CANONICAL_SPECIAL = {
    'Weapon Crysta': 'weapon xtal',
    'Armor Crysta': 'armor xtal',
    'Additional Crysta': 'additional xtal',
    'Special Crysta': 'ring xtal',
    'All Crysta': 'xtal',
    'Main Weapons': 'weapon',
}
```

Keep `_candidates()` matching behavior unchanged. In `extract_item_filter()`, replace the 3-field construction with:

```python
canonical = _CANONICAL_SPECIAL.get(label, normalize_stat_text(label))
return ItemTypeFilter(label, types, phrase, canonical), ' '.join(remaining)
```

This turns every alias that resolves to `Weapon Crysta` into canonical `weapon xtal` without changing which rows are searched.

- [ ] **Step 4: Extend `ItemSearchOutcome`**

Add imports and fields in `toram_search/items/models.py`:

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

- [ ] **Step 5: Implement `toram_search/items/interpretation.py`**

Create the file with these helpers and bodies:

```python
from __future__ import annotations

from typing import cast

from toram_search.interpretation import QueryChip, QueryInterpretation
from .aliases import normalize_stat_text
from .filters import ItemTypeFilter
from .models import ParsedClause, ParsedStatExpression

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


def _join(parts: list[str]) -> str:
    return ' '.join(part for part in parts if part).strip()


def _clause_fragment(clause: ParsedClause) -> str:
    stat = _stat_fragment(clause.typed_stat)
    if clause.explicit_comparison:
        return f'{stat} {clause.operator} {_number(clause.value)}'
    return stat


def _clause_label(clause: ParsedClause) -> str:
    if not clause.explicit_comparison:
        return clause.typed_stat
    symbol = {'>=': '≥', '<=': '≤', '==': '=', '=': '='}.get(clause.operator, clause.operator)
    return f'{clause.typed_stat} {symbol} {_number(clause.value)}'


def build_simple_item_interpretation(
    stat: str,
    item_filter: ItemTypeFilter | None,
    rank_direction: str | None,
    negative_stat: bool,
) -> QueryInterpretation:
    stat_kind = 'numeric_stat' if negative_stat else 'stat'
    stat_label = f'{stat} ≤ -1' if negative_stat else stat
    stat_fragment = f'{_stat_fragment(stat)} <= -1' if negative_stat else _stat_fragment(stat)
    semantic = []
    if rank_direction is not None:
        semantic.append(('rank', 'rank', 'Lowest' if rank_direction == 'asc' else 'Highest', 'lowest' if rank_direction == 'asc' else 'highest'))
    semantic.append(('stat', stat_kind, stat_label, stat_fragment))
    if item_filter is not None:
        semantic.append(('item_type', 'item_type', item_filter.label, item_filter.canonical_text))

    def rebuild_without(chip_id: str) -> str:
        removed = {chip_id}
        if chip_id == 'stat':
            removed.add('rank')
        return _join([fragment for part_id, _kind, _label, fragment in semantic if part_id not in removed])

    chips = tuple(
        QueryChip(
            part_id,
            kind,
            label,
            fragment,
            rebuild_without(part_id),
            ('stat',) if part_id == 'rank' else (),
        )
        for part_id, kind, label, fragment in semantic
    )
    return QueryInterpretation('Items', _join([row[3] for row in semantic]), chips)


def _rebuild_expression(
    expr: ParsedStatExpression,
    removed_clause: tuple[int, int] | None,
    remove_filter: bool,
) -> str:
    groups = []
    for group_index, group in enumerate(expr.groups):
        clauses = []
        for clause_index, clause in enumerate(group.clauses):
            if removed_clause == (group_index, clause_index):
                continue
            clauses.append(_clause_fragment(clause))
        if clauses:
            groups.append(' and '.join(clauses))
    expression = ' or '.join(groups)
    item_filter = None if remove_filter else cast(ItemTypeFilter | None, expr.item_filter)
    return _join([expression, item_filter.canonical_text if item_filter is not None else ''])


def build_expression_item_interpretation(expr: ParsedStatExpression) -> QueryInterpretation:
    chips = []
    for group_index, group in enumerate(expr.groups):
        for clause_index, clause in enumerate(group.clauses):
            chip_id = f'clause_{group_index}_{clause_index}'
            chips.append(QueryChip(
                chip_id,
                'numeric_stat' if clause.explicit_comparison else 'stat',
                _clause_label(clause),
                _clause_fragment(clause),
                _rebuild_expression(expr, (group_index, clause_index), False),
            ))
    item_filter = cast(ItemTypeFilter | None, expr.item_filter)
    if item_filter is not None:
        chips.append(QueryChip(
            'item_type',
            'item_type',
            item_filter.label,
            item_filter.canonical_text,
            _rebuild_expression(expr, None, True),
        ))
    return QueryInterpretation('Items', _rebuild_expression(expr, None, False), tuple(chips))
```

The helper reconstructs AND/OR from the parsed AST, so removing a clause can never leave a dangling boolean operator.

- [ ] **Step 6: Attach item metadata from the existing search branches**

In `ItemSearchService.search()`, after computing `raw`, define a local outcome factory so every branch assigns quality consistently:

```python
def finish(
    kind,
    results=(),
    message=None,
    suggested_queries=(),
    routing_confidence='none',
    family='none',
    specificity=0,
    interpretation=None,
):
    return ItemSearchOutcome(
        kind,
        raw,
        results,
        message,
        suggested_queries,
        routing_confidence,
        interpretation,
        RouteQuality(family, bool(results), specificity),
    )
```

Import `RouteQuality`, `build_simple_item_interpretation`, and `build_expression_item_interpretation`. Convert the existing return sites to `finish()` without changing their result/message values. Apply this exact metadata mapping:

```text
empty/unrecognized                      family=none, specificity=0
exact item name                         family=exact, specificity=1
exact upgrade target                    family=exact, specificity=1
fuzzy upgrade target                    family=structured, specificity=1
help/meta/refuse                        family=structured, specificity=0, interpretation=None
clarify/suggest/unsafe structured parse family=structured, specificity=max(1, recognized constraints), interpretation=None
fuzzy item-name fallback                family=weak, specificity=0, interpretation=None
```

For the simple stat branch, after sorting/grouping rows:

```python
interpretation = build_simple_item_interpretation(stat, item_filter, rank_direction, negative_stat)
specificity = 1 + int(item_filter is not None) + int(rank_direction is not None)
return finish(
    'results' if cards else 'not_found',
    cards,
    None if cards else 'No matching items found.',
    routing_confidence='strong',
    family='structured',
    specificity=specificity,
    interpretation=interpretation,
)
```

For the parsed expression branch, after unknown-stat validation:

```python
rows = self.repository.search_expression(expr)
cards = tuple(ItemCardResult(i, m) for i, m, _score in rows)
clause_count = sum(len(group.clauses) for group in expr.groups)
specificity = clause_count + int(expr.item_filter is not None)
return finish(
    'results' if cards else 'not_found',
    cards,
    None if cards else 'No matching items found.',
    routing_confidence='strong',
    family='structured',
    specificity=specificity,
    interpretation=build_expression_item_interpretation(expr),
)
```

Do not change existing `routing_confidence`; Universal weak-skill suppression still uses it.

- [ ] **Step 7: Confirm item GREEN**

```bash
python -m pytest tests/test_item_search.py -q
```

Expected: all old and new item tests pass, including duplicate-stat grouping and `aggro xtal wp` routing.

- [ ] **Step 8: Commit**

```bash
git add toram_search/items/interpretation.py toram_search/items/filters.py \
  toram_search/items/models.py toram_search/items/service.py tests/test_item_search.py
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
- `build_skill_interpretation(tree_name: str | None, ailment: str | None, mp_cost_max: int | None, required_level_max: int | None, mp_rank_direction: str | None, count_mode: bool, unsupported_structured_component: bool) -> QueryInterpretation | None`.
- The helper receives only values already resolved by `SkillSearchService`; it does not parse raw text.
- `SkillSearchOutcome` gains `interpretation` and `route_quality` fields after existing fields.

- [ ] **Step 1: Add failing skill tests**

Append to `tests/test_skill_search.py`:

```python
def test_skill_tree_query_exposes_tree_chip(tmp_path: Path) -> None:
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
    assert outcome.interpretation is not None
    assert [(c.kind, c.label) for c in outcome.interpretation.chips] == [('ailment', 'Stun')]


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
    assert [(c.kind, c.label) for c in level.interpretation.chips] == [('required_level', 'Required Level ≤ 20')]


def test_lowest_mp_tree_ranking_uses_atomic_rank_field_chip(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    try:
        outcome = service.search('lowest mp shield skills')
    finally:
        service.close()
    interpretation = outcome.interpretation
    assert interpretation is not None
    assert [(c.kind, c.label) for c in interpretation.chips] == [
        ('rank', 'Lowest MP'), ('skill_tree', 'Shield Skills'),
    ]
    assert interpretation.query_without(interpretation.chips[0].id) == 'shield skills'
    assert interpretation.query_without(interpretation.chips[1].id) == 'lowest mp'


def test_exact_skill_has_quality_but_no_chips(tmp_path: Path) -> None:
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

- [ ] **Step 2: Confirm RED**

```bash
python -m pytest tests/test_skill_search.py -q
```

Expected: new metadata assertions fail.

- [ ] **Step 3: Extend `SkillSearchOutcome`**

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

- [ ] **Step 4: Implement `toram_search/skills/interpretation.py` exactly**

```python
from __future__ import annotations

from toram_search.interpretation import QueryChip, QueryInterpretation


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
    if unsupported_structured_component:
        return None

    semantic = []
    if mp_rank_direction is not None:
        descending = mp_rank_direction == 'desc'
        semantic.append((
            'rank_mp', 'rank', 'Highest MP' if descending else 'Lowest MP',
            'highest mp' if descending else 'lowest mp',
        ))
    if ailment is not None:
        semantic.append(('ailment', 'ailment', ailment, f'inflict {ailment.casefold()}'))
    if mp_cost_max is not None:
        semantic.append(('mp', 'mp', f'MP ≤ {mp_cost_max}', f'mp <= {mp_cost_max}'))
    if required_level_max is not None:
        semantic.append((
            'required_level', 'required_level',
            f'Required Level ≤ {required_level_max}',
            f'required level <= {required_level_max}',
        ))
    if tree_name is not None:
        semantic.append(('skill_tree', 'skill_tree', tree_name, tree_name.casefold()))
    if not semantic:
        return None

    def canonical(fragments: list[str]) -> str:
        if not fragments:
            return ''
        body = ' '.join(fragments)
        return f'how many skills {body}' if count_mode else body

    chips = tuple(
        QueryChip(
            part_id,
            kind,
            label,
            fragment,
            canonical([row[3] for row in semantic if row[0] != part_id]),
        )
        for part_id, kind, label, fragment in semantic
    )
    return QueryInterpretation('Skills', canonical([row[3] for row in semantic]), chips)
```

`Lowest MP` / `Highest MP` is atomic because bare MP is not a filter in the existing tree-ranking route. This avoids a chip that would claim a filter the parser did not execute.

- [ ] **Step 5: Attach skill metadata from the existing search branches**

In `SkillSearchService.search()`, define a local factory after `raw`/`norm`:

```python
def finish(
    kind,
    results=(),
    message=None,
    suggested_queries=(),
    family='none',
    specificity=0,
    interpretation=None,
):
    return SkillSearchOutcome(
        kind,
        raw,
        results,
        message,
        suggested_queries,
        interpretation,
        RouteQuality(family, bool(results), specificity),
    )
```

Convert current return sites to `finish()` without changing results/messages. Apply:

```text
exact skill / exact property / compare -> family=exact, interpretation=None
refuse                               -> family=structured, interpretation=None
RapidFuzz / lexical fallback        -> family=weak, interpretation=None
strict no-match / final no-match    -> family=none, interpretation=None
```

For `structured_filter`, derive only from its existing values:

```python
unsupported = bool(
    structured_filter.tiers
    or structured_filter.skill_types
    or structured_filter.weapons
)
tree_name = None
if structured_filter.tree_ids:
    tree_name = self.repository.get_tree(structured_filter.tree_ids[0]).name
interpretation = build_skill_interpretation(
    tree_name=tree_name,
    ailment=structured_filter.ailments[0] if structured_filter.ailments else None,
    mp_cost_max=structured_filter.mp_cost_max,
    required_level_max=structured_filter.required_level_max,
    count_mode=norm.startswith('how many'),
    unsupported_structured_component=unsupported,
)
specificity = (
    len(structured_filter.tree_ids)
    + len(structured_filter.tiers)
    + len(structured_filter.skill_types)
    + len(structured_filter.ailments)
    + len(structured_filter.weapons)
    + int(structured_filter.mp_cost_max is not None)
    + int(structured_filter.required_level_max is not None)
)
```

Use that `interpretation` and `specificity` in the existing explicit-filter result/count return.

For the existing tree branch, use:

```python
if 'mp' in norm and any(x in norm for x in ('lowest', 'least', 'highest')):
    direction = 'desc' if 'highest' in norm else 'asc'
    rows = self.analytics.rank('mp_cost_value', direction, filters=SkillFilter(tree_ids=(tree.id,)), limit=20)
    interpretation = build_skill_interpretation(tree_name=tree.name, mp_rank_direction=direction)
    return finish('results', self._cards(rows, 'mp_cost_value'), family='structured', specificity=2, interpretation=interpretation)

rows = self.repository.list_skills_in_tree(tree.id)
return finish(
    'results' if rows else 'not_found',
    self._cards(rows),
    None if rows else 'No matching skills found.',
    family='structured',
    specificity=1,
    interpretation=build_skill_interpretation(tree_name=tree.name),
)
```

For the existing ailment fallback branch, pass `ailment=canonical`, family `structured`, specificity `1`. For the global MP ranking branch, pass `mp_rank_direction=direction`, family `structured`, specificity `1`.

Do not change `allow_weak_fallback` behavior.

- [ ] **Step 6: Confirm skill GREEN**

```bash
python -m pytest tests/test_skill_search.py -q
```

Expected: all current and new skill tests pass.

- [ ] **Step 7: Commit**

```bash
git add toram_search/skills/interpretation.py toram_search/skills/models.py \
  toram_search/skills/service.py tests/test_skill_search.py
git commit -m "feat: expose skill query interpretations"
```

---

### Task 4: Deterministic Universal winner selection

**Files:**
- Modify: `toram_search/models.py`
- Modify: `toram_search/router.py`
- Modify: `tests/test_universal.py`

**Interfaces:**
- `UniversalSearchOutcome` gains `interpretation: QueryInterpretation | None`.
- `select_winning_interpretation(items: ItemSearchOutcome | None, skills: SkillSearchOutcome | None) -> QueryInterpretation | None` selects by quality only.
- Existing item-first execution and item `routing_confidence` weak-skill suppression remain unchanged.

- [ ] **Step 1: Add failing Universal tests**

Add to `tests/test_universal.py`:

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


def test_exact_winner_with_no_chips_does_not_fall_back_to_other_domain() -> None:
    item = ItemSearchOutcome(
        'results', 'shared',
        route_quality=RouteQuality('structured', True, 3),
        interpretation=_interp('Items', 'Critical Rate'),
    )
    skill = SkillSearchOutcome(
        'results', 'shared',
        route_quality=RouteQuality('exact', True, 1),
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

Raw result count is deliberately absent from the selector's inputs and sort key; the tests fabricate outcomes with explicit route quality so adding more result cards cannot affect winner selection.

- [ ] **Step 2: Confirm RED**

```bash
python -m pytest tests/test_universal.py -q
```

Expected: failures for missing top-level interpretation/selector.

- [ ] **Step 3: Extend the top-level outcome**

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

- [ ] **Step 4: Add the selector**

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
    return max(candidates, key=lambda row: (row[0], row[1]))[2]
```

The second tuple value is only the final stable tie-break after result tier, route family, and specificity are identical. It never depends on result count.

- [ ] **Step 5: Wire the selector into all database modes**

Replace the current return construction with the same search calls plus interpretation metadata:

```python
if mode == 'Universal':
    items = _search_items(query, items_path)
    skills = _search_skills(
        query,
        skills_path,
        allow_weak_fallback=items.routing_confidence != 'strong',
    )
    return UniversalSearchOutcome(
        query=query,
        items=items,
        skills=skills,
        interpretation=select_winning_interpretation(items, skills),
    )
if mode == 'Items':
    items = _search_items(query, items_path)
    return UniversalSearchOutcome(query=query, items=items, interpretation=items.interpretation)
skills = _search_skills(query, skills_path)
return UniversalSearchOutcome(query=query, skills=skills, interpretation=skills.interpretation)
```

- [ ] **Step 6: Confirm Universal GREEN**

```bash
python -m pytest tests/test_universal.py -q
```

Expected: all tests pass, including existing `aggro xtal wp`, exact skill, and weak FTS regressions.

- [ ] **Step 7: Commit**

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
- Verify unchanged behavior: `tests/test_search_component.py`

**Interfaces:**
- `render_query_interpretation(interpretation: QueryInterpretation | None) -> str | None` returns a precomputed fill-only query or `None`.
- `main.py` owns session-state clearing/reset; the renderer owns only presentation/click detection.

- [ ] **Step 1: Add failing UI/AppTest coverage**

Append to `tests/test_ui_contract.py`:

```python
def test_query_interpretation_renders_after_search_box_before_results() -> None:
    source = text('main.py')
    assert 'render_query_interpretation' in source
    assert source.index('submission=render_search_box') < source.index('render_query_interpretation')
    assert source.index('render_query_interpretation') < source.index('st.divider()')


def test_chip_removal_clears_outcome_instead_of_submitting() -> None:
    source = text('main.py')
    block = source[source.index('chip_fill='):source.index('st.divider()')]
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
            QueryChip('rank', 'rank', 'Highest', 'highest', 'critical rate bow', ('stat',)),
            QueryChip('stat', 'stat', 'Critical Rate', 'critical rate', 'bow'),
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

The existing `tests/test_search_component.py::test_external_fill_syncs_when_streamlit_value_changes_even_if_input_keeps_focus` remains the visible-input synchronization regression.

- [ ] **Step 2: Confirm RED**

```bash
python -m pytest tests/test_app_shell.py tests/test_ui_contract.py -q
```

Expected: new renderer/state tests fail.

- [ ] **Step 3: Implement the renderer**

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

- [ ] **Step 4: Integrate directly below the search box**

Import:

```python
from ui.interpretation import render_query_interpretation
```

After the existing submit/`search_database()` block and before the existing results divider, use:

```python
outcome: UniversalSearchOutcome | None = st.session_state.last_outcome
chip_fill = render_query_interpretation(outcome.interpretation if outcome is not None else None)
if chip_fill is not None:
    st.session_state.query = chip_fill
    st.session_state.last_outcome = None
    st.session_state.item_limit = 20
    st.session_state.skill_limit = 20
    st.rerun()
```

Then leave the current `if outcome is not None:` result-rendering block unchanged. Do not assign `chip_fill` to `query_to_run`, do not call `search_database()` in this branch, and do not change `last_submission_nonce`.

- [ ] **Step 5: Confirm UI GREEN and fill-only regressions**

```bash
python -m pytest tests/test_app_shell.py tests/test_ui_contract.py tests/test_search_component.py -q
```

Expected: all tests pass, including examples, corrections, and external iframe fill synchronization.

- [ ] **Step 6: Commit**

```bash
git add ui/interpretation.py main.py tests/test_app_shell.py tests/test_ui_contract.py
git commit -m "feat: add removable query interpretation chips"
```

---

### Task 6: Real-database regressions and final verification

**Files:**
- Modify: `tests/test_real_databases.py`
- Verify unchanged: `items.sqlite`, `skills.sqlite`

**Interfaces:**
- Exercises the complete public `search_database()` path on committed databases.

- [ ] **Step 1: Add real-database tests**

Append to `tests/test_real_databases.py`:

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


def test_real_exact_guardian_has_no_interpretation_chips() -> None:
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

- [ ] **Step 2: Run real-database tests**

```bash
python -m pytest tests/test_real_databases.py -q
```

Expected: all pass, including the duplicate-item-ID regression.

- [ ] **Step 3: Commit real-database coverage**

```bash
git add tests/test_real_databases.py
git commit -m "test: cover query interpretation on real databases"
```

- [ ] **Step 4: Run the exact final test suite**

```bash
python -m pytest -q
```

Expected: full suite passes.

- [ ] **Step 5: Compile application Python**

```bash
python -m compileall -q main.py toram_search ui
```

Expected: exit code 0, no output.

- [ ] **Step 6: Verify database files and branch scope**

```bash
git diff --exit-code "$(git merge-base HEAD origin/main)" -- items.sqlite skills.sqlite
git diff --name-only "$(git merge-base HEAD origin/main)"..HEAD
```

Expected: first command has no diff; second lists only query-interpretation source/tests/docs and no unrelated application files.

- [ ] **Step 7: Fresh final verification after all commits**

```bash
python -m pytest -q
python -m compileall -q main.py toram_search ui
git diff --exit-code "$(git merge-base HEAD origin/main)" -- items.sqlite skills.sqlite
```

Expected: tests green, compileall green, databases unchanged.

---

## Final Review Checklist

- Item stat/type/rank and numeric-comparison chips come from executed parser decisions.
- `aggro xtal wp` reconstructs to `aggro` or `weapon xtal` for the corresponding removal.
- Removing `Critical Rate` from `highest cr bow` also removes dependent `Highest` and produces `bow`.
- `hp >= 5000 armor` is one atomic numeric chip plus Armor.
- Item AND/OR reconstruction uses `ParsedStatExpression`, not raw deletion.
- Skill tree, ailment, MP max, required-level max, and MP ranking are covered.
- Tier/skill-type/weapon skill routes do not emit partial chips.
- Exact/fuzzy/help/refusal/clarify/suggest routes do not render chips.
- Universal selection uses route quality and specificity, never result count.
- A winning route with no eligible chips yields no chips rather than using the losing domain.
- Chip removal is fill-only, clears old results/chips, resets limits, and leaves submission nonce unchanged.
- Existing example/correction fill-only behavior and iframe external-value synchronization still pass.
- Existing Universal routing and duplicate-item-card fixes remain green.
- `items.sqlite` and `skills.sqlite` are unchanged.

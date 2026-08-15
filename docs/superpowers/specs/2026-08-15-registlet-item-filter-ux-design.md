# Registlet Item Filtering and Focused UX Improvements

Date: 2026-08-15
Status: Approved design
Repository: `KarenYuusha/toram-item-search`

## 1. Purpose

The current `items.sqlite` contains rows whose `item_type` is `Regislet` (and may contain the alternate spelling `Registlet`). Those rows do not belong to the Item search domain because Registlet data is maintained separately in `registlets.json`.

This change has two goals:

1. Make Registlet data authoritative to `registlets.json` and prevent contaminated Registlet rows from appearing anywhere in Item behavior.
2. Improve the Food and Registlet user experience with a small set of focused UI changes, without redesigning the application.

No source database or data file will be edited as part of this feature.

## 2. Source-of-truth rules

### 2.1 Items

`items.sqlite` remains the source of truth for the Item domain, except rows whose `item_type` identifies them as Registlets.

The Item repository must treat these item types as excluded, case-insensitively:

- `Regislet`
- `Registlet`

Whitespace around the value does not affect the exclusion.

Excluded rows are treated as if they do not exist in the Item domain.

### 2.2 Registlets

`registlets.json` is the only source of truth for Registlet search and Registlet display.

The Registlet domain must never read Registlet records from `items.sqlite`.

Skill-to-Registlet relationships continue to use `registlets.json` and its curated `affects_skill` data.

## 3. Item repository filtering

The exclusion belongs at the Item repository boundary rather than in the Universal router or result renderer. This guarantees that all Item-facing behavior sees the same filtered dataset.

The filter applies to:

- listing items;
- exact item-name matching;
- fuzzy item-name matching;
- stat searches;
- structured/stat-expression searches;
- item counts;
- counts by item type;
- counts by stat;
- item-type discovery;
- Item autocomplete;
- Universal Item routing;
- upgrade predecessor/successor lookups when the referenced row is excluded.

`get_item()` must not expose an excluded Registlet row. Direct `get_item()` access to an excluded id raises `KeyError`, the same as an id unavailable to the Item domain.

Upgrade predecessor/successor lists omit excluded Registlet rows entirely; they must not turn those filtered references into `Unknown item` placeholders.

The database remains read-only and unchanged.

## 4. Universal routing behavior

Universal search keeps the existing four-domain architecture:

- Items
- Skills
- Food
- Registlets

The router does not need a special "remove Registlets from Items" rule. The Item service simply receives an already-filtered Item repository view.

Examples:

- A Registlet name present in both `items.sqlite` and `registlets.json` may only surface through the Registlet outcome.
- A stat query must not include `item_type=Regislet` rows in Item results.
- Item autocomplete must not suggest contaminated Registlet item names.
- Registlet search continues to use Stoodie level, Registlet name, and effect text from `registlets.json` only.

## 5. Registlet result UX

### 5.1 Match reason

Each Registlet result explains why it matched.

Supported labels:

- `Matched by name`
- `Matched by effect: <normalized query>`
- `Matched by Stoodie Lv<N>`
- `Matched by fuzzy name`

For example, an effect search for `physical pierce` displays:

`Matched by effect: physical pierce`

The label is explanatory UI metadata only. It must not change ranking or search semantics.

### 5.2 Stoodie levels

Stoodie source levels are shown as compact, visually scannable level badges/chips rather than a long undifferentiated text line.

Example:

`Lv70  Lv90  Lv110  Lv130  Lv220`

The underlying source levels and ordering remain unchanged.

### 5.3 Result card hierarchy

A Registlet card prioritizes information in this order:

1. Registlet name
2. match reason
3. max Registlet level
4. effect text
5. Stoodie source levels
6. affected Skills, when present

No effect text is rewritten or inferred.

## 6. Food result UX

### 6.1 Group by Food level

Food results for a stat are grouped by Food level, highest level first.

Example:

```text
MaxMP

Lv10
51110000
9090903

Lv8
8024545
```

Multiple codes at the same level remain separate entries.

### 6.2 Copy-code action

Each displayed Food code provides an explicit copy action.

The copy action copies only the numeric Food code. It must not trigger a search, change the query, or clear results.

If the pinned Streamlit version has no suitable native clipboard control, the implementation uses the smallest existing-compatible UI mechanism needed to provide the action. It must not add a large frontend framework.

## 7. Suggested-search UX

The current Universal page shows many suggested-search buttons at once. Reduce this visual crowding while keeping examples useful.

### 7.1 Universal

Show exactly three representative examples rather than five. The three examples together cover different domains:

- one Item/stat query;
- one Food or Stoodie query;
- one Skill or Registlet-effect query.

Use a static deterministic set for the first implementation.

### 7.2 Domain modes

Keep domain-specific examples, with at most three visible examples per mode so they fit more comfortably on desktop and mobile widths.

All example buttons remain fill-only. Clicking an example must never execute a search automatically.

## 8. Search guidance near the input

Keep the full Search Help in the sidebar, and add a short syntax hint near the search box so users do not have to open Help for common patterns.

Example Universal hint:

`Try: cr bow · food maxmp · std 220 · physical pierce`

The hint is informational only and remains compact.

The existing Help text must continue to explain:

- Food searches must begin with `food` or `code`;
- Food codes are results, not searchable input;
- Registlets can be searched by Stoodie level, name, or effect;
- Registlet data comes from `registlets.json`, not the Item database.

## 9. Error handling and source health

Filtering contaminated Item rows must not make `items.sqlite` unhealthy. They are valid database rows that are intentionally excluded from the Item domain.

Registlet health remains based on `registlets.json` validation.

If `registlets.json` is unavailable:

- Registlet mode is unavailable as today;
- Universal does not fall back to `items.sqlite` for Registlet data;
- contaminated `item_type=Regislet/Registlet` rows remain excluded from Items.

This prevents a missing JSON file from silently changing the source of Registlet truth.

## 10. Testing requirements

### 10.1 Item contamination regressions

Tests must prove that `Regislet` and `Registlet` item types are excluded case-insensitively from:

- exact Item search;
- fuzzy Item search;
- stat Item search;
- structured Item search;
- item counts;
- item-type lists;
- autocomplete;
- Universal Item results;
- direct `get_item()` access;
- upgrade predecessor/successor display.

A fixture includes a normal Item and a contaminated Registlet row with overlapping searchable content to prove the filter is not only cosmetic.

### 10.2 Registlet source authority

Tests must prove that:

- Registlet mode returns data from `registlets.json`;
- a Registlet present only as a contaminated Item row is not returned as a Registlet;
- when the same name exists in both sources, the displayed Registlet data comes from JSON;
- unavailable `registlets.json` does not reactivate contaminated Item rows.

### 10.3 UX contracts

Tests cover:

- Registlet match-reason metadata for name, effect, Stoodie, and fuzzy-name routes;
- effect match metadata carries the normalized effect query used for the label;
- Stoodie levels are exposed to the renderer as discrete values;
- Food results are grouped highest-level-first;
- every displayed Food code has a copy action;
- Food copy action does not submit a new search;
- suggested-search examples remain fill-only;
- Universal shows exactly three suggested searches;
- each domain mode shows at most three suggested searches;
- the near-search syntax hint and sidebar Help include the approved Food and Registlet rules.

### 10.4 Existing regressions

The full existing suite must remain green, including:

- `MAGIC: FINALE` weak Item suppression;
- Item structured routing;
- Food prefix gating;
- Registlet effect search;
- Stoodie-level search;
- Skill-to-Registlet relationship display;
- submit-only autocomplete and suggestion behavior.

## 11. Non-goals

This feature will not:

- delete or rewrite rows in `items.sqlite`;
- migrate Registlets into SQLite;
- infer Registlet relationships from effect text;
- add fuzzy effect matching;
- redesign the entire Streamlit layout;
- add an LLM, embeddings, or RAG;
- change Food query grammar;
- change Registlet search precedence beyond adding display metadata for the match reason.

## 12. Implementation boundaries

Expected implementation areas are limited to:

- Item repository filtering and related tests;
- Registlet outcome/result metadata needed for match-reason display;
- Food/Registlet renderers;
- suggested-search and help/hint UI;
- focused regression tests.

The router changes only if a small interface adjustment is required to carry Registlet match metadata. It must not regain domain-specific contamination filtering.

`items.sqlite`, `skills.sqlite`, `food_entries.csv`, `food_stat_aliases.json`, and `registlets.json` must remain unchanged by this feature.

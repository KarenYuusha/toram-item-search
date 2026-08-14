# Query Interpretation Chips Design

Date: 2026-08-14

## Summary

Add a deterministic query-interpretation layer to the existing Streamlit search UI. After a submitted structured query is parsed, the app shows removable interpretation chips directly below the search bar. The chips explain the structured filters the parser actually used and let the user remove individual filters without rewriting the entire query.

Removing a chip is fill-only: it reconstructs a valid canonical query, updates the search field, clears the previous results and interpretation, and waits for the user to press Enter/Search. It never automatically performs a database search.

This feature does not introduce an LLM, embeddings, new database schema, editable dropdown chips, or new search syntax.

## Goals

1. Make deterministic parser decisions visible to users.
2. Make structured searches easier to refine without retyping the full query.
3. Keep the interpretation shown in the UI identical to the interpretation that drove the search.
4. Preserve the current submit-only search behavior.
5. Keep Universal mode uncluttered by displaying only one winning domain interpretation.
6. Provide a reusable structured interpretation model for future refinement controls without coupling parsing logic to Streamlit.

## Non-goals

This feature will not add:

- auto-search when a chip is removed;
- editable chip dropdowns or replacement selectors;
- item/skill comparison mode;
- recent searches, favorites, or search history;
- new query operators or aliases solely for this feature;
- chips for exact item names, exact skill names, fuzzy name matches, help/meta queries, suggestions, clarifications, refusals, or unrecognized text;
- database migrations or modifications to `items.sqlite` or `skills.sqlite`;
- an LLM, RAG, embeddings, or probabilistic interpretation.

## User Experience

### Placement

Interpretation chips appear directly below the main search bar and before the results area.

They appear only after a submitted query has been parsed successfully as strong structured intent. Typing in the search field alone never creates or updates chips.

### Structured filters represented as chips

Only structured filters become chips. Supported semantic chip categories are:

- item stat;
- item type;
- ranking direction;
- numeric stat comparison;
- skill tree;
- ailment;
- MP filter;
- required-level filter.

Exact or fuzzy item/skill names do not become chips.

### Examples

Submitted query:

`aggro xtal wp`

Interpretation:

- `Aggro %`
- `Weapon Crysta`

Submitted query:

`highest cr bow`

Interpretation:

- `Highest`
- `Critical Rate`
- `Bow`

Submitted query:

`hp >= 5000 armor`

Interpretation:

- `MaxHP >= 5000`
- `Armor`

The visible chip labels may use human-friendly symbols such as `>=` rendered as `≥`, but canonical query reconstruction must use syntax already supported by the parser.

### Numeric comparisons are atomic

A numeric stat comparison is represented as one semantic chip rather than separate stat and comparison chips.

For example:

`hp >= 5000 armor`

becomes:

- `MaxHP ≥ 5000`
- `Armor`

This prevents a user from removing only `MaxHP` and leaving an invalid `>= 5000` fragment.

### Removing a chip

Removing a chip performs these steps in order:

1. Remove the selected semantic filter from the interpretation model.
2. Remove any filters that depend on the removed filter.
3. Reconstruct a valid canonical query from the remaining semantic parts.
4. Fill the search field with that canonical query.
5. Clear the previous search results.
6. Clear the previous interpretation chips.
7. Wait for the user to press Enter/Search.

No database search runs as part of chip removal.

Examples:

- `aggro xtal wp` -> remove `Weapon Crysta` -> search field becomes `aggro`.
- `highest cr bow` -> remove `Bow` -> search field becomes `highest critical rate`.
- `highest cr bow` -> remove `Critical Rate` -> dependent `Highest` is also removed -> search field becomes `bow`.
- `highest cr bow` -> remove `Highest` -> search field becomes `critical rate bow`.
- `hp >= 5000 armor` -> remove `MaxHP ≥ 5000` -> search field becomes `armor`.
- removing the final remaining structured chip -> search field becomes empty.

The reconstruction must be semantic. It must not be implemented by deleting raw substrings such as `wp` from the original user text.

## Architecture

### Approach

Use an explicit structured interpretation model in the search layer.

The item and skill search paths expose interpretation metadata alongside their existing search outcomes. The same deterministic parser decisions that drive a search produce the interpretation metadata. Streamlit renders that metadata but does not independently reparse the submitted query or infer intent from result rows.

This avoids two sources of truth and guarantees that the explanation shown to the user matches the actual search route.

### Domain-neutral interpretation model

Introduce a small domain-neutral model representing the structured interpretation of a submitted query. Exact names and weak fuzzy routes do not need interpretation chips.

Conceptually the model contains:

- domain: `Items` or `Skills`;
- strength/quality metadata used by Universal routing;
- canonical submitted query;
- ordered structured chips;
- dependency relationships between chips;
- deterministic reconstruction of the canonical query after one chip is removed.

Each chip must use a stable semantic type rather than relying on its visible label. Expected chip kinds include:

- `stat`;
- `item_type`;
- `numeric_stat`;
- `rank`;
- `skill_tree`;
- `ailment`;
- `mp`;
- `required_level`.

The exact Python type layout is an implementation detail for the plan, but the interface must allow the UI to render labels and request a canonical query with a selected chip removed without knowing parser internals.

### Dependencies

Dependencies are explicit in the interpretation model.

Example:

- `rank` depends on `stat` because `highest` or `lowest` is meaningless without a ranked field.
- removing a `stat` therefore removes its dependent `rank` chip automatically.
- `numeric_stat` is atomic and does not expose an independently removable comparison component.

The reconstruction layer must guarantee that every emitted query is syntactically valid according to current supported query syntax.

### Search outcomes

Actual result data remains owned by the existing item and skill search outcomes.

Interpretation metadata describes what the deterministic parser understood. It must not be inferred from returned cards, item types shared by all results, or matched-stat rows after the fact.

No changes are required to the SQLite database schema.

## Universal Mode Routing

Universal mode may internally obtain structured interpretations from both Items and Skills, but the UI displays only the interpretation for the domain that actually wins the deterministic routing-quality decision.

The selection priority is:

1. exact/structured match with results;
2. exact/structured interpretation with no results;
3. weak fuzzy/FTS result;
4. no match.

If both domains are at the same priority level, deterministic match quality breaks the tie. Raw result count must not decide the winner. A higher-quality exact or structured interpretation must not lose simply because another domain returned more broad matches.

Universal mode exposes at most one interpretation group under the search bar. The UI does not display duplicate Items/Skills interpretation rows.

Exact names themselves are not rendered as chips even if an exact-name route contributes to routing quality. If the winning domain has no chip-eligible structured filters, the UI renders no interpretation chips; it must not fall back to the losing domain merely because that domain has chips available.

## Visibility Rules

Interpretation chips are rendered only when all of the following are true:

- the user submitted a query;
- the winning route has strong structured intent;
- the structured parse is trusted and complete enough to drive a search or deterministic no-result outcome;
- at least one supported structured filter exists.

Do not render chips for:

- weak fuzzy item-name matches;
- weak fuzzy skill-name or FTS matches;
- exact item or skill names without structured filters;
- help/meta/refusal outcomes;
- clarification outcomes;
- suggestion outcomes caused by unsafe or incomplete parsing;
- completely unrecognized queries.

When parsing is ambiguous or unsafe, the existing clarification/suggestion UI remains the source of guidance instead of displaying partially trusted chips.

## State and Data Flow

Normal submitted-search flow:

`submit query -> deterministic parse/search -> choose winning interpretation -> store outcome -> render chips -> render results`

Chip-removal flow:

`click chip remove -> semantic reconstruction -> update session query -> clear stored outcome/interpretation -> rerun UI -> no search`

The existing custom search component remains submit-only. Chip removal follows the same fill-only contract already used by correction/suggestion buttons.

After chip removal, old result cards must not remain visible because they correspond to the previous query. The UI displays the reconstructed query in the search field with no results until the next explicit submission.

Mode changes continue to clear stale outcomes as they do today.

## UI Responsibilities

The Streamlit UI is responsible for:

- rendering chips in their provided order directly below the search bar;
- providing a remove action for each chip;
- invoking semantic reconstruction through the interpretation model/helper;
- updating `st.session_state.query` with the reconstructed canonical query;
- resetting item and skill result limits;
- clearing the stored previous outcome/interpretation;
- rerunning the UI without invoking `search_database`.

The UI is not responsible for:

- recognizing aliases;
- determining whether a phrase means a stat, item type, tree, ailment, or numeric filter;
- calculating chip dependencies;
- reconstructing queries through raw string replacement;
- deciding which Universal domain has the stronger interpretation.

## Search-layer Responsibilities

The deterministic search layer is responsible for:

- emitting semantic interpretation metadata from the same parsing decisions used to execute the search;
- generating canonical fragments for each semantic part;
- defining dependencies;
- reconstructing a valid canonical query after a chip is removed;
- assigning deterministic route quality needed by Universal selection;
- preserving current search result behavior independently of the chip UI.

## Error Handling

If interpretation metadata cannot be produced safely for a query, omit the chips rather than guessing.

If a submitted query already routes to a clarification or suggestion because parsing is ambiguous, preserve that existing behavior and do not expose partial interpretation chips.

Semantic reconstruction must be total for every chip that the UI is allowed to render. A rendered chip must never have a removal action that can produce unsupported or malformed query syntax.

The safest fallback for an interpretation with no remaining meaningful parts after removal is the empty query.

## Testing Strategy

### Interpretation/model tests

Add deterministic tests proving structured queries produce the expected semantic chips and canonical fragments. Representative coverage must include:

- `aggro xtal wp`;
- `highest cr bow`;
- `hp >= 5000 armor`;
- at least one structured skill-tree query;
- at least one ailment query;
- MP filtering;
- required-level filtering.

Tests should assert semantic types and canonical values, not only presentation labels.

### Reconstruction tests

Directly test chip removal and dependency behavior, including:

- remove Weapon Crysta from `aggro xtal wp` -> `aggro`;
- remove Bow from `highest cr bow` -> `highest critical rate`;
- remove Critical Rate from `highest cr bow` -> `bow` and remove dependent Highest;
- remove Highest from `highest cr bow` -> `critical rate bow`;
- remove `MaxHP >= 5000` from `hp >= 5000 armor` -> `armor`;
- remove the final remaining chip -> empty query.

Tests must demonstrate that reconstruction is semantic rather than raw substring deletion.

### Universal routing tests

Add tests proving:

- only one domain interpretation is selected;
- exact/structured-with-results outranks exact/structured-without-results;
- structured routes outrank weak fuzzy/FTS routes;
- raw result count cannot override a higher-quality route;
- tie-breaking is deterministic;
- a winning route with no chip-eligible structured filters produces no chips rather than exposing the losing domain's interpretation.

### Streamlit behavior tests

Add UI-level coverage proving that removing a chip:

- updates the visible search field;
- clears old item/skill results;
- clears old interpretation chips;
- resets result pagination limits as appropriate;
- does not submit a new search;
- preserves the existing fill-only behavior of correction/suggestion buttons.

### Regression coverage

The existing routing, duplicate-result, item-search, skill-search, and Universal-mode tests must continue to pass. No SQLite database files should be modified by this feature.

## Acceptance Criteria

The feature is complete when all of the following are true:

1. A successfully submitted structured query can expose semantic removable chips directly below the search bar.
2. Chips represent only recognized structured filters, not exact/fuzzy names or unsafe partial interpretations.
3. Numeric comparisons appear as atomic stat/comparison chips.
4. Removing a chip reconstructs a valid canonical query semantically.
5. Removing a parent filter also removes dependent filters such as rank when required.
6. Chip removal updates the search field, clears stale results/chips, and performs no database search until explicit submission.
7. Universal mode shows only the strongest domain interpretation using deterministic quality rules rather than result count.
8. If Universal mode's winning route has no eligible structured chips, no chips are shown and the losing domain is not used as a fallback.
9. The interpretation metadata comes from the same deterministic parsing path that drove the search.
10. Existing correction/example fill-only behavior remains unchanged.
11. Existing item and skill search semantics remain unchanged except for exposing interpretation metadata.
12. All automated tests and Python compilation checks pass.
13. `items.sqlite` and `skills.sqlite` remain unchanged.

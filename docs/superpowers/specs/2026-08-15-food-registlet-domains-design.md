# Food and Registlet Search Domains Design

Date: 2026-08-15

## Summary

Add Food and Registlet as first-class deterministic search domains in the existing Streamlit Toram database app.

The app will have five modes:

- `Universal`
- `Items`
- `Skills`
- `Food`
- `Registlets`

Food uses the committed root files `food_entries.csv` and `food_stat_aliases.json`. Registlets use the committed root file `registlets.json`. `items.sqlite` and `skills.sqlite` remain unchanged.

Food search is deliberately opt-in: it runs only when the normalized query begins with `food` or `code`, followed by a supported Food stat or alias. Food codes are result values, not searchable identifiers.

Registlet search supports three deterministic primary routes: Stoodie source level, Registlet name, and Registlet effect text, plus a fuzzy-name fallback. Bare effect searches are allowed in Universal mode, but effect matches are weaker than exact/structured routes so they cannot pollute strong Item, Skill, Food, or Registlet matches.

The feature remains fully deterministic. It does not add an LLM, embeddings, RAG, or probabilistic intent inference.

## Goals

1. Add Food and Registlet as independent search domains without forcing them into the Item schema.
2. Keep Food data easy to edit because Food codes change frequently.
3. Require explicit `food` or `code` prefixes before Food can participate in a search.
4. Search Registlets by Stoodie level, Registlet name, or effect text.
5. Preserve the existing submit-only UI contract: examples, suggestions, corrections, and chip removals fill the search field but do not auto-search.
6. Generalize Universal routing so strong routes suppress weaker guesses across all domains instead of adding more pairwise suppression hacks.
7. Add Search Help that documents the Food and Registlet query rules.
8. Keep existing Item and Skill behavior intact except where shared routing/output models must be generalized.
9. Support manually curated Registlet-to-Skill relationships in both directions without modifying `skills.sqlite`.

## Non-goals

This feature will not add:

- Food search by code value;
- Food search by player name;
- Food player names in the data model;
- Food search without a leading `food` or `code` token;
- Stoodie level ranges such as `std 100-200`;
- automatic inference of `affects_skill` from Registlet effect text;
- semantic/vector effect search;
- fuzzy matching against arbitrary Registlet effect text;
- a Food or Registlet SQLite database;
- changes to `items.sqlite` or `skills.sqlite`;
- an LLM, embeddings, RAG, or model-generated answers.

## Data Sources

The repository root remains the source location for the five committed data files:

```text
items.sqlite
skills.sqlite
food_entries.csv
food_stat_aliases.json
registlets.json
```

### Food aliases

`food_stat_aliases.json` is the source of truth for Food stat identity and search aliases. Each stat has:

- a stable `key`;
- a human-facing `display` label;
- one or more accepted `aliases`.

The current file defines 39 canonical Food stats, including explicit variants for all seven elements.

The search layer must resolve Food stat text through this alias data. Streamlit must not maintain a second hard-coded alias list.

### Food entries

`food_entries.csv` contains one Food code/stat/level association per row:

```text
code,stat,level
```

`code` is treated as text, not an integer, so future leading-zero codes are not damaged.

`stat` may be written as any value that deterministically resolves to a Food stat through `food_stat_aliases.json`. Accepted forms include the stable key, display text, or an alias. This lets the CSV remain human-maintainable even if some existing rows use machine-style keys.

The loader canonicalizes every valid row to the stat's stable key and display label before search.

Exact duplicate normalized rows are collapsed at load time using:

```text
(code, canonical_stat_key, level)
```

Duplicates in the source file are therefore harmless and never create duplicate result rows.

### Registlets

`registlets.json` remains the Registlet source of truth. The current schema provides:

- `name`;
- `max_lv`;
- `effect`;
- `affects_skill`;
- `obtained_from.source`;
- `obtained_from.location`;
- `obtained_from.level_notation`;
- `obtained_from.levels`.

Search must use the already-expanded integer array `obtained_from.levels` for Stoodie lookups. `level_notation` is display/source metadata and must not be reparsed to determine membership.

`affects_skill` is manually curated. It may be `null` when no relationship has been supplied, or an array of canonical Skill names when relationships are added. Effect text must never be parsed to populate this field automatically.

## Domain Architecture

Food and Registlet are separate search modules alongside the existing Item and Skill modules.

Conceptually:

```text
toram_search/
  items/
  skills/
  food/
  registlets/
  router.py
  interpretation.py
```

Each domain owns:

- source loading/validation;
- query parsing relevant to that domain;
- result models;
- deterministic search;
- domain interpretation metadata;
- route-quality metadata.

The router consumes domain outcomes through a common quality contract rather than knowing each domain's parsing internals.

No implementation should place Food or Registlet parsing rules directly in Streamlit UI code.

## Sidebar Modes

The database selector becomes:

```text
Universal
Items
Skills
Food
Registlets
```

Mode changes continue to clear stale outcomes and reset pagination.

Food mode still requires the same explicit `food` or `code` prefix as Universal mode. The dedicated mode does not create alternate Food syntax.

Examples:

```text
food maxmp       valid
code ampr        valid
maxmp            not a Food query
51110000         not a Food query
```

Registlet mode accepts Stoodie, name, and effect searches directly.

## Food Query Contract

### Prefix requirement

After trimming leading/trailing whitespace and applying case-insensitive normalization, Food participates only when the query begins with the standalone token:

- `food`; or
- `code`.

The prefix must be first.

Valid Food queries:

```text
food maxmp
food cr
food physical resist
food dt dark
food -aggro
code maxmp
code ampr
code weapon atk
```

Queries that do not activate Food:

```text
maxmp
maxmp food
critical rate
51110000
```

The word `code` means “find Food codes for this stat”; it does not mean “search this code value.”

### Stat parsing

Everything after the leading prefix is trimmed and resolved as one Food stat through `food_stat_aliases.json`.

The first version does not support multiple Food stats in one query, numeric comparisons, ranking operators, or code-value lookups.

If the remainder is empty, Food returns a structured clarification telling the user to enter a Food stat and may offer example fill-only suggestions.

If the remainder does not resolve to a supported alias, Food returns a structured no-result/clarification outcome with deterministic nearby stat suggestions. It must not fall through to arbitrary Food fuzzy results.

### Food route quality

A valid `food <stat>` or `code <stat>` parse is a strong structured Food route.

An explicit Food prefix with an invalid or missing stat is still recognized Food intent. That recognized structured intent suppresses weak cross-domain guesses in Universal mode and should show Food-specific guidance instead.

Food has no weak name-search route because codes are not searchable and stats already have explicit aliases.

## Food Results

Food results are grouped by canonical stat and Food level.

Primary ordering:

1. Food level descending;
2. code ascending as text within the same level.

Example:

```text
MaxMP

Lv. 10
51110000
9090903

Lv. 9
...

Lv. 8
8024545
```

Multiple codes at the same level are preserved. No player-name field is displayed or required.

The UI may use cards, bordered groups, or equivalent existing result primitives, but one source row must not become multiple duplicate UI elements.

Food pagination/show-more behavior should follow the existing submit-only state model. Pagination actions may reveal more already-returned results but must not reinterpret or rerun the query.

## Registlet Query Contract

Registlet search has three primary routes plus one fallback, evaluated in this precedence order:

1. Stoodie structured route;
2. Registlet exact-name route;
3. Registlet effect-content route;
4. Registlet fuzzy-name fallback.

Exact name and Stoodie routes are strong. Effect search is a middle-strength content route. Fuzzy name search is weak.

### Stoodie route

Accepted forms include:

```text
std 220
std lv 220
std lvl 220
std level 220
stoodie 220
stoodie lv 220
stoodie lvl 220
stoodie level 220
```

Whitespace between `lv`/`lvl` and the number is optional where the parser can normalize it safely, so forms such as `std lv220` are accepted.

All accepted forms canonicalize to one integer `stoodie_level` filter.

The valid Stoodie levels come from `registlets.json` metadata rather than a duplicated hard-coded UI list.

If a valid level is searched, return every Registlet whose `obtained_from.levels` contains that integer.

Stoodie results are ordered by Registlet name ascending.

If the number is not a valid Stoodie level, return no Registlet cards and provide deterministic nearby valid-level suggestions. For example, `std 200` may suggest `std 190` and `std 210`.

The first version does not accept level ranges or multiple Stoodie levels in one query.

### Exact and fuzzy Registlet name routes

An exact case-insensitive normalized Registlet name match is a strong exact route.

If no exact/structured/content match is found, the service may perform a fuzzy Registlet-name fallback using the same deterministic RapidFuzz-style principles already used elsewhere in the project. Fuzzy matching is only for Registlet names, not effects.

Fuzzy-name results are ordered by score descending and then name ascending for deterministic ties.

### Effect-content route

If the query is not a Stoodie query and not an exact Registlet name, Registlet search may search the `effect` field directly.

Bare effect queries are allowed in both Universal and Registlet modes:

```text
restores mp
physical pierce
inflicts stun
reduces aggro
normal attack power
```

Effect matching is deterministic and text-based:

1. Normalize case and whitespace/punctuation for comparison.
2. Prefer records containing the complete normalized query phrase.
3. If there is no phrase match, accept records where every normalized query token appears somewhere in the effect text.
4. Do not use fuzzy edit-distance matching over effect text.

Phrase matches sort before all-token matches. Ties sort by Registlet name ascending.

The effect search describes only what appears in the stored `effect` field. It does not infer hidden tags, skill relationships, stats, or mechanics that are not explicitly present in the source.

If effect search finds nothing, the Registlet service may then use fuzzy-name fallback for typo tolerance.

## Registlet Results

A Registlet detail result shows:

- Registlet name;
- max Registlet level;
- effect text;
- all Stoodie source levels;
- affected Skills when manually supplied.

Example structure:

```text
Arrow Rain Enhancer
Max Lv: 2

Effect
...

Stoodie Sources
Lv70 · Lv90 · Lv110 · Lv130 · Lv150 · Lv220

Affected Skills
Arrow Rain
```

A Stoodie-level search may use a compact list/card representation because many Registlets can share one level. Opening or expanding a Registlet should expose the full detail without performing another search.

Result pagination should use a separate Registlet limit so Item/Skill/Food pagination states do not interfere with each other.

## Registlet-to-Skill Relationships

The relationship is owned by `registlets.json`, not `skills.sqlite`.

Example future source representation:

```json
"affects_skill": [
  "Arrow Rain"
]
```

A Registlet may affect zero, one, or multiple Skills.

At load time, supplied Skill names are validated against canonical Skill names from `skills.sqlite` when that database is available.

A missing Skill reference is a data warning, not a crash. The Registlet remains searchable and its source text remains visible; the invalid relationship is not converted into a clickable Skill relation.

The app builds the reverse mapping in memory:

```text
Skill -> [Registlets that explicitly reference that Skill]
```

This enables:

- Registlet detail -> Affected Skills;
- Skill detail -> Related Registlets.

The app must never infer this relationship from quoted names or other words inside a Registlet effect.

## Universal Routing

### Route families

Generalize the shared route-quality model to support these domain-neutral families:

```text
exact
structured
content
weak
none
```

The conceptual precedence is:

1. successful exact/structured route;
2. recognized exact/structured route with no results, where the intent itself is trustworthy and should produce domain-specific guidance;
3. successful content route;
4. successful weak route;
5. none.

Within an equivalent tier, existing deterministic match-quality/specificity rules break ties. Raw result count must never determine which domain wins.

Exact may remain a stronger tie-break than structured where the existing route-quality model already makes that distinction.

### Cross-domain suppression

Universal may ask multiple healthy domains to evaluate a query, but it must suppress results from lower-quality domains when a stronger recognized route exists.

The rule is generic:

> A stronger trusted domain route suppresses weaker-domain guesses; equal-strength legitimate routes may coexist.

Examples:

- Exact `MAGIC: FINALE` Skill suppresses Registlet effect matches that merely mention Finale and weak Item fuzzies.
- `food maxmp` is a strong structured Food route and suppresses unrelated Item/Skill/Registlet weak matches.
- `std 220` is a strong structured Registlet route and suppresses weak other-domain guesses.
- `restores mp` may return Registlet effect matches when competing Item/Skill outcomes are only weak.
- A strong Item or Skill structured match suppresses Registlet effect-content results.

This replaces pairwise logic such as “strong Skill suppresses weak Item” with a common route-quality comparison across all domains.

### Food gating in Universal

Universal must not even consider Food as a matching domain unless the query starts with `food` or `code`.

A bare query such as `maxmp` can therefore match Items, Skills, or Registlets according to their own rules, but never Food.

### Universal interpretation winner

Universal still displays at most one query-interpretation chip group.

The interpretation comes from the highest-quality recognized route using the same route-quality ordering as result suppression. Result count must not choose the chip domain.

If the winning route has no chip-eligible structured interpretation, the UI shows no chips instead of borrowing chips from a lower-quality domain.

## Query Interpretation Chips

Add two structured interpretation forms.

### Food chip

Submitted:

```text
food maxmp
```

Interpretation:

```text
Food: MaxMP
```

The canonical reconstruction must retain a valid Food prefix. If additional Food chip types are not introduced, removing the final Food chip reconstructs to the empty query.

### Stoodie chip

Submitted:

```text
std 220
```

Interpretation:

```text
Stoodie Lv220
```

Removing the final Stoodie chip reconstructs to the empty query.

Exact/fuzzy Registlet names and Registlet effect searches do not produce chips.

Chip removal remains fill-only: update the search field, clear stale outcome/chips, reset pagination, rerun the UI, and wait for explicit Enter/Search.

## Autocomplete and Suggested Searches

Autocomplete expands to include:

- Food stat suggestions;
- Registlet names;
- optional structured Stoodie examples.

Food autocomplete values must include the required prefix, for example:

```text
food MaxMP
food Critical Rate
food DTE Fire
```

Autocomplete must not teach invalid bare Food syntax such as `MaxMP` as a Food suggestion.

Registlet autocomplete suggests names such as:

```text
Arrow Rain Enhancer
Magic: Wall Enhancer
```

Effect phrases are not precomputed as autocomplete entries.

Suggested searches should include representative new-domain examples such as:

```text
food maxmp
std 220
restores mp
```

Clicking autocomplete or suggested-search values continues to fill only; actual search occurs only on Enter/Search.

## Search Help

Add a `Search Help` expander to the sidebar as the single user-facing place for search syntax guidance.

It must document existing Item/Skill syntax plus the following Food and Registlet rules.

### Food help text

The help must communicate:

```text
Food Code Search

Start the query with "food" or "code", followed by a Food stat.

Examples:
food maxmp
code ampr
food critical rate
food dt fire
food -aggro

Food codes are returned as results. Code values themselves are not searchable.
```

It must be clear that `maxmp food`, bare `maxmp`, and a raw numeric code do not invoke Food search.

### Registlet help text

The help must communicate:

```text
Registlet Search

Search by Stoodie level:
std 220
stoodie lvl 220

Search by Registlet name:
Arrow Rain Enhancer

Search by effect text:
restores mp
physical pierce
inflicts stun
```

It must also explain that in Universal mode, effect-text matches are weaker than exact/structured Item, Skill, Food, or Registlet matches.

## Loading, Caching, and Validation

Food and Registlet sources are small text files and should be loaded through cached deterministic loaders rather than converted to SQLite.

Cache invalidation must include the source path/file contents or modification identity supported by the deployed environment so an app restart/source update loads current committed data.

### Food validation

Each Food CSV row requires:

- non-empty `code`;
- resolvable `stat`;
- integer `level`.

Validation behavior:

- canonicalize stat through `food_stat_aliases.json`;
- preserve code as text;
- collapse exact normalized duplicates;
- report row-numbered warnings/errors for invalid rows;
- never silently reinterpret an unknown stat as another stat through loose substring matching.

An invalid individual row should be skipped with a visible/diagnostic data warning while other valid rows remain searchable. A missing or malformed aliases file makes the Food domain unavailable because stat identity cannot be trusted.

### Registlet validation

Each Registlet requires:

- non-empty `name`;
- integer `max_lv`;
- non-empty `effect`;
- `obtained_from.levels` containing integers from the metadata's valid Stoodie levels;
- `affects_skill` equal to `null` or an array of strings.

Invalid source levels or malformed required fields must produce deterministic data warnings/errors rather than inferred repairs.

A malformed individual Registlet may be skipped while other valid records remain searchable if the top-level JSON/metadata remains trustworthy. A malformed top-level source makes the Registlet domain unavailable.

### Domain availability

Domain health is independent.

- Items mode requires `items.sqlite`.
- Skills mode requires `skills.sqlite`.
- Food mode requires valid Food aliases plus at least a readable Food entries source.
- Registlets mode requires a readable/valid Registlet source.

Universal searches healthy domains rather than disabling the entire app because one independent domain is unavailable. It surfaces a warning for unavailable domains.

If a query explicitly expresses an unavailable domain's strong intent, such as `food maxmp` while Food data is unavailable, the UI should show that domain error rather than filling the screen with weak matches from unrelated healthy domains.

## State and UI Integration

Extend the stored Universal outcome to carry optional outcomes for:

- Items;
- Skills;
- Food;
- Registlets;
- one winning interpretation.

Maintain separate pagination/session limits for each result domain.

The top-level caption and search placeholders should describe all supported domains without becoming overly long. The sidebar Search Help contains the detailed syntax.

Normal flow remains:

```text
explicit submit
-> deterministic domain searches
-> generic route comparison/suppression
-> store outcome
-> render winning interpretation
-> render surviving results
```

No loader, autocomplete interaction, suggestion click, correction click, or chip removal may trigger an automatic database search.

## Error Handling and Suggestions

### Food

- Missing prefix remainder -> explain that a Food stat is required.
- Unknown stat -> offer deterministic nearby supported stat suggestions.
- Raw code query -> do not search Food.
- Duplicate rows -> silently collapse duplicates; this is normal data hygiene, not a user error.

### Registlets

- Invalid Stoodie level -> no result cards; suggest nearby valid levels.
- Exact name miss -> attempt effect-content search, then fuzzy-name fallback according to route order.
- Effect-content miss -> fuzzy-name fallback may still recover a misspelled Registlet name.
- Invalid affected Skill reference -> data warning; Registlet search remains available.

Suggestions that populate the search field remain fill-only.

## Testing Strategy

Implementation must follow regression-first TDD.

### Food loader/parser tests

Cover:

- key, display, and alias forms all resolving to the same canonical Food stat;
- codes preserved as text;
- integer level parsing;
- duplicate `(code, stat, level)` rows collapsing to one result;
- unknown Food stat rejected with a deterministic warning;
- malformed row does not corrupt valid rows;
- missing/malformed aliases make Food unavailable.

### Food query tests

Cover at minimum:

```text
food maxmp
code ampr
food dt dark
food -aggro
```

and prove these do not invoke Food:

```text
maxmp
maxmp food
51110000
```

Verify highest level first and all matching codes retained.

### Registlet Stoodie tests

Cover aliases including:

```text
std 220
std lv 220
std lvl220
std level 220
stoodie 220
stoodie lvl 220
```

Verify membership uses `obtained_from.levels`, results are alphabetical, and invalid level guidance uses metadata-defined valid levels.

### Registlet name/effect tests

Cover:

- exact Registlet name;
- case-insensitive exact name;
- fuzzy Registlet-name typo;
- exact phrase effect match;
- all-token effect match;
- effect search does not use fuzzy text matching;
- phrase effect match sorts before token-only effect match.

Representative effect queries include:

```text
restores mp
physical pierce
inflicts stun
```

### Universal routing tests

Cover:

- exact Skill suppresses Registlet effect-content and weak Item matches;
- structured Item/Skill suppresses Registlet content matches;
- explicit Food structured route suppresses weak other-domain matches;
- Stoodie structured route suppresses weak other-domain matches;
- Registlet effect-content route outranks weak other-domain matches;
- equal-strength legitimate routes may coexist;
- result count never overrides stronger route quality;
- structured no-result Food/Stoodie intent suppresses irrelevant weak guesses;
- bare `maxmp` never activates Food.

Keep the existing `MAGIC: FINALE` regression passing.

### Relationship tests

Cover:

- `affects_skill: null`;
- one affected Skill;
- multiple affected Skills;
- Registlet -> Skill display mapping;
- Skill -> Registlet reverse mapping;
- unknown Skill reference produces a warning without crashing or mutating `skills.sqlite`.

### Interpretation/UI tests

Cover:

- Food structured chip;
- Stoodie structured chip;
- no chips for Registlet name/effect/fuzzy routes;
- removing a new chip remains fill-only;
- mode change clears stale results;
- domain pagination states are independent;
- suggested searches and autocomplete remain fill-only;
- Search Help includes the explicit Food prefix rule and all three Registlet search routes.

### Regression and repository checks

All existing Item, Skill, routing, autocomplete, suggestion, chip, and Streamlit behavior tests must continue to pass.

`python -m compileall -q main.py toram_search ui` must pass.

The implementation must not modify `items.sqlite` or `skills.sqlite`.

## Acceptance Criteria

The feature is complete when all of the following are true:

1. The sidebar offers Universal, Items, Skills, Food, and Registlets modes.
2. Food data is read from `food_entries.csv` plus `food_stat_aliases.json`; no Food SQLite database is introduced.
3. Food participates only when the normalized query starts with standalone `food` or `code`.
4. Food code values themselves are not searchable.
5. Food stat aliases resolve deterministically through the committed alias file.
6. Food results sort by level descending and preserve all unique matching codes.
7. Exact normalized duplicate Food rows display once.
8. Registlets are read from `registlets.json`; no Registlet SQLite database is introduced.
9. `std`/`stoodie` level aliases return all Registlets whose explicit source-level array contains that level.
10. Registlet exact-name search works and outranks effect/fuzzy matching.
11. Bare Registlet effect searches work through deterministic phrase/all-token text matching.
12. Fuzzy matching is limited to Registlet names, not effect text.
13. Universal route quality is generalized across all four domains using exact/structured/content/weak/none semantics.
14. Strong recognized routes suppress weaker cross-domain guesses, while equal-strength legitimate routes may coexist.
15. A bare query such as `maxmp` never invokes Food.
16. Food and Stoodie structured queries expose removable interpretation chips; Registlet name/effect routes do not.
17. `affects_skill` is manually curated and supports zero/one/multiple Skills without inference from effect text.
18. Registlet details show affected Skills and Skill details can show related Registlets through an in-memory reverse mapping.
19. Search Help explicitly documents the Food prefix requirement, non-searchable code values, Stoodie syntax, Registlet name search, and Registlet effect search.
20. Existing submit-only behavior remains unchanged for typing, autocomplete, examples, suggestions, corrections, and chip removal.
21. Independent data-source failures degrade by domain rather than disabling unrelated healthy domains in Universal mode.
22. All automated tests and Python compilation checks pass.
23. `items.sqlite` and `skills.sqlite` remain byte-for-byte unchanged by the implementation.

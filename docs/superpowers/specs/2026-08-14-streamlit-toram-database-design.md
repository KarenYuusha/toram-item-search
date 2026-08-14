# Streamlit Toram Database Design

Date: 2026-08-14

## Repository boundary

This design applies only to `KarenYuusha/toram-item-search`.

`KarenYuusha/filter_search` is a reference/source repository only. The Streamlit project may adapt deterministic search/parser/database code from `filter_search`, and it may copy the current SQLite database files from that repository, but Streamlit-specific code must not be written into `filter_search` as part of this project.

The public application entry point must remain the root-level `main.py` in `toram-item-search`.

## Goal

Build a fast, deterministic Toram Online database search website deployed on Streamlit Community Cloud. The site must support both item and skill data without using an LLM, embeddings, RAG, Ollama, Gemma, Qwen, or any other generative model.

The website should feel like a normal search application rather than a database administration interface: users search first, then refine or inspect details only when needed.

## Data ownership and update workflow

`filter_search` remains the canonical place where the user maintains Toram data.

The existing canonical databases in `filter_search` are:

- `coryn_data/database/items.sqlite`
- `coryn_data/database/skills.sqlite`

For the Streamlit repository, copies of those files will be stored as:

- `items.sqlite`
- `skills.sqlite`

The Streamlit application treats both files as read-only inputs. It does not contain an item editor, skill editor, migration UI, or database rebuild pipeline.

Normal update workflow:

1. Edit/update Toram data in `filter_search` using the existing maintenance workflow.
2. Copy the latest `coryn_data/database/items.sqlite` and `coryn_data/database/skills.sqlite` into the root of `toram-item-search` as `items.sqlite` and `skills.sqlite`.
3. Commit and push those replacement files to `toram-item-search`.
4. Streamlit Community Cloud redeploys the updated site.

The Streamlit app should validate both databases on startup and show a clear configuration/data error if a database is missing or lacks the expected schema.

## Product scope

The application supports three database modes selected from the sidebar:

- **Universal** — default; searches both item and skill databases and returns every applicable result grouped by domain.
- **Items** — searches only `items.sqlite`.
- **Skills** — searches only `skills.sqlite`.

There are no separate top-level Item/Skill/Universal pages. The main page always provides one primary search experience.

## Main UX

### Sidebar

Keep the sidebar intentionally small:

- Toram Database title/branding
- Database selector: Universal / Items / Skills
- About
- Credits
- GitHub

Do not place a large permanent advanced-filter form in the sidebar. The site follows a **search first, refine second** approach.

### Main page

The main page contains:

1. Page title: `Toram Database`
2. Short subtitle such as `Search items, stats, skills, and skill trees`
3. Search input
4. Search button
5. Autocomplete suggestions while typing
6. Contextual example searches
7. Search results

Example initial searches may include:

- `critical rate`
- `CR bow`
- `Guardian`
- `Shield Skills`
- `stun skills`

Examples can change based on the selected database mode.

## Search execution and autocomplete

Autocomplete is advisory only. Typing must not execute the full database search.

The actual search runs only when the user:

- presses Enter, or
- clicks the Search button.

In Universal mode, autocomplete may mix result types but must label them clearly, for example:

- Guardian — Skill
- Guard Skills — Skill Tree
- Guard Golem Crystal — Item
- Critical Rate — Stat

Autocomplete should be generated deterministically from known database values and alias dictionaries. It must not call an LLM or external search service.

## Deterministic query behavior

The project should reuse/adapt the proven deterministic behavior from `filter_search` where it is useful, while removing Discord-specific and LLM-specific layers.

Supported first-version query families should include:

- exact item name
- partial/fuzzy item name
- exact skill name
- partial/fuzzy skill name
- stat-based item queries
- item-type filters
- ranking queries such as highest/lowest stat values
- skill-tree queries
- skill property queries such as MP cost, tier, ailment/effect, and other fields already represented deterministically in the skill database/search code
- deterministic counts/comparisons where the existing implementation supports them cleanly

Examples:

- `Amnis Rapier`
- `Guardian`
- `critical rate bow`
- `highest dex% crysta`
- `shield skills`
- `guardian mp cost`
- `skills that inflict stun`

The app should preserve useful aliases already established in `filter_search`, for example common abbreviations such as CR, CD, PP, MRes, and ASPD when those aliases are already part of the canonical deterministic parser.

## Routing

The selected sidebar mode controls which deterministic search engines are allowed to run.

### Universal

The same submitted query is evaluated against both domains where applicable:

- item parser/search
- skill parser/search

Results are then grouped into Items and Skills sections.

Universal mode must not use an LLM to decide which database is relevant. Deterministic parsing/routing rules and direct name matching are sufficient.

### Items

Only the item parser/search is evaluated.

### Skills

Only the skill parser/search is evaluated.

## Match priority

Within each domain, the UI should favor results in approximately this order:

1. exact name match
2. strong/partial name match
3. recognized deterministic structured/natural query
4. corrected/suggested query
5. unsupported-query guidance

Exact-name searches should feel immediate and should not be hidden behind broad result sets.

## Failed and unsupported searches

A failed search should not end with a generic dead-end message.

When possible, generate deterministic corrected-query suggestions from known:

- item names
- skill names
- stat names and aliases
- item types
- skill trees
- ailment/property names
- parser grammar

Example:

Input: `crit bow hp`

Possible response:

`I couldn't understand that search.`

Suggested queries might include:

- `critical rate bow`
- `max hp bow`
- `critical rate + max hp`

Suggestions must be grounded in known parser/database vocabulary, not generated by an LLM.

Subjective queries such as `best tank xtal` or `best DPS skill` are out of scope for version 1 unless a deterministic scoring model is explicitly designed later. The site should redirect users toward objective filters/rankings rather than inventing a subjective answer.

## Result presentation

Use compact cards rather than large visual cards or a plain table-only interface.

### Item cards

A compact item card should show the most useful scan-level fields, such as:

- small item image/thumbnail when available
- item name
- item type
- matched/high-value stats relevant to the query
- `View details`

The field/stat that caused the match should be visually emphasized where practical.

### Skill cards

A compact skill card should show scan-level fields such as:

- small skill icon when available
- skill name
- skill tree
- tier
- MP cost when available
- active/passive or equivalent useful classification
- `View details`

### Responsive layout

- Desktop/wide screens: compact multi-column layout where it remains readable, typically two cards per row.
- Mobile/narrow screens: one card per row.

Avoid giant cards that force excessive scrolling.

## Detail views

Full item/skill records should open in a Streamlit dialog/modal rather than expanding every card inline.

This keeps the search list stable while users inspect detailed records.

Item detail may include:

- full image when available
- all stats
- item type and IDs where useful
- sell/process data
- drop/source data
- monster/map/source information
- other fields available in the item database

Skill detail may include:

- icon
- skill tree/tier
- MP cost
- required level
- skill type
- range/cast/charge information where available
- weapon/sub-weapon restrictions
- ailment/effect information
- formulas/mechanics stored in the database
- game description and other stored skill details

The application must present stored mechanics/data directly. It must not generate a prose explanation with an LLM.

Inline expanders may still be used for small secondary sections such as help text or optional extra stats, but not as the primary full-record interaction.

## Universal result layout

Universal results are grouped by domain on the same page, for example:

- `Items · 53`
- item cards
- `Show more items`
- `Skills · 7`
- skill cards
- `Show more skills`

Each section maintains its own result limit/show-more state.

Items-only and Skills-only modes can use the full result area for the selected domain.

Initial result rendering should be bounded (roughly 10–20 cards per domain) to avoid rendering very large result sets at once. Prefer `Show more` over traditional numbered pagination for the first Streamlit version.

## Optional refinement controls

Permanent advanced filters are intentionally not part of the main sidebar.

A small `Filters`/refinement control near the search area may expose context-sensitive deterministic filters when useful.

Examples for Items:

- item type
- stat
- relevance/highest/lowest sort

Examples for Skills:

- skill tree
- tier
- ailment/effect

After a result set exists, deterministic refinement chips/buttons may also be shown, such as Bow, Armor, Crysta, Highest first, Tier 5, or Stun. Refinements should be derived from known database fields and current results.

These controls are secondary to the search box and should not make users understand the database schema before searching.

## Application architecture

`main.py` is the Streamlit entry point and page orchestrator, but business/search logic should live in modules rather than a single monolithic file.

Proposed structure:

```text
toram-item-search/
├── main.py
├── items.sqlite
├── skills.sqlite
├── requirements.txt
├── README.md
├── .gitignore
├── .streamlit/
│   └── config.toml
├── toram_search/
│   ├── __init__.py
│   ├── database.py
│   ├── router.py
│   ├── models.py
│   ├── item_parser.py
│   ├── item_search.py
│   ├── skill_parser.py
│   └── skill_search.py
├── ui/
│   ├── __init__.py
│   ├── sidebar.py
│   ├── search.py
│   ├── autocomplete.py
│   ├── item_cards.py
│   ├── skill_cards.py
│   └── dialogs.py
└── tests/
    ├── test_database.py
    ├── test_router.py
    ├── test_item_search.py
    └── test_skill_search.py
```

Exact module names may be adjusted during implementation if the reused `filter_search` code has a cleaner natural boundary, but the separation of concerns must remain.

## Code reuse policy

Code may be copied or adapted from `filter_search` when it implements deterministic behavior that the Streamlit project needs.

Good candidates include:

- SQLite repositories/data-access logic
- stat aliases and normalization
- item type aliases
- deterministic item parser
- ranking/filtering logic
- deterministic skill repository/query logic
- shared search models that do not depend on Discord or LLM services

Do not bring over runtime dependencies or architecture that only exists for the Discord/RAG assistant, including:

- Discord bot/rendering code
- Ollama clients
- Qwen/Gemma integrations
- embeddings
- skill RAG
- vector search used only for generated explanations
- failed-query LLM context
- conversational LLM state

When copying code, reduce dependencies so `toram-item-search` contains only what the public deterministic website actually needs.

## Streamlit state and performance

Use Streamlit caching for expensive read-only setup such as database metadata, alias lists, and autocomplete indexes where appropriate.

Do not keep writable SQLite connections globally. Database access should be read-only/safely scoped for Streamlit reruns.

Search execution should occur only on submission, not on every keystroke. This avoids unnecessary database work and keeps typing/autocomplete responsive.

The UI should preserve the submitted query, selected database mode, result state, and show-more state across normal Streamlit reruns.

## Deployment

Deployment target: Streamlit Community Cloud.

Public app URL: `https://toram-item-search.streamlit.app/`

Entry point: root `main.py`.

The repository must include a Python dependency file (`requirements.txt`) containing only the packages needed by the Streamlit application. Do not include Ollama/Discord/LLM dependencies.

`.streamlit/config.toml` may define a restrained theme/configuration suitable for the search UI.

No external database server is required. The two SQLite files are packaged with the repository.

## Error handling

The public UI should provide clear user-facing messages for:

- missing `items.sqlite`
- missing `skills.sqlite`
- incompatible/missing required tables or columns
- malformed supported query syntax
- no results
- unsupported subjective query

Technical stack traces should not be the normal user experience.

One domain failing validation should be reported clearly. Universal mode should not silently present incomplete results as if both databases were healthy.

## Testing

Core deterministic behavior should be testable without launching Streamlit.

Minimum test coverage should include:

- database validation
- exact item lookup
- exact skill lookup
- partial/fuzzy name behavior
- common stat aliases
- item type filters
- stat ranking queries
- skill tree/property queries
- Universal routing
- Items-only routing
- Skills-only routing
- deterministic failed-query suggestions
- subjective/out-of-scope refusal behavior

UI helpers should be kept thin so most correctness tests target parser/router/repository behavior rather than Streamlit rendering internals.

Before considering implementation complete, verify the Streamlit app starts with the copied databases and run the full automated test suite.

## Version 1 non-goals

The first version does not include:

- LLM-generated answers
- RAG/embeddings
- subjective build recommendations
- public database editing
- automatic synchronization from `filter_search`
- a separate backend API/server
- user accounts
- write operations against the SQLite databases

## Final interaction flow

```text
Open site
  ↓
Choose Universal / Items / Skills (Universal default)
  ↓
Type into search box
  ↓
See deterministic autocomplete suggestions
  ↓
Press Enter or Search
  ↓
Deterministic parser/router + SQLite query
  ↓
Compact result cards
  ↓
Optional refine/show more
  ↓
View details
  ↓
Dialog/modal with full stored record
  ↓
Close dialog and continue searching
```

This design keeps the Streamlit application lightweight, fast, deterministic, easy to update by replacing the two canonical SQLite copies, and independent from the Discord/LLM runtime in `filter_search`.
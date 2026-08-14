# UI Suggestions and Skill Icons Design

Date: 2026-08-14
Target repository: `KarenYuusha/toram-item-search`
Reference/source repository only: `KarenYuusha/filter_search`

## Scope

This follow-up changes only three user-facing behaviors:

1. Move the suggested example searches above the search bar.
2. Turn correction/failed-query suggestions into clickable controls that fill the search bar without executing a search.
3. Show the real individual skill icons from `filter_search/coryn_skill_icons` in Streamlit skill cards and skill detail dialogs.

No LLM, RAG, embedding, database-schema, or unrelated search behavior changes are included.

## Repository Boundary

`toram-item-search` remains the deployed standalone Streamlit repository. `filter_search` remains source/reference-only.

The Streamlit repository will contain its own checked-in copy of `coryn_skill_icons/`, just as it already contains copied `items.sqlite` and `skills.sqlite`. The deployed site must not depend on `filter_search` being reachable at runtime.

When the canonical icons change in `filter_search`, the icon directory can be copied/replaced in `toram-item-search` together with normal data maintenance.

## Design Alternatives Considered

### A. Copy icons and reuse deterministic local resolver — chosen

Copy `filter_search/coryn_skill_icons/` into `toram-item-search` and adapt the existing `SkillIconCatalog` logic. This keeps deployment self-contained and reuses a resolver already proven by the Discord UI.

### B. Hotlink icons from `filter_search`

Avoids duplicated assets, but makes the public Streamlit app depend on GitHub/network availability and another repository's path structure. Rejected.

### C. Store icon paths in `skills.sqlite`

Makes icons data-driven, but changes the canonical skill database schema solely for presentation. Rejected for this follow-up.

## Suggested Searches Placement

The page order changes from:

```text
Search bar
Suggested searches
Results
```

to:

```text
Toram Database
Search items, stats, skills, and skill trees

Suggested searches
[ Critical Rate ] [ Guardian ] [ Shield Skills ] [ Stun Skills ]

[ Search items, stats, skills... ] [ Search ]

Results
```

The suggested-search controls are fill-only. Clicking one replaces the current search-box value but does not execute a database query. The user still presses Enter or Search to run it.

This keeps all suggestion interactions consistent with the existing submit-only search contract.

## Clickable Correction Suggestions

Current failed/clarification outcomes render suggestions as passive text such as:

```text
Try: `critical rate bow` · `critical rate`
```

They will instead render clickable chips/buttons:

```text
Try:
[ Critical Rate Bow ] [ Critical Rate ]
```

Click behavior:

1. Replace the current search-box value with the selected suggestion.
2. Do not call either search engine.
3. Preserve the selected database mode.
4. Allow the user to edit the filled value before submitting.
5. Search executes only after Enter or the Search button.

The same fill-only mechanism will be used by the top suggested-search controls.

### State flow

```text
Search "crit bow"
    ↓
parser returns suggestions
    ↓
render clickable suggestion controls
    ↓ click "critical rate bow"
update Streamlit query/input state
    ↓
search box displays "critical rate bow"
    ↓
user presses Enter/Search
    ↓
normal deterministic search executes
```

The implementation must avoid treating a Streamlit rerun caused by clicking a suggestion as a search submission. Existing nonce/submit-event semantics remain authoritative for the custom search component.

## Skill Icons

The source icon library is `filter_search/coryn_skill_icons/`, organized by skill-tree folder and PNG filename. For example:

```text
coryn_skill_icons/Shield/Guardian.png
coryn_skill_icons/Shield/Shield Bash.png
coryn_skill_icons/Shield/Shield Cannon.png
```

The Streamlit repository will receive the same directory at its root:

```text
toram-item-search/
├── coryn_skill_icons/
├── items.sqlite
├── skills.sqlite
└── main.py
```

### Resolver

Adapt the existing deterministic resolver from `filter_search/toram_discord/skill_icons.py` into a frontend-neutral Streamlit-side module such as:

```text
toram_search/skill_icons.py
```

The resolver behavior remains:

- Normalize Unicode/case/punctuation for tree and skill matching.
- Remove the `Skills` suffix when matching a tree folder.
- Preserve existing folder aliases, including `Magic Warrior → MagicBlade` and `Blacksmith → Smith`.
- Prefer a unique match inside the matching tree folder.
- Fall back to a globally unique skill-name match.
- Return no icon for ambiguous or missing matches instead of guessing.

No icon path is added to `skills.sqlite`.

## Skill Card Presentation

Each skill result card shows the icon beside its compact metadata:

```text
┌─────────────────────────────────────────────┐
│ [ICON]  Guardian                            │
│         Shield Skills · Tier 4              │
│                                             │
│         MP 600 · Lv. 110 · Active           │
│                                             │
│                       [ View details ]       │
└─────────────────────────────────────────────┘
```

The icon is a small thumbnail sized so it improves recognition without making cards significantly taller. Existing two-column desktop / one-column narrow-screen behavior remains.

If no icon resolves, the card still renders normally without a broken-image placeholder.

## Skill Detail Dialog

The skill detail dialog uses the same resolved individual icon at a somewhat larger size near the skill name/header. The icon resolver must not be duplicated in the UI layer; both cards and dialogs consume the same resolver/helper.

Missing icons degrade gracefully and do not affect detail content.

## Components and Boundaries

Expected responsibilities:

- `main.py`: arrange suggested searches above the search component and coordinate fill-only query updates.
- `ui/results.py`: render correction suggestions as clickable controls and return/communicate the chosen fill value rather than executing a search.
- `ui/search.py` / autocomplete component: display externally supplied query state while retaining submit-only nonce behavior.
- `toram_search/skill_icons.py`: deterministic local icon lookup only.
- `ui/skill_cards.py`: render resolved thumbnail.
- `ui/skill_dialog.py`: render resolved detail icon.
- `coryn_skill_icons/`: checked-in static source assets copied from `filter_search`.

Search/parser modules should not import Streamlit UI code.

## Error Handling

- Missing icon directory: skill search still works; cards/dialogs omit icons.
- Missing individual icon: omit icon for that skill.
- Ambiguous global icon name: omit icon rather than choose arbitrarily.
- Suggestion click with empty/invalid string: ignore it and keep current query.
- Database health behavior remains unchanged.

## Testing

Add focused regression coverage for:

- Icon normalization and tree-folder aliases.
- `Guardian` resolving to the Shield icon from the copied icon library.
- Ambiguous/missing icon resolution returning `None`.
- Skill card/detail code consuming the shared resolver.
- Top suggested-search buttons appearing before the search component in the page contract.
- Correction suggestions being rendered as clickable controls.
- Clicking either top examples or correction suggestions updates the search value without invoking `search_database`.
- Enter/Search still invokes the query exactly once after a fill-only suggestion action.
- Existing Universal/Items/Skills mode isolation remains intact.

Run the complete pytest suite and `compileall` in GitHub Actions after implementation.

## Success Criteria

The follow-up is complete when:

1. Suggested examples appear above the search bar.
2. Top examples fill the search field without auto-searching.
3. Failed-query corrections are clickable and fill the same search field without auto-searching.
4. Enter/Search remains the only action that executes the query.
5. Skill cards display the correct individual icons from copied `coryn_skill_icons` where available.
6. Skill detail dialogs display the same icon.
7. Missing icons never break search or UI rendering.
8. The Streamlit app remains standalone and has no runtime dependency on `filter_search`.
9. All existing and new tests pass.
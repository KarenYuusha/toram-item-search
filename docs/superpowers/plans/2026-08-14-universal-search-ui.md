# Universal Search and Streamlit UI Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the product by combining deterministic item and skill services behind the Universal / Items / Skills sidebar selector, replacing temporary native forms with a client-side autocomplete + Enter/Search submission component, and polishing the responsive Streamlit result/detail experience for deployment.

**Architecture:** A frontend-neutral coordinator executes only the domain services allowed by the selected mode. Autocomplete indexes are built from read-only database vocabulary and cached as immutable data, then filtered entirely inside a small custom Streamlit HTML component restored from the repository's older working implementation. Typing never performs a database query; only Enter or the component Search button emits a submit event to Python. Session state stores the last submitted outcomes and independent show-more limits. Domain services remain unaware of Streamlit.

**Tech Stack:** Python 3.12, Streamlit 1.61.x, Streamlit components API, browser JavaScript/HTML/CSS, SQLite, RapidFuzz, pytest/AppTest.

## Global Constraints

- Target repository is only `KarenYuusha/toram-item-search`.
- `KarenYuusha/filter_search` remains reference/source only.
- Root `main.py` is the only public Streamlit entry point.
- No LLM, embeddings, RAG, Ollama, Qwen, Gemma, Discord, or external search service.
- Universal is the default sidebar mode.
- Universal evaluates both deterministic domains and groups all applicable results by Items and Skills.
- Items mode must not execute the skill search service; Skills mode must not execute the item search service.
- Typing/autocomplete must not execute full database search.
- Full search occurs only on Enter or Search button.
- Suggestion click/Tab fills the input but does not submit automatically.
- Initial result limit is 20 per domain; Items and Skills have independent Show more state.
- Full item/skill records remain modal dialogs.
- Do not cache live SQLite connections globally; cache only immutable vocabulary/index data. Open/close read-only services per submitted search/detail operation.
- If a selected domain database is invalid, show the validation error. Universal must not silently omit a broken domain.
- Images/icons are best-effort; missing media must not break cards.

---

## File Structure for This Phase

```text
components/
└── autocomplete_search/
    ├── index.html
    └── streamlit_bridge.js
toram_search/
├── autocomplete.py
├── router.py
└── models.py
ui/
├── search.py
├── results.py
├── sidebar.py
├── item_cards.py
├── item_dialog.py
├── skill_cards.py
└── skill_dialog.py
main.py
README.md
.streamlit/config.toml
tests/
├── test_autocomplete.py
├── test_router.py
├── test_universal_app.py
└── test_app_shell.py
```

## Historical Component Source

Restore/adapt the known working component from target repository commit:

```text
6560bc0c6bdaddf428feae1f00624b6c11cd1de3
components/autocomplete_search/index.html
components/autocomplete_search/streamlit_bridge.js
```

Do not restore the old CSV/pandas application. Only the component is reused.

## Locked Integration Interfaces

Add to `toram_search/models.py`:

```python
from dataclasses import dataclass
from typing import Literal

SuggestionKind = Literal["Item", "Skill", "Skill Tree", "Stat", "Item Type", "Ailment"]

@dataclass(frozen=True)
class AutocompleteSuggestion:
    value: str
    label: str
    kind: SuggestionKind

@dataclass(frozen=True)
class UniversalSearchOutcome:
    query: str
    items: ItemSearchOutcome | None = None
    skills: SkillSearchOutcome | None = None
```

```python
# toram_search/autocomplete.py
def build_autocomplete_index(
    items_path: Path,
    skills_path: Path,
) -> tuple[AutocompleteSuggestion, ...]: ...

def suggestions_for_mode(
    suggestions: tuple[AutocompleteSuggestion, ...],
    mode: DatabaseMode,
) -> tuple[AutocompleteSuggestion, ...]: ...
```

```python
# toram_search/router.py
def search_database(
    mode: DatabaseMode,
    query: str,
    *,
    items_path: Path,
    skills_path: Path,
) -> UniversalSearchOutcome: ...
```

```python
# ui/search.py
@dataclass(frozen=True)
class SearchSubmission:
    query: str
    nonce: int


def render_search_box(
    *,
    value: str,
    suggestions: tuple[AutocompleteSuggestion, ...],
    placeholder: str,
) -> SearchSubmission | None: ...
```

---

### Task 1: Build the Universal Autocomplete Vocabulary

**Files:**
- Create: `toram_search/autocomplete.py`
- Modify: `toram_search/models.py`
- Create: `tests/test_autocomplete.py`

**Interfaces:**
- Consumes: domain service `list_autocomplete_values()` methods.
- Produces: immutable `AutocompleteSuggestion` index and mode filtering.

- [ ] **Step 1: Write failing autocomplete tests**

Create `tests/test_autocomplete.py` using both test database factories:

```python
from pathlib import Path

from tests.item_db_factory import create_item_database
from tests.skill_db_factory import create_skill_database
from toram_search.autocomplete import build_autocomplete_index, suggestions_for_mode


def databases(tmp_path: Path) -> tuple[Path, Path]:
    items = tmp_path / "items.sqlite"
    skills = tmp_path / "skills.sqlite"
    create_item_database(items)
    create_skill_database(skills)
    return items, skills


def test_universal_index_contains_labeled_item_and_skill_values(tmp_path: Path) -> None:
    items, skills = databases(tmp_path)
    index = build_autocomplete_index(items, skills)
    pairs = {(row.value, row.kind) for row in index}
    assert ("Test Bow", "Item") in pairs
    assert ("Guardian", "Skill") in pairs
    assert ("Shield Skills", "Skill Tree") in pairs
    assert ("Critical Rate", "Stat") in pairs


def test_items_mode_excludes_skill_suggestions(tmp_path: Path) -> None:
    items, skills = databases(tmp_path)
    index = build_autocomplete_index(items, skills)
    filtered = suggestions_for_mode(index, "Items")
    assert all(row.kind in {"Item", "Stat", "Item Type"} for row in filtered)


def test_skills_mode_excludes_item_suggestions(tmp_path: Path) -> None:
    items, skills = databases(tmp_path)
    index = build_autocomplete_index(items, skills)
    filtered = suggestions_for_mode(index, "Skills")
    assert all(row.kind in {"Skill", "Skill Tree", "Ailment"} for row in filtered)
```

- [ ] **Step 2: Run and verify failure**

```bash
pytest tests/test_autocomplete.py -v
```

Expected: import/model failure.

- [ ] **Step 3: Add shared integration models**

Add the locked `SuggestionKind`, `AutocompleteSuggestion`, and `UniversalSearchOutcome` to `toram_search/models.py`. Import the item/skill outcome types only under `TYPE_CHECKING` if needed to avoid circular imports; alternatively store them as forward references with `from __future__ import annotations`.

- [ ] **Step 4: Implement index construction with short-lived services**

Create `toram_search/autocomplete.py`:

```python
def build_autocomplete_index(items_path: Path, skills_path: Path) -> tuple[AutocompleteSuggestion, ...]:
    item_service = ItemSearchService(items_path)
    skill_service = SkillSearchService(skills_path)
    try:
        values = [
            AutocompleteSuggestion(value=value, label=value, kind=kind)
            for value, kind in item_service.list_autocomplete_values()
        ]
        values.extend(
            AutocompleteSuggestion(value=value, label=value, kind=kind)
            for value, kind in skill_service.list_autocomplete_values()
        )
    finally:
        item_service.close()
        skill_service.close()
    # dedupe by normalized value + kind, then stable sort
    ...
```

Add common item aliases to autocomplete without changing parser behavior. For each alias in `toram_search.items.aliases.STAT_ALIASES`, when its canonical target resolves to an available stat, add:

```python
AutocompleteSuggestion(
    value=alias,
    label=f"{alias} — {canonical_stat}",
    kind="Stat",
)
```

This makes `cr`, `cd`, `pp`, `mres`, etc. discoverable.

`build_autocomplete_index()` must not retain either repository/service connection after returning.

- [ ] **Step 5: Implement mode filtering**

```python
_ALLOWED_BY_MODE = {
    "Universal": frozenset({"Item", "Skill", "Skill Tree", "Stat", "Item Type", "Ailment"}),
    "Items": frozenset({"Item", "Stat", "Item Type"}),
    "Skills": frozenset({"Skill", "Skill Tree", "Ailment"}),
}
```

Return the original stable order filtered by allowed kinds.

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_autocomplete.py -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add toram_search/models.py toram_search/autocomplete.py tests/test_autocomplete.py
git commit -m "feat: add Universal autocomplete vocabulary"
```

---

### Task 2: Add the Universal Deterministic Coordinator

**Files:**
- Create: `toram_search/router.py`
- Create: `tests/test_router.py`

**Interfaces:**
- Consumes: `DatabaseMode`, item/skill services.
- Produces: `search_database()` with explicit domain isolation.

- [ ] **Step 1: Write routing tests that spy on domain execution**

Create `tests/test_router.py`. Use monkeypatch service fakes or the test DB factories. At minimum test real outcomes:

```python
from pathlib import Path

from tests.item_db_factory import create_item_database
from tests.skill_db_factory import create_skill_database
from toram_search.router import search_database


def databases(tmp_path: Path) -> tuple[Path, Path]:
    items = tmp_path / "items.sqlite"
    skills = tmp_path / "skills.sqlite"
    create_item_database(items)
    create_skill_database(skills)
    return items, skills


def test_universal_returns_both_domain_outcomes(tmp_path: Path) -> None:
    items, skills = databases(tmp_path)
    outcome = search_database(
        "Universal", "critical rate", items_path=items, skills_path=skills
    )
    assert outcome.items is not None
    assert outcome.skills is not None


def test_items_mode_never_opens_missing_skill_database(tmp_path: Path) -> None:
    items = tmp_path / "items.sqlite"
    create_item_database(items)
    outcome = search_database(
        "Items",
        "Test Bow",
        items_path=items,
        skills_path=tmp_path / "missing-skills.sqlite",
    )
    assert outcome.items is not None
    assert outcome.skills is None


def test_skills_mode_never_opens_missing_item_database(tmp_path: Path) -> None:
    skills = tmp_path / "skills.sqlite"
    create_skill_database(skills)
    outcome = search_database(
        "Skills",
        "Guardian",
        items_path=tmp_path / "missing-items.sqlite",
        skills_path=skills,
    )
    assert outcome.items is None
    assert outcome.skills is not None
```

- [ ] **Step 2: Run and verify failure**

```bash
pytest tests/test_router.py -v
```

Expected: missing coordinator module.

- [ ] **Step 3: Implement short-lived domain service execution**

Create `toram_search/router.py`:

```python
def _search_items(query: str, path: Path) -> ItemSearchOutcome:
    service = ItemSearchService(path)
    try:
        return service.search(query)
    finally:
        service.close()


def _search_skills(query: str, path: Path) -> SkillSearchOutcome:
    service = SkillSearchService(path)
    try:
        return service.search(query)
    finally:
        service.close()


def search_database(mode, query, *, items_path, skills_path):
    items = _search_items(query, items_path) if mode in {"Universal", "Items"} else None
    skills = _search_skills(query, skills_path) if mode in {"Universal", "Skills"} else None
    return UniversalSearchOutcome(query=query, items=items, skills=skills)
```

Do not add an LLM router or heuristic that suppresses one domain in Universal mode.

- [ ] **Step 4: Run coordinator tests**

```bash
pytest tests/test_router.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add toram_search/router.py tests/test_router.py
git commit -m "feat: add Universal deterministic search coordinator"
```

---

### Task 3: Restore and Upgrade the Client-Side Autocomplete Component

**Files:**
- Create: `components/autocomplete_search/index.html`
- Create: `components/autocomplete_search/streamlit_bridge.js`
- Create: `ui/search.py`
- Modify: `tests/test_autocomplete.py`

**Interfaces:**
- Consumes: `AutocompleteSuggestion` objects.
- Produces: one `SearchSubmission` only when Enter/Search is used.

Component input arguments:

```json
{
  "value": "last submitted query",
  "suggestions": [
    {"value": "Guardian", "label": "Guardian", "kind": "Skill"},
    {"value": "cr", "label": "cr — Critical Rate", "kind": "Stat"}
  ],
  "placeholder": "Search items, stats, skills..."
}
```

Component output on submit only:

```json
{
  "event": "submit",
  "value": "Guardian",
  "nonce": 1770000000000
}
```

The `nonce` must change on every submission so submitting the same query twice still creates a component value change.

- [ ] **Step 1: Restore the historical component files from target repo history**

From commit `6560bc0c6bdaddf428feae1f00624b6c11cd1de3`, restore:

```bash
git show 6560bc0c6bdaddf428feae1f00624b6c11cd1de3:components/autocomplete_search/index.html > components/autocomplete_search/index.html
git show 6560bc0c6bdaddf428feae1f00624b6c11cd1de3:components/autocomplete_search/streamlit_bridge.js > components/autocomplete_search/streamlit_bridge.js
```

Do not restore old `main.py`, CSV, or pandas modules.

- [ ] **Step 2: Change suggestion data from strings to objects**

In `index.html`, store suggestions as objects with `value`, `label`, `kind`.

Change normalization/scoring to use both `value` and `label`:

```javascript
function suggestionText(item) {
  return `${item.value || ""} ${item.label || ""} ${item.kind || ""}`;
}
```

`getMatches()` scores `suggestionText(item)` but inserts `item.value` into the input when accepted.

- [ ] **Step 3: Render kind badges**

For each suggestion row render escaped label plus a small right-aligned kind badge. Do not use unescaped `innerHTML` for database values; create DOM nodes and assign `.textContent`.

- [ ] **Step 4: Remove every non-submit Python event**

Delete the old behavior:

```javascript
input.addEventListener("blur", () => sendValue(input.value));
```

On `input`, only call client-side `updatePreview()`.

On Tab or suggestion click:

```text
fill input
update preview
keep focus
DO NOT call Streamlit.setComponentValue
```

- [ ] **Step 5: Add a visible Search button inside the component**

Add:

```html
<button id="submit" type="button">Search</button>
```

Use a layout where the input occupies available width and button sits to the right on desktop, wrapping cleanly on narrow screens.

Create:

```javascript
function submitQuery() {
  const value = input.value.trim();
  if (!value) return;
  Streamlit.setComponentValue({
    event: "submit",
    value,
    nonce: Date.now(),
  });
}
```

Call `submitQuery()` only from Enter and Search button click.

- [ ] **Step 6: Keep Tab autocomplete advisory**

Tab accepts the current best suggestion but does not submit. Arrow-key selection may be added only if implemented fully; do not leave half-working keyboard state.

- [ ] **Step 7: Add the Python component wrapper**

Create `ui/search.py`:

```python
from dataclasses import dataclass
from pathlib import Path
import streamlit.components.v1 as components

_COMPONENT_PATH = Path(__file__).resolve().parents[1] / "components" / "autocomplete_search"
_autocomplete_search = components.declare_component(
    "autocomplete_search",
    path=str(_COMPONENT_PATH),
)

@dataclass(frozen=True)
class SearchSubmission:
    query: str
    nonce: int


def render_search_box(*, value, suggestions, placeholder):
    payload = _autocomplete_search(
        value=value,
        suggestions=[
            {"value": row.value, "label": row.label, "kind": row.kind}
            for row in suggestions
        ],
        placeholder=placeholder,
        key="database-search",
        default=None,
    )
    if not isinstance(payload, dict) or payload.get("event") != "submit":
        return None
    query = str(payload.get("value", "")).strip()
    nonce = payload.get("nonce")
    if not query or not isinstance(nonce, int):
        return None
    return SearchSubmission(query=query, nonce=nonce)
```

- [ ] **Step 8: Add a pure payload parser test**

Extract `parse_component_submission(payload: object) -> SearchSubmission | None` from `render_search_box()` and test:

```python
assert parse_component_submission({"event": "submit", "value": " Guardian ", "nonce": 1}) == SearchSubmission("Guardian", 1)
assert parse_component_submission({"event": "select", "value": "Guardian", "nonce": 1}) is None
assert parse_component_submission(None) is None
```

- [ ] **Step 9: Run tests**

```bash
pytest tests/test_autocomplete.py -v
```

Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add components/autocomplete_search ui/search.py tests/test_autocomplete.py
git commit -m "feat: add submit-only autocomplete search component"
```

---

### Task 4: Build Shared Result Rendering and Final Session State

**Files:**
- Create: `ui/results.py`
- Modify: `ui/sidebar.py`
- Modify: `main.py`
- Create: `tests/test_universal_app.py`

**Interfaces:**
- Consumes: `UniversalSearchOutcome`, item/skill rendering helpers.
- Produces: final search-first page with grouped Universal results.

Use these session-state keys exactly:

```text
database_mode
submitted_query
last_submission_nonce
search_outcome
item_visible_limit
skill_visible_limit
selected_item_id
selected_skill_id
```

- [ ] **Step 1: Write failing Universal AppTest coverage**

Create `tests/test_universal_app.py` with test databases via environment overrides. Because custom component interaction is limited in AppTest, test the coordinator/render layer via an injectable test query session-state hook rather than trying to simulate browser JavaScript.

Add one app-only test hook:

```python
# main.py
if os.environ.get("TORAM_TEST_QUERY"):
    submission = SearchSubmission(
        query=os.environ["TORAM_TEST_QUERY"],
        nonce=int(os.environ.get("TORAM_TEST_NONCE", "1")),
    )
else:
    submission = render_search_box(...)
```

This hook must be documented as test-only and must not alter production behavior when the environment variable is absent.

Tests:

```python
def test_universal_query_renders_item_and_skill_sections(...):
    # TORAM_TEST_QUERY = "critical rate"
    # assert headings include Items and Skills and no exception


def test_items_mode_can_run_when_skill_db_is_invalid(...):
    # selected mode Items; missing skill path must not stop app


def test_universal_mode_reports_broken_skill_db(...):
    # missing skill DB -> visible error, no silent partial Universal results
```

- [ ] **Step 2: Run and verify failure**

```bash
pytest tests/test_universal_app.py -v
```

Expected: integration behavior not implemented yet.

- [ ] **Step 3: Make database validation mode-aware**

Replace the foundation behavior that stops on any unhealthy database.

Rules:

```text
Universal -> both Items and Skills must validate
Items -> only Items must validate; Skills health may be shown unobtrusively but cannot block search
Skills -> only Skills must validate; Items health cannot block search
```

If a required database fails, show its exact `DatabaseHealth.error` and stop before invoking search.

- [ ] **Step 4: Cache autocomplete data, not DB connections**

In `main.py`:

```python
@st.cache_data(show_spinner=False)
def cached_autocomplete(items_path: str, skills_path: str, item_mtime: float, skill_mtime: float):
    return build_autocomplete_index(Path(items_path), Path(skills_path))
```

Pass file mtimes into the cache key so replacing either SQLite file invalidates the index automatically after Streamlit sees the new files.

Do not use `st.cache_resource` for repository/service objects.

- [ ] **Step 5: Replace temporary Items/Skills forms with one search box**

Remove the phase-specific `st.form` blocks. Render one `render_search_box()` regardless of mode.

Mode-specific placeholders:

```python
{
    "Universal": "Search items, stats, skills...",
    "Items": "Search items or stats...",
    "Skills": "Search skills or skill trees...",
}
```

On a new `SearchSubmission` whose nonce differs from `last_submission_nonce`:

```text
store submitted_query
store nonce
reset item_visible_limit = 20
reset skill_visible_limit = 20
clear selected ids
execute search_database(mode, query, ...)
store UniversalSearchOutcome
```

Changing a Show more button or opening/closing a dialog must not execute `search_database()` again.

- [ ] **Step 6: Add contextual example searches beneath the search box**

Examples:

```python
EXAMPLES = {
    "Universal": ("Critical Rate", "Guardian", "Shield Skills", "CR Bow", "Stun Skills"),
    "Items": ("CR Bow", "highest dex% crysta", "hp >= 5000 armor"),
    "Skills": ("Guardian", "Shield Skills", "guardian mp cost", "skills that inflict stun"),
}
```

Example buttons may directly create a `SearchSubmission` with a monotonically increasing session nonce and execute immediately because clicking them is an explicit submit action.

- [ ] **Step 7: Implement `ui/results.py`**

Expose:

```python
def render_universal_results(
    outcome: UniversalSearchOutcome,
    *,
    item_visible_limit: int,
    skill_visible_limit: int,
) -> tuple[int | None, str | None, bool, bool]:
    """Return selected item id, selected skill id, show_more_items, show_more_skills."""
```

Universal layout:

```text
Results for "<query>"

Items · <total result count>
[item cards]
[Show more items]

Skills · <total result count>
[skill cards]
[Show more skills]
```

If one domain returns `help`, `meta`, `structured`, `suggest`, or `refuse`, render its message in that domain section. Do not hide a valid result from the other domain.

Items-only / Skills-only mode can use the same renderer but omit the absent section.

- [ ] **Step 8: Wire independent Show more state**

Increment only the requested domain by 20:

```python
if show_more_items:
    st.session_state.item_visible_limit += 20
if show_more_skills:
    st.session_state.skill_visible_limit += 20
```

Never modify the stored search outcome.

- [ ] **Step 9: Wire item/skill detail dialogs with short-lived services**

When a clicked ID is returned:

```text
instantiate corresponding service
fetch exactly one detail record
close service
render dialog
```

Only one dialog may be invoked in one script run. If both selected IDs somehow exist, item selection takes priority and skill selection is cleared, or vice versa based on the latest click. Never call both dialog functions in the same run.

- [ ] **Step 10: Run Universal app tests**

```bash
pytest tests/test_universal_app.py tests/test_item_app.py tests/test_skill_app.py tests/test_app_shell.py -v
```

Expected: all pass after updating older phase tests for the single final search component.

- [ ] **Step 11: Commit**

```bash
git add main.py ui/results.py ui/sidebar.py tests/test_universal_app.py tests/test_item_app.py tests/test_skill_app.py tests/test_app_shell.py
git commit -m "feat: integrate Universal Streamlit search"
```

---

### Task 5: Finish User-Friendly Layout, Help, Credits, and Refinement Surface

**Files:**
- Modify: `main.py`
- Modify: `ui/sidebar.py`
- Modify: `ui/item_cards.py`
- Modify: `ui/skill_cards.py`
- Modify: `.streamlit/config.toml`
- Modify: `README.md`
- Modify: `tests/test_universal_app.py`

**Interfaces:**
- Consumes: final search state.
- Produces: polished responsive public page matching the approved design.

- [ ] **Step 1: Keep the sidebar minimal**

Final sidebar content:

```text
Toram Database

Database
● Universal
○ Items
○ Skills

About
Credits
GitHub
```

Use expanders or link buttons for About/Credits/GitHub; do not place permanent advanced filters in the sidebar.

Credits must clearly acknowledge the database/source project used by this repository and preserve any Coryn Club attribution already present in the historical app where applicable.

- [ ] **Step 2: Add a compact optional Filters control near search**

Version 1 filters are secondary and may use an expander/popover beside/below search. Implement only deterministic fields already supported:

Items:

```text
Item type
Sort: Relevance / Highest / Lowest when a stat is selected
```

Skills:

```text
Skill tree
Tier
Ailment
```

Universal may hide the control initially unless a result domain is selected/refined. Search must remain usable without opening Filters.

Do not invent subjective DPS/tank filters.

- [ ] **Step 3: Add contextual refinement buttons only from current results**

If implemented, derive chips from observed result fields (item types, skill trees, tiers, ailments). Clicking a chip is an explicit deterministic refinement action and may re-run search with a structured filter state.

If this cannot be implemented cleanly without duplicating parser behavior, omit contextual chips from v1 rather than shipping a partial/inconsistent control. The approved design marks them optional.

- [ ] **Step 4: Ensure responsive cards**

Use `st.columns(2)` only on wide layouts where card content remains readable. Keep a one-column fallback path for narrow/mobile layout. Do not rely on unsupported browser-width detection; prefer a simple Streamlit layout that naturally stacks when constrained, or default to one-column if two-column behavior is unreliable.

Correctness/readability has priority over forcing two columns.

- [ ] **Step 5: Keep card summaries compact**

Item card maximum summary:

```text
name
type
up to 3 query-relevant/matched stats
View details
```

Skill card maximum summary:

```text
name
tree · tier
MP / type
one matched field when relevant
View details
```

- [ ] **Step 6: Add deterministic Search Help**

Expose help examples without an LLM:

```text
Item name: Amnis Rapier
Stat + type: cr bow
Numeric: hp >= 5000 armor
Boolean: hp > 5000 and cr bow
Skill: Guardian
Skill tree: shield skills
Skill property: guardian mp cost
Ailment: skills that inflict stun
```

- [ ] **Step 7: Update README with final architecture and UI behavior**

Document:

```text
Universal / Items / Skills
autocomplete is client-side advisory
Enter/Search submits
items.sqlite / skills.sqlite are drop-in copies from filter_search
no LLM/RAG
main.py is Streamlit entry point
```

- [ ] **Step 8: Add AppTest assertions for final labels**

Assert title, subtitle, mode selector, and no exception. Do not make brittle assertions on custom component iframe internals.

- [ ] **Step 9: Run full test suite**

```bash
pytest -q
```

Expected: all tests pass.

- [ ] **Step 10: Commit**

```bash
git add main.py ui .streamlit/config.toml README.md tests/test_universal_app.py
git commit -m "feat: polish Streamlit Toram database UI"
```

---

### Task 6: Deployment and Regression Verification

**Files:**
- Modify only if verification exposes a bug; otherwise no file changes.

- [ ] **Step 1: Run the complete automated suite**

```bash
pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Validate packaged DB schemas**

```bash
python - <<'PY'
from toram_search.database import validate_databases
health = validate_databases()
assert all(row.ok for row in health), health
print(health)
PY
```

Expected: both healthy.

- [ ] **Step 3: Scan runtime dependencies/source for forbidden LLM stack**

```bash
python - <<'PY'
from pathlib import Path
runtime = Path("requirements.txt").read_text().casefold()
source = "\n".join(
    path.read_text(errors="ignore")
    for root in (Path("main.py"), Path("toram_search"), Path("ui"))
    for path in ([root] if root.is_file() else root.rglob("*.py"))
).casefold()
for forbidden in ("ollama", "qwen", "gemma", "sentence_transformers", "discord.py", "groundedskillrag"):
    assert forbidden not in runtime, ("requirements", forbidden)
    assert forbidden not in source, ("source", forbidden)
PY
```

Expected: exit 0.

- [ ] **Step 4: Verify no public write statements exist**

```bash
python - <<'PY'
from pathlib import Path
text = "\n".join(path.read_text(errors="ignore") for path in Path("toram_search").rglob("*.py")).casefold()
for phrase in ("insert into items", "update items", "delete from items", "insert into skills", "update skills", "delete from skills"):
    assert phrase not in text, phrase
PY
```

Expected: exit 0.

- [ ] **Step 5: Manually run Streamlit**

```bash
streamlit run main.py --server.headless true
```

Verify all three modes and these representative submissions:

```text
Universal: critical rate
Universal: Guardian
Universal: shield skills
Items: CR Bow
Items: highest dex% crysta
Skills: guardian mp cost
Skills: skills that inflict stun
Skills: how does Hard Hit work?
```

Also verify:

```text
typing does not trigger a server rerun/search
Tab fills a suggestion without submitting
clicking suggestion fills without submitting
Enter submits
Search button submits
submitting the same query twice still works
Show more does not repeat DB search
item detail modal opens/closes cleanly
skill detail modal opens/closes cleanly
mobile/narrow layout remains readable
```

- [ ] **Step 6: Verify deployment metadata**

Confirm Streamlit Community Cloud is configured to use:

```text
Repository: KarenYuusha/toram-item-search
Branch: the implementation branch until merged, then main
Main file path: main.py
```

- [ ] **Step 7: Check update workflow once with copied DBs**

After making backup copies, replace from the reference repo:

```bash
cp ../filter_search/coryn_data/database/items.sqlite ./items.sqlite
cp ../filter_search/coryn_data/database/skills.sqlite ./skills.sqlite
pytest -q
```

Expected: tests and schema validation pass without any rebuild step.

- [ ] **Step 8: Final implementation commit only if verification required fixes**

If no fixes were required, do not create an empty commit. If fixes were needed:

```bash
git add <only verified fix files>
git commit -m "fix: resolve Streamlit integration regressions"
```

---

## Final Acceptance Checklist

The implementation is complete only when all of the following are true:

- `main.py` runs the public Streamlit UI.
- Universal is the default database mode.
- Items and Skills modes restrict execution to their own database.
- Universal returns all applicable item and skill outcomes in separate sections.
- autocomplete shows Item / Skill / Skill Tree / Stat / Item Type / Ailment labels.
- typing does not execute the full search.
- Enter and Search button execute the full search.
- compact cards are used for results.
- item and skill full records use dialogs.
- matched stats/properties are visible on cards.
- Show more is independent per domain.
- failures provide deterministic guidance/suggestions.
- subjective build/DPS/tank questions are not invented/answered subjectively.
- `items.sqlite` and `skills.sqlite` remain direct drop-in copies from `filter_search`.
- both DBs are opened read-only.
- no LLM/RAG/embedding runtime exists.
- full automated suite passes.
- Streamlit Community Cloud can start from root `main.py`.
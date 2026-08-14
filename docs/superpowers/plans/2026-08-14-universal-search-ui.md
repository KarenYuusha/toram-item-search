# Universal Search and Streamlit UI Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the product by combining deterministic item and skill services behind the Universal / Items / Skills sidebar selector, replacing temporary native forms with a client-side autocomplete + Enter/Search submission component, and polishing the responsive Streamlit result/detail experience for deployment.

**Architecture:** A frontend-neutral coordinator executes only the domain services allowed by the selected mode. Autocomplete vocabulary is also built per selected mode, so Items never requires a working skills database and Skills never requires a working items database. Suggestions are filtered entirely inside a small custom Streamlit HTML component restored from the repository's older working implementation. Typing never performs a database query; only Enter or the component Search button emits a submit event to Python. Session state stores the last submitted outcomes and independent show-more limits. No live SQLite connection is cached globally.

**Tech Stack:** Python 3.12, Streamlit 1.61.x, Streamlit components API, browser JavaScript/HTML/CSS, SQLite, RapidFuzz, pytest/AppTest.

## Global Constraints

- Target repository is only `KarenYuusha/toram-item-search`.
- `KarenYuusha/filter_search` remains reference/source only.
- Root `main.py` is the public Streamlit entry point.
- No LLM, embeddings, RAG, Ollama, Qwen, Gemma, Discord, or external search service.
- Universal is the default sidebar mode.
- Universal evaluates both deterministic domains and groups applicable results by Items and Skills.
- Items mode must not open/search/validate the skill database as a requirement for use.
- Skills mode must not open/search/validate the item database as a requirement for use.
- Universal requires both databases to validate; it must not silently omit a broken domain.
- Typing/autocomplete must not execute full database search.
- Full search occurs only on Enter or Search button.
- Suggestion click/Tab fills the input but does not submit automatically.
- Initial result limit is 20 per domain; Items and Skills have independent Show more state.
- Full item/skill records remain modal dialogs.
- Cache immutable autocomplete data only; do not cache live SQLite connections/services.
- Images/icons are best-effort; missing media must not break cards.
- Version 1 deliberately omits a permanent/manual advanced-filter panel. Search syntax, examples, deterministic suggestions, and result-specific Show more are the v1 refinement surface. This preserves the approved search-first UX and avoids making users learn schema controls before searching.

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

Restore/adapt only these files from target repository commit `6560bc0c6bdaddf428feae1f00624b6c11cd1de3`:

```text
components/autocomplete_search/index.html
components/autocomplete_search/streamlit_bridge.js
```

Do not restore the old CSV/pandas application or its old `main.py`.

## Locked Integration Models

Add to `toram_search/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from toram_search.items.models import ItemSearchOutcome
    from toram_search.skills.models import SkillSearchOutcome

SuggestionKind = Literal[
    "Item",
    "Skill",
    "Skill Tree",
    "Stat",
    "Item Type",
    "Ailment",
]


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

`from __future__ import annotations` prevents runtime evaluation of the type-only references.

---

### Task 1: Build Mode-Aware Autocomplete Vocabulary

**Files:**
- Create: `toram_search/autocomplete.py`
- Modify: `toram_search/models.py`
- Create: `tests/test_autocomplete.py`

**Interfaces:**
- Consumes: domain service `list_autocomplete_values()` methods.
- Produces: immutable suggestion tuples for one selected database mode.

Target signatures:

```python
def build_item_autocomplete_index(items_path: Path) -> tuple[AutocompleteSuggestion, ...]:
    ...


def build_skill_autocomplete_index(skills_path: Path) -> tuple[AutocompleteSuggestion, ...]:
    ...


def build_autocomplete_index(
    mode: DatabaseMode,
    *,
    items_path: Path,
    skills_path: Path,
) -> tuple[AutocompleteSuggestion, ...]:
    ...
```

The first two functions open only their own domain service. The third dispatches:

```text
Universal -> item index + skill index
Items     -> item index only
Skills    -> skill index only
```

- [ ] **Step 1: Write failing mode-isolation tests**

Create `tests/test_autocomplete.py` using the item and skill test database factories:

```python
from pathlib import Path

from tests.item_db_factory import create_item_database
from tests.skill_db_factory import create_skill_database
from toram_search.autocomplete import build_autocomplete_index


def test_universal_index_contains_both_domains(tmp_path: Path) -> None:
    items = tmp_path / "items.sqlite"
    skills = tmp_path / "skills.sqlite"
    create_item_database(items)
    create_skill_database(skills)

    index = build_autocomplete_index(
        "Universal",
        items_path=items,
        skills_path=skills,
    )

    pairs = {(row.value, row.kind) for row in index}
    assert ("Test Bow", "Item") in pairs
    assert ("Guardian", "Skill") in pairs
    assert ("Shield Skills", "Skill Tree") in pairs
    assert ("Critical Rate", "Stat") in pairs


def test_items_index_does_not_open_missing_skill_database(tmp_path: Path) -> None:
    items = tmp_path / "items.sqlite"
    create_item_database(items)

    index = build_autocomplete_index(
        "Items",
        items_path=items,
        skills_path=tmp_path / "missing-skills.sqlite",
    )

    assert any(row.kind == "Item" for row in index)
    assert all(row.kind in {"Item", "Stat", "Item Type"} for row in index)


def test_skills_index_does_not_open_missing_item_database(tmp_path: Path) -> None:
    skills = tmp_path / "skills.sqlite"
    create_skill_database(skills)

    index = build_autocomplete_index(
        "Skills",
        items_path=tmp_path / "missing-items.sqlite",
        skills_path=skills,
    )

    assert any(row.kind == "Skill" for row in index)
    assert all(row.kind in {"Skill", "Skill Tree", "Ailment"} for row in index)
```

- [ ] **Step 2: Run tests and verify failure**

```bash
pytest tests/test_autocomplete.py -v
```

Expected: import/model failure because the integration module does not exist.

- [ ] **Step 3: Add integration dataclasses**

Add the locked models above to `toram_search/models.py`.

- [ ] **Step 4: Implement item autocomplete construction**

Create `toram_search/autocomplete.py`. `build_item_autocomplete_index()` must:

1. instantiate `ItemSearchService(items_path)`;
2. collect `(value, kind)` rows from `list_autocomplete_values()`;
3. close the service in `finally`;
4. add validated stat aliases from `STAT_ALIASES` only when the alias target resolves to a real available stat;
5. deduplicate by `(normalize_stat_text(value), kind)`;
6. stable-sort by `value.casefold(), kind`.

Alias display shape:

```python
AutocompleteSuggestion(
    value=alias,
    label=f"{alias} — {canonical_stat}",
    kind="Stat",
)
```

This makes `cr`, `cd`, `pp`, `mres`, and other established aliases discoverable without changing parser semantics.

- [ ] **Step 5: Implement skill autocomplete construction**

`build_skill_autocomplete_index()` must:

1. instantiate `SkillSearchService(skills_path)`;
2. collect Skill / Skill Tree / Ailment rows;
3. close in `finally`;
4. deduplicate by `(normalize_skill_name(value), kind)`;
5. stable-sort by `value.casefold(), kind`.

- [ ] **Step 6: Implement exact mode dispatch**

```python
def build_autocomplete_index(mode, *, items_path, skills_path):
    if mode == "Items":
        return build_item_autocomplete_index(items_path)
    if mode == "Skills":
        return build_skill_autocomplete_index(skills_path)
    if mode == "Universal":
        rows = (*build_item_autocomplete_index(items_path), *build_skill_autocomplete_index(skills_path))
        return tuple(rows)
    raise ValueError(f"Unsupported database mode: {mode}")
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/test_autocomplete.py -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add toram_search/models.py toram_search/autocomplete.py tests/test_autocomplete.py
git commit -m "feat: add mode-aware autocomplete vocabulary"
```

---

### Task 2: Add the Universal Deterministic Coordinator

**Files:**
- Create: `toram_search/router.py`
- Create: `tests/test_router.py`

**Interfaces:**
- Consumes: `DatabaseMode`, item service, skill service.
- Produces: `search_database()` with strict domain isolation.

Target signature:

```python
def search_database(
    mode: DatabaseMode,
    query: str,
    *,
    items_path: Path,
    skills_path: Path,
) -> UniversalSearchOutcome:
    ...
```

- [ ] **Step 1: Write failing domain-isolation tests**

Create `tests/test_router.py`:

```python
from pathlib import Path

from tests.item_db_factory import create_item_database
from tests.skill_db_factory import create_skill_database
from toram_search.router import search_database


def test_universal_executes_both_domains(tmp_path: Path) -> None:
    items = tmp_path / "items.sqlite"
    skills = tmp_path / "skills.sqlite"
    create_item_database(items)
    create_skill_database(skills)

    outcome = search_database(
        "Universal",
        "critical rate",
        items_path=items,
        skills_path=skills,
    )

    assert outcome.items is not None
    assert outcome.skills is not None


def test_items_mode_does_not_open_missing_skills_database(tmp_path: Path) -> None:
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


def test_skills_mode_does_not_open_missing_items_database(tmp_path: Path) -> None:
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

- [ ] **Step 3: Implement short-lived service helpers**

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
```

- [ ] **Step 4: Implement coordinator dispatch**

```python
def search_database(mode, query, *, items_path, skills_path):
    if mode == "Items":
        return UniversalSearchOutcome(
            query=query,
            items=_search_items(query, items_path),
        )
    if mode == "Skills":
        return UniversalSearchOutcome(
            query=query,
            skills=_search_skills(query, skills_path),
        )
    if mode == "Universal":
        return UniversalSearchOutcome(
            query=query,
            items=_search_items(query, items_path),
            skills=_search_skills(query, skills_path),
        )
    raise ValueError(f"Unsupported database mode: {mode}")
```

Do not add an LLM router or heuristic that suppresses a domain in Universal mode.

- [ ] **Step 5: Run coordinator tests**

```bash
pytest tests/test_router.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

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
- Produces: a `SearchSubmission` only when Enter/Search is used.

Component input:

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

`nonce` changes on every submission so submitting the same query twice still produces a new component value.

- [ ] **Step 1: Restore only the old component files**

```bash
mkdir -p components/autocomplete_search
git show 6560bc0c6bdaddf428feae1f00624b6c11cd1de3:components/autocomplete_search/index.html > components/autocomplete_search/index.html
git show 6560bc0c6bdaddf428feae1f00624b6c11cd1de3:components/autocomplete_search/streamlit_bridge.js > components/autocomplete_search/streamlit_bridge.js
```

- [ ] **Step 2: Convert suggestion data from strings to objects**

In `index.html`, use objects with `value`, `label`, `kind`. Score this combined client-side text:

```javascript
function suggestionText(item) {
  return `${item.value || ""} ${item.label || ""} ${item.kind || ""}`;
}
```

When a suggestion is accepted, put `item.value` into the input.

- [ ] **Step 3: Render safe kind badges**

Create DOM nodes and assign `.textContent` for both label and kind. Do not interpolate database values into `innerHTML`.

- [ ] **Step 4: Remove all non-submit Python events**

Delete the old blur send:

```javascript
input.addEventListener("blur", () => sendValue(input.value));
```

On ordinary `input`, only run browser-side preview/filtering.

On Tab or suggestion click:

```text
fill input
update preview
keep focus
do not call Streamlit.setComponentValue
```

- [ ] **Step 5: Add the visible Search button inside the component**

Add:

```html
<button id="submit" type="button">Search</button>
```

Implement:

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

- [ ] **Step 6: Add a Python wrapper with a pure payload parser**

Create `ui/search.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import streamlit.components.v1 as components

from toram_search.models import AutocompleteSuggestion

_COMPONENT_PATH = Path(__file__).resolve().parents[1] / "components" / "autocomplete_search"
_autocomplete_search = components.declare_component(
    "autocomplete_search",
    path=str(_COMPONENT_PATH),
)


@dataclass(frozen=True)
class SearchSubmission:
    query: str
    nonce: int


def parse_component_submission(payload: object) -> SearchSubmission | None:
    if not isinstance(payload, dict) or payload.get("event") != "submit":
        return None
    query = str(payload.get("value", "")).strip()
    nonce = payload.get("nonce")
    if not query or not isinstance(nonce, int):
        return None
    return SearchSubmission(query, nonce)


def render_search_box(
    *,
    value: str,
    suggestions: tuple[AutocompleteSuggestion, ...],
    placeholder: str,
) -> SearchSubmission | None:
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
    return parse_component_submission(payload)
```

- [ ] **Step 7: Test payload parsing**

Append:

```python
from ui.search import SearchSubmission, parse_component_submission


def test_only_submit_payload_creates_search() -> None:
    assert parse_component_submission(
        {"event": "submit", "value": " Guardian ", "nonce": 1}
    ) == SearchSubmission("Guardian", 1)
    assert parse_component_submission(
        {"event": "select", "value": "Guardian", "nonce": 2}
    ) is None
    assert parse_component_submission(None) is None
```

- [ ] **Step 8: Run tests**

```bash
pytest tests/test_autocomplete.py -v
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add components/autocomplete_search ui/search.py tests/test_autocomplete.py
git commit -m "feat: add submit-only autocomplete search component"
```

---

### Task 4: Make Database Health and Autocomplete Caching Mode-Aware

**Files:**
- Modify: `main.py`
- Modify: `tests/test_app_shell.py`
- Create: `tests/test_universal_app.py`

**Interfaces:**
- Consumes: `validate_item_database`, `validate_skill_database`, `build_autocomplete_index`.
- Produces: correct operation when only the selected domain is healthy.

- [ ] **Step 1: Write failing AppTest health-isolation tests**

Using environment path overrides from the item/skill phases, test:

```text
Items + valid item DB + missing skill DB -> app remains usable
Skills + valid skill DB + missing item DB -> app remains usable
Universal + either DB missing -> visible error and no search execution
```

Use assertions on visible `st.error`/absence of `app.exception`, not private Streamlit internals.

- [ ] **Step 2: Replace foundation all-or-nothing validation**

In `main.py` resolve both configured paths, but validate only what the mode requires:

```python
if mode == "Items":
    required_health = (validate_item_database(items_path),)
elif mode == "Skills":
    required_health = (validate_skill_database(skills_path),)
else:
    required_health = (
        validate_item_database(items_path),
        validate_skill_database(skills_path),
    )
```

If any required health row is unhealthy, display each error then `st.stop()`.

- [ ] **Step 3: Cache immutable mode-specific indexes**

Add:

```python
@st.cache_data(show_spinner=False)
def cached_autocomplete(
    mode: str,
    items_path: str,
    skills_path: str,
    item_mtime: float | None,
    skill_mtime: float | None,
):
    return build_autocomplete_index(
        mode,
        items_path=Path(items_path),
        skills_path=Path(skills_path),
    )
```

For Items mode, pass `skill_mtime=None` and do not stat the missing skill path as a requirement. For Skills mode, pass `item_mtime=None`. Universal passes both mtimes.

This ensures replacing a SQLite file invalidates only relevant cached vocabulary.

- [ ] **Step 4: Run focused tests**

```bash
pytest tests/test_universal_app.py tests/test_app_shell.py -v
```

Expected: mode-isolation health tests pass.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_universal_app.py tests/test_app_shell.py
git commit -m "fix: isolate database health by selected mode"
```

---

### Task 5: Replace Temporary Forms With One Final Search Experience

**Files:**
- Modify: `main.py`
- Create: `ui/results.py`
- Modify: `ui/sidebar.py`
- Modify: `tests/test_universal_app.py`
- Modify: `tests/test_item_app.py`
- Modify: `tests/test_skill_app.py`

**Interfaces:**
- Consumes: `SearchSubmission`, `search_database`, item/skill renderers.
- Produces: final search-first Universal/Items/Skills page.

Use these session keys:

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

- [ ] **Step 1: Add a deterministic AppTest submission hook**

Custom component JavaScript is not reliably driven by `AppTest`, so use this production-inert hook:

```python
def test_submission_from_environment() -> SearchSubmission | None:
    query = os.environ.get("TORAM_TEST_QUERY")
    if not query:
        return None
    return SearchSubmission(
        query=query,
        nonce=int(os.environ.get("TORAM_TEST_NONCE", "1")),
    )
```

In normal use the environment variable is absent and `render_search_box()` is used.

- [ ] **Step 2: Write failing Universal result tests**

With both fixture DBs and `TORAM_TEST_QUERY`, assert:

```text
Universal query -> Items section exists and Skills section exists
Items mode -> only Items section rendered
Skills mode -> only Skills section rendered
new nonce + same query -> search accepted again
```

Do not test iframe HTML with AppTest.

- [ ] **Step 3: Remove temporary native `st.form` search UIs**

Render one component for every mode:

```python
PLACEHOLDERS = {
    "Universal": "Search items, stats, skills...",
    "Items": "Search items or stats...",
    "Skills": "Search skills or skill trees...",
}
```

Choose environment test submission first when present; otherwise use `render_search_box()`.

- [ ] **Step 4: Execute only on a new explicit submission nonce**

When `submission is not None` and its nonce differs from `last_submission_nonce`:

```text
store submitted_query
store last_submission_nonce
reset item_visible_limit to 20
reset skill_visible_limit to 20
clear selected item/skill ids
call search_database(mode, query, paths)
store returned UniversalSearchOutcome
```

Changing sidebar mode clears stale `search_outcome` so results from another domain are never mislabeled.

- [ ] **Step 5: Add explicit example-submit buttons**

Use:

```python
EXAMPLES = {
    "Universal": ("Critical Rate", "Guardian", "Shield Skills", "CR Bow", "Stun Skills"),
    "Items": ("CR Bow", "highest dex% crysta", "hp >= 5000 armor"),
    "Skills": ("Guardian", "Shield Skills", "guardian mp cost", "skills that inflict stun"),
}
```

Clicking an example is an explicit submit action. Generate a monotonically increasing integer from session state rather than current wall-clock time, then call the same submission handler used by the component.

- [ ] **Step 6: Implement shared result rendering**

Create `ui/results.py`:

```python
def render_universal_results(
    outcome: UniversalSearchOutcome,
    *,
    item_visible_limit: int,
    skill_visible_limit: int,
) -> tuple[int | None, str | None, bool, bool]:
    """Return selected item id, selected skill id, show-more-items, show-more-skills."""
```

Universal layout:

```text
Results for "<query>"

Items · <total>
[item cards]
[Show more items]

Skills · <total>
[skill cards]
[Show more skills]
```

For a domain outcome that is `help`, `meta`, `structured`, `compare`, `clarify`, `suggest`, `refuse`, or `not_found`, render its deterministic message in that domain section while preserving any valid result cards supplied by that outcome.

- [ ] **Step 7: Wire independent Show more state**

```python
if show_more_items:
    st.session_state.item_visible_limit += 20
if show_more_skills:
    st.session_state.skill_visible_limit += 20
```

Do not call `search_database()` from Show more.

- [ ] **Step 8: Wire one detail dialog per run**

When an item ID is selected:

```text
open short-lived ItemSearchService
fetch get_item(id)
close service
render item dialog
clear any skill selection
```

When a skill ID is selected, perform the symmetric skill flow. Never call both dialog functions in one script run.

- [ ] **Step 9: Run app tests**

```bash
pytest tests/test_universal_app.py tests/test_item_app.py tests/test_skill_app.py tests/test_app_shell.py -v
```

Expected: all pass after adapting the older phase tests to the final single search component.

- [ ] **Step 10: Commit**

```bash
git add main.py ui/results.py ui/sidebar.py tests/test_universal_app.py tests/test_item_app.py tests/test_skill_app.py tests/test_app_shell.py
git commit -m "feat: integrate Universal Streamlit search"
```

---

### Task 6: Finish Search-First Layout, Help, Credits, and Responsive Cards

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
- Produces: approved public UX without a permanent advanced-filter form.

- [ ] **Step 1: Finalize the minimal sidebar**

Final content:

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

Use Streamlit links/expanders for secondary information. Keep search controls out of the sidebar.

- [ ] **Step 2: Add deterministic Search Help**

Show examples and syntax from stored/static help only:

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

No generated help answer is required.

- [ ] **Step 3: Keep cards compact**

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
one query-matched field when relevant
View details
```

Prefer one-column rendering if a stable responsive two-column implementation cannot be achieved with Streamlit without brittle browser detection. Readability is more important than forced density.

- [ ] **Step 4: Add final credits and links**

Preserve Coryn Club/source attribution from the historical app where applicable and add a GitHub link for `KarenYuusha/toram-item-search`. Do not present `filter_search` as the deployed website repository.

- [ ] **Step 5: Update README**

Document:

```text
Universal / Items / Skills behavior
client-side autocomplete
Enter/Search-only execution
items.sqlite / skills.sqlite are direct drop-in copies from filter_search
no LLM/RAG/embeddings
root main.py deployment entry point
```

- [ ] **Step 6: Add final AppTest assertions**

Assert title, subtitle, three database modes, no startup exception with fixture DBs, and expected domain section headings after test submissions. Avoid brittle iframe internals.

- [ ] **Step 7: Run all tests**

```bash
pytest -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add main.py ui .streamlit/config.toml README.md tests/test_universal_app.py
git commit -m "feat: polish Streamlit Toram database UI"
```

---

### Task 7: Deployment and Regression Verification

**Files:**
- Modify only when a failing verification demonstrates a concrete bug.

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

- [ ] **Step 3: Scan runtime source/dependencies for forbidden model stack**

```bash
python - <<'PY'
from pathlib import Path

runtime = Path("requirements.txt").read_text().casefold()
paths = [Path("main.py"), *Path("toram_search").rglob("*.py"), *Path("ui").rglob("*.py")]
source = "\n".join(path.read_text(errors="ignore") for path in paths).casefold()

for forbidden in (
    "ollama",
    "qwen",
    "gemma",
    "sentence_transformers",
    "discord.py",
    "groundedskillrag",
):
    assert forbidden not in runtime, ("requirements", forbidden)
    assert forbidden not in source, ("source", forbidden)
PY
```

Expected: exit 0.

- [ ] **Step 4: Verify no public mutation SQL exists**

```bash
python - <<'PY'
from pathlib import Path
text = "\n".join(path.read_text(errors="ignore") for path in Path("toram_search").rglob("*.py")).casefold()
for phrase in (
    "insert into items",
    "update items",
    "delete from items",
    "insert into skills",
    "update skills",
    "delete from skills",
):
    assert phrase not in text, phrase
PY
```

Expected: exit 0.

- [ ] **Step 5: Launch Streamlit manually**

```bash
streamlit run main.py --server.headless true
```

Exercise:

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

Verify:

```text
typing does not trigger full search
Tab fills without submitting
suggestion click fills without submitting
Enter submits
Search button submits
same query can be submitted twice
Show more does not re-query
item dialog opens/closes
skill dialog opens/closes
narrow/mobile layout stays readable
```

- [ ] **Step 6: Verify deployment settings**

Streamlit Community Cloud must use:

```text
Repository: KarenYuusha/toram-item-search
Main file path: main.py
```

Use the implementation branch for preview if desired; production uses `main` after merge.

- [ ] **Step 7: Verify the actual database replacement workflow**

```bash
cp ../filter_search/coryn_data/database/items.sqlite ./items.sqlite
cp ../filter_search/coryn_data/database/skills.sqlite ./skills.sqlite
pytest -q
```

Expected: tests/schema checks pass without any build or migration command.

- [ ] **Step 8: Commit verification fixes only when files actually changed**

If verification required fixes, first inspect exactly what changed:

```bash
git status --short
git diff --check
```

Stage only the concrete files shown by `git status --short`, then verify the staged diff:

```bash
git diff --cached --check
git diff --cached --stat
git commit -m "fix: resolve Streamlit integration regressions"
```

If no files changed, do not create an empty commit.

---

## Final Acceptance Checklist

The implementation is complete only when all of the following are true:

- `main.py` runs the public Streamlit UI.
- Universal is the default database mode.
- Items mode remains usable even when the skill DB path is unavailable.
- Skills mode remains usable even when the item DB path is unavailable.
- Universal requires both DBs and never silently serves incomplete mixed results.
- Universal returns applicable item and skill outcomes in separate sections.
- autocomplete shows Item / Skill / Skill Tree / Stat / Item Type / Ailment labels.
- typing does not execute full search.
- Enter and Search button execute full search.
- suggestion click/Tab only fills the input.
- compact cards are used for results.
- item and skill full records use dialogs.
- matched stats/properties are visible on cards.
- Show more is independent per domain.
- failures provide deterministic guidance/suggestions.
- subjective build/DPS/tank questions are not answered subjectively.
- `items.sqlite` and `skills.sqlite` remain direct drop-in copies from `filter_search`.
- both DBs are opened read-only.
- no LLM/RAG/embedding runtime exists.
- full automated suite passes.
- Streamlit Community Cloud starts from root `main.py`.
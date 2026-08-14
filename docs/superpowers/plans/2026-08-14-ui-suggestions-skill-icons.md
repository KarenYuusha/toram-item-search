# UI Suggestions and Skill Icons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move suggested searches above the search bar, make examples/corrections fill-only clickable controls, and display the real individual skill icons copied from `filter_search/coryn_skill_icons` in Streamlit skill cards and detail dialogs.

**Architecture:** Keep `toram-item-search` standalone. Copy the canonical icon directory into the Streamlit repository and adapt the deterministic `SkillIconCatalog` resolver into `toram_search/skill_icons.py`. Keep query execution submit-only: top examples and result corrections only update `st.session_state.query`; only the custom component's nonce-backed `submit` event reaches `search_database`.

**Tech Stack:** Python 3.12, Streamlit 1.61.x, pytest 8.x, existing custom Streamlit component, checked-in PNG assets.

## Global Constraints

- Target repository is only `KarenYuusha/toram-item-search`.
- `KarenYuusha/filter_search` is source/reference-only and must not be modified.
- Copy `filter_search/coryn_skill_icons/` into root-level `toram-item-search/coryn_skill_icons/`.
- Do not add icon fields or presentation metadata to `skills.sqlite`.
- Do not add LLM, RAG, semantic-search, embedding, Discord, or runtime cross-repository dependencies.
- Clicking any example or correction suggestion fills the search field only; it must not execute a query.
- Enter or the Search button remains the only action that executes a query.
- Existing Universal / Items / Skills database-mode isolation remains unchanged.
- Missing or ambiguous icons return no icon and never break search/rendering.
- Run the complete pytest suite and `python -m compileall -q main.py toram_search ui` before integration.

---

## File Structure

**Create**

- `coryn_skill_icons/` — exact checked-in copy of the canonical source icon tree.
- `toram_search/skill_icons.py` — frontend-neutral deterministic icon resolver.
- `tests/test_skill_icons.py` — resolver tests plus a real checked-in asset smoke test.

**Modify**

- `main.py` — examples above search, fill-only state updates, correction fill coordination.
- `ui/results.py` — clickable correction suggestions that return a selected fill value.
- `ui/skill_cards.py` — individual skill thumbnail rendering.
- `ui/skill_dialog.py` — individual skill icon in the detail dialog.
- `tests/test_ui_contract.py` — ordering/fill-only/icon contracts.
- `tests/test_app_shell.py` — AppTest coverage for top example fill-only behavior.

**Do not modify unless a failing regression proves it necessary**

- `components/autocomplete_search/index.html` — it already accepts an external `value` and emits only nonce-backed `submit` events for Enter/Search.
- `items.sqlite`
- `skills.sqlite`
- deterministic item/skill parser behavior.

---

### Task 1: Copy Skill Icons and Add the Shared Resolver

**Files:**
- Copy: `filter_search/coryn_skill_icons/` → `coryn_skill_icons/`
- Create: `toram_search/skill_icons.py`
- Create: `tests/test_skill_icons.py`

**Interfaces:**
- Consumes: local root-level `coryn_skill_icons/`; `tree_name: str`; `skill_name: str`.
- Produces: `normalize_icon_key(value: str) -> str`; `SkillIconCatalog.resolve(tree_name: str, skill_name: str) -> Path | None`; `DEFAULT_SKILL_ICON_CATALOG`.

- [ ] **Step 1: Copy the canonical icon directory**

When the repositories are sibling checkouts:

```bash
rm -rf coryn_skill_icons
cp -R ../filter_search/coryn_skill_icons ./coryn_skill_icons
```

If the source checkout is elsewhere, use its actual path while preserving the target as `./coryn_skill_icons`.

Verify representative assets:

```bash
test -f 'coryn_skill_icons/Shield/Guardian.png'
test -f 'coryn_skill_icons/Shield/Shield Bash.png'
find coryn_skill_icons -type f -name '*.png' | sort | head
```

Expected: both `test -f` commands exit 0 and PNG paths are printed.

- [ ] **Step 2: Write failing resolver tests**

Create `tests/test_skill_icons.py`:

```python
from pathlib import Path

from toram_search.skill_icons import SkillIconCatalog, normalize_icon_key


def test_normalize_icon_key_ignores_case_space_and_punctuation() -> None:
    assert normalize_icon_key("Shield: Bash!") == "shieldbash"


def test_catalog_resolves_tree_local_icon(tmp_path: Path) -> None:
    root = tmp_path / "icons"
    folder = root / "Shield"
    folder.mkdir(parents=True)
    icon = folder / "Guardian.png"
    icon.write_bytes(b"png")

    catalog = SkillIconCatalog(root)

    assert catalog.resolve("Shield Skills", "Guardian") == icon.resolve()


def test_catalog_applies_existing_tree_folder_aliases(tmp_path: Path) -> None:
    root = tmp_path / "icons"
    folder = root / "MagicBlade"
    folder.mkdir(parents=True)
    icon = folder / "Magic Finale.png"
    icon.write_bytes(b"png")

    catalog = SkillIconCatalog(root)

    assert catalog.resolve("Magic Warrior Skills", "Magic Finale") == icon.resolve()


def test_catalog_uses_unique_global_fallback(tmp_path: Path) -> None:
    root = tmp_path / "icons"
    folder = root / "Other"
    folder.mkdir(parents=True)
    icon = folder / "Guardian.png"
    icon.write_bytes(b"png")

    catalog = SkillIconCatalog(root)

    assert catalog.resolve("Unknown Skills", "Guardian") == icon.resolve()


def test_catalog_refuses_ambiguous_global_fallback(tmp_path: Path) -> None:
    root = tmp_path / "icons"
    for folder_name in ("One", "Two"):
        folder = root / folder_name
        folder.mkdir(parents=True)
        (folder / "Duplicate.png").write_bytes(b"png")

    catalog = SkillIconCatalog(root)

    assert catalog.resolve("Missing Skills", "Duplicate") is None


def test_real_guardian_icon_is_checked_in() -> None:
    catalog = SkillIconCatalog(Path("coryn_skill_icons"))
    icon = catalog.resolve("Shield Skills", "Guardian")

    assert icon is not None
    assert icon.name == "Guardian.png"
    assert icon.is_file()
```

- [ ] **Step 3: Run the resolver tests and verify red state**

```bash
python -m pytest tests/test_skill_icons.py -q
```

Expected: FAIL because `toram_search.skill_icons` does not exist yet.

- [ ] **Step 4: Implement the resolver by adapting `filter_search/toram_discord/skill_icons.py`**

Create `toram_search/skill_icons.py`:

```python
from __future__ import annotations

from pathlib import Path
import unicodedata


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILL_ICON_ROOT = PROJECT_ROOT / "coryn_skill_icons"

TREE_FOLDER_ALIASES = {
    "magicwarrior": "magicblade",
    "blacksmith": "smith",
}


def normalize_icon_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value)).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _tree_folder_key(tree_name: str) -> str:
    key = normalize_icon_key(tree_name)
    if key.endswith("skills"):
        key = key[: -len("skills")]
    return TREE_FOLDER_ALIASES.get(key, key)


class SkillIconCatalog:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self._folder_index: dict[str, dict[str, tuple[Path, ...]]] | None = None
        self._global_index: dict[str, tuple[Path, ...]] | None = None

    def _ensure_index(self) -> None:
        if self._folder_index is not None and self._global_index is not None:
            return

        folder_lists: dict[str, dict[str, list[Path]]] = {}
        global_lists: dict[str, list[Path]] = {}

        if self.root.is_dir():
            for folder in sorted(self.root.iterdir(), key=lambda path: path.name.casefold()):
                if not folder.is_dir():
                    continue
                folder_key = normalize_icon_key(folder.name)
                local = folder_lists.setdefault(folder_key, {})
                for icon in sorted(folder.iterdir(), key=lambda path: path.name.casefold()):
                    if not icon.is_file() or icon.suffix.casefold() != ".png":
                        continue
                    skill_key = normalize_icon_key(icon.stem)
                    if not skill_key:
                        continue
                    local.setdefault(skill_key, []).append(icon)
                    global_lists.setdefault(skill_key, []).append(icon)

        self._folder_index = {
            folder_key: {skill_key: tuple(paths) for skill_key, paths in skill_map.items()}
            for folder_key, skill_map in folder_lists.items()
        }
        self._global_index = {
            skill_key: tuple(paths) for skill_key, paths in global_lists.items()
        }

    def resolve(self, tree_name: str, skill_name: str) -> Path | None:
        self._ensure_index()
        assert self._folder_index is not None
        assert self._global_index is not None

        skill_key = normalize_icon_key(skill_name)
        if not skill_key:
            return None

        folder_key = _tree_folder_key(tree_name)
        local_matches = self._folder_index.get(folder_key, {}).get(skill_key, ())
        if len(local_matches) == 1:
            return local_matches[0]
        if len(local_matches) > 1:
            return None

        global_matches = self._global_index.get(skill_key, ())
        if len(global_matches) == 1:
            return global_matches[0]
        return None


DEFAULT_SKILL_ICON_CATALOG = SkillIconCatalog(DEFAULT_SKILL_ICON_ROOT)
```

- [ ] **Step 5: Run the resolver tests**

```bash
python -m pytest tests/test_skill_icons.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit the assets and resolver**

```bash
git add coryn_skill_icons toram_search/skill_icons.py tests/test_skill_icons.py
git commit -m "feat: add individual skill icon catalog"
```

---

### Task 2: Make Top Examples and Result Corrections Fill-Only

**Files:**
- Modify: `main.py`
- Modify: `ui/results.py`
- Modify: `tests/test_ui_contract.py`
- Modify: `tests/test_app_shell.py`

**Interfaces:**
- Consumes: existing `SearchSubmission(query: str, nonce: int)` from `ui.search.render_search_box`; existing `suggested_queries` tuples.
- Produces: `_render_message(..., key_prefix: str) -> str | None`; `render_item_results(...) -> str | None`; `render_skill_results(...) -> str | None`.
- Invariant: only a new `SearchSubmission.nonce` may assign `query_to_run`.

- [ ] **Step 1: Add failing UI-contract tests**

Append to `tests/test_ui_contract.py`:

```python
def test_examples_render_before_search_box() -> None:
    source = text("main.py")
    assert source.index("examples=") < source.index("submission=render_search_box")


def test_examples_are_fill_only_not_query_submissions() -> None:
    source = text("main.py")
    assert "st.session_state.query=example_query" in source
    assert "query_to_run=example_query" not in source


def test_result_corrections_are_clickable_fill_values() -> None:
    source = text("ui/results.py")
    assert "key_prefix" in source
    assert "st.button" in source
    assert "-> str | None" in source
```

Append to `tests/test_app_shell.py` using the file's existing `AppTest.from_file(APP_PATH)` pattern:

```python
def test_example_button_fills_query_without_searching() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    target = next(button for button in app.button if button.label == "Guardian")
    target.click().run(timeout=10)

    assert app.session_state["query"] == "Guardian"
    assert app.session_state["last_outcome"] is None
```

- [ ] **Step 2: Run targeted tests and verify red state**

```bash
python -m pytest tests/test_ui_contract.py tests/test_app_shell.py -q
```

Expected: FAIL because examples currently execute searches below the component and result suggestions are passive text.

- [ ] **Step 3: Return correction clicks from `ui/results.py` instead of rendering passive text**

Implement:

```python
def _render_message(
    kind: str,
    message: str | None,
    suggestions: tuple[str, ...],
    *,
    key_prefix: str,
) -> str | None:
    if message:
        if kind == "refuse":
            st.warning(message)
        elif kind in {"not_found", "suggest", "clarify"}:
            st.info(message)
        else:
            st.write(message)

    if not suggestions:
        return None

    st.caption("Try:")
    columns = st.columns(min(len(suggestions), 4))
    for index, query in enumerate(suggestions):
        with columns[index % len(columns)]:
            if st.button(
                query,
                key=f"{key_prefix}_suggestion_{index}_{query}",
                use_container_width=True,
            ):
                return query.strip() or None
    return None
```

Change the two result functions to return that value after rendering cards. Use their current concrete parameter lists:

```python
def render_item_results(
    outcome: ItemSearchOutcome,
    *,
    database_path: Path,
    limit: int,
) -> str | None:
    fill_query = _render_message(
        outcome.kind,
        outcome.message,
        outcome.suggested_queries,
        key_prefix="item",
    )
    if outcome.results:
        st.markdown(f"### Items · {len(outcome.results)}")
        render_item_cards(outcome.results, database_path=database_path, limit=limit)
    return fill_query


def render_skill_results(
    outcome: SkillSearchOutcome,
    *,
    limit: int,
) -> str | None:
    fill_query = _render_message(
        outcome.kind,
        outcome.message,
        outcome.suggested_queries,
        key_prefix="skill",
    )
    if outcome.results:
        st.markdown(f"### Skills · {len(outcome.results)}")
        render_skill_cards(outcome.results, limit=limit)
    return fill_query
```

Do not call `search_database` from `ui/results.py`.

- [ ] **Step 4: Move examples above the component and make them fill-only**

In `main.py`, render the existing mode-specific example tuples before `render_search_box`:

```python
examples = {
    "Universal": ("critical rate", "Guardian", "Shield Skills", "stun skills"),
    "Items": ("cr bow", "hp >= 5000 armor", "-aggro xtal", "highest cr"),
    "Skills": ("Guardian", "Shield Skills", "skills that inflict stun", "lowest mp shield skills"),
}[mode]

st.caption("Suggested searches")
example_columns = st.columns(len(examples))
example_query = None
for column, example in zip(example_columns, examples):
    with column:
        if st.button(
            example,
            key=f"example_{mode}_{example}",
            use_container_width=True,
            disabled=not can_search,
        ):
            example_query = example

if example_query:
    st.session_state.query = example_query
```

Then call the existing custom component with `value=st.session_state.query`.

Keep query execution strictly nonce-backed:

```python
query_to_run = None
if submission is not None and submission.nonce != st.session_state.last_submission_nonce:
    st.session_state.last_submission_nonce = submission.nonce
    query_to_run = submission.query
```

Delete the current branch that assigns `example_query` to `query_to_run`.

- [ ] **Step 5: Feed correction clicks back into the search field without executing**

In `main.py`, capture fill values while rendering stored outcomes:

```python
fill_query = None

if outcome.items is not None:
    item_fill = render_item_results(
        outcome.items,
        database_path=ITEM_DATABASE,
        limit=st.session_state.item_limit,
    )
    fill_query = fill_query or item_fill
    # preserve the existing Show more items block

if outcome.skills is not None:
    skill_fill = render_skill_results(
        outcome.skills,
        limit=st.session_state.skill_limit,
    )
    fill_query = fill_query or skill_fill
    # preserve the existing Show more skills block

if fill_query:
    st.session_state.query = fill_query
    st.rerun()
```

Do not modify `last_submission_nonce`, `last_outcome`, or call `search_database` in the fill-only branch. The rerun is required because correction buttons render below the search component.

- [ ] **Step 6: Run focused fill-only regressions**

```bash
python -m pytest tests/test_ui_contract.py tests/test_app_shell.py tests/test_search_component.py -q
```

Expected: PASS, including the existing guarantees that autocomplete click/Tab acceptance does not submit.

- [ ] **Step 7: Commit the interaction change**

```bash
git add main.py ui/results.py tests/test_ui_contract.py tests/test_app_shell.py
git commit -m "feat: make search suggestions fill only"
```

---

### Task 3: Render Individual Skill Icons in Cards and Dialogs

**Files:**
- Modify: `ui/skill_cards.py`
- Modify: `ui/skill_dialog.py`
- Modify: `tests/test_ui_contract.py`

**Interfaces:**
- Consumes: `DEFAULT_SKILL_ICON_CATALOG.resolve(tree_name: str, skill_name: str) -> Path | None`.
- Produces: a small skill-card thumbnail and the same icon at a larger size in the detail dialog.

- [ ] **Step 1: Add failing shared-resolver UI tests**

Append to `tests/test_ui_contract.py`:

```python
def test_skill_card_and_dialog_use_shared_icon_catalog() -> None:
    card_source = text("ui/skill_cards.py")
    dialog_source = text("ui/skill_dialog.py")
    assert "DEFAULT_SKILL_ICON_CATALOG" in card_source
    assert "DEFAULT_SKILL_ICON_CATALOG" in dialog_source
    assert ".resolve(" in card_source
    assert ".resolve(" in dialog_source
    assert "st.image" in card_source
    assert "st.image" in dialog_source
```

- [ ] **Step 2: Run targeted tests and verify red state**

```bash
python -m pytest tests/test_ui_contract.py tests/test_skill_icons.py -q
```

Expected: FAIL because the current skill UI does not render icons.

- [ ] **Step 3: Render icons in skill cards**

Import in `ui/skill_cards.py`:

```python
from toram_search.skill_icons import DEFAULT_SKILL_ICON_CATALOG
```

Inside each existing bordered card, resolve once:

```python
icon_path = DEFAULT_SKILL_ICON_CATALOG.resolve(card.tree_name, skill.name)
```

Use the existing metadata/body logic inside a content container. When an icon exists:

```python
if icon_path is not None:
    icon_column, content_column = st.columns([1, 4], vertical_alignment="top")
    with icon_column:
        st.image(str(icon_path), width=64)
else:
    content_column = st.container()

with content_column:
    st.markdown(f"**{skill.name}**")
    # retain the existing tree/tier, MP/level/type, ailment, and View details rendering
```

Keep the outer two-card-per-row layout unchanged. If no icon resolves, render the same text-only card as today.

- [ ] **Step 4: Render the same icon in the skill detail dialog**

Import in `ui/skill_dialog.py`:

```python
from toram_search.skill_icons import DEFAULT_SKILL_ICON_CATALOG
```

At the top of `show_skill_dialog`:

```python
skill = card.skill
icon_path = DEFAULT_SKILL_ICON_CATALOG.resolve(card.tree_name, skill.name)

if icon_path is not None:
    icon_column, title_column = st.columns([1, 5], vertical_alignment="center")
    with icon_column:
        st.image(str(icon_path), width=96)
    with title_column:
        st.subheader(skill.name)
else:
    st.subheader(skill.name)
```

Keep all existing metadata, metrics, restrictions, descriptions, game description, and sections unchanged below the header.

- [ ] **Step 5: Run icon UI tests**

```bash
python -m pytest tests/test_skill_icons.py tests/test_ui_contract.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit skill icon rendering**

```bash
git add ui/skill_cards.py ui/skill_dialog.py tests/test_ui_contract.py
git commit -m "feat: show individual skill icons"
```

---

### Task 4: Full Regression and Integration Verification

**Files:**
- Verification only; modify code only when a failing check exposes a real defect.

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: a verified branch ready for integration.

- [ ] **Step 1: Run the complete test suite**

```bash
python -m pytest -q
```

Expected: all tests PASS, including real-database and custom-component tests.

- [ ] **Step 2: Compile application Python sources**

```bash
python -m compileall -q main.py toram_search ui
```

Expected: exit code 0.

- [ ] **Step 3: Run runtime-boundary scans**

```bash
! grep -R -n -E 'ollama|qwen|gemma|discord|embedding|semantic_search' main.py toram_search ui
! grep -R -n -E '\b(INSERT|UPDATE|DELETE|REPLACE)\b' toram_search --include='*.py'
```

Expected: both commands exit 0.

- [ ] **Step 4: Verify a real copied icon through production resolution**

```bash
python - <<'PY'
from toram_search.skill_icons import DEFAULT_SKILL_ICON_CATALOG

path = DEFAULT_SKILL_ICON_CATALOG.resolve("Shield Skills", "Guardian")
print(path)
assert path is not None
assert path.name == "Guardian.png"
assert path.is_file()
PY
```

Expected: prints the local Guardian PNG and exits 0.

- [ ] **Step 5: Review final scope**

```bash
git diff --stat main...HEAD
git diff --name-only main...HEAD
```

Expected: approved spec/plan, copied `coryn_skill_icons/`, shared resolver/tests, `main.py`, `ui/results.py`, `ui/skill_cards.py`, `ui/skill_dialog.py`, and relevant tests only. No SQLite schema changes and no `filter_search` modifications.

- [ ] **Step 6: Push the implementation branch and inspect GitHub Actions**

Confirm the repository `Tests` workflow completes successfully on Python 3.12 with `python -m pytest -q` and `compileall` both successful.

- [ ] **Step 7: Commit only genuine verification fixes if required**

If verification exposed a real test-harness issue, fix it, rerun the affected test plus the full suite, and commit the exact changed files. If no fix was required, do not create an empty commit.

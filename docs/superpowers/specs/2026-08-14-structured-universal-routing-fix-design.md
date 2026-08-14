# Structured Universal Routing Fix Design

## Problem

In Universal mode, queries such as `aggro xtal wp` currently produce irrelevant results in both domains:

- the item parser recognizes only one item-type phrase, so `xtal` can be consumed while `wp` remains; the remaining text then falls through to fuzzy item-name search and can return unrelated items such as a Dagger;
- the skill parser always runs in Universal mode and can fall through to fuzzy-name or FTS lexical search even when the query is clearly item-oriented, producing unrelated skills.

The fix must remain deterministic and must not add an LLM.

## Desired behavior

`aggro xtal wp` should be interpreted as:

- stat: `Aggro %`
- item filter: `Weapon Crysta`

Equivalent word orders such as `aggro wp xtal` and `aggro weapon xtal` should resolve to the same item intent.

When Universal mode has a confident item interpretation, weak skill fallback must not create an unrelated Skills section. Exact or clearly structured skill matches may still be returned when they genuinely match the query.

## Item filter parsing

### Order-insensitive crysta-slot aliases

The item filter parser will support equivalent crysta-slot phrases regardless of whether the slot or crysta token appears first. At minimum:

- `weapon xtal`, `wp xtal`, `xtal weapon`, `xtal wp` -> Weapon Crysta
- `armor xtal`, `arm xtal`, `xtal armor`, `xtal arm` -> Armor Crysta
- `additional xtal`, `add xtal`, `xtal additional`, `xtal add` -> Additional Crysta
- `ring xtal`, `special xtal`, `xtal ring`, `xtal special` -> Special Crysta

Existing canonical phrases continue to work.

Specific crysta-slot phrases must win over generic `xtal` and generic weapon aliases. Therefore `xtal wp` must be consumed as one Weapon Crysta filter rather than as generic All Crysta plus an unused `wp` token.

### Structured-intent fallback rule

Once the item parser has recognized structured intent, such as:

- a known stat or stat alias;
- an item-type/crysta filter;
- a numeric comparison;
- a ranking operator;

it must not silently fall back to fuzzy item-name search when leftover tokens cannot be safely interpreted.

Instead it returns `suggest` or `not_found` with a deterministic correction. This prevents structured queries from degrading into unrelated name matches.

Exact item-name matching still occurs before structured parsing, so legitimate item names are unaffected.

## Universal routing

Universal mode continues to call both domain services, but skill search will receive a strictness policy based on the item outcome.

### Confident item outcomes

The item side is considered confident when it produces one of these intent-bearing outcomes:

- exact/structured item results;
- stat-filter results;
- clarification for an ambiguous stat;
- a deterministic suggestion caused by recognized item syntax;
- item help/meta/refusal responses.

A plain fuzzy item-name result alone does not establish strong item intent.

### Skill fallback policy

When the item side is confident, the skill service may use only strong matching routes:

- exact skill name or alias;
- explicit skill tree query;
- explicit structured skill filters such as MP, tier, required level, ailment, or compare;
- exact stored skill phrase handling already used by the structured router.

Weak fallback is disabled in this situation:

- fuzzy skill-name matching;
- FTS lexical search over descriptions/raw text.

If no strong skill match exists, the skill outcome becomes `not_found` with no results. The UI therefore shows no irrelevant Skills cards.

When the item side is not confident, Universal mode preserves the normal skill behavior, including fuzzy and lexical fallback.

Skills-only mode is unchanged and continues to use the full skill search behavior.

## Example outcomes

### `aggro xtal wp`

Item interpretation: `Aggro %` + `Weapon Crysta`.

Expected UI:

- matching Weapon Crysta items with Aggro %;
- no unrelated Skills section.

### `aggro wp xtal`

Same interpretation and result as `aggro xtal wp`.

### `cr bow`

Item interpretation remains Critical Rate + Bow.

Universal mode must not append unrelated lexical skill matches unless a strong skill match independently exists.

### `Guardian`

The skill exact match remains visible in Universal mode. The item side may independently return a legitimate exact/fuzzy item result if one exists; this fix does not suppress strong cross-domain matches.

### `skills that inflict stun`

The skill structured ailment route remains unchanged.

## Code boundaries

Expected focused changes:

- `toram_search/items/filters.py` for order-insensitive specific crysta-slot aliases and precedence;
- `toram_search/items/service.py` for preventing fuzzy item-name fallback after recognized structured intent;
- `toram_search/skills/service.py` for an explicit `allow_weak_fallback` (or equivalent) search policy;
- `toram_search/router.py` for deriving Universal-mode skill strictness from the item outcome;
- tests in `tests/test_item_search.py`, `tests/test_skill_search.py`, and/or `tests/test_universal.py`.

No database schema changes are required.

## Testing

Regression coverage must include the exact production bug using the real or representative databases:

1. `aggro xtal wp` resolves the item filter to Weapon Crysta and returns no unrelated skill results in Universal mode.
2. `aggro wp xtal` behaves identically.
3. Specific crysta-slot aliases beat generic `xtal` and `wp` aliases.
4. A recognized structured item query with an unknown leftover token does not fall through to fuzzy item-name matching.
5. When item intent is confident, weak skill fuzzy/FTS matches are suppressed.
6. Exact skill matches still work under strict Universal routing.
7. Skills-only mode retains fuzzy/FTS fallback behavior.
8. Existing item, skill, Universal, autocomplete, UI, database, and compile tests remain green.

## Non-goals

This bugfix does not add:

- query interpretation chips;
- compare-mode UI;
- new result filters;
- subjective build recommendations;
- LLM or semantic search;
- database schema changes;
- unrelated performance refactors.

# Toram Database Search

Deterministic Streamlit search for Toram Online Items, Skills, Food codes, and Registlets. The public app does not use an LLM, RAG, embeddings, semantic search, or an external search service.

## Search modes

The app provides five modes:

- `Universal`
- `Items`
- `Skills`
- `Food`
- `Registlets`

### Food codes

Food search is explicit. Start the query with `food` or `code`, followed by a supported Food stat or alias.

Examples:

```text
food maxmp
code ampr
food dt fire
food -aggro
```

Food code values are returned as results; raw numeric code values themselves are not searchable. Bare `maxmp` and `maxmp food` do not invoke Food search.

Food data is read from:

- `food_entries.csv`
- `food_stat_aliases.json`

### Registlets

Registlets can be searched by Stoodie source level, Registlet name, or stored effect text.

Examples:

```text
std 220
Arrow Rain Enhancer
restores mp
```

Stoodie aliases such as `stoodie lvl 220` are supported. Effect search is deterministic phrase/word matching over the stored `effect` field; it is not semantic or AI search. Fuzzy matching is limited to Registlet names.

Registlet data is read from `registlets.json`.

## Run locally

    python -m pip install -r requirements-dev.txt
    streamlit run main.py

## Data update workflow

The Item and Skill SQLite databases are maintained in `KarenYuusha/filter_search`. Replace the Streamlit copies with:

    cp ../filter_search/coryn_data/database/items.sqlite ./items.sqlite
    cp ../filter_search/coryn_data/database/skills.sqlite ./skills.sqlite

Food and Registlet data is maintained directly in this repository through the CSV/JSON source files listed above.

After any data update, run:

    pytest -q
    python -m compileall -q main.py toram_search ui

The Streamlit app reads the SQLite databases and text data sources only; it never edits or rebuilds them at runtime.

## Deployment

Streamlit Community Cloud entry point: `main.py`.

Public deployment: https://toram-item-search.streamlit.app/

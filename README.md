# Toram Database Search

Deterministic Streamlit search for Toram Online items and skills. The public app does not use an LLM, RAG, embeddings, or an external search service.

## Run locally

    python -m pip install -r requirements-dev.txt
    streamlit run main.py

## Database update workflow

The canonical databases are maintained in `KarenYuusha/filter_search`. Replace the Streamlit copies with:

    cp ../filter_search/coryn_data/database/items.sqlite ./items.sqlite
    cp ../filter_search/coryn_data/database/skills.sqlite ./skills.sqlite

Then run:

    pytest -q
    git add items.sqlite skills.sqlite
    git commit -m "data: update Toram databases"
    git push

The Streamlit app reads these files only; it never edits or rebuilds them.

## Deployment

Streamlit Community Cloud entry point: `main.py`.

Public deployment: https://toram-item-search.streamlit.app/

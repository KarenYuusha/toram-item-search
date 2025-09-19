import pandas as pd
import streamlit as st
from rapidfuzz import fuzz, process
import ast
import os
import base64
import re
import streamlit as st

# Placeholder image (optional)
PLACEHOLDER = "placeholder.jpg"

# Load dataset
df = pd.read_csv("coryn_items.csv")

# Convert string back to list if necessary
if isinstance(df['image_paths'].iloc[0], str):
    df['image_paths'] = df['image_paths'].apply(ast.literal_eval)

# --- Weapon/app types ---
app_types = {
    'armor': 8,
    'additional': 6,
    'shield': 17,
    '1 handed sword': 4,
    '2 handed sword': 5,
    'bow': 9,
    'bowgun': 10,
    'knuckles': 13,
    'magic device': 15,
    'staff': 19,
    'halberd': 26,
    'katana': 27
}

# --- Helpers ---


def get_all_stats(df, min_occurrence=2):
    """
    Return a list of distinct stats that appear in at least `min_occurrence` items.
    """
    stat_counts = {}

    for s in df['stats'].dropna():
        parts = s.split(";")
        for part in parts:
            name_match = re.match(r"\s*([^\:]+)\s*:", part)
            if name_match:
                stat_name = name_match.group(1).strip()
                stat_counts[stat_name] = stat_counts.get(stat_name, 0) + 1

    # Keep only stats with enough occurrences
    filtered_stats = [stat for stat,
                      count in stat_counts.items() if count >= min_occurrence]
    return filtered_stats


def image_to_base64(path):
    with open(path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()


def extract_stat_value(stats_str, query):
    """
    Extract numeric value of a stat from the stats string.
    Handles spaces, %, and negative numbers like 'ASPD: -300'.
    """
    if not isinstance(stats_str, str):
        return None

    stats_normalized = re.sub(r"\s+", "", stats_str.lower())
    query_normalized = query.lower().replace(" ", "")
    pattern = re.compile(rf"{re.escape(query_normalized)}[:]\s*(-?[\d\.]+)")
    match = pattern.search(stats_normalized)
    if match:
        return float(match.group(1))
    return None


def search_by_stat(df, stat_query, k=5, ascending=False):
    """
    Search top-k items by stat.
    """
    df = df.copy()
    df['stat_value'] = df['stats'].apply(
        lambda x: extract_stat_value(x, stat_query))
    filtered = df[df['stat_value'].notna()]
    sorted_df = filtered.sort_values(by='stat_value', ascending=ascending)

    # Return all columns needed for UI
    return sorted_df.head(k)


def fuzzy_search_items(query, k=5, score_cutoff=50):
    if not query:
        return pd.DataFrame()
    choices = df['name'].tolist()
    scores = process.cdist([query], choices, scorer=fuzz.WRatio)[0]
    results = df.copy()
    results['match_score'] = scores
    results = results[results['match_score'] >= score_cutoff]
    results = results.sort_values(by='match_score', ascending=False).head(k)
    return results


def search_items(query, k=5):
    query = query.strip()

    # Check if query starts with "stat:" → search by stats
    if query.lower().startswith("stat:"):
        # Remove prefix
        stat_query = query[len("stat:"):].strip()
        return search_by_stat(df, stat_query, k=k, ascending=False)

    # Otherwise, do the old item name search
    query_lower = query.lower()

    # Case 1: "all {weapon_type}"
    if query_lower.startswith("all"):
        parts = query_lower.split(maxsplit=1)
        if len(parts) == 1:
            return df.copy()
        weapon_type_query = parts[1].strip()
        best_match = process.extractOne(
            weapon_type_query,
            list(app_types.keys()),
            scorer=fuzz.WRatio
        )
        if best_match and best_match[1] >= 60:
            weapon_type = best_match[0]
            return df[df["type"].str.lower().str.strip() == weapon_type].copy()
        else:
            return pd.DataFrame()

    # Case 2: fuzzy search by name
    return fuzzy_search_items(query, k=k)


# --- Streamlit UI ---
st.set_page_config(page_title="Item Search", layout="wide")

# --- Example usage in Streamlit ---
all_stats = get_all_stats(df)

with st.expander("📋 Show All Available Stats (click to expand)"):
    st.text_area(
        label="Copy a stat to use for searching (e.g., ASPD, MaxHP %, EXP Gain):",
        value="\n".join(all_stats),
        height=200
    )

# Create an anchor at the very top
st.markdown("<a name='top'></a>", unsafe_allow_html=True)

st.title("🔎 Item Search Engine")

# --- Session state init ---
if "last_query" not in st.session_state:
    st.session_state.last_query = ""
if "last_k" not in st.session_state:
    st.session_state.last_k = None
if "page" not in st.session_state:
    st.session_state.page = 1

query = st.text_input(
    "Search for an item by name (or type 'all <type>' or 'stat:<stat_name>'):", "")

with st.expander("⚙️ Settings"):
    k = st.slider("Number of results (k, fuzzy only):", 1, 100, 20)

if query:
    results = search_items(query, k=k)

    if results.empty:
        st.warning("No matches found.")
    else:
        # ✅ Reset page if query OR k value changed
        if query != st.session_state.last_query or k != st.session_state.last_k:
            st.session_state.page = 1
        st.session_state.last_query = query
        st.session_state.last_k = k

        # --- Pagination logic ---
        items_per_page = 20
        total_items = len(results)
        total_pages = (total_items - 1) // items_per_page + 1

        page = st.session_state.page

        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("⬅️ Prev") and page > 1:
                st.session_state.page -= 1
        with col3:
            if st.button("Next ➡️") and page < total_pages:
                st.session_state.page += 1

        st.markdown(f"**Page {st.session_state.page} / {total_pages}**")

        # Slice results for this page
        start = (st.session_state.page - 1) * items_per_page
        end = start + items_per_page
        page_results = results.iloc[start:end]

        for _, row in page_results.iterrows():
            with st.container():
                st.subheader(f"{row['name']} ({row['type']})")

                # For fuzzy matches, show score
                if "match_score" in row:
                    st.caption(f"Match score: {row['match_score']:.1f}")

                # Ensure image_paths is always a list
                raw_paths = row.get("image_paths", [])
                if not isinstance(raw_paths, list):
                    raw_paths = []

                # Build valid OS paths with .png
                paths = [os.path.join(*p.split("/")) +
                         ".png" for p in raw_paths]

                # Hover info
                hover_info = f"""
                Name: {row['name']}
                ID: {row['id']}
                Sell: {row['sell'] if pd.notna(row['sell']) else 'N/A'}
                Process: {row['process'] if pd.notna(row['process']) else 'N/A'}
                Stats: {row['stats'] if pd.notna(row['stats']) else 'N/A'}
                Monsters: {row['obtained_monster'] if pd.notna(row['obtained_monster']) else 'N/A'}
                Maps: {row['obtained_map'] if pd.notna(row['obtained_map']) else 'N/A'}
                """.strip()
                hover_info_html = hover_info.replace('"', '&quot;')

                if paths:  # ✅ item has at least one image
                    n_cols = min(4, max(1, len(paths)))
                    cols = st.columns(n_cols)

                    for i, path in enumerate(paths):
                        col = cols[i % n_cols]

                        if os.path.exists(path):
                            img_b64 = image_to_base64(path)
                            col.markdown(
                                f"""
                                <div title="{hover_info_html}">
                                    <img src="data:image/png;base64,{img_b64}" width="150"><br>
                                    <small>{os.path.basename(path)}</small>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                        else:
                            if os.path.exists(PLACEHOLDER):
                                img_b64 = image_to_base64(PLACEHOLDER)
                                col.markdown(
                                    f"""
                                    <div title="{hover_info_html}">
                                        <img src="data:image/png;base64,{img_b64}" width="150"><br>
                                        <small>Missing: {os.path.basename(path)}</small>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                            else:
                                col.error(f"Missing: {path}")
                else:  # ✅ no images at all
                    if os.path.exists(PLACEHOLDER):
                        img_b64 = image_to_base64(PLACEHOLDER)
                        st.markdown(
                            f"""
                            <div title="{hover_info_html}">
                                <img src="data:image/png;base64,{img_b64}" width="150"><br>
                                <small>No image available</small>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    else:
                        st.info(f"No images available for **{row['name']}**")

# --- Floating Back to Top Button ---
st.markdown(
    """
    <style>
    .back-to-top {
        position: fixed;
        bottom: 20px;
        right: 20px;
        width: 48px;
        height: 48px;
        background-color: var(--primary-color);
        color: white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        text-decoration: none;
        box-shadow: 0 2px 6px rgba(0,0,0,0.3);
        transition: background-color 0.2s ease, transform 0.2s ease;
        z-index: 1000;
    }
    .back-to-top:hover {
        filter: brightness(1.1);
        transform: translateY(-2px);
    }
    </style>

    <a href="#top" class="back-to-top">↑</a>
    """,
    unsafe_allow_html=True,
)

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


def go_prev(): st.session_state.page = max(1, st.session_state.page - 1)
def go_next(): st.session_state.page = min(total_pages, st.session_state.page + 1)
def go_page(p): st.session_state.page = p

# --- Compute pages to show ---
def get_page_range(current, total, max_visible=7):
    if total <= max_visible:
        return list(range(1, total + 1))
    pages = [1]
    left = max(2, current - 2)
    right = min(total - 1, current + 2)
    if left > 2:
        pages.append("...")
    pages.extend(range(left, right + 1))
    if right < total - 1:
        pages.append("...")
    pages.append(total)
    return pages

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
for key, default in {"last_query": "", "last_k": None, "page": 1}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# --- Inputs ---
query = st.text_input("Search for an item by name (or type 'all <type>' or 'stat:<stat_name>'):", "")

with st.expander("⚙️ Settings"):
    k = st.slider("Number of results (k, fuzzy only):", 1, 100, 20)

def render_image(path, hover_info, placeholder=PLACEHOLDER):
    """Render image with hover info; fallback to placeholder if missing."""
    if not os.path.exists(path):
        path = placeholder if os.path.exists(placeholder) else None
        label = "No image available"
    else:
        label = os.path.splitext(os.path.basename(path))[0]
        label = label.replace('_', ' ')

    if path:
        img_b64 = image_to_base64(path)
        return f"""
        <div title="{hover_info}">
            <img src="data:image/png;base64,{img_b64}" width="150"><br>
            <small>{label}</small>
        </div>
        """
    return None

if query:
    results = search_items(query, k=k)

    if results.empty:
        st.warning("No matches found.")
    else:
        # Reset page if query or k changes
        if query != st.session_state.last_query or k != st.session_state.last_k:
            st.session_state.page = 1
        st.session_state.last_query = query
        st.session_state.last_k = k

        # --- Pagination ---
        items_per_page = 20
        total_pages = (len(results) - 1) // items_per_page + 1
        if "page" not in st.session_state:
            st.session_state.page = 1

        pages_to_show = get_page_range(st.session_state.page, total_pages, max_visible=7)
        num_buttons = len(pages_to_show)

        # --- Layout ---
        prev_col, pages_col, next_col = st.columns([1, 6, 1])  # Prev + pages + Next

        # Prev button
        with prev_col:
            st.button("⬅️ Prev", on_click=go_prev)

        # Page buttons (centered)
        with pages_col:
            btn_cols = st.columns(len(pages_to_show))
            for i, p in enumerate(pages_to_show):
                with btn_cols[i]:
                    if p == "...":
                        st.markdown(
                            "<div style='color: gray; width: 40px; height: 40px; text-align:center; line-height:40px;'>...</div>",
                            unsafe_allow_html=True,
                        )
                    elif p == st.session_state.page:
                        # Current page
                        st.markdown(f"""
                        <div style="
                            background-color: #e2c4e7; 
                            color: white; 
                            width: 40px; 
                            height: 40px; 
                            display:flex;
                            align-items:center;
                            justify-content:center;
                            border-radius: 5px; 
                            font-weight: bold;
                            margin:auto;
                        ">{p}</div>
                        """, unsafe_allow_html=True)
                    else:
                        # Normal page button
                        if st.button(str(p), key=f"page_{p}", on_click=go_page, args=(p,)):
                            pass

        # Next button
        with next_col:
            st.button("Next ➡️", on_click=go_next)


        st.markdown(f"**Page {st.session_state.page} / {total_pages}**")

        # Slice results for current page
        start = (st.session_state.page - 1) * items_per_page
        page_results = results.iloc[start:start + items_per_page]

        for _, row in page_results.iterrows():

            # ----------------------------
            # Images first (always visible)
            # ----------------------------
            raw_paths = row.get("image_paths", [])
            if not isinstance(raw_paths, list):
                raw_paths = []

            # Convert paths to local app paths
            paths = [os.path.join(*p.split("/")) + ".png" for p in raw_paths]

            # Fallback to placeholder if no images
            if not paths:
                paths = [PLACEHOLDER] if os.path.exists(PLACEHOLDER) else []

            n_cols = min(4, max(1, len(paths)))
            cols = st.columns(n_cols)

            for i, path in enumerate(paths):
                col = cols[i % n_cols]

                if not os.path.exists(path):
                    path = PLACEHOLDER if os.path.exists(PLACEHOLDER) else None

                if path:
                    # Display image with hover info (tooltip)
                    col.image(
                        path,
                        width=150,
                        caption=row['name'],
                        use_column_width=False
                    )
                    # Optional: tooltip workaround using markdown
                    hover_html = f'<div title="{row["name"]}"></div>'
                    col.markdown(hover_html, unsafe_allow_html=True)

            # ----------------------------
            # Info in expander (click to see)
            # ----------------------------
            with st.expander(f"Details for {row['name']}"):
                st.write(f"Type: {row['type']}")
                st.write(f"ID: {row['id']}")
                st.write(f"Sell: {row.get('sell', 'N/A')}")
                st.write(f"Process: {row.get('process', 'N/A')}")
                st.write(f"Stats: {row.get('stats', 'N/A')}")
                st.write(f"Monsters: {row.get('obtained_monster', 'N/A')}")
                st.write(f"Maps: {row.get('obtained_map', 'N/A')}")

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

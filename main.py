import pandas as pd
from module.search_engine import search_engine
from module.normalizer import standard_prep
import streamlit as st
import ast
import time
import os
import base64
import re
import html as html_lib

PLACEHOLDER = "placeholder.jpg"

df = pd.read_csv('coryn_items.csv')

df['image_paths'] = df['image_paths'].apply(ast.literal_eval)
df['name_clean'] = df['name'].apply(standard_prep)

if isinstance(df['image_paths'].iloc[0], str):
    df['image_paths'] = df['image_paths'].apply(ast.literal_eval)

# --- Weapon/app types ---
wp_types_list = [
    'armor',
    'additional',
    'shield',
    '1 handed sword',
    '2 handed sword',
    'bow',
    'bowgun',
    'knuckles',
    'magic device',
    'staff',
    'halberd',
    'katana'
]


def get_all_stats(df, min_occurrence=6):
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

    # Keep only stats with enough occurrences and sort alphabetically
    filtered_stats = sorted(
        [stat for stat, count in stat_counts.items() if count >= min_occurrence]
    )

    return filtered_stats


def image_to_base64(path):
    with open(path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()


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

# pagination stuff


def go_prev(): st.session_state.page = max(1, st.session_state.page - 1)
def go_next(): st.session_state.page = min(
    total_pages, st.session_state.page + 1)


def go_page(p): st.session_state.page = p


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


# anchor
st.markdown("<a name='top'></a>", unsafe_allow_html=True)

# UI
st.set_page_config(page_title="Item Search", layout="wide")

all_stats = get_all_stats(df)

with st.expander("📋 Show All Available Stats (click to expand)"):
    search_component = """
    <style>
        #searchBox {{
            width: 100%;
            padding: 10px;
            border-radius: 8px;
            border: 1px solid #ccc;
            font-size: 16px;
            font-family: Arial, sans-serif;
        }}
        #statsList {{
            list-style: none;
            padding-left: 0;
            margin-top: 10px;
            max-height: 250px;
            overflow-y: scroll;
        }}
        #statsList li {{
            padding: 6px 0;
            font-size: 15px;
            font-family: Arial, sans-serif;
        }}
        /* Light mode */
        @media (prefers-color-scheme: light) {{
            #statsList li {{
                color: #222;
            }}
        }}
        /* Dark mode */
        @media (prefers-color-scheme: dark) {{
            #statsList li {{
                color: #eee;
            }}
        }}
        /* Hide scrollbar */
        #statsList::-webkit-scrollbar {{
            display: none;
        }}
        #statsList {{
            -ms-overflow-style: none;
            scrollbar-width: none;
        }}
    </style>

    <input type="text" id="searchBox" placeholder="Type to search stats...">

    <ul id="statsList">
    {items}
    </ul>

    <script>
    const searchBox = document.getElementById("searchBox");
    const statsList = document.getElementById("statsList").getElementsByTagName("li");

    searchBox.addEventListener("keyup", function() {{
        const filter = searchBox.value.toLowerCase();
        for (let i = 0; i < statsList.length; i++) {{
            let txt = statsList[i].textContent || statsList[i].innerText;
            statsList[i].style.display = txt.toLowerCase().includes(filter) ? "" : "none";
        }}
    }});
    </script>
    """

    items_html = "".join([f"<li>{stat}</li>" for stat in all_stats])

    st.components.v1.html(
        search_component.format(items=items_html),
        height=250,  # adjust depending on desired visible area
        scrolling=False
    )

st.title("🔎 Item Search Engine")

# session init
for key, default in {"last_query": "", "last_k": None, "page": 1}.items():
    if key not in st.session_state:
        st.session_state[key] = default

query = st.text_input(
    "Search for an item by name (or type 'all <type>' or 'stat:<stat_name>'):", "")

with st.expander("⚙️ Settings"):
    k = st.slider("Number of results (k, fuzzy only):", 1, 200, 20)


if query:
    results = search_engine(query, df, k=k)

    if results.empty:
        st.warning("No matches found.")
    else:
        # Reset page if query or k changes
        if query != st.session_state.last_query or k != st.session_state.last_k:
            st.session_state.page = 1
        st.session_state.last_query = query
        st.session_state.last_k = k

        # Pagination
        items_per_page = 20
        total_pages = (len(results) - 1) // items_per_page + 1
        if "page" not in st.session_state:
            st.session_state.page = 1

        pages_to_show = get_page_range(
            st.session_state.page, total_pages, max_visible=7)
        num_buttons = len(pages_to_show)

        prev_col, pages_col, next_col = st.columns(
            [1, 6, 1])  # Prev + pages + Next

        with prev_col:
            st.button("⬅️ Prev", on_click=go_prev)

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

        with next_col:
            st.button("Next ➡️", on_click=go_next)

        st.markdown(f"**Page {st.session_state.page} / {total_pages}**")

        # Slice results for current page
        start = (st.session_state.page - 1) * items_per_page
        page_results = results.iloc[start:start + items_per_page]

        for _, row in page_results.iterrows():
            raw_paths = row.get("image_paths", [])
            if not isinstance(raw_paths, list):
                raw_paths = []

            # Convert paths to local app paths
            paths = [p + ".png" for p in raw_paths]

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
                    # Convert image to base64
                    img_b64 = image_to_base64(path)

                    # Build hover text with full details (like expander)
                    hover_lines = [
                        f"Name: {row['name']}",
                        f"Type: {row['type']}",
                        f"ID: {row['id']}",
                        f"Sell: {row.get('sell', 'N/A')}",
                        f"Process: {row.get('process', 'N/A')}",
                        f"Stats: {row.get('stats', 'N/A')}",
                        f"Monsters: {row.get('obtained_monster', 'N/A')}",
                        f"Maps: {row.get('obtained_map', 'N/A')}"
                    ]
                    hover_text = html_lib.escape("\n".join(hover_lines))

                    # Render HTML with tooltip
                    html = f"""
                    <div style="text-align:center; margin-bottom:5px;" title="{hover_text}">
                        <img src="data:image/png;base64,{img_b64}" width="150" style="max-width:100%;"><br>
                        <small>{row['name']}</small>
                    </div>
                    """
                    col.markdown(html, unsafe_allow_html=True)

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

# back to top
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

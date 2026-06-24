import pandas as pd
from module.search_engine import GEAR_TYPES, search_engine
from module.normalizer import standard_prep
import streamlit as st
import streamlit.components.v1 as components
import ast
import os
import base64
import re
import html as html_lib

PLACEHOLDER = "placeholder.jpg"
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, 'coryn_items.csv')
PLACEHOLDER_PATH = os.path.join(BASE_DIR, PLACEHOLDER)
AUTOCOMPLETE_COMPONENT_PATH = os.path.join(BASE_DIR, "components", "autocomplete_search")

# UI
st.set_page_config(page_title="Item Search", layout="wide")
autocomplete_search = components.declare_component(
    "autocomplete_search",
    path=AUTOCOMPLETE_COMPONENT_PATH,
)


@st.cache_data
def load_items():
    items = pd.read_csv(DATA_PATH)
    items['image_paths'] = items['image_paths'].apply(ast.literal_eval)
    items['name_clean'] = items['name'].apply(standard_prep)
    return items


df = load_items()


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


def get_autocomplete_suggestions(df, all_stats):
    item_suggestions = df['name'].dropna().astype(str).tolist()
    stat_suggestions = [f"stat: {stat}" for stat in all_stats]
    type_suggestions = [f"all {item_type}" for item_type in GEAR_TYPES]
    aliases = [
        "all ring",
        "all rings",
        "all special",
        "stat: cr",
        "stat: cd",
        "stat: aggro%",
        "stat: atk%",
        "stat: matk%",
        "stat: physical pierce",
        "stat: magical pierce",
    ]

    return list(dict.fromkeys([*type_suggestions, *aliases, *stat_suggestions, *item_suggestions]))


@st.cache_data
def image_to_base64(path):
    with open(path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

# pagination stuff


def go_prev(): st.session_state.page = max(1, st.session_state.page - 1)
def go_next(total_pages): st.session_state.page = min(
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


all_stats = get_all_stats(df)
autocomplete_suggestions = get_autocomplete_suggestions(df, all_stats)

# anchor
st.markdown("<a name='top'></a>", unsafe_allow_html=True)

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

    items_html = "".join([f"<li>{html_lib.escape(stat)}</li>" for stat in all_stats])

    components.html(
        search_component.format(items=items_html),
        height=250,  # adjust depending on desired visible area
        scrolling=False
    )

st.title("🔎 Item Search Engine")

# session init
for key, default in {"query": "", "last_query": "", "last_k": None, "last_type_filters": [], "page": 1}.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.caption("Search by item name, or use commands like `all armor` / `stat: critical rate`. Press `Tab` to accept the best autocomplete preview.")
use_tab_autocomplete = st.toggle("Use experimental Tab autocomplete", value=False)
if use_tab_autocomplete:
    query_value = autocomplete_search(
        value=st.session_state.query,
        suggestions=autocomplete_suggestions,
        placeholder="Search items, stats, or types...",
        key="query_autocomplete",
        default=st.session_state.query,
    )
    if query_value is not None:
        st.session_state.query = query_value
else:
    st.session_state.query = st.text_input(
        "Search",
        value=st.session_state.query,
        placeholder="Search items, stats, or types...",
    )
query = st.session_state.query

with st.expander("⚙️ Settings"):
    k = st.slider("Number of results (k, fuzzy only):", 1, 200, 20)
    type_filter_options = [item_type.title() for item_type in GEAR_TYPES]
    selected_type_filters = st.multiselect(
        "Filter by item type:",
        type_filter_options,
        help="Works with name search, stat search, and all searches. Use Special for rings.",
    )
    ascending = st.toggle(
        "Sort stat searches lowest first",
        value=False,
        help="By default stat searches show the highest stat values first.",
    )


if query:
    type_filters = [item_type.lower() for item_type in selected_type_filters]
    results = search_engine(query, df, k=k, ascending=ascending, type_filters=type_filters)

    if results.empty:
        st.warning("No matches found.")
    else:
        # Reset page if query or k changes
        if (
            query != st.session_state.last_query
            or k != st.session_state.last_k
            or type_filters != st.session_state.last_type_filters
        ):
            st.session_state.page = 1
        st.session_state.last_query = query
        st.session_state.last_k = k
        st.session_state.last_type_filters = type_filters

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
            st.button("Next ➡️", on_click=go_next, args=(total_pages,))

        st.markdown(f"**Page {st.session_state.page} / {total_pages}**")

        # Slice results for current page
        start = (st.session_state.page - 1) * items_per_page
        page_results = results.iloc[start:start + items_per_page]

        for _, row in page_results.iterrows():
            with st.container():
                st.subheader(f"{row['name']} ({row['type']})")

                raw_paths = row.get("image_paths", [])
                if not isinstance(raw_paths, list):
                    raw_paths = []

                # Convert DataFrame paths to valid relative OS paths with .png
                paths = [os.path.join(*p.split("/")) +
                         ".png" for p in raw_paths]

                # Hover info
                hover_info = f"""
                Name: {row['name']}
                Sell: {row['sell'] if pd.notna(row['sell']) else 'N/A'}
                Process: {row['process'] if pd.notna(row['process']) else 'N/A'}
                Stats: {row['stats'] if pd.notna(row['stats']) else 'N/A'}
                Monsters: {row['obtained_monster'] if pd.notna(row['obtained_monster']) else 'N/A'}
                Maps: {row['obtained_map'] if pd.notna(row['obtained_map']) else 'N/A'}
                """.strip()
                hover_info_html = html_lib.escape(hover_info, quote=True)

                if paths:
                    n_cols = min(4, max(1, len(paths)))
                    cols = st.columns(n_cols)

                    for i, path in enumerate(paths):
                        path = os.path.join(BASE_DIR, path.lower())
                        col = cols[i % n_cols]

                        if os.path.exists(path):
                            img_b64 = image_to_base64(path)
                            name_html = html_lib.escape(row['name'])
                            col.markdown(
                                f"""
                                <div title="{hover_info_html}" style="text-align:center; margin-bottom:5px;">
                                    <img src="data:image/png;base64,{img_b64}" width="150" style="max-width:100%;"><br>
                                    <small>{name_html}</small>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                        else:
                            if os.path.exists(PLACEHOLDER_PATH):
                                img_b64 = image_to_base64(PLACEHOLDER_PATH)
                                missing_html = html_lib.escape(os.path.relpath(path, BASE_DIR))
                                col.markdown(
                                    f"""
                                    <div title="{hover_info_html}" style="text-align:center; margin-bottom:5px;">
                                        <img src="data:image/png;base64,{img_b64}" width="150" style="max-width:100%;"><br>
                                        <small>Missing: {missing_html}</small>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                            else:
                                col.error(f"Missing: {os.path.relpath(path, BASE_DIR)}")
                else:  # No images at all
                    if os.path.exists(PLACEHOLDER_PATH):
                        img_b64 = image_to_base64(PLACEHOLDER_PATH)
                        st.markdown(
                            f"""
                            <div title="{hover_info_html}" style="text-align:center; margin-bottom:5px;">
                                <img src="data:image/png;base64,{img_b64}" width="150" style="max-width:100%;"><br>
                                <small>No image available</small>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    else:
                        st.info(f"No images available for **{row['name']}**")

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

st.sidebar.markdown(
    """
    ### Credits
    Images & data © [Coryn Club](https://coryn.club/index.php)
    
    App by Schnee 
    [GitHub](https://github.com/KarenYuusha/toram-item-search)
    """
)

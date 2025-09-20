import pandas as pd
from module.search_engine import search_engine
from module.normalizer import standard_prep
import streamlit as st
import ast
import time
import os
import base64
import re


PLACEHOLDER = "placeholder.jpg"

df = pd.read_csv('coryn_items.csv')

df['image_paths'] = df['image_paths'].apply(ast.literal_eval)
df['name_clean'] = df['name'].apply(standard_prep)

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


st.set_page_config(page_title="Item Search", layout="wide")

all_stats = get_all_stats(df)

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

    items_html = "".join([f"<li>{stat}</li>" for stat in all_stats])

    st.components.v1.html(
        search_component.format(items=items_html),
        height=250,  # adjust depending on desired visible area
        scrolling=False
    )

query = st.text_input(
    "Search for an item by name (or type 'all <weapon type>' or 'stat:<stat name>'):",
    "",
    placeholder="Type here...",
    label_visibility="visible"
)

with st.expander("⚙️ Advanced options"):
    k = st.slider("Number of results:", 1, 100, 20)

if query:
    results = search_engine(query, df, k)
    
    if results.empty:
        st.warning("No matches found")
    
    for _, row in results.iterrows():
        

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
        font-size: 25px;
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
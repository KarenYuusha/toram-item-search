from __future__ import annotations

import streamlit as st

from toram_search.database import validate_databases
from ui.sidebar import render_sidebar

st.set_page_config(page_title="Toram Database", layout="wide")

mode = render_sidebar()
item_health, skill_health = validate_databases()

st.title("Toram Database")
st.caption("Search items, stats, skills, and skill trees")
st.text_input("Search", placeholder="Search items, stats, skills...")
st.button("Search", type="primary")

required_health = (
    (item_health, skill_health)
    if mode == "Universal"
    else (item_health,) if mode == "Items" else (skill_health,)
)
for health in required_health:
    if not health.ok:
        st.error(f"{health.name} database unavailable: {health.error}")

st.caption("Search functionality is being added in the next implementation phase.")

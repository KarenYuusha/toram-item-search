from __future__ import annotations

import streamlit as st

from toram_search.models import DatabaseMode


def render_sidebar() -> DatabaseMode:
    with st.sidebar:
        st.title("Toram Database")
        mode: DatabaseMode = st.radio(
            "Database",
            ("Universal", "Items", "Skills"),
            index=0,
        )
        st.divider()
        st.caption("Deterministic Toram Online database search.")
        st.markdown("**Data credits:** Coryn Club and project-maintained skill data.")
        st.markdown("[GitHub](https://github.com/KarenYuusha/toram-item-search)")
    return mode

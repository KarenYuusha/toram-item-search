from __future__ import annotations

import streamlit as st

from toram_search.models import DatabaseMode


def render_sidebar() -> DatabaseMode:
    with st.sidebar:
        st.title("Toram Database")
        mode: DatabaseMode = st.radio(
            "Database",
            ("Universal", "Items", "Skills", "Food", "Registlets"),
            index=0,
        )

        with st.expander("Search Help"):
            st.markdown(
                """
**Items**

Search by item name, stat, item type, comparisons, or ranking.

Examples: `cr bow`, `hp >= 5000 armor`, `-aggro xtal`, `highest cr`.

**Skills**

Search by skill name, skill tree, ailment, MP, or required level.

Examples: `Guardian`, `Shield Skills`, `skills that inflict stun`, `lowest mp shield skills`.

**Food Code Search**

Start the query with `food` or `code`, followed by a Food stat.

Examples: `food maxmp`, `code ampr`, `food critical rate`, `food dt fire`, `food -aggro`.

Code values themselves are not searchable. Bare `maxmp` and `maxmp food` do not invoke Food search.

**Registlet Search**

Search by Stoodie level: `std 220` or `stoodie lvl 220`.

Search by Registlet name: `Arrow Rain Enhancer`.

Search by effect: `restores mp`, `physical pierce`, or `inflicts stun`.

Registlet results come from `registlets.json`, not the Item database.

In Universal mode, Registlet effect matches are weaker than exact or structured matches.
"""
            )

        st.divider()
        st.caption("Deterministic Toram Online database search.")
        st.markdown("**Data credits:** Coryn Club and project-maintained Toram data.")
        st.markdown("[GitHub](https://github.com/KarenYuusha/toram-item-search)")
    return mode

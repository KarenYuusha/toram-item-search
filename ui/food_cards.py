from __future__ import annotations

from collections import defaultdict

import streamlit as st

from toram_search.food.models import FoodEntry


def render_food_cards(results: tuple[FoodEntry, ...], *, limit: int) -> None:
    visible = results[:limit]
    grouped: dict[int, list[str]] = defaultdict(list)
    for entry in visible:
        grouped[entry.level].append(entry.code)

    for level in sorted(grouped, reverse=True):
        with st.container(border=True):
            st.markdown(f'**Lv. {level}**')
            for code in grouped[level]:
                st.code(code, language=None)

from __future__ import annotations

import streamlit as st

from toram_search.interpretation import QueryInterpretation


def render_query_interpretation(interpretation: QueryInterpretation | None) -> str | None:
    if interpretation is None or not interpretation.chips:
        return None
    st.caption('Parsed filters')
    columns = st.columns(min(len(interpretation.chips), 4))
    for index, chip in enumerate(interpretation.chips):
        with columns[index % len(columns)]:
            if st.button(
                f'{chip.label} ×',
                key=f'query_chip_{interpretation.domain}_{chip.id}',
                use_container_width=True,
            ):
                return interpretation.query_without(chip.id)
    return None

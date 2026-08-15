from __future__ import annotations

import streamlit as st

from toram_search.registlets.models import RegistletRecord


def _render_registlet_card(record: RegistletRecord) -> None:
    st.markdown(f'**{record.name}**')
    st.caption(f'Max Lv. {record.max_lv}')
    st.write(record.effect)
    if record.source_levels:
        levels = ' · '.join(f'Lv{level}' for level in record.source_levels)
        st.write(f'**Stoodie Sources:** {levels}')
    if record.affects_skill:
        st.write('**Affected Skills:** ' + ', '.join(record.affects_skill))


def render_registlet_cards(results: tuple[RegistletRecord, ...], *, limit: int) -> None:
    visible = results[:limit]
    for index in range(0, len(visible), 2):
        columns = st.columns(2)
        for offset, record in enumerate(visible[index:index + 2]):
            with columns[offset]:
                with st.container(border=True):
                    _render_registlet_card(record)

from __future__ import annotations

import streamlit as st

from toram_search.registlets.models import RegistletMatch, RegistletRecord


def _match_label(match: RegistletMatch | None) -> str | None:
    if match is None:
        return None
    if match.kind == 'name':
        return 'Matched by name'
    if match.kind == 'effect':
        return f'Matched by effect: {match.detail}'
    if match.kind == 'stoodie':
        return f'Matched by Stoodie Lv{match.detail}'
    return 'Matched by fuzzy name'


def _render_registlet_card(record: RegistletRecord, match: RegistletMatch | None) -> None:
    st.markdown(f'**{record.name}**')
    label = _match_label(match)
    if label:
        st.caption(label)
    st.caption(f'Max Lv. {record.max_lv}')
    st.write(record.effect)
    if record.source_levels:
        badges = ' '.join(f':gray-badge[Lv{level}]' for level in record.source_levels)
        st.markdown(f'**Stoodie Sources:** {badges}')
    if record.affects_skill:
        st.write('**Affected Skills:** ' + ', '.join(record.affects_skill))


def render_registlet_cards(
    results: tuple[RegistletRecord, ...],
    *,
    limit: int,
    match: RegistletMatch | None,
) -> None:
    visible = results[:limit]
    for index in range(0, len(visible), 2):
        columns = st.columns(2)
        for offset, record in enumerate(visible[index:index + 2]):
            with columns[offset]:
                with st.container(border=True):
                    _render_registlet_card(record, match)

from __future__ import annotations

from pathlib import Path

import streamlit as st

from toram_search.items.models import ItemCardResult
from toram_search.items.repository import ItemRepository
from ui.item_dialog import show_item_dialog


def render_upgrade_path(results: tuple[ItemCardResult, ...], *, database_path: Path) -> None:
    if not results:
        return

    with ItemRepository(database_path) as repository:
        details = {row.item.id: repository.get_item(row.item.id) for row in results}

    chain_ids = set(details)
    successor_names: dict[int, tuple[str, ...]] = {}
    indegree = {item_id: 0 for item_id in chain_ids}
    edge_count = 0
    for item_id, detail in details.items():
        successors = tuple(
            successor
            for successor in detail.upgrade_successors
            if successor.id in chain_ids
        )
        successor_names[item_id] = tuple(successor.name for successor in successors)
        for successor in successors:
            indegree[successor.id] += 1
            edge_count += 1

    is_linear = (
        edge_count == len(results) - 1
        and all(len(successor_names[item_id]) <= 1 for item_id in chain_ids)
        and all(degree <= 1 for degree in indegree.values())
    )

    st.markdown(f'### Upgrade Path · {len(results)} stages')
    if is_linear:
        st.caption(' → '.join(row.item.name for row in results))
    else:
        st.caption('This upgrade path branches. Exact database relationships are shown below.')

    for index, row in enumerate(results, start=1):
        detail = details[row.item.id]
        searched = row.match_kind == 'upgrade_target'

        with st.container(border=True):
            stage_col, image_col, text_col = st.columns([0.7, 1, 5])
            with stage_col:
                st.markdown(f'**{index}**')
            with image_col:
                image_url = next(
                    (str(image.get('source_url')) for image in detail.images if image.get('source_url')),
                    None,
                )
                if image_url:
                    st.image(image_url, width=64)
            with text_col:
                title = f'**{row.item.name}**'
                if searched:
                    title += '  :primary-badge[Searched]'
                st.markdown(title)
                st.caption(row.item.item_type)
                if st.button(
                    'View details',
                    key=f'upgrade_detail_{row.item.id}',
                    use_container_width=True,
                ):
                    show_item_dialog(detail)

        successors = successor_names[row.item.id]
        if successors:
            st.markdown('↓ **Upgrades to:** ' + ' · '.join(successors))
        elif index == len(results):
            st.caption('End of upgrade chain')

from __future__ import annotations
from pathlib import Path
import streamlit as st
from toram_search.items.models import ItemCardResult
from toram_search.items.repository import ItemRepository
from ui.item_dialog import show_item_dialog

def _amount(value: float) -> str: return str(int(value)) if float(value).is_integer() else f'{value:g}'

def render_item_cards(results: tuple[ItemCardResult,...], *, database_path: Path, limit: int) -> None:
    visible=results[:limit]
    if not visible:return
    with ItemRepository(database_path) as repository: details={row.item.id:repository.get_item(row.item.id) for row in visible}
    for index in range(0,len(visible),2):
        columns=st.columns(2)
        for offset,row in enumerate(visible[index:index+2]):
            detail=details[row.item.id]
            with columns[offset]:
                with st.container(border=True):
                    image_url=next((str(img.get('source_url')) for img in detail.images if img.get('source_url')),None)
                    if image_url:
                        image_col,text_col=st.columns([1,4])
                        with image_col: st.image(image_url,width=72)
                    else: text_col=st.container()
                    with text_col:
                        st.markdown(f'**{row.item.name}**'); st.caption(row.item.item_type)
                        if row.matched_stats: st.write(' · '.join(f'{match.stat_name} {_amount(match.amount)}' for match in row.matched_stats[:3]))
                    if st.button('View details',key=f'item_detail_{row.item.id}',use_container_width=True): show_item_dialog(detail)

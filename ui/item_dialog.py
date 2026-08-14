from __future__ import annotations
import streamlit as st
from toram_search.items.models import ItemDetail

def _amount(value: object) -> str:
    try: number=float(value)
    except (TypeError,ValueError): return str(value)
    return str(int(number)) if number.is_integer() else f'{number:g}'

@st.dialog('Item details')
def show_item_dialog(detail: ItemDetail) -> None:
    st.subheader(detail.summary.name); st.caption(detail.summary.item_type)
    image_urls=[str(row.get('source_url')) for row in detail.images if row.get('source_url')]
    if image_urls: st.image(image_urls[0], width=220)
    if detail.badge: st.write(f'**Badge:** {detail.badge}')
    if detail.sell_price is not None: st.write(f'**Sell:** {_amount(detail.sell_price)}')
    if detail.process_material:
        amount=f' × {_amount(detail.process_amount)}' if detail.process_amount is not None else ''
        st.write(f'**Process:** {detail.process_material}{amount}')
    if detail.note: st.info(detail.note)
    st.markdown('#### Stats')
    if detail.stats:
        for row in detail.stats:
            condition=row.get('condition_text'); suffix=f' — {condition}' if condition else ''
            st.write(f"- **{row.get('stat_name','Stat')}**: {_amount(row.get('amount'))}{suffix}")
    else: st.caption('No stats recorded.')
    if detail.sources:
        st.markdown('#### Sources')
        for row in detail.sources:
            pieces=[str(row.get('source_name') or 'Unknown source')]
            if row.get('level') is not None: pieces.append(f"Lv. {row.get('level')}")
            if row.get('map'): pieces.append(str(row.get('map')))
            st.write('- '+' · '.join(pieces))
    if detail.upgrade_predecessors or detail.upgrade_successors:
        st.markdown('#### Upgrade path')
        if detail.upgrade_predecessors: st.write('**Upgrades from:** '+', '.join(row.name for row in detail.upgrade_predecessors))
        if detail.upgrade_successors: st.write('**Upgrades to:** '+', '.join(row.name for row in detail.upgrade_successors))
    if detail.page_url: st.link_button('Open source page', detail.page_url)

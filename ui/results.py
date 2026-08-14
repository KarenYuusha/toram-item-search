from __future__ import annotations
from pathlib import Path
import streamlit as st
from toram_search.items.models import ItemSearchOutcome
from toram_search.skills.models import SkillSearchOutcome
from ui.item_cards import render_item_cards
from ui.skill_cards import render_skill_cards


def _render_message(kind:str,message:str|None,suggestions:tuple[str,...],*,key_prefix:str)->str|None:
    if message:
        if kind=='refuse': st.warning(message)
        elif kind in {'not_found','suggest','clarify'}: st.info(message)
        else: st.write(message)
    if not suggestions:
        return None
    st.caption('Try:')
    columns=st.columns(min(len(suggestions),4))
    for index,query in enumerate(suggestions):
        with columns[index%len(columns)]:
            if st.button(query,key=f'{key_prefix}_suggestion_{index}_{query}',use_container_width=True):
                return query.strip() or None
    return None


def render_item_results(outcome:ItemSearchOutcome,*,database_path:Path,limit:int)->str|None:
    fill_query=_render_message(outcome.kind,outcome.message,outcome.suggested_queries,key_prefix='item')
    if outcome.results:
        st.markdown(f'### Items · {len(outcome.results)}'); render_item_cards(outcome.results,database_path=database_path,limit=limit)
    return fill_query


def render_skill_results(outcome:SkillSearchOutcome,*,limit:int)->str|None:
    fill_query=_render_message(outcome.kind,outcome.message,outcome.suggested_queries,key_prefix='skill')
    if outcome.results:
        st.markdown(f'### Skills · {len(outcome.results)}'); render_skill_cards(outcome.results,limit=limit)
    return fill_query

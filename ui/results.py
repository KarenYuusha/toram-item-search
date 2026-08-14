from __future__ import annotations
from pathlib import Path
import streamlit as st
from toram_search.items.models import ItemSearchOutcome
from toram_search.skills.models import SkillSearchOutcome
from ui.item_cards import render_item_cards
from ui.skill_cards import render_skill_cards

def _render_message(kind:str,message:str|None,suggestions:tuple[str,...])->None:
    if message:
        if kind=='refuse': st.warning(message)
        elif kind in {'not_found','suggest','clarify'}: st.info(message)
        else: st.write(message)
    if suggestions: st.caption('Try: '+' · '.join(f'`{query}`' for query in suggestions))

def render_item_results(outcome:ItemSearchOutcome,*,database_path:Path,limit:int)->None:
    _render_message(outcome.kind,outcome.message,outcome.suggested_queries)
    if outcome.results:
        st.markdown(f'### Items · {len(outcome.results)}'); render_item_cards(outcome.results,database_path=database_path,limit=limit)

def render_skill_results(outcome:SkillSearchOutcome,*,limit:int)->None:
    _render_message(outcome.kind,outcome.message,outcome.suggested_queries)
    if outcome.results:
        st.markdown(f'### Skills · {len(outcome.results)}'); render_skill_cards(outcome.results,limit=limit)

from __future__ import annotations

from pathlib import Path
import streamlit as st
from toram_search.autocomplete import build_autocomplete_index
from toram_search.database import ITEM_DATABASE, SKILL_DATABASE, validate_databases
from toram_search.models import DatabaseMode, UniversalSearchOutcome
from toram_search.router import search_database
from ui.results import render_item_results, render_skill_results
from ui.search import render_search_box
from ui.sidebar import render_sidebar

st.set_page_config(page_title='Toram Database', page_icon='🔎', layout='wide')
st.markdown('''<style>.block-container{max-width:1180px;padding-top:2rem}[data-testid="stMetricValue"]{font-size:1.35rem}div[data-testid="stVerticalBlockBorderWrapper"]{border-radius:.75rem}</style>''',unsafe_allow_html=True)
for key,value in {'query':'','last_submission_nonce':None,'last_outcome':None,'last_mode':'Universal','item_limit':20,'skill_limit':20}.items():
    if key not in st.session_state: st.session_state[key]=value
mode:DatabaseMode=render_sidebar(); item_health,skill_health=validate_databases()
if st.session_state.last_mode!=mode:
    st.session_state.last_mode=mode; st.session_state.last_outcome=None; st.session_state.item_limit=20; st.session_state.skill_limit=20
st.title('Toram Database'); st.caption('Search items, stats, skills, and skill trees')
required_health=(item_health,skill_health) if mode=='Universal' else (item_health,) if mode=='Items' else (skill_health,)
can_search=all(health.ok for health in required_health)
for health in required_health:
    if not health.ok: st.error(f'{health.name} database unavailable: {health.error}')
@st.cache_data(show_spinner=False)
def _suggestions(database_mode:DatabaseMode,items_path:str,skills_path:str):
    return build_autocomplete_index(database_mode,items_path=Path(items_path),skills_path=Path(skills_path))
suggestions=_suggestions(mode,str(ITEM_DATABASE),str(SKILL_DATABASE)) if can_search else ()
submission=render_search_box(value=st.session_state.query,suggestions=suggestions,placeholder=('Search items, stats, and skills...' if mode=='Universal' else 'Search items or stats...' if mode=='Items' else 'Search skills or skill trees...'),disabled=not can_search)
examples={'Universal':('critical rate','Guardian','Shield Skills','stun skills'),'Items':('cr bow','hp >= 5000 armor','-aggro xtal','highest cr'),'Skills':('Guardian','Shield Skills','skills that inflict stun','lowest mp shield skills')}[mode]
st.caption('Examples'); example_columns=st.columns(len(examples)); example_query=None
for column,example in zip(example_columns,examples):
    with column:
        if st.button(example,key=f'example_{mode}_{example}',use_container_width=True,disabled=not can_search): example_query=example
query_to_run=None
if submission is not None and submission.nonce!=st.session_state.last_submission_nonce:
    st.session_state.last_submission_nonce=submission.nonce; query_to_run=submission.query
elif example_query is not None: query_to_run=example_query
if query_to_run is not None and can_search:
    st.session_state.query=query_to_run; st.session_state.item_limit=20; st.session_state.skill_limit=20
    with st.spinner('Searching database...'):
        st.session_state.last_outcome=search_database(mode,query_to_run,items_path=ITEM_DATABASE,skills_path=SKILL_DATABASE)
outcome:UniversalSearchOutcome|None=st.session_state.last_outcome
if outcome is not None:
    st.divider(); st.caption(f'Results for “{outcome.query}”')
    if outcome.items is not None:
        render_item_results(outcome.items,database_path=ITEM_DATABASE,limit=st.session_state.item_limit)
        if len(outcome.items.results)>st.session_state.item_limit and st.button('Show more items',key='show_more_items'):
            st.session_state.item_limit+=20; st.rerun()
    if outcome.skills is not None:
        render_skill_results(outcome.skills,limit=st.session_state.skill_limit)
        if len(outcome.skills.results)>st.session_state.skill_limit and st.button('Show more skills',key='show_more_skills'):
            st.session_state.skill_limit+=20; st.rerun()

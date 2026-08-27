from __future__ import annotations

from pathlib import Path
import streamlit as st
from toram_search.autocomplete import build_autocomplete_index
from toram_search.database import (
    FOOD_ALIASES,
    FOOD_ENTRIES,
    ITEM_DATABASE,
    REGISTLET_DATA,
    SKILL_DATABASE,
    validate_sources,
)
from toram_search.models import DatabaseMode, UniversalSearchOutcome
from toram_search.router import search_database
from ui import interpretation as query_interpretation_ui
from ui.results import (
    render_food_results,
    render_item_results,
    render_registlet_results,
    render_skill_results,
)
from ui.search import render_search_box
from ui.sidebar import render_sidebar

st.set_page_config(page_title='Toram Database', page_icon='🔎', layout='wide')
st.markdown('''<style>.block-container{max-width:1180px;padding-top:2rem}[data-testid="stMetricValue"]{font-size:1.35rem}div[data-testid="stVerticalBlockBorderWrapper"]{border-radius:.75rem}</style>''',unsafe_allow_html=True)

_LIMIT_KEYS=('item_limit','skill_limit','food_limit','registlet_limit')

def _reset_limits()->None:
    for key in _LIMIT_KEYS:
        st.session_state[key]=20

for key,value in {
    'query':'',
    'last_submission_nonce':None,
    'last_outcome':None,
    'last_mode':'Universal',
    'item_limit':20,
    'skill_limit':20,
    'food_limit':20,
    'registlet_limit':20,
}.items():
    if key not in st.session_state: st.session_state[key]=value

mode:DatabaseMode=render_sidebar()
item_health,skill_health,food_health,registlet_health=validate_sources()
health_by_domain={
    'Items':item_health,
    'Skills':skill_health,
    'Food':food_health,
    'Registlets':registlet_health,
}
available_domains=frozenset(
    domain for domain,health in health_by_domain.items() if health.ok
)

if st.session_state.last_mode!=mode:
    st.session_state.last_mode=mode
    st.session_state.last_outcome=None
    _reset_limits()

st.title('Toram Database')
st.caption('Search items, skills, Food codes, and Registlets')

visible_health=tuple(health_by_domain.values()) if mode=='Universal' else (health_by_domain[mode],)
for health in visible_health:
    if not health.ok:
        st.error(f'{health.name} data unavailable: {health.error}')
can_search=bool(available_domains) if mode=='Universal' else mode in available_domains

examples={
    'Universal':('critical rate','food maxmp','physical pierce'),
    'Items':('cr bow','hp >= 5000 armor','highest cr','upgrade Iconos'),
    'Skills':('Guardian','Shield Skills','skills that inflict stun'),
    'Food':('food maxmp','code ampr','food dt fire'),
    'Registlets':('std 220','Arrow Rain Enhancer','physical pierce'),
}[mode]
st.caption('Suggested searches'); example_columns=st.columns(len(examples)); example_query=None
for column,example in zip(example_columns,examples):
    with column:
        if st.button(example,key=f'example_{mode}_{example}',use_container_width=True,disabled=not can_search): example_query=example
if example_query is not None:
    st.session_state.query=example_query
    st.session_state.last_outcome=None
    _reset_limits()
    st.rerun()

@st.cache_data(show_spinner=False)
def _suggestions(
    database_mode:DatabaseMode,
    items_path:str,
    skills_path:str,
    food_entries_path:str,
    food_aliases_path:str,
    registlets_path:str,
    available:tuple[str,...],
):
    return build_autocomplete_index(
        database_mode,
        items_path=Path(items_path),
        skills_path=Path(skills_path),
        food_entries_path=Path(food_entries_path),
        food_aliases_path=Path(food_aliases_path),
        registlets_path=Path(registlets_path),
        available_domains=frozenset(available),
    )

suggestions=_suggestions(
    mode,
    str(ITEM_DATABASE),
    str(SKILL_DATABASE),
    str(FOOD_ENTRIES),
    str(FOOD_ALIASES),
    str(REGISTLET_DATA),
    tuple(sorted(available_domains)),
) if can_search else ()

placeholders={
    'Universal':'Search Toram database...',
    'Items':'Search items or stats...',
    'Skills':'Search skills or skill trees...',
    'Food':'Start with food or code...',
    'Registlets':'Search Stoodie level, name, or effect...',
}
syntax_hints={
    'Universal':'Try: cr bow · food maxmp · std 220 · physical pierce',
    'Items':'Try: item name · cr bow · hp >= 5000 armor',
    'Skills':'Try: Guardian · Shield Skills · skills that inflict stun',
    'Food':'Start with food/code: food maxmp · code ampr',
    'Registlets':'Try: std 220 · Arrow Rain Enhancer · physical pierce',
}
st.caption(syntax_hints[mode])
submission=render_search_box(value=st.session_state.query,suggestions=suggestions,placeholder=placeholders[mode],disabled=not can_search)

query_to_run=None
if submission is not None and submission.nonce!=st.session_state.last_submission_nonce:
    st.session_state.last_submission_nonce=submission.nonce; query_to_run=submission.query
if query_to_run is not None and can_search:
    st.session_state.query=query_to_run
    _reset_limits()
    with st.spinner('Searching database...'):
        st.session_state.last_outcome=search_database(
            mode,
            query_to_run,
            items_path=ITEM_DATABASE,
            skills_path=SKILL_DATABASE,
            food_entries_path=FOOD_ENTRIES,
            food_aliases_path=FOOD_ALIASES,
            registlets_path=REGISTLET_DATA,
            available_domains=available_domains,
        )

outcome:UniversalSearchOutcome|None=st.session_state.last_outcome
chip_fill=query_interpretation_ui.render_query_interpretation(outcome.interpretation if outcome is not None else None)
if chip_fill is not None:
    st.session_state.query=chip_fill
    st.session_state.last_outcome=None
    _reset_limits()
    st.rerun()

if outcome is not None:
    st.divider(); st.caption(f'Results for “{outcome.query}”')
    if outcome.items is not None:
        item_fill=render_item_results(outcome.items,database_path=ITEM_DATABASE,limit=st.session_state.item_limit)
        if item_fill is not None:
            st.session_state.query=item_fill
            st.session_state.last_outcome=None
            _reset_limits()
            st.rerun()
        if len(outcome.items.results)>st.session_state.item_limit and st.button('Show more items',key='show_more_items'):
            st.session_state.item_limit+=20; st.rerun()
    if outcome.skills is not None:
        skill_fill=render_skill_results(outcome.skills,limit=st.session_state.skill_limit)
        if skill_fill is not None:
            st.session_state.query=skill_fill
            st.session_state.last_outcome=None
            _reset_limits()
            st.rerun()
        if len(outcome.skills.results)>st.session_state.skill_limit and st.button('Show more skills',key='show_more_skills'):
            st.session_state.skill_limit+=20; st.rerun()
    if outcome.food is not None:
        food_fill=render_food_results(outcome.food,limit=st.session_state.food_limit)
        if food_fill is not None:
            st.session_state.query=food_fill
            st.session_state.last_outcome=None
            _reset_limits()
            st.rerun()
        if len(outcome.food.results)>st.session_state.food_limit and st.button('Show more Food codes',key='show_more_food'):
            st.session_state.food_limit+=20; st.rerun()
    if outcome.registlets is not None:
        registlet_fill=render_registlet_results(outcome.registlets,limit=st.session_state.registlet_limit)
        if registlet_fill is not None:
            st.session_state.query=registlet_fill
            st.session_state.last_outcome=None
            _reset_limits()
            st.rerun()
        if len(outcome.registlets.results)>st.session_state.registlet_limit and st.button('Show more Registlets',key='show_more_registlets'):
            st.session_state.registlet_limit+=20; st.rerun()

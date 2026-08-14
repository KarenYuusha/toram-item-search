from __future__ import annotations
import streamlit as st
from toram_search.skill_icons import DEFAULT_SKILL_ICON_CATALOG
from toram_search.skills.models import SkillCardResult
from ui.skill_dialog import show_skill_dialog


def _render_skill_header(card: SkillCardResult) -> None:
    skill=card.skill
    icon=DEFAULT_SKILL_ICON_CATALOG.resolve(card.tree_name,skill.name)
    if icon is None:
        st.markdown(f'**{skill.name}**')
        meta=[card.tree_name]
        if skill.tier is not None: meta.append(f'Tier {skill.tier}')
        st.caption(' · '.join(meta))
        return
    icon_column,text_column=st.columns([1,4])
    with icon_column:
        st.image(str(icon),width=64)
    with text_column:
        st.markdown(f'**{skill.name}**')
        meta=[card.tree_name]
        if skill.tier is not None: meta.append(f'Tier {skill.tier}')
        st.caption(' · '.join(meta))


def render_skill_cards(results: tuple[SkillCardResult,...], *, limit: int) -> None:
    visible=results[:limit]
    for index in range(0,len(visible),2):
        columns=st.columns(2)
        for offset,card in enumerate(visible[index:index+2]):
            skill=card.skill
            with columns[offset]:
                with st.container(border=True):
                    _render_skill_header(card)
                    facts=[]
                    if skill.mp_cost_text: facts.append(f'MP {skill.mp_cost_text}')
                    if skill.required_level is not None: facts.append(f'Lv. {skill.required_level}')
                    if skill.skill_type: facts.append(skill.skill_type)
                    if facts: st.write(' · '.join(facts))
                    if skill.ailments: st.write('Ailment: '+', '.join(skill.ailments))
                    if st.button('View details',key=f'skill_detail_{skill.id}',use_container_width=True): show_skill_dialog(card)

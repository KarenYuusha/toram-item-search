from __future__ import annotations
import streamlit as st
from toram_search.skills.models import SkillCardResult

@st.dialog('Skill details')
def show_skill_dialog(card: SkillCardResult) -> None:
    skill=card.skill; st.subheader(skill.name)
    header=[card.tree_name]
    if skill.tier is not None: header.append(f'Tier {skill.tier}')
    if skill.skill_type: header.append(skill.skill_type)
    st.caption(' · '.join(header))
    left,right=st.columns(2)
    with left: st.metric('MP',skill.mp_cost_text or '—')
    with right: st.metric('Required Lv.',skill.required_level if skill.required_level is not None else '—')
    for label,value in (('Damage Type',skill.damage_type),('Element',skill.element),('Cast Range',skill.cast_range_text),('Hit Range',skill.hit_range_text),('Cast Time',skill.cast_time_text),('Hit Count',skill.hit_count_text)):
        if value: st.write(f'**{label}:** {value}')
    if skill.ailments: st.write('**Ailments:** '+', '.join(skill.ailments))
    if skill.weapon_requirements: st.write('**Weapon requirements:** '+', '.join(skill.weapon_requirements))
    if skill.weapon_restrictions: st.write('**Weapon restrictions:** '+', '.join(skill.weapon_restrictions))
    if skill.description: st.markdown('#### Description'); st.write(skill.description)
    if skill.game_description: st.markdown('#### Game description'); st.write(skill.game_description)
    for section in skill.sections:
        if section.body: st.markdown(f'#### {section.label}'); st.write(section.body)

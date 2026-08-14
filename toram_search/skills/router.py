from __future__ import annotations
from dataclasses import dataclass
from .models import SkillFilter

@dataclass(frozen=True)
class SkillPlan:
    intent:str
    filters:SkillFilter=SkillFilter()
    field:str|None=None
    direction:str|None=None


def route_skill_query(query:str)->SkillPlan:
    q=' '.join(query.casefold().strip(' ?!.').split())
    if q.startswith('best ') and any(x in q for x in ('dps','tank','build')):return SkillPlan('refuse')
    if 'mp' in q and any(x in q for x in ('lowest','least','highest')):return SkillPlan('rank',field='mp_cost_value',direction='desc' if 'highest' in q else 'asc')
    return SkillPlan('lookup')

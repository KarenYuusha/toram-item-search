from __future__ import annotations
from .models import SkillFilter, SkillRecord
from .repository import SkillRepository
from .structured_search import structured_skill_ids

COMPARABLE_FIELDS=frozenset({'mp_cost_value','required_level','tier'})

class SkillAnalytics:
    def __init__(self,repository:SkillRepository): self.repository=repository
    def filter_skills(self,filters:SkillFilter=SkillFilter())->tuple[SkillRecord,...]:
        ids=structured_skill_ids(self.repository,filters)
        if filters.ailments:
            eligible=structured_skill_ids(self.repository,SkillFilter(tree_ids=filters.tree_ids,tiers=filters.tiers,skill_types=filters.skill_types,weapons=filters.weapons,required_level_max=filters.required_level_max,mp_cost_max=filters.mp_cost_max))
            prose=set()
            for ailment in filters.ailments:
                term=' '.join(ailment.casefold().split())
                for row in self.repository.connection.execute("SELECT DISTINCT skill_id,LOWER(text) FROM skill_search_documents WHERE LOWER(text) LIKE ? OR LOWER(text) LIKE ?",(f'%inflict {term}%',f'%inflicts {term}%')):
                    prose.add(str(row[0]))
            selected=set(ids)|(prose&set(eligible)); ids=tuple(i for i in eligible if i in selected)
        return tuple(self.repository.get_skill(i) for i in ids)
    def count(self,filters:SkillFilter=SkillFilter())->int:return len(self.filter_skills(filters))
    def rank(self,field:str,direction:str,*,filters:SkillFilter=SkillFilter(),limit:int=5)->tuple[SkillRecord,...]:
        if field not in COMPARABLE_FIELDS: raise ValueError(field)
        rows=[s for s in self.filter_skills(filters) if getattr(s,field) is not None]
        rows.sort(key=lambda s:((int(getattr(s,field)) if direction=='asc' else -int(getattr(s,field))),s.normalized_name,s.id))
        return tuple(rows[:limit])
    def compare_field(self,skill_ids:tuple[str,...],field:str)->tuple[tuple[SkillRecord,int|None],...]:
        if field not in COMPARABLE_FIELDS: raise ValueError(field)
        return tuple((s,getattr(s,field)) for s in (self.repository.get_skill(i) for i in skill_ids))

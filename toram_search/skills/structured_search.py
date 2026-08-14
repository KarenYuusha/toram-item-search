from __future__ import annotations
from .models import SkillFilter
from .normalization import normalize_skill_name
from .repository import SkillRepository

def _ph(n:int)->str: return ','.join('?' for _ in range(n))

def structured_skill_ids(repository:SkillRepository,filters:SkillFilter)->tuple[str,...]:
    clauses=[];params=[]
    if filters.tree_ids: clauses.append(f's.tree_id IN ({_ph(len(filters.tree_ids))})');params.extend(filters.tree_ids)
    if filters.tiers: clauses.append(f's.tier IN ({_ph(len(filters.tiers))})');params.extend(filters.tiers)
    if filters.skill_types:
        vals=tuple(normalize_skill_name(x) for x in filters.skill_types);clauses.append(f'LOWER(s.skill_type) IN ({_ph(len(vals))})');params.extend(vals)
    if filters.required_level_max is not None: clauses.append('s.required_level IS NOT NULL AND s.required_level<=?');params.append(filters.required_level_max)
    if filters.mp_cost_max is not None: clauses.append('s.mp_cost_value IS NOT NULL AND s.mp_cost_value<=?');params.append(filters.mp_cost_max)
    if filters.ailments:
        vals=tuple(normalize_skill_name(x) for x in filters.ailments);clauses.append(f'EXISTS (SELECT 1 FROM skill_ailments a WHERE a.skill_id=s.id AND a.normalized_name IN ({_ph(len(vals))}))');params.extend(vals)
    if filters.weapons:
        vals=tuple(normalize_skill_name(x) for x in filters.weapons);ph=_ph(len(vals));clauses.append(f'''(EXISTS (SELECT 1 FROM skill_weapon_requirements wr WHERE wr.skill_id=s.id AND wr.normalized_name IN ({ph})) OR EXISTS (SELECT 1 FROM skill_weapon_restrictions ws WHERE ws.skill_id=s.id AND ws.normalized_name IN ({ph})) OR EXISTS (SELECT 1 FROM skill_tree_weapon_restrictions twr WHERE twr.tree_id=s.tree_id AND twr.normalized_weapon IN ({ph})))''');params.extend(vals);params.extend(vals);params.extend(vals)
    sql='SELECT s.id FROM skills s'
    if clauses: sql+=' WHERE '+' AND '.join(f'({c})' for c in clauses)
    sql+=' ORDER BY s.tree_id,s.source_order,s.id'
    return tuple(str(r[0]) for r in repository.connection.execute(sql,tuple(params)))

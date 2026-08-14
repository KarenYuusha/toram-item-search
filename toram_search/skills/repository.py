from __future__ import annotations
import json
from pathlib import Path
from toram_search.database import connect_readonly
from .models import SkillRecord, SkillSection, SkillTree
from .normalization import normalize_skill_name

class SkillRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path=Path(database_path).expanduser().resolve()
        self.connection=connect_readonly(self.database_path)
    def close(self): self.connection.close()
    def __enter__(self): return self
    def __exit__(self,exc_type,exc,tb): self.close()
    def count_trees(self)->int: return int(self.connection.execute('SELECT COUNT(*) FROM skill_trees').fetchone()[0])
    def count_skills(self)->int: return int(self.connection.execute('SELECT COUNT(*) FROM skills').fetchone()[0])
    def list_tree_names(self)->list[str]: return [str(r[0]) for r in self.connection.execute('SELECT name FROM skill_trees ORDER BY name COLLATE NOCASE,id')]
    def list_skill_names(self)->tuple[str,...]: return tuple(str(r[0]) for r in self.connection.execute('SELECT name FROM skills ORDER BY name COLLATE NOCASE,id'))
    def list_skill_types(self)->tuple[str,...]: return tuple(str(r[0]) for r in self.connection.execute("SELECT DISTINCT skill_type FROM skills WHERE skill_type IS NOT NULL AND TRIM(skill_type)<>'' ORDER BY skill_type COLLATE NOCASE"))
    def list_known_ailments(self)->tuple[str,...]: return tuple(str(r[0]) for r in self.connection.execute('SELECT MIN(name) FROM skill_ailments GROUP BY normalized_name ORDER BY MIN(name) COLLATE NOCASE'))
    def _tree(self,row)->SkillTree:
        tiers=tuple((int(v[0]),None if v[1] is None else int(v[1])) for v in json.loads(str(row['tier_requirements_json'] or '[]')))
        restrictions=tuple(str(v) for v in json.loads(str(row['weapon_restrictions_json'] or '[]')))
        return SkillTree(str(row['id']),str(row['name']),str(row['normalized_name']),str(row['tree_group']),str(row['general_text'] or ''),tiers,restrictions)
    def get_tree(self,tree_id:str)->SkillTree:
        row=self.connection.execute('SELECT id,name,normalized_name,tree_group,general_text,tier_requirements_json,weapon_restrictions_json FROM skill_trees WHERE id=?',(tree_id,)).fetchone()
        if row is None: raise KeyError(tree_id)
        return self._tree(row)
    def resolve_tree_name(self,name:str)->tuple[SkillTree,...]:
        q=normalize_skill_name(name)
        rows=self.connection.execute('SELECT id,name,normalized_name,tree_group,general_text,tier_requirements_json,weapon_restrictions_json FROM skill_trees ORDER BY id').fetchall()
        matches=[]
        for row in rows:
            n=normalize_skill_name(str(row['name']))
            shorthand=n[:-7].strip() if n.endswith(' skills') else n
            if q in {n,shorthand,f'{shorthand} skill tree',f'{shorthand} skills tree'}:
                matches.append(self._tree(row))
        return tuple(matches)
    def _values(self,table:str,column:str,skill_id:str)->tuple[str,...]:
        return tuple(str(r[0]) for r in self.connection.execute(f'SELECT {column} FROM {table} WHERE skill_id=? ORDER BY position',(skill_id,)))
    def get_skill(self,skill_id:str)->SkillRecord:
        row=self.connection.execute('SELECT id,tree_id,source_order,name,normalized_name,tier,required_level,skill_type,mp_cost_text,mp_cost_value,damage_type,element,cast_range_text,hit_range_text,cast_time_text,hit_count_text,description,game_description,raw_text FROM skills WHERE id=?',(skill_id,)).fetchone()
        if row is None: raise KeyError(skill_id)
        sections=tuple(SkillSection(int(r['position']),str(r['label']),str(r['normalized_label']),str(r['body'])) for r in self.connection.execute('SELECT position,label,normalized_label,body FROM skill_sections WHERE skill_id=? ORDER BY position',(skill_id,)))
        return SkillRecord(
            id=str(row['id']),tree_id=str(row['tree_id']),source_order=int(row['source_order']),name=str(row['name']),normalized_name=str(row['normalized_name']),
            aliases=self._values('skill_aliases','alias',skill_id),tier=None if row['tier'] is None else int(row['tier']),required_level=None if row['required_level'] is None else int(row['required_level']),
            skill_type=None if row['skill_type'] is None else str(row['skill_type']),mp_cost_text=None if row['mp_cost_text'] is None else str(row['mp_cost_text']),mp_cost_value=None if row['mp_cost_value'] is None else int(row['mp_cost_value']),
            damage_type=None if row['damage_type'] is None else str(row['damage_type']),element=None if row['element'] is None else str(row['element']),cast_range_text=None if row['cast_range_text'] is None else str(row['cast_range_text']),
            hit_range_text=None if row['hit_range_text'] is None else str(row['hit_range_text']),cast_time_text=None if row['cast_time_text'] is None else str(row['cast_time_text']),hit_count_text=None if row['hit_count_text'] is None else str(row['hit_count_text']),
            ailments=self._values('skill_ailments','name',skill_id),weapon_requirements=self._values('skill_weapon_requirements','weapon',skill_id),weapon_restrictions=self._values('skill_weapon_restrictions','weapon',skill_id),sections=sections,
            description=None if row['description'] is None else str(row['description']),game_description=None if row['game_description'] is None else str(row['game_description']),raw_text=str(row['raw_text'] or '')
        )
    def resolve_skill_name(self,name:str,*,tree_id:str|None=None)->tuple[SkillRecord,...]:
        q=normalize_skill_name(name)
        params=[q]
        tree_clause=' AND s.tree_id=?' if tree_id else ''
        if tree_id: params.append(tree_id)
        params.append(q)
        if tree_id: params.append(tree_id)
        rows=self.connection.execute(f'''SELECT DISTINCT s.id FROM skills s LEFT JOIN skill_aliases a ON a.skill_id=s.id WHERE (s.normalized_name=? {tree_clause}) OR (a.normalized_alias=? {tree_clause}) ORDER BY s.tree_id,s.source_order,s.id''',tuple(params)).fetchall()
        return tuple(self.get_skill(str(r[0])) for r in rows)
    def list_skills_in_tree(self,tree_id:str)->tuple[SkillRecord,...]:
        return tuple(self.get_skill(str(r[0])) for r in self.connection.execute('SELECT id FROM skills WHERE tree_id=? ORDER BY source_order,id',(tree_id,)))
    def all_skills(self)->tuple[SkillRecord,...]:
        return tuple(self.get_skill(str(r[0])) for r in self.connection.execute('SELECT id FROM skills ORDER BY tree_id,source_order,id'))

from __future__ import annotations
import re
from dataclasses import dataclass
from .repository import SkillRepository

@dataclass(frozen=True)
class SkillSearchHit:
    skill_id:str
    score:float

_WORD_RE=re.compile(r'\w+',re.UNICODE)
def _tokens(query:str)->tuple[str,...]:
    seen=[]
    for m in _WORD_RE.finditer(query.casefold()):
        t=m.group(0).strip('_')
        if t and t not in seen: seen.append(t)
    return tuple(seen)

def lexical_search(repository:SkillRepository,query:str,*,eligible_skill_ids:tuple[str,...]|None=None,limit:int=20)->tuple[SkillSearchHit,...]:
    tokens=_tokens(query)
    if not tokens or limit<=0:return ()
    def run(op:str):
        expr=f' {op} '.join(f'"{t}"' for t in tokens);params=[expr];sql='SELECT skill_id,bm25(skill_fts) score FROM skill_fts WHERE skill_fts MATCH ?'
        if eligible_skill_ids is not None:
            if not eligible_skill_ids:return []
            ph=','.join('?'*len(eligible_skill_ids));sql+=f' AND skill_id IN ({ph})';params.extend(eligible_skill_ids)
        sql+=' ORDER BY score ASC,skill_id';return list(repository.connection.execute(sql,tuple(params)))
    rows=run('AND')
    if not rows and len(tokens)>1: rows=run('OR')
    best={}
    for r in rows:
        sid=str(r['skill_id']);score=float(r['score'])
        if sid not in best or score<best[sid]:best[sid]=score
    ordered=sorted(best.items(),key=lambda x:(x[1],x[0]))[:limit]
    return tuple(SkillSearchHit(sid,-score) for sid,score in ordered)

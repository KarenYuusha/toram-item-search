from __future__ import annotations
from .normalization import normalize_skill_name
CONCEPT_ALIASES={'ignition':'ignite'}
def resolve_ailment(text:str,known:tuple[str,...])->str|None:
    q=normalize_skill_name(text);q=CONCEPT_ALIASES.get(q,q);by={normalize_skill_name(v):v for v in known};return by.get(q)

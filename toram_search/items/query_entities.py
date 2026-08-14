from __future__ import annotations
from dataclasses import dataclass
from .aliases import normalize_stat_text

@dataclass(frozen=True)
class QueryToken:
    index: int
    text: str
    normalized: str


def tokenize_item_query(raw_query:str)->tuple[QueryToken,...]:
    return tuple(QueryToken(i,t,normalize_stat_text(t)) for i,t in enumerate(raw_query.split()))

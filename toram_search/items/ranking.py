from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from rapidfuzz import fuzz
from .aliases import normalize_name
from .models import ItemSummary

@dataclass(frozen=True)
class RankedItem:
    item: ItemSummary
    score: float
    match_kind: str


def rank_items(query: str, items: Iterable[ItemSummary]) -> list[RankedItem]:
    q=normalize_name(query)
    if len(q)<2:return []
    rows=[]
    for item in items:
        n=normalize_name(item.name)
        score=max(float(fuzz.WRatio(q,n)),float(fuzz.token_set_ratio(q,n)),float(fuzz.token_sort_ratio(q,n)))
        kind='fuzzy'
        if n==q: score,kind=100.0,'exact'
        elif n.startswith(q): score,kind=max(score,98.0),'prefix'
        elif q in n: score,kind=max(score,95.0),'substring'
        if score>=70: rows.append(RankedItem(item,score,kind))
    rows.sort(key=lambda row:(-row.score,len(normalize_name(row.item.name)),normalize_name(row.item.name),row.item.id))
    return rows

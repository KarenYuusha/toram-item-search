from __future__ import annotations
from .aliases import STAT_ALIASES, STAT_AMBIGUOUS_GROUPS, normalize_stat_text
from .filters import extract_item_filter


def try_suggest_query(raw_query: str, *, available_stats: list[str], available_item_types: set[str]) -> str | None:
    item_filter, remaining = extract_item_filter(raw_query, available_item_types)
    tokens=normalize_stat_text(remaining).split()
    terms=sorted(set(STAT_ALIASES)|set(STAT_AMBIGUOUS_GROUPS),key=lambda x:(len(x.split()),len(x)),reverse=True)
    hits=[]
    occupied=set()
    for term in terms:
        parts=term.split()
        for start in range(len(tokens)-len(parts)+1):
            idx=tuple(range(start,start+len(parts)))
            if any(i in occupied for i in idx): continue
            if tokens[start:start+len(parts)]==parts:
                hits.append(term); occupied.update(idx); break
    for stat in available_stats:
        n=normalize_stat_text(stat); parts=n.split()
        for start in range(len(tokens)-len(parts)+1):
            idx=tuple(range(start,start+len(parts)))
            if any(i in occupied for i in idx): continue
            if tokens[start:start+len(parts)]==parts:
                hits.append(n); occupied.update(idx); break
    if len(hits)<2:return None
    filter_text=item_filter.consumed_text if item_filter else ''
    return (' and '.join(hits)+(f' {filter_text}' if filter_text else '')).strip()


def try_reconstruct_simple_search(raw_query: str, *, available_stats: list[str], available_item_types: set[str]) -> str | None:
    return try_suggest_query(raw_query,available_stats=available_stats,available_item_types=available_item_types)

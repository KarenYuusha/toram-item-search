from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from .aliases import normalize_stat_text
from .filters import extract_item_filter
from .repository import ItemRepository
from .models import ParsedStatExpression
from .stat_query import parse_stat_expression

SearchIntent=Literal['exact_item','item_search','stat_search','stat_expression','exact_upgrade','upgrade_search','guided_stat']

@dataclass(frozen=True)
class ParsedSearch:
    intent: SearchIntent
    raw_query: str
    item_query: str|None=None
    item_id: int|None=None
    stat_name: str|None=None
    parsed_expression: ParsedStatExpression|None=None


def parse_search_query(query: str, repository: ItemRepository) -> ParsedSearch:
    raw=query.strip()
    if raw.casefold().startswith('upgrade '):
        target=raw[8:].strip(); exact=repository.exact_upgrade_name_matches(target)
        if len(exact)==1:return ParsedSearch('exact_upgrade',raw,item_id=exact[0].id)
        return ParsedSearch('upgrade_search',raw,item_query=target)
    exact=repository.exact_name_matches(raw)
    if len(exact)==1:return ParsedSearch('exact_item',raw,item_id=exact[0].id)
    _item_filter, remaining=extract_item_filter(raw,repository.list_item_types())
    normalized=normalize_stat_text(remaining)
    if any(op in raw for op in ('>=','<=','==','>','<','=')) or ' and ' in f' {normalized} ' or ' or ' in f' {normalized} ':
        return ParsedSearch('stat_expression',raw,parsed_expression=parse_stat_expression(raw,repository.list_item_types(),repository.list_stat_names()))
    by_norm={normalize_stat_text(x):x for x in repository.list_stat_names()}
    stat=by_norm.get(normalized)
    if stat:return ParsedSearch('stat_search',raw,stat_name=stat)
    return ParsedSearch('item_search',raw,item_query=raw)

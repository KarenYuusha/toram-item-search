from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from .reconstruction import try_suggest_query

Decision=Literal['execute','suggest','fallback']
@dataclass(frozen=True)
class ItemQueryUnderstanding:
    decision: Decision
    canonical_query: str|None=None
    suggested_query: str|None=None


def understand_item_query(query:str,*,available_stats:list[str],available_item_types:set[str])->ItemQueryUnderstanding:
    suggestion=try_suggest_query(query,available_stats=available_stats,available_item_types=available_item_types)
    if suggestion:return ItemQueryUnderstanding('suggest',suggested_query=suggestion)
    return ItemQueryUnderstanding('fallback')

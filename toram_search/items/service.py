from __future__ import annotations
import re
from pathlib import Path
from rapidfuzz import fuzz
from .aliases import STAT_ALIASES, normalize_stat_text
from .filters import extract_item_filter
from .models import ItemCardResult, ItemSearchOutcome
from .repository import ItemRepository
from .stat_query import StatQuerySyntaxError, parse_stat_expression

_HELP = "Search by item name, stat, item type, numeric comparisons, AND/OR, or upgrade relationships. Examples: cr xtal; hp >= 5000 armor; hp > 5000 and cr bow."
_SUBJECTIVE = re.compile(r"\b(?:best|strongest)\b.*\b(?:tank|dps|build|mage)\b|\b(?:tank|dps)\b.*\b(?:xtal|crysta|item|build)\b",re.I)

class ItemSearchService:
    def __init__(self,database_path:Path): self.repository=ItemRepository(database_path)
    def close(self): self.repository.close()
    def get_item(self,item_id:int): return self.repository.get_item(item_id)
    def list_autocomplete_values(self):
        rows=[(x.name,'Item') for x in self.repository.list_items()]
        rows += [(x,'Stat') for x in self.repository.list_stat_names()]
        rows += [(x,'Item Type') for x in sorted(self.repository.list_item_types())]
        return tuple(rows)
    def _resolve_stat(self,text:str)->tuple[str|None,tuple[str,...]]:
        q=normalize_stat_text(text)
        expanded=STAT_ALIASES.get(q,q)
        by_norm={normalize_stat_text(x):x for x in self.repository.list_stat_names()}
        exact=by_norm.get(normalize_stat_text(expanded))
        if exact:return exact,()
        if q in {'crit','crt'}:
            choices=tuple(x for x in ('Critical Rate','Critical Damage') if normalize_stat_text(x) in by_norm)
            return None,choices
        best=None; score=0
        for name in self.repository.list_stat_names():
            s=float(fuzz.WRatio(expanded,normalize_stat_text(name)))
            if s>score: best,score=name,s
        return (best,()) if best and score>=88 else (None,())
    def search(self,query:str)->ItemSearchOutcome:
        raw=' '.join(str(query).split())
        if not raw:return ItemSearchOutcome('not_found',raw,message='Enter an item name or stat query.')
        q=raw.casefold().strip(' ?!.')
        if q in {'help','how to search','search help','how do i search','how to use'}:
            return ItemSearchOutcome('help',raw,message=_HELP)
        if _SUBJECTIVE.search(raw):
            return ItemSearchOutcome('refuse',raw,message='This search only compares objective database fields; subjective build/tank/DPS recommendations are not supported.')
        if q in {'list stats','what stats are in the database','what stats can i search'}:
            stats=self.repository.list_stat_names(); return ItemSearchOutcome('meta',raw,message='Stats in the database: '+', '.join(stats))
        if q in {'list item types','what item types are in the database'}:
            return ItemSearchOutcome('meta',raw,message='Item types: '+', '.join(sorted(self.repository.list_item_types())))
        if q in {'how many items are there','how many items are in the database','total item count'}:
            return ItemSearchOutcome('meta',raw,message=f'{self.repository.count_items_total()} items are in the database.')
        if q.startswith('upgrade '):
            target=raw[8:].strip(); exact=self.repository.exact_upgrade_name_matches(target)
            if exact:
                item=exact[0]; return ItemSearchOutcome('results',raw,(ItemCardResult(item),))
            fuzzy=[r for r in self.repository.fuzzy_items(target) if 'crysta' in r[0].item_type.casefold()]
            if fuzzy:return ItemSearchOutcome('results',raw,tuple(ItemCardResult(i,score=s,match_kind=k) for i,s,k in fuzzy))
            return ItemSearchOutcome('not_found',raw,message='No matching crysta found.')
        exact=self.repository.exact_name_matches(raw)
        if exact:return ItemSearchOutcome('results',raw,tuple(ItemCardResult(x,score=100,match_kind='exact') for x in exact))

        item_filter, remaining = extract_item_filter(raw,self.repository.list_item_types())
        remaining_norm=normalize_stat_text(remaining)
        negative_stat = bool(re.search(r'(^|\s)-\s*[A-Za-z_]', raw))
        rank_direction: str | None = None
        rank_match = re.match(r'^(highest|best|lowest|least)\s+(.+)$', remaining_norm, flags=re.I)
        if rank_match:
            rank_direction = 'asc' if rank_match.group(1).casefold() in {'lowest', 'least'} else 'desc'
            remaining_norm = rank_match.group(2).strip()
        stat_hits=[]
        tokens=remaining_norm.split()
        search_terms = tuple(STAT_ALIASES) + ('crit', 'crt')
        for alias in sorted(search_terms, key=lambda x: len(x.split()), reverse=True):
            if all(t in tokens for t in alias.split()):
                stat_hits.append(alias)
        if len(stat_hits)>=2 and not re.search(r"(>=|<=|==|>|<|=)|\b(and|or)\b",remaining_norm):
            filter_text=item_filter.consumed_text if item_filter else ''
            suggested=' and '.join(dict.fromkeys(stat_hits)) + (f' {filter_text}' if filter_text else '')
            return ItemSearchOutcome('suggest',raw,message=f'I could not safely parse "{raw}".',suggested_queries=(suggested.strip(),))

        looks_expression=bool(re.search(r"(>=|<=|==|>|<|=)|\b(and|or)\b",raw, re.I))
        stat, choices=self._resolve_stat(remaining_norm)
        if choices:
            return ItemSearchOutcome('clarify',raw,message='Choose a stat: '+', '.join(choices),suggested_queries=tuple(f'{c} {item_filter.consumed_text if item_filter else ""}'.strip() for c in choices))
        if stat and not looks_expression:
            rows=self.repository.search_stat(stat,item_filter.item_types if item_filter else None)
            if negative_stat:
                rows=[row for row in rows if row[1].amount <= -1]
                rows.sort(key=lambda row: (row[1].amount, row[0].name.casefold(), row[0].id))
            elif rank_direction == 'asc':
                rows.sort(key=lambda row: (row[1].amount, row[0].name.casefold(), row[0].id))
            return ItemSearchOutcome('results' if rows else 'not_found',raw,tuple(ItemCardResult(i,(m,)) for i,m in rows),None if rows else 'No matching items found.')
        if looks_expression:
            try: expr=parse_stat_expression(raw,self.repository.list_item_types(),self.repository.list_stat_names())
            except StatQuerySyntaxError as exc: return ItemSearchOutcome('suggest',raw,message=str(exc))
            known={normalize_stat_text(x) for x in self.repository.list_stat_names()}
            unknown=[c.typed_stat for g in expr.groups for c in g.clauses if normalize_stat_text(c.typed_stat) not in known]
            if unknown:return ItemSearchOutcome('suggest',raw,message='Unknown stat: '+unknown[0])
            rows=self.repository.search_expression(expr)
            return ItemSearchOutcome('results' if rows else 'not_found',raw,tuple(ItemCardResult(i,m) for i,m,_ in rows),None if rows else 'No matching items found.')
        ranked=self.repository.fuzzy_items(raw)
        if ranked:return ItemSearchOutcome('results',raw,tuple(ItemCardResult(i,score=s,match_kind=k) for i,s,k in ranked))
        return ItemSearchOutcome('not_found',raw,message='No matching item or stat found.')

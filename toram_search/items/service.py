from __future__ import annotations
import re
from pathlib import Path
from rapidfuzz import fuzz

from toram_search.interpretation import RouteQuality
from .aliases import STAT_ALIASES, normalize_stat_text
from .filters import extract_item_filter
from .interpretation import build_expression_item_interpretation, build_simple_item_interpretation
from .models import ItemCardResult, ItemSearchOutcome
from .repository import ItemRepository
from .stat_query import StatQuerySyntaxError, parse_stat_expression

_HELP = "Search by item name, stat, item type, numeric comparisons, AND/OR, or upgrade relationships. Use upgrade <crysta name> to show the full crysta upgrade chain from first to last. Examples: cr xtal; hp >= 5000 armor; hp > 5000 and cr bow; upgrade Iconos."
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
            s=float(fuzz.ratio(expanded,normalize_stat_text(name)))
            if s>score: best,score=name,s
        return (best,()) if best and score>=88 else (None,())
    @staticmethod
    def _group_stat_rows(rows):
        grouped={}
        order=[]
        for item,match in rows:
            if item.id not in grouped:
                grouped[item.id]=[item,[]]
                order.append(item.id)
            grouped[item.id][1].append(match)
        return tuple(ItemCardResult(grouped[item_id][0],tuple(grouped[item_id][1])) for item_id in order)
    def _upgrade_chain(self,item):
        nodes={}
        edges={}
        pending=[item]
        while pending:
            current=pending.pop()
            if current.id in nodes:
                continue
            nodes[current.id]=current
            for predecessor in self.repository.get_upgrade_predecessors(current.id):
                edges.setdefault(predecessor.id,set()).add(current.id)
                pending.append(predecessor)
            for successor in self.repository.get_upgrade_successors(current.id):
                edges.setdefault(current.id,set()).add(successor.id)
                pending.append(successor)
        indegree={item_id:0 for item_id in nodes}
        for successors in edges.values():
            for successor_id in successors:
                if successor_id in indegree:
                    indegree[successor_id]+=1
        key=lambda x:(x.name.casefold(),x.id)
        ready=sorted((nodes[item_id] for item_id,degree in indegree.items() if degree==0),key=key)
        ordered=[]
        emitted=set()
        while ready:
            current=ready.pop(0)
            if current.id in emitted:
                continue
            emitted.add(current.id)
            ordered.append(current)
            for successor_id in sorted(edges.get(current.id,()),key=lambda item_id:key(nodes[item_id])):
                if successor_id not in indegree:
                    continue
                indegree[successor_id]-=1
                if indegree[successor_id]==0:
                    ready.append(nodes[successor_id])
                    ready.sort(key=key)
        if len(emitted)<len(nodes):
            ordered.extend(sorted((row for item_id,row in nodes.items() if item_id not in emitted),key=key))
        return tuple(ordered)
    def search(self,query:str)->ItemSearchOutcome:
        raw=' '.join(str(query).split())

        def finish(
            kind,
            results=(),
            message=None,
            suggested_queries=(),
            routing_confidence='none',
            family='none',
            specificity=0,
            interpretation=None,
        ):
            return ItemSearchOutcome(
                kind,
                raw,
                results,
                message,
                suggested_queries,
                routing_confidence,
                interpretation,
                RouteQuality(family, bool(results), specificity),
            )

        if not raw:return finish('not_found',message='Enter an item name or stat query.')
        q=raw.casefold().strip(' ?!.')
        if q in {'help','how to search','search help','how do i search','how to use'}:
            return finish('help',message=_HELP,routing_confidence='strong',family='structured')
        if _SUBJECTIVE.search(raw):
            return finish('refuse',message='This search only compares objective database fields; subjective build/tank/DPS recommendations are not supported.',routing_confidence='strong',family='structured')
        if q in {'list stats','what stats are in the database','what stats can i search'}:
            stats=self.repository.list_stat_names(); return finish('meta',message='Stats in the database: '+', '.join(stats),routing_confidence='strong',family='structured')
        if q in {'list item types','what item types are in the database'}:
            return finish('meta',message='Item types: '+', '.join(sorted(self.repository.list_item_types())),routing_confidence='strong',family='structured')
        if q in {'how many items are there','how many items are in the database','total item count'}:
            return finish('meta',message=f'{self.repository.count_items_total()} items are in the database.',routing_confidence='strong',family='structured')
        if q.startswith('upgrade '):
            target=raw[8:].strip(); exact=self.repository.exact_upgrade_name_matches(target)
            if exact:
                chain=self._upgrade_chain(exact[0])
                return finish('results',tuple(ItemCardResult(item,match_kind='upgrade') for item in chain),routing_confidence='strong',family='exact',specificity=1)
            fuzzy=[r for r in self.repository.fuzzy_items(target) if 'crysta' in r[0].item_type.casefold()]
            prefix_chains=[]
            for item,_score,match_kind in fuzzy:
                if match_kind!='prefix':
                    continue
                chain=self._upgrade_chain(item)
                if len(chain)>1:
                    prefix_chains.append(chain)
            if len(prefix_chains)==1:
                chain=prefix_chains[0]
                return finish('results',tuple(ItemCardResult(item,match_kind='upgrade') for item in chain),routing_confidence='strong',family='structured',specificity=1)
            if fuzzy:return finish('results',tuple(ItemCardResult(i,score=s,match_kind=k) for i,s,k in fuzzy),routing_confidence='strong',family='structured',specificity=1)
            return finish('not_found',message='No matching crysta found.',routing_confidence='strong',family='structured',specificity=1)
        exact=self.repository.exact_name_matches(raw)
        if exact:return finish('results',tuple(ItemCardResult(x,score=100,match_kind='exact') for x in exact),routing_confidence='strong',family='exact',specificity=1)

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
            specificity=max(1,len(tuple(dict.fromkeys(stat_hits))) + int(item_filter is not None))
            return finish('suggest',message=f'I could not safely parse "{raw}".',suggested_queries=(suggested.strip(),),routing_confidence='strong',family='structured',specificity=specificity)

        looks_expression=bool(re.search(r"(>=|<=|==|>|<|=)|\b(and|or)\b",raw, re.I))
        stat, choices=self._resolve_stat(remaining_norm)
        recognized_structured_intent=bool(item_filter is not None or rank_direction is not None or looks_expression or stat is not None or choices or stat_hits)
        if choices:
            return finish(
                'clarify',
                message='Choose a stat: '+', '.join(choices),
                suggested_queries=tuple(f'{c} {item_filter.consumed_text if item_filter else ""}'.strip() for c in choices),
                routing_confidence='strong',
                family='structured',
                specificity=1 + int(item_filter is not None),
            )
        if stat and not looks_expression:
            rows=self.repository.search_stat(stat,item_filter.item_types if item_filter else None)
            if negative_stat:
                rows=[row for row in rows if row[1].amount <= -1]
                rows.sort(key=lambda row: (row[1].amount, row[0].name.casefold(), row[0].id))
            elif rank_direction == 'asc':
                rows.sort(key=lambda row: (row[1].amount, row[0].name.casefold(), row[0].id))
            cards=self._group_stat_rows(rows)
            interpretation=build_simple_item_interpretation(stat,item_filter,rank_direction,negative_stat)
            specificity=1 + int(item_filter is not None) + int(rank_direction is not None)
            return finish(
                'results' if cards else 'not_found',
                cards,
                None if cards else 'No matching items found.',
                routing_confidence='strong',
                family='structured',
                specificity=specificity,
                interpretation=interpretation,
            )
        if looks_expression:
            try: expr=parse_stat_expression(raw,self.repository.list_item_types(),self.repository.list_stat_names())
            except StatQuerySyntaxError as exc:
                return finish('suggest',message=str(exc),routing_confidence='strong',family='structured',specificity=1 + int(item_filter is not None))
            known={normalize_stat_text(x) for x in self.repository.list_stat_names()}
            unknown=[c.typed_stat for g in expr.groups for c in g.clauses if normalize_stat_text(c.typed_stat) not in known]
            if unknown:
                return finish('suggest',message='Unknown stat: '+unknown[0],routing_confidence='strong',family='structured',specificity=max(1,sum(len(g.clauses) for g in expr.groups) + int(expr.item_filter is not None)))
            rows=self.repository.search_expression(expr)
            cards=tuple(ItemCardResult(i,m) for i,m,_score in rows)
            clause_count=sum(len(group.clauses) for group in expr.groups)
            specificity=clause_count + int(expr.item_filter is not None)
            return finish(
                'results' if cards else 'not_found',
                cards,
                None if cards else 'No matching items found.',
                routing_confidence='strong',
                family='structured',
                specificity=specificity,
                interpretation=build_expression_item_interpretation(expr),
            )
        if recognized_structured_intent:
            specificity=max(1,int(item_filter is not None) + int(rank_direction is not None) + int(stat is not None) + len(stat_hits))
            alias_only_partial=bool(stat_hits) and item_filter is None and rank_direction is None and stat is None
            return finish(
                'suggest',
                message=f'I could not safely parse "{raw}".',
                routing_confidence='none' if alias_only_partial else 'strong',
                family='none' if alias_only_partial else 'structured',
                specificity=0 if alias_only_partial else specificity,
            )
        ranked=self.repository.fuzzy_items(raw)
        if ranked:return finish('results',tuple(ItemCardResult(i,score=s,match_kind=k) for i,s,k in ranked),routing_confidence='weak',family='weak')
        return finish('not_found',message='No matching item or stat found.')

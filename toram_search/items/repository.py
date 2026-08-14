from __future__ import annotations
from pathlib import Path
from typing import Any
from rapidfuzz import fuzz
from toram_search.database import connect_readonly
from .aliases import is_crysta_item_type, normalize_name, normalize_stat_text
from .models import ItemDetail, ItemSummary, ItemStatMatch
from .stat_query import compare_amount

class ItemRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.db = connect_readonly(self.database_path)
    def close(self): self.db.close()
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): self.close()
    def list_items(self) -> list[ItemSummary]:
        return [ItemSummary(int(r['id']),str(r['name']),str(r['item_type'])) for r in self.db.execute('SELECT id,name,item_type FROM items ORDER BY name COLLATE NOCASE,id')]
    def list_item_types(self) -> set[str]:
        return {str(r[0]) for r in self.db.execute('SELECT DISTINCT item_type FROM items WHERE item_type IS NOT NULL')}
    def list_stat_names(self) -> list[str]:
        return [str(r[0]) for r in self.db.execute("SELECT DISTINCT stat_name FROM item_stats WHERE stat_name <> 'Upgrade for' ORDER BY stat_name COLLATE NOCASE")]
    def count_items_total(self) -> int: return int(self.db.execute('SELECT COUNT(*) FROM items').fetchone()[0])
    def count_items_by_types(self, item_types: tuple[str,...]) -> int:
        if not item_types: return 0
        ph=','.join('?'*len(item_types)); return int(self.db.execute(f'SELECT COUNT(*) FROM items WHERE item_type IN ({ph})',item_types).fetchone()[0])
    def count_items_with_stat(self, stat_name: str) -> int:
        return int(self.db.execute("SELECT COUNT(DISTINCT item_id) FROM item_stats WHERE stat_name=? AND stat_name<>'Upgrade for'",(stat_name,)).fetchone()[0])
    def exact_name_matches(self, query: str) -> list[ItemSummary]:
        q=normalize_name(query); return [x for x in self.list_items() if normalize_name(x.name)==q]
    def exact_upgrade_name_matches(self, query: str) -> list[ItemSummary]:
        return [x for x in self.exact_name_matches(query) if is_crysta_item_type(x.item_type)]
    def fuzzy_items(self, query: str, limit: int=50) -> list[tuple[ItemSummary,float,str]]:
        q=normalize_name(query); out=[]
        if len(q)<2: return []
        for item in self.list_items():
            n=normalize_name(item.name)
            score=max(float(fuzz.WRatio(q,n)),float(fuzz.token_set_ratio(q,n)))
            kind='fuzzy'
            if n==q: score,kind=100,'exact'
            elif n.startswith(q): score,kind=max(score,98),'prefix'
            elif q in n: score,kind=max(score,95),'substring'
            if score>=70: out.append((item,score,kind))
        out.sort(key=lambda x:(-x[1],len(normalize_name(x[0].name)),normalize_name(x[0].name),x[0].id))
        return out[:limit]
    def _summary(self,item_id:int)->ItemSummary|None:
        r=self.db.execute('SELECT id,name,item_type FROM items WHERE id=?',(item_id,)).fetchone()
        return None if r is None else ItemSummary(int(r['id']),str(r['name']),str(r['item_type']))
    def _upgrade_predecessor_ids(self,item_id:int)->list[int]:
        out=[]
        for r in self.db.execute("SELECT amount FROM item_stats WHERE item_id=? AND stat_name='Upgrade for' ORDER BY position,id",(item_id,)):
            try: v=float(r['amount'])
            except (TypeError,ValueError): continue
            if v.is_integer() and v>0 and int(v) not in out: out.append(int(v))
        return out
    def get_upgrade_predecessors(self,item_id:int)->tuple[ItemSummary,...]:
        rows=[]
        for pid in self._upgrade_predecessor_ids(item_id): rows.append(self._summary(pid) or ItemSummary(pid,'Unknown item','Unknown'))
        return tuple(sorted(rows,key=lambda x:(x.name.casefold(),x.id)))
    def get_upgrade_successors(self,item_id:int)->tuple[ItemSummary,...]:
        rows=[]
        for r in self.db.execute("SELECT i.id,i.name,i.item_type,s.amount FROM item_stats s JOIN items i ON i.id=s.item_id WHERE s.stat_name='Upgrade for'"):
            try: v=float(r['amount'])
            except (TypeError,ValueError): continue
            if v.is_integer() and int(v)==item_id: rows.append(ItemSummary(int(r['id']),str(r['name']),str(r['item_type'])))
        return tuple(sorted(rows,key=lambda x:(x.name.casefold(),x.id)))
    def get_item(self,item_id:int)->ItemDetail:
        r=self.db.execute('SELECT id,name,item_type,sell_price,process_material,process_amount,badge,note,page_url FROM items WHERE id=?',(item_id,)).fetchone()
        if r is None: raise KeyError(item_id)
        stats=tuple(dict(x) for x in self.db.execute("SELECT stat_name,amount,conditions_json,condition_text,coryn_applies_to,needs_condition_review FROM item_stats WHERE item_id=? AND stat_name<>'Upgrade for' ORDER BY position,id",(item_id,)))
        sources=tuple(dict(x) for x in self.db.execute('SELECT source_id,source_name,level,map,dye,source_url,lookup_error FROM item_sources WHERE item_id=? ORDER BY position,id',(item_id,)))
        images=tuple(dict(x) for x in self.db.execute('SELECT category,gender,variant,local_path,source_url FROM item_images WHERE item_id=? ORDER BY position,id',(item_id,)))
        return ItemDetail(ItemSummary(int(r['id']),str(r['name']),str(r['item_type'])),r['sell_price'],r['process_material'],r['process_amount'],r['badge'],r['note'],r['page_url'],stats,sources,images,self.get_upgrade_predecessors(item_id),self.get_upgrade_successors(item_id))
    def search_stat(self, stat_name:str, item_types:tuple[str,...]|None=None) -> list[tuple[ItemSummary,ItemStatMatch]]:
        params: list[Any] = [stat_name]; sql="SELECT i.id,i.name,i.item_type,s.stat_name,s.amount,s.condition_text FROM item_stats s JOIN items i ON i.id=s.item_id WHERE s.stat_name=? AND s.amount IS NOT NULL"
        if item_types:
            ph=','.join('?'*len(item_types)); sql += f' AND i.item_type IN ({ph})'; params.extend(item_types)
        sql += ' ORDER BY s.amount DESC,i.name COLLATE NOCASE,i.id'
        return [(ItemSummary(int(r['id']),str(r['name']),str(r['item_type'])),ItemStatMatch(str(r['stat_name']),float(r['amount']),r['condition_text'])) for r in self.db.execute(sql,tuple(params))]
    def search_expression(self, expression) -> list[tuple[ItemSummary,tuple[ItemStatMatch,...],float|None]]:
        item_types = expression.item_filter.item_types if expression.item_filter is not None else None
        candidates = self.list_items()
        if item_types: candidates=[x for x in candidates if x.item_type in item_types]
        results=[]
        for item in candidates:
            stat_rows={}
            for r in self.db.execute("SELECT stat_name,amount,condition_text FROM item_stats WHERE item_id=? AND stat_name<>'Upgrade for' AND amount IS NOT NULL",(item.id,)):
                stat_rows.setdefault(normalize_stat_text(str(r['stat_name'])),[]).append(r)
            group_matches=[]
            for group in expression.groups:
                matched=[]; ok=True
                for clause in group.clauses:
                    rows=stat_rows.get(normalize_stat_text(clause.typed_stat),[])
                    good=[r for r in rows if compare_amount(float(r['amount']),clause.operator,clause.value)]
                    if not good: ok=False; break
                    matched.extend(ItemStatMatch(str(r['stat_name']),float(r['amount']),r['condition_text']) for r in good)
                if ok: group_matches.extend(matched)
            if group_matches:
                results.append((item,tuple(group_matches),group_matches[0].amount if group_matches else None))
        results.sort(key=lambda x:(-(x[2] or 0),x[0].name.casefold(),x[0].id))
        return results

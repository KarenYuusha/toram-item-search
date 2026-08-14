from __future__ import annotations
import re
from pathlib import Path
from rapidfuzz import fuzz

from toram_search.interpretation import RouteQuality
from .analytics import SkillAnalytics
from .concepts import resolve_ailment
from .interpretation import build_skill_interpretation
from .lexical_search import lexical_search
from .models import SkillCardResult, SkillFilter, SkillSearchOutcome
from .normalization import normalize_skill_name
from .repository import SkillRepository

_SUBJECTIVE=re.compile(r'\b(?:best|strongest|highest dps|most damage)\b.*\b(?:dps|tank|build|mage|skill)\b',re.I)

class SkillSearchService:
    def __init__(self,database_path:Path): self.repository=SkillRepository(database_path);self.analytics=SkillAnalytics(self.repository)
    def close(self): self.repository.close()
    def get_skill(self,skill_id:str)->SkillCardResult:
        s=self.repository.get_skill(skill_id);return SkillCardResult(s,self.repository.get_tree(s.tree_id).name)
    def list_autocomplete_values(self):
        rows=[(x,'Skill') for x in self.repository.list_skill_names()]
        rows += [(x,'Skill Tree') for x in self.repository.list_tree_names()]
        rows += [(x,'Ailment') for x in self.repository.list_known_ailments()]
        return tuple(rows)
    def _cards(self,skills,field=None):
        out=[]
        for s in skills:
            value=None
            if field:
                v=getattr(s,field,None);value=str(v) if v is not None else None
            out.append(SkillCardResult(s,self.repository.get_tree(s.tree_id).name,field,value))
        return tuple(out)
    def _find_skill_phrases(self,query:str):
        norm=normalize_skill_name(re.sub(r'[?!.]+$','',query))
        matches=[]
        for s in self.repository.all_skills():
            for phrase in (s.name,*s.aliases):
                n=normalize_skill_name(phrase)
                if f' {n} ' in f' {norm} ':
                    matches.append((norm.find(n),-len(n),s));break
        matches.sort(key=lambda x:(x[0],x[1],x[2].id));seen=[]
        for _,_,s in matches:
            if s.id not in {x.id for x in seen}:seen.append(s)
        return tuple(seen)
    def _tree_id_from_query(self, norm: str) -> str | None:
        for tree_name in self.repository.list_tree_names():
            tree=self.repository.resolve_tree_name(tree_name)[0]
            tn=normalize_skill_name(tree.name)
            short=tn[:-7].strip() if tn.endswith(' skills') else tn
            if tn in norm or f'{short} skill tree' in norm or f'{short} skills tree' in norm or f' {short} skills ' in f' {norm} ':
                return tree.id
        return None
    def _structured_filter_from_query(self, norm: str) -> SkillFilter:
        tree_id=self._tree_id_from_query(norm)
        tier_match=re.search(r'\btier\s+([1-5])\b', norm)
        skill_type=None
        for candidate in self.repository.list_skill_types():
            if f' {normalize_skill_name(candidate)} ' in f' {norm} ':
                skill_type=candidate
                break
        mp_match=re.search(r'\bmp(?:\s+cost)?\s*(?:<=|under|below|at most)\s*(\d+)\b', norm)
        level_match=re.search(r'\brequired\s+level\s*(?:<=|under|below|at most)\s*(\d+)\b', norm)
        ailment=None
        for known in self.repository.list_known_ailments():
            if f' {normalize_skill_name(known)} ' in f' {norm} ':
                ailment=resolve_ailment(known,self.repository.list_known_ailments()) or known
                break
        return SkillFilter(
            tree_ids=(tree_id,) if tree_id else (),
            tiers=(int(tier_match.group(1)),) if tier_match else (),
            skill_types=(skill_type,) if skill_type else (),
            ailments=(ailment,) if ailment and any(w in norm for w in ('inflict','inflicts','cause','causes','ailment')) else (),
            mp_cost_max=int(mp_match.group(1)) if mp_match else None,
            required_level_max=int(level_match.group(1)) if level_match else None,
        )
    def _stored_detail(self,s):
        bits=[]
        if s.description:bits.append(s.description)
        if s.game_description:bits.append(s.game_description)
        bits.extend(sec.body for sec in s.sections if sec.body)
        if not bits and s.raw_text:bits.append(s.raw_text)
        return '\n\n'.join(bits)
    def search(self,query:str,*,allow_weak_fallback:bool=True)->SkillSearchOutcome:
        raw=' '.join(str(query).split());norm=normalize_skill_name(raw.strip(' ?!.'))

        def finish(
            kind,
            results=(),
            message=None,
            suggested_queries=(),
            family='none',
            specificity=0,
            interpretation=None,
        ):
            return SkillSearchOutcome(
                kind,
                raw,
                results,
                message,
                suggested_queries,
                interpretation,
                RouteQuality(family, bool(results), specificity),
            )

        if not raw:return finish('not_found',message='Enter a skill, tree, ailment, or objective skill query.')
        if _SUBJECTIVE.search(raw):return finish('refuse',message='This search compares objective database facts only; subjective DPS/tank/build recommendations are not supported.',family='structured')
        skills=self._find_skill_phrases(raw)
        if len(skills)>=2 and norm.startswith('compare '):
            a,b=skills[:2]
            msg=(f'{a.name} vs {b.name}\nTree: {self.repository.get_tree(a.tree_id).name} | {self.repository.get_tree(b.tree_id).name}\n'
                 f'Tier: {a.tier} | {b.tier}\nRequired Level: {a.required_level} | {b.required_level}\nMP: {a.mp_cost_text or "not recorded"} | {b.mp_cost_text or "not recorded"}\n'
                 f'Type: {a.skill_type or "not recorded"} | {b.skill_type or "not recorded"}')
            return finish('compare',self._cards((a,b)),msg,family='exact',specificity=2)
        if len(skills)==1:
            s=skills[0]
            if 'mp cost' in norm:return finish('structured',self._cards((s,),'mp_cost_value'),f'{s.name}: MP {s.mp_cost_text or "not recorded"}',family='exact',specificity=1)
            if 'what tree' in norm:return finish('structured',self._cards((s,)),f'{s.name} is in {self.repository.get_tree(s.tree_id).name}.',family='exact',specificity=1)
            if 'what tier' in norm:return finish('structured',self._cards((s,),'tier'),f'{s.name}: Tier {s.tier if s.tier is not None else "not recorded"}',family='exact',specificity=1)
            if (norm.startswith('how does ') and norm.endswith(' work')) or (norm.startswith('what does ') and norm.endswith(' do')):
                return finish('structured',self._cards((s,)),self._stored_detail(s),family='exact',specificity=1)
            if norm in {normalize_skill_name(s.name),*(normalize_skill_name(a) for a in s.aliases)}:
                return finish('results',self._cards((s,)),family='exact',specificity=1)
        structured_filter=self._structured_filter_from_query(norm)
        has_explicit_filter=bool(structured_filter.tiers or structured_filter.skill_types or structured_filter.ailments or structured_filter.mp_cost_max is not None or structured_filter.required_level_max is not None)
        if has_explicit_filter:
            rows=self.analytics.filter_skills(structured_filter)
            unsupported=bool(structured_filter.tiers or structured_filter.skill_types or structured_filter.weapons)
            tree_name=None
            if structured_filter.tree_ids:
                tree_name=self.repository.get_tree(structured_filter.tree_ids[0]).name
            interpretation=build_skill_interpretation(
                tree_name=tree_name,
                ailment=structured_filter.ailments[0] if structured_filter.ailments else None,
                mp_cost_max=structured_filter.mp_cost_max,
                required_level_max=structured_filter.required_level_max,
                count_mode=norm.startswith('how many'),
                unsupported_structured_component=unsupported,
            )
            specificity=(
                len(structured_filter.tree_ids)
                + len(structured_filter.tiers)
                + len(structured_filter.skill_types)
                + len(structured_filter.ailments)
                + len(structured_filter.weapons)
                + int(structured_filter.mp_cost_max is not None)
                + int(structured_filter.required_level_max is not None)
            )
            if norm.startswith('how many'):
                return finish('structured',message=f'{len(rows)} skills match those database filters.',family='structured',specificity=specificity,interpretation=interpretation)
            cards=self._cards(rows)
            return finish('results' if cards else 'not_found',cards,None if cards else 'No matching skills found.',family='structured',specificity=specificity,interpretation=interpretation)
        for tree_name in self.repository.list_tree_names():
            tree=self.repository.resolve_tree_name(tree_name)[0];tn=normalize_skill_name(tree.name);short=tn[:-7].strip() if tn.endswith(' skills') else tn
            if norm in {tn,short,f'{short} skill tree',f'{short} skills tree'} or (short in norm and ('skill tree' in norm or 'skills' in norm)):
                rows=self.repository.list_skills_in_tree(tree.id)
                if 'mp' in norm and any(x in norm for x in ('lowest','least','highest')):
                    direction='desc' if 'highest' in norm else 'asc';rows=self.analytics.rank('mp_cost_value',direction,filters=SkillFilter(tree_ids=(tree.id,)),limit=20)
                    interpretation=build_skill_interpretation(tree_name=tree.name,mp_rank_direction=direction)
                    return finish('results',self._cards(rows,'mp_cost_value'),family='structured',specificity=2,interpretation=interpretation)
                cards=self._cards(rows)
                return finish('results' if cards else 'not_found',cards,None if cards else 'No matching skills found.',family='structured',specificity=1,interpretation=build_skill_interpretation(tree_name=tree.name))
        for ailment in self.repository.list_known_ailments():
            n=normalize_skill_name(ailment)
            if n in norm and any(w in norm for w in ('inflict','inflicts','cause','causes','ailment','skills')):
                canonical=resolve_ailment(ailment,self.repository.list_known_ailments()) or ailment
                rows=self.analytics.filter_skills(SkillFilter(ailments=(canonical,)))
                cards=self._cards(rows,'ailments')
                return finish('results' if cards else 'not_found',cards,None if cards else 'No matching skills found.',family='structured',specificity=1,interpretation=build_skill_interpretation(ailment=canonical))
        if 'mp' in norm and any(w in norm for w in ('lowest','least','highest')):
            direction='desc' if 'highest' in norm else 'asc';rows=self.analytics.rank('mp_cost_value',direction,limit=20)
            cards=self._cards(rows,'mp_cost_value')
            return finish('results' if cards else 'not_found',cards,None if cards else 'No matching skills found.',family='structured',specificity=1,interpretation=build_skill_interpretation(mp_rank_direction=direction))
        exact=self.repository.resolve_skill_name(raw)
        if exact:return finish('results',self._cards(exact),family='exact',specificity=1)
        if not allow_weak_fallback:
            return finish('not_found',message='No matching skill database information found.')
        fuzzy=[]
        for s in self.repository.all_skills():
            score=max(float(fuzz.WRatio(norm,s.normalized_name)),float(fuzz.token_set_ratio(norm,s.normalized_name)))
            if score>=88:fuzzy.append((score,s))
        if fuzzy:
            fuzzy.sort(key=lambda x:(-x[0],x[1].normalized_name,x[1].id));return finish('results',self._cards(tuple(s for _,s in fuzzy[:20])),family='weak')
        hits=lexical_search(self.repository,raw,limit=20)
        if hits:return finish('results',self._cards(tuple(self.repository.get_skill(h.skill_id) for h in hits)),family='weak')
        return finish('not_found',message='No matching skill database information found.')

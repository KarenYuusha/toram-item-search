from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from toram_search.database import FOOD_ALIASES, FOOD_ENTRIES, REGISTLET_DATA
from toram_search.food.service import FoodSearchService, is_food_intent
from toram_search.interpretation import QueryInterpretation, RouteQuality, SearchDomain
from toram_search.items.service import ItemSearchService
from toram_search.models import DatabaseMode, UniversalSearchOutcome
from toram_search.registlets.data import load_registlet_dataset
from toram_search.registlets.relationships import build_relationship_index
from toram_search.registlets.service import RegistletSearchService, is_stoodie_intent
from toram_search.skills.repository import SkillRepository
from toram_search.skills.service import SkillSearchService

_ALL_DOMAINS: frozenset[SearchDomain] = frozenset({'Items', 'Skills', 'Food', 'Registlets'})
_DOMAIN_ORDER: tuple[SearchDomain, ...] = ('Items', 'Skills', 'Food', 'Registlets')


def _search_items(query: str, path: Path):
    service = ItemSearchService(path)
    try:
        return service.search(query)
    finally:
        service.close()


def _search_skills(query: str, path: Path):
    service = SkillSearchService(path)
    try:
        return service.search(query, allow_weak_fallback=True)
    finally:
        service.close()


def _search_food(query: str, entries_path: Path, aliases_path: Path):
    return FoodSearchService(entries_path, aliases_path).search(query)


def _search_registlets(query: str, path: Path):
    return RegistletSearchService(path).search(query)


def select_surviving_domains(
    qualities: dict[SearchDomain, RouteQuality],
) -> frozenset[SearchDomain]:
    if not qualities:
        return frozenset()
    best = max(quality.sort_key for quality in qualities.values())
    return frozenset(
        domain for domain, quality in qualities.items() if quality.sort_key == best
    )


def select_winning_interpretation(*outcomes) -> QueryInterpretation | None:
    candidates = [
        (outcome.route_quality.sort_key, -priority, outcome)
        for priority, outcome in enumerate(outcomes)
        if outcome is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: (row[0], row[1]))[2].interpretation


def _suppress_outcome(domain: SearchDomain, outcome):
    if outcome is None:
        return None
    common = {
        'kind': 'not_found',
        'results': (),
        'message': None,
        'suggested_queries': (),
        'interpretation': None,
    }
    if domain == 'Items':
        return replace(outcome, routing_confidence='none', **common)
    if domain == 'Registlets':
        return replace(outcome, match=None, **common)
    return replace(outcome, **common)


def _enrich_skill_relationships(skills, *, skills_path: Path, registlets_path: Path):
    if skills is None or not skills.results:
        return skills
    dataset = load_registlet_dataset(registlets_path)
    with SkillRepository(skills_path) as repository:
        canonical_names = repository.list_skill_names()
    index = build_relationship_index(dataset.records, canonical_names)
    enriched = tuple(
        replace(
            card,
            related_registlets=index.by_skill.get(card.skill.name.casefold(), ()),
        )
        for card in skills.results
    )
    return replace(skills, results=enriched)


def _search_available_domains(
    query: str,
    *,
    available: frozenset[SearchDomain],
    items_path: Path,
    skills_path: Path,
    food_entries_path: Path,
    food_aliases_path: Path,
    registlets_path: Path,
):
    items = _search_items(query, items_path) if 'Items' in available else None
    skills = _search_skills(query, skills_path) if 'Skills' in available else None
    food = (
        _search_food(query, food_entries_path, food_aliases_path)
        if 'Food' in available
        else None
    )
    registlets = (
        _search_registlets(query, registlets_path)
        if 'Registlets' in available
        else None
    )
    if skills is not None and 'Registlets' in available:
        skills = _enrich_skill_relationships(
            skills,
            skills_path=skills_path,
            registlets_path=registlets_path,
        )
    return items, skills, food, registlets


def search_database(
    mode: DatabaseMode,
    query: str,
    *,
    items_path: Path,
    skills_path: Path,
    food_entries_path: Path = FOOD_ENTRIES,
    food_aliases_path: Path = FOOD_ALIASES,
    registlets_path: Path = REGISTLET_DATA,
    available_domains: frozenset[SearchDomain] | None = None,
) -> UniversalSearchOutcome:
    available = available_domains if available_domains is not None else _ALL_DOMAINS

    if mode == 'Items':
        items = _search_items(query, items_path) if 'Items' in available else None
        return UniversalSearchOutcome(
            query=query,
            items=items,
            interpretation=items.interpretation if items is not None else None,
        )

    if mode == 'Skills':
        skills = _search_skills(query, skills_path) if 'Skills' in available else None
        if skills is not None and 'Registlets' in available:
            skills = _enrich_skill_relationships(
                skills,
                skills_path=skills_path,
                registlets_path=registlets_path,
            )
        return UniversalSearchOutcome(
            query=query,
            skills=skills,
            interpretation=skills.interpretation if skills is not None else None,
        )

    if mode == 'Food':
        food = (
            _search_food(query, food_entries_path, food_aliases_path)
            if 'Food' in available
            else None
        )
        return UniversalSearchOutcome(
            query=query,
            food=food,
            interpretation=food.interpretation if food is not None else None,
        )

    if mode == 'Registlets':
        registlets = (
            _search_registlets(query, registlets_path)
            if 'Registlets' in available
            else None
        )
        return UniversalSearchOutcome(
            query=query,
            registlets=registlets,
            interpretation=registlets.interpretation if registlets is not None else None,
        )

    items, skills, food, registlets = _search_available_domains(
        query,
        available=available,
        items_path=items_path,
        skills_path=skills_path,
        food_entries_path=food_entries_path,
        food_aliases_path=food_aliases_path,
        registlets_path=registlets_path,
    )

    blocked_explicit_intent = (
        ('Food' not in available and is_food_intent(query))
        or ('Registlets' not in available and is_stoodie_intent(query))
    )
    if blocked_explicit_intent:
        items = _suppress_outcome('Items', items)
        skills = _suppress_outcome('Skills', skills)
        food = _suppress_outcome('Food', food)
        registlets = _suppress_outcome('Registlets', registlets)
        return UniversalSearchOutcome(
            query=query,
            items=items,
            skills=skills,
            food=food,
            registlets=registlets,
        )

    raw_outcomes = {
        'Items': items,
        'Skills': skills,
        'Food': food,
        'Registlets': registlets,
    }
    qualities = {
        domain: outcome.route_quality
        for domain, outcome in raw_outcomes.items()
        if outcome is not None
    }
    survivors = select_surviving_domains(qualities)
    interpretation = select_winning_interpretation(items, skills, food, registlets)

    suppressed = {}
    for domain in _DOMAIN_ORDER:
        outcome = raw_outcomes[domain]
        suppressed[domain] = (
            outcome if domain in survivors else _suppress_outcome(domain, outcome)
        )

    return UniversalSearchOutcome(
        query=query,
        items=suppressed['Items'],
        skills=suppressed['Skills'],
        food=suppressed['Food'],
        registlets=suppressed['Registlets'],
        interpretation=interpretation,
    )

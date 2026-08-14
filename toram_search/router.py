from __future__ import annotations

from pathlib import Path

from toram_search.items.service import ItemSearchService
from toram_search.models import DatabaseMode, UniversalSearchOutcome
from toram_search.skills.service import SkillSearchService


def _search_items(query: str, path: Path):
    service = ItemSearchService(path)
    try:
        return service.search(query)
    finally:
        service.close()


def _search_skills(query: str, path: Path, *, allow_weak_fallback: bool = True):
    service = SkillSearchService(path)
    try:
        return service.search(query, allow_weak_fallback=allow_weak_fallback)
    finally:
        service.close()


def select_winning_interpretation(items, skills):
    candidates = []
    if items is not None:
        candidates.append((items.route_quality.sort_key, 1, items.interpretation))
    if skills is not None:
        candidates.append((skills.route_quality.sort_key, 0, skills.interpretation))
    if not candidates:
        return None
    return max(candidates, key=lambda row: (row[0], row[1]))[2]


def search_database(
    mode: DatabaseMode,
    query: str,
    *,
    items_path: Path,
    skills_path: Path,
) -> UniversalSearchOutcome:
    if mode == 'Universal':
        items = _search_items(query, items_path)
        skills = _search_skills(
            query,
            skills_path,
            allow_weak_fallback=items.routing_confidence != 'strong',
        )
        return UniversalSearchOutcome(
            query=query,
            items=items,
            skills=skills,
            interpretation=select_winning_interpretation(items, skills),
        )
    if mode == 'Items':
        items = _search_items(query, items_path)
        return UniversalSearchOutcome(query=query, items=items, interpretation=items.interpretation)
    skills = _search_skills(query, skills_path)
    return UniversalSearchOutcome(query=query, skills=skills, interpretation=skills.interpretation)

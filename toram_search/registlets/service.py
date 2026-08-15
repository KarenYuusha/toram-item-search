from __future__ import annotations

import re
from pathlib import Path

from rapidfuzz import fuzz

from toram_search.interpretation import QueryChip, QueryInterpretation, RouteQuality
from .data import load_registlet_dataset
from .models import RegistletMatch, RegistletRecord, RegistletSearchOutcome

_STOODIE_INTENT = re.compile(r'^\s*(?:std|stoodie)(?:\s+|$)', re.IGNORECASE)
_STOODIE_QUERY = re.compile(
    r'^\s*(?:std|stoodie)\s+(?:(?:lv|lvl|level)\s*)?(\d+)\s*$',
    re.IGNORECASE,
)
_WORD = re.compile(r'[a-z0-9]+', re.IGNORECASE)


def is_stoodie_intent(query: str) -> bool:
    return _STOODIE_INTENT.match(str(query)) is not None


def _normalize_name(value: str) -> str:
    return ' '.join(str(value).casefold().split())


def _normalize_effect(value: str) -> str:
    return ' '.join(token.casefold() for token in _WORD.findall(str(value)))


def _phrase_in_effect(normalized_query: str, normalized_effect: str) -> bool:
    return f' {normalized_query} ' in f' {normalized_effect} '


class RegistletSearchService:
    def __init__(self, path: Path) -> None:
        self.dataset = load_registlet_dataset(path)

    def list_autocomplete_values(self) -> tuple[tuple[str, str], ...]:
        rows = [(record.name, 'Registlet') for record in self.dataset.records]
        return tuple(sorted(rows, key=lambda row: row[0].casefold()))

    def _nearest_level_suggestions(self, level: int) -> tuple[str, ...]:
        ranked = sorted(
            self.dataset.valid_stoodie_levels,
            key=lambda candidate: (abs(candidate - level), candidate),
        )
        return tuple(f'std {candidate}' for candidate in ranked[:2])

    def _stoodie_search(self, raw: str) -> RegistletSearchOutcome:
        match = _STOODIE_QUERY.match(raw)
        if match is None:
            return RegistletSearchOutcome(
                kind='clarify',
                query=raw,
                message='Use one Stoodie level, for example: std 220.',
                route_quality=RouteQuality('structured', False, 1),
            )
        level = int(match.group(1))
        if level not in self.dataset.valid_stoodie_levels:
            return RegistletSearchOutcome(
                kind='suggest',
                query=raw,
                message=f'Stoodie Lv{level} is not a supported source level.',
                suggested_queries=self._nearest_level_suggestions(level),
                route_quality=RouteQuality('structured', False, 1),
            )
        results = tuple(
            sorted(
                (record for record in self.dataset.records if level in record.source_levels),
                key=lambda record: (record.name.casefold(), record.name),
            )
        )
        interpretation = QueryInterpretation(
            domain='Registlets',
            canonical_query=f'std {level}',
            chips=(
                QueryChip(
                    id='stoodie_level',
                    kind='stoodie_level',
                    label=f'Stoodie Lv{level}',
                    canonical_fragment=f'std {level}',
                    query_without='',
                ),
            ),
        )
        return RegistletSearchOutcome(
            kind='results' if results else 'not_found',
            query=raw,
            results=results,
            message=None if results else f'No Registlets are listed for Stoodie Lv{level}.',
            interpretation=interpretation,
            route_quality=RouteQuality('structured', bool(results), 1),
            match=RegistletMatch('stoodie', str(level)) if results else None,
        )

    def _effect_matches(self, raw: str) -> tuple[RegistletRecord, ...]:
        normalized_query = _normalize_effect(raw)
        if not normalized_query:
            return ()
        phrase_hits = [
            record
            for record in self.dataset.records
            if _phrase_in_effect(normalized_query, _normalize_effect(record.effect))
        ]
        if phrase_hits:
            return tuple(sorted(phrase_hits, key=lambda record: (record.name.casefold(), record.name)))

        query_tokens = set(normalized_query.split())
        token_hits = []
        for record in self.dataset.records:
            effect_tokens = set(_normalize_effect(record.effect).split())
            if query_tokens and query_tokens <= effect_tokens:
                token_hits.append(record)
        return tuple(sorted(token_hits, key=lambda record: (record.name.casefold(), record.name)))

    def _fuzzy_name_matches(self, raw: str) -> tuple[RegistletRecord, ...]:
        normalized_query = _normalize_name(raw)
        if not normalized_query:
            return ()
        scored: list[tuple[float, RegistletRecord]] = []
        for record in self.dataset.records:
            score = float(fuzz.ratio(normalized_query, _normalize_name(record.name)))
            if score >= 88:
                scored.append((score, record))
        scored.sort(key=lambda row: (-row[0], row[1].name.casefold(), row[1].name))
        return tuple(record for _, record in scored[:20])

    def search(self, query: str) -> RegistletSearchOutcome:
        raw = ' '.join(str(query).split())
        if not raw:
            return RegistletSearchOutcome(
                kind='not_found',
                query=raw,
                message='Enter a Stoodie level, Registlet name, or effect text.',
            )

        if is_stoodie_intent(raw):
            return self._stoodie_search(raw)

        normalized_query = _normalize_name(raw)
        exact = tuple(
            record for record in self.dataset.records if _normalize_name(record.name) == normalized_query
        )
        if exact:
            return RegistletSearchOutcome(
                kind='results',
                query=raw,
                results=tuple(sorted(exact, key=lambda record: (record.name.casefold(), record.name))),
                route_quality=RouteQuality('exact', True, 1),
                match=RegistletMatch('name'),
            )

        effect_hits = self._effect_matches(raw)
        if effect_hits:
            return RegistletSearchOutcome(
                kind='results',
                query=raw,
                results=effect_hits,
                route_quality=RouteQuality('content', True, len(_normalize_effect(raw).split())),
                match=RegistletMatch('effect', _normalize_effect(raw)),
            )

        fuzzy_hits = self._fuzzy_name_matches(raw)
        if fuzzy_hits:
            return RegistletSearchOutcome(
                kind='results',
                query=raw,
                results=fuzzy_hits,
                route_quality=RouteQuality('weak', True, 1),
                match=RegistletMatch('fuzzy_name'),
            )

        return RegistletSearchOutcome(
            kind='not_found',
            query=raw,
            message='No matching Registlet or effect text found.',
        )

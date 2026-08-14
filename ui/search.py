from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import streamlit.components.v1 as components

from toram_search.models import AutocompleteSuggestion

_COMPONENT_PATH = Path(__file__).resolve().parents[1] / 'components' / 'autocomplete_search'
autocomplete_search = components.declare_component('autocomplete_search', path=str(_COMPONENT_PATH))


@dataclass(frozen=True)
class SearchSubmission:
    query: str
    nonce: int


def render_search_box(*, value: str, suggestions: tuple[AutocompleteSuggestion, ...], placeholder: str, disabled: bool = False) -> SearchSubmission | None:
    result = autocomplete_search(value=value, suggestions=[asdict(row) for row in suggestions], placeholder=placeholder, disabled=disabled, default=None, key='toram_search_box')
    if not isinstance(result, dict) or result.get('event') != 'submit': return None
    query = str(result.get('value') or '').strip(); nonce = result.get('nonce')
    if not query or not isinstance(nonce, int): return None
    return SearchSubmission(query=query, nonce=nonce)

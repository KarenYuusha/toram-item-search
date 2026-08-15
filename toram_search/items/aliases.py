from __future__ import annotations

import re
import unicodedata
from typing import Iterable

MAIN_WEAPON_TYPES = (
    "1 Handed Sword", "2 Handed Sword", "Bow", "Bowgun", "Katana",
    "Staff", "Magic Device", "Knuckles", "Halberd",
)
ALL_CRYSTA_TYPES = (
    "Normal Crysta", "Weapon Crysta", "Armor Crysta", "Additional Crysta",
    "Special Crysta", "Enhancer Crysta (Red)", "Enhancer Crysta (Purple)",
    "Enhancer Crysta (Green)", "Enhancer Crysta (Yellow)", "Enhancer Crysta (Blue)",
)
REGISTLET_ITEM_TYPES = frozenset({"regislet", "registlet"})
ITEM_WORD_ALIASES = {"crystal": "xtal", "crysta": "xtal", "xtall": "xtal"}
ITEM_TYPE_ALIASES = {
    "1h": "1 Handed Sword", "ohs": "1 Handed Sword",
    "2h": "2 Handed Sword", "ths": "2 Handed Sword",
    "bg": "Bowgun", "bwg": "Bowgun", "bowgun": "Bowgun", "bow": "Bow",
    "ktn": "Katana", "katana": "Katana", "staff": "Staff", "stf": "Staff",
    "md": "Magic Device", "magic device": "Magic Device",
    "knk": "Knuckles", "knuckle": "Knuckles", "knuckles": "Knuckles",
    "hb": "Halberd", "halberd": "Halberd",
    "armor": "Armor", "arm": "Armor", "additional": "Additional", "add": "Additional", "hat": "Additional",
    "special": "Special", "ring": "Special", "rings": "Special",
    "arrow": "Arrow", "dagger": "Dagger", "shield": "Shield",
    "usable": "Usable", "consumable": "Usable",
}
STAT_ALIASES = {
    "cr": "critical rate", "cd": "critical damage", "crit rate": "critical rate",
    "hp": "maxhp", "max hp": "maxhp", "ampr": "attack mp recovery",
    "pp": "physical pierce %", "mp": "magic pierce %",
    "atk%": "atk %", "matk%": "matk %", "aggro": "aggro %",
    "pres": "physical resistance %", "mres": "magic resistance %",
    "lrd": "long range damage %", "srd": "short range damage %",
    "stab": "stability", "motion": "motion speed %",
}
STAT_AMBIGUOUS_GROUPS = {"crit": ("Critical Rate", "Critical Damage"), "crt": ("Critical Rate", "Critical Damage")}


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value)).casefold()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def normalize_stat_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value)).casefold()
    value = re.sub(r"[^\w%]+", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s*%\s*", " % ", value)
    return " ".join(value.split())


def expand_stat_aliases(value: str) -> str:
    normalized = normalize_stat_text(value)
    if normalized in STAT_ALIASES:
        return STAT_ALIASES[normalized]
    tokens = normalized.split()
    ordered = sorted(STAT_ALIASES.items(), key=lambda pair: len(pair[0].split()), reverse=True)
    out: list[str] = []
    i = 0
    while i < len(tokens):
        matched = False
        for alias, target in ordered:
            a = alias.split()
            if tokens[i:i+len(a)] == a:
                out.extend(target.split())
                i += len(a)
                matched = True
                break
        if not matched:
            out.append(tokens[i]); i += 1
    return " ".join(out)


def is_crysta_item_type(item_type: str) -> bool:
    return "crysta" in normalize_name(item_type).split()


def is_registlet_item_type(item_type: str | None) -> bool:
    return str(item_type or '').strip().casefold() in REGISTLET_ITEM_TYPES


def resolve_stat_term(text: str, available_stats: Iterable[str]) -> tuple[str | None, tuple[str, ...], bool]:
    q = expand_stat_aliases(text)
    by_norm = {normalize_stat_text(v): v for v in available_stats}
    if q in STAT_AMBIGUOUS_GROUPS:
        candidates = tuple(v for v in STAT_AMBIGUOUS_GROUPS[q] if normalize_stat_text(v) in by_norm)
        return None, candidates, bool(candidates)
    exact = by_norm.get(normalize_stat_text(q))
    if exact:
        return exact, (), False
    return None, (), False

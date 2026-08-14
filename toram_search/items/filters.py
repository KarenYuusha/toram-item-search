from __future__ import annotations
from dataclasses import dataclass
from .aliases import ALL_CRYSTA_TYPES, ITEM_TYPE_ALIASES, MAIN_WEAPON_TYPES, normalize_name, normalize_stat_text

@dataclass(frozen=True)
class ItemTypeFilter:
    label: str
    item_types: tuple[str, ...]
    consumed_text: str


def _existing(types: tuple[str, ...], available: set[str]) -> tuple[str, ...]:
    by_norm = {normalize_name(x): x for x in available}
    return tuple(by_norm[normalize_name(x)] for x in types if normalize_name(x) in by_norm)


def _candidates(available: set[str]) -> list[tuple[str, str, tuple[str, ...]]]:
    rows: list[tuple[str,str,tuple[str,...]]] = []
    special = {
        "weapon xtal": ("Weapon Crysta", ("Weapon Crysta", "Enhancer Crysta (Red)")),
        "wp xtal": ("Weapon Crysta", ("Weapon Crysta", "Enhancer Crysta (Red)")),
        "xtal weapon": ("Weapon Crysta", ("Weapon Crysta", "Enhancer Crysta (Red)")),
        "xtal wp": ("Weapon Crysta", ("Weapon Crysta", "Enhancer Crysta (Red)")),
        "armor xtal": ("Armor Crysta", ("Armor Crysta", "Enhancer Crysta (Green)")),
        "arm xtal": ("Armor Crysta", ("Armor Crysta", "Enhancer Crysta (Green)")),
        "xtal armor": ("Armor Crysta", ("Armor Crysta", "Enhancer Crysta (Green)")),
        "xtal arm": ("Armor Crysta", ("Armor Crysta", "Enhancer Crysta (Green)")),
        "additional xtal": ("Additional Crysta", ("Additional Crysta", "Enhancer Crysta (Yellow)")),
        "add xtal": ("Additional Crysta", ("Additional Crysta", "Enhancer Crysta (Yellow)")),
        "xtal additional": ("Additional Crysta", ("Additional Crysta", "Enhancer Crysta (Yellow)")),
        "xtal add": ("Additional Crysta", ("Additional Crysta", "Enhancer Crysta (Yellow)")),
        "ring xtal": ("Special Crysta", ("Special Crysta", "Enhancer Crysta (Purple)")),
        "special xtal": ("Special Crysta", ("Special Crysta", "Enhancer Crysta (Purple)")),
        "xtal ring": ("Special Crysta", ("Special Crysta", "Enhancer Crysta (Purple)")),
        "xtal special": ("Special Crysta", ("Special Crysta", "Enhancer Crysta (Purple)")),
        "xtal": ("All Crysta", ALL_CRYSTA_TYPES),
        "crysta": ("All Crysta", ALL_CRYSTA_TYPES),
        "crystal": ("All Crysta", ALL_CRYSTA_TYPES),
        "weapon": ("Main Weapons", MAIN_WEAPON_TYPES),
        "wp": ("Main Weapons", MAIN_WEAPON_TYPES),
    }
    for phrase, (label, types) in special.items():
        actual = _existing(tuple(types), available)
        if actual: rows.append((phrase,label,actual))
    for alias, item_type in ITEM_TYPE_ALIASES.items():
        actual = _existing((item_type,), available)
        if actual: rows.append((normalize_stat_text(alias), actual[0], actual))
    for item_type in available:
        rows.append((normalize_stat_text(item_type), item_type, (item_type,)))
    rows.sort(key=lambda x:(len(x[0].split()),len(x[0])), reverse=True)
    return rows


def extract_item_filter(text: str, available_item_types: set[str]) -> tuple[ItemTypeFilter | None, str]:
    normalized = normalize_stat_text(text)
    tokens = normalized.split()
    for phrase,label,types in _candidates(available_item_types):
        p = phrase.split()
        for start in range(len(tokens)-len(p)+1):
            if tokens[start:start+len(p)] == p:
                remaining = tokens[:start] + tokens[start+len(p):]
                return ItemTypeFilter(label, types, phrase), " ".join(remaining)
    return None, normalized

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FoodStatDefinition:
    key: str
    display: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class FoodEntry:
    code: str
    stat_key: str
    stat_display: str
    level: int


@dataclass(frozen=True)
class FoodDataset:
    stats: tuple[FoodStatDefinition, ...]
    entries: tuple[FoodEntry, ...]
    warnings: tuple[str, ...] = ()

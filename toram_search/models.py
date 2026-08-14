from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DatabaseMode = Literal["Universal", "Items", "Skills"]


@dataclass(frozen=True)
class DatabaseHealth:
    name: str
    path: Path
    ok: bool
    error: str | None = None

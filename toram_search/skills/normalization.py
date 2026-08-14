from __future__ import annotations

def normalize_skill_name(text: str) -> str:
    return " ".join(str(text).casefold().replace("’", "'").split())

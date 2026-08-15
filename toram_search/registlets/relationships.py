from __future__ import annotations

from dataclasses import dataclass

from .models import RegistletRecord


@dataclass(frozen=True)
class RegistletRelationshipIndex:
    by_skill: dict[str, tuple[str, ...]]
    warnings: tuple[str, ...] = ()


def build_relationship_index(
    records: tuple[RegistletRecord, ...],
    canonical_skill_names: tuple[str, ...],
) -> RegistletRelationshipIndex:
    canonical = {name.casefold(): name for name in canonical_skill_names}
    edges: dict[str, set[str]] = {}
    warnings: list[str] = []

    for record in records:
        if record.affects_skill is None:
            continue
        for supplied_name in record.affects_skill:
            key = supplied_name.casefold()
            if key not in canonical:
                warnings.append(
                    f'Registlet {record.name!r} references unknown Skill {supplied_name!r}; relationship skipped.'
                )
                continue
            edges.setdefault(key, set()).add(record.name)

    by_skill = {
        key: tuple(sorted(names, key=lambda name: (name.casefold(), name)))
        for key, names in edges.items()
    }
    return RegistletRelationshipIndex(by_skill=by_skill, warnings=tuple(warnings))

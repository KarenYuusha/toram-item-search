from __future__ import annotations

from toram_search.interpretation import QueryChip, QueryInterpretation


def build_skill_interpretation(
    *,
    tree_name: str | None = None,
    ailment: str | None = None,
    mp_cost_max: int | None = None,
    required_level_max: int | None = None,
    mp_rank_direction: str | None = None,
    count_mode: bool = False,
    unsupported_structured_component: bool = False,
) -> QueryInterpretation | None:
    if unsupported_structured_component:
        return None

    semantic = []
    if mp_rank_direction is not None:
        descending = mp_rank_direction == 'desc'
        semantic.append((
            'rank_mp', 'rank', 'Highest MP' if descending else 'Lowest MP',
            'highest mp' if descending else 'lowest mp',
        ))
    if ailment is not None:
        semantic.append(('ailment', 'ailment', ailment, f'inflict {ailment.casefold()}'))
    if mp_cost_max is not None:
        semantic.append(('mp', 'mp', f'MP ≤ {mp_cost_max}', f'mp <= {mp_cost_max}'))
    if required_level_max is not None:
        semantic.append((
            'required_level', 'required_level',
            f'Required Level ≤ {required_level_max}',
            f'required level <= {required_level_max}',
        ))
    if tree_name is not None:
        semantic.append(('skill_tree', 'skill_tree', tree_name, tree_name.casefold()))
    if not semantic:
        return None

    def canonical(fragments: list[str]) -> str:
        if not fragments:
            return ''
        body = ' '.join(fragments)
        return f'how many skills {body}' if count_mode else body

    chips = tuple(
        QueryChip(
            part_id,
            kind,
            label,
            fragment,
            canonical([row[3] for row in semantic if row[0] != part_id]),
        )
        for part_id, kind, label, fragment in semantic
    )
    return QueryInterpretation('Skills', canonical([row[3] for row in semantic]), chips)

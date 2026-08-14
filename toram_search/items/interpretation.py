from __future__ import annotations

from typing import cast

from toram_search.interpretation import QueryChip, QueryInterpretation
from .aliases import normalize_stat_text
from .filters import ItemTypeFilter
from .models import ParsedClause, ParsedStatExpression

_PREFERRED_STAT_QUERY = {
    'Aggro %': 'aggro',
    'Critical Rate': 'critical rate',
    'Critical Damage': 'critical damage',
    'MaxHP': 'maxhp',
}


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f'{value:g}'


def _stat_fragment(stat_name: str) -> str:
    return _PREFERRED_STAT_QUERY.get(stat_name, normalize_stat_text(stat_name))


def _join(parts: list[str]) -> str:
    return ' '.join(part for part in parts if part).strip()


def _clause_fragment(clause: ParsedClause) -> str:
    stat = _stat_fragment(clause.typed_stat)
    if clause.explicit_comparison:
        return f'{stat} {clause.operator} {_number(clause.value)}'
    return stat


def _clause_label(clause: ParsedClause) -> str:
    if not clause.explicit_comparison:
        return clause.typed_stat
    symbol = {'>=': '≥', '<=': '≤', '==': '=', '=': '='}.get(clause.operator, clause.operator)
    return f'{clause.typed_stat} {symbol} {_number(clause.value)}'


def build_simple_item_interpretation(
    stat: str,
    item_filter: ItemTypeFilter | None,
    rank_direction: str | None,
    negative_stat: bool,
) -> QueryInterpretation:
    stat_kind = 'numeric_stat' if negative_stat else 'stat'
    stat_label = f'{stat} ≤ -1' if negative_stat else stat
    stat_fragment = f'{_stat_fragment(stat)} <= -1' if negative_stat else _stat_fragment(stat)
    semantic = []
    if rank_direction is not None:
        semantic.append(('rank', 'rank', 'Lowest' if rank_direction == 'asc' else 'Highest', 'lowest' if rank_direction == 'asc' else 'highest'))
    semantic.append(('stat', stat_kind, stat_label, stat_fragment))
    if item_filter is not None:
        semantic.append(('item_type', 'item_type', item_filter.label, item_filter.canonical_text))

    def rebuild_without(chip_id: str) -> str:
        removed = {chip_id}
        if chip_id == 'stat':
            removed.add('rank')
        return _join([fragment for part_id, _kind, _label, fragment in semantic if part_id not in removed])

    chips = tuple(
        QueryChip(
            part_id,
            kind,
            label,
            fragment,
            rebuild_without(part_id),
            ('stat',) if part_id == 'rank' else (),
        )
        for part_id, kind, label, fragment in semantic
    )
    return QueryInterpretation('Items', _join([row[3] for row in semantic]), chips)


def _rebuild_expression(
    expr: ParsedStatExpression,
    removed_clause: tuple[int, int] | None,
    remove_filter: bool,
) -> str:
    groups = []
    for group_index, group in enumerate(expr.groups):
        clauses = []
        for clause_index, clause in enumerate(group.clauses):
            if removed_clause == (group_index, clause_index):
                continue
            clauses.append(_clause_fragment(clause))
        if clauses:
            groups.append(' and '.join(clauses))
    expression = ' or '.join(groups)
    item_filter = None if remove_filter else cast(ItemTypeFilter | None, expr.item_filter)
    return _join([expression, item_filter.canonical_text if item_filter is not None else ''])


def build_expression_item_interpretation(expr: ParsedStatExpression) -> QueryInterpretation:
    chips = []
    for group_index, group in enumerate(expr.groups):
        for clause_index, clause in enumerate(group.clauses):
            chip_id = f'clause_{group_index}_{clause_index}'
            chips.append(QueryChip(
                chip_id,
                'numeric_stat' if clause.explicit_comparison else 'stat',
                _clause_label(clause),
                _clause_fragment(clause),
                _rebuild_expression(expr, (group_index, clause_index), False),
            ))
    item_filter = cast(ItemTypeFilter | None, expr.item_filter)
    if item_filter is not None:
        chips.append(QueryChip(
            'item_type',
            'item_type',
            item_filter.label,
            item_filter.canonical_text,
            _rebuild_expression(expr, None, True),
        ))
    return QueryInterpretation('Items', _rebuild_expression(expr, None, False), tuple(chips))

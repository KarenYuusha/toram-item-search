from __future__ import annotations
import re
from .aliases import expand_stat_aliases, normalize_stat_text
from .filters import extract_item_filter
from .models import ParsedAndGroup, ParsedClause, ParsedStatExpression

_COMPARISON = re.compile(r"(>=|<=|==|>|<|=)")
_BOOLEAN = re.compile(r"\b(and|or)\b", re.I)

class StatQuerySyntaxError(ValueError): pass


def _canonical_stat(text: str, available_stats: list[str] | None) -> str:
    expanded = expand_stat_aliases(text)
    if available_stats is None:
        return expanded
    by_norm = {normalize_stat_text(x): x for x in available_stats}
    return by_norm.get(normalize_stat_text(expanded), expanded)


def parse_stat_expression(text: str, available_item_types: set[str], available_stats: list[str] | None = None) -> ParsedStatExpression:
    item_filter, _normalized_remaining = extract_item_filter(text, available_item_types)
    expr = text.strip()
    if item_filter is not None:
        phrase = re.escape(item_filter.consumed_text)
        expr = re.sub(rf'(?i)(?<!\w){phrase}(?!\w)', ' ', expr, count=1)
        expr = ' '.join(expr.split())
    if expr.casefold().startswith("stat "):
        expr = expr[5:].strip()
    if not expr:
        raise StatQuerySyntaxError("expected a stat")
    parts = _BOOLEAN.split(expr)
    groups: list[list[ParsedClause]] = [[]]
    pending = None
    for i, raw in enumerate(parts):
        if i % 2:
            pending = raw.casefold(); continue
        clause_text = raw.strip()
        if not clause_text: raise StatQuerySyntaxError("expected a stat")
        m = _COMPARISON.search(clause_text)
        if m:
            stat = clause_text[:m.start()].strip(); value_text = clause_text[m.end():].strip()
            if not stat or not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", value_text):
                raise StatQuerySyntaxError("invalid comparison")
            clause = ParsedClause(_canonical_stat(stat, available_stats), m.group(1), float(value_text), True)
        else:
            clause = ParsedClause(_canonical_stat(clause_text, available_stats), ">=", 1.0, False)
        if i and pending == "or": groups.append([clause])
        else: groups[-1].append(clause)
    return ParsedStatExpression(tuple(ParsedAndGroup(tuple(g)) for g in groups), item_filter, text)


def compare_amount(amount: float, operator: str, value: float) -> bool:
    if operator == ">": return amount > value
    if operator == ">=": return amount >= value
    if operator == "<": return amount < value
    if operator == "<=": return amount <= value
    return amount == value

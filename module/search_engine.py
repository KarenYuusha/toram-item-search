import re

import pandas as pd
from rapidfuzz import fuzz, process

from .normalizer import standard_prep, normalize_gear_name, normalize_stat_name


GEAR_TYPES = [
    'armor',
    'additional',
    'special',
    'shield',
    'arrow',
    'dagger',
    '1 handed sword',
    '2 handed sword',
    'bow',
    'bowgun',
    'knuckles',
    'magic device',
    'staff',
    'halberd',
    'katana'
]


def _empty_results(df, extra_columns=None) -> pd.DataFrame:
    columns = list(df.columns)
    for column in extra_columns or []:
        if column not in columns:
            columns.append(column)
    return pd.DataFrame(columns=columns)


def _normalize_type_filter(type_filters):
    if not type_filters:
        return []
    if isinstance(type_filters, str):
        type_filters = [type_filters]

    normalized = []
    for item_type in type_filters:
        item_type = normalize_gear_name(item_type)
        best_match = process.extractOne(item_type, GEAR_TYPES, scorer=fuzz.WRatio)
        if best_match and best_match[1] >= 60:
            normalized.append(best_match[0])

    return list(dict.fromkeys(normalized))


def apply_type_filter(df, type_filters) -> pd.DataFrame:
    normalized_types = _normalize_type_filter(type_filters)
    if not normalized_types:
        return df

    type_clean = df["type"].astype(str).str.lower().str.strip()
    return df[type_clean.isin(normalized_types)]


def extract_stat_value(stats_str, query):
    if not isinstance(stats_str, str):
        return None

    stats_normalized = re.sub(r"\s+", "", stats_str.lower())
    query_normalized = query.lower().replace(" ", "")
    pattern = re.compile(rf"{re.escape(query_normalized)}[:]\s*(-?[\d\.]+)")
    match = pattern.search(stats_normalized)
    if match:
        return float(match.group(1))
    return None


def search_by_name(query, df, k=5, score_cutoff=50, type_filters=None) -> pd.DataFrame:
    if not query:
        return _empty_results(df, ["match_score"])

    df = apply_type_filter(df, type_filters)
    if df.empty:
        return _empty_results(df, ["match_score"])

    query_clean = standard_prep(query)

    # Find matches for multi-keyword queries
    matches = process.extract(
        query_clean,
        df['name_clean'].tolist(),
        scorer=fuzz.token_set_ratio,
        limit=k,
        score_cutoff=score_cutoff
    )

    if not matches:
        return _empty_results(df, ["match_score"])

    indices, scores = zip(*[(m[2], m[1]) for m in matches])
    results = df.iloc[list(indices)].copy()
    results['match_score'] = scores

    return results.sort_values('match_score', ascending=False)


def search_by_stat(query, df, k=5, ascending=False, type_filters=None) -> pd.DataFrame:
    df = apply_type_filter(df, type_filters)
    if df.empty:
        return _empty_results(df, ["stat_value"])

    stat_values = df['stats'].apply(lambda x: extract_stat_value(x, query))
    filtered = df[stat_values.notna()].copy()
    filtered['stat_value'] = stat_values[stat_values.notna()]
    sorted_df = filtered.sort_values('stat_value', ascending=ascending)
    return sorted_df.head(k)


def search_engine(query, df, k=5, ascending=False, type_filters=None) -> pd.DataFrame:
    query = query.strip()

    if not query:
        return _empty_results(df)

    query_lower = query.lower()

    type_match = re.search(r"\btype\s*:\s*([^,]+)$", query, flags=re.IGNORECASE)
    if type_match:
        existing_filters = [type_filters] if isinstance(type_filters, str) else list(type_filters or [])
        type_filters = [*existing_filters, type_match.group(1).strip()]
        query = query[:type_match.start()].strip()
        query_lower = query.lower()

    # search by stat
    if query_lower.startswith("stat:"):
        stat_query = query[len("stat:"):].strip()
        stat_query = normalize_stat_name(stat_query)
        return search_by_stat(stat_query, df, k, ascending, type_filters)

    # search by weapon type
    if query_lower.startswith("all"):
        parts = query_lower.split(maxsplit=1)
        if len(parts) == 1:
            return apply_type_filter(df, type_filters).copy()

        weapon_type_query = parts[1].strip()
        weapon_type_query = normalize_gear_name(weapon_type_query)
        best_match = process.extractOne(weapon_type_query,
                                        GEAR_TYPES, scorer=fuzz.WRatio)
        if best_match and best_match[1] >= 60:
            weapon_type = best_match[0]
            results = apply_type_filter(df, [weapon_type])
            return apply_type_filter(results, type_filters).copy()
        return _empty_results(df)

    # search by item name
    return search_by_name(query, df, k, type_filters=type_filters)

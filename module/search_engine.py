import re

import pandas as pd
from rapidfuzz import fuzz, process

from .normalizer import standard_prep, normalize_gear_name, normalize_stat_name


wp_types_list = [
    'armor',
    'additional',
    'shield',
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


def search_by_name(query, df, k=5, score_cutoff=50) -> pd.DataFrame:
    if not query:
        return pd.DataFrame(columns=[*df.columns, "match_score"])

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
        return pd.DataFrame(columns=[*df.columns, "match_score"])

    indices, scores = zip(*[(m[2], m[1]) for m in matches])
    results = df.iloc[list(indices)].copy()
    results['match_score'] = scores

    return results.sort_values('match_score', ascending=False)


def search_by_stat(query, df, k=5, ascending=False) -> pd.DataFrame:
    df = df.copy()
    df['stat_value'] = df['stats'].apply(
        lambda x: extract_stat_value(x, query))
    filtered = df[df['stat_value'].notna()]
    sorted_df = filtered.sort_values('stat_value', ascending=ascending)
    return sorted_df.head(k)


def search_engine(query, df, k=5, ascending=False) -> pd.DataFrame:
    query = query.strip()

    if not query:
        return pd.DataFrame()

    query_lower = query.lower()

    # search by stat
    if query_lower.startswith("stat:"):
        stat_query = query[len("stat:"):].strip()
        stat_query = normalize_stat_name(stat_query)
        return search_by_stat(stat_query, df, k, ascending)

    # search by weapon type
    if query_lower.startswith("all"):
        parts = query_lower.split(maxsplit=1)
        if len(parts) == 1:
            return df.copy()

        weapon_type_query = parts[1].strip()
        weapon_type_query = normalize_gear_name(weapon_type_query)
        best_match = process.extractOne(weapon_type_query,
                                        wp_types_list, scorer=fuzz.WRatio)
        if best_match and best_match[1] >= 60:
            weapon_type = best_match[0]

            return df[df["type"].str.lower().str.strip() == weapon_type.lower()].copy()
        return pd.DataFrame()

    # search by item name
    return search_by_name(query, df, k)

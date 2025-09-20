import re

WEAPON_ALIASES = {
    "one hand": "1 handed sword",
    "1h": "1 handed sword",
    "1-h": "1 handed sword",
    "ohs": "1 handed sword",

    "two hand": "2 handed sword",
    "2h": "2 handed sword",
    "2-h": "2 handed sword",
    "ths": "2 handed sword",

    "bow gun": "bowgun",
    "bg": "bowgun",
    "bwg": "bowgun",

    "bow": "bow",
    "bw": "bow",

    "katana": "katana",
    "ktn": "katana",

    "staff": "staff",
    "stf": "staff",

    "magic device": "magic device",
    "md": "magic device",

    "knuckles": "knuckles",
    "knuckle": "knuckles",
    "knuck": "knuckles",
    "knk": "knuckles",

    "add": "additional",
    "hat": "additional",
    "ad":  "additional",

    "halberd": "halberd",
    "hb": "halberd",

    "armor": "armor",
    "arm": "armor",
}

STAT_ALIASES = {
    "dt": "% stronger against",

    "dte": "% stronger against earth",
    "dtearth": "% stronger against earth",

    "dtf": "% stronger against fire",
    "dtfire": "% stronger against fire",

    "dtw": "% stronger against wind",
    "dtwind": "% stronger against wind",

    "dtwa": "% stronger against water",
    "dtwater": "% stronger against water",

    "dtn": "% stronger against neutral",
    "dtneutral": "% stronger against neutral",

    "dtd": "% stronger against dark",
    "dtdark": "% stronger against dark",

    "dtl": "% stronger against light",
    "dtlight": "% stronger against light",

    "cast speed": "cspd",
    "attack spped": "aspd",

    "acc": "accuracy",
    "defense": "def",

    "mag": "magic",
    "phys": "physcial",

    "dmg": "damage",

    "anti": "anticipate",

    "ampr": "attack mp recovery",

    "lrd": "long range damage",
    "srd": "short range damage",

    "ref": "refine",

    "natural hp": "natural hp regen",
    "natural mp": "natural mp regen",

    "motion": "motion speed %",
    "motion %": "motion speed %",
    "motion%": "motion speed %",

    "cr": "critical rate",
    "cd": "critical damage",

    "stab": "stability",

    "rev": "revive",

    "xp": "exp",

    "ele": "element",

    "resist": "resistance",

    "pp": "physical pierce",
    "mp": "magical pierce",

    "pot": "potential",

    "bar": "barrier",

    "invi": "invicible",

    "gem dust": "gem dust drop amount %",
    "gem dust drop amount %": "gem dust drop amount %",

    "drop rate %": "drop rate %",
    "drop rate": "drop rate %"
}


def standard_prep(text):
    if not isinstance(text, str):  # handle NaN, None, numbers
        text = str(text) if text is not None else ""
    text = re.sub(r"\s{2,}", " ", text)
    return re.sub(r"[^a-z0-9'-]+", " ", text.lower()).strip()


def normalize_gear_name(text):
    text = standard_prep(text)

    for alias, canonical in sorted(WEAPON_ALIASES.items(), key=lambda x: -len(x[0])):
        pattern = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"
        text = re.sub(pattern, canonical, text, flags=re.IGNORECASE)

    return text


def normalize_stat_name(text):
    if not isinstance(text, str):
        return text

    # Merge weapon + stat aliases (lowercased keys for case-insensitive lookup)
    combined = {k.lower(): v for k, v in {
        **WEAPON_ALIASES, **STAT_ALIASES}.items()}

    # Sort aliases by length (longest first to avoid partial overlap issues)
    aliases_sorted = sorted(combined.keys(), key=len, reverse=True)

    # Build regex that matches any alias as a standalone token
    pattern = re.compile(
        r"(?<!\w)(" + "|".join(re.escape(a)
                               for a in aliases_sorted) + r")(?!\w)",
        flags=re.IGNORECASE,
    )

    # Replace in a single pass
    return pattern.sub(lambda m: combined[m.group(1).lower()], text).strip()

import csv
import math
import os
import re
import statistics

# ---------------------------------------------------------------------------
# Rarity expected price ranges (min, max) in USD
# ---------------------------------------------------------------------------
RARITY_RANGES = {
    "Common":        (0.10,    2.00),
    "Uncommon":      (0.50,    5.00),
    "Rare":          (2.00,   20.00),
    "Rare Holo":     (5.00,  100.00),
    "Rare Ultra":   (20.00,  500.00),
    "Rare Secret": (100.00, 1000.00),
}

# ---------------------------------------------------------------------------
# Set era classification — strip trailing digits from set id prefix
# e.g. "base1" → "base" → vintage
# ---------------------------------------------------------------------------
_VINTAGE    = {"base", "gym", "neo", "np", "basep", "bp"}
_OLDSCHOOL  = {"ecard", "ex", "pop", "ru", "si"}
_CLASSIC    = {"dp", "dpp", "pl", "hgss", "hsp", "col", "bw", "bwp", "dv"}
_MODERN     = {"xy", "xyp", "dc", "det", "g", "sm", "smp", "cel", "cel25", "pgo"}
# anything else (sv*, swsh*, me*, mcd*, fut*, rsv*) → recent

_ERA_SCARCITY = {
    "vintage":   90,
    "oldschool": 65,
    "classic":   42,
    "modern":    22,
    "recent":    10,
}

_RARITY_SCARCITY_BONUS = {
    "Common":        0,
    "Uncommon":      3,
    "Rare":          6,
    "Rare Holo":    10,
    "Rare Ultra":   14,
    "Rare Secret":  18,
}

# ---------------------------------------------------------------------------
# PSA grade multipliers over raw price — (psa9_mult, psa10_mult)
# Grounded in real hobby observations: vintage holos command the biggest
# premiums; recent commons barely justify grading costs.
# ---------------------------------------------------------------------------
_GRADE_MULTIPLIERS: dict[tuple, tuple[float, float]] = {
    ("vintage",   "Rare Holo"):   (4.0, 18.0),
    ("vintage",   "Rare"):        (3.0,  9.0),
    ("vintage",   "Uncommon"):    (3.0, 10.0),
    ("vintage",   "Common"):      (3.5, 13.0),
    ("oldschool", "Rare Holo"):   (2.5,  8.0),
    ("oldschool", "Rare Ultra"):  (2.5,  7.0),
    ("oldschool", "Rare"):        (2.0,  5.0),
    ("oldschool", "Common"):      (2.0,  5.0),
    ("classic",   "Rare Holo"):   (2.0,  5.5),
    ("classic",   "Rare Ultra"):  (2.0,  5.0),
    ("classic",   "Rare"):        (1.6,  3.5),
    ("classic",   "Common"):      (1.5,  3.0),
    ("modern",    "Rare Ultra"):  (1.5,  3.5),
    ("modern",    "Rare Secret"): (1.5,  4.0),
    ("modern",    "Rare Holo"):   (1.4,  3.0),
    ("modern",    "Common"):      (1.2,  2.0),
    ("recent",    "Rare Ultra"):  (1.3,  2.8),
    ("recent",    "Rare Secret"): (1.4,  3.2),
    ("recent",    "Rare Holo"):   (1.25, 2.5),
    ("recent",    "Common"):      (1.1,  1.7),
}
_GRADE_DEFAULT = (1.2, 2.5)

# ---------------------------------------------------------------------------
# Suffix pattern to strip card variant labels from a Pokemon name
# so "Charizard VMAX" → "Charizard" for popularity lookup
# ---------------------------------------------------------------------------
_SUFFIX_RE = re.compile(
    r"\s+(V|VMAX|VSTAR|VUNION|GX|EX|TAG|TEAM|"
    r"Prime|LV\.X|Level-Up|LEGEND|BREAK|"
    r"delta|Star|[♀♂])\b.*$",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Pull rates — average packs to open before seeing ONE of a given rarity
# (any card of that rarity, not a specific one).
#
# Per-set rates sourced from ThePriceDex community aggregations, Card Shop
# Live empirical samples, and DigitalTQ pack-opening data.
# Era-based defaults are used when no per-set rate is available.
#
# Format:  _SET_PULL_RATES[set_code][rarity] = packs_per_any_of_that_rarity
# ---------------------------------------------------------------------------
_SET_PULL_RATES: dict[str, dict[str, float]] = {
    # ── Scarlet & Violet era ──────────────────────────────────────────
    "sv1": {
        "Hyper Rare": 54.1, "Special Illustration Rare": 31.7,
        "Ultra Rare": 15.2, "Illustration Rare": 13.0,
        "Double Rare": 7.3, "Rare Holo": 1.3,
    },
    "sv2": {
        "Hyper Rare": 56.8, "Special Illustration Rare": 31.5,
        "Ultra Rare": 15.1, "Illustration Rare": 13.0,
        "Double Rare": 7.3, "Rare Holo": 1.3,
    },
    "sv3": {
        "Hyper Rare": 52.1, "Special Illustration Rare": 31.9,
        "Ultra Rare": 15.1, "Illustration Rare": 13.2,
        "Double Rare": 7.3, "Rare Holo": 1.3,
    },
    "sv3pt5": {   # 151
        "Hyper Rare": 51.5, "Special Illustration Rare": 32.2,
        "Ultra Rare": 15.5, "Illustration Rare": 11.8,
        "Double Rare": 7.5, "Rare Holo": 1.2,
    },
    "sv4": {      # Paradox Rift — notably harder for SIR/HR
        "Hyper Rare": 82.0, "Special Illustration Rare": 47.4,
        "Ultra Rare": 15.1, "Illustration Rare": 13.0,
        "Double Rare": 6.4, "Rare Holo": 1.3,
    },
    "sv4pt5": {   # Paldean Fates
        "Hyper Rare": 62.1, "Special Illustration Rare": 58.1,
        "Ultra Rare": 15.1, "Illustration Rare": 13.9,
        "Double Rare": 6.3, "Rare Holo": 1.3,
    },
    "sv5": {      # Temporal Forces — big jump in SIR/HR difficulty
        "Hyper Rare": 138.9, "Special Illustration Rare": 85.5,
        "Ultra Rare": 15.0,  "Illustration Rare": 13.0,
        "ACE SPEC Rare": 20.0, "Double Rare": 5.9, "Rare Holo": 1.3,
    },
    "sv6": {      # Twilight Masquerade
        "Hyper Rare": 147.1, "Special Illustration Rare": 85.5,
        "Ultra Rare": 15.1,  "Illustration Rare": 12.9,
        "ACE SPEC Rare": 19.8, "Double Rare": 5.9, "Rare Holo": 1.3,
    },
    "sv6pt5": {   # Shrouded Fable
        "Hyper Rare": 128.3, "Special Illustration Rare": 87.2,
        "Ultra Rare": 14.3,  "Illustration Rare": 13.0,
        "ACE SPEC Rare": 20.0, "Double Rare": 6.0, "Rare Holo": 1.3,
    },
    "sv7": {      # Stellar Crown
        "Hyper Rare": 137.0, "Special Illustration Rare": 90.1,
        "Ultra Rare": 14.8,  "Illustration Rare": 12.8,
        "ACE SPEC Rare": 20.2, "Double Rare": 5.9, "Rare Holo": 1.3,
    },
    "sv8": {      # Surging Sparks — hardest HR in SV era (1/189)
        "Hyper Rare": 188.7, "Special Illustration Rare": 87.0,
        "Ultra Rare": 14.8,  "Illustration Rare": 13.0,
        "ACE SPEC Rare": 19.9, "Double Rare": 5.9, "Rare Holo": 1.3,
    },
    "sv8pt5": {   # Prismatic Evolutions
        "Hyper Rare": 178.6, "Special Illustration Rare": 45.0,
        "Ultra Rare": 13.4,  "ACE SPEC Rare": 21.4,
        "Double Rare": 6.1,  "Rare Holo": 1.3,
    },
    "sv9": {      # Journey Together
        "Hyper Rare": 137.0, "Special Illustration Rare": 86.2,
        "Ultra Rare": 15.3,  "Illustration Rare": 11.8,
        "Double Rare": 4.9,  "Rare Holo": 1.4,
    },
    # ── Sword & Shield era ───────────────────────────────────────────
    # ── Mega Evolution sets ───────────────────────────────────────────
    "me2": {   # Phantasmal Flames (Nov 2025) — rates from TCGplayer 5,000-pack sample
        "Double Rare":                5.0,   # 1/5
        "Illustration Rare":          9.0,   # 1/9
        "Ultra Rare":                12.0,   # 1/12
        "Special Illustration Rare": 80.0,   # 1/80  → 5 SIRs = 400 packs each
        "Mega Hyper Rare":         1260.0,   # 1/1260 → 1 MHR = 1,260 packs
    },
    # ── Sword & Shield era ───────────────────────────────────────────
    "swsh1": {
        "Rare Secret": 109.9, "Rare Rainbow": 81.3,
        "Ultra Rare": 26.7,   "Rare Holo VMAX": 45.5,
        "Rare Holo V": 7.0,   "Rare Holo": 5.5,   "Rare": 1.7,
    },
    "swsh35": {   # Champion's Path
        "Rare Secret": 75.8,  "Rare Rainbow": 63.7,
        "Ultra Rare": 18.6,   "Rare Holo VMAX": 28.2,
        "Rare Holo V": 6.4,   "Rare Holo": 1.4,
    },
    "swsh45": {   # Shining Fates
        "Rare Secret": 109.9, "Rare Rainbow": 84.0,
        "Ultra Rare": 30.8,   "Rare Holo VMAX": 18.4,
        "Rare Holo V": 9.2,   "Rare Holo": 5.6,   "Rare": 1.6,
    },
    "swsh8": {    # Fusion Strike
        "Rare Secret": 120.0, "Rare Rainbow": 91.9,
        "Ultra Rare": 26.0,   "Rare Holo VMAX": 26.5,
        "Rare Holo V": 11.1,  "Rare Holo": 5.6,   "Rare": 1.6,
    },
    "swsh9": {    # Brilliant Stars (first Trainer Gallery set)
        "Rare Secret": 117.0, "Rare Rainbow": 68.0,
        "Ultra Rare": 24.3,   "Rare Holo VSTAR": 43.0,
        "Rare Holo V": 7.0,   "Rare Holo": 5.7,   "Rare": 1.7,
        "Trainer Gallery Rare Holo": 11.4,
    },
    "swsh10": {   # Astral Radiance
        "Rare Secret": 131.6, "Rare Rainbow": 78.1,
        "Ultra Rare": 25.3,   "Rare Holo VSTAR": 37.1,
        "Rare Holo V": 7.8,   "Rare Holo": 5.7,   "Rare": 1.7,
        "Trainer Gallery Rare Holo": 11.4,
    },
    "swsh11": {   # Lost Origin
        "Rare Secret": 131.6, "Rare Rainbow": 78.1,
        "Ultra Rare": 25.6,   "Rare Holo VSTAR": 26.4,
        "Rare Holo V": 8.6,   "Rare Holo": 5.6,   "Rare": 1.7,
        "Trainer Gallery Rare Holo": 11.7,
    },
    "swsh12pt5": {  # Crown Zenith
        "Rare Secret": 133.3, "Rare Rainbow": 35.1,
        "Ultra Rare": 35.1,   "Rare Holo VSTAR": 30.7,
        "Rare Holo VMAX": 49.1, "Rare Holo V": 8.1,
        "Rare Holo": 5.6,     "Rare": 1.6,
        "Trainer Gallery Rare Holo": 4.5,
    },
}

# Era-based fallback rates (used when no per-set entry exists)
_ERA_PULL_RATES: dict[tuple, float] = {
    # Vintage (Base, Jungle, Fossil, Gym, Neo)
    ("vintage",   "Rare Holo"):              9.0,
    ("vintage",   "Rare"):                   5.0,
    ("vintage",   "Uncommon"):               2.0,
    ("vintage",   "Common"):                 1.0,
    # e-Card / EX (2002-2007)
    ("oldschool", "Rare Holo"):             12.0,
    ("oldschool", "Rare Ultra"):            36.0,
    ("oldschool", "Rare"):                   6.0,
    # DP / HGSS / BW (2007-2013)
    ("classic",   "Rare Holo"):             12.0,
    ("classic",   "Rare Ultra"):            18.0,
    ("classic",   "Rare Secret"):           36.0,
    ("classic",   "Rare Prime"):            18.0,
    # XY / SM (2014-2019)
    ("modern",    "Rare Holo"):              8.0,
    ("modern",    "Rare Holo EX"):           8.0,
    ("modern",    "Rare Holo GX"):           8.0,
    ("modern",    "Ultra Rare"):            18.0,
    ("modern",    "Rare Ultra"):            18.0,
    ("modern",    "Rare Secret"):           36.0,
    ("modern",    "Rare Rainbow"):          60.0,
    ("modern",    "Rare Shiny GX"):         60.0,
    # SWSH / SV fallback
    ("recent",    "Rare Holo"):              5.6,
    ("recent",    "Rare Holo V"):            8.0,
    ("recent",    "Rare Holo VMAX"):        45.0,
    ("recent",    "Rare Holo VSTAR"):       35.0,
    ("recent",    "Double Rare"):            7.0,
    ("recent",    "ACE SPEC Rare"):         20.0,
    ("recent",    "Ultra Rare"):            15.0,
    ("recent",    "Illustration Rare"):     13.0,
    ("recent",    "Special Illustration Rare"): 87.0,
    ("recent",    "Hyper Rare"):           137.0,
    ("recent",    "Rare Rainbow"):          80.0,
    ("recent",    "Rare Secret"):          120.0,
    ("recent",    "Trainer Gallery Rare Holo"): 18.0,
    ("recent",    "Mega Hyper Rare"):         1260.0,
}
_PULL_RATE_DEFAULT = 6.0

# How much pull odds contributes to the composite score per era.
# Vintage/oldschool cards are no longer being opened from packs so
# pack odds don't drive their secondary market price the same way.
_PULL_ODDS_ERA_WEIGHT: dict[str, float] = {
    "vintage":   0.10,   # 10 % of the 15 % weight
    "oldschool": 0.25,
    "classic":   0.45,
    "modern":    0.70,
    "recent":    1.00,   # full weight for active sets
}

# Module-level cache for the card DB (used for pull-odds counting)
_card_db_cache: list | None = None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

from src.pokemon_popularity import get_popularity_score as _pop_lookup


def _base_pokemon_name(card_name: str) -> str:
    if " & " in card_name:
        card_name = card_name.split(" & ")[0].strip()
    return _SUFFIX_RE.sub("", card_name).strip()


def _popularity_score(card_name: str) -> float:
    """Return 0-100 fan popularity score from pokemon_popularity.py."""
    base = _base_pokemon_name(card_name)
    return float(_pop_lookup(base))


def _card_era(card_id: str) -> str:
    """Return era string from a card id like 'base1-4'."""
    prefix = re.sub(r"\d+", "", card_id.split("-")[0]).lower()
    if prefix in _VINTAGE:   return "vintage"
    if prefix in _OLDSCHOOL: return "oldschool"
    if prefix in _CLASSIC:   return "classic"
    if prefix in _MODERN:    return "modern"
    return "recent"


def _scarcity_score(card_details: dict) -> float:
    """Return 0-100 scarcity score from set era and rarity."""
    era = _card_era(card_details.get("id", "recent-0"))
    rarity = card_details.get("rarity", "Common")
    base = _ERA_SCARCITY.get(era, 10)
    bonus = _RARITY_SCARCITY_BONUS.get(rarity, 0)
    return min(100.0, float(base + bonus))


def _simulate_graded(raw_price: float, card_details: dict) -> tuple[float, float]:
    """Return simulated (psa9_price, psa10_price) from raw price."""
    era = _card_era(card_details.get("id", "recent-0"))
    rarity = card_details.get("rarity", "Common")
    psa9_mult, psa10_mult = _GRADE_MULTIPLIERS.get((era, rarity), _GRADE_DEFAULT)
    return round(raw_price * psa9_mult, 2), round(raw_price * psa10_mult, 2)


def _load_card_db() -> list:
    """Lazily load all card dicts for pull-odds counting."""
    global _card_db_cache
    if _card_db_cache is not None:
        return _card_db_cache
    try:
        import sys as _sys
        _sys.path.insert(0, os.path.dirname(__file__))
        from card_db import CardDatabase
        _card_db_cache = CardDatabase()._cards
    except Exception:
        _card_db_cache = []
    return _card_db_cache


def _pull_odds_packs(card_details: dict) -> tuple[float, float]:
    """
    Return (packs_to_pull, era_weight) for this specific card.

    packs_to_pull  — average packs needed to pull this exact card from a
                     fresh booster. Uses per-set community data where
                     available, falls back to era-based estimates.
    era_weight     — 0.0–1.0 scaling factor that reduces the pull-odds
                     contribution for older sets where packs are no longer
                     actively opened (secondary market dominates pricing).
    """
    era      = _card_era(card_details.get("id", "recent-0"))
    rarity   = card_details.get("rarity", "Common")
    set_code = card_details.get("id", "").rsplit("-", 1)[0]

    # 1. Per-set rate (most accurate) → era-based fallback
    set_rates = _SET_PULL_RATES.get(set_code, {})
    base_rate = (set_rates.get(rarity)
                 or _ERA_PULL_RATES.get((era, rarity), _PULL_RATE_DEFAULT))

    # 2. Count how many distinct cards share this rarity in the set
    cards = _load_card_db()
    count_in_set = sum(
        1 for c in cards
        if c.get("id", "").rsplit("-", 1)[0] == set_code
        and c.get("rarity") == rarity
    ) or 1

    packs_to_pull = base_rate * count_in_set
    era_weight    = _PULL_ODDS_ERA_WEIGHT.get(era, 1.0)
    return float(packs_to_pull), era_weight


def _parse_price(price_str) -> float | None:
    if isinstance(price_str, (int, float)):
        return float(price_str)
    if not price_str:
        return None
    match = re.search(r"\d+\.?\d*", str(price_str).replace(",", ""))
    return float(match.group()) if match else None


def _null_result(card_name: str) -> dict:
    return {
        "card_name":         card_name,
        "num_sales":         0,
        "average_price":     None,
        "median_price":      None,
        "lowest_price":      None,
        "highest_price":     None,
        "trend":             None,
        "trend_pct_change":  None,
        "volatility":        None,
        "volatility_std":    None,
        "rarity_baseline":   None,
        "popularity_score":  None,
        "scarcity_score":    None,
        "pull_odds_packs":   None,
        "composite_score":   None,
        "recommendation":    "Insufficient Data",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_VARIANT_SCARCITY_FLOOR: dict[str, float] = {
    "1st edition shadowless": 90.0,
    "1st edition":            82.0,
    "shadowless":             72.0,
}
_VARIANT_COMPOSITE_BONUS: dict[str, float] = {
    "1st edition shadowless": 20.0,
    "1st edition":            15.0,
    "shadowless":              8.0,
}


def analyze_card(
    card_name: str,
    prices_list: list[dict],
    card_details: dict | None = None,
    variant: str = "",
) -> dict:
    """
    Analyze sold listing data and return a valuation dictionary.

    Composite score (-100 to +100) is built from eight components:
      A  Price vs average      18 % — recent sale vs mean; below = potential bargain
      B  Trend                 13 % — 5 newest vs 5 oldest sales
      C  Volatility             9 % — coefficient of variation
      D  Rarity baseline        5 % — price vs expected range for its rarity tier
      E  Popularity            25 % — Google Trends 12-month interest (from popularity.csv)
      F  Scarcity              15 % — set era age + rarity tier
      H  Pull odds             15 % — avg packs to pull this specific card from a pack
    """

    # 1. Parse prices
    parsed = [v for v in (_parse_price(l.get("price")) for l in prices_list) if v is not None]
    if len(parsed) < 5:
        return _null_result(card_name)

    # 2. Summary stats
    avg     = statistics.mean(parsed)
    median  = statistics.median(parsed)
    low     = min(parsed)
    high    = max(parsed)
    std_dev = statistics.stdev(parsed)

    # 3. Trend — linear regression over the last 10 price points (or all if fewer).
    # Requires at least 6 distinct prices to be meaningful; if all prices are
    # identical (e.g. single API snapshot padded to 5) mark as "no data".
    trend_window = parsed[:10]
    if len(set(trend_window)) < 3:
        # All prices are the same — single API snapshot, no trend possible
        trend     = "no data"
        trend_pct = 0.0
    else:
        n       = len(trend_window)
        xs      = list(range(n))          # 0 = most recent, n-1 = oldest
        x_mean  = sum(xs) / n
        y_mean  = sum(trend_window) / n
        numer   = sum((xs[i] - x_mean) * (trend_window[i] - y_mean) for i in range(n))
        denom   = sum((xs[i] - x_mean) ** 2 for i in range(n))
        slope   = numer / denom if denom else 0.0
        # slope is price-change per step going forward in time (negative x = newer)
        # positive slope means price was HIGHER recently → falling toward past
        # negative slope means price was LOWER recently → rising toward past
        # flip sign so positive = price rising over time
        trend_pct = round(-slope / y_mean * 100, 1) if y_mean else 0.0
        trend     = "rising" if trend_pct > 3 else ("falling" if trend_pct < -3 else "stable")

    # 4. Volatility
    cv = (std_dev / avg) if avg else 0.0
    volatility = "stable" if cv < 0.15 else ("moderate" if cv < 0.30 else "volatile")

    # 5. Rarity baseline
    rarity_baseline = None
    if card_details:
        rarity = card_details.get("rarity")
        if rarity in RARITY_RANGES:
            lo, hi = RARITY_RANGES[rarity]
            rarity_baseline = ("below range" if avg < lo else
                               "above range" if avg > hi else "within range")

    # 6. Popularity
    pop_score = _popularity_score(card_name)

    # 7. Scarcity — base score + printing floor for display; direct composite
    #    bonus bypasses the 100 cap so vintage variants still show differentiation
    scar_score = _scarcity_score(card_details) if card_details else 10.0
    v_lower = variant.lower()
    variant_comp_bonus = 0.0
    for key in _VARIANT_SCARCITY_FLOOR:
        if key in v_lower:
            scar_score = max(scar_score, _VARIANT_SCARCITY_FLOOR[key])
            variant_comp_bonus = _VARIANT_COMPOSITE_BONUS[key]
            break

    # 8. Pull odds
    pull_packs, pull_era_w = _pull_odds_packs(card_details) if card_details else (6.0, 1.0)

    # ------------------------------------------------------------------
    # Composite score
    # Weights: A 18%  B 13%  C 9%  D 5%  E 25%  F 15%  H 15% = 100%
    # ------------------------------------------------------------------
    most_recent = parsed[0]

    # A — price vs average (weight 18 %)
    dev_pct = (avg - most_recent) / avg * 100 if avg else 0.0
    comp_a  = max(-50.0, min(50.0, dev_pct)) * 0.18

    # B — trend (weight 13 %; neutral when no trend data available)
    comp_b  = {"falling": 50, "stable": 0, "rising": -50, "no data": 0}.get(trend, 0) * 0.13

    # C — volatility (weight 9 %)
    comp_c  = {"stable": 30, "moderate": 0, "volatile": -30}[volatility] * 0.09

    # D — rarity baseline (weight 5 %)
    comp_d  = {"below range": 50, "within range": 0, "above range": -50,
               None: 0}.get(rarity_baseline, 0) * 0.05

    # E — popularity (weight 25 %)
    pop_raw = max(-50.0, min(50.0, (pop_score - 15.0) * (50.0 / 85.0)))
    comp_e  = pop_raw * 0.25

    # F — scarcity (weight 15 %)
    scar_raw = max(-50.0, min(50.0, (scar_score - 30.0) * (50.0 / 70.0)))
    comp_f   = scar_raw * 0.15

    # H — pull odds (up to 15 %, scaled down for older eras)
    # Log scale: breakeven at ~20 packs; SIRs at 350-900 packs → near +50.
    # Era weight: vintage cards get only 10% of this signal since their
    # prices are driven by secondary market scarcity, not pack openings.
    pull_raw = max(-50.0, min(50.0,
        (math.log(pull_packs + 1) - math.log(21)) / math.log(17) * 50.0
    ))
    comp_h  = pull_raw * 0.15 * pull_era_w

    composite_score = round(comp_a + comp_b + comp_c + comp_d + comp_e + comp_f + comp_h + variant_comp_bonus, 1)

    # Recommendation — positive score = overvalued (sell), negative = undervalued (buy)
    if composite_score >= 60:
        rec = "Strong Sell"
    elif composite_score >= 25:
        rec = "Sell"
    elif composite_score > -25:
        rec = "Hold"
    elif composite_score > -60:
        rec = "Buy"
    else:
        rec = "Strong Buy"

    return {
        "card_name":         card_name,
        "num_sales":         len(parsed),
        "average_price":     round(avg, 2),
        "median_price":      round(median, 2),
        "lowest_price":      round(low, 2),
        "highest_price":     round(high, 2),
        "trend":             trend,
        "trend_pct_change":  round(trend_pct, 1),
        "volatility":        volatility,
        "volatility_std":    round(std_dev, 2),
        "rarity_baseline":   rarity_baseline,
        "popularity_score":  round(pop_score, 1),
        "scarcity_score":    round(scar_score, 1),
        "pull_odds_packs":   round(pull_packs, 1),
        "composite_score":   composite_score,
        "recommendation":    rec,
    }


# ---------------------------------------------------------------------------
# Smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    base_charizard = {
        "id": "base1-4", "name": "Charizard", "rarity": "Rare Holo",
    }
    modern_pikachu = {
        "id": "sm1-35", "name": "Pikachu", "rarity": "Common",
    }
    recent_common = {
        "id": "sv1-50", "name": "Magnemite", "rarity": "Common",
    }

    listings = [{"price": f"${p:.2f}"} for p in
                [45, 48, 42, 50, 47, 55, 60, 58, 62, 65,
                 63, 61, 59, 57, 55, 53, 51, 49, 47, 45]]

    for label, details in [
        ("Base Set Charizard (vintage Rare Holo)", base_charizard),
        ("SM Pikachu (modern Common)",             modern_pikachu),
        ("SV Magnemite (recent Common)",           recent_common),
    ]:
        result = analyze_card(details["name"], listings, details)
        print(f"\n=== {label} ===")
        for k, v in result.items():
            print(f"  {k:<22}: {v}")

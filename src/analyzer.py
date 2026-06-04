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
# Sourced from community pack-opening data and official set disclosures.
# ---------------------------------------------------------------------------
_PULL_RATES: dict[tuple, int] = {
    # Vintage (Base, Jungle, Fossil, Gym, Neo) — ~1/9 for holo slot
    ("vintage",   "Rare Holo"):              9,
    ("vintage",   "Rare"):                   5,
    ("vintage",   "Uncommon"):               2,
    ("vintage",   "Common"):                 1,
    # e-Card / EX series (2002-2007)
    ("oldschool", "Rare Holo"):             12,
    ("oldschool", "Rare Ultra"):            36,
    ("oldschool", "Rare"):                   6,
    ("oldschool", "Uncommon"):               2,
    ("oldschool", "Common"):                 1,
    # DP / HGSS / BW (2007-2013)
    ("classic",   "Rare Holo"):             12,
    ("classic",   "Rare Prime"):            18,
    ("classic",   "Rare Ultra"):            18,
    ("classic",   "Rare Secret"):           36,
    ("classic",   "Rare Holo LV.X"):        18,
    ("classic",   "Rare"):                   6,
    # XY / SM (2014-2019)
    ("modern",    "Rare Holo"):              8,
    ("modern",    "Rare Holo EX"):           8,
    ("modern",    "Rare Holo GX"):           8,
    ("modern",    "Ultra Rare"):            18,
    ("modern",    "Rare Ultra"):            18,
    ("modern",    "Rare Secret"):           36,
    ("modern",    "Rare Rainbow"):          60,
    ("modern",    "Rare Shiny"):            20,
    ("modern",    "Rare Shiny GX"):         60,
    # SWSH / SV (2020-present)
    ("recent",    "Rare Holo"):              8,
    ("recent",    "Rare Holo V"):            8,
    ("recent",    "Rare Holo VMAX"):         8,
    ("recent",    "Rare Holo VSTAR"):        8,
    ("recent",    "Double Rare"):            8,
    ("recent",    "ACE SPEC Rare"):         35,
    ("recent",    "Ultra Rare"):            12,
    ("recent",    "Illustration Rare"):      8,
    ("recent",    "Special Illustration Rare"): 70,
    ("recent",    "Hyper Rare"):            70,
    ("recent",    "Rare Rainbow"):          60,
    ("recent",    "Rare Secret"):           20,
    ("recent",    "Trainer Gallery Rare Holo"): 18,
}
_PULL_RATE_DEFAULT = 6   # fallback for unrecognised rarity/era combos

# Module-level cache for popularity data so the CSV is only read once
_popularity_cache: dict[str, float] | None = None
# Module-level cache for the card DB (used for pull-odds counting)
_card_db_cache: list | None = None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _load_popularity() -> dict[str, float]:
    global _popularity_cache
    if _popularity_cache is not None:
        return _popularity_cache

    path = os.path.join(os.path.dirname(__file__), "..", "data", "popularity.csv")
    scores: dict[str, float] = {}
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                scores[row["name"].lower()] = float(row["score"])
    _popularity_cache = scores
    return scores


def _base_pokemon_name(card_name: str) -> str:
    if " & " in card_name:
        card_name = card_name.split(" & ")[0].strip()
    return _SUFFIX_RE.sub("", card_name).strip()


def _popularity_score(card_name: str) -> float:
    """Return 0-100 Google Trends score; 0 if not found in popularity.csv."""
    scores = _load_popularity()
    base = _base_pokemon_name(card_name).lower()
    return scores.get(base, 0.0)


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


def _pull_odds_packs(card_details: dict) -> float:
    """
    Return the average number of packs needed to pull THIS specific card.

    Formula:  packs_to_pull = base_rate_for_rarity × cards_of_same_rarity_in_set

    A common card might need 3 packs on average; a specific Special
    Illustration Rare in a 5-SIR set (1/70 rate) needs 350 packs.
    """
    era    = _card_era(card_details.get("id", "recent-0"))
    rarity = card_details.get("rarity", "Common")
    set_code = card_details.get("id", "").rsplit("-", 1)[0]

    base_rate = _PULL_RATES.get((era, rarity), _PULL_RATE_DEFAULT)

    cards = _load_card_db()
    count_in_set = sum(
        1 for c in cards
        if c.get("id", "").rsplit("-", 1)[0] == set_code
        and c.get("rarity") == rarity
    ) or 1

    return float(base_rate * count_in_set)


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

def analyze_card(
    card_name: str,
    prices_list: list[dict],
    card_details: dict | None = None,
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

    # 7. Scarcity
    scar_score = _scarcity_score(card_details) if card_details else 10.0

    # 8. Pull odds
    pull_packs = _pull_odds_packs(card_details) if card_details else 6.0

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

    # H — pull odds (weight 15 %)
    # Map log(packs_to_pull) onto -50 to +50.
    # Breakeven at ~20 packs (common rare holo); hard-to-pull SIRs (350+) → +50.
    # log scale so the difference between 1 and 20 packs is visible, not just 1 vs 350.
    pull_raw = max(-50.0, min(50.0,
        (math.log(pull_packs + 1) - math.log(21)) / math.log(17) * 50.0
    ))
    comp_h  = pull_raw * 0.15

    composite_score = round(comp_a + comp_b + comp_c + comp_d + comp_e + comp_f + comp_h, 1)

    # Recommendation
    if composite_score > 60:
        rec = "Strong Buy"
    elif composite_score > 30:
        rec = "Buy"
    elif composite_score >= -30:
        rec = "Fair Value"
    elif composite_score >= -60:
        rec = "Sell"
    else:
        rec = "Strong Sell"

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

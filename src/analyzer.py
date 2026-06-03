import csv
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

# Module-level cache for popularity data so the CSV is only read once
_popularity_cache: dict[str, float] | None = None


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

    Composite score (-100 to +100) is built from seven components:
      A  Price vs average      20 % — recent sale vs mean; below = potential bargain
      B  Trend                 15 % — 5 newest vs 5 oldest sales
      C  Volatility            10 % — coefficient of variation
      D  Rarity baseline       10 % — price vs expected range for its rarity tier
      E  Popularity            25 % — Google Trends 12-month interest (from popularity.csv)
      F  Scarcity              15 % — set era age + rarity tier
      G  Grade premium          5 % — implied PSA 10 upside over raw price
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

    # 3. Trend (most-recent-first assumed)
    recent_avg = statistics.mean(parsed[:5])
    oldest_avg = statistics.mean(parsed[-5:])
    trend_pct  = (recent_avg - oldest_avg) / oldest_avg * 100 if oldest_avg else 0.0
    trend      = "rising" if trend_pct > 5 else ("falling" if trend_pct < -5 else "stable")

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

    # ------------------------------------------------------------------
    # Composite score
    # Weights: A 20%  B 15%  C 10%  D 10%  E 25%  F 20%  = 100%
    # ------------------------------------------------------------------
    most_recent = parsed[0]

    # A — price vs average (clamped deviation ±50, weight 20 %)
    dev_pct = (avg - most_recent) / avg * 100 if avg else 0.0
    comp_a  = max(-50.0, min(50.0, dev_pct)) * 0.20

    # B — trend (weight 15 %)
    comp_b  = {"falling": 50, "stable": 0, "rising": -50}[trend] * 0.15

    # C — volatility (weight 10 %)
    comp_c  = {"stable": 30, "moderate": 0, "volatile": -30}[volatility] * 0.10

    # D — rarity baseline (weight 10 %)
    comp_d  = {"below range": 50, "within range": 0, "above range": -50,
               None: 0}.get(rarity_baseline, 0) * 0.10

    # E — popularity (weight 25 %)
    pop_raw = max(-50.0, min(50.0, (pop_score - 15.0) * (50.0 / 85.0)))
    comp_e  = pop_raw * 0.25

    # F — scarcity (weight 20 %, increased from 15 % now PSA signal removed)
    scar_raw = max(-50.0, min(50.0, (scar_score - 30.0) * (50.0 / 70.0)))
    comp_f   = scar_raw * 0.20

    composite_score = round(comp_a + comp_b + comp_c + comp_d + comp_e + comp_f, 1)

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

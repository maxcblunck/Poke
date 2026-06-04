"""
Calculates a simulated market price for a Pokemon card based on its full
card dict from CardDatabase, using a weighted multiplier system.

Weights sum to 1.0:
  popularity  0.30
  nostalgia   0.15
  subtype     0.10
  age         0.08
  ability     0.05
  secret      0.03
  neutral     0.29  (remainder so all weights total 1.0)
"""

import re

# ---------------------------------------------------------------------------
# 1. Base price by rarity tier
# ---------------------------------------------------------------------------
BASE_PRICES: dict[str, float] = {
    # Standard
    "Common":                     0.25,
    "Uncommon":                   0.75,
    "Rare":                       3.00,
    "Rare Holo":                  8.00,
    # Modern V/VMAX/GX/EX holos
    "Rare Holo V":               10.00,
    "Rare Holo VMAX":            18.00,
    "Rare Holo VSTAR":           15.00,
    "Rare Holo GX":               8.00,
    "Rare Holo EX":               8.00,
    "Double Rare":               15.00,
    "ACE SPEC Rare":             35.00,
    # Full arts / ultra rares
    "Rare Ultra":                30.00,
    "Ultra Rare":                25.00,
    "Illustration Rare":         20.00,
    # Secret / rainbow / alt arts — priced conservatively;
    # real prices vary hugely by Pokemon popularity.
    # The popularity multiplier in valuate_card() pushes these up.
    "Rare Rainbow":              60.00,   # rainbow secret rares (SWSH era)
    "Rare Secret":               75.00,   # gold secret rares
    "Special Illustration Rare": 80.00,   # alt arts (SV era)
    "Hyper Rare":                55.00,   # gold full arts (SV era)
    # Trainer Gallery / Shiny
    "Trainer Gallery Rare Holo": 20.00,
    "Rare Shiny":                30.00,
    "Rare Shiny GX":             50.00,
}
DEFAULT_BASE_PRICE = 2.00  # unknown rarity — at least worth more than $1

# ---------------------------------------------------------------------------
# 2. Character popularity tiers (checked via case-insensitive substring match)
# ---------------------------------------------------------------------------
_POP_TIERS: list[tuple[float, set[str]]] = [
    (3.0, {"Charizard", "Pikachu", "Mewtwo"}),
    (2.0, {"Mew", "Eevee", "Gengar", "Lugia", "Rayquaza", "Umbreon"}),
    (1.5, {"Blastoise", "Venusaur", "Garchomp", "Dragonite",
           "Gyarados", "Snorlax", "Alakazam", "Arcanine"}),
]

# ---------------------------------------------------------------------------
# 5. Set age multipliers keyed by the alphabetic prefix of the set ID
#    (e.g. "base1" → "base", "swsh3" → "swsh")
# ---------------------------------------------------------------------------
_AGE_MAP: dict[str, float] = {
    # 1999–2000
    "base": 2.5, "jungle": 2.5, "fossil": 2.5,
    "rocket": 2.5, "gym": 2.5, "basep": 2.5, "bp": 2.5,
    # 2000–2002
    "neo": 2.0, "legendary": 2.0, "expedition": 2.0, "np": 2.0,
    # 2003–2007
    "ex": 1.6, "ecard": 1.6, "pop": 1.6,
    # 2007–2011
    "dp": 1.3, "dpp": 1.3, "pl": 1.3,
    "hgss": 1.3, "hsp": 1.3, "col": 1.3,
    # 2011–2016
    "bw": 1.2, "bwp": 1.2, "dv": 1.2,
    "xy": 1.2, "dc": 1.2, "det": 1.2, "g": 1.2,
    # 2017–2019
    "sm": 1.1, "smp": 1.1, "cel": 1.1,
    # 2020–2023
    "swsh": 1.05, "sve": 1.05, "me": 1.05,
    "shf": 1.05, "cpa": 1.05, "fut": 1.05,
    # 2023+ (Scarlet & Violet)
    "sv": 1.0, "svp": 1.0, "rsv": 1.0,
}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _popularity_mult(card_name: str) -> float:
    name_lower = card_name.lower()
    for mult, names in _POP_TIERS:
        if any(n.lower() in name_lower for n in names):
            return mult
    return 1.0


def _nostalgia_mult(card: dict) -> float:
    dex = card.get("nationalPokedexNumbers") or []
    return 1.4 if dex and dex[0] <= 151 else 1.0


def _subtype_mult(card: dict) -> float:
    subtypes = {s.upper() for s in (card.get("subtypes") or [])}
    if subtypes & {"VMAX", "VSTAR"}:
        return 2.0
    if subtypes & {"MEGA", "LEGEND"}:
        return 1.8
    if subtypes & {"EX", "GX", "V"}:
        return 1.6
    if "STAGE 2" in subtypes:
        return 1.2
    return 1.0


def _age_mult(card: dict) -> float:
    card_id = card.get("id", "")
    set_code = card_id.split("-")[0].lower()          # "base1-4" → "base1"
    prefix   = re.sub(r"\d+", "", set_code)           # "base1"   → "base"
    return _AGE_MAP.get(prefix, 1.0)


def _ability_mult(card: dict) -> float:
    return 1.3 if card.get("abilities") else 1.0


def _secret_mult(card: dict) -> float:
    number = str(card.get("number", ""))
    if re.search(r"[a-zA-Z]", number):                # e.g. TG01, GG01
        return 1.5
    try:
        if int(number) > 200:
            return 1.5
    except ValueError:
        pass
    return 1.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def valuate_card(card: dict) -> dict:
    """
    Return a valuation dict for a card dict from CardDatabase.

    Keys:
      base_price          — starting price for the rarity tier
      combined_multiplier — weighted combination of all signals
      simulated_price     — base_price * combined_multiplier
      desirability_score  — 0-100, normalised against a max of 4.0
      breakdown           — individual multiplier values
    """
    rarity     = card.get("rarity", "")
    base_price = BASE_PRICES.get(rarity, DEFAULT_BASE_PRICE)
    name       = card.get("name", "")

    pop_mult  = _popularity_mult(name)
    nos_mult  = _nostalgia_mult(card)
    sub_mult  = _subtype_mult(card)
    age_mult  = _age_mult(card)
    abl_mult  = _ability_mult(card)
    sec_mult  = _secret_mult(card)

    combined = (
        pop_mult * 0.30
        + nos_mult * 0.15
        + sub_mult * 0.10
        + age_mult * 0.08
        + abl_mult * 0.05
        + sec_mult * 0.03
        + 1.0    * 0.29   # neutral remainder so weights sum to 1.0
    )

    simulated_price   = round(base_price * combined, 2)
    desirability_score = round(min(100.0, combined / 4.0 * 100), 1)

    return {
        "base_price":          base_price,
        "combined_multiplier": round(combined, 4),
        "simulated_price":     simulated_price,
        "desirability_score":  desirability_score,
        "breakdown": {
            "popularity_mult": pop_mult,
            "nostalgia_mult":  nos_mult,
            "subtype_mult":    sub_mult,
            "age_mult":        age_mult,
            "ability_mult":    abl_mult,
            "secret_mult":     sec_mult,
        },
    }


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from card_db import CardDatabase

    db = CardDatabase()

    test_cards = [
        ("Charizard",  "Base",   "4"),
        ("Pikachu",    "Base",   "58"),
        ("Abra",       "Base",   "43"),
    ]

    for name, set_prefix, number in test_cards:
        matches = [c for c in db._cards
                   if c.get("name") == name
                   and c.get("id", "").startswith(set_prefix.lower())]
        card = next((c for c in matches if str(c.get("number")) == number), None)
        if not card:
            print(f"Card not found: {name} #{number}\n")
            continue

        result = valuate_card(card)
        print(f"=== {name} (#{number}, {card.get('rarity')}, set {card.get('id','').split('-')[0]}) ===")
        print(f"  Base price          : ${result['base_price']:.2f}")
        print(f"  Combined multiplier : {result['combined_multiplier']:.4f}")
        print(f"  Simulated price     : ${result['simulated_price']:.2f}")
        print(f"  Desirability score  : {result['desirability_score']}/100")
        print(f"  Breakdown:")
        for k, v in result["breakdown"].items():
            print(f"    {k:<20}: {v:.2f}")
        print()

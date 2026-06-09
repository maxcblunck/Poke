import json
import os
import re
import sys
import random
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=False)
except ImportError:
    pass

POKEWALLET_BASE_URL  = "https://api.pokewallet.io"
POKEWALLET_API_KEY   = os.getenv("POKEWALLET_API_KEY", "")
POKETRACE_BASE_URL   = "https://api.poketrace.com/v1"
POKETRACE_API_KEY    = os.getenv("POKETRACE_API_KEY", "")
TCGPLAYER_BASE_URL     = "https://api.tcgplayer.com/v1.32.0"
TCGPLAYER_CLIENT_ID    = os.getenv("TCGPLAYER_CLIENT_ID", "")
TCGPLAYER_CLIENT_SECRET = os.getenv("TCGPLAYER_CLIENT_SECRET", "")
_SETS_CACHE_PATH     = os.path.join(os.path.dirname(__file__), "..", "data", "pokewallet_sets.json")
_sets_cache: list | None = None
_set_language: dict[str, str] = {}   # set_id → language, populated alongside _sets_cache
_poketrace_id_cache: dict[str, str | None] = {}   # card_local_id → PokeTrace UUID
_tcg_token_cache: dict = {}            # {"token": str, "expires_at": float}
_tcg_product_cache: dict[str, int | None] = {}   # card_local_id → TCGPlayer productId

_IR_RARITIES = frozenset({"Illustration Rare", "Special Illustration Rare", "Hyper Rare", "Mega Hyper Rare"})


def _get_pokewallet_sets() -> list:
    """
    Return the PokéWallet sets list, loading from disk cache if available,
    otherwise fetching from the API and saving to disk for future calls.
    The cache avoids burning API quota on every card lookup.
    """
    global _sets_cache
    if _sets_cache is not None:
        return _sets_cache

    if os.path.exists(_SETS_CACHE_PATH):
        try:
            with open(_SETS_CACHE_PATH, encoding="utf-8") as f:
                _sets_cache = json.load(f)
                _set_language.update({
                    str(s["set_id"]): (s.get("language") or "eng")
                    for s in _sets_cache
                })
                return _sets_cache
        except Exception:
            pass

    api_key = POKEWALLET_API_KEY or os.environ.get("POKEWALLET_API_KEY", "")
    if not api_key:
        return []
    try:
        resp = requests.get(
            f"{POKEWALLET_BASE_URL}/sets",
            headers={"X-API-Key": api_key},
            timeout=30,
        )
        if resp.status_code == 200:
            _sets_cache = resp.json().get("data", [])
            _set_language.update({
                str(s["set_id"]): (s.get("language") or "eng")
                for s in _sets_cache
            })
            os.makedirs(os.path.dirname(os.path.abspath(_SETS_CACHE_PATH)), exist_ok=True)
            with open(_SETS_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(_sets_cache, f)
            return _sets_cache
    except Exception:
        pass
    return []


def _api_set_id_for(local_id: str) -> str | None:
    """
    Map a local card id like 'hgss1-108' to the PokéWallet API set_id.

    Tries three strategies in order:
    1. Hardcoded table — for sets where count-based matching is ambiguous
       (local DB includes secret rares; API card_count does not).
    2. Exact count match + set_code prefix overlap.
    3. Returns None — caller falls back to name-only search.
    """
    if not local_id or "-" not in local_id:
        return None
    set_code = local_id.rsplit("-", 1)[0]

    # ── 1. Hardcoded overrides ──────────────────────────────────────
    # Verified against the PokéWallet API sets list (data/pokewallet_sets.json).
    # Covers all major English sets so the scraper never falls back to fuzzy
    # count-matching, which is ambiguous for sets with secret rares.
    _KNOWN: dict[str, str] = {
        # Base / Vintage (1999-2002)
        "base1":  "604",    # Base Set
        "base2":  "635",    # Jungle
        "base3":  "630",    # Fossil
        "base4":  "605",    # Base Set 2
        "base5":  "1373",   # Team Rocket
        "base6":  "1374",   # Legendary Collection
        "gym1":   "1441",   # Gym Heroes
        "gym2":   "24202",  # Gym Challenge
        # Neo (2000-2002)
        "neo1":   "-128",   # Neo Genesis
        "neo2":   "-129",   # Neo Discovery
        "neo3":   "-130",   # Neo Revelation  (also 1389)
        "neo4":   "1444",   # Neo Destiny
        # e-Card / Expedition (2002-2003)
        "ecard1": "-93",    # Expedition Base Set
        "ecard2": "1397",   # Aquapolis
        "ecard3": "1372",   # Skyridge
        # EX Series (2003-2007)
        "ex1":    "1393",   # Ruby & Sapphire
        "ex2":    "1392",   # Sandstorm
        "ex3":    "1376",   # Dragon
        "ex4":    "1377",   # Team Magma vs Team Aqua
        "ex5":    "1416",   # Hidden Legends
        "ex6":    "1419",   # FireRed & LeafGreen
        "ex7":    "1428",   # Team Rocket Returns
        "ex8":    "1404",   # Deoxys
        "ex9":    "1410",   # Emerald
        "ex10":   "1398",   # Unseen Forces
        "ex11":   "1429",   # Delta Species
        "ex12":   "1378",   # Legend Maker
        "ex13":   "1379",   # Holon Phantoms
        "ex14":   "1395",   # Crystal Guardians
        "ex15":   "1411",   # Dragon Frontiers
        "ex16":   "-91",    # Power Keepers
        # Diamond & Pearl (2007-2009)
        "dp1":    "1430",   # Diamond and Pearl
        "dp2":    "1368",   # Mysterious Treasures
        "dp3":    "1380",   # Secret Wonders
        "dp4":    "1405",   # Great Encounters
        "dp5":    "1390",   # Majestic Dawn
        "dp6":    "1417",   # Legends Awakened
        "dp7":    "1369",   # Stormfront
        "pl1":    "1406",   # Platinum
        "pl2":    "1367",   # Rising Rivals
        "pl3":    "1384",   # Supreme Victors
        "pl4":    "1391",   # Arceus
        # HeartGold SoulSilver (2010-2011)
        "hgss1":  "1402",   # HeartGold SoulSilver
        "hgss2":  "1399",   # Unleashed
        "hgss3":  "1403",   # Undaunted
        "hgss4":  "1381",   # Triumphant
        "col1":   "1415",   # Call of Legends
        # Black & White (2011-2013)
        "bw1":    "1400",   # Black and White
        "bw2":    "1424",   # Emerging Powers
        "bw3":    "1385",   # Noble Victories
        "bw4":    "-126",   # Next Destinies
        "bw5":    "1386",   # Dark Explorers
        "bw6":    "-85",    # Dragons Exalted
        "bw7":    "1408",   # Boundaries Crossed
        "bw8":    "1413",   # Plasma Storm
        "bw9":    "1382",   # Plasma Freeze
        "bw10":   "1370",   # Plasma Blast
        "bw11":   "1409",   # Legendary Treasures
        # XY (2013-2016)
        "xy1":    "1387",   # XY Base Set
        "xy2":    "1464",   # Flashfire
        "xy3":    "1481",   # Furious Fists
        "xy4":    "1494",   # Phantom Forces
        "xy5":    "1509",   # Primal Clash
        "xy6":    "1534",   # Roaring Skies
        "xy7":    "1576",   # Ancient Origins
        "xy8":    "1661",   # BREAKthrough
        "xy9":    "2175",   # BREAKpoint
        "xy10":   "1780",   # Fates Collide
        "xy11":   "1815",   # Steam Siege
        "xy12":   "1842",   # Evolutions
        # Sun & Moon (2017-2019)
        "sm1":    "1880",   # Sun & Moon
        "sm2":    "1919",   # Guardians Rising
        "sm3":    "1957",   # Burning Shadows
        "sm4":    "2071",   # Crimson Invasion
        "sm5":    "2178",   # Ultra Prism
        "sm6":    "2209",   # Forbidden Light
        "sm7":    "2278",   # Celestial Storm
        "sm8":    "2295",   # Dragon Majesty
        "sm9":    "2377",   # Team Up
        "sm10":   "2420",   # Unbroken Bonds
        "sm11":   "2464",   # Unified Minds
        "sm12":   "2534",   # Cosmic Eclipse
        # Sword & Shield (2020-2023)
        "swsh1":  "-171",   # Sword & Shield Base Set
        "swsh2":  "2626",   # Rebel Clash
        "swsh3":  "2675",   # Darkness Ablaze
        "swsh4":  "2701",   # Vivid Voltage
        "swsh5":  "2765",   # Battle Styles
        "swsh6":  "2807",   # Chilling Reign
        "swsh7":  "2848",   # Evolving Skies
        "swsh8":  "2906",   # Fusion Strike
        "swsh9":  "2948",   # Brilliant Stars
        "swsh10": "3040",   # Astral Radiance
        "swsh11": "3118",   # Lost Origin
        "swsh12": "3170",   # Silver Tempest
        # Scarlet & Violet (2023-)
        "sv1":    "22873",  # Scarlet & Violet Base Set
        "sv2":    "23120",  # Paldea Evolved
        "sv3":    "23228",  # Obsidian Flames
        "sv3pt5": "23237",  # Pokémon 151
        "sv4":    "23286",  # Paradox Rift
        "sv4pt5": "23353",  # Paldean Fates
        "sv5":    "23381",  # Temporal Forces
        "sv6":    "23473",  # Twilight Masquerade
        "sv6pt5": "23529",  # Shrouded Fable
        "sv7":    "23537",  # Stellar Crown
        "sv8":    "23651",  # Surging Sparks
        # Celebrations (2021)
        "cel25":  "2867",   # Celebrations
        "cel25c": "2931",   # Celebrations: Classic Collection
        # SWSH subsets & Trainer Galleries
        "swsh35":     "2685",   # Champion's Path
        "swsh45":     "2754",   # Shining Fates
        "swsh9tg":    "3020",   # Brilliant Stars Trainer Gallery
        "swsh10tg":   "3068",   # Astral Radiance Trainer Gallery
        "swsh11tg":   "3172",   # Lost Origin Trainer Gallery
        "swsh12tg":   "17674",  # Silver Tempest Trainer Gallery
        "swsh12pt5":  "17688",  # Crown Zenith
        "swsh12pt5gg":"17689",  # Crown Zenith: Galarian Gallery
        # SM subsets
        "sm35":   "2480",   # Hidden Fates
        "sm75":   "2295",   # Dragon Majesty
        "sm115":  "2054",   # Shining Legends
        "sma":    "2594",   # Hidden Fates: Shiny Vault
        "smp":    "1861",   # SM Promos
        # SV subsets
        "sv8pt5": "23821",  # Prismatic Evolutions (180 cards)
        "sv9":    "24073",  # Journey Together (190 cards)
        "sv10":   "24269",  # Destined Rivals (244 cards)
        "sve":    "22873",  # SV Energy (within main SV base set)
        "zsv10pt5":"17688", # Crown Zenith (alt code)
        "rsv10pt5":"17688", # Crown Zenith (alt code)
        # Promo sets
        "basep":  "-193",   # Wizards Black Star Promos
        "bp":     "-193",   # Wizards Black Star Promos
        "np":     "1423",   # Nintendo Promos
        "hsp":    "1453",   # HGSS Promos
        "xyp":    "1451",   # XY Promos
        # POP Series
        "pop1":   "1422",   # POP Series 1
        "pop2":   "1447",   # POP Series 2
        "pop3":   "1442",   # POP Series 3
        "pop4":   "1452",   # POP Series 4
        "pop5":   "1439",   # POP Series 5
        "pop6":   "1432",   # POP Series 6
        "pop7":   "1414",   # POP Series 7
        "pop8":   "1450",   # POP Series 8
        "pop9":   "1446",   # POP Series 9
        # McDonald's promos
        "mcd21":  "2782",   # McDonald's 25th Anniversary
        "mcd22":  "3150",   # McDonald's 2022
        # Special sets
        "det1":   "2409",   # Detective Pikachu
        "dv1":    "1426",   # Dragon Vault
        "xy0":    "1522",   # Kalos Starter Set
        "me2":    "-233",   # Extended Art: Mega Evolution
        "me2pt5": "24448",  # ME02: Phantasmal Flames
        "me3":    "24587",  # ME03: Perfect Order
        # me4 (Chaos Rising) intentionally omitted — "-233" is the wrong set ID
        # (copy-paste from me2). Let the count-based fallback resolve it.
        # Trainer Kits
        "tk1a":   "-178",   # BW Trainer Kit
        "tk1b":   "-178",   # BW Trainer Kit
        "tk2a":   "-9",     # XY BREAKpoint Promos
        "tk2b":   "-9",     # XY BREAKpoint Promos
        # Promo sets (found via PR set_code disambiguation)
        "bwp":    "1407",   # Black and White Promos
        "dpp":    "1421",   # Diamond and Pearl Promos
        "svp":    "22872",  # SV: Scarlet & Violet Promo Cards
        "swshp":  "2545",   # SWSH: Sword & Shield Promo Cards
        # McDonald's promos (all years)
        "mcd11":  "1401",   # McDonald's Promos 2011
        "mcd12":  "1427",   # McDonald's Promos 2012
        "mcd14":  "1692",   # McDonald's Promos 2014
        "mcd15":  "1694",   # McDonald's Promos 2015
        "mcd16":  "3087",   # McDonald's Promos 2016
        "mcd17":  "2148",   # McDonald's Promos 2017
        "mcd18":  "2364",   # McDonald's Promos 2018
        "mcd19":  "2555",   # McDonald's Promos 2019
        # Shiny Vault & Generations
        "swsh45sv": "2781", # Shining Fates: Shiny Vault
        "g1":       "1728", # Generations
        # SV Special Energy set
        "sve":    "22873",  # Part of main SV base set
    }
    if set_code in _KNOWN:
        return _KNOWN[set_code]

    # ── 2. Exact count + set_code prefix match ──────────────────────
    db = _load_db()
    if not db:
        return None
    local_count = sum(1 for c in db._cards
                      if c.get("id", "").rsplit("-", 1)[0] == set_code)
    if not local_count:
        return None

    sets = _get_pokewallet_sets()
    if not sets:
        return None

    prefix = re.sub(r"\d+", "", set_code).upper()

    def _code_matches(s: dict) -> bool:
        sc = (s.get("set_code") or "").upper()
        return prefix in sc or sc in prefix

    exact = [s for s in sets
             if s.get("language") in ("eng", None)
             and s.get("card_count") == local_count
             and _code_matches(s)]

    if len(exact) == 1:
        return str(exact[0]["set_id"])

    return None

# Module-level cache so CardDatabase is only loaded once across all calls
_db = None
_set_count_cache: dict[str, int] = {}   # set_code → DB card count for that set


def _db_set_count(set_code: str) -> int:
    """Return how many cards the local DB has for set_code (cached)."""
    if set_code not in _set_count_cache:
        db = _load_db()
        if db:
            _set_count_cache[set_code] = sum(
                1 for c in db._cards
                if c.get("id", "").rsplit("-", 1)[0] == set_code
            )
        else:
            _set_count_cache[set_code] = 0
    return _set_count_cache[set_code]


def _composite_cache_key(card_name: str, card_local_id: str | None) -> str:
    """
    Build a cache key that encodes set-id, collector number, and rarity so
    that a Common and an IR of the same Pokémon name never share a cache entry.
    Example: "me4-88::illustration-rare"
    """
    if not card_local_id:
        return card_name
    db = _load_db()
    if db:
        exact = next((c for c in db._cards if c.get("id") == card_local_id), None)
        if exact and exact.get("rarity"):
            rarity_slug = exact["rarity"].lower().replace(" ", "-")
            return f"{card_local_id}::{rarity_slug}"
    return card_local_id


def _is_premium_range(card_local_id: str) -> bool:
    """
    Return True when the collector number exceeds the set's DB card count,
    meaning the card is a premium variant (IR/SIR/HR) not present in the local DB.
    """
    if not card_local_id or "-" not in card_local_id:
        return False
    set_code, raw_num = card_local_id.rsplit("-", 1)
    m = re.match(r"(\d+)", raw_num)
    if not m:
        return False
    num_int   = int(m.group(1))
    set_total = _db_set_count(set_code)
    return bool(set_total and num_int > set_total)


def _load_db():
    """Lazily load and cache the CardDatabase instance."""
    global _db
    if _db is None:
        try:
            sys.path.insert(0, os.path.dirname(__file__))
            from card_db import CardDatabase
            _db = CardDatabase()
        except Exception:
            pass
    return _db


_EXTENDED_RARITIES = frozenset({
    # Rarities that are always numbered above the base-set print run in every
    # modern Pokemon TCG set.  Used to derive the denominator for card-number
    # notation (e.g. "87/86" for the first IR in a 86-card base set).
    "Illustration Rare",
    "Special Illustration Rare",
    "Hyper Rare",
    "Mega Hyper Rare",
    "Rare Secret",
    "Rare Rainbow",
    "Shiny Ultra Rare",
})


def _base_set_size(set_code: str) -> int:
    """
    Return the denominator used in TCGPlayer card-number notation for set_code.

    For sets with secret/extended cards, this equals (lowest extended-rarity
    collector number − 1).  Example: me4 has its first IR at #87, so the base
    set size is 86 and IRs are written as "87/86".

    Falls back to the full DB card count for sets with no extended-rarity cards.
    """
    db = _load_db()
    if not db:
        return 0
    all_set_cards = [c for c in db._cards
                     if c.get("id", "").rsplit("-", 1)[0] == set_code]
    extended_nums = [
        int(c["number"])
        for c in all_set_cards
        if c.get("rarity") in _EXTENDED_RARITIES and str(c.get("number", "")).isdigit()
    ]
    if extended_nums:
        return min(extended_nums) - 1  # e.g. min=87 → base size = 86
    return len(all_set_cards)


def _format_card_number(local_id: str) -> str | None:
    """
    Convert a local card id like 'base1-4' to the API query format '4/102'.

    Uses the base-set print-run size (via _base_set_size) as the denominator
    so that secret rares produce the standard TCGPlayer notation "87/86" rather
    than "87/122".
    """
    if not local_id or "-" not in local_id:
        return None
    set_code, num = local_id.rsplit("-", 1)
    total = _base_set_size(set_code)
    return f"{num}/{total}" if total else None


def _get_base_price(card_name: str, card_local_id: str | None = None) -> float | None:
    """
    Look up the exact card in CardDatabase and return its valuated price.
    Uses card_local_id (e.g. 'swsh6-201') for an exact match when provided,
    falling back to name+set filtering, then a seeded random price.

    Returns None when the card is in the premium-range (collector number exceeds
    the set's DB card count) and no IR/SIR/HR match can be found — callers must
    not substitute a Common-card price in that case.
    """
    try:
        db = _load_db()
        if not db:
            return random.Random(card_name).uniform(5.0, 500.0)
        from card_valuator import valuate_card
    except Exception:
        return random.Random(card_name).uniform(5.0, 500.0)

    # Fast path: exact match by local DB id
    if card_local_id:
        exact = next((c for c in db._cards if c.get("id") == card_local_id), None)
        if exact:
            return valuate_card(exact)["simulated_price"]

        # Card not in DB.  If the collector number exceeds the set's base-run
        # count, this is a premium variant (IR/SIR/HR).  Returning a same-named
        # Common's price would be wrong, so return None instead.
        if _is_premium_range(card_local_id):
            print(
                f"[scraper] WARNING: {card_local_id!r} is outside the DB set range"
                f" (premium variant); refusing to fall back to Common price",
                file=sys.stderr,
            )
            return None

    # Slow path: name + set_name filter
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", card_name)
    name     = m.group(1).strip() if m else card_name
    set_hint = m.group(2).strip() if m else None

    candidates = [c for c in db._cards if c.get("name", "").lower() == name.lower()]
    if set_hint:
        filtered = [c for c in candidates
                    if set_hint.lower() in c.get("set_name", "").lower()]
        if filtered:
            candidates = filtered

    if not candidates:
        return random.Random(card_name).uniform(5.0, 500.0)

    # Among same-named candidates, prefer the one whose rarity is in _IR_RARITIES
    # when the card_local_id already resolved to an IR in the DB (e.g. me4-88).
    if card_local_id:
        ir_candidates = [c for c in candidates if c.get("rarity") in _IR_RARITIES]
        target_id = card_local_id  # e.g. "me4-88"
        id_match = next((c for c in ir_candidates if c.get("id") == target_id), None)
        if id_match:
            return valuate_card(id_match)["simulated_price"]
        if ir_candidates:
            return valuate_card(ir_candidates[0])["simulated_price"]

    return valuate_card(candidates[0])["simulated_price"]


# ---------------------------------------------------------------------------
# TCGPlayer direct API — individual Near Mint listings
#
# Requires a free Partner account at developer.tcgplayer.com.
# Set TCGPLAYER_CLIENT_ID and TCGPLAYER_CLIENT_SECRET in .env to enable.
# ---------------------------------------------------------------------------

_TCG_NM_CONDITION_ID = 1   # TCGPlayer conditionId for Near Mint


def _tcgplayer_api_key() -> tuple[str, str]:
    return (
        os.environ.get("TCGPLAYER_CLIENT_ID", "")     or TCGPLAYER_CLIENT_ID,
        os.environ.get("TCGPLAYER_CLIENT_SECRET", "") or TCGPLAYER_CLIENT_SECRET,
    )


def _tcgplayer_bearer() -> str | None:
    """
    Return a valid TCGPlayer OAuth2 bearer token, refreshing when within
    60 seconds of expiry. Returns None if credentials are not configured.
    """
    import time
    cid, csec = _tcgplayer_api_key()
    if not cid or not csec:
        return None

    now = time.time()
    if _tcg_token_cache.get("token") and _tcg_token_cache.get("expires_at", 0) > now + 60:
        return _tcg_token_cache["token"]

    try:
        r = requests.post(
            "https://api.tcgplayer.com/token",
            data={
                "grant_type":    "client_credentials",
                "client_id":     cid,
                "client_secret": csec,
            },
            timeout=15,
        )
        r.raise_for_status()
        data  = r.json()
        token = data.get("access_token")
        if not token:
            return None
        _tcg_token_cache["token"]      = token
        _tcg_token_cache["expires_at"] = now + float(data.get("expires_in", 1_209_600))
        return token
    except Exception:
        return None


def _tcgplayer_find_product(card_name: str, card_local_id: str | None = None) -> int | None:
    """
    Resolve a TCGPlayer productId for a Pokémon card.
    Results are cached for the process lifetime to avoid redundant lookups.
    """
    cache_key = _composite_cache_key(card_name, card_local_id)
    if cache_key in _tcg_product_cache:
        return _tcg_product_cache[cache_key]

    token = _tcgplayer_bearer()
    if not token:
        return None

    headers = {"Authorization": f"Bearer {token}"}

    # Parse "Charizard (Base Set)" → name + optional set hint
    m        = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", card_name)
    name     = m.group(1).strip() if m else card_name
    set_hint = m.group(2).strip() if m else None

    params: dict = {"productLineName": "Pokemon", "productName": name, "limit": 20}
    if set_hint:
        params["groupName"] = set_hint

    try:
        r = requests.get(
            f"{TCGPLAYER_BASE_URL}/catalog/products",
            headers=headers,
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        items = r.json().get("results", [])
    except Exception:
        _tcg_product_cache[cache_key] = None
        return None

    if not items:
        _tcg_product_cache[cache_key] = None
        return None

    # Prefer exact card-number match when we have it
    product_id = None
    if card_local_id:
        raw_num = card_local_id.rsplit("-", 1)[-1].lstrip("0")
        for item in items:
            cn = str(item.get("number", "")).lstrip("0")
            if cn == raw_num:
                product_id = item["productId"]
                break

    if product_id is None:
        product_id = items[0]["productId"]

    _tcg_product_cache[cache_key] = product_id
    return product_id


def get_tcgplayer_nm_listings(
    card_name: str,
    card_local_id: str | None = None,
    limit: int = 15,
) -> list[dict]:
    """
    Fetch active Near Mint listings from TCGPlayer, sorted by price ascending.

    Each dict contains:
        seller        — seller display name
        price         — float, listed price USD
        quantity      — int, copies available at that price
        seller_rating — float | None, feedback score (0–5)
        verified      — bool, TCGPlayer Direct / verified seller
        condition     — "Near Mint"

    Returns an empty list when credentials are absent or the card isn't found.
    """
    product_id = _tcgplayer_find_product(card_name, card_local_id)
    if not product_id:
        return []

    token = _tcgplayer_bearer()
    if not token:
        return []

    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(
            f"{TCGPLAYER_BASE_URL}/stores/product/{product_id}/listings",
            headers=headers,
            params={
                "conditionIds":  _TCG_NM_CONDITION_ID,
                "limit":         limit,
                "sortBy":        "price",
                "sortDirection": "Ascending",
            },
            timeout=15,
        )
        r.raise_for_status()
        raw = r.json().get("results", [])
    except Exception:
        return []

    listings = []
    for row in raw[:limit]:
        # TCGPlayer returns seller info either at root or nested under "seller"
        seller_obj  = row.get("seller") or {}
        seller_name = (row.get("sellerName")
                       or seller_obj.get("name")
                       or "Unknown")
        rating = (row.get("sellerRating")
                  or seller_obj.get("feedbackScore"))
        verified = bool(
            row.get("verified")
            or row.get("isTCGDirectListing")
            or seller_obj.get("verified")
        )
        listings.append({
            "seller":        seller_name,
            "price":         float(row.get("price", 0.0)),
            "quantity":      int(row.get("quantity", 1)),
            "seller_rating": round(float(rating), 1) if rating is not None else None,
            "verified":      verified,
            "condition":     "Near Mint",
        })

    listings.sort(key=lambda x: x["price"])
    return listings[:limit]


# Full set of headers that match what Chrome sends on a real page visit.
# eBay's bot-detection checks for Accept, Accept-Encoding, and Connection
# in addition to User-Agent, so omitting any of them increases the chance
# of a 403 Forbidden response.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;"
        "q=0.8,application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    # Tell the server we can handle compressed responses (standard for browsers)
    "Accept-Encoding": "gzip, deflate, br",
    # Keep-alive prevents the connection from closing after each request,
    # which is normal browser behavior
    "Connection": "keep-alive",
    # Referer makes the search request look like it originated from the eBay
    # homepage rather than appearing out of nowhere
    "Referer": "https://www.ebay.com/",
}

MAX_RESULTS = 20


def get_ebay_sold_prices(card_name: str) -> list[dict]:
    """
    Attempt to fetch eBay completed/sold listings via requests.

    eBay now renders search results client-side, so this will typically
    return an empty list. get_card_prices() falls back to simulated data
    when fewer than 5 results are returned.

    Args:
        card_name: The Pokemon card name (e.g. "Charizard VMAX").

    Returns:
        A list of dicts with keys: title, price, date_sold, url.
    """
    params = {
        "_nkw": card_name + " pokemon card",
        "LH_Complete": "1",
        "LH_Sold": "1",
        "_sop": "13",
        "_ipg": "100",
    }
    url = "https://www.ebay.com/sch/i.html?" + urlencode(params)

    session = requests.Session()
    session.headers.update(HEADERS)
    session.get("https://www.ebay.com/", timeout=10)
    response = session.get(url, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    for item in soup.select("li.s-item"):
        if "s-item__pl-on-bottom" in item.get("class", []):
            continue

        title_tag = item.select_one(".s-item__title")
        title = title_tag.get_text(strip=True) if title_tag else None
        if not title or title.lower() == "shop on ebay":
            continue

        price_tag = item.select_one(".s-item__price")
        price = price_tag.get_text(strip=True) if price_tag else None

        date_tag = item.select_one(".s-item__caption--signal.POSITIVE")
        date_sold = None
        if date_tag:
            date_sold = date_tag.get_text(strip=True).replace("Sold", "").strip()

        link_tag = item.select_one("a.s-item__link")
        listing_url = link_tag["href"] if link_tag and link_tag.get("href") else None

        results.append({
            "title": title,
            "price": price,
            "date_sold": date_sold,
            "url": listing_url,
        })

        if len(results) >= MAX_RESULTS:
            break

    return results


def _pokewallet_api_key() -> str:
    """Return the PokéWallet API key, always reading live from os.environ."""
    return os.environ.get("POKEWALLET_API_KEY", "") or POKEWALLET_API_KEY


def get_pokewallet_prices(card_name: str, card_local_id: str | None = None) -> list[dict]:
    """
    Fetch real TCGPlayer market prices via the PokéWallet API.

    Searches by card name, scores candidates to find the best match
    (boosted by set name when the caller passes "Name (Set)" format),
    fetches the full card detail, then generates MAX_RESULTS price
    points sampled from the real low–high spread so the analyzer has
    enough data points to work with.

    Returns an empty list when no API key is configured or the API
    returns no usable price data — get_card_prices() will fall back
    to the simulated path in that case.
    """
    api_key = _pokewallet_api_key()
    if not api_key or api_key == "pk_live_your_key_here":
        return []

    headers = {"X-API-Key": api_key}

    # Parse "Charizard (Base Set)" → name="Charizard", set_hint="Base Set"
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", card_name)
    name     = m.group(1).strip() if m else card_name
    set_hint = m.group(2).strip().lower() if m else None

    # Compute set lookup values once — used by both query building and scoring
    fraction   = _format_card_number(card_local_id) if card_local_id else None
    raw_number = card_local_id.rsplit("-", 1)[-1] if card_local_id else None
    if raw_number:
        # Strip non-numeric suffixes like "_A" from ids such as "cel25c-66_A"
        raw_number = re.sub(r"[^0-9].*$", "", raw_number) or raw_number
    api_set_id = _api_set_id_for(card_local_id) if card_local_id else None

    # Skip fraction for legacy-numbered reprints where the collector number comes
    # from a different set (e.g. cel25c Shining Magikarp #66 in a 25-card set).
    # Do NOT skip for genuine secret rares — "87/86" IS the correct TCGPlayer
    # notation when a card's number exceeds the base set size.
    if fraction and raw_number and raw_number.isdigit():
        num, _, total = fraction.partition("/")
        if total.isdigit() and int(raw_number) > int(total):
            _db_ref  = _load_db()
            _ir_card = next(
                (c for c in _db_ref._cards if c.get("id") == card_local_id), None
            ) if (_db_ref and card_local_id) else None
            if not (_ir_card and _ir_card.get("rarity") in _IR_RARITIES):
                fraction = None

    queries: list[str] = []
    if fraction:
        queries.append(f"{name} {fraction}")          # "Charizard 4/102"
    if api_set_id and raw_number:
        queries.append(f"{api_set_id} {raw_number}")  # "1402 108" (most precise)
    if raw_number and raw_number != fraction:
        queries.append(f"{name} {raw_number}")        # "Charizard 4"
    queries.append(name)                              # "Charizard" (broadest)

    cards: list = []
    for search_q in queries:
        try:
            resp = requests.get(
                f"{POKEWALLET_BASE_URL}/search",
                headers=headers,
                params={"q": search_q, "limit": 20},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            continue
        found = data.get("data") or data.get("results") or []
        if found:
            cards = found
            break

    if not cards:
        return []

    # ── Step 2: score candidates, pick best match ───────────────────
    name_lower = name.lower()

    # Resolve expected rarity from the local DB so the scorer can discriminate
    # between a Common and an IR of the same Pokémon name.
    expected_rarity: str | None = None
    is_premium = _is_premium_range(card_local_id) if card_local_id else False
    if card_local_id:
        _db_ref = _load_db()
        if _db_ref:
            _exact = next((c for c in _db_ref._cards if c.get("id") == card_local_id), None)
            if _exact:
                expected_rarity = _exact.get("rarity")

    def _score(c: dict) -> int:
        info      = c.get("card_info") or c
        cname     = info.get("name", "").lower()
        cset      = info.get("set_name", "").lower()
        cset_id   = str(info.get("set_id", ""))
        crarity   = info.get("rarity", "")
        s = 0
        if cname == name_lower:            s += 10
        elif cname.startswith(name_lower): s += 5
        elif name_lower in cname:          s += 2
        if set_hint and set_hint in cset:  s += 8
        # Penalise non-English sets — Japanese cards should never beat English ones
        if _set_language.get(cset_id, "eng") not in ("eng", ""):
            s -= 20
        # Strong boost when this card is from the exact target set
        if api_set_id and cset_id == api_set_id:
            s += 15
        # Penalise premium/variant pressings — but NOT when this IS the target set
        _PENALTY = ["shadowless", "1st edition", "error", "promo",
                    "jumbo", "metal", "classic collection", "celebrations"]
        is_target = (api_set_id and cset_id == api_set_id) or \
                    (set_hint and set_hint in cset)
        if not is_target and any(p in cset for p in _PENALTY):
            s -= 6
        # Rarity-aware scoring: exact rarity match gets a large boost; returning a
        # Common when we expected an IR/SIR/HR is heavily penalised.
        if expected_rarity:
            if crarity == expected_rarity:
                s += 12
            elif expected_rarity in _IR_RARITIES and crarity not in _IR_RARITIES:
                s -= 15
        elif is_premium:
            # Card not in local DB but collector number is above base-run count →
            # treat as a premium card and prefer IR/SIR/HR API results.
            # TODO: filter client-side when PokéWallet adds rarity query param.
            if crarity in _IR_RARITIES:
                s += 12
            elif crarity and crarity not in _IR_RARITIES:
                s -= 15
        return s

    best = max(cards, key=_score)
    card_id = best.get("id")
    if not card_id:
        return []

    # IR guard: if we expect an IR/SIR/HR (either from DB or premium-range
    # detection) but the API best match came back as a Common-tier card, refuse
    # to return that price rather than silently mis-pricing.
    _needs_ir = expected_rarity in _IR_RARITIES or is_premium
    if _needs_ir:
        best_rarity = (best.get("card_info") or best).get("rarity", "")
        if best_rarity and best_rarity not in _IR_RARITIES:
            print(
                f"[scraper] WARNING: PokéWallet best match for {card_local_id!r}"
                f" has rarity {best_rarity!r} (expected IR/SIR/HR); returning []",
                file=sys.stderr,
            )
            return []

    # ── Step 3: fetch full card detail + pricing ────────────────────
    try:
        resp = requests.get(
            f"{POKEWALLET_BASE_URL}/cards/{card_id}",
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        detail = resp.json()
    except Exception:
        return []

    tcg      = detail.get("tcgplayer") or {}
    variants = tcg.get("prices") or []
    if not variants:
        return []

    card_info     = detail.get("card_info") or {}
    display_title = f"{card_info.get('name', name)} ({card_info.get('set_name', '')})"
    tcg_url       = tcg.get("url")
    today_str     = datetime.date.today().strftime("%b %d, %Y")

    # ── Step 4: collect variants from ALL matching search results ───
    # The Shadowless and 1st Edition copies are separate card entries
    # in the API (e.g. "Base Set" vs "Base Set (Shadowless)"), so we
    # harvest price rows from every same-name result and label them.

    def _variant_label(set_name: str, sub_type: str) -> str:
        sn = set_name.lower()
        st = sub_type.lower()
        if "shadowless" in sn and "1st edition" in st:
            return "1st Edition Shadowless"
        if "shadowless" in sn:
            return "Shadowless"
        if "1st edition" in st:
            return "1st Edition"
        # For modern cards keep the API label (e.g. "Holofoil", "Reverse Holofoil")
        return sub_type

    def _variant_sort_key(v: dict) -> int:
        label = v["sub_type_name"].lower()
        if "1st edition shadowless" in label: return 3
        if "1st edition" in label:            return 2
        if "shadowless" in label:             return 1
        return 0

    seen_labels: set = set()
    all_variants: list = []

    def _normalize(n: str) -> str:
        """Normalize name for fuzzy matching: strip suffixes, remove punctuation."""
        n = re.sub(r"\s*-\s*\d+/\d+.*$", "", n)           # "Char ex - 006/165" → "Char ex"
        n = re.sub(r"[()]", " ", n)                         # "Feraligatr (Prime)" → "Feraligatr  Prime"
        n = re.sub(r"-(?=[A-Za-z])", " ", n)               # "Xerneas-EX" → "Xerneas EX"
        return " ".join(n.lower().split())                  # normalize whitespace

    name_norm = _normalize(name_lower)

    for c in sorted(cards, key=_score, reverse=True):
        info_c   = c.get("card_info") or c
        api_raw  = info_c.get("name", "")
        api_norm = _normalize(api_raw)
        # Accept if normalized names match exactly or API name starts with ours
        if not (api_norm == name_norm
                or api_norm.startswith(name_norm + " ")
                or api_norm.startswith(name_norm + "-")):
            continue
        cset      = info_c.get("set_name", "")
        prices_c  = (c.get("tcgplayer") or {}).get("prices") or []
        for v in prices_c:
            mp = v.get("market_price")
            if not mp:
                continue
            label = _variant_label(cset, v.get("sub_type_name", "Normal"))
            if label in seen_labels:
                continue
            seen_labels.add(label)
            all_variants.append({
                "sub_type_name": label,
                "market_price":  mp,
                "low_price":     v.get("low_price"),
                "mid_price":     v.get("mid_price"),
                "high_price":    v.get("high_price"),
            })

    all_variants.sort(key=_variant_sort_key)

    if not all_variants:
        return []

    # Primary = first standard (Unlimited) variant
    primary  = all_variants[0]
    market   = primary["market_price"]
    low      = primary.get("low_price")
    mid      = primary.get("mid_price")
    high     = primary.get("high_price")
    sub_type = primary["sub_type_name"]

    real_points = [p for p in [market, low, mid, high] if p]
    while len(real_points) < 5:
        real_points.append(market)

    results = []
    for price in real_points:
        results.append({
            "title":         f"{display_title} [{sub_type}]",
            "price":         f"${price:.2f}",
            "date_sold":     today_str,
            "source":        "pokewallet",
            "url":           tcg_url,
            "market_price":  market,
            "low_price":     low,
            "mid_price":     mid,
            "high_price":    high,
            "sub_type_name": sub_type,
            "all_variants":  all_variants,
            "sales_volume":  None,
        })

    return results


def _poketrace_api_key() -> str:
    return os.environ.get("POKETRACE_API_KEY", "") or POKETRACE_API_KEY


def _poketrace_find_card(card_name: str, card_local_id: str | None) -> str | None:
    """Return PokeTrace UUID for a card, or None if not found. Results are cached."""
    cache_key = _composite_cache_key(card_name, card_local_id)
    if cache_key in _poketrace_id_cache:
        return _poketrace_id_cache[cache_key]

    key = _poketrace_api_key()
    if not key:
        return None

    # Strip set suffix from display name e.g. "Charizard (Base Set)" → "Charizard"
    search_name = re.sub(r"\s*\(.*?\)\s*$", "", card_name).strip()

    # Extract card number from local id e.g. "me2-125" → "125"
    card_number = None
    if card_local_id and "-" in card_local_id:
        raw = card_local_id.rsplit("-", 1)[-1]
        m = re.match(r"(\d+)", raw)
        if m:
            card_number = m.group(1)

    is_premium = _is_premium_range(card_local_id) if card_local_id else False

    try:
        r = requests.get(
            f"{POKETRACE_BASE_URL}/cards",
            headers={"X-API-Key": key},
            params={"search": search_name, "limit": 20},
            timeout=10,
        )
        if r.status_code != 200:
            _poketrace_id_cache[cache_key] = None
            return None
        items = r.json().get("data", [])
    except Exception:
        _poketrace_id_cache[cache_key] = None
        return None

    if not items:
        _poketrace_id_cache[cache_key] = None
        return None

    # Prefer the entry whose cardNumber starts with our target number
    # e.g. card_number="125" matches "125/094"
    uid = None
    if card_number:
        for item in items:
            cn = item.get("cardNumber") or ""
            if cn.startswith(card_number + "/") or cn == card_number:
                uid = item["id"]
                break

    if not uid:
        # For premium-range cards, don't fall back to items[0] — that entry is
        # likely a Common or a lower-rarity card from a different set entirely.
        if is_premium:
            print(
                f"[scraper] WARNING: PokeTrace has no exact match for premium card"
                f" {card_local_id!r} (card_number={card_number!r}); skipping fallback",
                file=sys.stderr,
            )
            _poketrace_id_cache[cache_key] = None
            return None
        uid = items[0]["id"]

    _poketrace_id_cache[cache_key] = uid
    return uid


def get_poketrace_history(card_name: str, card_local_id: str | None = None) -> list[dict]:
    """
    Fetch NM price history from PokeTrace (last 90 days, daily aggregates).
    Returns a list of price dicts compatible with analyze_card(), most recent first.
    Each entry has a real date so the trend regression works properly.
    """
    uid = _poketrace_find_card(card_name, card_local_id)
    if not uid:
        return []

    key = _poketrace_api_key()
    import time as _time
    for _attempt in range(3):
        try:
            r = requests.get(
                f"{POKETRACE_BASE_URL}/cards/{uid}/prices/NEAR_MINT/history",
                headers={"X-API-Key": key},
                params={"period": "90d", "limit": 50},
                timeout=10,
            )
            if r.status_code == 429:
                _time.sleep(2)
                continue
            if r.status_code != 200:
                return []
            entries = r.json().get("data", [])
            break
        except Exception:
            return []
    else:
        return []

    results = []
    for e in entries:
        avg = e.get("avg")
        if not avg:
            continue
        # PokeTrace dates are ISO strings like "2026-05-28"
        raw_date = e.get("date", "")
        try:
            d = datetime.date.fromisoformat(raw_date[:10])
            date_str = d.strftime("%b %d, %Y")
        except Exception:
            date_str = raw_date

        results.append({
            "title":       f"{card_name} [PokeTrace]",
            "price":       f"${avg:.2f}",
            "date_sold":   date_str,
            "source":      "poketrace",
            "data_source": "live",
            "market_price": avg,
            "low_price":    e.get("low"),
            "high_price":   e.get("high"),
            "sale_count":   e.get("saleCount"),
        })

    # Most recent first
    results.sort(key=lambda x: x["date_sold"], reverse=True)
    return results


def get_card_prices(card_name: str, card_local_id: str | None = None) -> list[dict]:
    """
    Return price data for a Pokemon card.

    Priority:
      1. PokéWallet API  — current TCGPlayer market price + all variants (display)
         + PokeTrace API — 90-day NM sales history (trend / analysis)
      2. Simulated       — valuator-anchored prices with ±20% variance

    Returns a list of dicts with keys:
      title, price, date_sold, source, data_source,
      market_price, low_price, high_price, all_variants  (PokéWallet metadata
      is merged onto the first PokeTrace entry so the UI still has variants).
    """
    # 1a. PokéWallet — current market price + variant selector data
    try:
        pw = get_pokewallet_prices(card_name, card_local_id)
    except Exception:
        pw = []

    pw_meta = pw[0] if pw else {}   # market_price, all_variants, etc.

    # 1b. PokeTrace — real 90-day NM sales history for trend analysis
    try:
        pt = get_poketrace_history(card_name, card_local_id)
    except Exception:
        pt = []

    if len(pt) >= 5:
        # Merge PokéWallet display metadata onto the first PokeTrace entry
        # so app.py can still show market price, variants, etc.
        pt[0].update({
            "source":        "pokewallet",   # keeps the "API Live" badge
            "market_price":  pw_meta.get("market_price") or pt[0].get("market_price"),
            "low_price":     pw_meta.get("low_price")    or pt[0].get("low_price"),
            "high_price":    pw_meta.get("high_price")   or pt[0].get("high_price"),
            "mid_price":     pw_meta.get("mid_price"),
            "sub_type_name": pw_meta.get("sub_type_name", ""),
            "all_variants":  pw_meta.get("all_variants", []),
        })
        for entry in pt:
            entry["data_source"] = "live"
        return pt

    # PokéWallet snapshot only (no PokeTrace data) — trend will show "no data"
    if len(pw) >= 5:
        for entry in pw:
            entry["data_source"] = "live"
        return pw

    # 2. Simulated fallback
    base_price = _get_base_price(card_name, card_local_id)
    if base_price is None:
        # Premium-range card not in local DB — return empty rather than a Common price.
        return []
    rng        = random.Random(card_name)
    today      = datetime.date.today()
    results    = []

    for i in range(20):
        price    = round(rng.uniform(base_price * 0.80, base_price * 1.20), 2)
        days_ago = rng.randint(0, 60)
        date_sold = (today - datetime.timedelta(days=days_ago)).strftime("%b %d, %Y")
        results.append({
            "title":        f"{card_name} Pokemon Card (Simulated #{i + 1})",
            "price":        f"${price:.2f}",
            "date_sold":    date_sold,
            "source":       "simulated",
            "data_source":  "simulated",
            "sales_volume": None,
        })

    results.sort(key=lambda r: r["date_sold"], reverse=True)
    return results


if __name__ == "__main__":
    card = "Charizard VMAX"
    print(f"Fetching prices for: {card}\n")
    listings = get_card_prices(card)
    print(f"--- Results ({len(listings)} found) ---")
    for i, listing in enumerate(listings, 1):
        print(f"{i}. {listing['title']}")
        print(f"   Price     : {listing['price']}")
        print(f"   Date sold : {listing['date_sold']}")
        print(f"   Source    : {listing['source']}\n")

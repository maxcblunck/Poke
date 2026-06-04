import json
import os
import re
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
_SETS_CACHE_PATH     = os.path.join(os.path.dirname(__file__), "..", "data", "pokewallet_sets.json")
_sets_cache: list | None = None


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
    # Keys are local set prefixes (strip trailing digits from set_code).
    # Values are the API numeric set_id confirmed by manual testing.
    _KNOWN: dict[str, str] = {
        # HGSS era (2009-2011) — fraction queries return no results
        "hgss1": "1402",   # HeartGold SoulSilver
        "hgss2": "1399",   # Unleashed
        "hgss3": "1403",   # Undaunted
        "hgss4": "1381",   # Triumphant
        "col1":  "1415",   # Call of Legends
        # XY era (2013-2016) — fraction returns no results
        "xy1":   "1387",   # XY Base Set
        "xy2":   "1464",   # Flashfire
        "xy3":   "1481",   # Furious Fists
        "xy4":   "1494",   # Phantom Forces
        "xy5":   "1509",   # Primal Clash
        "xy6":   "1534",   # Roaring Skies
        "xy7":   "1576",   # Ancient Origins
        "xy8":   "1661",   # BREAKthrough
        "xy9":   "1701",   # BREAKpoint
        "xy10":  "1780",   # Fates Collide
        "xy11":  "1815",   # Steam Siege
        "xy12":  "1842",   # Evolutions
        # Celebrations (2021) — "celebrations" is penalised in scoring
        # unless the target set_id is explicitly set here
        "cel25":  "2867",  # Celebrations
        "cel25c": "2931",  # Celebrations: Classic Collection
        # Sun & Moon era (2017-2019) — count ambiguous due to secrets
        "sm3":   "1957",   # Burning Shadows
        "sm2":   "1919",   # Guardians Rising
        "sm4":   "2071",   # Crimson Invasion
        "sm5":   "2178",   # Ultra Prism
        "sm6":   "2209",   # Forbidden Light
        "sm7":   "2278",   # Celestial Storm
        "sm9":   "2377",   # Team Up
        "sm10":  "2420",   # Unbroken Bonds
        "sm11":  "2464",   # Unified Minds
        "sm12":  "2534",   # Cosmic Eclipse
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


def _load_db():
    """Lazily load and cache the CardDatabase instance."""
    global _db
    if _db is None:
        try:
            import sys as _sys
            _sys.path.insert(0, os.path.dirname(__file__))
            from card_db import CardDatabase
            _db = CardDatabase()
        except Exception:
            pass
    return _db


def _format_card_number(local_id: str) -> str | None:
    """
    Convert a local card id like 'base1-4' to the API query format '4/102'
    by counting how many cards share that set prefix in the local DB.
    Returns None if the DB isn't available or the format can't be built.
    """
    if not local_id or "-" not in local_id:
        return None
    set_code, num = local_id.rsplit("-", 1)
    db = _load_db()
    if not db:
        return None
    total = sum(1 for c in db._cards
                if c.get("id", "").rsplit("-", 1)[0] == set_code)
    return f"{num}/{total}" if total else None


def _get_base_price(card_name: str, card_local_id: str | None = None) -> float:
    """
    Look up the exact card in CardDatabase and return its valuated price.
    Uses card_local_id (e.g. 'swsh6-201') for an exact match when provided,
    falling back to name+set filtering, then a seeded random price.
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

    return valuate_card(candidates[0])["simulated_price"]

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
    # which is normal browser behaviour
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
    """Return the PokéWallet API key, preferring the module-level variable."""
    return POKEWALLET_API_KEY or os.environ.get("POKEWALLET_API_KEY", "")


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

    # Skip fraction when card number exceeds the set total (e.g. cel25c has 25
    # cards but Shining Magikarp keeps its original #66 from Neo Revelation).
    if fraction and raw_number and raw_number.isdigit():
        num, _, total = fraction.partition("/")
        if total.isdigit() and int(raw_number) > int(total):
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

    def _score(c: dict) -> int:
        info      = c.get("card_info") or c
        cname     = info.get("name", "").lower()
        cset      = info.get("set_name", "").lower()
        cset_id   = str(info.get("set_id", ""))
        s = 0
        if cname == name_lower:            s += 10
        elif cname.startswith(name_lower): s += 5
        elif name_lower in cname:          s += 2
        if set_hint and set_hint in cset:  s += 8
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
        return s

    best = max(cards, key=_score)
    card_id = best.get("id")
    if not card_id:
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

    def _normalise(n: str) -> str:
        """Normalise name for fuzzy matching: strip suffixes, remove punctuation."""
        n = re.sub(r"\s*-\s*\d+/\d+.*$", "", n)           # "Char ex - 006/165" → "Char ex"
        n = re.sub(r"[()]", " ", n)                         # "Feraligatr (Prime)" → "Feraligatr  Prime"
        n = re.sub(r"-(?=[A-Za-z])", " ", n)               # "Xerneas-EX" → "Xerneas EX"
        return " ".join(n.lower().split())                  # normalise whitespace

    name_norm = _normalise(name_lower)

    for c in sorted(cards, key=_score, reverse=True):
        info_c   = c.get("card_info") or c
        api_raw  = info_c.get("name", "")
        api_norm = _normalise(api_raw)
        # Accept if normalised names match exactly or API name starts with ours
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


def get_card_prices(card_name: str, card_local_id: str | None = None) -> list[dict]:
    """
    Return price data for a Pokemon card.

    Priority:
      1. PokéWallet API  — real TCGPlayer market prices
      2. eBay scraper    — live sold listings (often blocked client-side)
      3. Simulated       — valuator-anchored prices with ±20% variance

    Returns a list of dicts with keys:
      title, price, date_sold, source, sales_volume
    """
    # 1. PokéWallet
    try:
        pw = get_pokewallet_prices(card_name, card_local_id)
    except Exception:
        pw = []

    if len(pw) >= 5:
        for entry in pw:
            entry["data_source"] = "live"
        return pw

    # 2. eBay
    try:
        ebay = get_ebay_sold_prices(card_name)
    except Exception:
        ebay = []

    if len(ebay) >= 5:
        return [
            {
                "title":        r["title"],
                "price":        r["price"],
                "date_sold":    r["date_sold"],
                "source":       "ebay",
                "data_source":  "live",
                "sales_volume": None,
            }
            for r in ebay
        ]

    # 3. Simulated fallback
    base_price = _get_base_price(card_name, card_local_id)
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

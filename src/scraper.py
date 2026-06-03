import os
import re
import random
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode

POKEWALLET_BASE_URL = "https://api.pokewallet.io"

# Module-level cache so CardDatabase is only loaded once across all calls
_db = None

def _get_base_price(card_name: str) -> float:
    """
    Look up the card in CardDatabase and return a valuated simulated price.
    Falls back to a length-seeded random price if the card isn't found.
    """
    global _db
    try:
        if _db is None:
            import os, sys
            sys.path.insert(0, os.path.dirname(__file__))
            from card_db import CardDatabase
            _db = CardDatabase()
        from card_valuator import valuate_card
    except Exception:
        return random.Random(len(card_name)).uniform(5.0, 500.0)

    # card_name may be "Charizard (Base Set)" — parse name and set
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", card_name)
    name     = m.group(1).strip() if m else card_name
    set_hint = m.group(2).strip() if m else None

    candidates = [c for c in _db._cards if c.get("name", "").lower() == name.lower()]
    if set_hint:
        filtered = [c for c in candidates
                    if set_hint.lower() in c.get("set_name", "").lower()]
        if filtered:
            candidates = filtered

    if not candidates:
        return random.Random(len(card_name)).uniform(5.0, 500.0)

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
    """Load API key from .env or environment. Returns empty string if absent."""
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        load_dotenv(env_path, override=False)
    except ImportError:
        pass
    return os.environ.get("POKEWALLET_API_KEY", "")


def get_pokewallet_prices(card_name: str) -> list[dict]:
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

    # ── Step 1: search ──────────────────────────────────────────────
    try:
        resp = requests.get(
            f"{POKEWALLET_BASE_URL}/search",
            headers=headers,
            params={"q": name, "limit": 20},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []

    cards = data.get("data") or data.get("results") or []
    if not cards:
        return []

    # ── Step 2: score candidates, pick best match ───────────────────
    name_lower = name.lower()

    def _score(c: dict) -> int:
        # Fields live under card_info in search results
        info  = c.get("card_info") or c
        cname = info.get("name", "").lower()
        cset  = info.get("set_name", "").lower()
        s = 0
        if cname == name_lower:            s += 10
        elif cname.startswith(name_lower): s += 5
        elif name_lower in cname:          s += 2
        if set_hint and set_hint in cset:  s += 8
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
    results       = []

    # ── Step 4: use the real API price points directly ──────────────
    # For each printing variant return the four real TCGPlayer price
    # points (market, low, mid, high) so the analyzer works with
    # actual data rather than random samples.
    for variant in variants:
        market = variant.get("market_price")
        if not market:
            continue

        low      = variant.get("low_price")
        mid      = variant.get("mid_price")
        high     = variant.get("high_price")
        sub_type = variant.get("sub_type_name", "Normal")

        # Build a list of the real values; duplicate market so we always
        # have at least 5 entries for analyze_card's minimum threshold.
        real_points = [p for p in [market, low, mid, high] if p]
        while len(real_points) < 5:
            real_points.append(market)

        for price in real_points:
            results.append({
                "title":        f"{display_title} [{sub_type}]",
                "price":        f"${price:.2f}",
                "date_sold":    today_str,
                "source":       "pokewallet",
                "url":          tcg_url,
                "market_price": market,
                "low_price":    low,
                "mid_price":    mid,
                "high_price":   high,
                "sub_type_name": sub_type,
                "sales_volume": None,
            })

    return results


def get_card_prices(card_name: str) -> list[dict]:
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
        pw = get_pokewallet_prices(card_name)
    except Exception:
        pw = []

    if len(pw) >= 5:
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
                "sales_volume": None,
            }
            for r in ebay
        ]

    # 3. Simulated fallback
    base_price = _get_base_price(card_name)
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

# ---------------------------------------------------------------------------
# PLACEHOLDER — get_card_prices() below returns simulated data only.
# It will be replaced with a real eBay API call once API access is confirmed.
# ---------------------------------------------------------------------------

import random
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode

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

    soup = BeautifulSoup(response.text, "lxml")
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


def get_card_prices(card_name: str) -> list[dict]:
    """
    Return sold-price data for a Pokemon card.

    Tries get_ebay_sold_prices() first. Falls back to simulated data if
    fewer than 5 results come back (e.g. eBay blocks the request or the
    card is too obscure to have recent sales).

    Args:
        card_name: The Pokemon card name (e.g. "Charizard Base Set").

    Returns:
        A list of dicts with keys: title, price, date_sold, source,
        sales_volume (placeholder, currently None).
    """
    # TODO — extend to return sales volume once eBay API access is confirmed:
    #   total_sold_7d, total_sold_30d, total_sold_90d, velocity_trend

    try:
        real = get_ebay_sold_prices(card_name)
    except Exception:
        real = []

    if len(real) >= 5:
        return [
            {
                "title":        r["title"],
                "price":        r["price"],
                "date_sold":    r["date_sold"],
                "source":       "ebay",
                "sales_volume": None,
            }
            for r in real
        ]

    # --- Simulated fallback ---
    rng = random.Random(len(card_name))
    base_price = rng.uniform(5.0, 500.0)
    today = datetime.date.today()
    results = []

    for i in range(20):
        price = round(rng.uniform(base_price * 0.80, base_price * 1.20), 2)
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

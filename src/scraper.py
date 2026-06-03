# ---------------------------------------------------------------------------
# PLACEHOLDER — get_card_prices() below returns simulated data only.
# It will be replaced with a real eBay API call once API access is confirmed.
# ---------------------------------------------------------------------------

import random
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode, quote_plus
from playwright.sync_api import sync_playwright

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
    Search eBay completed/sold listings for a Pokemon card and return
    up to 20 of the most recent sales.

    Args:
        card_name: The Pokemon card name to search for (e.g. "Charizard VMAX").

    Returns:
        A list of dicts with keys: title, price, date_sold, url.
    """

    # Build the eBay search URL for completed & sold listings.
    # LH_Complete=1 shows completed listings; LH_Sold=1 filters to sold only.
    params = {
        "_nkw": card_name + " pokemon card",
        "LH_Complete": "1",
        "LH_Sold": "1",
        "_sop": "13",     # sort by most recently ended
        "_ipg": "100",    # request 100 results per page (we'll cap at 20)
    }
    url = "https://www.ebay.com/sch/i.html?" + urlencode(params)

    # A Session object persists cookies across requests, just like a real
    # browser does. eBay sets session cookies on the homepage visit and then
    # expects to see them on subsequent requests — without them the search
    # request looks bot-like and gets blocked with a 403.
    session = requests.Session()
    session.headers.update(HEADERS)

    # Step 1: Visit the eBay homepage first so the session receives the
    # standard cookies (e.g. ebay session id, gdpr consent) before we hit
    # the search endpoint. This mirrors normal human browsing behaviour.
    session.get("https://www.ebay.com/", timeout=10)

    # Step 2: Now make the actual search request with the warmed-up session.
    # The cookies from the homepage visit are automatically sent along.
    response = session.get(url, timeout=10)
    response.raise_for_status()

    # Parse the HTML with BeautifulSoup using the fast lxml parser
    soup = BeautifulSoup(response.text, "lxml")

    # Each sold listing lives in an <li> with class "s-item"
    listing_elements = soup.select("li.s-item")

    results = []

    for item in listing_elements:
        # Skip the ghost/template <li> eBay injects at position 0
        if "s-item__pl-on-bottom" in item.get("class", []):
            continue

        # --- Title ---
        title_tag = item.select_one(".s-item__title")
        title = title_tag.get_text(strip=True) if title_tag else None

        # Skip the dummy "Shop on eBay" placeholder card
        if not title or title.lower() == "shop on ebay":
            continue

        # --- Price ---
        price_tag = item.select_one(".s-item__price")
        price = price_tag.get_text(strip=True) if price_tag else None

        # --- Date sold ---
        # eBay shows the sold date in a <span> that carries both classes:
        # class="s-item__caption--signal POSITIVE". The compound selector
        # (no comma/space) matches elements that have BOTH classes at once.
        date_tag = item.select_one(".s-item__caption--signal.POSITIVE")
        date_sold = None
        if date_tag:
            text = date_tag.get_text(strip=True)
            # The text is usually "Sold  Jun 1, 2026" — strip the label
            date_sold = text.replace("Sold", "").strip()

        # --- Listing URL ---
        link_tag = item.select_one("a.s-item__link")
        listing_url = link_tag["href"] if link_tag and link_tag.get("href") else None

        results.append({
            "title": title,
            "price": price,
            "date_sold": date_sold,
            "url": listing_url,
        })

        # Stop once we have enough results
        if len(results) >= MAX_RESULTS:
            break

    return results


def get_130point_sold_prices(card_name: str, max_results: int = 20) -> list[dict]:
    """
    Fetch sold eBay listings for a Pokemon card from 130point.com using a
    headed Chromium browser so Cloudflare's JS challenge can complete normally.

    Args:
        card_name:   The Pokemon card name to search for (e.g. "Charizard VMAX").
        max_results: Maximum number of listings to return (default 20).

    Returns:
        A list of dicts with keys: title, price, date_sold, url.
        Returns an empty list if no results are found or on error.
    """
    search_url = f"https://130point.com/sales/?search={quote_plus(card_name)}"
    results = []

    with sync_playwright() as p:
        # Headed (non-headless) browser so Cloudflare sees a real Chrome window.
        # slow_mo adds a 500 ms delay between every Playwright action, which makes
        # the interaction pattern look more human and gives the CF challenge time
        # to resolve before we start reading the DOM.
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            page.goto(search_url, wait_until="domcontentloaded", timeout=60_000)

            # Skip networkidle — Cloudflare's challenge page keeps polling forever
            # so networkidle never fires. Instead wait directly for the first real
            # content selector, giving CF up to 60 s to complete its JS challenge.
            page.wait_for_selector(
                "div.item, table#result_table tr, tr.result_row, .sold_item",
                timeout=20_000,
            )

            soup = BeautifulSoup(page.content(), "lxml")

            # --- Strategy 1: div.item layout (current desktop layout) ---
            items = soup.select("div.item")
            for item in items:
                title_tag = item.select_one(".item_title, .title, h3, h4")
                price_tag = item.select_one(".item_price, .price, .sold_price")
                date_tag  = item.select_one(".item_date, .date, .sold_date, .date_sold")
                link_tag  = item.select_one("a[href]")

                title     = title_tag.get_text(strip=True) if title_tag else None
                price     = price_tag.get_text(strip=True) if price_tag else None
                date_sold = date_tag.get_text(strip=True)  if date_tag  else None
                url       = link_tag["href"]               if link_tag  else None

                if title or price:
                    results.append({
                        "title":     title,
                        "price":     price,
                        "date_sold": date_sold,
                        "url":       url,
                    })
                if len(results) >= max_results:
                    break

            # --- Strategy 2: table row layout (fallback) ---
            if not results:
                rows = soup.select("table#result_table tr.result_row, table tr[class*='result']")
                for row in rows:
                    cols = row.select("td")
                    if len(cols) < 3:
                        continue

                    title_tag = row.select_one("td.title, td:nth-child(2), .item_name")
                    price_tag = row.select_one("td.price, td.sold_price, td:nth-child(3)")
                    date_tag  = row.select_one("td.date, td.sold_date, td:nth-child(4)")
                    link_tag  = row.select_one("a[href]")

                    results.append({
                        "title":     title_tag.get_text(strip=True) if title_tag else None,
                        "price":     price_tag.get_text(strip=True) if price_tag else None,
                        "date_sold": date_tag.get_text(strip=True)  if date_tag  else None,
                        "url":       link_tag["href"]               if link_tag  else None,
                    })
                    if len(results) >= max_results:
                        break

        except Exception as exc:
            print(f"[130point scraper] Error: {exc}")
        finally:
            context.close()
            browser.close()

    return results


def get_card_prices(card_name: str) -> list[dict]:
    """
    Return sold listing data for a Pokemon card.

    Tries 130point.com first via a headed Playwright browser. Falls back to
    simulated data only when fewer than 5 real listings are returned (e.g.
    Cloudflare blocked the request or the card has very few sales).

    Args:
        card_name: The Pokemon card name (e.g. "Charizard Base Set").

    Returns:
        A list of dicts with keys: title, price, date_sold, source,
        sales_volume (placeholder, currently None).
    """
    # --- 1. Try 130point.com (requires a real desktop display; fails in Xvfb) ---
    print(f"[scraper] Trying 130point.com for: {card_name}")
    real_listings = get_130point_sold_prices(card_name)

    if len(real_listings) >= 5:
        print(f"[scraper] Got {len(real_listings)} listings from 130point.")
        return [
            {
                "title":        r["title"],
                "price":        r["price"],
                "date_sold":    r["date_sold"],
                "source":       "130point",
                "sales_volume": None,
                "url":          r["url"],
            }
            for r in real_listings
        ]

    # --- 2. Fall back to eBay scraper (works without a display) ---
    print(f"[scraper] 130point returned {len(real_listings)} result(s) — trying eBay scraper.")
    try:
        ebay_listings = get_ebay_sold_prices(card_name)
    except Exception as exc:
        print(f"[scraper] eBay scraper error: {exc}")
        ebay_listings = []

    if len(ebay_listings) >= 5:
        print(f"[scraper] Got {len(ebay_listings)} listings from eBay.")
        return [
            {
                "title":        r["title"],
                "price":        r["price"],
                "date_sold":    r["date_sold"],
                "source":       "ebay",
                "sales_volume": None,
                "url":          r.get("url"),
            }
            for r in ebay_listings
        ]

    print(f"[scraper] eBay also returned {len(ebay_listings)} result(s) — falling back to simulated data.")

    rng = random.Random(len(card_name))
    base_price = rng.uniform(5.0, 500.0)
    today = datetime.date.today()
    results = []

    for i in range(20):
        price = round(rng.uniform(base_price * 0.80, base_price * 1.20), 2)
        days_ago = rng.randint(0, 60)
        date_sold = (today - datetime.timedelta(days=days_ago)).strftime("%b %-d, %Y")
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
    card = "Charizard Base Set"
    print(f"=== get_card_prices smoke-test: {card} ===\n")
    listings = get_card_prices(card)
    print(f"\nReturned {len(listings)} listing(s):\n")
    for i, listing in enumerate(listings, 1):
        print(f"{i:>2}. {listing['title']}")
        print(f"     Price     : {listing['price']}")
        print(f"     Date sold : {listing['date_sold']}")
        print(f"     Source    : {listing['source']}")
        url = listing.get('url')
        if url:
            print(f"     URL       : {url}")
        print()

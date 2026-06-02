import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode

# Mimic a real Chrome browser so eBay doesn't block the request
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
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
        "_ipg": "60",     # request 60 results per page (we'll cap at 20)
    }
    url = "https://www.ebay.com/sch/i.html?" + urlencode(params)

    # Fetch the search results page
    response = requests.get(url, headers=HEADERS, timeout=10)
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
        # eBay shows the sold date inside a <span class="POSITIVE"> or
        # a <span class="s-item__caption--signal POSITIVE"> element
        date_tag = item.select_one(".s-item__caption--signal, .POSITIVE")
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


if __name__ == "__main__":
    # Quick smoke-test: search for a common card and print results
    card = "Charizard VMAX"
    print(f"Fetching sold eBay listings for: {card}\n")
    listings = get_ebay_sold_prices(card)
    for i, listing in enumerate(listings, 1):
        print(f"{i}. {listing['title']}")
        print(f"   Price     : {listing['price']}")
        print(f"   Date sold : {listing['date_sold']}")
        print(f"   URL       : {listing['url']}\n")

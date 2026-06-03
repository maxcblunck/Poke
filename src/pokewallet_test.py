"""
Standalone test script for the PokéWallet API.

Usage:
    1. Put your API key in the .env file at the project root:
           POKEWALLET_API_KEY=pk_live_xxxxxxxxxxxx
    2. Run from the project root:
           python src/pokewallet_test.py

Prints the raw JSON response so you can inspect the exact field names
and structure before wiring it into the main app.
"""

import json
import os
import sys

import requests
from dotenv import load_dotenv

# Load .env from the project root (one level up from src/)
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(_env_path)

BASE_URL = "https://api.pokewallet.io"


def get_api_key() -> str:
    key = os.environ.get("POKEWALLET_API_KEY", "")
    if not key or key == "pk_live_your_key_here":
        sys.exit(
            "ERROR: Set POKEWALLET_API_KEY in your .env file before running this script."
        )
    return key


def search_card(query: str, page: int = 1, limit: int = 5) -> dict:
    """
    Search for cards using GET /search?q=<query>.

    Args:
        query: Card name, set code, card number, or combination.
        page:  Result page (default 1).
        limit: Results per page (default 5, max 100).

    Returns:
        Parsed JSON response dict.
    """
    url = f"{BASE_URL}/search"
    headers = {"X-API-Key": get_api_key()}
    params  = {"q": query, "page": page, "limit": limit}

    print(f"GET {url}")
    print(f"Params  : {params}")
    print(f"Headers : X-API-Key: {headers['X-API-Key'][:12]}…\n")

    response = requests.get(url, headers=headers, params=params, timeout=15)

    print(f"Status  : {response.status_code}")
    print(f"Rate limits:")
    for h in ("X-RateLimit-Limit-Hour", "X-RateLimit-Remaining-Hour",
              "X-RateLimit-Limit-Day",  "X-RateLimit-Remaining-Day"):
        if h in response.headers:
            print(f"  {h}: {response.headers[h]}")

    response.raise_for_status()
    return response.json()


def get_card(card_id: str) -> dict:
    """
    Fetch full card details + pricing using GET /cards/:id.
    """
    url = f"{BASE_URL}/cards/{card_id}"
    headers = {"X-API-Key": get_api_key()}

    print(f"\nGET {url}")
    response = requests.get(url, headers=headers, timeout=15)
    print(f"Status  : {response.status_code}")
    response.raise_for_status()
    return response.json()


def main():
    # Search specifically for base1-4 (Base Set Charizard card #4)
    # The API uses set_id format — "base1 4" queries set code base1, card number 4
    queries = ["base1 4", "Charizard base1"]
    api_key = get_api_key()
    headers = {"X-API-Key": api_key}
    card_id = None

    print("=" * 60)
    print("PokéWallet API test — Charizard base1-4")
    print("=" * 60 + "\n")

    # ── Step 1: broad search, then scan all pages for Base Set ──────
    print("Searching 'Charizard' across up to 3 pages (limit=20 each)…\n")
    result = {}
    for page in range(1, 4):
        result = search_card("Charizard", page=page, limit=20)
        cards = result.get("data") or result.get("results") or []
        print(f"Page {page}: {len(cards)} result(s)")

        # Dump the first raw card object on page 1 to reveal the schema
        if cards and page == 1:
            print("\n  --- First raw search result (full object) ---")
            print("  " + json.dumps(cards[0], indent=4).replace("\n", "\n  "))
            print()

        for c in cards:
            # Fields nest under card_info in search results
            info     = c.get("card_info") or c
            name     = info.get("name", "")
            set_name = info.get("set_name", "")
            print(f"  -> {name!r:55s} set: {set_name!r}")
            if "charizard" in name.lower() and "base set" in set_name.lower():
                card_id = c.get("id")
                print(f"  [MATCH] Matched Base Set Charizard")
                break
        if card_id:
            break
        total_pages = result.get("pagination", {}).get("total_pages", 1)
        if page >= total_pages:
            break
        print()

    if not card_id:
        print("\nCould not find Base Set Charizard. Printing last search response:")
        print(json.dumps(result, indent=2))
        return

    # ── Step 2: full card detail ─────────────────────────────────
    print(f"\n── Fetching full details for id: {card_id[:40]}… ──")
    detail = get_card(card_id)

    print("\n── COMPLETE RAW RESPONSE (every field) ─────────────────")
    print(json.dumps(detail, indent=2))

    # ── Step 3: field name summary ───────────────────────────────
    print("\n── TOP-LEVEL FIELDS ────────────────────────────────────")
    for k, v in detail.items():
        preview = json.dumps(v)[:80].replace("\n", " ")
        print(f"  {k:<20} : {preview}")

    print("\n── card_info FIELDS ────────────────────────────────────")
    for k, v in (detail.get("card_info") or {}).items():
        preview = json.dumps(v)[:80].replace("\n", " ")
        print(f"  {k:<20} : {preview}")

    print("\n── tcgplayer FIELDS ────────────────────────────────────")
    tcg = detail.get("tcgplayer") or {}
    for k, v in tcg.items():
        if k != "prices":
            print(f"  {k:<20} : {json.dumps(v)[:80]}")
    for i, p in enumerate(tcg.get("prices") or []):
        print(f"\n  prices[{i}]:")
        for pk, pv in p.items():
            print(f"    {pk:<22} : {pv}")

    cardmarket = detail.get("cardmarket")
    if cardmarket:
        print("\n── cardmarket FIELDS ───────────────────────────────────")
        print(json.dumps(cardmarket, indent=2))
    else:
        print("\n── cardmarket: not present ─────────────────────────────")


if __name__ == "__main__":
    main()

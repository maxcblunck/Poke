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
    query = "Charizard"
    print("=" * 60)
    print(f"PokéWallet API test — searching for: {query!r}")
    print("=" * 60 + "\n")

    # ── Step 1: search ───────────────────────────────────────────
    search_result = search_card(query, limit=5)

    print("\n── Raw search response ─────────────────────────────────")
    print(json.dumps(search_result, indent=2))

    # ── Step 2: fetch full details for the first result ──────────
    cards = search_result.get("data") or search_result.get("results") or []
    if not cards:
        print("\nNo cards returned — check your API key and query.")
        return

    first_id = cards[0].get("id")
    if not first_id:
        print("\nFirst result has no 'id' field — printing raw card:")
        print(json.dumps(cards[0], indent=2))
        return

    print(f"\n── Fetching full details for card id: {first_id} ──────")
    card_detail = get_card(first_id)

    print("\n── Raw card detail response ────────────────────────────")
    print(json.dumps(card_detail, indent=2))

    # ── Step 3: summary of pricing fields found ──────────────────
    print("\n── Pricing field summary ───────────────────────────────")
    for source in ("tcgplayer", "cardmarket"):
        pricing = card_detail.get(source)
        if pricing:
            print(f"\n{source}:")
            print(json.dumps(pricing, indent=2))
        else:
            print(f"\n{source}: not present in response")


if __name__ == "__main__":
    main()

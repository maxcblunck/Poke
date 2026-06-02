import time
import random

from scraper import get_ebay_sold_prices
from analyzer import analyze_card
from reporter import print_report

# Cards to look up — edit this list to add or remove targets
CARDS = [
    "Charizard Base Set",
    "Pikachu Illustrator",
    "Blastoise Base Set",
    "Mewtwo Base Set",
    "Lugia Neo Genesis",
]


def main():
    print(f"Starting price check for {len(CARDS)} cards...\n")

    for i, card_name in enumerate(CARDS):
        print(f"[{i + 1}/{len(CARDS)}] Searching eBay for: {card_name}")

        # Step 1: Scrape eBay sold listings for this card
        listings = get_ebay_sold_prices(card_name)
        print(f"         Found {len(listings)} listing(s).")

        # Step 2: Calculate summary statistics and the value signal
        analysis = analyze_card(card_name, listings)

        # Step 3: Print the report to the terminal and save it to CSV
        print_report(analysis)

        # Step 4: Wait a random 2–5 seconds before the next request so eBay
        # does not flag the traffic as a bot and start returning blocked pages
        if i < len(CARDS) - 1:
            delay = random.uniform(2, 5)
            print(f"  Waiting {delay:.1f}s before next search...")
            time.sleep(delay)

    print("Done. All results saved to data/prices/results.csv")


if __name__ == "__main__":
    main()

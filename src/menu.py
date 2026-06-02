import time


class Menu:
    """
    Interactive terminal menu for the Pokemon card price tracker.

    Dependencies are injected so the menu is not coupled to any specific
    scraper implementation — swap get_card_prices for the real eBay scraper
    without touching this file.
    """

    def __init__(self, db, get_card_prices, analyze_card, print_report):
        """
        Args:
            db:               CardDatabase instance (already loaded).
            get_card_prices:  Callable(card_name) → list of price dicts.
            analyze_card:     Callable(card_name, prices_list) → analysis dict.
            print_report:     Callable(analysis_dict) → None (prints + saves CSV).
        """
        self.db = db
        self.get_card_prices = get_card_prices
        self.analyze_card = analyze_card
        self.print_report = print_report

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self):
        """Start the main menu loop. Runs until the user chooses Exit."""
        while True:
            self._print_menu()
            choice = input("Choose an option: ").strip()

            if choice == "1":
                self._search_card()
            elif choice == "2":
                self._scan_rare_cards(target_signal="undervalued")
            elif choice == "3":
                self._scan_rare_cards(target_signal="overvalued")
            elif choice == "4":
                print("\nGoodbye!")
                break
            else:
                print("\nInvalid choice. Please enter 1, 2, 3, or 4.\n")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _print_menu(self):
        """Render the top-level menu options."""
        print("\n" + "=" * 44)
        print("  Pokemon Card Price Tracker")
        print("=" * 44)
        print("  1) Search a card by name")
        print("  2) Show undervalued cards")
        print("  3) Show overvalued cards")
        print("  4) Exit")
        print("=" * 44)

    def _search_card(self):
        """
        Option 1: let the user type a partial name, show matching cards,
        let them pick one, then fetch prices → analyze → print report.
        """
        query = input("\nEnter card name to search: ").strip()
        if not query:
            print("No input provided.")
            return

        # Search the local database for partial, case-insensitive matches
        matches = self.db.search_card(query)

        if not matches:
            print(f"\nNo cards found matching '{query}'.")
            return

        # Show the match list so the user can pick by number
        print(f"\nFound {len(matches)} match(es):\n")
        for i, card in enumerate(matches):
            print(
                f"  {i + 1:>3}. {card['name']:<30} "
                f"Set: {card['set_name']:<12} "
                f"#{card['number']:<6} "
                f"{card['rarity'] or 'Unknown'}"
            )

        # Ask the user to pick one entry from the list
        try:
            pick = int(input("\nEnter number to analyse (0 to cancel): "))
        except ValueError:
            print("Invalid input.")
            return

        if pick == 0:
            return

        if not (1 <= pick <= len(matches)):
            print("Number out of range.")
            return

        chosen = matches[pick - 1]
        card_label = f"{chosen['name']} ({chosen['set_name']})"
        print(f"\nFetching prices for: {card_label}")

        # Fetch, analyse, and report for the chosen card
        prices = self.get_card_prices(card_label)
        analysis = self.analyze_card(card_label, prices)
        self.print_report(analysis)

    def _scan_rare_cards(self, target_signal: str):
        """
        Options 2 & 3: fetch the top 20 rare holo cards, analyse each one,
        and list only those whose value_signal matches target_signal.

        A 1-second delay is inserted between each lookup so we don't
        hammer the scraper API with rapid-fire requests.

        Args:
            target_signal: 'undervalued' or 'overvalued'.
        """
        label = target_signal.capitalize()
        print(f"\nScanning top 20 rare cards for {label} ones...")
        print("This may take a moment.\n")

        # Pull the full rare list from the database and take the first 20
        rare_cards = self.db.get_rare_cards()[:20]

        if not rare_cards:
            print("No rare cards found in the database.")
            return

        flagged = []

        for i, card in enumerate(rare_cards):
            card_label = f"{card['name']} ({card['set_name']})"
            print(f"  [{i + 1}/{len(rare_cards)}] Checking: {card_label}")

            prices = self.get_card_prices(card_label)
            analysis = self.analyze_card(card_label, prices)

            # Collect cards that match the requested signal
            if analysis.get("value_signal") == target_signal:
                flagged.append(analysis)

            # Pause between requests to avoid overwhelming the API
            if i < len(rare_cards) - 1:
                time.sleep(1)

        # Display results
        print(f"\n{'=' * 44}")
        print(f"  {label} cards ({len(flagged)} found)")
        print(f"{'=' * 44}")

        if not flagged:
            print(f"  No {target_signal} cards found in this scan.")
        else:
            for a in flagged:
                avg = f"${a['average_price']:.2f}" if a["average_price"] else "N/A"
                print(f"  {a['card_name']:<40} avg {avg}")

        print()


if __name__ == "__main__":
    # Wire everything together for a quick smoke-test
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))

    from card_db import CardDatabase
    from scraper import get_card_prices
    from analyzer import analyze_card
    from reporter import print_report

    db = CardDatabase()
    menu = Menu(db, get_card_prices, analyze_card, print_report)
    menu.run()

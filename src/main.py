from card_db import CardDatabase
from scraper import get_card_prices
from analyzer import analyze_card
from reporter import print_report
from menu import Menu


def main():
    # Step 1: Load all card data from data/cards/en/ into memory.
    # CardDatabase reads every JSON file once at init time so all subsequent
    # lookups run from RAM without any further disk I/O.
    print("Loading card database...")
    db = CardDatabase()
    print(f"Loaded {len(db._cards):,} cards from {len(db._cards)} entries.\n")

    # Step 2: Create the Menu, injecting each dependency so the menu itself
    # stays decoupled from any specific scraper or reporter implementation.
    menu = Menu(
        db=db,
        get_card_prices=get_card_prices,
        analyze_card=analyze_card,
        print_report=print_report,
    )

    # Step 3: Hand control to the menu loop. It will run until the user
    # selects Exit, at which point run() returns and the program ends.
    menu.run()


if __name__ == "__main__":
    main()

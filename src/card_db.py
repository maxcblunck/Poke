import json
import os
import glob
from src.set_names import get_set_name

# All rarities that are considered "Rare Holo or higher".
# Common, Uncommon, Rare (non-holo), and Promo are excluded.
RARE_HOLO_AND_ABOVE = {
    "Rare Holo",
    "Rare Holo EX",
    "Rare Holo GX",
    "Rare Holo LV.X",
    "Rare Holo Star",
    "Rare Holo V",
    "Rare Holo VMAX",
    "Rare Holo VSTAR",
    "Rare Ultra",
    "Rare Secret",
    "Rare Rainbow",
    "Rare Shining",
    "Rare Shiny",
    "Rare Shiny GX",
    "Rare Prime",
    "Rare Prism Star",
    "Rare ACE",
    "Rare BREAK",
    "Amazing Rare",
    "Radiant Rare",
    "Double Rare",
    "Ultra Rare",
    "Hyper Rare",
    "Illustration Rare",
    "Special Illustration Rare",
    "Shiny Rare",
    "Shiny Ultra Rare",
    "Trainer Gallery Rare Holo",
    "LEGEND",
    "ACE SPEC Rare",
    "Black White Rare",
    "Classic Collection",
    "MEGA_ATTACK_RARE",
    "Mega Hyper Rare",
}

# Directory containing one JSON file per set (e.g. base1.json, bw1.json)
CARDS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cards", "en")


class CardDatabase:
    """
    Loads all Pokemon card JSON files from data/cards/en/ into memory once
    and exposes search and filter methods.

    Each card dict is augmented with a 'set_name' key derived from its
    filename (e.g. base1.json → 'base1') because the JSON files themselves
    do not embed a set name field.
    """

    def __init__(self):
        # _cards holds every card across all sets as a flat list of dicts.
        # Loading everything up-front means all methods run from RAM with no
        # further disk I/O.
        self._cards: list[dict] = []
        self._load_all()

    def _load_all(self):
        """Read every JSON file in the cards directory and flatten into one list."""
        pattern = os.path.join(os.path.abspath(CARDS_DIR), "*.json")
        files = sorted(glob.glob(pattern))

        for filepath in files:
            set_code = os.path.splitext(os.path.basename(filepath))[0]
            set_name = get_set_name(set_code)   # human-readable, e.g. "Base Set"

            with open(filepath, encoding="utf-8") as f:
                cards = json.load(f)

            for card in cards:
                card["set_name"] = set_name
                card["set_code"] = set_code     # keep raw code for API lookups

            self._cards.extend(cards)

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def search_card(self, name: str) -> list[dict]:
        """
        Return cards whose name contains `name` (case-insensitive partial match).

        For example, searching 'char' matches 'Charizard', 'Charmeleon', etc.

        Returns a lightweight summary list — use get_card_details() for full data.
        """
        needle = name.lower()

        results = []
        for card in self._cards:
            if needle in card.get("name", "").lower():
                results.append({
                    "name":     card.get("name"),
                    "set_name": card.get("set_name"),
                    "set_code": card.get("set_code"),
                    "number":   card.get("number"),
                    "rarity":   card.get("rarity"),
                })

        return results

    def get_rare_cards(self) -> list[dict]:
        """
        Return all cards whose rarity is 'Rare Holo' or higher.

        The full set of qualifying rarities is defined in RARE_HOLO_AND_ABOVE
        at the top of this file.
        """
        results = []
        for card in self._cards:
            if card.get("rarity") in RARE_HOLO_AND_ABOVE:
                results.append({
                    "name":     card.get("name"),
                    "set_name": card.get("set_name"),
                    "set_code": card.get("set_code"),
                    "number":   card.get("number"),
                    "rarity":   card.get("rarity"),
                })

        return results

    def get_card_details(
        self, name: str, set_name: str, number: str | None = None
    ) -> dict | None:
        """
        Return the full card dict identified by name and set name
        (both case-insensitive). When number is provided all three fields
        must match, which disambiguates cards that share a name within a
        set (e.g. Charizard ex Double Rare vs Special Illustration Rare).
        Falls back to the first name+set match if number is given but not
        found, so existing callers that omit number keep working.

        Returns None if no match is found at all.
        """
        name_lower = name.lower()
        set_lower  = set_name.lower()
        fallback   = None

        for card in self._cards:
            if (
                card.get("name", "").lower() == name_lower
                and card.get("set_name", "").lower() == set_lower
            ):
                if number is None or str(card.get("number", "")) == str(number):
                    return card
                if fallback is None:
                    fallback = card

        return fallback


if __name__ == "__main__":
    db = CardDatabase()

    # --- smoke test: search ---
    print(f"Total cards loaded: {len(db._cards)}\n")

    hits = db.search_card("char")
    print(f"search_card('char') → {len(hits)} result(s)")
    for card in hits[:5]:
        print(f"  {card['name']} | {card['set_name']} | #{card['number']} | {card['rarity']}")

    # --- smoke test: rare cards ---
    rares = db.get_rare_cards()
    print(f"\nget_rare_cards() → {len(rares)} card(s)")

    # --- smoke test: full details ---
    details = db.get_card_details("Charizard", "base1")
    if details:
        print(f"\nget_card_details('Charizard', 'base1'):")
        print(f"  id      : {details.get('id')}")
        print(f"  rarity  : {details.get('rarity')}")
        print(f"  hp      : {details.get('hp')}")
        print(f"  artist  : {details.get('artist')}")
    else:
        print("Card not found.")

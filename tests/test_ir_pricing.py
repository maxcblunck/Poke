"""
Regression tests: Illustration Rares must never inherit Common card pricing.

Run with:  python -m pytest tests/test_ir_pricing.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.card_db import CardDatabase
from src.card_valuator import valuate_card, BASE_PRICES
from src.scraper import _get_base_price, _is_premium_range, _composite_cache_key


def _find_card(db: CardDatabase, card_id: str):
    return next((c for c in db._cards if c.get("id") == card_id), None)


class TestMe4RarityPricing:
    """Chaos Rising (me4) — 122-card base set, premium variants at 123+."""

    def setup_method(self):
        self.db = CardDatabase()

    def test_ir_base_price_greater_than_common_base_price(self):
        """valuate_card must return a higher simulated price for an IR than a Common."""
        assert BASE_PRICES["Illustration Rare"] > BASE_PRICES["Common"]

    def test_chespin_ir_vs_common_in_db(self):
        """me4-87 is an IR Chespin; it must price higher than any Common Chespin."""
        ir_card = _find_card(self.db, "me4-87")
        assert ir_card is not None, "me4-87 (Chespin IR) not found in DB"
        assert ir_card["rarity"] == "Illustration Rare"

        ir_price = valuate_card(ir_card)["simulated_price"]
        assert ir_price > 0

        # Find any Common Chespin in the DB (any set) to compare
        common_cards = [
            c for c in self.db._cards
            if c.get("name", "").lower() == "chespin" and c.get("rarity") == "Common"
        ]
        if common_cards:
            common_price = valuate_card(common_cards[0])["simulated_price"]
            assert ir_price > common_price, (
                f"IR price ${ir_price:.2f} must be greater than "
                f"Common price ${common_price:.2f}"
            )

    def test_get_base_price_ir_by_id(self):
        """_get_base_price with an in-DB IR local_id must not return the Common price."""
        ir_price     = _get_base_price("Chespin", "me4-87")
        common_price = BASE_PRICES["Common"]
        assert ir_price is not None, "IR price should not be None for an in-DB card"
        assert ir_price > common_price, (
            f"_get_base_price returned ${ir_price:.2f} for IR, "
            f"which is not greater than Common base ${common_price:.2f}"
        )

    def test_get_base_price_premium_range_returns_none(self):
        """
        A card whose collector number exceeds me4's 122-card DB count is a
        premium variant not in the local DB.  _get_base_price must return None
        rather than substituting a Common price.
        """
        # me4 has 122 cards in the DB; 150 is out of range
        result = _get_base_price("Froakie", "me4-150")
        assert result is None, (
            f"Expected None for out-of-DB premium card me4-150, got {result}"
        )

    def test_is_premium_range_true_above_set_count(self):
        assert _is_premium_range("me4-150") is True

    def test_is_premium_range_false_within_set_count(self):
        assert _is_premium_range("me4-87") is False

    def test_is_premium_range_false_for_no_id(self):
        assert _is_premium_range("") is False

    def test_composite_cache_key_differs_for_ir_and_common(self):
        """IR and Common of the same Pokémon must produce different cache keys."""
        ir_key     = _composite_cache_key("Chespin", "me4-87")   # IR in DB
        common_key = _composite_cache_key("Chespin", "me4-1")    # Common (card 1 in set)
        assert ir_key != common_key, (
            "IR and Common share the same cache key — "
            f"both resolved to {ir_key!r}"
        )

    def test_ir_cache_key_contains_rarity_slug(self):
        key = _composite_cache_key("Chespin", "me4-87")
        assert "illustration-rare" in key, f"Expected rarity slug in key, got {key!r}"

    def test_format_card_number_uses_base_set_size(self):
        """IR cards must produce 'N/86' notation, not 'N/122'."""
        from src.scraper import _format_card_number
        fraction = _format_card_number("me4-87")
        assert fraction is not None
        num, _, total = fraction.partition("/")
        assert num == "87", f"Expected num=87, got {num!r}"
        assert int(total) == 86, (
            f"Fraction denominator should be base set size 86, got {total!r}. "
            "Wrong denominator causes the skip-fraction guard to mis-classify "
            "secret rares and sends '87/122' to PokéWallet instead of '87/86'."
        )

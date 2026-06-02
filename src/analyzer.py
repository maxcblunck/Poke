import re
import statistics


def _parse_price(price_str: str) -> float | None:
    """
    Convert a raw eBay price string like '$12.99' or '$10.00 to $15.00'
    into a single float. For ranges, takes the lower bound.
    Returns None if the string cannot be parsed.
    """
    if not price_str:
        return None

    # Strip currency symbols, commas, and whitespace, then grab the first
    # numeric value found (handles both single prices and ranges)
    match = re.search(r"[\d,]+\.?\d*", price_str.replace(",", ""))
    if not match:
        return None

    return float(match.group())


def analyze_card(card_name: str, prices_list: list[dict]) -> dict:
    """
    Analyze eBay sold listing data for a Pokemon card.

    Args:
        card_name:   The name of the card being analyzed.
        prices_list: List of dicts from get_ebay_sold_prices(), each with
                     keys: title, price, date_sold, url.

    Returns:
        A dict with keys:
            card_name, num_sales, average_price, median_price,
            lowest_price, highest_price, value_signal.
    """

    # --- Parse raw price strings into floats, skipping any unparseable entries ---
    parsed_prices = []
    for listing in prices_list:
        value = _parse_price(listing.get("price", ""))
        if value is not None:
            parsed_prices.append(value)

    # Can't analyze without at least one valid price
    if not parsed_prices:
        return {
            "card_name": card_name,
            "num_sales": 0,
            "average_price": None,
            "median_price": None,
            "lowest_price": None,
            "highest_price": None,
            # Always return a string so callers can safely call .upper() etc.
            "value_signal": "insufficient data",
        }

    # --- Overall summary statistics ---
    overall_average = sum(parsed_prices) / len(parsed_prices)
    overall_median = statistics.median(parsed_prices)
    lowest = min(parsed_prices)
    highest = max(parsed_prices)

    # --- Value signal: compare the 5 most recent sales to the overall average ---
    # The input list is already sorted most-recent-first (eBay sort order),
    # so the first 5 entries represent the most recent sales.
    recent_prices = parsed_prices[:5]

    if len(recent_prices) >= 2:
        recent_average = sum(recent_prices) / len(recent_prices)

        # Calculate how much the recent average deviates from the overall average
        deviation = (recent_average - overall_average) / overall_average

        if deviation < -0.15:
            # Recent sales are more than 15% below the overall average
            value_signal = "undervalued"
        elif deviation > 0.15:
            # Recent sales are more than 15% above the overall average
            value_signal = "overvalued"
        else:
            value_signal = "fair value"
    else:
        # Not enough recent data to make a reliable signal
        value_signal = "insufficient data"

    return {
        "card_name": card_name,
        "num_sales": len(parsed_prices),
        "average_price": round(overall_average, 2),
        "median_price": round(overall_median, 2),
        "lowest_price": round(lowest, 2),
        "highest_price": round(highest, 2),
        "value_signal": value_signal,
    }


if __name__ == "__main__":
    # Smoke-test with synthetic data that mimics get_ebay_sold_prices() output
    sample_listings = [
        {"title": "Charizard VMAX PSA 10", "price": "$45.00", "date_sold": "Jun 1, 2026", "url": "https://ebay.com/1"},
        {"title": "Charizard VMAX Raw",    "price": "$20.00", "date_sold": "May 30, 2026", "url": "https://ebay.com/2"},
        {"title": "Charizard VMAX CGC 9",  "price": "$38.00", "date_sold": "May 28, 2026", "url": "https://ebay.com/3"},
        {"title": "Charizard VMAX Holo",   "price": "$22.00", "date_sold": "May 25, 2026", "url": "https://ebay.com/4"},
        {"title": "Charizard VMAX LP",     "price": "$18.00", "date_sold": "May 20, 2026", "url": "https://ebay.com/5"},
        {"title": "Charizard VMAX NM",     "price": "$60.00", "date_sold": "May 15, 2026", "url": "https://ebay.com/6"},
        {"title": "Charizard VMAX PSA 9",  "price": "$55.00", "date_sold": "May 10, 2026", "url": "https://ebay.com/7"},
    ]

    result = analyze_card("Charizard VMAX", sample_listings)

    for key, value in result.items():
        print(f"{key:>16}: {value}")

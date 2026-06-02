import re
import statistics


# ---------------------------------------------------------------------------
# Rarity price ranges: (min_expected, max_expected) in USD.
# Used by the rarity baseline check when card_details are provided.
# ---------------------------------------------------------------------------
RARITY_RANGES = {
    "Common":       (0.10,   2.00),
    "Uncommon":     (0.50,   5.00),
    "Rare":         (2.00,  20.00),
    "Rare Holo":    (5.00, 100.00),
    "Rare Ultra":  (20.00, 500.00),
    "Rare Secret": (100.00, 1000.00),
}


def _parse_price(price_str: str) -> float | None:
    """
    Convert a raw price string like '$12.99' or '$10.00 to $15.00' into a
    single float. For ranges, takes the lower bound.
    Returns None if the string cannot be parsed.
    """
    if not price_str:
        return None

    # Remove commas so "1,200.00" parses correctly, then grab the first
    # numeric value in the string (handles currency symbols and ranges)
    match = re.search(r"\d+\.?\d*", price_str.replace(",", ""))
    if not match:
        return None

    return float(match.group())


def _null_result(card_name: str) -> dict:
    """Return the standard 'insufficient data' dict when we can't analyze."""
    return {
        "card_name":        card_name,
        "num_sales":        0,
        "average_price":    None,
        "median_price":     None,
        "lowest_price":     None,
        "highest_price":    None,
        "trend":            None,
        "trend_pct_change": None,
        "volatility":       None,
        "volatility_std":   None,
        "rarity_baseline":  None,
        "composite_score":  None,
        "recommendation":   "Insufficient Data",
    }


def analyze_card(card_name: str, prices_list: list[dict], card_details: dict | None = None) -> dict:
    """
    Analyze sold listing data for a Pokemon card and return a comprehensive
    valuation dictionary.

    Args:
        card_name:    Name of the card being analyzed.
        prices_list:  List of price dicts from get_card_prices() / get_ebay_sold_prices().
                      Each dict must have a 'price' key (string or numeric).
                      Assumed to be sorted most-recent-first.
        card_details: Optional full card dict from CardDatabase.get_card_details().
                      Used for the rarity baseline check. Pass None to skip it.

    Returns:
        Dict with keys: card_name, num_sales, average_price, median_price,
        lowest_price, highest_price, trend, trend_pct_change, volatility,
        volatility_std, rarity_baseline, composite_score, recommendation.
    """

    # -----------------------------------------------------------------------
    # 1. Parse all price strings into floats, skipping unparseable entries
    # -----------------------------------------------------------------------
    parsed_prices = []
    for listing in prices_list:
        raw = listing.get("price", "")
        # Accept prices already stored as numbers (e.g. from simulated data)
        if isinstance(raw, (int, float)):
            parsed_prices.append(float(raw))
        else:
            value = _parse_price(raw)
            if value is not None:
                parsed_prices.append(value)

    # Need at least 5 prices to produce meaningful trend and volatility figures
    if len(parsed_prices) < 5:
        return _null_result(card_name)

    # -----------------------------------------------------------------------
    # 2. Basic summary statistics
    # -----------------------------------------------------------------------
    average_price = statistics.mean(parsed_prices)
    median_price  = statistics.median(parsed_prices)
    lowest_price  = min(parsed_prices)
    highest_price = max(parsed_prices)

    # -----------------------------------------------------------------------
    # 3. Trend — compare the 5 most recent sales to the 5 oldest sales.
    #    The input list is most-recent-first, so:
    #      parsed_prices[:5]  = the 5 newest sales
    #      parsed_prices[-5:] = the 5 oldest sales
    #    Percentage change = (recent_avg - old_avg) / old_avg * 100
    #    >+5%  → 'rising'   (price is climbing)
    #    <-5%  → 'falling'  (price is dropping)
    #    else  → 'stable'
    # -----------------------------------------------------------------------
    recent_avg = statistics.mean(parsed_prices[:5])
    oldest_avg = statistics.mean(parsed_prices[-5:])

    # Guard against a zero oldest_avg to avoid division by zero
    if oldest_avg == 0:
        trend_pct_change = 0.0
    else:
        trend_pct_change = (recent_avg - oldest_avg) / oldest_avg * 100

    if trend_pct_change > 5:
        trend = "rising"
    elif trend_pct_change < -5:
        trend = "falling"
    else:
        trend = "stable"

    # -----------------------------------------------------------------------
    # 4. Volatility — standard deviation expressed as a fraction of the mean
    #    (coefficient of variation).
    #    < 15% of mean → 'stable'    (consistent prices)
    #    < 30% of mean → 'moderate'  (some spread)
    #    ≥ 30% of mean → 'volatile'  (wide price swings)
    # -----------------------------------------------------------------------
    std_dev = statistics.stdev(parsed_prices)  # sample std dev (n-1)

    # Coefficient of variation: normalise std dev to the mean so the label
    # is comparable across cards with very different price levels
    if average_price == 0:
        cv = 0.0
    else:
        cv = std_dev / average_price

    if cv < 0.15:
        volatility = "stable"
    elif cv < 0.30:
        volatility = "moderate"
    else:
        volatility = "volatile"

    # -----------------------------------------------------------------------
    # 5. Rarity baseline — only calculated when card_details is provided.
    #    Compares the average price against the expected range for the card's
    #    rarity using RARITY_RANGES defined at the top of this file.
    #    Returns 'within range', 'below range', 'above range', or None if
    #    rarity data is unavailable.
    # -----------------------------------------------------------------------
    rarity_baseline = None
    if card_details:
        rarity = card_details.get("rarity")
        if rarity and rarity in RARITY_RANGES:
            low, high = RARITY_RANGES[rarity]
            if average_price < low:
                rarity_baseline = "below range"
            elif average_price > high:
                rarity_baseline = "above range"
            else:
                rarity_baseline = "within range"

    # -----------------------------------------------------------------------
    # 6. Composite score (-100 to +100)
    #
    #    A higher score means the card looks more undervalued (good to buy).
    #    A lower score means it looks more overvalued (consider selling).
    #
    #    Component A — price vs average (weight 40%)
    #      Compares the most recent sale to the overall average.
    #      Below average → positive contribution (potential bargain).
    #      Above average → negative contribution (potentially overpriced).
    #      Clamped to ±50 before weighting to prevent one outlier dominating.
    #
    #    Component B — trend direction (weight 30%)
    #      'falling' prices → positive (buying opportunity if it rebounds).
    #      'rising'  prices → negative (momentum may be spent).
    #      'stable'  prices → neutral.
    #
    #    Component C — volatility (weight 15%)
    #      'stable'   → positive (predictable, lower risk).
    #      'moderate' → neutral.
    #      'volatile' → negative (harder to time a purchase).
    #
    #    Component D — rarity baseline (weight 15%)
    #      'below range' → positive (underpriced for its rarity tier).
    #      'above range' → negative (overpriced for its rarity tier).
    #      'within range' or None → neutral.
    # -----------------------------------------------------------------------

    # Component A: price vs average
    # Use the most recent price (index 0) as the current market price.
    # Express deviation as a percentage of the average, clamped to ±50.
    most_recent_price = parsed_prices[0]
    if average_price > 0:
        price_deviation_pct = (average_price - most_recent_price) / average_price * 100
    else:
        price_deviation_pct = 0.0
    price_vs_avg_raw = max(-50, min(50, price_deviation_pct))  # clamp to [-50, 50]
    component_a = price_vs_avg_raw * 0.40                      # weight: 40%

    # Component B: trend direction
    trend_scores = {"falling": 50, "stable": 0, "rising": -50}
    component_b = trend_scores[trend] * 0.30                   # weight: 30%

    # Component C: volatility
    volatility_scores = {"stable": 30, "moderate": 0, "volatile": -30}
    component_c = volatility_scores[volatility] * 0.15         # weight: 15%

    # Component D: rarity baseline
    baseline_scores = {
        "below range":  50,
        "within range":  0,
        "above range": -50,
        None:            0,   # no rarity data → neutral
    }
    component_d = baseline_scores.get(rarity_baseline, 0) * 0.15  # weight: 15%

    # Sum all weighted components; round to one decimal place
    composite_score = round(component_a + component_b + component_c + component_d, 1)

    # -----------------------------------------------------------------------
    # 7. Recommendation label based on composite score thresholds
    # -----------------------------------------------------------------------
    if composite_score > 60:
        recommendation = "Strong Buy"
    elif composite_score > 30:
        recommendation = "Buy"
    elif composite_score >= -30:
        recommendation = "Fair Value"
    elif composite_score >= -60:
        recommendation = "Sell"
    else:
        recommendation = "Strong Sell"

    return {
        "card_name":        card_name,
        "num_sales":        len(parsed_prices),
        "average_price":    round(average_price, 2),
        "median_price":     round(median_price, 2),
        "lowest_price":     round(lowest_price, 2),
        "highest_price":    round(highest_price, 2),
        "trend":            trend,
        "trend_pct_change": round(trend_pct_change, 1),
        "volatility":       volatility,
        "volatility_std":   round(std_dev, 2),
        "rarity_baseline":  rarity_baseline,
        "composite_score":  composite_score,
        "recommendation":   recommendation,
    }


if __name__ == "__main__":
    # -----------------------------------------------------------------------
    # Smoke-test: three scenarios
    # -----------------------------------------------------------------------

    # Scenario 1: rising, cheap relative to Rare Holo range → should Buy/Strong Buy
    listings_rising = [
        {"price": "$18.00"},  # recent (most-recent-first)
        {"price": "$17.50"},
        {"price": "$16.00"},
        {"price": "$15.50"},
        {"price": "$15.00"},
        {"price": "$10.00"},  # older
        {"price": "$10.00"},
        {"price": "$9.50"},
        {"price": "$9.00"},
        {"price": "$8.50"},
    ]
    rare_holo_details = {"rarity": "Rare Holo"}

    r1 = analyze_card("Charizard Base Set", listings_rising, rare_holo_details)
    print("=== Scenario 1: rising price, within Rare Holo range ===")
    for k, v in r1.items():
        print(f"  {k:<20}: {v}")

    # Scenario 2: falling, stable, within Rare range
    listings_falling = [
        {"price": "$5.00"},
        {"price": "$5.50"},
        {"price": "$6.00"},
        {"price": "$6.50"},
        {"price": "$7.00"},
        {"price": "$10.00"},
        {"price": "$11.00"},
        {"price": "$12.00"},
        {"price": "$13.00"},
        {"price": "$14.00"},
    ]
    r2 = analyze_card("Blastoise Base Set", listings_falling, {"rarity": "Rare"})
    print("\n=== Scenario 2: falling price, within Rare range ===")
    for k, v in r2.items():
        print(f"  {k:<20}: {v}")

    # Scenario 3: fewer than 5 prices → Insufficient Data
    r3 = analyze_card("Pikachu Promo", [{"price": "$3.00"}, {"price": "$4.00"}])
    print("\n=== Scenario 3: fewer than 5 prices ===")
    for k, v in r3.items():
        print(f"  {k:<20}: {v}")

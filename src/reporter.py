import csv
import os
from datetime import datetime, timezone

# Path to the CSV file where results are accumulated across runs
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "prices", "results.csv")

# All columns written to the CSV — must stay in sync with the row dict below
CSV_COLUMNS = [
    "timestamp",
    "card_name",
    "num_sales",
    "average_price",
    "median_price",
    "lowest_price",
    "highest_price",
    "trend",
    "trend_pct_change",
    "volatility",
    "volatility_std",
    "rarity_baseline",
    "composite_score",
    "recommendation",
]

# Emoji and label shown next to the final recommendation
RECOMMENDATION_STYLE = {
    "Strong Buy":       ("🟢", "STRONG BUY"),
    "Buy":              ("🟡", "BUY"),
    "Fair Value":       ("⚪", "FAIR VALUE"),
    "Sell":             ("🟠", "SELL"),
    "Strong Sell":      ("🔴", "STRONG SELL"),
    "Insufficient Data":("⬛", "INSUFFICIENT DATA"),
}

# Bar chart settings
BAR_WIDTH    = 20   # total number of character cells in the bar
FILLED_CHAR  = "█"
EMPTY_CHAR   = "░"


def _fmt_price(value) -> str:
    """Format a price float as '$X.XX', or return 'N/A' for None."""
    return f"${value:.2f}" if value is not None else "N/A"


def _composite_bar(score) -> str:
    """
    Render a fixed-width block bar that shows where the composite score sits
    on the -100 → +100 scale, followed by the numeric score.

    Example for +67:  '████████████████░░░░ +67'
    Example for -40:  '████░░░░░░░░░░░░░░░░ -40'

    Mapping: score -100 → 0 filled blocks, score +100 → BAR_WIDTH filled blocks.
    """
    if score is None:
        return "N/A"

    # Convert the -100..+100 range to 0..BAR_WIDTH filled blocks
    filled = round((score + 100) / 200 * BAR_WIDTH)
    filled = max(0, min(BAR_WIDTH, filled))   # clamp in case of float edge cases
    empty  = BAR_WIDTH - filled

    bar = FILLED_CHAR * filled + EMPTY_CHAR * empty
    sign = "+" if score >= 0 else ""
    return f"{bar} {sign}{score}"


def print_report(analysis_dict: dict) -> None:
    """
    Print a rich terminal report for an analyze_card() result and append
    the data as a new row to data/prices/results.csv.

    Args:
        analysis_dict: The dict returned by analyze_card().
    """

    # Pull every field up front with safe defaults so the display code below
    # never has to worry about missing keys
    card_name       = analysis_dict.get("card_name",       "Unknown Card")
    num_sales       = analysis_dict.get("num_sales",       0)
    average_price   = analysis_dict.get("average_price")
    median_price    = analysis_dict.get("median_price")
    lowest_price    = analysis_dict.get("lowest_price")
    highest_price   = analysis_dict.get("highest_price")
    trend           = analysis_dict.get("trend")
    trend_pct       = analysis_dict.get("trend_pct_change")
    volatility      = analysis_dict.get("volatility")
    volatility_std  = analysis_dict.get("volatility_std")
    rarity_baseline = analysis_dict.get("rarity_baseline")
    composite_score = analysis_dict.get("composite_score")
    recommendation  = analysis_dict.get("recommendation",  "Insufficient Data")

    # --- Build display strings ---

    # Trend: show direction label and percentage change together
    if trend and trend_pct is not None:
        sign = "+" if trend_pct >= 0 else ""
        trend_str = f"{trend.capitalize()} ({sign}{trend_pct:.1f}%)"
    else:
        trend_str = "N/A"

    # Volatility: pair the label with the raw standard deviation for context
    if volatility and volatility_std is not None:
        volatility_str = f"{volatility.capitalize()}  (σ = ${volatility_std:.2f})"
    else:
        volatility_str = "N/A"

    # Rarity baseline is optional — only shown when card_details was provided
    rarity_str = rarity_baseline.replace("_", " ").title() if rarity_baseline else "N/A (no rarity data)"

    # Composite bar
    bar_str = _composite_bar(composite_score)

    # Recommendation emoji + label
    emoji, rec_label = RECOMMENDATION_STYLE.get(recommendation, ("⬛", recommendation.upper()))

    # --- Print the report ---
    width = 50
    print()
    print("=" * width)
    print(f"  {card_name}")
    print("=" * width)
    print(f"  Sales analysed : {num_sales}")
    print(f"  Average price  : {_fmt_price(average_price)}")
    print(f"  Median price   : {_fmt_price(median_price)}")
    print(f"  Lowest / High  : {_fmt_price(lowest_price)} / {_fmt_price(highest_price)}")
    print("-" * width)
    print(f"  Trend          : {trend_str}")
    print(f"  Volatility     : {volatility_str}")
    print(f"  Rarity check   : {rarity_str}")
    print("-" * width)

    # Composite score bar — visually shows where the card sits on the scale
    print(f"  Score  (-100 ← fair → +100)")
    print(f"  {bar_str}")
    print("-" * width)

    # Recommendation in large, emoji-prefixed text so it reads at a glance
    print(f"  {emoji}  {rec_label}")
    print("=" * width)
    print()

    # --- CSV export ---
    csv_path = os.path.abspath(CSV_PATH)

    # Check existence before opening so we know whether to write the header.
    # Must be done before open() because opening in 'a' mode creates the file.
    file_exists = os.path.isfile(csv_path)

    # Append mode: existing rows are never overwritten
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)

        # Write the header only the very first time the file is created
        if not file_exists:
            writer.writeheader()

        # Stamp each row with UTC time so results from different runs are
        # easy to sort or filter in a spreadsheet
        row = {
            "timestamp":        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "card_name":        card_name,
            "num_sales":        num_sales,
            "average_price":    average_price,
            "median_price":     median_price,
            "lowest_price":     lowest_price,
            "highest_price":    highest_price,
            "trend":            trend,
            "trend_pct_change": trend_pct,
            "volatility":       volatility,
            "volatility_std":   volatility_std,
            "rarity_baseline":  rarity_baseline,
            "composite_score":  composite_score,
            "recommendation":   recommendation,
        }
        writer.writerow(row)

    print(f"  Saved → {csv_path}")
    print()


if __name__ == "__main__":
    # Smoke-test: one result for each recommendation tier
    samples = [
        {
            "card_name": "Charizard Base Set",   "num_sales": 20,
            "average_price": 320.00, "median_price": 315.00,
            "lowest_price": 280.00,  "highest_price": 380.00,
            "trend": "falling",      "trend_pct_change": -18.5,
            "volatility": "stable",  "volatility_std": 24.10,
            "rarity_baseline": "within range",
            "composite_score": 67.5, "recommendation": "Strong Buy",
        },
        {
            "card_name": "Blastoise Base Set",   "num_sales": 12,
            "average_price": 85.00,  "median_price": 82.00,
            "lowest_price": 65.00,   "highest_price": 105.00,
            "trend": "stable",       "trend_pct_change": 1.2,
            "volatility": "moderate","volatility_std": 12.80,
            "rarity_baseline": "within range",
            "composite_score": 10.0, "recommendation": "Fair Value",
        },
        {
            "card_name": "Pikachu Illustrator",  "num_sales": 6,
            "average_price": 9800.00,"median_price": 9500.00,
            "lowest_price": 8000.00, "highest_price": 12000.00,
            "trend": "rising",       "trend_pct_change": 22.0,
            "volatility": "volatile","volatility_std": 1450.00,
            "rarity_baseline": "above range",
            "composite_score": -72.0,"recommendation": "Strong Sell",
        },
        {
            "card_name": "Mewtwo Base Set",      "num_sales": 0,
            "average_price": None,   "median_price": None,
            "lowest_price": None,    "highest_price": None,
            "trend": None,           "trend_pct_change": None,
            "volatility": None,      "volatility_std": None,
            "rarity_baseline": None,
            "composite_score": None, "recommendation": "Insufficient Data",
        },
    ]
    for s in samples:
        print_report(s)

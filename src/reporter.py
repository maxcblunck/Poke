import csv
import os
from datetime import datetime

# Path to the CSV file where results are accumulated across runs
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "prices", "results.csv")

# Column order used for both the header row and each data row
CSV_COLUMNS = [
    "timestamp",
    "card_name",
    "num_sales",
    "average_price",
    "median_price",
    "lowest_price",
    "highest_price",
    "value_signal",
]


def print_report(analysis_dict: dict) -> None:
    """
    Print a human-readable summary of an analyze_card() result and append
    it as a new row to data/prices/results.csv.

    Args:
        analysis_dict: The dict returned by analyze_card().
    """

    # --- Terminal output ---
    # Helper so every price field is formatted consistently or shows N/A
    def fmt(value) -> str:
        return f"${value:.2f}" if value is not None else "N/A"

    print()
    print("=" * 44)
    print(f"  {analysis_dict.get('card_name', 'Unknown Card')}")
    print("=" * 44)
    print(f"  Sales found  : {analysis_dict.get('num_sales', 0)}")
    print(f"  Average price: {fmt(analysis_dict.get('average_price'))}")
    print(f"  Median price : {fmt(analysis_dict.get('median_price'))}")
    print(f"  Lowest price : {fmt(analysis_dict.get('lowest_price'))}")
    print(f"  Highest price: {fmt(analysis_dict.get('highest_price'))}")
    # Use `or 'N/A'` so that a None value_signal never reaches .upper(),
    # which would raise an AttributeError
    signal = analysis_dict.get("value_signal") or "N/A"
    print(f"  Value signal : {signal.upper()}")
    print("=" * 44)
    print()

    # --- CSV export ---
    csv_path = os.path.abspath(CSV_PATH)

    # Check whether the file already exists before opening it so we know
    # whether to write the header row (we only want the header once)
    file_exists = os.path.isfile(csv_path)

    # Open in append mode so previous results are never overwritten
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)

        # Write the header only when creating the file for the first time
        if not file_exists:
            writer.writeheader()

        # Build the row, stamping the current UTC time so each run is traceable
        row = {
            "timestamp":     datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "card_name":     analysis_dict.get("card_name"),
            "num_sales":     analysis_dict.get("num_sales"),
            "average_price": analysis_dict.get("average_price"),
            "median_price":  analysis_dict.get("median_price"),
            "lowest_price":  analysis_dict.get("lowest_price"),
            "highest_price": analysis_dict.get("highest_price"),
            "value_signal":  analysis_dict.get("value_signal"),
        }
        writer.writerow(row)

    print(f"  Results appended to: {csv_path}")
    print()


if __name__ == "__main__":
    # Smoke-test with a realistic analysis_dict (as if returned by analyze_card)
    sample = {
        "card_name":     "Charizard VMAX",
        "num_sales":     7,
        "average_price": 36.86,
        "median_price":  38.0,
        "lowest_price":  18.0,
        "highest_price": 60.0,
        "value_signal":  "undervalued",
    }
    print_report(sample)

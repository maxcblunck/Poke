"""
Fetches 12-month Google Trends search interest for Pokemon, prioritized by
how many cards each species has in the database (more cards = more relevant
to the project). Stops early once a full batch of 4 averages below
STOP_THRESHOLD — at that point the remaining species are all near-zero and
not worth fetching.

Results are saved incrementally to data/popularity.csv so no progress is
lost if Google rate-limits us mid-run.
"""

import json
import os
import re
import time
import csv

import pandas as pd
from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError

# --- Config ---
DATA_DIR = "data/cards/en"
OUT_CSV = "data/popularity.csv"
ANCHOR = "Pikachu"
TIMEFRAME = "today 12-m"
BATCH_SIZE = 4       # anchor fills the 5th slot; Google Trends max is 5
STOP_THRESHOLD = 3.0 # stop when a full batch averages below this score
SLEEP_BETWEEN = 6    # seconds between requests


# Suffixes that don't represent distinct species
_SUFFIX_RE = re.compile(
    r"\s+(V|VMAX|VSTAR|VUNION|GX|EX|TAG|TEAM|"
    r"Prime|LV\.X|Level-Up|LEGEND|BREAK|"
    r"delta|Star|[♀♂])\b.*$",
    re.IGNORECASE,
)


def _base_name(card_name: str) -> str:
    """Strip card-variant suffixes to get the base species name."""
    # Handle TAG TEAM names like "Pikachu & Zekrom-GX" -> keep first species
    if " & " in card_name:
        card_name = card_name.split(" & ")[0].strip()
    return _SUFFIX_RE.sub("", card_name).strip()


def build_ranked_list() -> list[tuple[str, int]]:
    """Return [(species_name, card_count), ...] sorted by card_count desc."""
    counts: dict[str, int] = {}
    for fname in os.listdir(DATA_DIR):
        with open(f"{DATA_DIR}/{fname}", encoding="utf-8") as f:
            for card in json.load(f):
                if card.get("supertype") in ("Pokémon", "Pokemon"):
                    base = _base_name(card["name"])
                    counts[base] = counts.get(base, 0) + 1
    return sorted(counts.items(), key=lambda x: x[1], reverse=True)


def _fetch_with_retry(
    pytrends: TrendReq, keywords: list[str], max_retries: int = 4
) -> pd.DataFrame:
    delay = 15
    for attempt in range(max_retries):
        try:
            pytrends.build_payload(keywords, timeframe=TIMEFRAME)
            return pytrends.interest_over_time()
        except TooManyRequestsError:
            if attempt == max_retries - 1:
                raise
            print(f"    Rate limited — waiting {delay}s (retry {attempt + 2}/{max_retries})...")
            time.sleep(delay)
            delay *= 2
    return pd.DataFrame()


def run():
    ranked = build_ranked_list()
    total = len(ranked)
    print(f"Found {total} distinct Pokemon species in the card database.")
    print(f"Fetching in card-count order, stopping when batch avg < {STOP_THRESHOLD}.\n")

    # Load already-fetched results so we can resume a partial run
    done: dict[str, float] = {}
    if os.path.exists(OUT_CSV):
        with open(OUT_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done[row["name"]] = float(row["score"])
        print(f"Resuming: {len(done)} species already in {OUT_CSV}\n")

    # Open CSV for appending
    csv_exists = os.path.exists(OUT_CSV)
    csv_file = open(OUT_CSV, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(csv_file, fieldnames=["name", "card_count", "score"])
    if not csv_exists:
        writer.writeheader()

    pytrends = TrendReq(hl="en-US", tz=0)

    # Anchor baseline
    if ANCHOR not in done:
        print(f"Fetching anchor baseline: {ANCHOR}")
        df = _fetch_with_retry(pytrends, [ANCHOR])
        anchor_mean = float(df[ANCHOR].mean()) if not df.empty else 1.0
        anchor_card_count = next((c for n, c in ranked if n == ANCHOR), 0)
        done[ANCHOR] = anchor_mean
        writer.writerow({"name": ANCHOR, "card_count": anchor_card_count, "score": anchor_mean})
        csv_file.flush()
        time.sleep(SLEEP_BETWEEN)
    else:
        anchor_mean = done[ANCHOR]
        print(f"Anchor {ANCHOR} already fetched: {anchor_mean:.1f}")

    # Work through ranked list in batches of BATCH_SIZE
    pending = [(n, c) for n, c in ranked if n != ANCHOR and n not in done]
    fetched = 0

    for i in range(0, len(pending), BATCH_SIZE):
        batch_items = pending[i : i + BATCH_SIZE]
        batch_names = [n for n, _ in batch_items] + [ANCHOR]

        species_labels = [n for n, _ in batch_items]
        print(f"Batch {i // BATCH_SIZE + 1}: {species_labels}")

        df = _fetch_with_retry(pytrends, batch_names)

        if df.empty:
            for name, count in batch_items:
                done[name] = 0.0
                writer.writerow({"name": name, "card_count": count, "score": 0.0})
            csv_file.flush()
            time.sleep(SLEEP_BETWEEN)
            continue

        batch_anchor = float(df[ANCHOR].mean())
        scale = (anchor_mean / batch_anchor) if batch_anchor else 1.0

        batch_scores = []
        for name, count in batch_items:
            score = float(df[name].mean()) * scale if name in df.columns else 0.0
            done[name] = score
            batch_scores.append(score)
            writer.writerow({"name": name, "card_count": count, "score": score})

        csv_file.flush()
        fetched += len(batch_items)

        avg = sum(batch_scores) / len(batch_scores) if batch_scores else 0
        print(f"  scores: {[f'{s:.1f}' for s in batch_scores]}  avg={avg:.1f}")

        if avg < STOP_THRESHOLD:
            print(f"\nBatch avg {avg:.1f} < threshold {STOP_THRESHOLD} — stopping early.")
            print(f"Remaining {len(pending) - fetched} species skipped (near-zero interest).")
            break

        time.sleep(SLEEP_BETWEEN)

    csv_file.close()

    # Print final rankings
    results = sorted(done.items(), key=lambda x: x[1], reverse=True)
    print(f"\n{'Rank':<6}{'Pokemon':<18}{'Score':>8}  Bar")
    print("-" * 50)
    for rank, (name, score) in enumerate(results, 1):
        bar = "#" * int(score / 2)
        print(f"{rank:<6}{name:<18}{score:>8.1f}  {bar}")

    print(f"\nFull results saved to {OUT_CSV}")


if __name__ == "__main__":
    run()

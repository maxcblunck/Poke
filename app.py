import sys
import os
import time
import streamlit as st

# Make src/ importable without installing it as a package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from card_db import CardDatabase
from scraper import get_card_prices
from analyzer import analyze_card

# ---------------------------------------------------------------------------
# Page config — must be the first Streamlit call in the script
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Pokemon Card Valuation Tool",
    page_icon="🃏",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Load the card database once and cache it for the lifetime of the session.
# st.cache_resource keeps the object alive across reruns without re-reading
# all 173 JSON files every time the user interacts with the page.
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Loading card database…")
def load_database() -> CardDatabase:
    return CardDatabase()


db = load_database()

# ---------------------------------------------------------------------------
# Sidebar — scan filters
# These widgets render in the sidebar panel and their values are read on every
# rerun, so no session state is needed; they're just local variables here.
# ---------------------------------------------------------------------------

# Available rarity options for the scan multiselect.
# These are the four tiers users are most likely to care about.
SCAN_RARITY_OPTIONS = ["Rare Holo", "Rare Ultra", "Rare Secret", "Rare Rainbow"]

@st.cache_data
def get_rare_set_names() -> list[str]:
    """
    Return a sorted list of unique set names that contain at least one rare card.
    Cached so the 6 000+ card list is only iterated once per session.
    """
    return sorted({c["set_name"] for c in db.get_rare_cards()})

with st.sidebar:
    st.header("⚙️ Scan Filters")
    st.markdown("Applied to the **Bulk Rare Card Scan** below.")

    # Rarity filter — default to all four tiers selected ("Rare Holo and above")
    selected_rarities = st.multiselect(
        "Rarity",
        options=SCAN_RARITY_OPTIONS,
        default=SCAN_RARITY_OPTIONS,
        help="Only cards matching one of these rarities will be scanned.",
    )

    # Set filter — default to empty which the scan treats as "all sets"
    all_set_names = get_rare_set_names()
    selected_sets = st.multiselect(
        "Sets  (leave empty to include all)",
        options=all_set_names,
        default=[],
        help="Restrict the scan to specific sets. Leave blank to scan every set.",
    )

    # How many cards to analyse in one scan run
    max_cards = st.number_input(
        "Max cards to scan",
        min_value=10,
        max_value=500,
        value=50,
        step=10,
        help="The candidate pool is filtered first, then capped at this number.",
    )

    # Sort direction for the results table
    sort_order = st.radio(
        "Sort results by composite score",
        options=["Highest first", "Lowest first"],
        index=0,
        help="Highest first surfaces the most undervalued cards at the top; "
             "Lowest first surfaces the most overvalued.",
    )

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def fmt_price(value) -> str:
    """Format a float as a dollar string, or return 'N/A'."""
    return f"${value:,.2f}" if value is not None else "N/A"


def recommendation_color(rec: str) -> str:
    """Map a recommendation label to a CSS hex colour."""
    colors = {
        "Strong Buy":  "#22c55e",   # green-500
        "Buy":         "#86efac",   # green-300
        "Fair Value":  "#9ca3af",   # grey-400
        "Sell":        "#fb923c",   # orange-400
        "Strong Sell": "#ef4444",   # red-500
    }
    return colors.get(rec, "#9ca3af")


def recommendation_emoji(rec: str) -> str:
    emojis = {
        "Strong Buy":  "🟢",
        "Buy":         "🟡",
        "Fair Value":  "⚪",
        "Sell":        "🟠",
        "Strong Sell": "🔴",
    }
    return emojis.get(rec, "⬛")


def composite_bar(score) -> str:
    """Render a 20-cell block bar showing position on the -100 → +100 scale."""
    if score is None:
        return "N/A"
    filled = round((score + 100) / 200 * 20)
    filled = max(0, min(20, filled))
    sign = "+" if score >= 0 else ""
    return "█" * filled + "░" * (20 - filled) + f"  {sign}{score}"


def fetch_and_analyse(card_label: str, card_details: dict | None = None) -> dict:
    """Fetch prices for one card and run the full analysis."""
    prices = get_card_prices(card_label)
    return analyze_card(card_label, prices, card_details)


def display_valuation(result: dict):
    """
    Render the full valuation report for one card using Streamlit components.
    Key numbers use st.metric(); recommendation uses coloured HTML.
    """
    rec   = result.get("recommendation", "Insufficient Data")
    color = recommendation_color(rec)
    emoji = recommendation_emoji(rec)

    # --- Recommendation banner ---
    st.markdown(
        f"<h2 style='color:{color};'>{emoji} {rec}</h2>",
        unsafe_allow_html=True,
    )

    # --- Key metrics row ---
    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Avg Price",    fmt_price(result.get("average_price")))
    col2.metric("Median Price", fmt_price(result.get("median_price")))
    col3.metric("Lowest",       fmt_price(result.get("lowest_price")))
    col4.metric("Highest",      fmt_price(result.get("highest_price")))
    col5.metric("Sales Found",  result.get("num_sales", 0))

    st.divider()

    # --- Score bar + signal details ---
    col_bar, col_signals = st.columns([2, 3])

    with col_bar:
        st.subheader("Composite Score")
        # Display the score as a large number metric with the bar below it
        score = result.get("composite_score")
        st.metric(
            label="Score  (−100 undervalued → +100 overvalued)",
            value=score if score is not None else "N/A",
        )
        # Monospace block bar for visual reference
        st.code(composite_bar(score), language=None)

    with col_signals:
        st.subheader("Signals")

        # Trend — show direction and percentage change
        trend     = result.get("trend")
        trend_pct = result.get("trend_pct_change")
        if trend and trend_pct is not None:
            sign = "+" if trend_pct >= 0 else ""
            trend_str = f"{trend.capitalize()}  ({sign}{trend_pct:.1f}%)"
        else:
            trend_str = "N/A"
        st.markdown(f"**📈 Price Trend:** {trend_str}")

        # Volatility — label plus standard deviation
        vol     = result.get("volatility")
        vol_std = result.get("volatility_std")
        if vol and vol_std is not None:
            vol_str = f"{vol.capitalize()}  (σ = {fmt_price(vol_std)})"
        else:
            vol_str = "N/A"
        st.markdown(f"**📊 Volatility:** {vol_str}")

        # Rarity baseline — only present when card_details was passed in
        baseline = result.get("rarity_baseline") or "N/A (no rarity data)"
        st.markdown(f"**💎 Rarity Baseline:** {baseline.replace('_', ' ').title()}")


# ---------------------------------------------------------------------------
# App layout
# ---------------------------------------------------------------------------

st.title("🃏 Pokemon Card Valuation Tool")
st.markdown(
    "Search any Pokemon card to see a full market valuation — "
    "or scan the rare card pool to surface **undervalued** and **overvalued** picks."
)

st.divider()

# ============================================================
# Session state initialisation
# Keys are set only on the very first run; subsequent reruns
# leave existing values untouched so results persist across
# widget interactions.
# ============================================================

# List of card dicts returned by the last Search press
if "search_results" not in st.session_state:
    st.session_state.search_results = []

# The card dict the user has selected in the dropdown
if "selected_card" not in st.session_state:
    st.session_state.selected_card = None

# The full analysis dict; cleared only when Search runs again
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

# ============================================================
# Section 1: Search a specific card
# ============================================================
st.header("🔍 Search a Card")

search_query = st.text_input("Card name", placeholder="e.g. Charizard, Pikachu, Lugia…")
search_btn   = st.button("Search", type="primary")

if search_btn:
    if not search_query.strip():
        st.warning("Please enter a card name to search.")
    else:
        # Run the search and save the full result list to session state so
        # the dropdown stays visible on every subsequent rerun — not just the
        # one triggered by clicking Search.
        matches = db.search_card(search_query.strip())

        if not matches:
            st.warning(f"No cards found matching '{search_query}'.")
            # Clear stale results from a previous search
            st.session_state.search_results = []
            st.session_state.selected_card  = None
            st.session_state.analysis_result = None
        else:
            # Persist the results list; reset selected card and analysis so
            # the old report doesn't linger after a brand-new search.
            st.session_state.search_results  = matches
            st.session_state.selected_card   = matches[0]
            st.session_state.analysis_result = None

# Render the dropdown whenever we have search results in session state —
# this keeps it visible even after the user clicks "Analyse" or changes
# any other widget (every widget interaction triggers a full rerun).
if st.session_state.search_results:
    matches = st.session_state.search_results

    # Build human-readable option strings for the selectbox
    options = [
        f"{c['name']} — {c['set_name']} #{c['number']} ({c['rarity'] or 'Unknown'})"
        for c in matches
    ]

    # Determine which index was previously selected so the dropdown doesn't
    # jump back to position 0 on every rerun.
    current_card = st.session_state.selected_card
    try:
        current_idx = matches.index(current_card) if current_card in matches else 0
    except ValueError:
        current_idx = 0

    chosen_idx = st.selectbox(
        f"{len(matches)} match(es) found — select one to analyse:",
        range(len(options)),
        format_func=lambda i: options[i],
        index=current_idx,
        # key is omitted intentionally: we manage state ourselves below so
        # that changing the dropdown does NOT wipe the existing analysis_result.
    )

    # Write the newly selected card back to session state so it survives
    # the next rerun, but do NOT clear analysis_result here — the report
    # should only disappear when the user explicitly clicks Analyse again.
    st.session_state.selected_card = matches[chosen_idx]

    analyse_btn = st.button("Analyse Card", type="secondary")

    if analyse_btn:
        chosen_card  = st.session_state.selected_card
        card_label   = f"{chosen_card['name']} ({chosen_card['set_name']})"

        # Load full card details so analyze_card() can run the rarity check
        card_details = db.get_card_details(
            chosen_card["name"], chosen_card["set_name"]
        )

        with st.spinner(f"Fetching prices for {card_label}…"):
            result = fetch_and_analyse(card_label, card_details)

        # Store the result in session state so it persists across reruns;
        # display_valuation() reads from here, not from a local variable.
        st.session_state.analysis_result = result

# Render the analysis whenever a result exists in session state.
# This block is intentionally outside every button/widget conditional so
# the report stays on screen regardless of what the user does next.
if st.session_state.analysis_result:
    result = st.session_state.analysis_result
    st.subheader(result.get("card_name", ""))
    display_valuation(result)

st.divider()

# ============================================================
# Section 2 & 3: Bulk scans (undervalued / overvalued)
# ============================================================
st.header("📋 Bulk Rare Card Scan")
st.markdown(
    "Applies the sidebar filters, then analyses up to **max cards** and surfaces "
    "undervalued or overvalued picks. Adjust the filters in the sidebar before scanning."
)

col_under, col_over = st.columns(2)
scan_undervalued = col_under.button("🟢 Show Undervalued Cards", use_container_width=True)
scan_overvalued  = col_over.button("🔴 Show Overvalued Cards",  use_container_width=True)


def build_candidate_pool(
    rarities: list[str],
    sets: list[str],
    limit: int,
) -> list[dict]:
    """
    Build the list of cards that will actually be scanned.

    Steps:
      1. Start from db.get_rare_cards() (all rare-holo+ cards).
      2. Keep only cards whose rarity is in the selected rarities list.
         If the rarity multiselect is empty, skip no cards (treat as "all").
      3. Keep only cards whose set_name is in the selected sets list.
         If the set multiselect is empty, skip no cards (treat as "all sets").
      4. Cap the list at `limit` so the scan doesn't run for too long.
    """
    candidates = db.get_rare_cards()

    # Rarity filter — skip if nothing selected (safety valve, UI defaults to all)
    if rarities:
        candidates = [c for c in candidates if c.get("rarity") in rarities]

    # Set filter — empty selection means "include all sets"
    if sets:
        candidates = [c for c in candidates if c.get("set_name") in sets]

    # Cap to the user-specified maximum
    return candidates[:limit]


def run_bulk_scan(
    target_signal: str,
    rarities: list[str],
    sets: list[str],
    limit: int,
    sort_highest_first: bool,
):
    """
    Fetch prices and analyse each card in the filtered candidate pool, then
    display those whose recommendation matches target_signal.

    Args:
        target_signal:      'Buy' or 'Sell' (recommendation label to filter on).
        rarities:           Rarity tiers to include (from sidebar multiselect).
        sets:               Set names to include; empty means all sets.
        limit:              Maximum number of cards to analyse.
        sort_highest_first: True → sort by composite score descending.
    """
    import pandas as pd

    # Step 1: Apply sidebar filters to get the candidate pool
    candidates = build_candidate_pool(rarities, sets, limit)

    if not candidates:
        st.warning("No cards match the current sidebar filters. Try broadening your selection.")
        return

    results = []

    # Step 2: Progress bar — shows card-by-card progress through the pool
    progress = st.progress(0, text="Starting scan…")
    total    = len(candidates)

    for i, card in enumerate(candidates):
        card_label   = f"{card['name']} ({card['set_name']})"
        card_details = db.get_card_details(card["name"], card["set_name"])

        # Update the progress bar with the current card name and position
        progress.progress(
            (i + 1) / total,
            text=f"Analysing {card_label}  ({i + 1} / {total})",
        )

        result = fetch_and_analyse(card_label, card_details)
        results.append(result)

        # Brief pause between requests to avoid hammering the data source
        if i < total - 1:
            time.sleep(1)

    # Clear the progress bar now that the scan is complete
    progress.empty()

    # Step 3: Keep only cards whose recommendation matches the requested signal.
    # 'Buy' catches both "Buy" and "Strong Buy"; 'Sell' catches both sell tiers.
    flagged = [
        r for r in results
        if (r.get("recommendation") or "").lower().startswith(target_signal.lower())
    ]

    # Step 4: Show totals — scanned count and flagged count
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Cards scanned",  total)
    col_b.metric("Cards flagged",  len(flagged))
    col_c.metric("Hit rate", f"{len(flagged) / total * 100:.0f}%" if total else "—")

    if not flagged:
        st.info(f"No {target_signal} signals found. Try adjusting the sidebar filters.")
        return

    # Step 5: Sort by composite score using the sidebar sort preference
    flagged.sort(
        key=lambda r: r.get("composite_score") or 0,
        reverse=sort_highest_first,
    )

    # Step 6: Summary table for quick comparison across all flagged cards
    rows = [
        {
            "Card":            r["card_name"],
            "Avg Price":       fmt_price(r.get("average_price")),
            "Composite Score": r.get("composite_score"),
            "Trend":           r.get("trend", "N/A"),
            "Volatility":      r.get("volatility", "N/A"),
            "Rarity Baseline": r.get("rarity_baseline") or "N/A",
            "Recommendation":  r.get("recommendation"),
        }
        for r in flagged
    ]

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Step 7: Full valuation panel for each flagged card in a collapsible expander
    for r in flagged:
        with st.expander(
            f"{recommendation_emoji(r.get('recommendation', ''))}  {r['card_name']}"
        ):
            display_valuation(r)


if scan_undervalued:
    st.subheader("🟢 Undervalued Cards")
    run_bulk_scan(
        target_signal="Buy",
        rarities=selected_rarities,
        sets=selected_sets,
        limit=max_cards,
        sort_highest_first=(sort_order == "Highest first"),
    )

if scan_overvalued:
    st.subheader("🔴 Overvalued Cards")
    run_bulk_scan(
        target_signal="Sell",
        rarities=selected_rarities,
        sets=selected_sets,
        limit=max_cards,
        sort_highest_first=(sort_order == "Lowest first"),
    )

import re
import streamlit as st
import plotly.graph_objects as go
from streamlit_extras.colored_header import colored_header

from src.ui_helpers import (
    load_database, fmt_price, rec_badge,
    type_badges, signal_chips, display_rarity,
)
from src.scraper import get_card_prices
from src.analyzer import analyze_card

db = load_database()

# ── Session state defaults ───────────────────────────────────────────────────
for key, default in [
    ("search_results", []), ("selected_card", None), ("analysis_result", None),
    ("nm_market_price", None), ("_pw_prices", {}), ("_pw_variants", []),
    ("_variant_idx", 0), ("_analyzed_variant_idx", 0), ("_raw_prices", []),
    ("_card_label", ""), ("_card_details_cache", None), ("data_source", "simulated"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

colored_header(
    label="Search a Card",
    description="Look up any Pokémon card by name to get a live valuation",
    color_name="red-70",
)

# ── Search input ─────────────────────────────────────────────────────────────
search_query = st.text_input("", placeholder="Charizard, Pikachu, Lugia…", label_visibility="collapsed")
search_btn   = st.button("SEARCH", type="primary")

if search_btn:
    q = search_query.strip()
    if not q:
        st.warning("Enter a card name.")
    else:
        matches = db.search_card(q)
        if not matches:
            st.warning(f"No cards found for '{q}'.")
            st.session_state.search_results  = []
            st.session_state.selected_card   = None
            st.session_state.analysis_result = None
        else:
            st.session_state.search_results  = matches
            st.session_state.selected_card   = matches[0]
            st.session_state.analysis_result = None

if st.session_state.search_results:
    matches = st.session_state.search_results
    options = [
        f"{c['name']} — {c['set_name']} #{c['number']} ({c['rarity'] or 'Unknown'})"
        for c in matches
    ]
    current = st.session_state.selected_card
    try:    current_idx = matches.index(current) if current in matches else 0
    except: current_idx = 0

    chosen_idx = st.selectbox(
        f"{len(matches)} match(es) — pick one:",
        range(len(options)),
        format_func=lambda i: options[i],
        index=current_idx,
    )
    st.session_state.selected_card = matches[chosen_idx]

    if st.button("ANALYZE CARD"):
        card    = st.session_state.selected_card
        label   = f"{card['name']} ({card['set_name']})"
        details = db.get_card_details(card["name"], card["set_name"], card.get("number"))
        with st.spinner("Crunching numbers…"):
            prices = get_card_prices(label, details.get("id") if details else None)
            first  = prices[0] if prices else {}
            is_pw  = first.get("source") == "pokewallet"
            st.session_state.nm_market_price = first.get("market_price") if is_pw else None
            st.session_state._pw_prices = {
                "market": first.get("market_price"),
                "mid":    first.get("mid_price"),
                "low":    first.get("low_price"),
                "high":   first.get("high_price"),
            } if is_pw else {}
            st.session_state._pw_variants           = first.get("all_variants", []) if is_pw else []
            st.session_state._variant_idx           = 0
            st.session_state._analyzed_variant_idx  = 0
            st.session_state._raw_prices            = prices
            st.session_state._card_label            = label
            st.session_state._card_details_cache    = details
            st.session_state.data_source            = first.get("data_source", "simulated")
            variant_name = first.get("sub_type_name", "") if is_pw else ""
            st.session_state.analysis_result = analyze_card(label, prices, details, variant=variant_name)

# ── Analysis display ─────────────────────────────────────────────────────────
if st.session_state.analysis_result:
    r       = st.session_state.analysis_result
    card    = st.session_state.selected_card
    details = db.get_card_details(card["name"], card["set_name"], card.get("number")) if card else None

    st.markdown("---")

    # ── Variant selector ─────────────────────────────────────────────────────
    variants = st.session_state.get("_pw_variants", [])
    if len(variants) > 1:
        variant_labels = [v.get("sub_type_name", "Standard") for v in variants]
        sel_idx = st.selectbox(
            "Printing variant",
            range(len(variant_labels)),
            format_func=lambda i: variant_labels[i],
            index=st.session_state.get("_variant_idx", 0),
            key="_variant_selector",
        )
        if sel_idx != st.session_state.get("_analyzed_variant_idx", 0):
            sel_variant = variants[sel_idx]
            vname = sel_variant.get("sub_type_name", "")
            mp = sel_variant.get("market_price") or 0
            lp = sel_variant.get("low_price")    or mp
            hp = sel_variant.get("high_price")   or mp
            v_prices = [{"price": f"${p:.2f}"} for p in [mp, lp, hp, mp, lp]]
            _lbl = st.session_state.get("_card_label", r.get("card_name", ""))
            _det = st.session_state.get("_card_details_cache")
            st.session_state.analysis_result       = analyze_card(_lbl, v_prices, _det, variant=vname)
            st.session_state._analyzed_variant_idx = sel_idx
        st.session_state._variant_idx = sel_idx
    else:
        sel_idx = 0

    active = variants[sel_idx] if variants else {}
    pw = {
        "market": active.get("market_price"),
        "mid":    active.get("mid_price"),
        "low":    active.get("low_price"),
        "high":   active.get("high_price"),
    } if active else (st.session_state.get("_pw_prices") or {})

    # ── Two-column layout ────────────────────────────────────────────────────
    img_col, info_col = st.columns([1, 2], gap="large")

    with img_col:
        if details and details.get("images"):
            st.image(
                details["images"].get("large") or details["images"].get("small"),
                use_container_width=True,
            )
        else:
            st.markdown(
                "<div style='background:#1e2035;border-radius:12px;height:340px;"
                "display:flex;align-items:center;justify-content:center;font-size:3rem;'>🃏</div>",
                unsafe_allow_html=True,
            )

        nm = pw.get("market") or r.get("average_price")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="psa-box" style="border-color:#22c55e;">
          <div class="psa-grade" style="color:#22c55e;">NM MARKET PRICE</div>
          <div class="psa-price">{fmt_price(nm)}</div>
        </div>""", unsafe_allow_html=True)

    with info_col:
        types_html = type_badges(details.get("types", []) if details else [])
        rarity     = (details or {}).get("rarity", "")
        set_name   = card.get("set_name", "") if card else ""
        st.markdown(f"""
        <h2 style='margin-bottom:0.3rem;'>{r['card_name']}</h2>
        <p style='color:#9ca3af;font-size:0.85rem;margin-bottom:0.6rem;'>{set_name} · {display_rarity(rarity)}</p>
        {types_html}
        """, unsafe_allow_html=True)

        # Data source badge
        ds = st.session_state.get("data_source", "simulated")
        if ds == "live":
            ds_badge = "<span style='background:#14532d;color:#86efac;border:1px solid #22c55e;border-radius:4px;font-family:Inter,sans-serif;font-size:0.72rem;padding:2px 10px;'>&#9679; Live TCGPlayer Data</span>"
        else:
            ds_badge = "<span style='background:#1f2937;color:#9ca3af;border:1px solid #374151;border-radius:4px;font-family:Inter,sans-serif;font-size:0.72rem;padding:2px 10px;'>&#9679; Simulated Estimate</span>"
        st.markdown(ds_badge, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown(rec_badge(r.get("recommendation", "N/A")), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # ── Composite score gauge ────────────────────────────────────────────
        score = r.get("composite_score")
        if score is not None:
            if score <= -25:
                bar_color, step_color = "#22c55e", "#14532d"
            elif score < 25:
                bar_color, step_color = "#eab308", "#854d0e"
            else:
                bar_color, step_color = "#ef4444", "#7f1d1d"

            gauge_fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=score,
                number={"font": {"color": "#FFDE00", "size": 28}, "suffix": " / 100"},
                gauge={
                    "axis": {
                        "range": [-100, 100],
                        "tickcolor": "#6b7280",
                        "tickfont": {"color": "#6b7280", "size": 10},
                    },
                    "bar": {"color": bar_color, "thickness": 0.25},
                    "bgcolor": "#1e2035",
                    "bordercolor": "#374151",
                    "borderwidth": 2,
                    "steps": [
                        {"range": [-100, -25], "color": "#0f2d1a"},
                        {"range": [-25,   25], "color": "#1c1917"},
                        {"range": [  25, 100], "color": "#2d0f0f"},
                    ],
                    "threshold": {
                        "line": {"color": "#FFDE00", "width": 2},
                        "thickness": 0.75,
                        "value": score,
                    },
                },
            ))
            gauge_fig.update_layout(
                paper_bgcolor="#0d0f1a",
                font={"color": "#e8e8e8", "family": "Inter"},
                height=180,
                margin=dict(l=20, r=20, t=20, b=10),
            )
            st.plotly_chart(gauge_fig, use_container_width=True)

        # ── Price metrics ────────────────────────────────────────────────────
        m1, m2, m3 = st.columns(3)
        m1.metric("Market Price", fmt_price(pw.get("market") or r.get("average_price")))
        m2.metric("Lowest Ask",   fmt_price(pw.get("low")    or r.get("lowest_price")))
        m3.metric("Highest Ask",  fmt_price(pw.get("high")   or r.get("highest_price")))

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f'<div class="signal-row">{signal_chips(r)}</div>', unsafe_allow_html=True)

        with st.expander("Full signal breakdown"):
            trend_str = r.get("trend", "N/A")
            if trend_str not in ("no data", None, ""):
                pct_val = r.get("trend_pct_change")
                sign    = "+" if (pct_val or 0) >= 0 else ""
                trend_str = f"{trend_str.title()} ({sign}{pct_val:.1f}%)" if pct_val is not None else trend_str.title()
            else:
                trend_str = "Not enough sales history"
            rows = {
                "Trend (last 10 sales)": trend_str,
                "Popularity":            f"{r.get('popularity_score','N/A')} / 100",
                "Scarcity (era+rarity)": f"{r.get('scarcity_score','N/A')} / 100",
                "Avg packs to pull":     f"~{r.get('pull_odds_packs','N/A')} packs",
                "Composite score":       r.get("composite_score"),
            }
            for k, v in rows.items():
                c_l, c_r = st.columns([1, 2])
                c_l.markdown(f"**{k}**")
                c_r.markdown(str(v))

    # ── Price history chart ──────────────────────────────────────────────────
    raw_prices = st.session_state.get("_raw_prices", [])
    parsed_prices = []
    for p in raw_prices:
        price_str = p.get("price", "")
        m = re.search(r"\d+\.?\d*", str(price_str).replace(",", ""))
        if m:
            parsed_prices.append(float(m.group()))

    if len(parsed_prices) >= 5:
        st.markdown("---")
        st.markdown("### Price History")

        # Reverse so oldest sale is on the left
        chart_prices = list(reversed(parsed_prices))

        price_fig = go.Figure()
        price_fig.add_trace(go.Scatter(
            y=chart_prices,
            mode="lines+markers",
            line={"color": "#FFDE00", "width": 2},
            marker={"color": "#CC0000", "size": 7, "line": {"color": "#FFDE00", "width": 1}},
            name="Sale Price",
            hovertemplate="$%{y:,.2f}<extra></extra>",
        ))

        avg_price = r.get("average_price")
        if avg_price:
            price_fig.add_hline(
                y=avg_price,
                line_dash="dot",
                line_color="#6b7280",
                annotation_text=f"Avg ${avg_price:,.2f}",
                annotation_font_color="#9ca3af",
                annotation_position="top right",
            )

        price_fig.update_layout(
            paper_bgcolor="#0d0f1a",
            plot_bgcolor="#161828",
            font={"color": "#e8e8e8", "family": "Inter"},
            height=260,
            margin=dict(l=10, r=10, t=20, b=40),
            xaxis={
                "title": "Sales (oldest → newest)",
                "gridcolor": "#2a2d45",
                "zerolinecolor": "#2a2d45",
                "tickfont": {"color": "#6b7280"},
            },
            yaxis={
                "tickprefix": "$",
                "gridcolor": "#2a2d45",
                "zerolinecolor": "#2a2d45",
                "tickfont": {"color": "#6b7280"},
            },
            showlegend=False,
        )
        st.plotly_chart(price_fig, use_container_width=True)

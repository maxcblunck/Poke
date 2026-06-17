# -*- coding: utf-8 -*-
import streamlit as st
import plotly.graph_objects as go
from streamlit_extras.colored_header import colored_header

from src.ui_helpers import load_database, fmt_price, rec_badge, type_badges, signal_chips, display_rarity
from src.scraper import get_card_prices
from src.analyzer import analyze_card

db = load_database()

for key, default in [
    ("cmp_a_results", []), ("cmp_a_card", None), ("cmp_a_analysis", None),
    ("cmp_a_prices", {}), ("cmp_a_raw", []), ("cmp_a_details", None),
    ("cmp_b_results", []), ("cmp_b_card", None), ("cmp_b_analysis", None),
    ("cmp_b_prices", {}), ("cmp_b_raw", []), ("cmp_b_details", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

colored_header(
    label="Compare Cards",
    description="Search two cards and compare valuations side by side",
    color_name="red-70",
)

col_a, col_b = st.columns(2, gap="large")


def render_search_col(prefix, col, label):
    with col:
        st.markdown(f"#### {label}")
        q = st.text_input(
            "", placeholder="Card name…",
            key=f"{prefix}_query", label_visibility="collapsed"
        )
        if st.button("SEARCH", key=f"{prefix}_search", type="primary"):
            matches = db.search_card(q.strip()) if q.strip() else []
            if matches:
                st.session_state[f"{prefix}_results"] = matches
                st.session_state[f"{prefix}_card"] = matches[0]
                st.session_state[f"{prefix}_analysis"] = None
            else:
                st.warning("No cards found.")
        results = st.session_state.get(f"{prefix}_results", [])
        if results:
            options = [
                f"{c['name']} — {c['set_name']} #{c['number']} ({c['rarity'] or 'Unknown'})"
                for c in results
            ]
            idx = st.selectbox(
                "", range(len(options)),
                format_func=lambda i: options[i],
                key=f"{prefix}_select",
                label_visibility="collapsed",
            )
            st.session_state[f"{prefix}_card"] = results[idx]


render_search_col("cmp_a", col_a, "Card A")
render_search_col("cmp_b", col_b, "Card B")

_, mid, _ = st.columns([1, 2, 1])
with mid:
    analyze_clicked = st.button("ANALYZE BOTH", type="primary", use_container_width=True)

if analyze_clicked:
    for prefix in ("cmp_a", "cmp_b"):
        card = st.session_state.get(f"{prefix}_card")
        if not card:
            st.warning(f"Search a card for {prefix.replace('cmp_', 'Card ').upper()} first.")
            continue
        label = f"{card['name']} ({card['set_name']})"
        details = db.get_card_details(card["name"], card["set_name"], card.get("number"))
        with st.spinner(f"Analyzing {card['name']}…"):
            prices = get_card_prices(label, details.get("id") if details else None)
            first = prices[0] if prices else {}
            is_pw = first.get("source") == "pokewallet"
            pw = {
                "market": first.get("market_price"),
                "low":    first.get("low_price"),
                "high":   first.get("high_price"),
            } if is_pw else {}
            variant = first.get("sub_type_name", "") if is_pw else ""
            st.session_state[f"{prefix}_analysis"] = analyze_card(label, prices, details, variant=variant)
            st.session_state[f"{prefix}_prices"]   = pw
            st.session_state[f"{prefix}_raw"]      = prices
            st.session_state[f"{prefix}_details"]  = details

ra = st.session_state.get("cmp_a_analysis")
rb = st.session_state.get("cmp_b_analysis")

if ra and rb:
    st.markdown("---")
    sa = ra.get("composite_score") or 0
    sb = rb.get("composite_score") or 0
    ca = st.session_state.get("cmp_a_card")
    cb = st.session_state.get("cmp_b_card")
    name_a = ca["name"] if ca else "Card A"
    name_b = cb["name"] if cb else "Card B"

    # Winner banner
    if sa < sb:
        winner, win_color = name_a, "#22c55e"
    elif sb < sa:
        winner, win_color = name_b, "#22c55e"
    else:
        winner, win_color = "Tied", "#eab308"

    st.markdown(
        f'<div style="background:{win_color}22;border:2px solid {win_color};border-radius:12px;'
        f'padding:1rem;text-align:center;margin-bottom:1.5rem;">'
        f'<div style="color:{win_color};font-family:\'Press Start 2P\',monospace;font-size:0.65rem;'
        f'letter-spacing:.1em;margin-bottom:0.4rem;">BETTER BUY</div>'
        f'<div style="font-size:1.5rem;font-weight:700;">{winner}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    def score_color(s):
        return "#22c55e" if s <= -25 else ("#eab308" if s < 25 else "#ef4444")

    def make_gauge(r):
        score = r.get("composite_score")
        if score is None:
            return None
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            number={"font": {"color": "#FFDE00", "size": 20}, "suffix": "/100"},
            gauge={
                "axis": {"range": [-100, 100], "tickcolor": "#6b7280",
                         "tickfont": {"color": "#6b7280", "size": 8}},
                "bar": {"color": score_color(score), "thickness": 0.25},
                "bgcolor": "#1e2035",
                "bordercolor": "#374151",
                "borderwidth": 2,
                "steps": [
                    {"range": [-100, -25], "color": "#0f2d1a"},
                    {"range": [-25,   25], "color": "#1c1917"},
                    {"range": [  25, 100], "color": "#2d0f0f"},
                ],
                "threshold": {"line": {"color": "#FFDE00", "width": 2},
                              "thickness": 0.75, "value": score},
            },
        ))
        fig.update_layout(
            paper_bgcolor="#0d0f1a",
            font={"color": "#e8e8e8", "family": "Inter"},
            height=155,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        return fig

    def render_result_col(col, r, pw, details, card):
        with col:
            if details and details.get("images"):
                st.image(
                    details["images"].get("large") or details["images"].get("small"),
                    use_container_width=True,
                )
            else:
                st.markdown(
                    "<div style='background:#1e2035;border-radius:10px;height:220px;"
                    "display:flex;align-items:center;justify-content:center;font-size:2.5rem;'>🃏</div>",
                    unsafe_allow_html=True,
                )
            rarity   = (details or {}).get("rarity", "")
            set_name = (card or {}).get("set_name", "")
            st.markdown(
                f"<div style='margin-top:0.5rem;'><strong>{r['card_name']}</strong><br>"
                f"<span style='color:#9ca3af;font-size:0.8rem;'>{set_name} · {display_rarity(rarity)}</span></div>",
                unsafe_allow_html=True,
            )
            types_html = type_badges(details.get("types", []) if details else [])
            st.markdown(types_html, unsafe_allow_html=True)
            st.markdown(rec_badge(r.get("recommendation", "N/A")), unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            fig = make_gauge(r)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            market = pw.get("market") or r.get("average_price")
            low    = pw.get("low")    or r.get("lowest_price")
            high   = pw.get("high")   or r.get("highest_price")
            m1, m2, m3 = st.columns(3)
            m1.metric("Market", fmt_price(market))
            m2.metric("Low",    fmt_price(low))
            m3.metric("High",   fmt_price(high))
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f'<div class="signal-row">{signal_chips(r)}</div>', unsafe_allow_html=True)

    col_a2, col_b2 = st.columns(2, gap="large")
    render_result_col(col_a2, ra, st.session_state.get("cmp_a_prices", {}),
                      st.session_state.get("cmp_a_details"), ca)
    render_result_col(col_b2, rb, st.session_state.get("cmp_b_prices", {}),
                      st.session_state.get("cmp_b_details"), cb)

    # Score comparison bar chart
    st.markdown("---")
    st.markdown("### Score Comparison")
    st.caption("Negative = undervalued (buy signal) · Positive = overvalued (sell signal)")

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        x=[name_a, name_b],
        y=[sa, sb],
        marker_color=[score_color(sa), score_color(sb)],
        text=[f"{sa:+d}", f"{sb:+d}"],
        textposition="outside",
        textfont={"color": "#e8e8e8", "size": 14},
        width=0.4,
    ))
    fig_bar.add_hline(y=0,  line_color="#6b7280", line_dash="dash")
    fig_bar.add_hline(y=-25, line_color="#22c55e", line_dash="dot",
                      annotation_text="Buy", annotation_font_color="#22c55e",
                      annotation_position="right")
    fig_bar.add_hline(y=25,  line_color="#ef4444", line_dash="dot",
                      annotation_text="Sell", annotation_font_color="#ef4444",
                      annotation_position="right")
    fig_bar.update_layout(
        paper_bgcolor="#0d0f1a",
        plot_bgcolor="#161828",
        font={"color": "#e8e8e8", "family": "Inter"},
        height=280,
        margin=dict(l=10, r=60, t=20, b=10),
        yaxis={
            "range": [-115, 115],
            "gridcolor": "#2a2d45",
            "zerolinecolor": "#2a2d45",
            "tickfont": {"color": "#6b7280"},
            "title": "Composite Score",
            "titlefont": {"color": "#6b7280", "size": 11},
        },
        xaxis={"tickfont": {"color": "#e8e8e8", "size": 13}},
        showlegend=False,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

elif ra or rb:
    st.info("Search and analyze both cards to see the comparison.")

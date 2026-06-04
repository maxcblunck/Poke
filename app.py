import os
import time
import base64
import streamlit as st

# ── Inject Streamlit Cloud secrets into os.environ BEFORE importing scraper ──
# On Streamlit Cloud, API keys live in st.secrets (set via the dashboard).
# We inject them into os.environ here so the scraper's os.getenv() calls
# find them regardless of module import order.
try:
    _pw = st.secrets.get("POKEWALLET_API_KEY", "")
    if _pw:
        os.environ["POKEWALLET_API_KEY"] = _pw
except Exception:
    pass  # running locally — .env handles it

from src.card_db import CardDatabase
from src.scraper import get_card_prices
from src.analyzer import analyze_card
from src.pokemon_popularity import POPULARITY_SCORES

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PokéValue — Pokémon Card Analyser",
    page_icon="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/144.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Inter:wght@400;600&display=swap');

/* ── Base ── */
html, body, .stApp {
    background-color: #0d0f1a !important;
    color: #e8e8e8;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #10121f !important;
    border-right: 2px solid #FFDE00 !important;
}
[data-testid="stSidebar"] * { color: #e8e8e8 !important; }

/* Hide default streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }

/* ── Typography ── */
h1, h2, h3 { font-family: 'Press Start 2P', monospace !important; }
h1 { font-size: 1.6rem !important; line-height: 2.2rem !important; }
h2 { font-size: 1.1rem !important; line-height: 1.8rem !important; color: #FFDE00 !important; }
h3 { font-size: 0.8rem !important; line-height: 1.4rem !important; color: #aaa !important; }
p, span, div, label { font-family: 'Inter', sans-serif !important; }

/* ── Hero banner ── */
.hero {
    background: linear-gradient(135deg, #CC0000 0%, #880000 60%, #0d0f1a 100%);
    border: 3px solid #FFDE00;
    border-radius: 12px;
    padding: 2.5rem 2rem 2rem;
    margin-bottom: 1.8rem;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: "⬤";
    font-size: 28rem;
    color: rgba(255,255,255,0.03);
    position: absolute;
    top: -8rem; right: -8rem;
    line-height: 1;
    pointer-events: none;
}
.hero-title {
    font-family: 'Press Start 2P', monospace;
    font-size: 2.4rem;
    color: #FFDE00;
    text-shadow: 4px 4px 0 #000, -1px -1px 0 #CC0000;
    margin: 0 0 0.7rem 0;
    letter-spacing: 2px;
}
.hero-sub {
    font-family: 'Inter', sans-serif;
    color: rgba(255,255,255,0.85);
    font-size: 1rem;
    margin: 0;
}

/* ── Panel card ── */
.panel {
    background: #161828;
    border: 1px solid #2a2d45;
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
}
.panel-gold {
    border-color: #FFDE00;
}
.panel-red {
    border-color: #CC0000;
}

/* ── Recommendation badge ── */
.badge {
    display: inline-block;
    font-family: 'Press Start 2P', monospace;
    font-size: 0.65rem;
    padding: 0.45rem 0.9rem;
    border-radius: 6px;
    letter-spacing: 1px;
}
.badge-strong-buy  { background:#15803d; color:#fff; border:2px solid #22c55e; }
.badge-buy         { background:#854d0e; color:#fff; border:2px solid #eab308; }
.badge-fair        { background:#374151; color:#ccc; border:2px solid #6b7280; }
.badge-sell        { background:#9a3412; color:#fff; border:2px solid #f97316; }
.badge-strong-sell { background:#7f1d1d; color:#fff; border:2px solid #ef4444; }
.badge-na          { background:#1f2937; color:#6b7280; border:2px solid #374151; }

/* ── HP-style score bar ── */
.score-wrap { margin: 0.5rem 0 1rem; }
.score-label {
    font-family: 'Press Start 2P', monospace;
    font-size: 0.55rem;
    color: #9ca3af;
    margin-bottom: 4px;
    display: flex;
    justify-content: space-between;
}
.score-track {
    background: #1e2035;
    border-radius: 8px;
    height: 22px;
    border: 2px solid #374151;
    position: relative;
    overflow: hidden;
}
.score-fill {
    height: 100%;
    border-radius: 6px;
    transition: width 0.4s ease;
    position: relative;
}
.score-text {
    font-family: 'Press Start 2P', monospace;
    font-size: 0.6rem;
    text-align: right;
    color: #FFDE00;
    margin-top: 4px;
}

/* ── Type badge ── */
.type-badge {
    display: inline-block;
    font-family: 'Inter', sans-serif;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 2px 10px;
    border-radius: 12px;
    margin-right: 4px;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ── Signal row ── */
.signal-row {
    display: flex;
    gap: 0.8rem;
    flex-wrap: wrap;
    margin: 0.6rem 0;
}
.signal-chip {
    background: #1e2035;
    border: 1px solid #2a2d45;
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.8rem;
    font-family: 'Inter', sans-serif;
    white-space: nowrap;
}

/* ── PSA box ── */
.psa-box {
    background: linear-gradient(135deg, #1a1420 0%, #241930 100%);
    border: 2px solid #7c3aed;
    border-radius: 10px;
    padding: 1rem;
    text-align: center;
}
.psa-grade {
    font-family: 'Press Start 2P', monospace;
    font-size: 0.75rem;
    color: #a78bfa;
    margin-bottom: 0.3rem;
}
.psa-price {
    font-family: 'Press Start 2P', monospace;
    font-size: 1.1rem;
    color: #FFDE00;
}

/* ── Streamlit metric value colour override ── */
[data-testid="stMetricValue"] {
    color: #FFDE00 !important;
    font-family: 'Press Start 2P', monospace !important;
    font-size: 0.85rem !important;
}
[data-testid="stMetricLabel"] {
    color: #9ca3af !important;
    font-size: 0.72rem !important;
}

/* ── Pop card (popularity dashboard) ── */
.pop-card {
    background: #161828;
    border: 1px solid #2a2d45;
    border-radius: 10px;
    padding: 0.8rem;
    text-align: center;
    transition: border-color 0.2s;
}
.pop-card:hover { border-color: #FFDE00; }
.pop-name {
    font-family: 'Press Start 2P', monospace;
    font-size: 0.55rem;
    color: #FFDE00;
    margin-top: 0.5rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.pop-score {
    font-size: 0.8rem;
    color: #9ca3af;
    margin-top: 0.2rem;
}

/* ── Stat metric ── */
.stat-box {
    background: #161828;
    border: 1px solid #2a2d45;
    border-radius: 8px;
    padding: 1rem;
    text-align: center;
}
.stat-val {
    font-family: 'Press Start 2P', monospace;
    font-size: 1.2rem;
    color: #FFDE00;
}
.stat-lbl {
    font-size: 0.75rem;
    color: #9ca3af;
    margin-top: 0.4rem;
}

/* ── Buttons ── */
.stButton > button {
    font-family: 'Press Start 2P', monospace !important;
    font-size: 0.6rem !important;
    background: #CC0000 !important;
    color: #FFDE00 !important;
    border: 2px solid #FFDE00 !important;
    border-radius: 6px !important;
    padding: 0.6rem 1.2rem !important;
    cursor: pointer;
    transition: all 0.15s;
}
.stButton > button:hover {
    background: #FFDE00 !important;
    color: #000 !important;
}

/* Inputs */
.stTextInput input, .stSelectbox select, div[data-baseweb="select"] {
    background: #161828 !important;
    border: 1px solid #2a2d45 !important;
    color: #e8e8e8 !important;
    border-radius: 6px !important;
    font-family: 'Inter', sans-serif !important;
}
.stTextInput input:focus { border-color: #FFDE00 !important; outline: none !important; }

/* Divider */
hr { border-color: #2a2d45 !important; }

/* Dataframe */
[data-testid="stDataFrame"] { border: 1px solid #2a2d45; border-radius: 8px; }

/* ── Sidebar widget labels — retro font ── */
[data-testid="stSidebar"] .stMultiSelect label,
[data-testid="stSidebar"] .stNumberInput label,
[data-testid="stSidebar"] .stRadio > label,
[data-testid="stSidebar"] .stSelectbox label {
    font-family: 'Press Start 2P', monospace !important;
    font-size: 0.46rem !important;
    color: #FFDE00 !important;
    letter-spacing: 0.5px !important;
    line-height: 2.2 !important;
}

/* ── Multiselect container — dark ── */
[data-testid="stSidebar"] div[data-baseweb="select"] > div:first-child {
    background: #161828 !important;
    border: 1px solid #2a2d45 !important;
    border-radius: 6px !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] input {
    color: #e8e8e8 !important;
    background: transparent !important;
}

/* Selected tag chips inside multiselect */
[data-testid="stSidebar"] [data-baseweb="tag"] {
    background: #1e2035 !important;
    border: 1px solid #FFDE00 !important;
    border-radius: 4px !important;
}
[data-testid="stSidebar"] [data-baseweb="tag"] span {
    color: #FFDE00 !important;
    font-size: 0.62rem !important;
}
[data-testid="stSidebar"] [data-baseweb="tag"] [role="presentation"] {
    color: #FFDE00 !important;
}

/* ── Number input — dark ── */
[data-testid="stSidebar"] [data-testid="stNumberInput"] input {
    background: #161828 !important;
    border: 1px solid #2a2d45 !important;
    color: #e8e8e8 !important;
    border-radius: 6px !important;
}
[data-testid="stSidebar"] [data-testid="stNumberInput"] button {
    background: #1e2035 !important;
    border-color: #2a2d45 !important;
    color: #FFDE00 !important;
}

/* ── Radio options — Inter (readable at small sizes) ── */
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.78rem !important;
    color: #e8e8e8 !important;
}

/* ── Global dropdown popover — dark ── */
ul[data-baseweb="menu"] {
    background-color: #161828 !important;
    border: 1px solid #2a2d45 !important;
}
ul[data-baseweb="menu"] li {
    background-color: #161828 !important;
    color: #e8e8e8 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.8rem !important;
}
ul[data-baseweb="menu"] li:hover,
ul[data-baseweb="menu"] li[aria-selected="true"] {
    background-color: #1e2035 !important;
    color: #FFDE00 !important;
}

/* Checkbox inside multiselect dropdown */
ul[data-baseweb="menu"] svg { color: #FFDE00 !important; }
</style>
""", unsafe_allow_html=True)

# ── Pokéball background pattern ────────────────────────────────────────────────
# SVG drawn as a 60×60 tile: outer circle, red top half, white bottom half,
# centre dividing line, and button circle. All fills/strokes at ~0.06 opacity
# so it reads as a barely-there watermark against the dark background.
_pokeball_svg = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='60' height='60'>"
    "<path d='M12,30 A18,18 0 0,1 48,30' fill='rgba(204,0,0,0.07)' stroke='rgba(255,255,255,0.06)' stroke-width='1.5'/>"
    "<path d='M12,30 A18,18 0 0,0 48,30' fill='rgba(200,200,200,0.04)' stroke='rgba(255,255,255,0.06)' stroke-width='1.5'/>"
    "<line x1='12' y1='30' x2='48' y2='30' stroke='rgba(255,255,255,0.07)' stroke-width='2'/>"
    "<circle cx='30' cy='30' r='18' fill='none' stroke='rgba(255,255,255,0.07)' stroke-width='1.5'/>"
    "<circle cx='30' cy='30' r='5' fill='rgba(13,15,26,0.6)' stroke='rgba(255,255,255,0.07)' stroke-width='2'/>"
    "<circle cx='30' cy='30' r='2.5' fill='rgba(255,255,255,0.06)'/>"
    "</svg>"
)
_pokeball_b64 = base64.b64encode(_pokeball_svg.encode()).decode()

st.markdown(f"""
<style>
.stApp {{
    background-image: url("data:image/svg+xml;base64,{_pokeball_b64}");
    background-repeat: repeat;
    background-size: 60px 60px;
    background-attachment: fixed;
}}
</style>
""", unsafe_allow_html=True)

# ── Type colour map ─────────────────────────────────────────────────────────────
TYPE_COLORS = {
    "Fire":      "#e25822", "Water":    "#4d9be6", "Grass":    "#5db85d",
    "Lightning": "#f7d716", "Psychic":  "#e96bb0", "Fighting": "#c04a28",
    "Darkness":  "#5a5a8a", "Metal":    "#9badb7", "Dragon":   "#7038f8",
    "Fairy":     "#f0a0d0", "Colorless":"#a8a878",
}

# ── Helpers ─────────────────────────────────────────────────────────────────────

_RARITY_DISPLAY: dict[str, str] = {
    "Rare Rainbow":              "Rainbow Rare (Secret)",
    "Rare Secret":               "Gold Secret Rare",
    "Rare Ultra":                "Full Art / Alt Art",
    "Ultra Rare":                "Ultra Rare",
    "Special Illustration Rare": "Special Illustration Rare (Alt Art)",
    "Hyper Rare":                "Hyper Rare (Gold)",
    "Rare Shiny":                "Shiny Rare",
    "Rare Shiny GX":             "Shiny GX Secret",
    "Trainer Gallery Rare Holo": "Trainer Gallery",
    "Rare Holo VMAX":            "Rare Holo VMAX",
    "Rare Holo VSTAR":           "Rare Holo VSTAR",
    "Rare Holo V":               "Rare Holo V",
    "Rare Holo GX":              "Rare Holo GX",
    "Rare Holo EX":              "Rare Holo EX",
    "Double Rare":               "Double Rare (ex)",
    "ACE SPEC Rare":             "ACE SPEC Rare",
}


def display_rarity(rarity: str) -> str:
    return _RARITY_DISPLAY.get(rarity, rarity)


def fmt_price(v) -> str:
    return f"${v:,.2f}" if v is not None else "N/A"


def rec_badge(rec: str) -> str:
    classes = {
        "Strong Buy":  "badge-strong-buy",
        "Buy":         "badge-buy",
        "Fair Value":  "badge-fair",
        "Sell":        "badge-sell",
        "Strong Sell": "badge-strong-sell",
    }
    cls = classes.get(rec, "badge-na")
    return f'<span class="badge {cls}">{rec}</span>'


def score_bar(score) -> str:
    if score is None:
        return "<p style='color:#6b7280;font-size:0.8rem;'>No score</p>"
    pct = (score + 100) / 200 * 100
    pct = max(0, min(100, pct))
    if score >= 30:
        color = "linear-gradient(90deg,#15803d,#22c55e)"
    elif score >= -30:
        color = "linear-gradient(90deg,#854d0e,#eab308)"
    else:
        color = "linear-gradient(90deg,#7f1d1d,#ef4444)"
    sign = "+" if score >= 0 else ""
    return f"""
    <div class="score-wrap">
      <div class="score-label"><span>UNDERVALUED</span><span>OVERVALUED</span></div>
      <div class="score-track">
        <div class="score-fill" style="width:{pct}%;background:{color};"></div>
      </div>
      <div class="score-text">{sign}{score} / 100</div>
    </div>"""


def type_badges(types: list) -> str:
    html = ""
    for t in (types or []):
        color = TYPE_COLORS.get(t, "#555")
        html += f'<span class="type-badge" style="background:{color};color:#fff;">{t}</span>'
    return html


def signal_chips(result: dict) -> str:
    chips = []
    trend = result.get("trend")
    pct   = result.get("trend_pct_change")
    if trend == "no data":
        chips.append("━ Trend: not enough sales history")
    elif trend:
        icon = "▲" if trend == "rising" else ("▼" if trend == "falling" else "━")
        sign = "+" if (pct or 0) >= 0 else ""
        chips.append(f'{icon} Trend: {trend.title()} ({sign}{pct:.1f}%)' if pct is not None else f"{icon} {trend.title()}")
    if result.get("volatility"):
        chips.append(f"≈ {result['volatility'].title()} volatility")
    if result.get("rarity_baseline"):
        chips.append(f"◈ {result['rarity_baseline'].title()}")
    pop = result.get("popularity_score")
    if pop is not None:
        chips.append(f"★ Popularity {pop:.0f}/100")
    scar = result.get("scarcity_score")
    if scar is not None:
        chips.append(f"⧖ Scarcity {scar:.0f}/100")
    pull = result.get("pull_odds_packs")
    if pull is not None:
        chips.append(f"◈ ~{pull:.0f} packs to pull")
    return "".join(f'<span class="signal-chip">{c}</span>' for c in chips)


# ── Data loaders ────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Loading card database…")
def load_database():
    return CardDatabase()


@st.cache_data
def load_popularity():
    return sorted(
        [{"name": k, "score": v} for k, v in POPULARITY_SCORES.items()],
        key=lambda r: r["score"],
        reverse=True,
    )


@st.cache_data
def get_rare_set_names(db_key=None):
    return sorted({c["set_name"] for c in db.get_rare_cards()})


db = load_database()

# ── Sidebar ─────────────────────────────────────────────────────────────────────
SCAN_RARITY_OPTIONS = ["Rare Holo", "Rare Ultra", "Rare Secret", "Rare Rainbow"]

with st.sidebar:
    st.markdown("### ⚙ SCAN FILTERS")
    st.markdown("---")
    selected_rarities = st.multiselect("Rarity", SCAN_RARITY_OPTIONS, default=SCAN_RARITY_OPTIONS)
    selected_sets     = st.multiselect("Sets (empty = all)", get_rare_set_names(), default=[])
    max_cards         = st.number_input("Max cards", 10, 500, 50, 10)
    sort_order        = st.radio("Sort", ["Highest score first", "Lowest score first"], index=0)
    st.markdown("---")
    _pw_key = os.environ.get("POKEWALLET_API_KEY", "")
    if _pw_key.startswith("pk_live_"):
        st.markdown("<span style='font-size:0.7rem;color:#22c55e !important;background:#14532d;padding:2px 8px;border-radius:4px;'>&#9679; API Live</span>", unsafe_allow_html=True)
    elif _pw_key.startswith("pk_test_"):
        st.markdown("<span style='font-size:0.7rem;color:#000 !important;background:#eab308;padding:2px 8px;border-radius:4px;'>&#9679; Test Key — limited</span>", unsafe_allow_html=True)
    else:
        st.markdown("<span style='font-size:0.7rem;color:#fff !important;background:#ef4444;padding:2px 8px;border-radius:4px;'>&#9679; No API Key</span>", unsafe_allow_html=True)

# ── Hero ─────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <p class="hero-title">🎴 PokéValue</p>
  <p class="hero-sub">Card Valuation Powered by Scarcity, Popularity & Simulated Market Data</p>
</div>
""", unsafe_allow_html=True)

# ── Popularity dashboard ─────────────────────────────────────────────────────────
pop_data = load_popularity()

if pop_data:
    st.markdown("## 🌟 POPULARITY RANKINGS")
    st.markdown("<p style='color:#9ca3af;margin-bottom:1rem;'>Fan sentiment scores across all 1025 Pokémon · community polls &amp; cultural impact</p>", unsafe_allow_html=True)

    top = pop_data[:20]

    def _render_pop_row(entries):
        cols = st.columns(len(entries))
        for col, row in zip(cols, entries):
            name  = row["name"]
            score = float(row["score"])
            matches = db.search_card(name)
            img_url = None
            if matches:
                det = db.get_card_details(matches[0]["name"], matches[0]["set_name"], matches[0].get("number"))
                if det and det.get("images"):
                    img_url = det["images"].get("small")
            bar_color = "#FFDE00" if score >= 75 else ("#f97316" if score >= 55 else "#9ca3af")
            with col:
                if img_url:
                    st.image(img_url, use_container_width=True)
                else:
                    st.markdown("<div style='height:80px;background:#1e2035;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1.5rem;'>?</div>", unsafe_allow_html=True)
                st.markdown(f"""
                <div class='pop-name'>{name.upper()}</div>
                <div style='background:#1e2035;border-radius:4px;height:6px;margin:4px 0;'>
                  <div style='width:{score:.0f}%;height:100%;background:{bar_color};border-radius:4px;'></div>
                </div>
                <div class='pop-score'>{score:.0f} / 100</div>
                """, unsafe_allow_html=True)

    _render_pop_row(top[:10])
    st.markdown("<div style='margin:0.6rem 0;'></div>", unsafe_allow_html=True)
    _render_pop_row(top[10:])
    st.markdown("---")

# ── Quick stats row ──────────────────────────────────────────────────────────────
all_cards  = db._cards if hasattr(db, "_cards") else []
total_sets = len({c.get("set_name") for c in all_cards}) if all_cards else "—"
rare_count = len(db.get_rare_cards())

c1, c2, c3, c4 = st.columns(4)
for col, val, lbl in [
    (c1, f"{len(all_cards):,}" if all_cards else "—", "CARDS IN DB"),
    (c2, str(total_sets),                              "SETS"),
    (c3, str(rare_count),                              "RARE+ CARDS"),
    (c4, str(len(POPULARITY_SCORES)),                   "TRACKED SPECIES"),
]:
    col.markdown(f"""
    <div class="stat-box">
      <div class="stat-val">{val}</div>
      <div class="stat-lbl">{lbl}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")

# ── Session state ────────────────────────────────────────────────────────────────
for key, default in [("search_results", []), ("selected_card", None), ("analysis_result", None), ("nm_market_price", None), ("_pw_prices", {}), ("_pw_variants", []), ("_variant_idx", 0), ("_analyzed_variant_idx", 0), ("_raw_prices", []), ("_card_label", ""), ("_card_details_cache", None), ("data_source", "simulated")]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Section 1: Card search ───────────────────────────────────────────────────────
st.markdown("## 🔍 SEARCH A CARD")

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

    if st.button("ANALYSE CARD"):
        card      = st.session_state.selected_card
        label     = f"{card['name']} ({card['set_name']})"
        details   = db.get_card_details(card["name"], card["set_name"], card.get("number"))
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
            st.session_state._pw_variants        = first.get("all_variants", []) if is_pw else []
            st.session_state._variant_idx        = 0
            st.session_state._analyzed_variant_idx = 0
            st.session_state._raw_prices         = prices
            st.session_state._card_label         = label
            st.session_state._card_details_cache = details
            st.session_state.data_source         = first.get("data_source", "simulated")
            variant_name = first.get("sub_type_name", "") if is_pw else ""
            st.session_state.analysis_result = analyze_card(label, prices, details, variant=variant_name)

# ── Analysis display ─────────────────────────────────────────────────────────────
if st.session_state.analysis_result:
    r       = st.session_state.analysis_result
    card    = st.session_state.selected_card
    details = db.get_card_details(card["name"], card["set_name"], card.get("number")) if card else None

    st.markdown("---")

    # ── Variant selector ────────────────────────────────────────────────────────
    # Shown whenever the API returns multiple printings (e.g. Unlimited,
    # Shadowless, 1st Edition Shadowless, 1st Edition for Base Set cards).
    # The selected variant drives all price display below.
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
        # Re-analyze when variant changes so scarcity / score reflect the printing
        if sel_idx != st.session_state.get("_analyzed_variant_idx", 0):
            sel_variant  = variants[sel_idx]
            vname        = sel_variant.get("sub_type_name", "")
            mp = sel_variant.get("market_price") or 0
            lp = sel_variant.get("low_price")    or mp
            hp = sel_variant.get("high_price")   or mp
            v_prices = [{"price": f"${p:.2f}"} for p in [mp, lp, hp, mp, lp]]
            _lbl     = st.session_state.get("_card_label", r.get("card_name", ""))
            _det     = st.session_state.get("_card_details_cache")
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

    # ── Two-column layout ───────────────────────────────────────────────────────
    img_col, info_col = st.columns([1, 2], gap="large")

    with img_col:
        if details and details.get("images"):
            st.image(details["images"].get("large") or details["images"].get("small"), use_container_width=True)
        else:
            st.markdown("<div style='background:#1e2035;border-radius:12px;height:340px;display:flex;align-items:center;justify-content:center;font-size:3rem;'>🃏</div>", unsafe_allow_html=True)

        # NM Market Price — reflects the selected variant
        nm = pw.get("market") or r.get("average_price")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="psa-box" style="border-color:#22c55e;">
          <div class="psa-grade" style="color:#22c55e;">NM MARKET PRICE</div>
          <div class="psa-price">{fmt_price(nm)}</div>
        </div>""", unsafe_allow_html=True)

    with info_col:
        # Name + types
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

        # Recommendation badge
        st.markdown(rec_badge(r.get("recommendation", "N/A")), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # Score bar
        st.markdown(score_bar(r.get("composite_score")), unsafe_allow_html=True)

        # Price metrics — market price from API; low/high show the listing spread
        m1, m2, m3 = st.columns(3)
        m1.metric("Market Price", fmt_price(pw.get("market") or r.get("average_price")))
        m2.metric("Lowest Ask",   fmt_price(pw.get("low")    or r.get("lowest_price")))
        m3.metric("Highest Ask",  fmt_price(pw.get("high")   or r.get("highest_price")))

        st.markdown("<br>", unsafe_allow_html=True)

        # Signal chips
        st.markdown(f'<div class="signal-row">{signal_chips(r)}</div>', unsafe_allow_html=True)

        # Extra detail expander
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

st.markdown("---")

# ── Section 2: Bulk scan ─────────────────────────────────────────────────────────
st.markdown("## 📋 BULK RARE CARD SCAN")
st.markdown("<p style='color:#9ca3af;'>Filter in the sidebar, then scan the rare card pool for signals.</p>", unsafe_allow_html=True)

col_u, col_o = st.columns(2)
scan_under = col_u.button("🟢  SHOW UNDERVALUED", use_container_width=True)
scan_over  = col_o.button("🔴  SHOW OVERVALUED",  use_container_width=True)


def build_pool(rarities, sets, limit):
    candidates = db.get_rare_cards()
    if rarities: candidates = [c for c in candidates if c.get("rarity") in rarities]
    if sets:     candidates = [c for c in candidates if c.get("set_name") in sets]
    return candidates[:limit]


def run_scan(signal, rarities, sets, limit, highest_first):
    pool = build_pool(rarities, sets, limit)
    if not pool:
        st.warning("No cards match the filters.")
        return

    results  = []
    progress = st.progress(0, text="Starting…")
    for i, card in enumerate(pool):
        label   = f"{card['name']} ({card['set_name']})"
        details = db.get_card_details(card["name"], card["set_name"], card.get("number"))
        progress.progress((i + 1) / len(pool), text=f"{label}  ({i+1}/{len(pool)})")
        results.append(analyze_card(label, get_card_prices(label, details.get("id") if details else None), details))
        if i < len(pool) - 1:
            time.sleep(0.5)
    progress.empty()

    flagged = [r for r in results if (r.get("recommendation") or "").lower().startswith(signal.lower())]
    flagged.sort(key=lambda r: r.get("composite_score") or 0, reverse=highest_first)

    a, b, c_ = st.columns(3)
    a.metric("Scanned",  len(pool))
    b.metric("Flagged",  len(flagged))
    c_.metric("Hit rate", f"{len(flagged)/len(pool)*100:.0f}%" if pool else "—")

    if not flagged:
        st.info(f"No {signal} signals found.")
        return

    rows = [{
        "Card":        r["card_name"],
        "Market (NM)": fmt_price(r.get("average_price")),
        "Score":       r.get("composite_score"),
        "Popularity":  r.get("popularity_score"),
        "Scarcity":    r.get("scarcity_score"),
        "Signal":      r.get("recommendation"),
    } for r in flagged]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    for r in flagged:
        with st.expander(f"{r['card_name']}  ·  {r.get('recommendation','')}"):
            st.markdown(score_bar(r.get("composite_score")), unsafe_allow_html=True)
            st.markdown(f'<div class="signal-row">{signal_chips(r)}</div>', unsafe_allow_html=True)
            cols = st.columns(4)
            for col, (lbl, val) in zip(cols, [
                ("Market (NM)", fmt_price(r.get("average_price"))),
                ("Low",         fmt_price(r.get("lowest_price"))),
                ("High",        fmt_price(r.get("highest_price"))),
                ("Score",       r.get("composite_score")),
            ]):
                col.metric(lbl, val)


if scan_under:
    st.markdown("### 🟢 UNDERVALUED PICKS")
    run_scan("Buy", selected_rarities, selected_sets, max_cards, True)

if scan_over:
    st.markdown("### 🔴 OVERVALUED PICKS")
    run_scan("Sell", selected_rarities, selected_sets, max_cards, False)

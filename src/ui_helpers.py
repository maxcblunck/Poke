import base64
import streamlit as st
from src.pokemon_popularity import POPULARITY_SCORES

TYPE_COLORS = {
    "Fire":      "#e25822", "Water":    "#4d9be6", "Grass":    "#5db85d",
    "Lightning": "#f7d716", "Psychic":  "#e96bb0", "Fighting": "#c04a28",
    "Darkness":  "#5a5a8a", "Metal":    "#9badb7", "Dragon":   "#7038f8",
    "Fairy":     "#f0a0d0", "Colorless":"#a8a878",
}

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

# CSS not covered by config.toml: font imports, custom component classes,
# sidebar overrides, and Streamlit internal element overrides.
GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Inter:wght@400;600&display=swap');

h1, h2, h3 { font-family: 'Press Start 2P', monospace !important; }
h1 { font-size: 1.6rem !important; line-height: 2.2rem !important; }
h2 { font-size: 1.1rem !important; line-height: 1.8rem !important; color: #FFDE00 !important; }
h3 { font-size: 0.8rem !important; line-height: 1.4rem !important; color: #aaa !important; }
p, span, div, label { font-family: 'Inter', sans-serif !important; }

#MainMenu, footer, header { visibility: hidden; }

/* ── Hero ── */
.hero {
    background: linear-gradient(135deg, #FF8C00 0%, #CC0000 60%, #880000 100%);
    border: 3px solid #FFDE00;
    border-radius: 12px;
    padding: 2.5rem 2rem 2rem;
    margin-bottom: 1.8rem;
    position: relative;
    overflow: hidden;
    text-align: center;
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
    font-family: 'Press Start 2P', monospace !important;
    font-size: 2.4rem;
    color: #FFDE00;
    text-shadow: 4px 4px 0 #000, -1px -1px 0 #FF8C00;
    margin: 0 0 0.7rem 0;
    letter-spacing: 2px;
}
.hero-sub {
    font-family: 'Inter', sans-serif;
    color: rgba(255,255,255,0.85);
    font-size: 1rem;
    margin: 0;
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
.signal-row { display: flex; gap: 0.8rem; flex-wrap: wrap; margin: 0.6rem 0; }
.signal-chip {
    background: #1e2035;
    border: 1px solid #2a2d45;
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.8rem;
    font-family: 'Inter', sans-serif;
    white-space: nowrap;
}

/* ── PSA price box ── */
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

/* ── Streamlit metric overrides ── */
[data-testid="stMetricValue"] {
    color: #FFDE00 !important;
    font-family: 'Press Start 2P', monospace !important;
    font-size: 0.85rem !important;
}
[data-testid="stMetricLabel"] {
    color: #9ca3af !important;
    font-size: 0.72rem !important;
}

/* ── Popularity card ── */
.pop-name {
    font-family: 'Press Start 2P', monospace;
    font-size: 0.55rem;
    color: #FFDE00;
    margin-top: 0.5rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.pop-score { font-size: 0.8rem; color: #9ca3af; margin-top: 0.2rem; }

/* ── Stat box ── */
.stat-box {
    background: #161828;
    border: 1px solid #2a2d45;
    border-radius: 8px;
    padding: 1rem;
    text-align: center;
}
.stat-val { font-family: 'Press Start 2P', monospace; font-size: 1.2rem; color: #FFDE00; }
.stat-lbl { font-size: 0.75rem; color: #9ca3af; margin-top: 0.4rem; }

/* ── Buttons ── */
.stButton > button {
    font-family: 'Press Start 2P', monospace !important;
    font-size: 0.6rem !important;
    background: #CC0000 !important;
    color: #FFDE00 !important;
    border: 2px solid #FFDE00 !important;
    border-radius: 6px !important;
    padding: 0.6rem 1.2rem !important;
    transition: all 0.15s;
}
.stButton > button:hover { background: #FFDE00 !important; color: #000 !important; }

/* ── Inputs ── */
.stTextInput input, div[data-baseweb="select"] {
    background: #161828 !important;
    border: 1px solid #2a2d45 !important;
    color: #e8e8e8 !important;
    border-radius: 6px !important;
    font-family: 'Inter', sans-serif !important;
}
.stTextInput input:focus { border-color: #FFDE00 !important; outline: none !important; }

hr { border-color: #2a2d45 !important; }
[data-testid="stDataFrame"] { border: 1px solid #2a2d45; border-radius: 8px; }

/* ── NM Listings table ── */
.listings-table { width: 100%; border-collapse: collapse; font-family: 'Inter', sans-serif; font-size: 0.82rem; }
.listings-table thead tr { border-bottom: 2px solid #FFDE00; }
.listings-table thead th { color: #FFDE00; font-weight: 600; padding: 6px 10px; text-align: left; font-size: 0.72rem; letter-spacing: 0.5px; text-transform: uppercase; }
.listings-table tbody tr { border-bottom: 1px solid #2a2d45; transition: background 0.1s; }
.listings-table tbody tr:hover { background: #1e2035; }
.listings-table tbody td { padding: 7px 10px; color: #e8e8e8; vertical-align: middle; }
.listing-price { font-family: 'Press Start 2P', monospace; font-size: 0.75rem; color: #22c55e; }
.listing-price-high { color: #ef4444; }
.listing-verified { background: #1a3a2a; color: #22c55e; border: 1px solid #22c55e; border-radius: 4px; font-size: 0.65rem; padding: 1px 6px; white-space: nowrap; }
.listing-rating { color: #eab308; }
.listings-header { display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.6rem; }
.listings-source-badge { background: #14532d; color: #86efac; border: 1px solid #22c55e; border-radius: 4px; font-size: 0.7rem; padding: 2px 8px; font-family: 'Inter', sans-serif; }

/* ── Sidebar ── */
[data-testid="stSidebar"] { background: #10121f !important; border-right: 2px solid #FFDE00 !important; }
[data-testid="stSidebar"] * { color: #e8e8e8 !important; }
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
[data-testid="stSidebar"] div[data-baseweb="select"] > div:first-child {
    background: #161828 !important;
    border: 1px solid #2a2d45 !important;
    border-radius: 6px !important;
}
[data-testid="stSidebar"] div[data-baseweb="select"] input {
    color: #e8e8e8 !important;
    background: transparent !important;
}
[data-testid="stSidebar"] [data-baseweb="tag"] {
    background: #1e2035 !important;
    border: 1px solid #FFDE00 !important;
    border-radius: 4px !important;
}
[data-testid="stSidebar"] [data-baseweb="tag"] span { color: #FFDE00 !important; font-size: 0.62rem !important; }
[data-testid="stSidebar"] [data-baseweb="tag"] [role="presentation"] { color: #FFDE00 !important; }
[data-testid="stSidebar"] [data-testid="stNumberInput"] input {
    background: #161828 !important; border: 1px solid #2a2d45 !important;
    color: #e8e8e8 !important; border-radius: 6px !important;
}
[data-testid="stSidebar"] [data-testid="stNumberInput"] button {
    background: #1e2035 !important; border-color: #2a2d45 !important; color: #FFDE00 !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label {
    font-family: 'Inter', sans-serif !important; font-size: 0.78rem !important; color: #e8e8e8 !important;
}

/* ── Global dropdown popover ── */
ul[data-baseweb="menu"] { background-color: #161828 !important; border: 1px solid #2a2d45 !important; }
ul[data-baseweb="menu"] li {
    background-color: #161828 !important; color: #e8e8e8 !important;
    font-family: 'Inter', sans-serif !important; font-size: 0.8rem !important;
}
ul[data-baseweb="menu"] li:hover,
ul[data-baseweb="menu"] li[aria-selected="true"] {
    background-color: #1e2035 !important; color: #FFDE00 !important;
}
ul[data-baseweb="menu"] svg { color: #FFDE00 !important; }
</style>
"""

# Pokéball watermark background pattern
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

_ANIMATED = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-v/black-white/animated/"
# (id, top%, left%, size-px, opacity)
_BG_SPRITES = [
    (25,  "4%",  "2%",  72, 0.10),   # Pikachu
    (6,   "8%",  "88%", 80, 0.08),   # Charizard
    (150, "28%", "94%", 88, 0.07),   # Mewtwo
    (94,  "52%", "1%",  76, 0.09),   # Gengar
    (143, "68%", "85%", 90, 0.07),   # Snorlax
    (131, "82%", "6%",  80, 0.08),   # Lapras
    (149, "88%", "92%", 80, 0.07),   # Dragonite
    (133, "46%", "48%", 64, 0.06),   # Eevee (subtle centre)
]
_sprite_imgs = "".join(
    f'<img src="{_ANIMATED}{pid}.gif" style="position:fixed;top:{top};left:{left};'
    f'width:{sz}px;height:{sz}px;opacity:{op};image-rendering:pixelated;'
    f'pointer-events:none;z-index:0;" />'
    for pid, top, left, sz, op in _BG_SPRITES
)

POKEBALL_CSS = f"""
<style>
.stApp {{
    background-image: url("data:image/svg+xml;base64,{_pokeball_b64}");
    background-repeat: repeat;
    background-size: 60px 60px;
    background-attachment: fixed;
}}
</style>
{_sprite_imgs}
"""


# ── Cached data loaders ──────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Loading card database…")
def load_database():
    from src.card_db import CardDatabase
    return CardDatabase()


@st.cache_data
def load_popularity():
    return sorted(
        [{"name": k, "score": v} for k, v in POPULARITY_SCORES.items()],
        key=lambda r: r["score"],
        reverse=True,
    )


# ── UI helpers ───────────────────────────────────────────────────────────────

def display_rarity(rarity: str) -> str:
    return _RARITY_DISPLAY.get(rarity, rarity)


def fmt_price(v) -> str:
    return f"${v:,.2f}" if v is not None else "N/A"


def rec_badge(rec: str) -> str:
    classes = {
        "Strong Buy":  "badge-strong-buy",
        "Buy":         "badge-buy",
        "Hold":        "badge-fair",
        "Sell":        "badge-sell",
        "Strong Sell": "badge-strong-sell",
    }
    cls = classes.get(rec, "badge-na")
    return f'<span class="badge {cls}">{rec}</span>'


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

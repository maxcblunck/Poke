import os
import streamlit as st

# Inject Streamlit Cloud secrets into os.environ before any other imports.
# On Streamlit Cloud, API keys live in st.secrets; locally, .env handles it.
try:
    _pw = st.secrets.get("POKEWALLET_API_KEY", "")
    if _pw:
        os.environ["POKEWALLET_API_KEY"] = _pw
    _pt = st.secrets.get("POKETRACE_API_KEY", "")
    if _pt:
        os.environ["POKETRACE_API_KEY"] = _pt
except Exception:
    pass

from src.ui_helpers import GLOBAL_CSS, POKEBALL_CSS

st.set_page_config(
    page_title="PokéValue — Pokémon Card Analyzer",
    page_icon="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/144.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
st.markdown(POKEBALL_CSS, unsafe_allow_html=True)

# Hero banner shown on every page
st.markdown("""
<div class="hero">
  <p class="hero-title" style="font-family:'Press Start 2P',monospace;">PokéValue & PokéCross</p>
  <p class="hero-sub">Card Valuation Tool and Fun 2D Game</p>
</div>
""", unsafe_allow_html=True)

pg = st.navigation([
    st.Page("pages/1_Popularity.py", title="Popularity",  icon="🌟"),
    st.Page("pages/2_Search.py",     title="Card Search", icon="🔍"),
    st.Page("pages/3_Game.py",       title="PokéCross",   icon="⚡"),
])
pg.run()

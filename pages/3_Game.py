import pathlib
import streamlit as st
import streamlit.components.v1 as components

from src.ui_helpers import GLOBAL_CSS

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
st.markdown("""
<div style="text-align:center;padding:12px 0 4px;color:#94a3b8;font-size:0.8rem;letter-spacing:.05em">
  ⚡ POKÉCROSS — use arrow keys or WASD to move
</div>
""", unsafe_allow_html=True)

game_html = pathlib.Path(__file__).parent.parent / "game.html"
components.html(game_html.read_text(encoding="utf-8"), height=760, scrolling=False)

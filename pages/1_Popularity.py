import streamlit as st
from streamlit_extras.colored_header import colored_header
from src.ui_helpers import load_database, load_popularity, fmt_price

db = load_database()
pop_data = load_popularity()

colored_header(
    label="Popularity Rankings",
    description="Fan sentiment scores across all 1025 Pokémon · community polls & cultural impact",
    color_name="yellow-80",
)

if not pop_data:
    st.info("No popularity data available.")
    st.stop()

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
                st.markdown(
                    "<div style='height:80px;background:#1e2035;border-radius:8px;"
                    "display:flex;align-items:center;justify-content:center;font-size:1.5rem;'>?</div>",
                    unsafe_allow_html=True,
                )
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

# ── Database stats row ───────────────────────────────────────────────────────
all_cards  = db._cards if hasattr(db, "_cards") else []
total_sets = len({c.get("set_name") for c in all_cards}) if all_cards else "—"
rare_count = len(db.get_rare_cards())

from src.pokemon_popularity import POPULARITY_SCORES

c1, c2, c3, c4 = st.columns(4)
for col, val, lbl in [
    (c1, f"{len(all_cards):,}" if all_cards else "—", "CARDS IN DB"),
    (c2, str(total_sets),                              "SETS"),
    (c3, str(rare_count),                              "RARE+ CARDS"),
    (c4, str(len(POPULARITY_SCORES)),                  "TRACKED SPECIES"),
]:
    col.markdown(f"""
    <div class="stat-box">
      <div class="stat-val">{val}</div>
      <div class="stat-lbl">{lbl}</div>
    </div>""", unsafe_allow_html=True)

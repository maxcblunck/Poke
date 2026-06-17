import streamlit as st
from src.db import init_db, register_user, login_user, get_collection, add_to_collection, remove_from_collection
from src.ui_helpers import load_database

init_db()

# ── Session state defaults ──────────────────────────────────────────────────
for key, default in [
    ("col_user_id", None),
    ("col_username", None),
    ("col_search_results", []),
    ("col_selected_card", None),
    ("col_add_success", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Condition options ───────────────────────────────────────────────────────
CONDITIONS = ["NM", "LP", "MP", "HP", "Damaged"]
CONDITION_COLORS = {
    "NM":      "#4CAF50",
    "LP":      "#8BC34A",
    "MP":      "#FFC107",
    "HP":      "#FF5722",
    "Damaged": "#9E9E9E",
}

# ── Page header ─────────────────────────────────────────────────────────────
st.markdown("""
<h2 style='font-family:"Press Start 2P",monospace;color:#FFDE00;
           text-shadow:2px 2px 0 #000;margin-bottom:0.25rem;'>
  My Collection
</h2>
""", unsafe_allow_html=True)

# ── AUTH: not logged in ──────────────────────────────────────────────────────
if st.session_state.col_user_id is None:
    st.markdown(
        "<p style='color:#ccc;margin-bottom:1.5rem;'>"
        "Create an account or log in to track your cards.</p>",
        unsafe_allow_html=True,
    )

    login_tab, register_tab = st.tabs(["Login", "Register"])

    with login_tab:
        with st.form("login_form"):
            l_user = st.text_input("Username")
            l_pass = st.text_input("Password", type="password")
            if st.form_submit_button("Log In", use_container_width=True):
                user = login_user(l_user, l_pass)
                if user:
                    st.session_state.col_user_id = user["id"]
                    st.session_state.col_username = user["username"]
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

    with register_tab:
        with st.form("register_form"):
            r_user = st.text_input("Choose a username")
            r_pass = st.text_input("Choose a password", type="password")
            r_pass2 = st.text_input("Confirm password", type="password")
            if st.form_submit_button("Create Account", use_container_width=True):
                if r_pass != r_pass2:
                    st.error("Passwords don't match.")
                else:
                    ok, msg = register_user(r_user, r_pass)
                    if ok:
                        user = login_user(r_user, r_pass)
                        st.session_state.col_user_id = user["id"]
                        st.session_state.col_username = user["username"]
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
    st.stop()

# ── LOGGED IN ────────────────────────────────────────────────────────────────
user_id = st.session_state.col_user_id
username = st.session_state.col_username

col_header, col_logout = st.columns([5, 1])
with col_header:
    collection = get_collection(user_id)
    st.markdown(
        f"<p style='color:#aaa;margin:0;'>Logged in as "
        f"<span style='color:#FFDE00;font-weight:bold;'>{username}</span> "
        f"· {len(collection)} card{'s' if len(collection) != 1 else ''}</p>",
        unsafe_allow_html=True,
    )
with col_logout:
    if st.button("Log Out", use_container_width=True):
        st.session_state.col_user_id = None
        st.session_state.col_username = None
        st.session_state.col_search_results = []
        st.session_state.col_selected_card = None
        st.rerun()

st.divider()

# ── ADD CARDS SECTION ────────────────────────────────────────────────────────
st.markdown(
    "<h4 style='font-family:\"Press Start 2P\",monospace;color:#FFDE00;"
    "font-size:0.75rem;'>Add Cards</h4>",
    unsafe_allow_html=True,
)

search_col, btn_col = st.columns([4, 1])
with search_col:
    query = st.text_input("Search by name", label_visibility="collapsed",
                          placeholder="Search Pokémon card name…")
with btn_col:
    do_search = st.button("Search", use_container_width=True)

if do_search and query.strip():
    db = load_database()
    results = db.search_card(query.strip())
    st.session_state.col_search_results = results
    st.session_state.col_selected_card = None

if st.session_state.col_search_results:
    results = st.session_state.col_search_results
    options = [
        f"{r['name']} — {r['set_name']} #{r['number']} ({r.get('rarity', '?')})"
        for r in results
    ]
    sel_idx = st.selectbox(
        f"{len(results)} result(s) — pick one to add:",
        range(len(options)),
        format_func=lambda i: options[i],
        label_visibility="collapsed",
    )

    selected_summary = results[sel_idx]
    db = load_database()
    card_full = db.get_card_details(
        selected_summary["name"],
        selected_summary["set_name"],
        selected_summary.get("number"),
    )

    if card_full:
        add_cols = st.columns([1, 2, 1])
        with add_cols[0]:
            img = card_full.get("images", {}).get("small")
            if img:
                st.image(img, width=120)
        with add_cols[1]:
            st.markdown(
                f"**{card_full.get('name')}**  \n"
                f"{card_full.get('set_name')} · #{card_full.get('number')}  \n"
                f"*{card_full.get('rarity', 'Unknown rarity')}*"
            )
            condition = st.selectbox("Condition", CONDITIONS, key="add_condition")
        with add_cols[2]:
            st.write("")
            st.write("")
            if st.button("Add to Collection", use_container_width=True, type="primary"):
                add_to_collection(user_id, card_full, condition)
                name = card_full.get("name", "Card")
                st.session_state.col_add_success = f"{name} added!"
                st.session_state.col_search_results = []
                st.session_state.col_selected_card = None
                st.rerun()

if st.session_state.col_add_success:
    st.success(st.session_state.col_add_success)
    st.session_state.col_add_success = None

st.divider()

# ── COLLECTION GRID ──────────────────────────────────────────────────────────
st.markdown(
    "<h4 style='font-family:\"Press Start 2P\",monospace;color:#FFDE00;"
    "font-size:0.75rem;'>My Cards</h4>",
    unsafe_allow_html=True,
)

collection = get_collection(user_id)

if not collection:
    st.markdown(
        "<p style='color:#888;text-align:center;padding:2rem;'>"
        "No cards yet — search above to add some!</p>",
        unsafe_allow_html=True,
    )
else:
    COLS_PER_ROW = 5
    rows = [collection[i:i + COLS_PER_ROW] for i in range(0, len(collection), COLS_PER_ROW)]

    for row in rows:
        cols = st.columns(COLS_PER_ROW)
        for col, entry in zip(cols, row):
            with col:
                badge_color = CONDITION_COLORS.get(entry["condition"], "#9E9E9E")
                img_url = entry.get("image_url") or ""
                if img_url:
                    st.image(img_url, use_container_width=True)
                else:
                    st.markdown(
                        "<div style='height:140px;background:#1a1a2e;border:1px solid #333;"
                        "border-radius:8px;display:flex;align-items:center;"
                        "justify-content:center;color:#555;font-size:0.7rem;'>No image</div>",
                        unsafe_allow_html=True,
                    )
                st.markdown(
                    f"<div style='font-size:0.65rem;line-height:1.4;margin-top:4px;'>"
                    f"<strong style='color:#FFDE00;'>{entry['card_name']}</strong><br>"
                    f"<span style='color:#aaa;'>{entry['set_name']}</span><br>"
                    f"<span style='background:{badge_color};color:#000;padding:1px 5px;"
                    f"border-radius:3px;font-size:0.55rem;'>{entry['condition']}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if st.button("Remove", key=f"rm_{entry['id']}", use_container_width=True):
                    remove_from_collection(user_id, entry["id"])
                    st.rerun()

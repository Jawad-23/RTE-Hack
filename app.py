"""Croptions: Streamlit entry point with the top bar, page navigation and the assistant dialog. Owned by Me.

Run with:  streamlit run app.py
Pages live in views/ (not pages/, so Streamlit does not add its own sidebar menu).
"""

import streamlit as st

from i18n import t
from planner import chat_ui
from ui import components as ui
from ui import state
from ui.theme import css

st.set_page_config(page_title="Croptions", page_icon="assets/logo.svg", layout="wide", initial_sidebar_state="collapsed")
state.init()
lang = state.lang()
st.markdown(css(lang), unsafe_allow_html=True)

PAGES = {
    "home": st.Page("views/home.py", title=t("nav_home", lang), url_path="home", default=True),
    "plan": st.Page("views/plan.py", title=t("nav_plan", lang), url_path="plan"),
    "results": st.Page("views/results.py", title=t("nav_results", lang), url_path="results"),
    "compare": st.Page("views/compare.py", title=t("nav_compare", lang), url_path="compare"),
    "operate": st.Page("views/operate.py", title=t("nav_operate", lang), url_path="kit"),
    "assumptions": st.Page("views/assumptions.py", title=t("nav_settings", lang), url_path="assumptions"),
}
# Kit simulator for demos: not in any menu, reached only by the link in the README ("Try the Croptions Kit").
REMOTE = st.Page("views/kit_remote.py", title=t("kit_remote_nav", lang), url_path="kit-simulator")
MENU_ICONS = {"home": "🏠", "plan": "📍", "results": "📊", "compare": "⚖️", "operate": "🌡️", "assumptions": "📋"}
st.session_state["_pages"] = PAGES
current = st.navigation([*PAGES.values(), REMOTE], position="hidden")
if current.url_path == REMOTE.url_path:  # simulator screen: no top bar, no assistant
    current.run()
    st.stop()

# ---------- top bar ----------
with st.container(key="topbar"):
    # Home, Plan and Results are always visible; the menu holds every page, including the Kit and Compare sites.
    nav_ratios = [1.35, 0.75, 0.7, 0.9, 1.55, 1.05, 0.9, 1.55, 1.45]
    cols = st.columns(nav_ratios, vertical_alignment="center")
    cols[0].markdown(ui.brand(lang), unsafe_allow_html=True)
    for col, key in zip(cols[1:4], ("home", "plan", "results")):
        col.page_link(PAGES[key], label=PAGES[key].title)
    cols[4].page_link(PAGES["operate"], label=f"✦ {PAGES['operate'].title}")
    with cols[5].popover(f"☰ {t('menu', lang)}", use_container_width=True):
        st.markdown(f'<div class="cr-eyebrow">{t("menu_sub", lang)}</div>', unsafe_allow_html=True)
        for key in PAGES:
            st.page_link(PAGES[key], label=PAGES[key].title, icon=MENU_ICONS[key])
    if cols[7].button(f"● {t('chat_open', lang)}", key="ask_top", type="primary", use_container_width=True):
        state.open_chat()
    cols[8].segmented_control(
        t("language", lang), options=["en", "ar"], format_func=lambda x: "English" if x == "en" else "العربية",
        key=state.bind("lang"), on_change=state.save, args=("lang",), label_visibility="collapsed",
    )


# ---------- assistant dialog ----------
def _close_chat():
    st.session_state["chat_open"] = False


@st.dialog(t("bot_name", lang), width="large", on_dismiss=_close_chat)
def assistant():
    chat_ui.render(st.session_state.get("plan"), lang, preset=st.session_state.pop("chat_preset", None))


current.run()

if st.session_state.get("chat_open"):
    assistant()

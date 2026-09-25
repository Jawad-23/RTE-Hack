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
    "assumptions": st.Page("views/assumptions.py", title=t("nav_settings", lang), url_path="assumptions"),
}
st.session_state["_pages"] = PAGES
current = st.navigation(list(PAGES.values()), position="hidden")

# ---------- top bar ----------
with st.container(key="topbar"):
    cols = st.columns([1.35, 0.72, 0.62, 0.85, 1.35, 1.2, 0.6, 1.45, 1.55], vertical_alignment="center")
    cols[0].markdown(ui.brand(lang), unsafe_allow_html=True)
    for col, key in zip(cols[1:6], PAGES):
        col.page_link(PAGES[key], label=PAGES[key].title)
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

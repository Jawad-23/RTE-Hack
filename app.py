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
MENU_ICONS = {"home": ":material/home:", "plan": ":material/add_location_alt:", "results": ":material/insights:",
              "compare": ":material/compare_arrows:", "operate": ":material/sensors:", "assumptions": ":material/fact_check:"}
st.session_state["_pages"] = PAGES
current = st.navigation([*PAGES.values(), REMOTE], position="hidden")
if current.url_path == REMOTE.url_path:  # simulator screen: no top bar, no assistant
    current.run()
    st.stop()

# ---------- top bar: brand, Home, Plan, then the menu (every page), the assistant and the language ----------
MENU_GROUPS = [("menu_g_plan", ["home", "plan", "results"]), ("menu_g_operate", ["operate", "compare"]), ("menu_g_data", ["assumptions"])]
if st.session_state.get("_last_page") != current.url_path:  # a new page closes the menu
    st.session_state["nav_menu"] = False
    st.session_state["_last_page"] = current.url_path
with st.container(key="topbar"):
    cols = st.columns([1.5, 0.62, 0.62, 3.0, 1.05, 1.45, 1.1], vertical_alignment="center")
    cols[0].markdown(ui.brand(lang), unsafe_allow_html=True)
    cols[1].page_link(PAGES["home"], label=PAGES["home"].title)
    cols[2].page_link(PAGES["plan"], label=PAGES["plan"].title)
    with cols[4].popover(t("menu", lang), icon=":material/menu:", key="nav_menu", use_container_width=True):
        for group, keys in MENU_GROUPS:
            st.markdown(f'<div class="cr-menu-group">{t(group, lang)}</div>', unsafe_allow_html=True)
            for key in keys:
                label = PAGES[key].title + ("  ✦" if key == "operate" else "")
                st.page_link(PAGES[key], label=label, icon=MENU_ICONS[key], use_container_width=True)
    with cols[5]:
        if st.button(t("chat_open", lang), key="ask_top", type="primary", icon=":material/forum:", use_container_width=True):
            state.open_chat()
    cols[6].segmented_control(
        t("language", lang), options=["en", "ar"], format_func=lambda x: "EN" if x == "en" else "عربي",
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

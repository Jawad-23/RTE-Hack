"""Home: what Croptions does, what it checks, and the Croptions Kit, with a way into planning or a demo site. Owned by Me."""

import streamlit as st

from i18n import t
from planner.solar import load_settings
from ui import components as ui
from ui import state

lang = state.lang()
pages = st.session_state["_pages"]

left, right = st.columns([1.1, 1], gap="large", vertical_alignment="center")
with left:
    st.markdown(
        f"""<div class="cr-home-hero">
<span class="cr-pill soft">{t("l_eyebrow", lang)}</span>
<h1>{t("l_hero", lang)}</h1>
<p class="lead">{t("l_sub", lang)}</p></div>""",
        unsafe_allow_html=True,
    )
    b1, b2, _ = st.columns([1, 1.2, 0.6])
    if b1.button(f"{t('l_plan', lang)} →", type="primary", use_container_width=True):
        st.switch_page(pages["plan"])
    demo = state.demo_sites().iloc[0]
    if b2.button(t("l_demo", lang).format(site=demo["name_ar"] if lang == "ar" else demo["name_en"]), use_container_width=True):
        st.session_state["pin"] = (float(demo["lat"]), float(demo["lon"]))
        state.run_analysis()
        st.switch_page(pages["results"])
    st.markdown(f'<p class="cr-note" style="margin-top:8px">{t("l_oss", lang)} · {t("l_data", lang)}</p>', unsafe_allow_html=True)

with right:
    st.markdown(
        """<svg viewBox="0 0 520 420" width="100%" role="img" aria-label="Greenhouse under the desert sun" style="border-radius:24px;background:#EFE8DA">
  <defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F7EAD0"/><stop offset="1" stop-color="#EFE8DA"/></linearGradient></defs>
  <rect width="520" height="420" rx="24" fill="url(#sky)"/>
  <circle cx="390" cy="110" r="54" fill="#E9B92F"/><circle cx="390" cy="110" r="78" fill="#E9B92F" opacity=".18"/>
  <path d="M0 300 C120 270 230 290 330 275 C420 262 470 280 520 272 L520 420 L0 420 Z" fill="#E6DDCB"/>
  <path d="M0 330 C150 305 300 330 520 310 L520 420 L0 420 Z" fill="#CFC3AA"/>
  <g transform="translate(95 205)">
    <path d="M0 110 L0 50 Q120 -20 240 50 L240 110 Z" fill="#E2EEF7" stroke="#1F5F8C" stroke-width="3"/>
    <path d="M60 110 L60 30 M120 110 L120 16 M180 110 L180 30" stroke="#1F5F8C" stroke-width="2" opacity=".5"/>
    <rect x="-6" y="108" width="252" height="8" rx="3" fill="#1E5B3F"/>
    <g fill="#1E5B3F"><circle cx="30" cy="96" r="8"/><circle cx="90" cy="96" r="8"/><circle cx="150" cy="96" r="8"/><circle cx="210" cy="96" r="8"/></g>
  </g>
  <g transform="translate(360 250)"><rect x="0" y="0" width="120" height="44" rx="4" fill="#1E5B3F" transform="skewX(-18)"/>
    <path d="M10 4 L4 40 M40 4 L34 40 M70 4 L64 40 M100 4 L94 40" stroke="#EBDDBF" stroke-width="1.5" transform="skewX(-18)"/>
    <rect x="40" y="44" width="6" height="40" fill="#5E6558"/></g>
</svg>""",
        unsafe_allow_html=True,
    )

st.write("")
cols = st.columns(3, gap="medium")
for i, col in enumerate(cols, start=1):
    col.markdown(
        f'<div class="cr-value"><div class="n">{i}</div><h3>{t(f"v{i}", lang)}</h3><p>{t(f"v{i}t", lang)}</p></div>',
        unsafe_allow_html=True,
    )

# ---------- what the planner checks ----------
st.write("")
st.markdown(f'<div class="cr-section-head"><span class="cr-pill soft">{t("h_feat_eyebrow", lang)}</span><h2>{t("h_feat_title", lang)}</h2></div>',
            unsafe_allow_html=True)
cols = st.columns(3, gap="medium")
for col, (icon, key) in zip(cols, (("🛰", "h_f1"), ("🌱", "h_f2"), ("📈", "h_f3"))):
    col.markdown(f'<div class="cr-feature"><div class="ic">{icon}</div><h3>{t(key, lang)}</h3><p>{t(key + "t", lang)}</p></div>',
                 unsafe_allow_html=True)

# ---------- the Croptions Kit ----------
st.write("")
cfg = load_settings()
with st.container(key="kit_home"):
    st.markdown(ui.kit_pitch(lang, cfg["kit_pod_price_qar"], cfg["kit_service_qar_year"], pod_area_m2=cfg["kit_pod_area_m2"]),
                unsafe_allow_html=True)
    area = state.n0(cfg["kit_pod_area_m2"])
    steps = "".join(f'<div class="s"><b>{i}</b><div><h4>{t(f"h_k{i}", lang)}</h4><p>{t(f"h_k{i}t", lang).format(area=area)}</p></div></div>'
                    for i in (1, 2, 3))
    st.markdown(f'<div class="cr-kit-steps">{steps}</div>', unsafe_allow_html=True)
    k1, k2, _ = st.columns([1, 1, 2])
    if k1.button(f"{t('h_kit_cta', lang)} →", type="primary", use_container_width=True, key="home_kit"):
        st.switch_page(pages["operate"])
    if k2.button(t("l_plan", lang), use_container_width=True, key="home_plan2"):
        st.switch_page(pages["plan"])

# ---------- open data behind every number ----------
st.markdown(f'<p class="cr-note" style="text-align:center;margin-top:24px">{t("h_data", lang)}</p>', unsafe_allow_html=True)

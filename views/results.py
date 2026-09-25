"""Results: the recommendation, key numbers, crop calendar, setup comparison and charts. Owned by Me.

Every number on this page comes from the plan or from ui/insights.py, which summarises the planner's physics.
"""

import json

import pandas as pd
import streamlit as st

from i18n import t
from planner.schemas import SETUPS
from ui import charts, insights, state
from ui import components as ui
from ui.theme import PLOTLY_CONFIG

lang = state.lang()
ss = st.session_state
pages = ss["_pages"]
plan = ss.get("plan")

if not plan:
    st.markdown(f'<div class="cr-card" style="margin-top:24px"><p class="cr-title">{t("r_empty", lang)}</p>'
                f'<p class="cr-sub">{t("r_empty_sub", lang)}</p></div>', unsafe_allow_html=True)
    if st.button(f"{t('l_plan', lang)} →", type="primary"):
        st.switch_page(pages["plan"])
    st.stop()

inp, rec = plan["inputs"], plan.get("recommended")
lat, lon = inp["lat"], inp["lon"]
crop = insights.focus_crop(plan)

# ---------- header ----------
h1, h2 = st.columns([1.4, 1.6], vertical_alignment="bottom")
h1.markdown(
    f'<div class="cr-eyebrow">{t("results_for", lang)}</div>'
    f'<div style="font-size:24px;font-weight:600">{state.site_name(lat, lon, lang) or t("p_pinned", lang)}</div>'
    f'<div class="cr-mono">{state.coords(lat, lon)}</div>',
    unsafe_allow_html=True,
)
with h2:
    b1, b2, b3 = st.columns([1, 0.8, 1.35])
    b1.download_button(t("download_plan", lang), data=json.dumps(plan, ensure_ascii=False, indent=2),
                       file_name=f"croptions-plan-{lat:.2f}-{lon:.2f}.json", mime="application/json", use_container_width=True)
    with b2.popover(t("share", lang), use_container_width=True):
        st.caption(t("share_hint", lang))
        base = (st.context.url or "").split("?")[0]
        st.code(base + "?" + "&".join(f"{k}={v}" for k, v in st.query_params.items()), language=None)
    if b3.button(f"{t('compare_other', lang)} →", type="primary", use_container_width=True):
        st.switch_page(pages["compare"])

# ---------- recommendation ----------
summary = t("run_summary", lang).format(area=state.n0(inp["area_m2"]), budget=state.n0(inp["budget_qar"]), priority=t(f"pr_{inp['priority']}", lang))
if rec:
    verdict = t("verdict", lang).format(crop=state.crop_in_sentence(rec["crop"], lang), setup=t(f"setupv_{rec['setup']}", lang))
    pay = t("verdict_pay", lang).format(years=state.n1(rec["payback_years"])) if rec["payback_years"] is not None else t("verdict_nopay", lang)
    with st.container(key="hero"):
        st.markdown(
            f'<div class="cr-hero-label">{t("recommendation", lang)} <span class="cr-pill sand">✓ {t("calc_badge", lang)}</span></div>'
            f'<div class="cr-verdict">{verdict} <em>{pay}</em></div><div class="cr-run">{summary}</div>',
            unsafe_allow_html=True,
        )
        c1, c2, _ = st.columns([0.7, 1, 3])
        if c1.button(t("ask_why", lang), type="primary", use_container_width=True):
            state.open_chat(t("suggest_why", lang))
            st.rerun()
        c2.markdown(f'<a href="#setup-comparison" style="display:inline-block;border:1px solid rgba(255,253,248,.35);color:#FFFDF8;'
                    f'border-radius:10px;padding:10px 18px;min-height:44px;font-weight:600;text-decoration:none;white-space:nowrap">{t("see_setups", lang)}</a>',
                    unsafe_allow_html=True)
else:
    with st.container(key="hero_none"):
        st.markdown(
            f'<div class="cr-hero-label" style="color:#E8D9CF">{t("recommendation", lang)}</div>'
            f'<div class="cr-verdict">{t("none_title", lang)}</div>'
            f'<div class="cr-run" style="color:#E8D9CF">{t(insights.no_recommendation_key(plan), lang)} · {summary}</div>',
            unsafe_allow_html=True,
        )

if not plan.get("options"):
    st.error(plan.get("reason", ""))
    st.stop()

# ---------- key numbers ----------
if rec:
    limit = insights.crop_limit(plan, rec["crop"])
    st.markdown(ui.tiles([
        {"k": t("k_cov", lang), "v": f"{rec['coverage_pct']:.0f}", "unit": "%",
         "note": t("k_cov_n", lang).format(limit=f"{limit:.0f}", crop=state.crop_label(rec["crop"], lang).lower() if lang == "en" else state.crop_label(rec["crop"], lang))},
        {"k": t("k_cost", lang), "v": state.n0(rec["capex_qar"]), "unit": t("qar", lang),
         "note": t("k_cost_n_solar" if rec["solar_kw"] > 0 else "k_cost_n", lang)},
        {"k": t("k_profit", lang), "v": state.n0(rec["profit_qar_year"]), "unit": t("qar", lang), "note": t("k_profit_n", lang)},
        {"k": t("k_pay", lang), "v": state.n1(rec["payback_years"]), "unit": t("years", lang),
         "note": t("k_pay_n", lang).format(budget=state.n0(inp["budget_qar"]))},
        {"k": t("k_water", lang), "v": state.n0(rec["water_l_day"]), "unit": t("lday", lang), "note": t("k_water_n", lang), "water": True},
        {"k": t("k_solar", lang), "v": state.n1(rec["solar_kw"]), "unit": t("kw", lang),
         "note": t("k_solar_n" if rec["solar_kw"] > 0 else "k_solar_none", lang)},
    ]), unsafe_allow_html=True)
st.markdown(f'<div class="cr-banner">⚠ {t("estimate_banner", lang)}</div>', unsafe_allow_html=True)

# ---------- crop calendar ----------
with st.container(key="card_calendar"):
    a, b = st.columns([1.3, 1], vertical_alignment="center")
    a.markdown(ui.title(t("cal_title", lang), t("cal_sub", lang)), unsafe_allow_html=True)
    b.markdown(f'<div style="display:flex;justify-content:flex-start">{ui.legend_status(lang)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="overflow-x:auto">{ui.calendar(plan["calendar"], rec["crop"] if rec else inp.get("crop"), lang)}</div>',
                unsafe_allow_html=True)

# ---------- setup comparison ----------
options = insights.crop_options(plan, crop)
st.markdown('<div id="setup-comparison"></div>', unsafe_allow_html=True)
with st.container(key="card_compare"):
    st.markdown(ui.title(t("cmp_title", lang), t("cmp_sub", lang).format(crop=state.crop_label(crop, lang), area=state.n0(inp["area_m2"]))),
                unsafe_allow_html=True)
    st.markdown(ui.comparison(options, rec, lang), unsafe_allow_html=True)

# ---------- charts ----------
climate_df = state.climate_for(lat, lon)
limit = insights.crop_limit(plan, crop)
crop_info = next(c for c in plan["assumptions"]["crops"] if c["crop"] == crop)
monthly = insights.monthly_inside_max(climate_df, inp["area_m2"], crop_info)
with st.container(key="card_temp"):
    st.markdown(ui.title(t("temp_title", lang), t("temp_sub", lang)), unsafe_allow_html=True)
    st.plotly_chart(charts.inside_temperature(monthly, limit, state.crop_label(crop, lang), lang), use_container_width=True, config=PLOTLY_CONFIG)
    cool_all_year = [state.setup_label(s, lang) for s in SETUPS if not insights.months_above(monthly[s], limit)]
    pad_hot = insights.months_above(monthly["wet_pad"], limit)
    parts = [t("temp_cap_ok", lang).format(setups="، ".join(cool_all_year) if lang == "ar" else ", ".join(cool_all_year), limit=f"{limit:.0f}")
             if cool_all_year else t("temp_cap_none", lang).format(limit=f"{limit:.0f}")]
    if pad_hot:
        parts.append(t("temp_cap_pad", lang).format(months=", ".join(ui.MONTHS[lang][m - 1] for m in pad_hot)))
    st.markdown(f'<p class="cr-note">{" ".join(parts)} {t("temp_cap_note", lang)}</p>', unsafe_allow_html=True)

left, right = st.columns(2, gap="medium")
chiller = next((o for o in options if o["setup"] == "chiller"), None)
with left, st.container(key="card_day"):
    if chiller and chiller["solar_kw"] > 0:
        day = insights.hottest_day(climate_df, inp["area_m2"], chiller["solar_kw"])
        st.markdown(ui.title(t("solar_title", lang), t("solar_sub", lang).format(month=ui.MONTHS[lang][day["month"] - 1], kw=state.n1(chiller["solar_kw"]))),
                    unsafe_allow_html=True)
        st.plotly_chart(charts.summer_day(day, lang), use_container_width=True, config=PLOTLY_CONFIG)
        st.markdown(f'<p class="cr-note">{t("solar_cap", lang).format(solar=state.n0(day["solar_day_kwh"]), cooling=state.n0(day["cooling_day_kwh"]))}</p>',
                    unsafe_allow_html=True)
    else:
        st.markdown(ui.title(t("solar_title", lang), t("solar_none", lang)), unsafe_allow_html=True)
with right, st.container(key="card_profit"):
    st.markdown(ui.title(t("profit_title", lang), t("profit_sub", lang)), unsafe_allow_html=True)
    st.plotly_chart(charts.cumulative_profit(options, rec, lang), use_container_width=True, config=PLOTLY_CONFIG)
    best = max((o for o in options if o["profit_10y_qar"] is not None), key=lambda o: o["profit_10y_qar"], default=None)
    if best:
        st.markdown(f'<p class="cr-note">{t("profit_cap", lang).format(setup=state.setup_label(best["setup"], lang), p10=state.n0(best["profit_10y_qar"]))}</p>',
                    unsafe_allow_html=True)

# ---------- assumptions and sources ----------
st.subheader(t("diagnostics_title", lang))
st.caption(t("diagnostics_note", lang))
diagnostic_cols = ["setup", "light_ok_pct", "dli_mean_mol_m2_day", "vpd_stress_hours", "inside_rh_mean_pct", "grid_kwh_year", "export_kwh_year"]
diagnostics = pd.DataFrame(options).reindex(columns=diagnostic_cols)
diagnostics["setup"] = diagnostics["setup"].map(lambda s: state.setup_label(s, lang))
diagnostics = diagnostics.rename(columns={k: t("diag_" + k, lang) for k in diagnostic_cols})
st.dataframe(diagnostics, hide_index=True)
with st.expander(t("failure_reasons", lang)):
    for option in options:
        if option["fail_reasons"]:
            st.write(state.setup_label(option["setup"], lang) + ": " + "; ".join(option["fail_reasons"]))

left, right = st.columns(2, gap="medium")
with left, st.container(key="card_assum"):
    st.markdown(ui.title(t("assumptions", lang), t("assum_sub", lang)), unsafe_allow_html=True)
    if st.button(f"{t('all_assum', lang)} →"):
        st.switch_page(pages["assumptions"])
    with st.expander(t("all_options", lang)):
        cols = ["crop", "setup", "coverage_pct", "capex_qar", "profit_qar_year", "payback_years", "profit_10y_qar", "water_l_day", "passes"]
        df = pd.DataFrame(plan["options"])[cols]
        df["crop"] = df["crop"].map(lambda c: state.crop_label(c, lang))
        df["setup"] = df["setup"].map(lambda s: state.setup_label(s, lang))
        st.dataframe(df, hide_index=True, use_container_width=True)
with right, st.container(key="card_sources"):
    st.markdown(ui.title(t("sources", lang), t("sources_sub", lang)) + ui.sources(plan, lang), unsafe_allow_html=True)

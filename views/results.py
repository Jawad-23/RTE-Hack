"""Results: the recommendation, the assistant's summary, the Croptions Kit, investment scenarios, site intelligence,
the crop calendar, setup comparison, an optional second site and charts. Owned by Me.

Every number on this page comes from the plan or from ui/insights.py, which summarises the planner's physics.
The assistant's summary is written last (into a slot near the top) so the rest of the page shows while it thinks.
"""

import json

import pandas as pd
import streamlit as st

from i18n import t
from planner import chat_ui, dust, optimizer
from planner.schemas import SETUPS
from planner.solar import load_settings
from ui import charts, insights, kit_ui, state
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
    b3.markdown(f'<a class="cr-linkbtn" href="#compare-sites">+ {t("cmp_add", lang)}</a>', unsafe_allow_html=True)

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

# ---------- assistant summary (filled at the end) + Croptions Kit spotlight ----------
chat_col, kit_col = st.columns([1.15, 1], gap="medium")
with chat_col:
    chat_slot = st.container(key="card_chat")
cfg = load_settings()
kit_cost = plan.get("kit") or {}
with kit_col, st.container(key="kit_spot"):
    st.markdown(ui.kit_pitch(lang, compact=True), unsafe_allow_html=True)
    if rec and kit_cost.get("capex_with_kit_qar") is not None:
        st.markdown(ui.tiles([
            {"k": t("kc_pods", lang), "v": str(kit_cost["pods"]), "unit": "",
             "note": t("kc_pods_n", lang).format(price=state.n0(kit_cost["kit_capex_qar"] / kit_cost["pods"]), area=state.n0(kit_cost["pod_area_m2"]))},
            {"k": t("kc_cost", lang), "v": state.n0(kit_cost["capex_with_kit_qar"]), "unit": t("qar", lang),
             "note": t("kc_cost_n", lang).format(plan=state.n0(rec["capex_qar"]), kit=state.n0(kit_cost["kit_capex_qar"]))},
            {"k": t("kc_pay", lang), "v": state.n1(kit_cost["payback_with_kit_years"]), "unit": t("years", lang),
             "note": t("kc_pay_n", lang).format(years=state.n1(rec["payback_years"]))},
        ]), unsafe_allow_html=True)
    last = kit_ui.latest(ss.get("_kit_code"))
    if last:
        st.markdown(f'<p class="cr-kit-live">● {t("kc_live", lang).format(leaf=state.n1(last["leaf_c"]), air=state.n1(last["air_c"]), rh=state.n0(last["rh_pct"]))}</p>',
                    unsafe_allow_html=True)
    if st.button(f"{t('kc_open', lang)} →", type="primary", use_container_width=True, key="kit_open"):
        st.switch_page(pages["operate"])
    st.markdown(f'<p class="cr-kit-note">{t("kc_note", lang)}</p>', unsafe_allow_html=True)

# ---------- investment scenarios ----------
fin = plan.get("finance") or {}
invest_options = insights.crop_options(plan, crop)
with st.container(key="card_invest"):
    st.markdown(ui.title(t("i_title", lang), t("i_sub", lang).format(crop=state.crop_label(crop, lang), years=fin.get("years", 10))),
                unsafe_allow_html=True)
    st.markdown(ui.investment(invest_options, rec, lang), unsafe_allow_html=True)
    if fin.get("basis") == "world_bank":
        basis = t("i_rate_wb", lang).format(rate=state.n1(fin["rate_pct"]), lending=state.n1(fin["lending_rate_pct"]), ly=fin["lending_rate_year"],
                                            inflation=state.n1(fin["inflation_pct"]), iy=fin["inflation_year"])
    else:
        basis = t("i_rate_fallback", lang).format(rate=state.n1(fin.get("rate_pct")))
    down_pct = f"{fin.get('price_down_pct', 20):.0f}"
    st.markdown(f'<p class="cr-note">{basis} {t("i_notes", lang).format(down=down_pct)}</p>', unsafe_allow_html=True)

# ---------- what NASA measured at this site ----------
site = plan.get("site") or {}
if "monthly_temp_max_mean_c" in site:
    def _v(key, fmt=state.n1):
        return fmt(site.get(key))

    hot = site["hottest_month"]
    focus_limit = insights.crop_limit(plan, crop)
    focus = next((c for c in plan["assumptions"]["crops"] if c["crop"] == crop), {})
    peak_et0 = max(site["monthly_et0_mm_day"].items(), key=lambda kv: kv[1])
    nasa = next((s for s in plan.get("sources", []) if "NASA" in s.get("name", "")), {})
    years = nasa.get("years") or []
    with st.container(key="card_site"):
        st.markdown(ui.title(t("sc_title", lang), t("sc_sub", lang)), unsafe_allow_html=True)
        st.markdown(ui.tiles([
            {"k": t("sc_peak", lang), "v": _v("hottest_month_temp_max_mean_c"), "unit": "°C",
             "note": t("sc_peak_n", lang).format(month=ui.MONTHS[lang][hot - 1], max=state.n1(site.get("temp_max_c")))},
            {"k": t("sc_hours", lang), "v": state.n0((site.get("hours_above_limit_outdoor") or {}).get(crop)), "unit": t("sc_h_year", lang),
             "note": t("sc_hours_n", lang).format(crop=state.crop_label(crop, lang), limit=f"{focus_limit:.0f}")},
            {"k": t("sc_humid", lang), "v": state.n0(site.get("hottest_month_rh_mean_pct")), "unit": "%",
             "note": t("sc_humid_n", lang).format(wb=state.n1(site.get("hottest_month_wet_bulb_max_c")))},
            {"k": t("sc_sun", lang), "v": _v("peak_sun_hours_day"), "unit": t("sc_kwh_day", lang),
             "note": t("sc_sun_n", lang).format(year=state.n0(site.get("solar_kwh_m2_year")))},
            {"k": t("sc_dli", lang), "v": _v("dli_outdoor_mol_m2_day"), "unit": t("sc_mol", lang),
             "note": t("sc_dli_n", lang).format(crop=state.crop_label(crop, lang), need=state.n0(focus.get("dli_min_mol_m2_day")))},
            {"k": t("sc_ir", lang), "v": _v("heat_share_pct", state.n0), "unit": "%", "note": t("sc_ir_n", lang)},
            {"k": t("sc_haze", lang), "v": _v("haze_loss_pct", state.n0), "unit": "%", "note": t("sc_haze_n", lang)},
            {"k": t("sc_et0", lang), "v": _v("et0_mm_day"), "unit": t("sc_mm_day", lang),
             "note": t("sc_et0_n", lang).format(month=ui.MONTHS[lang][int(peak_et0[0]) - 1], mm=state.n1(peak_et0[1]))},
        ]), unsafe_allow_html=True)
        c1, c2 = st.columns(2, gap="medium")
        c1.plotly_chart(charts.site_temperature(site, focus_limit, state.crop_label(crop, lang), lang), use_container_width=True, config=PLOTLY_CONFIG)
        c2.plotly_chart(charts.site_humidity(site, lang), use_container_width=True, config=PLOTLY_CONFIG)
        span = f"{min(years)}–{max(years)}" if years else "—"
        st.markdown(f'<p class="cr-note">{t("sc_source", lang).format(years=span, date=nasa.get("fetched") or "—")}</p>',
                    unsafe_allow_html=True)
        if site.get("missing"):
            st.caption(" · ".join(site["missing"]))

# ---------- sun, heat and humidity from satellites, maps and forecasts ----------
gis, fc = plan.get("solar_gis") or {}, plan.get("forecast") or {}
if gis.get("available") or fc.get("available"):
    with st.container(key="card_gis"):
        st.markdown(ui.title(t("gis_title", lang), t("gis_sub", lang)), unsafe_allow_html=True)
        left, right = st.columns(2, gap="medium")
        if gis.get("available"):
            with left:
                st.markdown(ui.tiles([
                    {"k": t("gis_yield", lang), "v": state.n0(gis["kwh_per_kw_year"]), "unit": t("gis_yield_u", lang),
                     "note": t("gis_yield_n", lang).format(years=gis["years"])},
                    {"k": t("gis_heat", lang), "v": state.n1(gis["heat_loss_pct"]), "unit": "%", "note": t("gis_heat_n", lang)},
                    {"k": t("gis_tilt", lang), "v": str(gis["tilt_deg"]), "unit": "°",
                     "note": t("gis_tilt_n", lang).format(az=gis.get("bearing_deg", (gis["azimuth_deg"] + 180) % 360), elev=state.n0(gis["elevation_m"]))},
                ]), unsafe_allow_html=True)
                st.plotly_chart(charts.solar_months(gis["monthly_kwh_per_kw"], lang), use_container_width=True, config=PLOTLY_CONFIG)
                st.markdown(f'<p class="cr-note">{t("gis_src", lang)}</p>', unsafe_allow_html=True)
        if fc.get("available"):
            with right:
                limit_c = insights.crop_limit(plan, crop)
                hot_days = sum(1 for d in fc["days"] if d["temp_max_c"] is not None and d["temp_max_c"] > limit_c)
                uv = max((d["uv_max"] for d in fc["days"] if d["uv_max"] is not None), default=None)
                st.markdown(ui.tiles([
                    {"k": t("fc_hot", lang), "v": str(hot_days), "unit": t("fc_of7", lang),
                     "note": t("fc_hot_n", lang).format(crop=state.crop_label(crop, lang), limit=f"{limit_c:.0f}")},
                    {"k": t("fc_uv", lang), "v": state.n1(uv), "unit": "", "note": t("fc_uv_n", lang)},
                ]), unsafe_allow_html=True)
                st.plotly_chart(charts.forecast_week(fc["days"], limit_c, lang), use_container_width=True, config=PLOTLY_CONFIG)
                st.markdown(f'<p class="cr-note">{t("fc_src", lang)}</p>', unsafe_allow_html=True)
        d1, d2 = st.columns([1, 3], vertical_alignment="center")
        if d1.button(t("dust_fetch", lang), key="dust_btn", use_container_width=True):
            with st.spinner(t("dust_fetch", lang)):
                ss["_dust_exposure"] = (lat, lon, dust.recent_exposure(lat, lon))
        saved = ss.get("_dust_exposure")
        if saved and saved[:2] == (lat, lon):
            e = saved[2]
            d2.markdown(f'<p class="cr-note">{t("dust_line", lang).format(mean=state.n0(e["mean_ug_m3"]), n=e["event_hours"], total=e["valid_hours"])}</p>'
                        if e["available"] else f'<p class="cr-note">{t("dust_unavailable", lang)}</p>', unsafe_allow_html=True)
        else:
            d2.markdown(f'<p class="cr-note">{t("dust_note", lang)}</p>', unsafe_allow_html=True)

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

# ---------- compare with another site (optional) ----------
st.markdown('<div id="compare-sites"></div>', unsafe_allow_html=True)
with st.container(key="card_addsite"):
    st.markdown(ui.title(t("cmp_add_title", lang), t("cmp_add_sub", lang)), unsafe_allow_html=True)
    demos = state.demo_sites()
    others = [r for r in demos.itertuples() if abs(r.lat - lat) > 0.01 or abs(r.lon - lon) > 0.01]
    c1, c2, c3 = st.columns([1.6, 0.8, 0.9], vertical_alignment="bottom")
    pick = c1.selectbox(t("c_site_b", lang), range(len(others)), key="_add_site",
                        format_func=lambda i: f"{others[i].name_ar if lang == 'ar' else others[i].name_en} · {state.coords(others[i].lat, others[i].lon)}")
    if c2.button(f"+ {t('cmp_add_btn', lang)}", type="primary", use_container_width=True) and others:
        o = others[pick]
        with st.spinner(t("a_title", lang)):
            other = optimizer.plan(float(o.lat), float(o.lon), inp["area_m2"], inp["budget_qar"], inp["priority"], inp.get("crop"),
                                   cleaning_interval_days=inp.get("cleaning_interval_days"))
        ss["results_compare"] = {"base": (lat, lon), "name": o.name_ar if lang == "ar" else o.name_en, "plan": other}
    if c3.button(t("cmp_full", lang), use_container_width=True):
        st.switch_page(pages["compare"])
    extra = ss.get("results_compare")
    if extra and extra["base"] == (lat, lon):
        def _verdict(p):
            r = p.get("recommended")
            if not r:
                return t("none_title", lang)
            pay = t("verdict_pay", lang).format(years=state.n1(r["payback_years"])) if r["payback_years"] is not None else t("verdict_nopay", lang)
            return t("verdict", lang).format(crop=state.crop_in_sentence(r["crop"], lang), setup=t(f"setupv_{r['setup']}", lang)) + " " + pay
        here_rh, there_rh = (plan["site"].get("hottest_month_rh_mean_pct") or 0), (extra["plan"]["site"].get("hottest_month_rh_mean_pct") or 0)
        a, b = st.columns(2, gap="medium")
        a.markdown(ui.site_card(state.site_name(lat, lon, lang) or t("p_pinned", lang), t("cmp_this", lang), lat, lon, plan, None,
                                _verdict(plan), lang, here_rh > there_rh), unsafe_allow_html=True)
        xi = extra["plan"]["inputs"]
        b.markdown(ui.site_card(extra["name"], t("cmp_other_site", lang), xi["lat"], xi["lon"], extra["plan"], None,
                                _verdict(extra["plan"]), lang, there_rh > here_rh), unsafe_allow_html=True)
        if st.button(t("cmp_remove", lang), key="cmp_remove"):
            ss["results_compare"] = None
            st.rerun()

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

# ---------- assistant: summary first, then questions (last, so the page is already on screen) ----------
with chat_slot:
    st.markdown(ui.title(t("chat_card", lang), t("chat_card_sub", lang)), unsafe_allow_html=True)
    chat_ui.render(plan, lang, key="inline_chat", summary=True)

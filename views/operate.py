"""Croptions Kit: the Operate stage. Live (simulated) kit readings, the day simulator and recent dust. Owned by Me.

There is no hardware: a phone (views/kit_remote.py) or the buttons here send simulated readings built
from this site's NASA typical year. Everything on this page is labelled as a simulation.
"""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from i18n import t
from planner import crops, dust, kit, operate
from planner.solar import load_settings
from ui import charts, insights, kit_ui, state, theme
from ui import components as ui

lang = state.lang()
ss = st.session_state
st.markdown(f'<h1 style="font-size:32px;margin:8px 0 0">{t("kit_name", lang)}</h1><p class="cr-sub">{t("kit_sub", lang)}</p>',
            unsafe_allow_html=True)
plan = ss.get("plan")
if not plan or not plan.get("options"):
    st.write(t("r_empty", lang))
    if st.button(t("l_plan", lang)):
        st.switch_page(ss["_pages"]["plan"])
    st.stop()
inp = plan["inputs"]
weather = state.climate_for(inp["lat"], inp["lon"])
crop_table = crops.load_crops().set_index("crop")
cfg = load_settings()
live_tab, day_tab, dust_tab = st.tabs([t("kit_tab_live", lang), t("kit_tab_day", lang), t("dust_title", lang)])

# ======================= live kit =======================
focus = insights.focus_crop(plan)
rec = plan.get("recommended")
setup = rec["setup"] if rec else max(insights.crop_options(plan, focus), key=lambda o: o["coverage_pct"])["setup"]
crop = {"crop": focus, **crop_table.loc[focus].to_dict()}
site = state.site_name(inp["lat"], inp["lon"], "en") or state.coords(inp["lat"], inp["lon"])

with live_tab:
    st.markdown(f'<div class="cr-banner">⚠ {t("kit_sim_banner", lang)}</div>', unsafe_allow_html=True)
    pair, controls = st.columns([1, 1.6], gap="medium")
    with controls, st.container(key="card_kit_setup"):
        st.markdown(ui.title(t("kit_watching", lang).format(crop=state.crop_label(focus, lang), setup=state.setup_label(setup, lang)),
                             t("kit_watching_sub", lang)), unsafe_allow_html=True)
        sim_date = st.date_input(t("kit_date", lang), value=date.today(), key="_kit_date")
        sim_day = min(sim_date.timetuple().tm_yday, 365)
        st.segmented_control(t("kit_mode", lang), ["auto", "approve", "manual"], default="approve",
                             format_func=lambda m: t(f"kit_mode_{m}", lang), key="_kit_mode")
        st.caption(t(f"kit_mode_{ss.get('_kit_mode') or 'approve'}_n", lang))

    # one farm code per session; its context follows the plan, crop and date
    signature = (inp["lat"], inp["lon"], focus, setup, sim_day)
    try:
        day = kit.day_conditions(weather, setup, inp["area_m2"], crop, sim_day)
    except ValueError:
        day = None
    context = {"site": site, "lat": inp["lat"], "lon": inp["lon"], "crop": focus, "setup": setup, "sim_day": sim_day, "day": day}
    code = ss.get("_kit_code")
    if day is not None and (code is None or kit_ui.store().context(code) is None):
        code = ss["_kit_code"] = kit_ui.store().create(context)
    elif day is not None and ss.get("_kit_sig") != signature:
        kit_ui.store().set_context(code, context)
    ss["_kit_sig"] = signature
    ss.setdefault("_kit_seen", 0)
    ss.setdefault("_kit_log", [])
    ss.setdefault("_kit_events", [])
    ss.setdefault("_kit_screen", 0.0)

    with pair, st.container(key="card_kit_pair"):
        if day is None:
            st.warning(t("operate_missing", lang))
        else:
            url = kit_ui.remote_url(code, lang)
            st.markdown(f'<div class="cr-eyebrow">{t("kit_code", lang)}</div>'
                        f'<div style="font-size:40px;font-weight:700;letter-spacing:.12em;direction:ltr">{code}</div>',
                        unsafe_allow_html=True)
            qr = kit_ui.qr_data_uri(url) if url.startswith("http") else None
            if qr:
                st.markdown(f'<img src="{qr}" alt="QR" style="width:180px;max-width:100%;border-radius:12px;background:#fff">',
                            unsafe_allow_html=True)
            st.markdown(f'<p class="cr-note">{t("kit_scan", lang)}</p>', unsafe_allow_html=True)
            st.code(url, language=None)
            if kit_ui.is_local(url):
                st.caption(t("kit_local_note", lang))
            with st.expander(t("kit_no_phone", lang)):
                kit_ui.sender(code, context, lang, key="desk")

    def _event(seq, kind, **params):
        ss["_kit_events"] = (ss["_kit_events"] + [{"seq": seq, "kind": kind, **params}])[-40:]

    def _apply(pct, seq, kind):
        ss["_kit_screen"] = float(pct)
        ss["_kit_pending"] = None
        _event(seq, kind, pct=pct)

    @st.fragment(run_every=2)
    def live():
        mode = ss.get("_kit_mode") or "approve"
        new = kit_ui.store().readings(code, ss["_kit_seen"]) if code else []
        for r in new:
            d = kit.derive(r, crop, cfg)
            advice = kit.recommend(r, crop, ss["_kit_screen"], cfg)
            if advice["screen_pct"] != ss["_kit_screen"]:
                if mode == "auto":
                    _apply(advice["screen_pct"], r["seq"], "auto")
                elif mode == "approve":
                    ss["_kit_pending"] = {**advice, "seq": r["seq"]}
            elif mode == "approve":
                ss["_kit_pending"] = None
            for a in d["alerts"]:  # log an alert when it starts, not on every reading while it lasts
                if a not in ss.get("_kit_active", ()):
                    _event(r["seq"], a)
            ss["_kit_active"] = tuple(d["alerts"])
            ss["_kit_log"] = (ss["_kit_log"] + [{**{k: r.get(k) for k in kit.READING_KEYS}, **{k: v for k, v in d.items() if k != "alerts"},
                              "alerts": " ".join(d["alerts"]), "advised_screen_pct": advice["screen_pct"],
                              "advice_reason": advice["reason"], "screen_pct": ss["_kit_screen"], "mode": mode}])[-500:]
            ss["_kit_seen"] = r["seq"]

        log = ss["_kit_log"]
        if not log:
            st.markdown(f'<div class="cr-card"><p class="cr-title">{t("kit_waiting", lang)}</p>'
                        f'<p class="cr-sub">{t("kit_waiting_sub", lang)}</p></div>', unsafe_allow_html=True)
            return
        last = log[-1]
        received = t("kit_last", lang).format(n=last["seq"], at=last["sent_at"][11:19], hour=f"{last['sim_hour']:02d}:00",
                                              scenario=kit_ui.scenario_label(last["scenario"], lang))
        st.markdown(f'<p class="cr-note">📡 {received}</p>', unsafe_allow_html=True)
        light = kit.dli_so_far(log, last["sim_day"], cfg)
        st.markdown(ui.tiles([
            {"k": t("kit_leaf", lang), "v": state.n1(last["leaf_c"]), "unit": "°C",
             "note": t("kit_leaf_n", lang).format(limit=state.n0(crop["t_max_c"]))},
            {"k": t("kit_air", lang), "v": state.n1(last["air_c"]), "unit": "°C", "note": t("kit_air_n", lang)},
            {"k": t("kit_rh", lang), "v": state.n0(last["rh_pct"]), "unit": "%", "note": t("kit_rh_n", lang)},
            {"k": t("kit_par", lang), "v": state.n0(last["par_w_m2"]), "unit": "W/m²", "note": t("kit_par_n", lang)},
        ]), unsafe_allow_html=True)
        st.markdown(ui.tiles([
            {"k": t("kit_cwsi", lang), "v": "—" if last["cwsi"] is None else f"{last['cwsi']:.2f}", "unit": "",
             "note": t("kit_cwsi_n", lang).format(alert=f"{cfg['kit_cwsi_alert']:.2f}") if last["cwsi"] is not None else t("kit_cwsi_night", lang)},
            {"k": t("kit_vpd", lang), "v": f"{last['vpd_kpa']:.2f}", "unit": "kPa",
             "note": t("kit_vpd_n", lang).format(limit=f"{crop.get('vpd_max_kpa', float('nan')):.1f}")},
            {"k": t("kit_dew", lang), "v": state.n1(last["leaf_dew_gap_c"]), "unit": "°C",
             "note": t("kit_dew_n", lang).format(alert=state.n1(cfg["kit_dew_gap_alert_c"]))},
            {"k": t("kit_dli", lang), "v": state.n1(light), "unit": t("sc_mol", lang),
             "note": t("kit_dli_n", lang).format(need=state.n0(crop["dli_min_mol_m2_day"]))},
        ]), unsafe_allow_html=True)

        with st.container(key="card_kit_advice"):
            st.markdown(ui.title(t("kit_advice", lang)), unsafe_allow_html=True)
            now_pct, advised = ss["_kit_screen"], last["advised_screen_pct"]
            st.markdown(f'<p style="font-size:20px;font-weight:600;margin:0">{t("kit_screen_now", lang).format(now=f"{now_pct:.0f}", advised=f"{advised:.0f}")}</p>'
                        f'<p class="cr-note">{t("reason_" + last["advice_reason"], lang)}</p>', unsafe_allow_html=True)
            pending = ss.get("_kit_pending")
            if mode == "approve" and pending:
                a, b = st.columns(2)
                if a.button(t("kit_approve", lang).format(pct=f"{pending['screen_pct']:.0f}"), type="primary", use_container_width=True):
                    _apply(pending["screen_pct"], pending["seq"], "approved")
                    st.rerun(scope="fragment")
                if b.button(t("kit_dismiss", lang), use_container_width=True):
                    ss["_kit_pending"] = None
                    _event(pending["seq"], "dismissed")
                    st.rerun(scope="fragment")
            elif mode == "manual":
                pct = st.slider(t("operate_screen", lang), 0, int(cfg["screen_max_pct"]), int(now_pct), int(cfg["screen_step_pct"]),
                                format="%d%%", key="_kit_manual")
                if pct != now_pct:
                    _apply(pct, last["seq"], "manual")

        left, right = st.columns([1.1, 1], gap="medium")
        with left, st.container(key="card_kit_thermal"):
            st.markdown(ui.title(t("kit_thermal", lang), t("kit_thermal_sub", lang)), unsafe_allow_html=True)
            reading = {k: last[k] for k in ("leaf_c", "air_c", "par_w_m2")}
            st.plotly_chart(charts.thermal(kit.thermal_grid(reading, seed=last["seq"]), lang), use_container_width=True,
                            config=theme.PLOTLY_CONFIG, key="kit_thermal_chart")
        with right, st.container(key="card_kit_alerts"):
            st.markdown(ui.title(t("kit_alerts", lang)), unsafe_allow_html=True)
            events = ss["_kit_events"][::-1][:8]
            if not events:
                st.markdown(f'<p class="cr-note">{t("kit_no_alerts", lang)}</p>', unsafe_allow_html=True)
            for e in events:
                icon = "⚙" if e["kind"] in ("auto", "approved", "manual", "dismissed") else "⚠"
                text = t(f"kit_ev_{e['kind']}", lang).format(pct=f"{e.get('pct', 0):.0f}")
                st.markdown(f'<p style="margin:4px 0">{icon} <b>#{e["seq"]}</b> {text}</p>', unsafe_allow_html=True)

        with st.container(key="card_kit_trace"):
            st.markdown(ui.title(t("kit_trace", lang)), unsafe_allow_html=True)
            st.plotly_chart(charts.kit_trace(pd.DataFrame(log), lang), use_container_width=True, config=theme.PLOTLY_CONFIG,
                            key="kit_trace_chart")
            a, b = st.columns(2)
            a.download_button(t("kit_csv", lang), pd.DataFrame(log).to_csv(index=False), "croptions-kit-readings.csv", "text/csv",
                              use_container_width=True)
            if b.button(t("kit_clear", lang), use_container_width=True):
                ss.update(_kit_log=[], _kit_events=[], _kit_pending=None, _kit_screen=0.0, _kit_active=())
                st.rerun(scope="fragment")

    live()

# ======================= simulated day (typical-year weather) =======================
with day_tab:
    st.info(t("operate_banner", lang))
    crop_names = crop_table.index.tolist()
    selected = st.selectbox(t("p_crop", lang), crop_names, index=crop_names.index(focus), format_func=lambda c: state.crop_label(c, lang))
    sim = st.slider(t("operate_day", lang), 1, 365, 200)
    day_crop = crop_table.loc[selected].to_dict()
    try:
        frame = operate.simulate_day(weather, sim, day_crop, inp["area_m2"])
    except ValueError:
        frame = None
        st.warning(t("operate_missing", lang))
    if frame is not None:
        signature = (inp["lat"], inp["lon"], selected, sim, inp["area_m2"])
        if ss.get("_operate_signature") != signature:
            ss.update(_operate_signature=signature, _operate_tick=0, _operate_play=False)
        play, reset, download = st.columns(3)
        if play.button(t("operate_pause" if ss.get("_operate_play") else "operate_play", lang)):
            ss["_operate_play"] = not ss.get("_operate_play", False)
            st.rerun()
        if reset.button(t("operate_reset", lang)):
            ss.update(_operate_tick=0, _operate_play=False)
            st.rerun()
        download.download_button(t("operate_csv", lang), frame.to_csv(index=False), "croptions-simulation.csv", "text/csv")

        @st.fragment(run_every=0.5 if ss.get("_operate_play") else None)
        def playback():
            tick = ss.get("_operate_tick", 0)
            row = frame.iloc[tick]
            st.subheader(row["time"])
            a, b, c = st.columns(3)
            a.metric(t("operate_fixed", lang), f"{row['fixed_inside_c']:.1f} °C")
            b.metric(t("operate_smart", lang), f"{row['smart_inside_c']:.1f} °C")
            c.metric(t("operate_screen", lang), f"{row['screen_pct']:.0f}%")
            st.caption(t("reason_" + row["reason"], lang))
            fig = go.Figure()
            for key, label, colour in (("fixed_inside_c", "operate_fixed", theme.SKY), ("smart_inside_c", "operate_smart", theme.GREEN)):
                fig.add_scatter(x=frame["time"].iloc[:tick + 1], y=frame[key].iloc[:tick + 1], name=t(label, lang), line_color=colour)
            fig.update_layout(**theme.plotly_layout(lang))
            fig.update_xaxes(tickmode="array", tickvals=["00:00", "06:00", "12:00", "18:00", "23:50"])
            fig.update_yaxes(title="°C")
            st.plotly_chart(fig, use_container_width=True, config=theme.PLOTLY_CONFIG)
            if ss.get("_operate_play"):
                if tick < len(frame) - 1:
                    ss["_operate_tick"] = tick + 1
                else:
                    ss["_operate_play"] = False
                    st.rerun()

        playback()
        with st.expander(t("operate_data", lang)):
            st.dataframe(frame, hide_index=True)

# ======================= recent dust =======================
with dust_tab:
    st.caption(t("dust_note", lang))
    if st.button(t("dust_fetch", lang)):
        with st.spinner(t("dust_fetch", lang)):
            ss["_dust_exposure"] = (inp["lat"], inp["lon"], dust.recent_exposure(inp["lat"], inp["lon"]))
    saved = ss.get("_dust_exposure")
    if saved and saved[:2] == (inp["lat"], inp["lon"]):
        exposure = saved[2]
        if exposure["available"]:
            st.metric(t("dust_mean", lang), f"{exposure['mean_ug_m3']} µg/m³")
            st.write(t("dust_hours", lang).format(n=exposure["event_hours"], total=exposure["valid_hours"]))
            st.caption(f"{exposure['start']} — {exposure['end']} UTC · CAMS / Open-Meteo")
            st.link_button("CAMS / Open-Meteo", exposure["source"])
        else:
            st.warning(t("dust_unavailable", lang))

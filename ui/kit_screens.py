"""Kit page: the farmer picks a screen (coated ETFE shade or dynamic aluminium-strip thermal screen) and gets
three evaluations: PAR:NIR spectrum, canopy heat and stress, predictive maintenance and hazard training. Owned by Me.

All numbers come from planner/screens.py (site NASA weather, the latest kit reading, the 7-day forecast and
data/screens.csv).
"""

from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from i18n import t
from planner import cooling, kit, screens
from ui import components as ui
from ui import kit_ui, state, theme

LEVEL_PILL = {"ok": "soft", "caution": "warn", "high": "bad", "danger": "bad"}
STEPS = 3  # briefing steps per hazard in i18n (haz_<code>_s1..s3)


def _spectrum_chart(sp: dict, lang: str) -> go.Figure:
    months = ui.MONTHS[lang]
    fig = go.Figure()
    for key, name, colour, dash in (("monthly_ratio_outside", "sp_out", theme.INK_MUTED, "dot"), ("monthly_ratio_inside", "sp_in", theme.GREEN, "solid")):
        fig.add_scatter(x=months, y=[sp[key].get(m) for m in range(1, 13)], name=t(name, lang), mode="lines+markers",
                        line=dict(color=colour, width=2.5, dash=dash), hovertemplate="%{x}: %{y:.2f}<extra></extra>")
    fig.update_layout(**theme.plotly_layout(lang, 260))
    fig.update_yaxes(title_text=t("sp_axis", lang))
    return fig


@st.cache_data(show_spinner=False, max_entries=16)
def _screen_moves_year(lat: float, lon: float, area_m2: float, crop: dict) -> int:
    """How many times the kit's controller moves a dynamic screen over the whole typical year (hourly steps)."""
    prof = cooling.hourly_profile(state.climate_for(lat, lon), "agrivoltaic_louver", area_m2, crop)
    return int((np.diff(prof["screen_pct"].to_numpy()) != 0).sum())


def render(plan: dict, climate_df: pd.DataFrame, crop: dict, code: str | None, sim_day: int, cfg: dict, lang: str) -> None:
    ss = st.session_state
    with st.container(key="card_screen_pick"):
        st.markdown(ui.title(t("scr_title", lang), t("scr_sub", lang)), unsafe_allow_html=True)
        choice = st.segmented_control(t("scr_pick", lang), list(screens.SCREENS), format_func=lambda s: t(f"scr_{s}", lang),
                                      key="_kit_screen_type", label_visibility="collapsed")
        if not choice:
            st.markdown(f'<p class="cr-note">{t("scr_choose", lang)}</p>', unsafe_allow_html=True)
            return
        s = screens.load_screens().loc[choice]
        st.markdown(f'<p class="cr-note">{t(f"scr_{choice}_n", lang)}</p>', unsafe_allow_html=True)
        closure = 100.0
        if s["movable"]:
            closure = float(st.slider(t("scr_closure", lang), 0, 100, int(ss.get("_kit_screen", 0) or 80), 10, format="%d%%",
                                      key=f"_scr_closure_{choice}", help=t("scr_closure_help", lang)))

    spec_tab, canopy_tab, maint_tab = st.tabs([t("scr_tab1", lang), t("scr_tab2", lang), t("scr_tab3", lang)])

    # ---------- 1. spectrum ratio of PAR to NIR ----------
    with spec_tab:
        sp = screens.spectrum(climate_df, choice, crop, closure, sim_day, cfg["par_umol_j"])
        need = sp["dli_need"]
        enough = np.isfinite(need) and sp["dli_inside"] >= need
        st.markdown(ui.tiles([
            {"k": t("sp_ratio", lang), "v": f'{state.n1(sp["ratio_outside"])} → {state.n1(sp["ratio_inside"])}', "unit": "",
             "note": t("sp_ratio_n", lang)},
            {"k": t("sp_par", lang), "v": state.n0(sp["par_kept_pct"]), "unit": "%", "note": t("sp_par_n", lang)},
            {"k": t("sp_nir", lang), "v": state.n0(sp["nir_blocked_pct"]), "unit": "%",
             "note": t("sp_nir_n", lang).format(kwh=state.n1(sp["nir_blocked_kwh_m2_day"]))},
            {"k": t("sp_dli", lang), "v": state.n1(sp["dli_inside"]), "unit": t("sc_mol", lang),
             "note": t("sp_dli_ok" if enough else "sp_dli_low", lang).format(need=state.n0(need), out=state.n1(sp["dli_outside"]))},
        ]), unsafe_allow_html=True)
        st.plotly_chart(_spectrum_chart(sp, lang), use_container_width=True, config=theme.PLOTLY_CONFIG, key="scr_spec_chart")
        verdict = "sp_v_better" if (sp["ratio_inside"] or 0) > (sp["ratio_outside"] or 0) * 1.2 else "sp_v_same"
        st.markdown(f'<p class="cr-note">{t(verdict, lang)} {t("sp_src", lang)}</p>', unsafe_allow_html=True)

    # ---------- 2. crop canopy heat and stress detection (updates with every reading) ----------
    with canopy_tab:
        @st.fragment(run_every=2)
        def canopy_live():
            reading = kit_ui.latest(code)
            if not reading:
                st.markdown(f'<p class="cr-note">{t("cn_wait", lang)}</p>', unsafe_allow_html=True)
                return
            d = kit.derive(reading, crop, cfg)
            grid = kit.thermal_grid(reading, seed=reading["seq"])
            c = screens.canopy(reading, d["cwsi"], grid, crop, choice, closure)
            band = c["band"]
            st.markdown(ui.tiles([
                {"k": t("cn_cwsi", lang), "v": "—" if c["cwsi"] is None else f'{c["cwsi"]:.2f}', "unit": "",
                 "note": t(f"cn_band_{band}", lang) if band else t("kit_cwsi_night", lang)},
                {"k": t("cn_hot", lang), "v": state.n0(c["hotspot_pct"]), "unit": "%",
                 "note": t("cn_hot_n", lang).format(limit=state.n0(c["limit_c"]))},
                {"k": t("cn_now", lang), "v": state.n1(c["leaf_now_c"]), "unit": "°C", "note": t("cn_now_n", lang).format(n=reading["seq"])},
                {"k": t("cn_under", lang), "v": state.n1(c["leaf_under_screen_c"]), "unit": "°C",
                 "note": t("cn_under_n", lang).format(cool=state.n1(c["cooling_c"]), screen=t(f"scr_{choice}", lang))},
            ]), unsafe_allow_html=True)
            key = "cn_v_fixed" if c["above_limit_now"] and not c["above_limit_under_screen"] else \
                  "cn_v_still" if c["above_limit_under_screen"] else "cn_v_ok"
            st.markdown(f'<p class="cr-note">{t(key, lang).format(screen=t(f"scr_{choice}", lang), limit=state.n0(c["limit_c"]))}</p>',
                        unsafe_allow_html=True)
        canopy_live()

    # ---------- 3. predictive maintenance and hazard training ----------
    with maint_tab:
        inp = plan["inputs"]
        dust = ss.get("_dust_exposure")
        dust = dust[2] if dust and dust[:2] == (inp["lat"], inp["lon"]) else None
        moves = _screen_moves_year(inp["lat"], inp["lon"], inp["area_m2"], crop) if s["movable"] else 0
        m = screens.maintenance(choice, cfg, moves, 365.0, dust)  # average moves a day over the typical year
        tiles = [
            {"k": t("mt_clean", lang), "v": state.n0(m["clean_every_days"]), "unit": t("mt_days", lang),
             "note": t("mt_clean_dust" if dust else "mt_clean_n", lang).format(x=state.n1(m["dust_multiplier"]), pct=state.n0(s["clean_trigger_loss_pct"]))},
            {"k": t("mt_age", lang), "v": state.n1(m["ageing_pct_year"]), "unit": t("mt_pct_year", lang),
             "note": t("mt_age_n", lang).format(five=state.n1(m["loss_at_5_years_pct"]), life=m["lifespan_years"])},
        ]
        if s["movable"]:
            tiles.append({"k": t("mt_moves", lang), "v": state.n0(m["moves_per_day"]), "unit": t("mt_per_day", lang),
                          "note": t("mt_service", lang).format(days=state.n0(m["service_in_days"]), cycles=state.n0(s["drive_service_cycles"]))})
        st.markdown(ui.tiles(tiles), unsafe_allow_html=True)

        st.markdown(ui.title(t("hz_title", lang), t("hz_sub", lang)), unsafe_allow_html=True)
        briefed = ss.setdefault("_kit_training", {}).setdefault(choice, {})
        items = screens.hazards(choice, plan.get("forecast"))
        for h in items:
            level, hc = h["level"], h["code"]
            value = "" if h["value"] is None else state.n1(h["value"])
            msg = t(f"hz_{hc}_m", lang).format(value=value, day=h.get("day") or "", limit=state.n0(h.get("limit")))
            steps = "".join(f"<li>{escape(t(f'hz_{hc}_s{i}', lang))}</li>" for i in range(1, STEPS + 1))
            st.markdown(f'<div class="cr-hazard"><div class="h"><b>{escape(t(f"hz_{hc}", lang))}</b>'
                        f'<span class="cr-pill {LEVEL_PILL[level]}">{escape(t(f"hz_lvl_{level}", lang))}</span></div>'
                        f'<p>{escape(msg)}</p><ol>{steps}</ol></div>', unsafe_allow_html=True)
            briefed[hc] = st.checkbox(t("hz_done", lang), value=briefed.get(hc, False), key=f"_brief_{choice}_{hc}")
        done = sum(bool(briefed.get(h["code"])) for h in items)
        st.progress(done / len(items), text=t("hz_progress", lang).format(done=done, total=len(items)))

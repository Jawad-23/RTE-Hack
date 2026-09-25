"""Streamlit app: map, inputs, results dashboard and chat. Owned by Me.

Run with:  streamlit run app.py
"""

from pathlib import Path

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from i18n import t
from planner import chat_ui, climate, cooling, crops, optimizer
from planner.schemas import PRIORITIES, STATUS

MAP_START = (25.3, 51.2)  # starting view only; any pin on Earth works
MAP_ZOOM = 8
PLOTLY_CONFIG = {"displayModeBar": False}  # cleaner on a projector
STATUS_COLORS = {"good": "#2e7d32", "risky": "#f9a825", "impossible": "#c62828"}

st.set_page_config(page_title="Farming the Desert Sun", page_icon="🌱", layout="wide")


# ---------- Sidebar: language and inputs ----------
lang = st.sidebar.radio("Language / اللغة", ["en", "ar"], format_func=lambda x: "English" if x == "en" else "العربية", horizontal=True)
if lang == "ar":
    st.markdown(f"<style>{Path('styles/rtl.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

area_m2 = st.sidebar.number_input(t("farm_size", lang), min_value=50, max_value=100_000, value=500, step=50)
budget_qar = st.sidebar.number_input(t("budget", lang), min_value=0, max_value=50_000_000, value=250_000, step=10_000)
crop_names = crops.load_crops()["crop"].tolist()
crop_choice = st.sidebar.selectbox(t("crop", lang), [None, *crop_names], format_func=lambda c: t("crop_any", lang) if c is None else c.replace("_", " "))
priority = st.sidebar.radio(t("priority", lang), PRIORITIES, format_func=lambda p: t(f"priority_{p}", lang))


# ---------- Header and map ----------
st.title(t("app_title", lang))
st.caption(t("app_subtitle", lang))

map_col, chat_col = st.columns([3, 2])
with map_col:
    st.write(t("map_hint", lang))
    pin = st.session_state.get("pin")
    fmap = folium.Map(location=pin or MAP_START, zoom_start=MAP_ZOOM)
    if pin:
        folium.Marker(pin).add_to(fmap)
    clicked = st_folium(fmap, height=420, use_container_width=True, returned_objects=["last_clicked"], key="map")
    if clicked and clicked.get("last_clicked"):
        new_pin = (round(clicked["last_clicked"]["lat"], 4), round(clicked["last_clicked"]["lng"], 4))
        if new_pin != pin:
            st.session_state["pin"] = new_pin
            st.rerun()

    # Fallback when the map can't load (offline venue Wi-Fi) or for exact coordinates.
    with st.expander(t("enter_coords", lang)):
        lat_in = st.number_input(t("latitude", lang), -90.0, 90.0, float((pin or MAP_START)[0]), format="%.4f")
        lon_in = st.number_input(t("longitude", lang), -180.0, 180.0, float((pin or MAP_START)[1]), format="%.4f")
        if st.button(t("use_coords", lang)):
            st.session_state["pin"] = (round(lat_in, 4), round(lon_in, 4))
            st.rerun()

    if pin:
        st.write(f"**{t('selected_site', lang)}:** {pin[0]:.4f}, {pin[1]:.4f}")
    if st.button(t("analyse", lang), type="primary", use_container_width=True):
        if not pin:
            st.warning(t("no_pin", lang))
        else:
            with st.spinner(t("analysing", lang)):
                st.session_state["plan"] = optimizer.plan(pin[0], pin[1], float(area_m2), float(budget_qar), priority, crop_choice)

with chat_col:
    chat_ui.render(st.session_state.get("plan"), lang)


# ---------- Results ----------
def setup_label(setup: str) -> str:
    return t(f"setup_{setup}", lang)


def fmt_qar(v) -> str:
    return "—" if v is None else f"{v:,.0f} QAR"


plan = st.session_state.get("plan")
if plan:
    st.divider()
    rec = plan["recommended"]
    if rec is None:
        st.error(f"**{t('no_recommendation', lang)}.** {plan['reason']}")
    else:
        st.subheader(f"{t('recommendation', lang)}: {setup_label(rec['setup'])} · {rec['crop'].replace('_', ' ')}")
        st.caption(plan["reason"])
        m = st.columns(3) + st.columns(3)
        m[0].metric(t("coverage", lang), f"{rec['coverage_pct']:.0f}%")
        m[1].metric(t("build_cost", lang), fmt_qar(rec["capex_qar"]))
        m[2].metric(t("profit_year", lang), fmt_qar(rec["profit_qar_year"]))
        m[3].metric(t("payback", lang), "—" if rec["payback_years"] is None else f"{rec['payback_years']:.1f} {t('years', lang)}")
        m[4].metric(t("solar_size", lang), f"{rec['solar_kw']:.1f} kW")
        m[5].metric(t("water_day", lang), f"{rec['water_l_day']:,.0f} L")
    st.caption(t("illustrative", lang))

    if plan["options"]:
        # Crop calendar heatmap
        st.subheader(t("crop_calendar", lang))
        cal = pd.DataFrame(plan["calendar"]).T
        cal = cal[[str(m) for m in range(1, 13)]]
        z = cal.map(STATUS.index).to_numpy()
        n = len(STATUS) - 1
        scale = [[i / n, STATUS_COLORS[s]] for i, s in enumerate(STATUS)]
        fig = go.Figure(go.Heatmap(
            z=z, x=list(range(1, 13)), y=[c.replace("_", " ") for c in cal.index], zmin=0, zmax=n,
            colorscale=scale, showscale=False, xgap=2, ygap=2,
            text=cal.map(lambda s: t(f"status_{s}", lang)).to_numpy(), hovertemplate="%{y} · %{x}: %{text}<extra></extra>",
        ))
        fig.update_layout(height=60 + 32 * len(cal), margin=dict(l=0, r=0, t=10, b=0), xaxis=dict(title=t("month", lang), dtick=1))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        # Comparison table
        st.subheader(t("comparison", lang))
        cols = ["crop", "setup", "coverage_pct", "growing_months", "capex_qar", "profit_qar_year", "payback_years", "profit_10y_qar", "solar_kw", "water_l_day", "passes"]
        table = pd.DataFrame(plan["options"])[cols]
        table["setup"] = table["setup"].map(setup_label)
        table["growing_months"] = table["growing_months"].map(len)
        st.dataframe(table, use_container_width=True, hide_index=True)

    if rec is not None:
        lat, lon = plan["inputs"]["lat"], plan["inputs"]["lon"]
        climate_df = climate.get_typical_year(lat, lon)
        prof = cooling.hourly_profile(climate_df, rec["setup"], plan["inputs"]["area_m2"])
        crop_limit = next(c["t_max_c"] for c in plan["assumptions"]["crops"] if c["crop"] == rec["crop"])
        uses_power = rec["solar_kw"] > 0
        c1, c2 = st.columns(2) if uses_power else (st.container(), None)

        # Inside vs outside daily maximum
        with c1:
            st.subheader(t("inside_temp_chart", lang))
            daily = prof.groupby(prof["hour_of_year"] // 24)[["outside_c", "inside_c"]].max()
            fig = go.Figure()
            fig.add_scatter(x=daily.index + 1, y=daily["outside_c"], name=t("outside", lang), line=dict(color="#c62828"))
            fig.add_scatter(x=daily.index + 1, y=daily["inside_c"], name=setup_label(rec["setup"]), line=dict(color="#1565c0"))
            fig.add_hline(y=crop_limit, line_dash="dash", annotation_text=t("crop_limit", lang))
            fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="°C", legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        # Hottest day: cooling electricity vs solar output, hour by hour (only when there is cooling to power)
        if uses_power:
            with c2:
                st.subheader(t("solar_vs_cooling", lang))
                day_kwh = prof.groupby(prof["hour_of_year"] // 24)["cooling_kwh"].sum()
                peak_day = int(day_kwh.idxmax())
                hours = slice(peak_day * 24, peak_day * 24 + 24)
                ghi = climate_df["ghi_wh_m2"].to_numpy()[hours]
                # Share the panels' daily output across the hours in proportion to sunlight.
                solar_kwh = ghi / ghi.sum() * rec["solar_kwh_year"] / 365 if ghi.sum() > 0 else ghi * 0
                fig = go.Figure()
                fig.add_bar(x=list(range(24)), y=prof["cooling_kwh"].to_numpy()[hours], name=t("cooling_need", lang), marker_color="#1565c0")
                fig.add_scatter(x=list(range(24)), y=solar_kwh, name=t("solar_output", lang), line=dict(color="#f9a825", width=3))
                fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="kWh", xaxis_title="h", legend=dict(orientation="h", yanchor="bottom", y=1.02))
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        # Cumulative 10-year profit for each setup of the recommended crop
        st.subheader(t("profit_chart", lang))
        fig = go.Figure()
        for o in (o for o in plan["options"] if o["crop"] == rec["crop"]):
            years = list(range(0, 11))
            fig.add_scatter(x=years, y=[-o["capex_qar"] + o["profit_qar_year"] * y for y in years], name=setup_label(o["setup"]),
                            line=dict(width=4 if o["setup"] == rec["setup"] else 2))
        fig.add_hline(y=0, line_color="gray")
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="QAR", xaxis_title=t("years", lang), legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    with st.expander(t("assumptions", lang)):
        for name, rows in plan["assumptions"].items():
            if isinstance(rows, list):
                st.markdown(f"**{name}**")
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.write(f"**{name}:** {rows}")
    with st.expander(t("sources", lang)):
        for s in plan["sources"]:
            st.markdown(f"- {s['name']} — {s['url']}" + (f" (fetched {s['fetched']})" if s.get("fetched") else ""))

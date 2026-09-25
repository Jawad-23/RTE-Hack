"""Operate: inspect and play one simulated day, with an honest data-source banner."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from i18n import t
from planner import crops, dust, operate
from ui import state, theme

lang = state.lang()
st.title(t("nav_operate", lang))
st.info(t("operate_banner", lang))
plan = st.session_state.get("plan")
if not plan or not plan.get("options"):
    st.write(t("r_empty", lang))
    if st.button(t("l_plan", lang)):
        st.switch_page(st.session_state["_pages"]["plan"])
    st.stop()
inp = plan["inputs"]
weather = state.climate_for(inp["lat"], inp["lon"])
crop_names = crops.load_crops()["crop"].tolist()
selected = st.selectbox(t("p_crop", lang), crop_names, format_func=lambda c: state.crop_label(c, lang))
day = st.slider(t("operate_day", lang), 1, 365, 200)
crop = crops.load_crops().set_index("crop").loc[selected].to_dict()
try:
    frame = operate.simulate_day(weather, day, crop, inp["area_m2"])
except ValueError:
    st.warning(t("operate_missing", lang))
    st.stop()
signature = (inp["lat"], inp["lon"], selected, day, inp["area_m2"])
if st.session_state.get("_operate_signature") != signature:
    st.session_state.update(_operate_signature=signature, _operate_tick=0, _operate_play=False)
play, reset, download = st.columns(3)
if play.button(t("operate_pause" if st.session_state.get("_operate_play") else "operate_play", lang)):
    st.session_state["_operate_play"] = not st.session_state.get("_operate_play", False)
    st.rerun()
if reset.button(t("operate_reset", lang)):
    st.session_state.update(_operate_tick=0, _operate_play=False)
    st.rerun()
download.download_button(t("operate_csv", lang), frame.to_csv(index=False), "croptions-simulation.csv", "text/csv")


@st.fragment(run_every=0.5 if st.session_state.get("_operate_play") else None)
def playback():
    tick = st.session_state.get("_operate_tick", 0)
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
    if st.session_state.get("_operate_play"):
        if tick < len(frame) - 1:
            st.session_state["_operate_tick"] = tick + 1
        else:
            st.session_state["_operate_play"] = False
            st.rerun()


playback()
with st.expander(t("operate_data", lang)):
    st.dataframe(frame, hide_index=True)
st.subheader(t("dust_title", lang))
st.caption(t("dust_note", lang))
if st.button(t("dust_fetch", lang)):
    with st.spinner(t("dust_fetch", lang)):
        st.session_state["_dust_exposure"] = (inp["lat"], inp["lon"], dust.recent_exposure(inp["lat"], inp["lon"]))
saved = st.session_state.get("_dust_exposure")
if saved and saved[:2] == (inp["lat"], inp["lon"]):
    exposure = saved[2]
    if exposure["available"]:
        st.metric(t("dust_mean", lang), f"{exposure['mean_ug_m3']} µg/m³")
        st.write(t("dust_hours", lang).format(n=exposure["event_hours"], total=exposure["valid_hours"]))
        st.caption(f"{exposure['start']} — {exposure['end']} UTC · CAMS / Open-Meteo")
        st.link_button("CAMS / Open-Meteo", exposure["source"])
    else:
        st.warning(t("dust_unavailable", lang))

"""Plan: pick a site on the map and describe the farm. Owned by Me."""

import folium
import streamlit as st
from streamlit_folium import st_folium

from i18n import t
from planner import crops
from planner.schemas import PRIORITIES
from ui import state

lang = state.lang()
ss = st.session_state
pages = ss["_pages"]
MAP_START = (25.3, 51.2)  # starting view only; any pin on Earth works

form, map_col = st.columns([1, 2.2], gap="medium")

with form:
    with st.container(key="card_form"):
        st.markdown(f'<p class="cr-title" style="font-size:24px">{t("p_title", lang)}</p><p class="cr-sub">{t("p_sub", lang)}</p>',
                    unsafe_allow_html=True)
        pin = ss["pin"]
        if pin:
            name = state.site_name(*pin, lang) or t("p_pinned", lang)
            st.markdown(f'<div class="cr-site on"><span class="pin"></span><div><b>{name}</b><div class="cr-mono">{state.coords(*pin)}</div></div></div>',
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="cr-site"><span class="pin"></span><div><b>{t("p_nopin", lang)}</b><div class="cr-note">{t("p_empty", lang)}</div></div></div>',
                        unsafe_allow_html=True)

        st.number_input(f"{t('p_size', lang)} (m²)", min_value=50.0, max_value=100000.0, step=50.0, format="%.0f",
                        key=state.bind("area"), on_change=state.save, args=("area",))
        st.number_input(f"{t('p_budget', lang)} ({t('qar', lang)})", min_value=0.0, max_value=50000000.0, step=10000.0, format="%.0f",
                        key=state.bind("budget"), on_change=state.save, args=("budget",))
        names = crops.load_crops()["crop"].tolist()
        st.selectbox(f"{t('p_crop', lang)} {t('optional', lang)}", [state.ANY, *names],
                     format_func=lambda c: t("p_crop_any", lang) if c == state.ANY else state.crop_label(c, lang),
                     key=state.bind("crop"), on_change=state.save, args=("crop",))
        with st.container(key="priority"):
            st.radio(t("p_priority", lang), PRIORITIES,
                     format_func=lambda p: f"{t(f'pr_{p}', lang)} — {t(f'pr_{p}_n', lang)}",
                     key=state.bind("priority"), on_change=state.save, args=("priority",))

        go = st.button(f"{t('p_analyse', lang)} →", type="primary", use_container_width=True, disabled=pin is None)
        if pin is None:
            st.markdown(f'<p class="cr-note" style="text-align:center">{t("p_need_pin", lang)}</p>', unsafe_allow_html=True)
        if go:
            state.run_analysis()
            st.switch_page(pages["results"])

with map_col:
    center = ss["pin"] or MAP_START
    fmap = folium.Map(location=center, zoom_start=9 if ss["pin"] else 8, tiles=None, control_scale=True)
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics", name=t("p_sat", lang),
    ).add_to(fmap)
    folium.TileLayer("OpenStreetMap", name=t("p_ter", lang), show=False).add_to(fmap)
    folium.LayerControl(position="topleft", collapsed=False).add_to(fmap)
    for row in state.demo_sites().itertuples():
        folium.CircleMarker((row.lat, row.lon), radius=6, color="#EBDDBF", fill=True, fill_opacity=0.9,
                            tooltip=row.name_ar if lang == "ar" else row.name_en).add_to(fmap)
    if ss["pin"]:
        folium.Marker(ss["pin"], icon=folium.Icon(color="darkgreen", icon="leaf")).add_to(fmap)
    clicked = st_folium(fmap, height=640, use_container_width=True, returned_objects=["last_clicked"], key="plan_map")
    if clicked and clicked.get("last_clicked"):
        new_pin = (round(clicked["last_clicked"]["lat"], 4), round(clicked["last_clicked"]["lng"], 4))
        if new_pin != ss["pin"]:
            ss["pin"] = new_pin
            st.rerun()

    with st.expander(t("enter_coords", lang)):
        c1, c2, c3 = st.columns([1, 1, 1], vertical_alignment="bottom")
        lat = c1.number_input(t("latitude", lang), -90.0, 90.0, float(center[0]), format="%.4f")
        lon = c2.number_input(t("longitude", lang), -180.0, 180.0, float(center[1]), format="%.4f")
        if c3.button(t("use_coords", lang), use_container_width=True):
            ss["pin"] = (round(lat, 4), round(lon, 4))
            st.rerun()
        demos = state.demo_sites()
        for row in demos.itertuples():
            if st.button(f"📍 {row.name_ar if lang == 'ar' else row.name_en}", key=f"demo_{row.key}"):
                ss["pin"] = (float(row.lat), float(row.lon))
                st.rerun()

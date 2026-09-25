"""Assumptions: every value the planner uses, with its source. Owned by Me.

Read-only for now: values are edited in data/*.csv (see docs/02-project-plan.md, section 10).
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from i18n import t
from ui import state

lang = state.lang()
DATA = Path(__file__).resolve().parent.parent / "data"

st.markdown(f'<h1 style="font-size:32px;margin:8px 0 0">{t("set_title", lang)}</h1><p class="cr-sub">{t("set_note", lang)}</p>',
            unsafe_allow_html=True)


def show(csv: str, rename: dict[str, str], label_col: str | None = None, label=None) -> None:
    df = pd.read_csv(DATA / csv)
    if label_col and label:
        df[label_col] = df[label_col].map(label)
    df = df.rename(columns={k: t(v, lang) for k, v in rename.items()})
    with st.container(key=f"card_{csv.split('.')[0]}"):
        st.dataframe(df, hide_index=True, use_container_width=True,
                     column_config={t("h_source", lang): st.column_config.TextColumn(width="large")})
        est = int(df[t("h_source", lang)].astype(str).str.contains("estimate", case=False).sum())
        if est:
            st.markdown(f'<p class="cr-note">⚠ {t("est_count", lang).format(n=est, total=len(df))}</p>', unsafe_allow_html=True)


tabs = st.tabs([t("tab_limits", lang), t("tab_costs", lang), t("tab_prices", lang), t("tab_settings", lang)])
with tabs[0]:
    show("crops.csv", {"crop": "h_crop", "t_min_c": "h_min", "t_opt_min_c": "h_opt_min", "t_opt_max_c": "h_opt_max", "t_max_c": "h_max",
                       "yield_kg_m2_year": "h_yield", "water_l_m2_day": "h_water", "source": "h_source"},
         "crop", lambda c: state.crop_label(c, lang))
with tabs[1]:
    show("setups.csv", {"setup": "c_setup", "capex_qar_m2": "h_build", "opex_qar_m2_year": "h_run", "source": "h_source"},
         "setup", lambda s: state.setup_label(s, lang))
with tabs[2]:
    show("prices.csv", {"crop": "h_crop", "price_qar_kg": "h_price", "source": "h_source", "year": "h_year"},
         "crop", lambda c: state.crop_label(c, lang))
with tabs[3]:
    show("settings.csv", {"key": "h_key", "value": "h_value", "unit": "h_unit", "source": "h_source"})

st.markdown(f'<p class="cr-note">{t("set_edit_hint", lang)}</p>', unsafe_allow_html=True)

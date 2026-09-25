"""Assumptions: every value the planner uses, with its source. Owned by Me.

Read-only for now: values are edited in data/*.csv (see docs/02-project-plan.md, section 10).
Crop prices are not a CSV: they come live from FAOSTAT for the analysed site's country (planner/market.py).
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from i18n import t
from planner import market, solar
from ui import state

lang = state.lang()
DATA = Path(__file__).resolve().parent.parent / "data"

st.markdown(f'<h1 style="font-size:32px;margin:8px 0 0">{t("set_title", lang)}</h1><p class="cr-sub">{t("set_note", lang)}</p>',
            unsafe_allow_html=True)


def show(csv: str | pd.DataFrame, rename: dict[str, str], label_col: str | None = None, label=None, key: str | None = None) -> None:
    df = pd.read_csv(DATA / csv) if isinstance(csv, str) else csv
    if label_col and label:
        df[label_col] = df[label_col].map(label)
    df = df.rename(columns={k: t(v, lang) for k, v in rename.items()})
    with st.container(key=f"card_{key or csv.split('.')[0]}"):
        st.dataframe(df, hide_index=True, use_container_width=True,
                     column_config={t("h_source", lang): st.column_config.TextColumn(width="large")})
        src = t("h_source", lang)
        est = int(df[src].astype(str).str.contains("estimate", case=False).sum()) if src in df else 0
        if est:
            st.markdown(f'<p class="cr-note">⚠ {t("est_count", lang).format(n=est, total=len(df))}</p>', unsafe_allow_html=True)


tabs = st.tabs([t("tab_limits", lang), t("tab_costs", lang), t("tab_prices", lang), t("tab_settings", lang)])
with tabs[0]:
    limits = pd.read_csv(DATA / "crops.csv")
    limits["kc"] = limits[["kc_ini", "kc_mid", "kc_end"]].astype(str).agg(" / ".join, axis=1)
    limits = limits[["crop", "t_min_c", "t_opt_min_c", "t_opt_max_c", "t_max_c", "yield_kg_m2_year", "kc", "source", "kc_source"]]
    show(limits, {"crop": "h_crop", "t_min_c": "h_min", "t_opt_min_c": "h_opt_min", "t_opt_max_c": "h_opt_max", "t_max_c": "h_max",
                  "yield_kg_m2_year": "h_yield", "kc": "h_kc", "source": "h_source", "kc_source": "h_kc_source"},
         "crop", lambda c: state.crop_label(c, lang), key="crops")
with tabs[1]:
    show("setups.csv", {"setup": "c_setup", "capex_qar_m2": "h_build", "opex_qar_m2_year": "h_run", "source": "h_source"},
         "setup", lambda s: state.setup_label(s, lang))
with tabs[2]:
    plan = st.session_state.get("plan") or {}
    prices = (plan.get("assumptions") or {}).get("prices")
    country = (plan.get("assumptions") or {}).get("price_country")
    fetched = next((s.get("fetched") for s in plan.get("sources", []) if "FAOSTAT" in s.get("name", "")), None)
    if not prices:  # no site analysed yet: world medians from the same FAOSTAT table
        table, fetched = market.load_price_table()
        prices = [{"crop": c, **p} for c, p in market.price_per_crop(table, None, solar.load_settings()["usd_to_qar"]).items()]
    if country:
        note = t("prices_country", lang).format(country=country["name"], date=fetched)
    else:  # no site yet, or the site's country could not be looked up
        note = t("prices_world_site" if plan.get("assumptions") else "prices_world", lang).format(date=fetched)
    st.markdown(f'<p class="cr-note">{note}</p>', unsafe_allow_html=True)
    table = pd.DataFrame(prices)[["crop", "price_qar_kg", "year", "note"]].rename(columns={"note": "source"})
    table["year"] = table["year"].map(lambda y: "—" if pd.isna(y) else str(int(y)))
    show(table,
         {"crop": "h_crop", "price_qar_kg": "h_price", "year": "h_year", "source": "h_price_basis"},
         "crop", lambda c: state.crop_label(c, lang), key="prices")
with tabs[3]:
    show("settings.csv", {"key": "h_key", "value": "h_value", "unit": "h_unit", "source": "h_source"})

st.markdown(f'<p class="cr-note">{t("set_edit_hint", lang)}</p>', unsafe_allow_html=True)

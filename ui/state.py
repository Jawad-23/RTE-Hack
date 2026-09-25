"""Session state, formatting and the "analyse a site" action shared by every page. Owned by Me."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from i18n import has, t
from planner import climate, optimizer
from planner.schemas import PRIORITIES

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DEFAULTS = {
    "lang": "en",
    "area": 500.0,
    "budget": 250000.0,
    "crop": None,
    "priority": "profit",
    "pin": None,          # (lat, lon)
    "plan": None,
    "compare": None,      # {"a": plan, "b": plan}
    "chat_open": False,
    "chat_preset": None,
}


def init() -> None:
    """Fill missing session keys and restore a shared plan from the URL (?lat=..&lon=..)."""
    for key, value in DEFAULTS.items():
        st.session_state.setdefault(key, value)
    qp = st.query_params
    if st.session_state["plan"] is None and "lat" in qp and "lon" in qp and not st.session_state.get("_restored"):
        st.session_state["_restored"] = True
        try:
            st.session_state["pin"] = (float(qp["lat"]), float(qp["lon"]))
            st.session_state["area"] = float(qp.get("area", DEFAULTS["area"]))
            st.session_state["budget"] = float(qp.get("budget", DEFAULTS["budget"]))
            st.session_state["priority"] = qp.get("priority", "profit") if qp.get("priority") in PRIORITIES else "profit"
            st.session_state["crop"] = qp.get("crop") or None
            run_analysis(show_steps=False)
        except (ValueError, TypeError):
            pass
    if qp.get("lang") in ("en", "ar"):
        st.session_state["lang"] = qp["lang"]


def lang() -> str:
    return st.session_state["lang"]


ANY = ""  # widget value for "no preference" (the stored value is None)


def bind(key: str) -> str:
    """Keep a widget's value across pages: copy the stored value into the widget key before drawing it."""
    wkey = f"_w_{key}"
    value = st.session_state[key]
    st.session_state[wkey] = ANY if (key == "crop" and value is None) else value
    return wkey


def save(key: str) -> None:
    """on_change callback that stores a widget's value under its permanent key (ignores an emptied toggle)."""
    value = st.session_state[f"_w_{key}"]
    if value is None and key in ("lang", "priority"):
        return
    if key == "crop" and value == ANY:
        value = None
    st.session_state[key] = value


# ---------- formatting ----------

def n0(v) -> str:
    """1234.5 -> '1,235'; None -> '—'."""
    return "—" if v is None else f"{v:,.0f}"


def n1(v) -> str:
    return "—" if v is None else f"{v:,.1f}"


def coords(lat: float, lon: float) -> str:
    return f"{abs(lat):.2f}° {'N' if lat >= 0 else 'S'}, {abs(lon):.2f}° {'E' if lon >= 0 else 'W'}"


def crop_label(crop: str, lg: str) -> str:
    return t(f"crop_{crop}", lg) if _has(f"crop_{crop}") else crop.replace("_", " ").capitalize()


def crop_in_sentence(crop: str, lg: str) -> str:
    return t(f"cropv_{crop}", lg) if _has(f"cropv_{crop}") else crop.replace("_", " ")


def setup_label(setup: str, lg: str) -> str:
    return t(f"setup_{setup}", lg)


def _has(key: str) -> bool:
    return has(key)


@st.cache_data(show_spinner=False)
def demo_sites() -> pd.DataFrame:
    """data/demo_sites.csv: named example pins for the home page and the compare page."""
    return pd.read_csv(DATA_DIR / "demo_sites.csv")


def site_name(lat: float, lon: float, lg: str) -> str | None:
    """Name of a demo site within about 1 km of the pin, else None."""
    for row in demo_sites().itertuples():
        if abs(row.lat - lat) < 0.01 and abs(row.lon - lon) < 0.01:
            return row.name_ar if lg == "ar" else row.name_en
    return None


@st.cache_data(show_spinner=False, max_entries=16)
def climate_for(lat: float, lon: float) -> pd.DataFrame:
    return climate.get_typical_year(lat, lon)


# ---------- actions ----------

def run_analysis(show_steps: bool = True) -> dict | None:
    """Run the planner for the stored pin and inputs; store and return the plan."""
    ss = st.session_state
    if not ss["pin"]:
        return None
    lat, lon = ss["pin"]
    args = dict(area_m2=float(ss["area"]), budget_qar=float(ss["budget"]), priority=ss["priority"], crop=ss["crop"])
    lg = lang()
    if show_steps:
        with st.status(t("a_title", lg), expanded=True) as status:
            st.write(f"⏳ {t('s1', lg)}")
            try:
                climate_for(lat, lon)
            except climate.ClimateUnavailable:
                pass  # plan() reports the reason
            st.write(f"✓ {t('s1', lg)}")
            st.write(f"⏳ {t('s3', lg)}")
            plan = optimizer.plan(lat, lon, **args)
            for key in ("s2", "s3", "s4", "s5"):
                st.write(f"✓ {t(key, lg)}")
            status.update(label=t("st_done", lg), state="complete", expanded=False)
    else:
        plan = optimizer.plan(lat, lon, **args)
    ss["plan"] = plan
    st.query_params.update({"lat": f"{lat:.4f}", "lon": f"{lon:.4f}", "area": f"{args['area_m2']:.0f}",
                            "budget": f"{args['budget_qar']:.0f}", "priority": args["priority"], **({"crop": args["crop"]} if args["crop"] else {})})
    if not args["crop"] and "crop" in st.query_params:
        del st.query_params["crop"]
    return plan


def open_chat(question: str | None = None) -> None:
    """Open the assistant dialog, optionally sending a question straight away."""
    st.session_state["chat_open"] = True
    st.session_state["chat_preset"] = question

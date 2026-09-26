"""Croptions Kit pieces shared by the Kit page (views/operate.py), Results and the kit simulator (views/kit_remote.py). Owned by Me.

The simulator and the dashboard are separate Streamlit sessions; they meet in one KitStore kept by
st.cache_resource, so it is shared by every visitor of this server (and emptied on restart).
"""

from __future__ import annotations

import numpy as np
import streamlit as st

from i18n import t
from planner import kit


@st.cache_resource(show_spinner=False)
def store() -> kit.KitStore:
    return kit.KitStore()


def latest(code: str | None) -> dict | None:
    """The newest reading stored for a Kit ID, or None."""
    readings = store().readings(code) if code else []
    return readings[-1] if readings else None


def scenario_label(scenario: str, lang: str) -> str:
    return t(f"kit_sc_{scenario}", lang)


def send(code: str, ctx: dict, scenario: str, hour: int | None) -> dict | None:
    """Simulate one reading for the farm and put it in the shared inbox."""
    reading = kit.simulate_reading(ctx["day"], hour, scenario, np.random.default_rng())
    return store().push(code, {**reading, "sim_day": ctx["sim_day"]})


def sender(code: str, ctx: dict, lang: str, key: str) -> None:
    """One button per scenario. 'Normal' uses the chosen time of day; the others use their own hour."""
    hour = st.slider(t("kit_hour", lang), 0, 23, 12, format="%d:00", key=f"{key}_hour")
    table = kit.load_scenarios()
    cols = st.columns(2)
    for i, scenario in enumerate(kit.scenarios()):
        fixed = table.loc[scenario, "hour"]
        at = hour if scenario == "normal" or np.isnan(fixed) else int(fixed)
        if cols[i % 2].button(f"{scenario_label(scenario, lang)} · {at:02d}:00", key=f"{key}_{scenario}",
                              use_container_width=True, type="primary" if scenario == "normal" else "secondary"):
            sent = send(code, ctx, scenario, at)
            if sent:
                st.toast(t("kit_sent", lang).format(n=sent["seq"]), icon="📡")
            else:
                st.error(t("kit_code_unknown", lang))

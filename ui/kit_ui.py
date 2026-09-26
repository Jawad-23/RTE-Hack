"""Croptions Kit pieces shared by the dashboard (views/operate.py) and the phone remote (views/kit_remote.py). Owned by Me.

The phone and the laptop are separate Streamlit sessions; they meet in one KitStore kept by
st.cache_resource, so it is shared by every visitor of this server (and emptied on restart).
"""

from __future__ import annotations

from urllib.parse import urlsplit

import numpy as np
import streamlit as st

from i18n import t
from planner import kit

REMOTE_PATH = "kit-remote"


@st.cache_resource(show_spinner=False)
def store() -> kit.KitStore:
    return kit.KitStore()


def remote_url(code: str, lang: str) -> str:
    """Link the phone opens: this server's address + /kit-remote?farm=<code>."""
    parts = urlsplit(st.context.url or "")
    base = f"{parts.scheme}://{parts.netloc}" if parts.netloc else ""
    return f"{base}/{REMOTE_PATH}?farm={code}" + ("&lang=ar" if lang == "ar" else "")


def is_local(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    return host in ("", "localhost", "127.0.0.1", "0.0.0.0")


def qr_data_uri(url: str) -> str | None:
    """QR code for the remote link as an SVG data URI (segno, pure Python). None if segno is not installed."""
    try:
        import segno
    except ImportError:
        return None
    return segno.make(url, error="m").svg_data_uri(scale=6, border=2, dark="#1E5B3F")


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

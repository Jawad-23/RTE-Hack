"""Croptions Kit phone remote: the phone plays the kit and sends simulated readings. Owned by Me.

Opened from the QR code on the Kit page (…/kit-remote?farm=1234). No top bar, big buttons, works on a phone.
"""

import streamlit as st

from i18n import t
from ui import kit_ui, state

lang = state.lang()
ss = st.session_state

code = st.query_params.get("farm") or st.text_input(t("kit_enter_code", lang), max_chars=4, key="_remote_code")
ctx = kit_ui.store().context(code) if code else None
if not ctx:
    if code:
        st.error(t("kit_code_unknown", lang))
    st.info(t("kit_remote_help", lang))
    st.stop()

st.markdown(f'<p class="cr-title" style="font-size:26px">{t("kit_remote_title", lang).format(code=code)}</p>'
            f'<p class="cr-sub">{ctx["site"]} · {state.crop_label(ctx["crop"], lang)} · {state.setup_label(ctx["setup"], lang)}</p>',
            unsafe_allow_html=True)
st.markdown(f'<div class="cr-banner">⚠ {t("kit_sim_banner", lang)}</div>', unsafe_allow_html=True)

kit_ui.sender(code, ctx, lang, key="remote")

# ---------- stream a whole day, one reading every two seconds ----------
FIRST_HOUR, LAST_HOUR = 5, 20
streaming = ss.get("_stream_hour") is not None
if st.button(t("kit_stream_stop" if streaming else "kit_stream", lang), use_container_width=True, key="stream_btn"):
    ss["_stream_hour"] = None if streaming else FIRST_HOUR
    st.rerun()


@st.fragment(run_every=2 if streaming else None)
def stream():
    hour = ss.get("_stream_hour")
    if hour is None:
        return
    sent = kit_ui.send(code, ctx, "normal", hour)
    st.progress((hour - FIRST_HOUR + 1) / (LAST_HOUR - FIRST_HOUR + 1),
                text=t("kit_streaming", lang).format(hour=f"{hour:02d}:00", n=sent["seq"] if sent else "—"))
    if hour >= LAST_HOUR or sent is None:
        ss["_stream_hour"] = None
        st.rerun()
    ss["_stream_hour"] = hour + 1


stream()
last = kit_ui.store().readings(code)[-1:]
if last:
    r = last[0]
    st.caption(t("kit_last_sent", lang).format(n=r["seq"], leaf=f"{r['leaf_c']:.1f}", air=f"{r['air_c']:.1f}",
                                               rh=f"{r['rh_pct']:.0f}", hour=f"{r['sim_hour']:02d}:00"))

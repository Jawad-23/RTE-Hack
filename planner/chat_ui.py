"""English/Arabic chat panel, shown in the "Ask Croptions" dialog. Owned by Salih."""

from __future__ import annotations

import html

import streamlit as st

from i18n import t
from planner import agent

SUGGESTIONS = ["suggest_why", "suggest_budget", "suggest_water", "suggest_crop"]


def _bubble(text: str, lang: str) -> None:
    """Draw message text; Arabic goes inside a right-to-left block so mixed Arabic/English reads correctly."""
    if lang == "ar":
        st.markdown(f'<div dir="rtl" style="text-align:right">{html.escape(text)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(text)


def render(plan: dict | None, lang: str, preset: str | None = None) -> None:
    """Current plan + language (+ an optional question to send at once) -> draws the chat."""
    chat = st.session_state.setdefault("chat", [])
    head, new = st.columns([4, 1], vertical_alignment="center")
    head.caption(f"● {t('reply_in', lang)} · {t('chat_footer', lang)}")
    if chat and new.button(t("new_chat", lang), key="chat_new", use_container_width=True):
        chat.clear()
        st.rerun()

    ready, why = agent.llm_ready()
    if not ready:
        st.info(t(why, lang))

    if not chat:
        st.markdown(f"**{t('chat_hello', lang)}**  \n{t('chat_hello_sub', lang)}")

    for msg in chat:
        with st.chat_message(msg["role"]):
            _bubble(msg["content"], msg.get("language", lang))
            if msg["role"] == "assistant":
                if msg.get("verified"):
                    st.caption(f"✅ {t('verified', lang)}")
                if msg.get("plan_updated"):
                    st.caption(f"🔄 {t('plan_updated', lang)}")
                if msg.get("tool_log"):
                    with st.expander(t("tool_log", lang)):
                        for line in msg["tool_log"]:
                            st.code(line, language=None)

    question = preset
    if not chat and not question:
        cols = st.columns(2)
        for i, key in enumerate(SUGGESTIONS):
            if cols[i % 2].button(t(key, lang), key=f"suggest_{key}_{lang}", use_container_width=True):
                question = t(key, lang)

    typed = st.chat_input(t("chat_placeholder", lang), key="chat_input")
    question = typed or question
    if not question:
        return

    history = [{"role": m["role"], "content": m["content"]} for m in chat]
    chat.append({"role": "user", "content": question, "language": agent.detect_language(question)})
    with st.spinner(t("chat_thinking", lang)):
        result = agent.ask(question, history, plan)
    chat.append({
        "role": "assistant", "content": result["reply"], "language": result["language"],
        "verified": result["verified"], "tool_log": result["tool_log"], "plan_updated": result["plan"] is not None,
    })
    if result["plan"] is not None:
        st.session_state["plan"] = result["plan"]
    st.rerun()  # full rerun redraws the dashboard; the dialog reopens because chat_open stays True

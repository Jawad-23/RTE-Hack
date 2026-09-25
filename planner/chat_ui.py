"""English/Arabic chat panel. Owned by Salih."""

from __future__ import annotations

import html
import os

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


def render(plan: dict | None, lang: str) -> None:
    """Current plan + language -> draws the chat panel in the Streamlit page."""
    st.subheader(t("chat_title", lang))
    chat = st.session_state.setdefault("chat", [])

    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.info(t("chat_no_key", lang))

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

    question = None
    if not chat:
        cols = st.columns(2)
        for i, key in enumerate(SUGGESTIONS):
            if cols[i % 2].button(t(key, lang), key=f"suggest_{key}_{lang}", use_container_width=True):
                question = t(key, lang)

    typed = st.chat_input(t("chat_placeholder", lang))
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
    st.rerun()

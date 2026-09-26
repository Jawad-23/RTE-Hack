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


def _plan_signature(plan: dict) -> tuple:
    rec = plan.get("recommended") or {}
    return tuple(sorted((plan.get("inputs") or {}).items(), key=lambda kv: kv[0])) + (rec.get("crop"), rec.get("setup"))


def render(plan: dict | None, lang: str, preset: str | None = None, key: str = "chat", summary: bool = False) -> None:
    """Current plan + language (+ an optional question to send at once) -> draws the chat.

    summary=True (Results page): a new plan starts a fresh chat that opens with the assistant's summary of it.
    key keeps widget keys apart when the chat is on the page and in the dialog.
    """
    ss = st.session_state
    if summary and plan and ss.get("chat_plan_sig") != _plan_signature(plan):
        ss["chat"], ss["chat_plan_sig"], ss["chat_summary_pending"] = [], _plan_signature(plan), True
    chat = ss.setdefault("chat", [])
    head, new = st.columns([4, 1], vertical_alignment="center")
    head.caption(f"● {t('reply_in', lang)} · {t('chat_footer', lang)}")
    if chat and new.button(t("new_chat", lang), key=f"{key}_new", use_container_width=True):
        chat.clear()
        ss["chat_summary_pending"] = summary
        st.rerun()

    ready, why = agent.llm_ready()
    if not ready:
        st.info(t(why, lang))

    if not chat and not ss.get("chat_summary_pending"):
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

    if summary and plan and ss.get("chat_summary_pending"):
        with st.chat_message("assistant"), st.spinner(t("chat_summarising", lang)):
            result = agent.summarize(plan, lang)
        ss["chat_summary_pending"] = False
        chat.append({"role": "assistant", "content": result["reply"], "language": result["language"],
                     "verified": result["verified"], "tool_log": result["tool_log"], "plan_updated": False})
        st.rerun()

    question = preset
    if len(chat) <= (1 if summary else 0) and not question:
        cols = st.columns(2)
        for i, s_key in enumerate(SUGGESTIONS):
            if cols[i % 2].button(t(s_key, lang), key=f"{key}_suggest_{s_key}_{lang}", use_container_width=True):
                question = t(s_key, lang)

    typed = st.chat_input(t("chat_placeholder", lang), key=f"{key}_input")
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
        ss["chat_plan_sig"] = _plan_signature(result["plan"])  # keep this conversation; only a plan from the Plan page starts a new one
    st.rerun()  # full rerun redraws the dashboard; the dialog reopens because chat_open stays True

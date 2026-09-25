"""English/Arabic chat panel. Owned by Salih.

STUB: shows a placeholder until Salih builds the chat (docs/03-team-tasks.md, section 6, step 4).
"""

import streamlit as st

from i18n import t


def render(plan: dict | None, lang: str) -> None:
    """Current plan + language -> draws the chat panel in the Streamlit page."""
    # TODO(Salih): history in st.session_state["chat"], suggested prompts, verified badge.
    st.subheader(t("chat_title", lang))
    st.info(t("chat_coming_soon", lang))

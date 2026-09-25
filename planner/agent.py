"""AI agent: Claude with tools, plus the number checker. Owned by Salih.

STUB: returns a correctly shaped placeholder until Salih builds the real agent
(docs/03-team-tasks.md, section 6, step 1).
"""

import re

ARABIC = re.compile(r"[؀-ۿ]")


def ask(message: str, history: list, current_plan: dict | None) -> dict:
    """User message, chat history, current plan -> reply, language ("en"/"ar"), verified, plan (new or None), tool_log."""
    # TODO(Salih): tool loop with run_plan / compare_sites, then checker.verify().
    language = "ar" if ARABIC.search(message) else "en"
    reply = "المساعد قيد الإنشاء." if language == "ar" else "The assistant is not built yet."
    return {"reply": reply, "language": language, "verified": False, "plan": None, "tool_log": []}

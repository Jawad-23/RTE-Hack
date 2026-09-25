"""Hallucination guard: every number in a reply must come from the plan, a tool result or the user. Owned by Salih."""

from __future__ import annotations

import re

# Arabic-Indic (٠–٩) and Eastern Arabic-Indic (۰–۹) digits, Arabic decimal (٫) and thousands (٬) separators
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬", "01234567890123456789.,")
# thousands may be grouped with commas or spaces (plain, no-break or narrow no-break): 175,000 / 175 000
_NUMBER = re.compile(r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?!\d)(?:\.\d+)?|\d+(?:\.\d+)?)(?:\s?([kK])\b|\s(thousand)\b)?")

REL_TOL = 0.01   # a number passes if within 1 % ...
ABS_TOL = 0.1    # ... or within ±0.1 of an allowed number
ALWAYS_ALLOWED = [(1, 12), (2000, 2100)]  # month numbers and years


def extract_numbers(text: str) -> list[float]:
    """Reply text (English or Arabic) -> every number in it, as positive floats."""
    text = text.translate(_DIGITS)
    # "175k" and "175 thousand" mean 175,000, so they are checked as that
    return [float(re.sub(r"[, \u00a0\u202f]", "", m.group(1))) * (1000 if m.group(2) or m.group(3) else 1) for m in _NUMBER.finditer(text)]


def allowed_numbers(plan, tool_results=None, user_text: str = "") -> set[float]:
    """Plan, tool results and the user's own message -> every number that appears in them (including inside strings)."""
    found: set[float] = set()

    def walk(obj):
        if isinstance(obj, bool) or obj is None:
            return
        if isinstance(obj, (int, float)):
            found.add(abs(float(obj)))
        elif isinstance(obj, str):
            found.update(extract_numbers(obj))
        elif isinstance(obj, dict):
            for k, v in obj.items():
                walk(k)
                walk(v)
        elif isinstance(obj, (list, tuple, set)):
            for v in obj:
                walk(v)

    walk(plan)
    walk(tool_results or [])
    found.update(extract_numbers(user_text))
    return found


def _ok(n: float, allowed: set[float]) -> bool:
    if any(lo <= n <= hi and n.is_integer() for lo, hi in ALWAYS_ALLOWED):
        return True
    return any(abs(n - a) <= max(ABS_TOL, REL_TOL * abs(a)) for a in allowed)


def verify(reply: str, plan, tool_results=None, user_text: str = "") -> tuple[bool, list]:
    """Reply text, plan, tool results (and optionally the user's message) -> (ok, bad_numbers)."""
    allowed = allowed_numbers(plan, tool_results, user_text)
    bad = sorted({n for n in extract_numbers(reply) if not _ok(n, allowed)})
    return (not bad, bad)

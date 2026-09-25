"""Hallucination guard: every number in a reply must come from the plan or a tool result. Owned by Salih.

STUB: accepts everything until Salih builds it (docs/03-team-tasks.md, section 6, step 2).
"""


def verify(reply: str, plan: dict | None, tool_results: list) -> tuple[bool, list]:
    """Reply text, plan, tool results -> (ok, bad_numbers)."""
    # TODO(Salih): extract_numbers() + allowed_numbers(), 1% / ±0.1 tolerance.
    return True, []

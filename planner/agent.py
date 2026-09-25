"""AI agent: Claude plans with our tools and explains; the checker blocks invented numbers. Owned by Salih.

Only call_llm() talks to the Claude API, so the model can be swapped for an open-weight one later.
"""

from __future__ import annotations

import json
import re

from dotenv import load_dotenv

from i18n import t
from planner import checker, optimizer
from planner.schemas import PRIORITIES

load_dotenv()

# All LLM settings in one place. Sonnet 5 does not accept a temperature setting; determinism
# comes from the tools instead: every number in a reply is checked against tool output.
MODEL = "claude-sonnet-5"
MAX_TOKENS = 4096
MAX_TOOL_ROUNDS = 5

ARABIC = re.compile(r"[؀-ۿ]")

SYSTEM_PROMPT = """You are a farm planning assistant for hot, arid regions.
Rules:
1. Use ONLY numbers that appear in the current plan or in tool results. Never estimate, round creatively, or invent a number.
2. If the user asks "what if", call a tool and answer from its result.
3. If the data does not answer the question, say so plainly.
4. Reply in the same language as the user. For Arabic, use clear Modern Standard Arabic and Western digits.
5. Always include units (°C, QAR, m², kW, years).
6. Keep answers short: the answer first, then one or two reasons.
7. You advise; the farmer makes the final decision.
Setup names: open_field = open field, shade_net = shade net, wet_pad = wet-pad (evaporative) greenhouse, chiller = solar-powered chiller greenhouse.
Cost and price inputs marked "estimate" in the assumptions are illustrative; say so if the user relies on them."""

_SITE = {
    "type": "object",
    "properties": {"lat": {"type": "number", "description": "Latitude in degrees"}, "lon": {"type": "number", "description": "Longitude in degrees"}},
    "required": ["lat", "lon"],
}
_SHARED = {
    "area_m2": {"type": "number", "description": "Farm area in square metres"},
    "budget_qar": {"type": "number", "description": "Build budget in Qatari riyals"},
    "priority": {"type": "string", "enum": PRIORITIES, "description": "profit = highest 10-year profit, payback = fastest payback, water = least water"},
    "crop": {"type": "string", "description": "Optional crop name exactly as in the plan's crop table"},
}
TOOLS = [
    {
        "name": "run_plan",
        "description": "Run the full farm planner for one site and return the plan (recommendation, every crop × setup option, "
                       "crop calendar, sources, assumptions). Use it for any 'what if' question about budget, area, priority, crop or location.",
        "input_schema": {
            "type": "object",
            "properties": {**_SITE["properties"], **_SHARED},
            "required": ["lat", "lon", "area_m2", "budget_qar", "priority"],
        },
    },
    {
        "name": "compare_sites",
        "description": "Run the planner for two sites with the same area, budget and priority, and return both plans' recommendations.",
        "input_schema": {
            "type": "object",
            "properties": {"site_a": _SITE, "site_b": _SITE, **_SHARED},
            "required": ["site_a", "site_b", "area_m2", "budget_qar", "priority"],
        },
    },
]

_client = None


def call_llm(system: str, messages: list, tools: list, tool_choice: dict | None = None):
    """The only function that talks to the Claude API. Returns the SDK Message."""
    global _client
    import anthropic

    if _client is None:
        _client = anthropic.Anthropic()
    kwargs = {"tool_choice": tool_choice} if tool_choice else {}
    return _client.messages.create(model=MODEL, max_tokens=MAX_TOKENS, system=system, messages=messages, tools=tools, **kwargs)


def detect_language(text: str) -> str:
    """Message text -> "ar" if it contains Arabic script, else "en"."""
    return "ar" if ARABIC.search(text) else "en"


def compact_plan(plan: dict | None) -> dict | None:
    """Full plan -> the parts the LLM needs (drops per-month detail to keep the prompt small)."""
    if not plan:
        return None
    keep = ["crop", "setup", "coverage_pct", "growing_months", "inside_max_c", "capex_qar", "opex_qar_year", "revenue_qar_year",
            "profit_qar_year", "payback_years", "profit_10y_qar", "water_l_day", "solar_kw", "cooling_kwh_year", "passes", "fail_reasons"]
    slim = lambda o: {k: o.get(k) for k in keep} if o else None  # noqa: E731
    site = {k: v for k, v in plan.get("site", {}).items() if not k.startswith("monthly_")}
    return {
        "inputs": plan.get("inputs"),
        "site": site,
        "recommended": slim(plan.get("recommended")),
        "reason": plan.get("reason"),
        "options": [slim(o) for o in plan.get("options", [])],
        "calendar": plan.get("calendar"),
        "sources": plan.get("sources"),
        "assumptions": plan.get("assumptions"),
    }


def _run_tool(name: str, args: dict) -> tuple[dict, dict | None, str]:
    """Tool name + input -> (result for the LLM, new plan or None, readable log line)."""
    shared = {k: args.get(k) for k in ("area_m2", "budget_qar", "priority")}
    crop = args.get("crop") or None
    if name == "run_plan":
        plan = optimizer.plan(args["lat"], args["lon"], crop=crop, **shared)
        log = f"run_plan(lat={args['lat']}, lon={args['lon']}, area_m2={shared['area_m2']}, budget_qar={shared['budget_qar']}, priority={shared['priority']}" + (f", crop={crop})" if crop else ")")
        return compact_plan(plan), plan, log
    if name == "compare_sites":
        a = optimizer.plan(args["site_a"]["lat"], args["site_a"]["lon"], crop=crop, **shared)
        b = optimizer.plan(args["site_b"]["lat"], args["site_b"]["lon"], crop=crop, **shared)
        result = {"site_a": {k: compact_plan(a)[k] for k in ("site", "recommended", "reason")},
                  "site_b": {k: compact_plan(b)[k] for k in ("site", "recommended", "reason")}}
        return result, None, f"compare_sites({args['site_a']}, {args['site_b']}, budget_qar={shared['budget_qar']})"
    raise ValueError(f"Unknown tool {name!r}")


def _text(response) -> str:
    return "\n".join(b.text for b in response.content if b.type == "text").strip()


def safe_answer(plan: dict | None, lang: str) -> str:
    """Template answer built only from plan fields, used when the LLM keeps using unverified numbers."""
    if not plan:
        return t("safe_answer_no_plan", lang)
    rec = plan.get("recommended")
    if rec is None:
        return t("safe_answer_none", lang).format(reason=plan.get("reason", ""))
    payback = "—" if rec.get("payback_years") is None else f"{rec['payback_years']}"
    return t("safe_answer_rec", lang).format(
        setup=t(f"setup_{rec['setup']}", lang), crop=rec["crop"].replace("_", " "), coverage=rec["coverage_pct"],
        capex=f"{rec['capex_qar']:,.0f}", payback=payback,
    )


def ask(message: str, history: list, current_plan: dict | None) -> dict:
    """User message, chat history ([{role, content}] text turns), current plan -> reply, language ("en"/"ar"), verified, plan (new or None), tool_log."""
    lang = detect_language(message)
    context = json.dumps(compact_plan(current_plan), ensure_ascii=False) if current_plan else "No plan yet: the user has not analysed a site."
    messages = [{"role": m["role"], "content": m["content"]} for m in history if m.get("content")]
    messages.append({"role": "user", "content": f"<current_plan>\n{context}\n</current_plan>\n\n{message}"})

    tool_log: list[str] = []
    tool_results: list = []
    new_plan = None
    try:
        response = call_llm(SYSTEM_PROMPT, messages, TOOLS)
        for _ in range(MAX_TOOL_ROUNDS):
            if response.stop_reason != "tool_use":
                break
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for block in (b for b in response.content if b.type == "tool_use"):
                try:
                    result, plan, log = _run_tool(block.name, block.input)
                    tool_results.append(result)
                    tool_log.append(log)
                    new_plan = plan or new_plan
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result, ensure_ascii=False)})
                except Exception as exc:  # report the failure to the model instead of crashing the chat
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": f"Tool error: {exc}", "is_error": True})
            messages.append({"role": "user", "content": results})
            response = call_llm(SYSTEM_PROMPT, messages, TOOLS)

        if response.stop_reason == "refusal":
            return {"reply": t("chat_error", lang), "language": lang, "verified": False, "plan": new_plan, "tool_log": tool_log}
        if response.stop_reason == "tool_use":  # still asking for tools after MAX_TOOL_ROUNDS
            tool_log.append(f"stopped after {MAX_TOOL_ROUNDS} tool rounds; using template answer")
            return {"reply": safe_answer(new_plan or current_plan, lang), "language": lang, "verified": True, "plan": new_plan, "tool_log": tool_log}

        reply = _text(response)
        known = [current_plan, new_plan]
        ok, bad = checker.verify(reply, known, tool_results, user_text=message)
        if not ok:
            tool_log.append(f"checker rejected: {bad}")
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": "Rewrite your answer using only numbers from the plan or tool results. "
                                                        f"These numbers are not in the data: {bad}"})
            response = call_llm(SYSTEM_PROMPT, messages, TOOLS, tool_choice={"type": "none"})
            reply = _text(response)
            ok, bad = checker.verify(reply, known, tool_results, user_text=message)
            if not ok:
                tool_log.append(f"checker rejected again: {bad}; using template answer")
                reply, ok = safe_answer(new_plan or current_plan, lang), True
        return {"reply": reply, "language": lang, "verified": ok, "plan": new_plan, "tool_log": tool_log}
    except Exception as exc:  # no key, network down, API error: the dashboard still works without the chat
        tool_log.append(f"{type(exc).__name__}: {exc}")
        return {"reply": t("chat_error", lang), "language": lang, "verified": False, "plan": new_plan, "tool_log": tool_log}

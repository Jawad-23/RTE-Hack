"""AI agent: an LLM plans with our tools and explains; the checker blocks invented numbers. Owned by Salih.

Only call_llm() talks to an LLM. It supports two providers, chosen in .env:
- LLM_PROVIDER=anthropic (default): the Claude API.
- LLM_PROVIDER=openai_compatible: any open-weight model behind an OpenAI-compatible chat API
  (Ollama, llama.cpp server, vLLM, LM Studio, or hosted ones such as Groq or OpenRouter).
Both return the same response shape, so the rest of the agent does not care which one runs.
"""

from __future__ import annotations

import json
import os
import re
from types import SimpleNamespace

import requests
from dotenv import load_dotenv

from i18n import t
from planner import checker, optimizer
from planner.schemas import PRIORITIES

load_dotenv()


def _cfg(name: str, default: str = "") -> str:
    """A setting from the environment (.env), else from Streamlit secrets (Streamlit Cloud), else the default."""
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st

        return str(st.secrets.get(name, default))
    except Exception:  # no secrets file, or not running under Streamlit
        return default


# All LLM settings in one place; override them in .env or in the app's Secrets.
PROVIDER = _cfg("LLM_PROVIDER", "anthropic")
# Claude: Sonnet 5 does not accept a temperature setting, so none is sent; every number is checked instead.
MODEL = _cfg("LLM_MODEL", "claude-sonnet-5" if PROVIDER == "anthropic" else "qwen2.5:7b-instruct")
# OpenAI-compatible: default is a local Ollama server. Open models do take temperature 0.
BASE_URL = _cfg("LLM_BASE_URL", "http://localhost:11434/v1")
API_KEY = _cfg("LLM_API_KEY", "")  # only needed for hosted providers
# OpenRouter only: models to try, in order, if LLM_MODEL is unavailable (free models come and go).
FALLBACK_MODELS = [m.strip() for m in _cfg("LLM_FALLBACK_MODELS", "").split(",") if m.strip()]
APP_URL = _cfg("APP_URL", "https://croptions.streamlit.app")
TEMPERATURE = 0.0
MAX_TOKENS = 4096
MAX_TOOL_ROUNDS = 5
REQUEST_TIMEOUT_S = 180  # local models on a laptop CPU can be slow

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


def llm_ready() -> tuple[bool, str]:
    """Is an LLM configured? -> (ready, i18n key explaining what is missing)."""
    if PROVIDER == "anthropic":
        return (bool(_cfg("ANTHROPIC_API_KEY")), "chat_no_key")
    if PROVIDER == "openai_compatible":
        if "openrouter.ai" in BASE_URL and not API_KEY:
            return (False, "chat_no_llm_key")
        return (bool(BASE_URL), "chat_no_base_url")
    return (False, "chat_bad_provider")


def call_llm(system: str, messages: list, tools: list, tool_choice: dict | None = None):
    """The only function that talks to an LLM. Returns an object with .stop_reason and .content blocks (Anthropic shape)."""
    if PROVIDER == "openai_compatible":
        return _call_openai_compatible(system, messages, tools, tool_choice)
    if PROVIDER != "anthropic":
        raise ValueError(f"Unknown LLM_PROVIDER {PROVIDER!r}; use 'anthropic' or 'openai_compatible'")
    global _client
    import anthropic

    if _client is None:
        _client = anthropic.Anthropic(api_key=_cfg("ANTHROPIC_API_KEY") or None)
    kwargs = {"tool_choice": tool_choice} if tool_choice else {}
    return _client.messages.create(model=MODEL, max_tokens=MAX_TOKENS, system=system, messages=messages, tools=tools, **kwargs)


def _field(block, name, default=None):
    """Read a content block field whether it is an SDK object, a SimpleNamespace or a dict."""
    return block.get(name, default) if isinstance(block, dict) else getattr(block, name, default)


def to_openai_messages(system: str, messages: list) -> list[dict]:
    """Our Anthropic-shaped history -> OpenAI chat messages (system, user, assistant with tool_calls, tool)."""
    out = [{"role": "system", "content": system}]
    for m in messages:
        content = m["content"]
        if isinstance(content, str):
            out.append({"role": m["role"], "content": content})
            continue
        if m["role"] == "user":  # a list here means tool results
            for block in content:
                if _field(block, "type") == "tool_result":
                    out.append({"role": "tool", "tool_call_id": _field(block, "tool_use_id"), "content": str(_field(block, "content"))})
            continue
        text = "\n".join(_field(b, "text", "") for b in content if _field(b, "type") == "text")
        calls = [
            {"id": _field(b, "id"), "type": "function", "function": {"name": _field(b, "name"), "arguments": json.dumps(_field(b, "input", {}))}}
            for b in content if _field(b, "type") == "tool_use"
        ]
        msg = {"role": "assistant", "content": text or None}
        if calls:
            msg["tool_calls"] = calls
        out.append(msg)
    return out


def from_openai_response(data: dict):
    """OpenAI chat completion JSON -> Anthropic-shaped response (stop_reason + text / tool_use blocks)."""
    choice = data["choices"][0]
    msg = choice.get("message", {})
    blocks = []
    if msg.get("content"):
        blocks.append(SimpleNamespace(type="text", text=msg["content"]))
    for i, call in enumerate(msg.get("tool_calls") or []):
        fn = call.get("function", {})
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {"_invalid_json": fn.get("arguments")}  # the tool call then fails and the model is told why
        blocks.append(SimpleNamespace(type="tool_use", id=call.get("id") or f"call_{i}", name=fn.get("name"), input=args))
    finish = choice.get("finish_reason")
    if any(b.type == "tool_use" for b in blocks):
        stop = "tool_use"
    elif finish == "length":
        stop = "max_tokens"
    else:
        stop = "end_turn"
    return SimpleNamespace(stop_reason=stop, content=blocks)


def _call_openai_compatible(system: str, messages: list, tools: list, tool_choice: dict | None):
    """POST /chat/completions to an OpenAI-compatible server (Ollama, llama.cpp, vLLM, Groq, OpenRouter...)."""
    payload = {
        "model": MODEL,
        "messages": to_openai_messages(system, messages),
        "tools": [{"type": "function", "function": {"name": x["name"], "description": x["description"], "parameters": x["input_schema"]}} for x in tools],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }
    if tool_choice and tool_choice.get("type") == "none":
        payload["tool_choice"] = "none"
    headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
    if "openrouter.ai" in BASE_URL:
        headers |= {"HTTP-Referer": APP_URL, "X-Title": "Croptions"}  # shows the app name in OpenRouter
        if FALLBACK_MODELS:
            payload["models"] = [MODEL, *FALLBACK_MODELS]  # OpenRouter tries these in order
    resp = requests.post(f"{BASE_URL.rstrip('/')}/chat/completions", json=payload, headers=headers, timeout=REQUEST_TIMEOUT_S)
    resp.raise_for_status()
    return from_openai_response(resp.json())


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

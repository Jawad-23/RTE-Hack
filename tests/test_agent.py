"""Agent tests with a fake call_llm, so they run offline and cost nothing."""

from types import SimpleNamespace as NS

import pytest

from planner import agent, climate

PLAN = {
    "inputs": {"lat": 25.0, "lon": 51.0, "area_m2": 500, "budget_qar": 250000, "priority": "profit", "crop": None},
    "site": {"lat": 25.0, "lon": 51.0},
    "recommended": {"crop": "tomato", "setup": "wet_pad", "coverage_pct": 100.0, "capex_qar": 150000.0, "payback_years": 6.0},
    "reason": "wet_pad for tomato keeps the crop below its heat limit 100.0% of the year.",
    "options": [], "calendar": {}, "sources": [], "assumptions": {},
}


def text(s):
    return NS(stop_reason="end_turn", content=[NS(type="text", text=s)])


def tool_call(name, args):
    return NS(stop_reason="tool_use", content=[NS(type="tool_use", id="t1", name=name, input=args)])


def script(monkeypatch, *responses):
    """Make call_llm return these responses in order and record what it was sent."""
    queue, calls = list(responses), []

    def fake(system, messages, tools, tool_choice=None):
        calls.append({"messages": list(messages), "tool_choice": tool_choice})
        return queue.pop(0)

    monkeypatch.setattr(agent, "call_llm", fake)
    return calls


def test_detect_language():
    assert agent.detect_language("لماذا هذا النظام؟") == "ar"
    assert agent.detect_language("Why this setup?") == "en"


def test_answer_from_current_plan_is_verified(monkeypatch):
    calls = script(monkeypatch, text("A wet-pad greenhouse: it costs 150,000 QAR and pays back in 6 years."))
    out = agent.ask("Why this setup?", [], PLAN)
    assert out["verified"] and out["language"] == "en" and out["plan"] is None
    assert "<current_plan>" in calls[0]["messages"][-1]["content"]


def test_invented_number_is_rewritten(monkeypatch):
    calls = script(monkeypatch, text("It pays back in 3.4 years."), text("It pays back in 6 years."))
    out = agent.ask("How fast does it pay back?", [], PLAN)
    assert out["verified"] and out["reply"] == "It pays back in 6 years."
    assert calls[1]["tool_choice"] == {"type": "none"}
    assert any("3.4" in line for line in out["tool_log"])


def test_repeated_invented_number_falls_back_to_template(monkeypatch):
    script(monkeypatch, text("It pays back in 3.4 years."), text("Still 3.4 years."))
    out = agent.ask("لماذا هذا النظام؟", [], PLAN)
    assert out["verified"] and out["language"] == "ar"
    assert "150,000" in out["reply"] and "3.4" not in out["reply"]


def test_tool_call_runs_planner_and_returns_new_plan(monkeypatch, dry_year):
    monkeypatch.setattr(climate, "get_typical_year", lambda lat, lon: dry_year)
    args = {"lat": 25.0, "lon": 51.0, "area_m2": 500, "budget_qar": 125000, "priority": "profit"}
    calls = script(monkeypatch, tool_call("run_plan", args), text("With half the budget, see the new plan."))
    out = agent.ask("What if my budget is half?", [], PLAN)
    assert out["plan"] is not None and out["plan"]["inputs"]["budget_qar"] == 125000
    assert out["tool_log"][0].startswith("run_plan(")
    tool_result = calls[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and tool_result["tool_use_id"] == "t1"


def test_api_failure_degrades_gracefully(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no API key")

    monkeypatch.setattr(agent, "call_llm", boom)
    out = agent.ask("Why?", [], PLAN)
    assert not out["verified"] and out["plan"] is None and "RuntimeError" in out["tool_log"][0]


def test_tool_loop_is_capped(monkeypatch, dry_year):
    monkeypatch.setattr(climate, "get_typical_year", lambda lat, lon: dry_year)
    args = {"lat": 25.0, "lon": 51.0, "area_m2": 500, "budget_qar": 250000, "priority": "profit"}
    script(monkeypatch, *[tool_call("run_plan", args) for _ in range(agent.MAX_TOOL_ROUNDS + 1)])
    out = agent.ask("Keep going", [], PLAN)
    assert any("stopped after" in line for line in out["tool_log"])


def test_compact_plan_is_json_safe_and_smaller(monkeypatch, dry_year):
    import json
    from planner import optimizer
    monkeypatch.setattr(climate, "get_typical_year", lambda lat, lon: dry_year)
    full = optimizer.plan(25.0, 51.0, 500, 250000, "profit")
    slim = agent.compact_plan(full)
    assert len(json.dumps(slim)) < len(json.dumps(full))
    assert "monthly_coverage_pct" not in json.dumps(slim)


def test_history_that_opens_with_the_summary_starts_with_a_user_turn(monkeypatch):
    calls = script(monkeypatch, text("The wet-pad greenhouse keeps it cool."))
    history = [{"role": "assistant", "content": "Here is your plan summary."}]
    agent.ask("Why?", history, PLAN)
    sent = calls[0]["messages"]
    assert sent[0]["role"] == "user" and sent[1]["role"] == "assistant"
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]


def test_system_prompt_names_every_setup():
    from planner.schemas import SETUPS
    assert all(s in agent.SYSTEM_PROMPT for s in SETUPS)

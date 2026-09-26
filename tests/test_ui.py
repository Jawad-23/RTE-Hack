"""Smoke tests: every page renders without an exception, in English and Arabic, with and without a plan."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from planner import climate

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PAGES = ["views/home.py", "views/plan.py", "views/results.py", "views/compare.py", "views/assumptions.py", "views/operate.py"]


@pytest.fixture
def offline(monkeypatch, humid_year, tmp_path):
    monkeypatch.setattr(climate, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(climate, "get_typical_year", lambda lat, lon, years=None: humid_year)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from planner import agent
    monkeypatch.setattr(agent, "llm_ready", lambda: (False, "chat_no_key"))  # never call a real LLM (a local .env may hold a key)


def run(page: str, lang: str = "en", plan: bool = False) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["lang"] = lang
    if plan:
        from planner import optimizer
        at.session_state["pin"] = (25.69, 51.50)
        at.session_state["plan"] = optimizer.plan(25.69, 51.50, 500, 250000, "profit")
    at.run()
    at.switch_page(page).run()
    return at


@pytest.mark.parametrize("lang", ["en", "ar"])
@pytest.mark.parametrize("page", PAGES)
def test_page_renders(offline, page, lang):
    at = run(page, lang, plan=True)
    assert not at.exception, at.exception


def test_results_without_plan_shows_empty_state(offline):
    at = run("views/results.py")
    assert not at.exception
    assert any("No plan yet" in m.value for m in at.markdown)


def test_results_verdict_uses_plan_numbers(offline):
    at = run("views/results.py", plan=True)
    plan = at.session_state["plan"]
    rec = plan["recommended"]
    text = " ".join(m.value for m in at.markdown)
    assert f"{rec['payback_years']:.1f}" in text
    assert f"{rec['capex_qar']:,.0f}" in text


def test_assumptions_without_plan_shows_world_prices(offline):
    at = run("views/assumptions.py")
    assert not at.exception, at.exception
    assert any("world median" in m.value for m in at.markdown)


def test_kit_dashboard_shows_phone_readings(offline):
    from ui import kit_ui
    at = run("views/operate.py", plan=True)
    assert not at.exception, at.exception
    code = at.session_state["_kit_code"]
    ctx = kit_ui.store().context(code)
    assert kit_ui.send(code, ctx, "heat_stress", None)["seq"] == 1
    at.run()
    assert not at.exception, at.exception
    assert at.session_state["_kit_seen"] == 1
    text = " ".join(m.value for m in at.markdown)
    assert "Leaf temperature" in text and "Water stress" in text


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_kit_remote_page(offline, lang):
    from ui import kit_ui
    code = kit_ui.store().create({"site": "Al Khor", "crop": "tomato", "setup": "wet_pad", "sim_day": 200,
                                  "day": [{"hour": h, "air_c": 30.0, "rh_pct": 50.0, "par_w_m2": 300.0 if 6 <= h <= 18 else 0.0,
                                           "outside_c": 35.0} for h in range(24)]})
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["lang"] = lang
    at.query_params["farm"] = code
    at.run()
    at.switch_page("views/kit_remote.py").run()
    assert not at.exception, at.exception
    at.button(key="remote_heat_stress").click().run()
    assert not at.exception, at.exception
    assert kit_ui.store().readings(code)[-1]["scenario"] == "heat_stress"


def test_results_shows_site_climate_and_kit_cost(offline):
    at = run("views/results.py", plan=True)
    text = " ".join(m.value for m in at.markdown)
    assert "What NASA measured at this site" in text
    if at.session_state["plan"]["recommended"]:
        assert "Build cost with kit" in text


def test_results_opens_with_assistant_summary_kit_and_investment(offline):
    at = run("views/results.py", plan=True)
    assert not at.exception, at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Your plan, explained" in text and "Investment scenarios" in text and "Feel the heat before your crop does" in text
    chat = at.session_state["chat"]
    assert chat and chat[0]["role"] == "assistant"  # the summary is the first message, before any question
    assert "Compare with another site" in text


def test_kit_page_has_no_simulation_tabs_or_qr(offline):
    at = run("views/operate.py", plan=True)
    assert not at.exception, at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Simulated day" not in [tab.label for tab in at.tabs]
    assert "QR" not in text and "Kit ID" in text


def test_menu_lists_kit_and_compare(offline):
    at = run("views/home.py")
    labels = " ".join(str(p.label) for p in at.get("page_link"))
    assert "Croptions Kit" in labels and "Compare sites" in labels
    assert any("Feel the heat" in m.value for m in at.markdown)


def test_kit_page_labels_demo_readings_and_shows_the_day_simulator(offline):
    from ui import kit_ui
    at = run("views/operate.py", plan=True)
    code = at.session_state["_kit_code"]
    kit_ui.send(code, kit_ui.store().context(code), "normal", 12)
    at.run()
    assert not at.exception, at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Demo reading" in text
    assert any("one simulated day" in e.label for e in at.expander)
    assert "Too hot with fixed shade" in text

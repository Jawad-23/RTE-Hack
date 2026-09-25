"""Smoke tests: every page renders without an exception, in English and Arabic, with and without a plan."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from planner import climate

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PAGES = ["views/home.py", "views/plan.py", "views/results.py", "views/compare.py", "views/assumptions.py"]


@pytest.fixture
def offline(monkeypatch, humid_year, tmp_path):
    monkeypatch.setattr(climate, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(climate, "get_typical_year", lambda lat, lon, years=None: humid_year)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


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

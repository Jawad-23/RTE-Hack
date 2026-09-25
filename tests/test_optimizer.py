import json

import pytest

from planner import climate, optimizer
from planner.schemas import MIN_COVERAGE_PCT, SETUPS


@pytest.fixture
def offline_climate(monkeypatch, humid_year):
    monkeypatch.setattr(climate, "get_typical_year", lambda lat, lon: humid_year)


def test_plan_is_json_safe_and_complete(offline_climate):
    p = optimizer.plan(25.3, 51.5, 500, 250_000, "profit")
    json.dumps(p)  # must not raise
    assert {"site", "recommended", "options", "calendar", "sources", "assumptions"} <= set(p)
    n_crops = len(p["assumptions"]["crops"])
    assert len(p["options"]) == n_crops * len(SETUPS)


def test_recommended_passes_and_is_best(offline_climate):
    p = optimizer.plan(25.3, 51.5, 500, 250_000, "profit")
    rec = p["recommended"]
    assert rec is not None and rec["passes"]
    assert rec["coverage_pct"] >= MIN_COVERAGE_PCT
    assert rec["capex_qar"] <= 250_000
    assert rec["profit_10y_qar"] == max(o["profit_10y_qar"] for o in p["options"] if o["passes"])


def test_zero_budget_gives_no_recommendation_with_reason(offline_climate):
    p = optimizer.plan(25.3, 51.5, 500, 0, "profit", crop="tomato")
    assert p["recommended"] is None
    assert "budget" in p["reason"]


def test_unknown_crop_gives_reason(offline_climate):
    p = optimizer.plan(25.3, 51.5, 500, 250_000, "profit", crop="banana")
    assert p["recommended"] is None and "banana" in p["reason"]


def test_missing_climate_gives_reason(monkeypatch):
    def unavailable(lat, lon):
        raise climate.ClimateUnavailable("NASA POWER unreachable")

    monkeypatch.setattr(climate, "get_typical_year", unavailable)
    p = optimizer.plan(25.3, 51.5, 500, 250_000, "profit")
    assert p["recommended"] is None and "NASA POWER" in p["reason"]


def test_bad_priority_rejected(offline_climate):
    with pytest.raises(ValueError):
        optimizer.plan(25.3, 51.5, 500, 250_000, "vibes")

"""Croptions Kit (simulated): readings, derived metrics, advice, costs, the shared inbox and the site climate card."""

import json

import numpy as np
import pytest

from planner import crops, kit, optimizer, site_climate
from planner.solar import load_settings


@pytest.fixture
def tomato():
    return {"crop": "tomato", **crops.load_crops().set_index("crop").loc["tomato"].to_dict()}


@pytest.fixture
def day(humid_year, tomato):
    return kit.day_conditions(humid_year, "wet_pad", 500, tomato, 200)


def test_day_conditions_has_24_inside_hours(day):
    assert [h["hour"] for h in day] == list(range(24))
    assert all(h["air_c"] <= h["outside_c"] + 1e-6 for h in day if h["par_w_m2"] == 0)  # pads never heat the air at night


def test_day_conditions_rejects_bad_day(humid_year, tomato):
    with pytest.raises(ValueError):
        kit.day_conditions(humid_year, "wet_pad", 500, tomato, 366)


@pytest.mark.parametrize("scenario", kit.scenarios())
def test_every_scenario_makes_a_labelled_json_safe_reading(day, tomato, scenario):
    reading = kit.simulate_reading(day, None, scenario, np.random.default_rng(0))
    assert reading["source"] == "simulated" and reading["scenario"] == scenario
    json.dumps({**reading, **kit.derive(reading, tomato)})


def test_cwsi_follows_the_scenario_stress(day, tomato):
    cfg = {**load_settings(), "kit_noise_temp_c": 0, "kit_noise_rh_pct": 0, "kit_noise_par_fraction": 0}
    normal = kit.derive(kit.simulate_reading(day, 12, "normal", cfg=cfg), tomato, cfg)
    stressed = kit.derive(kit.simulate_reading(day, 14, "heat_stress", cfg=cfg), tomato, cfg)
    assert normal["cwsi"] == pytest.approx(kit.load_scenarios().loc["normal", "leaf_stress_fraction"], abs=0.01)
    assert stressed["cwsi"] > normal["cwsi"]
    assert "water_stress" in stressed["alerts"] and "water_stress" not in normal["alerts"]


def test_night_has_no_cwsi_and_humid_night_warns_of_condensation(day, tomato):
    d = kit.derive(kit.simulate_reading(day, None, "humid_night", np.random.default_rng(1)), tomato)
    assert d["cwsi"] is None and d["cwsi_reason"]
    assert "condensation" in d["alerts"]


def test_dew_point_matches_air_at_saturation():
    assert kit.dew_point_c(30, 100) == pytest.approx(30, abs=0.01)
    assert kit.dew_point_c(30, 50) == pytest.approx(18.4, abs=0.3)


def test_recommend_uses_the_shared_controller(tomato):
    hot = {"air_c": 40.0, "par_w_m2": 400.0}
    cfg = load_settings()
    assert kit.recommend(hot, tomato, 0) == {"screen_pct": cfg["screen_max_pct"], "reason": "reduce_heat"}
    assert kit.recommend({"air_c": 25.0, "par_w_m2": 0.0}, tomato, 80)["screen_pct"] == 0


def test_dli_so_far_counts_latest_reading_per_hour():
    cfg = load_settings()
    readings = [{"sim_day": 1, "sim_hour": 12, "par_w_m2": 100}, {"sim_day": 1, "sim_hour": 12, "par_w_m2": 200},
                {"sim_day": 1, "sim_hour": 13, "par_w_m2": 100}, {"sim_day": 2, "sim_hour": 13, "par_w_m2": 999}]
    assert kit.dli_so_far(readings, 1, cfg) == pytest.approx(300 * 3600 * cfg["par_umol_j"] / 1e6, abs=0.01)


def test_thermal_grid_mean_leaf_matches_reading():
    image = kit.thermal_grid({"leaf_c": 33.0, "air_c": 30.0, "par_w_m2": 300}, seed=4)
    assert image.shape == kit.GRID_SHAPE
    assert 30 < image.mean() < 34


def test_costs_add_kit_to_plan():
    cfg = load_settings()
    out = kit.costs(1200, {"capex_qar": 100000.0, "profit_qar_year": 20000.0})
    pods = int(np.ceil(1200 / cfg["kit_pod_area_m2"]))
    assert out["pods"] == pods
    assert out["capex_with_kit_qar"] == pytest.approx(100000 + pods * cfg["kit_pod_price_qar"])
    assert out["payback_with_kit_years"] == pytest.approx(out["capex_with_kit_qar"] / out["profit_with_kit_qar_year"], abs=0.01)
    assert kit.costs(500, None)["capex_with_kit_qar"] is None and kit.costs(500, None)["reason"]


def test_store_round_trip_and_unknown_code():
    store = kit.KitStore()
    code = store.create({"site": "x"})
    assert len(code) == 4 and store.context(code) == {"site": "x"}
    first, second = store.push(code, {"leaf_c": 30}), store.push(code, {"leaf_c": 31})
    assert (first["seq"], second["seq"]) == (1, 2) and first["farm_code"] == code
    assert [r["seq"] for r in store.readings(code, after_seq=1)] == [2]
    assert store.push("0000" if code != "0000" else "0001", {}) is None


def test_site_climate_summary(humid_year):
    table = crops.load_crops()
    out = site_climate.summary(humid_year, table)
    assert set(out["hours_above_limit_outdoor"]) == set(table["crop"])
    assert out["heat_share_pct"] == pytest.approx(50, abs=0.1)
    assert out["haze_loss_pct"] is None and out["missing"]  # the synthetic year has no clear-sky column
    assert len(out["monthly_et0_mm_day"]) == 12 and out["et0_mm_day"] > 0


def test_plan_carries_site_climate_and_kit(monkeypatch, humid_year, tmp_path):
    from planner import climate
    monkeypatch.setattr(climate, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(climate, "get_typical_year", lambda lat, lon, years=None: humid_year)
    plan = optimizer.plan(25.69, 51.50, 500, 250000, "profit")
    assert "dli_outdoor_mol_m2_day" in plan["site"] and "kit" in plan
    json.dumps(plan)

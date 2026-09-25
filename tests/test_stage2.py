import json

import numpy as np
import pandas as pd
import pytest

from planner import agronomy, climate, controller, cooling, dust, operate, optimizer, scan, solar


def test_spectral_unit_conversion_and_partition():
    from tests.test_climate import fake_power_payload
    payload = fake_power_payload(2023, "MJ/hr")
    keys = payload["properties"]["parameter"]["T2M"]
    for name in climate.SPECTRAL_PARAMS:
        payload["properties"]["parameter"][name] = {key: 0.1 for key in keys}
        payload["parameters"][name] = {"units": "MJ/hr"}
    typical = climate.build_typical_year(climate.parse_power_json(payload))
    assert typical["par_w_m2"].iloc[0] == pytest.approx(100000 / 3600)
    assert np.allclose(typical["par_w_m2"] + typical["uv_w_m2"] + typical["nir_w_m2"], typical["ghi_wh_m2"])


def test_night_heat_share_is_undefined():
    from tests.test_climate import fake_power_payload
    hourly = climate.parse_power_json(fake_power_payload(2023))
    for col in climate.SPECTRAL_PARAMS.values():
        hourly[col] = 0.0
    hourly["ghi_wh_m2"] = 0
    typical = climate.build_typical_year(hourly)
    assert typical["heat_share"].isna().all()
    assert typical["nir_w_m2"].eq(0).all()


def test_controller_bounds_light_guard_and_hysteresis():
    cfg = solar.load_settings()
    crop = {"t_max_c": 35}
    state = {"screen_pct": 0}
    for _ in range(20):
        state = controller.decide({"temp_c": 45, "par_w_m2": 400}, crop, state, cfg)
    assert state["screen_pct"] == 80
    lower = controller.decide({"temp_c": 45, "par_w_m2": 50}, crop, state, cfg)
    assert lower == {"screen_pct": 70, "reason": "protect_light"}
    night = controller.decide({"temp_c": 40, "par_w_m2": 0}, crop, state, cfg)
    assert night["screen_pct"] == 0
    held = controller.decide({"temp_c": 31, "par_w_m2": 400}, crop, state, cfg)
    assert held["screen_pct"] == state["screen_pct"]


def test_humidity_and_dli_are_physical(dry_year):
    p = cooling.hourly_profile(dry_year, "wet_pad", 500)
    assert p["inside_rh_pct"].between(0, 100).all()
    assert p["vpd_kpa"].ge(0).all()
    assert p["inside_rh_pct"].mean() > dry_year["rh_pct"].mean()
    known = p.iloc[:24].copy()
    known["par_inside_w_m2"] = 100
    m = agronomy.metrics(known, {"dli_min_mol_m2_day": 30, "vpd_max_kpa": 2}, [1])
    assert m["dli_mean_mol_m2_day"] == pytest.approx(100 * 86400 * 4.57 / 1e6, abs=.01)
    assert m["light_ok_pct"] == 100


def test_missing_or_insufficient_light_excludes_recommendation(monkeypatch, humid_year):
    dim = humid_year.copy()
    dim["par_w_m2"] = 1.0
    monkeypatch.setattr(climate, "get_typical_year", lambda *a: dim)
    p = optimizer.plan(25, 51, 500, 1000000, "profit", "tomato")
    assert p["recommended"] is None
    assert any("light sufficiency" in r for o in p["options"] for r in o["fail_reasons"])
    dim.drop(columns="par_w_m2", inplace=True)
    p = optimizer.plan(25, 51, 500, 1000000, "profit", "tomato")
    assert all(o["light_ok_pct"] is None and not o["passes"] for o in p["options"])
    json.dumps(p, allow_nan=False)


def test_grid_import_includes_night_cooling(monkeypatch, humid_year):
    monkeypatch.setattr(climate, "get_typical_year", lambda *a: humid_year)
    p = optimizer.plan(25, 51, 500, 1000000, "profit", "tomato")
    chiller = next(o for o in p["options"] if o["setup"] == "chiller")
    assert chiller["grid_kwh_year"] > 0
    assert chiller["opex_qar_year"] > 500 * cooling.load_setups().loc["chiller", "opex_qar_m2_year"]


def test_cleaning_tradeoff_and_failure(monkeypatch):
    weekly, monthly = dust.cleaning_scenario(500, 7), dust.cleaning_scenario(500, 30)
    assert weekly["loss_fraction"].mean() < monthly["loss_fraction"].mean()
    assert weekly["cleaning_cost_qar_year"] > monthly["cleaning_cost_qar_year"]
    def fail(*a, **k):
        raise dust.requests.ConnectionError("offline")
    monkeypatch.setattr(dust.requests, "get", fail)
    assert dust.recent_exposure(25, 51)["available"] is False


def test_operate_energy_and_resolution(dry_year):
    crop = {"t_max_c": 35}
    frame = operate.simulate_day(dry_year, 200, crop, 500)
    assert len(frame) == 144 and frame["time"].iloc[-1] == "23:50"
    hourly = dry_year.iloc[199*24:200*24]
    expected = cooling.hourly_profile(hourly, "agrivoltaic_fixed", 500, crop)["pv_kwh"].sum()
    assert frame["fixed_pv_kwh"].sum() == pytest.approx(expected)
    assert frame["screen_pct"].between(0, 80).all()


def test_grid_cap_and_bounds():
    assert len(scan.grid(25, 51, 26, 52, 5)) == 25
    with pytest.raises(ValueError):
        scan.grid(25, 51, 26, 52, 6)
    with pytest.raises(ValueError):
        scan.grid(26, 51, 25, 52)


@pytest.mark.parametrize("args", [(91, 51, 500, 10), (25, 51, -1, 10), (25, 51, 1, -10), (25, 51, float('nan'), 10)])
def test_invalid_inputs_rejected(args):
    with pytest.raises(ValueError):
        optimizer.plan(*args, "profit")

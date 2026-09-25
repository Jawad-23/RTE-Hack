import pandas as pd
import pytest

from planner import crops, economics, solar


@pytest.fixture
def tiny_data(tmp_path, monkeypatch):
    """Small CSVs with round numbers so the expected results are easy to check by hand."""
    pd.DataFrame([{"crop": "tomato", "t_min_c": 10, "t_opt_min_c": 20, "t_opt_max_c": 27, "t_max_c": 35,
                   "yield_kg_m2_year": 10, "water_l_m2_day": 5, "source": "test"}]).to_csv(tmp_path / "crops.csv", index=False)
    pd.DataFrame([{"crop": "tomato", "price_qar_kg": 15, "source": "test", "year": 2024}]).to_csv(tmp_path / "prices.csv", index=False)
    pd.DataFrame([{"setup": "wet_pad", "capex_qar_m2": 400, "opex_qar_m2_year": 30, "shade_drop_c": 0, "pad_efficiency": 0.8,
                   "solar_gain_c": 4, "setpoint_c": 0, "chiller_kw_per_m2_per_c": 0, "cop": 0, "water_l_m2_day_extra": 8,
                   "yield_factor": 1.0, "source": "test"}]).to_csv(tmp_path / "setups.csv", index=False)
    pd.DataFrame([{"key": "solar_capex_qar_kw", "value": 2500, "unit": "QAR/kW", "source": "test"},
                  {"key": "performance_ratio", "value": 0.8, "unit": "fraction", "source": "test"}]).to_csv(tmp_path / "settings.csv", index=False)
    monkeypatch.setattr(economics, "DATA_DIR", tmp_path)
    return tmp_path


def test_payback_matches_hand_calculation(tiny_data):
    # capex = 500 × 400 = 200,000; revenue = 500 × 10 × 15 = 75,000; opex = 500 × 30 = 15,000; profit = 60,000
    out = economics.evaluate("wet_pad", "tomato", 500, 12, 0, 0)
    assert out["capex_qar"] == 200_000
    assert out["profit_qar_year"] == 60_000
    assert out["payback_years"] == 3.33
    assert out["profit_10y_qar"] == 400_000
    assert out["water_l_day"] == 500 * (5 + 8)


def test_revenue_scales_with_growing_months_and_solar_adds_capex(tiny_data):
    half = economics.evaluate("wet_pad", "tomato", 500, 6, 0, 10)
    assert half["revenue_qar_year"] == 37_500
    assert half["capex_qar"] == 200_000 + 10 * 2500


def test_no_profit_means_no_payback(tiny_data):
    assert economics.evaluate("wet_pad", "tomato", 500, 0, 0, 0)["payback_years"] is None


def test_missing_crop_returns_none_with_reason(tiny_data):
    out = economics.evaluate("wet_pad", "banana", 500, 12, 0, 0)
    assert out["capex_qar"] is None and "banana" in out["reason"]


def test_evaluate_outputs_are_plain_floats():
    out = economics.evaluate("chiller", "tomato", 500, 12, 1000, 5)
    assert all(v is None or type(v) is float for v in out.values())


def test_zero_cooling_needs_no_solar(dry_year):
    assert solar.size_solar(0, dry_year)["solar_kw"] == 0


def test_solar_sized_to_cover_peak_day(dry_year):
    out = solar.size_solar(100, dry_year)
    pr = solar.load_settings()["performance_ratio"]
    assert out["solar_kw"] * out["peak_sun_hours"] * pr == pytest.approx(100, rel=0.01)


def test_45c_month_is_impossible_for_lettuce(dry_year):
    hot = dry_year.copy()
    hot.loc[hot["month"] == 7, "temp_c"] = 45.0
    lettuce = crops.load_crops().query("crop == 'lettuce'")
    assert crops.crop_calendar(hot, lettuce).loc["lettuce", 7] == "impossible"


def test_status_bands():
    assert crops.crop_status(30, 15, 10, 35) == "good"
    assert crops.crop_status(37, 15, 10, 35) == "risky"
    assert crops.crop_status(39, 15, 10, 35) == "impossible"
    assert crops.crop_status(30, 5, 10, 35) == "impossible"


def test_calendar_shape(dry_year):
    cal = crops.crop_calendar(dry_year, crops.load_crops())
    assert list(cal.columns) == list(range(1, 13))
    assert set(cal.to_numpy().ravel()) <= {"good", "risky", "impossible"}

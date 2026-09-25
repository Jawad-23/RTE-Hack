import numpy as np
import pandas as pd
import pytest

from planner import climate
from planner.schemas import CLIMATE_COLUMNS, HOURS_PER_YEAR


def fake_power_payload(year: int, ghi_units: str = "Wh/m^2") -> dict:
    stamps = pd.date_range(f"{year}-01-01", f"{year}-12-31 23:00", freq="h")
    keys = [s.strftime("%Y%m%d%H") for s in stamps]
    temp = {k: 30.0 for k in keys}
    temp[keys[5]] = -999.0  # fill value
    return {
        "properties": {"parameter": {
            "T2M": temp,
            "RH2M": {k: 40.0 for k in keys},
            "ALLSKY_SFC_SW_DWN": {k: 0.5 for k in keys},
            "WS2M": {k: 3.0 for k in keys},
        }},
        "parameters": {"ALLSKY_SFC_SW_DWN": {"units": ghi_units}},
    }


def test_parse_marks_fill_values_as_nan():
    df = climate.parse_power_json(fake_power_payload(2023))
    assert df["temp_c"].isna().sum() == 1
    assert df["ghi_wh_m2"].iloc[0] == pytest.approx(0.5)


def test_parse_converts_kwh_to_wh():
    df = climate.parse_power_json(fake_power_payload(2023, "kW-hr/m^2"))
    assert df["ghi_wh_m2"].iloc[0] == pytest.approx(500.0)


def test_parse_rejects_unknown_units():
    with pytest.raises(ValueError):
        climate.parse_power_json(fake_power_payload(2023, "furlongs"))


def test_typical_year_has_8760_rows_and_no_gaps():
    hourly = pd.concat([climate.parse_power_json(fake_power_payload(y)) for y in (2023, 2024)])  # 2024 is a leap year
    typical = climate.build_typical_year(hourly)
    assert list(typical.columns) == CLIMATE_COLUMNS
    assert len(typical) == HOURS_PER_YEAR
    assert not typical.isna().any().any()
    assert typical["hour_of_year"].tolist() == list(range(HOURS_PER_YEAR))
    assert np.allclose(typical["temp_c"], 30.0)


def test_get_typical_year_uses_cache_and_reports_missing_data(tmp_path, monkeypatch, dry_year):
    monkeypatch.setattr(climate, "CACHE_DIR", tmp_path)
    dry_year.to_csv(climate.cache_path(1.0, 2.0), index=False)
    assert len(climate.get_typical_year(1.0, 2.0)) == HOURS_PER_YEAR

    def offline(*_a, **_k):
        raise climate.requests.ConnectionError("offline")

    monkeypatch.setattr(climate.requests, "get", offline)
    monkeypatch.setattr(climate.time, "sleep", lambda _s: None)
    with pytest.raises(climate.ClimateUnavailable):
        climate.get_typical_year(3.0, 4.0, years=[2023])


def test_offline_gives_up_after_first_year(tmp_path, monkeypatch):
    monkeypatch.setattr(climate, "CACHE_DIR", tmp_path)
    calls = []

    def offline(*_a, **_k):
        calls.append(1)
        raise climate.requests.ConnectionError("offline")

    monkeypatch.setattr(climate.requests, "get", offline)
    monkeypatch.setattr(climate.time, "sleep", lambda _s: None)
    with pytest.raises(climate.ClimateUnavailable):
        climate.get_typical_year(5.0, 6.0, years=[2021, 2022, 2023])
    assert len(calls) == climate.RETRIES  # one year's retries, not all three years'

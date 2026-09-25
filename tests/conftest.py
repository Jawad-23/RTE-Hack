"""Shared fixtures: synthetic climate tables so tests never call NASA POWER."""

import numpy as np
import pandas as pd
import pytest

from planner.schemas import CLIMATE_COLUMNS, HOURS_PER_YEAR


def synthetic_year(summer_max_c: float = 45.0, rh_pct: float = 20.0) -> pd.DataFrame:
    """A smooth fake typical year: hot summer, cool winter, daily cycle, sun from 6 to 18 h."""
    hours = np.arange(HOURS_PER_YEAR)
    stamps = pd.date_range("2001-01-01", periods=HOURS_PER_YEAR, freq="h")
    day, hour = hours // 24, stamps.hour.to_numpy()
    seasonal = np.cos((day - 200) / 365 * 2 * np.pi)          # +1 mid-July, -1 mid-January
    daily = np.cos((hour - 15) / 24 * 2 * np.pi)              # peak at 15:00
    temp = (summer_max_c - 10) + 8 * seasonal + 6 * daily - 2  # daily max ≈ summer_max_c in July
    sun = np.clip(np.sin((hour - 6) / 12 * np.pi), 0, None)
    df = pd.DataFrame({
        "hour_of_year": hours,
        "month": stamps.month.to_numpy(),
        "temp_c": temp,
        "rh_pct": np.full(HOURS_PER_YEAR, rh_pct),
        "ghi_wh_m2": 900 * sun,
        "wind_ms": np.full(HOURS_PER_YEAR, 3.0),
    })
    df["par_w_m2"] = df["ghi_wh_m2"] * 0.45
    df["heat_share"] = 0.5
    return df


@pytest.fixture
def dry_year():
    return synthetic_year(rh_pct=15.0)


@pytest.fixture
def humid_year():
    return synthetic_year(rh_pct=60.0)


@pytest.fixture(autouse=True)
def offline_market(monkeypatch):
    """Tests use the committed FAOSTAT snapshot and a fixed country, never the network."""
    from planner import market

    monkeypatch.setattr(market, "load_price_table", lambda refresh=True: market._read_table(market.SNAPSHOT_CSV))
    monkeypatch.setattr(market, "country_for", lambda lat, lon: {"name": "Qatar", "m49": 634})

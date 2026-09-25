"""Wet-bulb physics and the 8,760-hour inside-temperature simulation. Owned by Me.

Parameters for each setup come from data/setups.csv, never from code.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from planner.schemas import SETUPS

try:
    import psychrolib

    psychrolib.SetUnitSystem(psychrolib.SI)
except ImportError:  # pragma: no cover - falls back to the Stull formula below
    psychrolib = None

SETUPS_CSV = Path(__file__).resolve().parent.parent / "data" / "setups.csv"
SEA_LEVEL_PA = 101325.0


@lru_cache(maxsize=1)
def load_setups() -> pd.DataFrame:
    """data/setups.csv -> DataFrame indexed by setup name."""
    df = pd.read_csv(SETUPS_CSV).set_index("setup")
    unknown = set(df.index) - set(SETUPS)
    if unknown:
        raise ValueError(f"Unknown setups in {SETUPS_CSV.name}: {sorted(unknown)}")
    return df


def wet_bulb_c(temp_c, rh_pct) -> np.ndarray:
    """Air temperature (°C) and relative humidity (%) -> wet-bulb temperature (°C), elementwise."""
    temp_c = np.asarray(temp_c, dtype=float)
    rh_pct = np.clip(np.asarray(rh_pct, dtype=float), 1.0, 100.0)
    if psychrolib is not None:
        return np.vectorize(
            lambda t, rh: psychrolib.GetTWetBulbFromRelHum(t, rh / 100.0, SEA_LEVEL_PA)
        )(temp_c, rh_pct)
    # Stull (2011); valid for RH 5–99 % and T -20–50 °C
    return (
        temp_c * np.arctan(0.151977 * np.sqrt(rh_pct + 8.313659))
        + np.arctan(temp_c + rh_pct)
        - np.arctan(rh_pct - 1.676331)
        + 0.00391838 * rh_pct**1.5 * np.arctan(0.023101 * rh_pct)
        - 4.686035
    )


def hourly_profile(climate_df: pd.DataFrame, setup: str, area_m2: float) -> pd.DataFrame:
    """Climate table + setup + farm area (m²) -> hourly DataFrame: outside_c, wet_bulb_c, inside_c, cooling_kwh."""
    if setup not in SETUPS:
        raise ValueError(f"Unknown setup {setup!r}; expected one of {SETUPS}")
    p = load_setups().loc[setup]

    t = climate_df["temp_c"].to_numpy(dtype=float)
    tw = _wet_bulb_cached(climate_df)
    sunny = climate_df["ghi_wh_m2"].to_numpy(dtype=float) > 0
    # Solar heat gain inside a closed greenhouse only applies while the sun is up.
    wet_pad_c = t - p["pad_efficiency"] * (t - tw) + p["solar_gain_c"] * sunny

    cooling_kwh = np.zeros_like(t)
    if setup == "open_field":
        inside = t
    elif setup == "shade_net":
        inside = t - p["shade_drop_c"]
    elif setup == "wet_pad":
        inside = wet_pad_c
    else:  # chiller: wet pads first, the chiller removes whatever is left above the setpoint
        excess_c = np.clip(wet_pad_c - p["setpoint_c"], 0, None)
        inside = np.where(excess_c > 0, p["setpoint_c"], wet_pad_c)
        cooling_kwh = area_m2 * p["chiller_kw_per_m2_per_c"] * excess_c / p["cop"]

    return pd.DataFrame(
        {
            "hour_of_year": climate_df["hour_of_year"].to_numpy(),
            "month": climate_df["month"].to_numpy(),
            "outside_c": t,
            "wet_bulb_c": tw,
            "inside_c": inside,
            "cooling_kwh": cooling_kwh,
        }
    )


def simulate(climate_df: pd.DataFrame, setup: str, crop_limit_c: float, area_m2: float) -> dict:
    """Climate table, setup name, crop t_max_c (°C), area (m²) -> inside_temp_c (8,760 °C), coverage_pct, cooling_kwh_year, cooling_kwh_peak_day."""
    prof = hourly_profile(climate_df, setup, area_m2)
    daily_kwh = prof["cooling_kwh"].groupby(prof["hour_of_year"] // 24).sum()
    return {
        "inside_temp_c": [round(float(v), 2) for v in prof["inside_c"]],
        "coverage_pct": round(float((prof["inside_c"] < crop_limit_c).mean() * 100), 2),
        "cooling_kwh_year": round(float(prof["cooling_kwh"].sum()), 2),
        "cooling_kwh_peak_day": round(float(daily_kwh.max()), 2),
    }


def monthly_coverage_pct(inside_temp_c, months, crop_limit_c: float) -> dict[int, float]:
    """Hourly inside temps (°C) + month per hour -> {month: % of hours below crop_limit_c}."""
    s = pd.Series(np.asarray(inside_temp_c) < crop_limit_c, index=np.asarray(months))
    return {int(m): round(float(v * 100), 2) for m, v in s.groupby(level=0).mean().items()}


_WB_CACHE: dict[int, np.ndarray] = {}


def _wet_bulb_cached(climate_df: pd.DataFrame) -> np.ndarray:
    """Wet-bulb is the slow step; compute it once per climate table (4 setups × 8 crops reuse it)."""
    t = climate_df["temp_c"].to_numpy(dtype=float)
    rh = climate_df["rh_pct"].to_numpy(dtype=float)
    key = hash((t.tobytes(), rh.tobytes()))
    if key not in _WB_CACHE:
        _WB_CACHE.clear()
        _WB_CACHE[key] = wet_bulb_c(t, rh)
    return _WB_CACHE[key]

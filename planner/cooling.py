"""Wet-bulb physics and the 8,760-hour inside-temperature simulation. Owned by Me.

Parameters for each setup come from data/setups.csv, never from code.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from planner.schemas import SETUPS
from planner import agronomy, controller
from planner.solar import load_settings

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


def hourly_profile(climate_df: pd.DataFrame, setup: str, area_m2: float, crop=None) -> pd.DataFrame:
    """Climate table + setup + farm area (m²) -> hourly DataFrame: outside_c, wet_bulb_c, inside_c, cooling_kwh, inside_rh_pct, pad_moisture_kg_kg, ..."""
    if setup not in SETUPS:
        raise ValueError(f"Unknown setup {setup!r}; expected one of {SETUPS}")
    p = load_setups().loc[setup]

    t = climate_df["temp_c"].to_numpy(dtype=float)
    tw = _wet_bulb_cached(climate_df)
    sunny = climate_df["ghi_wh_m2"].to_numpy(dtype=float) > 0
    cfg = load_settings()
    screen = np.zeros(len(t))
    reasons = ["fixed"] * len(t)
    if setup == "agrivoltaic_louver":
        previous = {"screen_pct": 0}
        for i, row in enumerate(climate_df.to_dict("records")):
            previous = controller.decide(row, crop or {"t_max_c": 35}, previous, cfg)
            screen[i], reasons[i] = previous["screen_pct"], previous["reason"]
    par = climate_df.get("par_w_m2", pd.Series(np.nan, index=climate_df.index)).to_numpy(dtype=float)
    transmission = float(p["par_transmission"]) * (1 - screen / 100 * float(p["screen_max_light_loss"]))
    gain = p["solar_gain_c"] * sunny
    if setup == "nir_screen_wet_pad":
        heat_share = climate_df.get("heat_share", pd.Series(np.nan, index=climate_df.index)).fillna(0).to_numpy()
        gain = gain * (1 - heat_share * (1 - float(p["nir_transmission"])))
    # Solar heat gain inside a closed greenhouse only applies while the sun is up.
    wet_pad_c = t - p["pad_efficiency"] * (t - tw) + gain

    cooling_kwh = np.zeros_like(t)
    if setup == "open_field":
        inside = t
    elif setup in ("shade_net", "agrivoltaic_fixed"):
        inside = t - p["shade_drop_c"] * sunny
    elif setup == "agrivoltaic_louver":
        inside = t - p["shade_drop_c"] * screen / 100
    elif setup in ("wet_pad", "nir_screen_wet_pad"):
        inside = wet_pad_c
    else:  # chiller: wet pads first, the chiller removes whatever is left above the setpoint
        excess_c = np.clip(wet_pad_c - p["setpoint_c"], 0, None)
        inside = np.where(excess_c > 0, p["setpoint_c"], wet_pad_c)
        cooling_kwh = area_m2 * p["chiller_kw_per_m2_per_c"] * excess_c / p["cop"]

    # Evaporative cooling adds moisture. Approximate constant moist-air enthalpy
    # across the pad; clip condensation to saturation after mechanical cooling.
    vapour = agronomy.saturation_kpa(t) * climate_df["rh_pct"].to_numpy() / 100
    ratio = 0.62198 * vapour / (SEA_LEVEL_PA / 1000 - vapour)
    pad_t = t - p["pad_efficiency"] * (t - tw)
    enthalpy = 1.006 * t + ratio * (2501 + 1.86 * t)
    pad_ratio = np.maximum(ratio, (enthalpy - 1.006 * pad_t) / (2501 + 1.86 * pad_t))
    vapour = pad_ratio * (SEA_LEVEL_PA / 1000) / (0.62198 + pad_ratio)
    saturation = agronomy.saturation_kpa(inside)
    rh = np.clip(vapour / saturation * 100, 0, 100)
    pv_factor = np.ones(len(t))
    if setup == "agrivoltaic_louver":
        pv_factor = cfg["pv_louver_open_output_fraction"] + (1 - cfg["pv_louver_open_output_fraction"]) * screen / 100
    pv = area_m2 * float(p["pv_kw_m2"]) * climate_df["ghi_wh_m2"].to_numpy() / 1000 * cfg["performance_ratio"] * pv_factor

    return pd.DataFrame(
        {
            "hour_of_year": climate_df["hour_of_year"].to_numpy(),
            "month": climate_df["month"].to_numpy(),
            "outside_c": t,
            "wet_bulb_c": tw,
            "inside_c": inside,
            "cooling_kwh": cooling_kwh,
            "inside_rh_pct": rh,
            "pad_moisture_kg_kg": pad_ratio - ratio,  # water the pads evaporate per kg of air (0 without pads)
            "vpd_kpa": saturation * (1 - rh / 100),
            "par_inside_w_m2": par * transmission,
            "screen_pct": screen,
            "screen_reason": reasons,
            "pv_kwh": pv,
        }
    )


def simulate(climate_df: pd.DataFrame, setup: str, crop_limit_c: float, area_m2: float, crop=None) -> dict:
    """Climate table, setup name, crop t_max_c (°C), area (m²) -> inside_temp_c (8,760 °C), coverage_pct, cooling_kwh_year, cooling_kwh_peak_day."""
    prof = hourly_profile(climate_df, setup, area_m2, crop)
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

"""Solar panel sizing for the cooling load. Owned by Mustafa."""

from pathlib import Path

import pandas as pd

SETTINGS_CSV = Path(__file__).resolve().parent.parent / "data" / "settings.csv"


def load_settings() -> dict:
    """data/settings.csv -> {key: float value}."""
    df = pd.read_csv(SETTINGS_CSV)
    return {k: float(v) for k, v in zip(df["key"], df["value"])}


def size_solar(cooling_kwh_peak_day: float, climate_df: pd.DataFrame) -> dict:
    """Peak-day cooling energy (kWh) + climate table -> solar_kw, solar_kwh_year, peak_sun_hours (kWh/m²/day)."""
    peak_sun_hours = float(climate_df["ghi_wh_m2"].sum() / 1000 / 365)
    if cooling_kwh_peak_day <= 0 or peak_sun_hours <= 0:
        return {"solar_kw": 0.0, "solar_kwh_year": 0.0, "peak_sun_hours": round(peak_sun_hours, 2)}
    pr = load_settings()["performance_ratio"]
    solar_kw = cooling_kwh_peak_day / (peak_sun_hours * pr)
    return {
        "solar_kw": round(solar_kw, 2),
        "solar_kwh_year": round(solar_kw * peak_sun_hours * pr * 365, 2),
        "peak_sun_hours": round(peak_sun_hours, 2),
    }

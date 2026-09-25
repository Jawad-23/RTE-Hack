"""Numbers for the results and compare pages, derived from the planner's own physics. Owned by Me.

Nothing here invents a value: every function summarises cooling.hourly_profile() or the plan.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from planner import cooling, solar
from planner.schemas import MIN_COVERAGE_PCT, SETUPS


def monthly_inside_max(climate_df: pd.DataFrame, area_m2: float) -> pd.DataFrame:
    """Climate table + area -> DataFrame (index month 1–12): average daily maximum temperature (°C) outside and inside each setup."""
    out = {}
    for setup in SETUPS:
        prof = cooling.hourly_profile(climate_df, setup, area_m2)
        daily = prof.groupby(prof["hour_of_year"] // 24).agg(month=("month", "first"), inside=("inside_c", "max"), outside=("outside_c", "max"))
        out[setup] = daily.groupby("month")["inside"].mean()
        out["outside"] = daily.groupby("month")["outside"].mean()
    return pd.DataFrame(out)


def months_above(monthly: pd.Series, limit_c: float) -> list[int]:
    """Months whose average daily maximum is above the crop limit."""
    return [int(m) for m, v in monthly.items() if v > limit_c]


def hottest_day(climate_df: pd.DataFrame, area_m2: float, solar_kw: float) -> dict:
    """The day with the most chiller cooling: hourly cooling electricity (kWh) and solar output (kWh) for that day."""
    prof = cooling.hourly_profile(climate_df, "chiller", area_m2)
    day_kwh = prof["cooling_kwh"].groupby(prof["hour_of_year"] // 24).sum()
    day = int(day_kwh.idxmax())
    hours = slice(day * 24, day * 24 + 24)
    pr = solar.load_settings()["performance_ratio"]
    ghi = climate_df["ghi_wh_m2"].to_numpy()[hours]
    solar_kwh = solar_kw * ghi / 1000 * pr  # kW of panels × kWh/m² of sunlight × performance ratio
    cooling_kwh = prof["cooling_kwh"].to_numpy()[hours]
    month = int(climate_df["month"].iloc[day * 24])
    return {
        "day_of_year": day + 1,
        "month": month,
        "hour": list(range(24)),
        "cooling_kwh": [round(float(v), 2) for v in cooling_kwh],
        "solar_kwh": [round(float(v), 2) for v in solar_kwh],
        "cooling_day_kwh": round(float(cooling_kwh.sum()), 1),
        "solar_day_kwh": round(float(solar_kwh.sum()), 1),
        "solar_peak_kwh": round(float(solar_kwh.max()), 1),
        "solar_peak_hour": int(np.argmax(solar_kwh)),
        "cooling_peak_kwh": round(float(cooling_kwh.max()), 1),
        "cooling_peak_hour": int(np.argmax(cooling_kwh)),
    }


def wet_pad_drop_c(climate_df: pd.DataFrame, area_m2: float) -> float:
    """How much the wet pads cool the air (°C) at the hottest hour of each day, averaged over the hottest month."""
    prof = cooling.hourly_profile(climate_df, "wet_pad", area_m2)
    hottest = int(prof.groupby("month")["outside_c"].mean().idxmax())
    month = prof[prof["month"] == hottest]
    peak_rows = month.loc[month.groupby(month["hour_of_year"] // 24)["outside_c"].idxmax()]
    return round(float((peak_rows["outside_c"] - peak_rows["inside_c"]).mean()), 1)


def crop_options(plan: dict, crop: str) -> list[dict]:
    """The four setup options for one crop, in the SETUPS order."""
    by_setup = {o["setup"]: o for o in plan["options"] if o["crop"] == crop}
    return [by_setup[s] for s in SETUPS if s in by_setup]


def crop_limit(plan: dict, crop: str) -> float:
    return next(float(c["t_max_c"]) for c in plan["assumptions"]["crops"] if c["crop"] == crop)


def no_recommendation_key(plan: dict) -> str:
    """i18n key explaining why a plan has no recommendation."""
    if not plan.get("options"):
        return "none_nodata"
    if not any(o["coverage_pct"] >= MIN_COVERAGE_PCT for o in plan["options"]):
        return "none_too_hot"
    return "none_budget"


def focus_crop(plan: dict) -> str | None:
    """Crop to show in the setup comparison: the recommended one, else the chosen one, else the best-covered one."""
    if plan.get("recommended"):
        return plan["recommended"]["crop"]
    if plan["inputs"].get("crop"):
        return plan["inputs"]["crop"]
    if plan.get("options"):
        return max(plan["options"], key=lambda o: o["coverage_pct"])["crop"]
    return None

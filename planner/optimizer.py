"""The decision: run every crop × setup, filter by coverage and budget, rank by priority. Owned by Me.

plan() is the single entry point used by both the app and the AI agent, so its output is
JSON-safe (plain floats, strings, lists, dicts) and every number traces to a source or CSV value.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from planner import climate, cooling, crops, economics, solar
from planner.schemas import MIN_COVERAGE_PCT, PRIORITIES, SETUPS

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# priority -> (option key to rank by, True if higher is better)
RANK_KEYS = {
    "profit": ("profit_10y_qar", True),
    "payback": ("payback_years", False),
    "water": ("water_l_day", False),
}
RANK_WORDS = {"profit": "highest 10-year profit", "payback": "fastest payback", "water": "lowest water use"}


def plan(lat: float, lon: float, area_m2: float, budget_qar: float, priority: str, crop: str | None = None) -> dict:
    """Pin (°), farm area (m²), budget (QAR), priority, optional crop -> dict: site, recommended, options, calendar, sources, assumptions."""
    if priority not in PRIORITIES:
        raise ValueError(f"priority must be one of {PRIORITIES}, got {priority!r}")
    inputs = {"lat": lat, "lon": lon, "area_m2": area_m2, "budget_qar": budget_qar, "priority": priority, "crop": crop}

    try:
        climate_df = climate.get_typical_year(lat, lon)
    except climate.ClimateUnavailable as exc:
        return _empty_plan(inputs, str(exc))

    crops_df = crops.load_crops()
    if crop is not None:
        if crop not in set(crops_df["crop"]):
            return _empty_plan(inputs, f"'{crop}' is not in the crop table (data/crops.csv).", climate_df)
        crops_df = crops_df[crops_df["crop"] == crop]

    calendar_df = crops.crop_calendar(climate_df, crops_df)

    options = []
    for row in crops_df.itertuples(index=False):
        for setup in SETUPS:
            options.append(_evaluate_option(climate_df, row, setup, area_m2, budget_qar))

    passing = [o for o in options if o["passes"]]
    ranked = _rank(passing, priority)
    recommended = ranked[0] if ranked else None

    result = {
        "inputs": inputs,
        "site": _site_summary(climate_df, lat, lon),
        "recommended": recommended,
        "reason": _reason(recommended, options, priority, crop),
        "options": _rank(options, priority),
        "calendar": {
            str(c): {str(m): str(calendar_df.loc[c, m]) for m in calendar_df.columns} for c in calendar_df.index
        },
        "sources": _sources(lat, lon),
        "assumptions": _assumptions(crops_df),
    }
    return to_json_safe(result)


def _evaluate_option(climate_df: pd.DataFrame, crop_row, setup: str, area_m2: float, budget_qar: float) -> dict:
    """One crop × setup -> option dict with coverage, energy, solar and economics."""
    sim = cooling.simulate(climate_df, setup, crop_row.t_max_c, area_m2)
    monthly = cooling.monthly_coverage_pct(sim["inside_temp_c"], climate_df["month"], crop_row.t_max_c)
    growing = [m for m, pct in monthly.items() if pct >= MIN_COVERAGE_PCT]
    sol = solar.size_solar(sim["cooling_kwh_peak_day"], climate_df)
    econ = economics.evaluate(
        setup, crop_row.crop, area_m2, len(growing), sim["cooling_kwh_year"], sol["solar_kw"]
    )

    fails = []
    if sim["coverage_pct"] < MIN_COVERAGE_PCT:
        fails.append(f"coverage {sim['coverage_pct']}% is below {MIN_COVERAGE_PCT}%")
    if econ["capex_qar"] > budget_qar:
        fails.append(f"build cost {econ['capex_qar']} QAR is over the {budget_qar} QAR budget")

    inside = np.asarray(sim["inside_temp_c"])
    return {
        "crop": crop_row.crop,
        "setup": setup,
        "coverage_pct": sim["coverage_pct"],
        "monthly_coverage_pct": monthly,
        "growing_months": growing,
        "inside_max_c": round(float(inside.max()), 2),
        "cooling_kwh_year": sim["cooling_kwh_year"],
        "cooling_kwh_peak_day": sim["cooling_kwh_peak_day"],
        **sol,
        **econ,
        "passes": not fails,
        "fail_reasons": fails,
    }


def _rank(options: list[dict], priority: str) -> list[dict]:
    """Sort options best-first for the priority; missing values (e.g. no payback) go last."""
    key, higher_is_better = RANK_KEYS[priority]

    def sort_key(o):
        v = o.get(key)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return (1, 0.0)
        return (0, -v if higher_is_better else v)

    return sorted(options, key=sort_key)


def _reason(recommended: dict | None, options: list[dict], priority: str, crop: str | None) -> str:
    """One plain sentence explaining the recommendation or why there is none."""
    if recommended is not None:
        return (
            f"{recommended['setup']} for {recommended['crop']} keeps the crop below its heat limit "
            f"{recommended['coverage_pct']}% of the year and has the {RANK_WORDS[priority]} "
            f"of the options within budget."
        )
    what = crop or "any crop in the table"
    if not any(o["coverage_pct"] >= MIN_COVERAGE_PCT for o in options):
        return f"No setup keeps {what} below its heat limit {MIN_COVERAGE_PCT}% of the year at this site."
    return f"Setups that keep {what} cool enough all cost more than this budget."


def _site_summary(climate_df: pd.DataFrame, lat: float, lon: float) -> dict:
    """Headline climate numbers for the pin."""
    tw = cooling.wet_bulb_c(climate_df["temp_c"], climate_df["rh_pct"])
    by_month = climate_df.assign(wet_bulb_c=tw).groupby("month")
    hottest = int(by_month["temp_c"].mean().idxmax())
    return {
        "lat": lat,
        "lon": lon,
        "temp_mean_c": round(float(climate_df["temp_c"].mean()), 2),
        "temp_max_c": round(float(climate_df["temp_c"].max()), 2),
        "rh_mean_pct": round(float(climate_df["rh_pct"].mean()), 2),
        "hottest_month": hottest,
        "hottest_month_rh_mean_pct": round(float(by_month["rh_pct"].mean()[hottest]), 2),
        "hottest_month_wet_bulb_max_c": round(float(by_month["wet_bulb_c"].max()[hottest]), 2),
        "solar_kwh_m2_year": round(float(climate_df["ghi_wh_m2"].sum() / 1000), 2),
        "monthly_temp_max_c": {int(m): round(float(v), 2) for m, v in by_month["temp_c"].max().items()},
        "monthly_wet_bulb_max_c": {int(m): round(float(v), 2) for m, v in by_month["wet_bulb_c"].max().items()},
    }


def _sources(lat: float, lon: float) -> list[dict]:
    """Every dataset the plan relies on, with where it came from."""
    return [
        climate.source_info(lat, lon),
        {"name": "Crop heat limits and yields", "url": "data/crops.csv", "fetched": None},
        {"name": "Crop prices", "url": "data/prices.csv", "fetched": None},
        {"name": "Setup costs and cooling parameters", "url": "data/setups.csv", "fetched": None},
        {"name": "Shared costs (electricity, solar)", "url": "data/settings.csv", "fetched": None},
    ]


def _assumptions(crops_df: pd.DataFrame) -> dict:
    """Every CSV value the plan used, so the user (and the agent) can see and question it."""
    return {
        "min_coverage_pct": MIN_COVERAGE_PCT,
        "crops": crops_df.to_dict(orient="records"),
        "prices": pd.read_csv(DATA_DIR / "prices.csv").to_dict(orient="records"),
        "setups": pd.read_csv(DATA_DIR / "setups.csv").to_dict(orient="records"),
        "settings": pd.read_csv(DATA_DIR / "settings.csv").to_dict(orient="records"),
    }


def _empty_plan(inputs: dict, reason: str, climate_df: pd.DataFrame | None = None) -> dict:
    """Plan with no recommendation and a reason, used when data is missing."""
    lat, lon = inputs["lat"], inputs["lon"]
    return to_json_safe(
        {
            "inputs": inputs,
            "site": _site_summary(climate_df, lat, lon) if climate_df is not None else {"lat": lat, "lon": lon},
            "recommended": None,
            "reason": reason,
            "options": [],
            "calendar": {},
            "sources": _sources(lat, lon),
            "assumptions": {},
        }
    )


def to_json_safe(obj):
    """Recursively convert NumPy/pandas values into plain Python types; NaN becomes None."""
    if isinstance(obj, dict):
        return {str(k): to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_json_safe(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Print a farm plan for a pin.")
    ap.add_argument("lat", type=float)
    ap.add_argument("lon", type=float)
    ap.add_argument("--area", type=float, default=500)
    ap.add_argument("--budget", type=float, default=250000)
    ap.add_argument("--priority", choices=PRIORITIES, default="profit")
    ap.add_argument("--crop", default=None)
    args = ap.parse_args()

    p = plan(args.lat, args.lon, args.area, args.budget, args.priority, args.crop)
    print(json.dumps({k: p[k] for k in ("site", "recommended", "reason")}, indent=2, ensure_ascii=False))
    print(f"{len(p['options'])} options evaluated; {sum(o['passes'] for o in p['options'])} pass.")

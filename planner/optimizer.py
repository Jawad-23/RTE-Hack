"""The decision: run every crop × setup, filter by coverage and budget, rank by priority. Owned by Me.

plan() is the single entry point used by both the app and the AI agent, so its output is
JSON-safe (plain floats, strings, lists, dicts) and every number traces to a source or CSV value.
"""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from planner import agronomy, climate, cooling, crops, dust, economics, finance, kit, market, site_climate, site_data, solar, water
from planner.schemas import MIN_COVERAGE_PCT, MIN_LIGHT_OK_PCT, PRIORITIES, SETUPS

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# priority -> (option key to rank by, True if higher is better)
RANK_KEYS = {
    "profit": ("profit_10y_qar", True),
    "payback": ("payback_years", False),
    "water": ("water_l_day", False),
}
RANK_WORDS = {"profit": "highest 10-year profit", "payback": "fastest payback", "water": "lowest water use"}


def plan(lat: float, lon: float, area_m2: float, budget_qar: float, priority: str, crop: str | None = None,
         *, cleaning_interval_days: int | None = None, extras: bool = True) -> dict:
    """Pin (°), farm area (m²), budget (QAR), priority, optional crop -> dict: site, recommended, options, calendar, sources, assumptions.

    extras=False skips the online extras (World Bank rate, PVGIS, forecast), e.g. for each point of an area scan.
    """
    if priority not in PRIORITIES:
        raise ValueError(f"priority must be one of {PRIORITIES}, got {priority!r}")
    if not np.isfinite([lat, lon, area_m2, budget_qar]).all() or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Coordinates, area and budget must be finite and coordinates within bounds")
    if area_m2 <= 0 or budget_qar < 0:
        raise ValueError("Area must be positive and budget cannot be negative")
    if cleaning_interval_days is not None and cleaning_interval_days not in (7, 14, 30):
        raise ValueError("Cleaning interval must be 7, 14 or 30 days")
    inputs = {"lat": lat, "lon": lon, "area_m2": area_m2, "budget_qar": budget_qar, "priority": priority, "crop": crop}
    inputs["cleaning_interval_days"] = cleaning_interval_days

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
    prices = market.prices_for(lat, lon, solar.load_settings()["usd_to_qar"])

    options = []
    for row in crops_df.itertuples(index=False):
        for setup in SETUPS:
            options.append(_evaluate_option(climate_df, row, setup, area_m2, budget_qar, cleaning_interval_days,
                                            prices["prices"].get(row.crop)))

    cfg = solar.load_settings()
    skipped = {"available": False, "reason": "not requested (extras=False)"}
    money = site_data.money(market.iso3(prices["country"])) if extras else skipped
    rate = finance.real_rate(money, cfg)
    for o in options:
        o.update(finance.evaluate(o, rate["rate_pct"], cfg.get("electricity_sell_qar_kwh", 0)))

    passing = [o for o in options if o["passes"]]
    ranked = _rank(passing, priority)
    recommended = ranked[0] if ranked else None

    result = {
        "inputs": inputs,
        "site": _site_summary(climate_df, lat, lon, crops_df),
        "recommended": recommended,
        "reason": _reason(recommended, options, priority, crop),
        "options": _rank(options, priority),
        "calendar": {
            str(c): {str(m): str(calendar_df.loc[c, m]) for m in calendar_df.columns} for c in calendar_df.index
        },
        "sources": _sources(lat, lon, prices),
        "assumptions": _assumptions(crops_df, prices),
        "kit": kit.costs(area_m2, recommended),
        "finance": {**rate, "years": finance.YEARS, "price_down_pct": finance.PRICE_DOWN * 100, "capex_up_pct": finance.CAPEX_UP * 100},
        "solar_gis": site_data.pvgis(lat, lon) if extras else skipped,
        "forecast": site_data.forecast(lat, lon) if extras else skipped,
    }
    today = date.today().isoformat()
    for name, info in (("Discount rate: World Bank lending rate and inflation", money),
                       ("Solar yield with terrain shading: EU JRC PVGIS", result["solar_gis"]),
                       ("7-day heat, humidity and UV forecast: Open-Meteo", result["forecast"])):
        if info.get("available"):
            result["sources"].append({"name": name, "url": info["source"], "fetched": today})
    # The existing assistant already forwards assumptions; no provider-code change
    # is needed for these new diagnostics to reach the model and number checker.
    result["assumptions"]["option_diagnostics"] = [{k: o.get(k) for k in (
        "crop", "setup", "light_ok_pct", "dli_mean_mol_m2_day", "vpd_stress_hours",
        "inside_rh_mean_pct", "grid_kwh_year", "export_kwh_year", "cleaning_cost_qar_year")} for o in options]
    return to_json_safe(result)


def _evaluate_option(climate_df: pd.DataFrame, crop_row, setup: str, area_m2: float, budget_qar: float,
                     cleaning_interval_days: int | None = None, price: dict | None = None) -> dict:
    """One crop × setup (+ its market price) -> option dict with coverage, energy, solar, water and economics."""
    crop_info = crop_row._asdict()
    sim = cooling.simulate(climate_df, setup, crop_row.t_max_c, area_m2, crop_info)
    prof = cooling.hourly_profile(climate_df, setup, area_m2, crop_info)
    monthly = cooling.monthly_coverage_pct(sim["inside_temp_c"], climate_df["month"], crop_row.t_max_c)
    growing = [m for m, pct in monthly.items() if pct >= MIN_COVERAGE_PCT]
    sol = solar.size_solar(sim["cooling_kwh_peak_day"], climate_df)
    cfg = solar.load_settings()
    integrated_kw = area_m2 * float(cooling.load_setups().loc[setup, "pv_kw_m2"])
    sol["solar_kw"] = round(sol["solar_kw"] + integrated_kw, 2)
    output = prof["pv_kwh"].to_numpy() + (sol["solar_kw"] - integrated_kw) * climate_df["ghi_wh_m2"].to_numpy() / 1000 * cfg["performance_ratio"]
    clean = {"cleaning_cost_qar_year": 0.0, "cleaning_water_l_year": 0.0}
    light_yield_factor = 1.0
    if cleaning_interval_days and setup != "open_field":
        scenario = dust.cleaning_scenario(area_m2, cleaning_interval_days, len(prof))
        loss = scenario["loss_fraction"]
        output *= 1 - loss
        prof["par_inside_w_m2"] *= 1 - loss
        light_yield_factor = 1 - float(loss.mean()) * cfg["light_yield_loss_factor"]
        clean = {k: scenario[k] for k in clean}
    sol["solar_kwh_year"] = round(float(output.sum()), 2)
    grid = float(np.maximum(prof["cooling_kwh"].to_numpy() - output, 0).sum())
    export = float(np.maximum(output - prof["cooling_kwh"].to_numpy(), 0).sum())
    diagnostics = agronomy.metrics(prof, crop_info, growing)
    use = water.water_l_m2_day(climate_df, prof, crop_info, cooling.load_setups().loc[setup], growing, cfg)
    econ = economics.evaluate(
        setup, crop_row.crop, area_m2, len(growing), sim["cooling_kwh_year"], sol["solar_kw"],
        grid_kwh_year=grid, export_kwh_year=export, yield_factor=light_yield_factor,
        price_qar_kg=price["price_qar_kg"] if price else None, water_l_m2_day=use["crop_l_m2_day"] + use["pad_l_m2_day"], **clean
    )

    fails = []
    if sim["coverage_pct"] < MIN_COVERAGE_PCT:
        fails.append(f"coverage {sim['coverage_pct']}% is below {MIN_COVERAGE_PCT}%")
    if econ["capex_qar"] is None:
        fails.append(econ.get("reason", "Missing economic assumptions"))
    elif econ["capex_qar"] > budget_qar:
        fails.append(f"build cost {econ['capex_qar']} QAR is over the {budget_qar} QAR budget")
    if diagnostics["light_ok_pct"] is None:
        fails.append("Light sufficiency unavailable: no growing days or missing PAR/crop light limit")
    elif diagnostics["light_ok_pct"] < MIN_LIGHT_OK_PCT:
        fails.append(f"light sufficiency {diagnostics['light_ok_pct']}% is below {MIN_LIGHT_OK_PCT}% of growing days")

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
        "price_qar_kg": price["price_qar_kg"] if price else None,
        "irrigation_l_day": round(use["crop_l_m2_day"] * area_m2, 2),
        "pad_water_l_day": round(use["pad_l_m2_day"] * area_m2, 2),
        "et0_mm_day": use["et0_mm_day"],
        **diagnostics,
        **clean,
        "grid_kwh_year": round(grid, 2),
        "export_kwh_year": round(export, 2),
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
    return f"No option for {what} passes all temperature, light, data and budget checks. See each option's fail_reasons."


def _site_summary(climate_df: pd.DataFrame, lat: float, lon: float, crops_df: pd.DataFrame | None = None) -> dict:
    """Headline climate numbers for the pin, plus site_climate.summary() (the Results page's climate card)."""
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
        **site_climate.summary(climate_df, crops.load_crops() if crops_df is None else crops_df),
    }


def _sources(lat: float, lon: float, prices: dict | None = None) -> list[dict]:
    """Every dataset the plan relies on, with where it came from."""
    country = (prices or {}).get("country") or {}
    return [
        climate.source_info(lat, lon),
        {"name": "Crop prices: FAOSTAT producer (farm-gate) prices" + (f" for {country['name']}" if country else ", world median"),
         "url": market.FAOSTAT_PAGE, "fetched": (prices or {}).get("fetched")},
        {"name": "Crop water: FAO-56 Penman-Monteith with the NASA POWER weather above",
         "url": "https://www.fao.org/4/x0490e/x0490e00.htm", "fetched": None},
        {"name": "Crop heat limits, yields and FAO-56 crop coefficients", "url": "data/crops.csv", "fetched": None},
        {"name": "Setup costs and cooling parameters", "url": "data/setups.csv", "fetched": None},
        {"name": "Shared costs (electricity, solar)", "url": "data/settings.csv", "fetched": None},
    ]


def _assumptions(crops_df: pd.DataFrame, prices: dict | None = None) -> dict:
    """Every value the plan used, so the user (and the agent) can see and question it."""
    return {
        "min_coverage_pct": MIN_COVERAGE_PCT,
        "crops": crops_df.to_dict(orient="records"),
        "prices": [{"crop": c, **p} for c, p in (prices or {}).get("prices", {}).items()],
        "price_country": (prices or {}).get("country"),
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

"""Cost, profit and payback for one setup and crop. Owned by Mustafa.

Costs come from data/*.csv; the crop price (FAOSTAT, see market.py) and water use (FAO-56, see water.py)
are passed in by the optimizer. Nothing is hard-coded here.
"""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
KEYS = ["capex_qar", "opex_qar_year", "revenue_qar_year", "profit_qar_year", "payback_years", "profit_10y_qar", "water_l_day"]


def _row(csv_name: str, key_col: str, key: str) -> dict | None:
    """One row of data/<csv_name> where key_col == key, as a dict, or None if missing."""
    df = pd.read_csv(DATA_DIR / csv_name)
    match = df[df[key_col] == key]
    return None if match.empty else match.iloc[0].to_dict()


def _settings() -> dict:
    df = pd.read_csv(DATA_DIR / "settings.csv")
    return {k: float(v) for k, v in zip(df["key"], df["value"])}


def evaluate(setup: str, crop: str, area_m2: float, growing_months: float, cooling_kwh_year: float, solar_kw: float,
             *, grid_kwh_year: float = 0, export_kwh_year: float = 0, cleaning_cost_qar_year: float = 0,
             cleaning_water_l_year: float = 0, yield_factor: float = 1, price_qar_kg: float | None = None,
             water_l_m2_day: float = 0) -> dict:
    """Setup, crop, area (m²), growing months, cooling (kWh/year), solar (kW) -> capex_qar, opex_qar_year, revenue_qar_year, profit_qar_year, payback_years, profit_10y_qar, water_l_day.

    The optimizer supplies hourly-balanced grid imports and exports. Optional keyword
    defaults preserve callers that only have the original annual-energy contract.
    price_qar_kg is the farm-gate price; water_l_m2_day is irrigation plus pad water per m² (from water.py).
    If the crop, setup or price is missing, every value is None and "reason" says why.
    """
    s, c = _row("setups.csv", "setup", setup), _row("crops.csv", "crop", crop)
    missing = [name for name, row in (("setups.csv", s), ("crops.csv", c), ("a price", price_qar_kg)) if row is None]
    if missing:
        return {**{k: None for k in KEYS}, "reason": f"No data for {setup}/{crop}: missing {', '.join(missing)}"}

    cfg = _settings()
    capex = area_m2 * s["capex_qar_m2"] + solar_kw * cfg["solar_capex_qar_kw"]
    revenue = area_m2 * c["yield_kg_m2_year"] * price_qar_kg * (growing_months / 12) * s["yield_factor"] * yield_factor
    revenue += export_kwh_year * cfg.get("electricity_sell_qar_kwh", 0)
    opex = area_m2 * s["opex_qar_m2_year"] + grid_kwh_year * cfg.get("electricity_price_qar_kwh", 0) + cleaning_cost_qar_year
    profit = revenue - opex
    return {
        "capex_qar": round(float(capex), 2),
        "opex_qar_year": round(float(opex), 2),
        "revenue_qar_year": round(float(revenue), 2),
        "profit_qar_year": round(float(profit), 2),
        "payback_years": round(float(capex / profit), 2) if profit > 0 else None,
        "profit_10y_qar": round(float(profit * 10 - capex), 2),
        "water_l_day": round(float(area_m2 * water_l_m2_day + cleaning_water_l_year / 365), 2),
    }

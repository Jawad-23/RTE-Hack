"""Cost, profit and payback for one setup and crop. Owned by Mustafa.

STUB: returns fake but correctly shaped data until Mustafa replaces it
(docs/03-team-tasks.md, section 7, step 2).
"""

_FAKE = {
    # setup: (capex_qar per m², profit_qar_year per m²)
    "open_field": (10.0, 6.0),
    "shade_net": (40.0, 16.0),
    "wet_pad": (300.0, 60.0),
    "chiller": (460.0, 136.0),
}


def evaluate(setup: str, crop: str, area_m2: float, growing_months: float, cooling_kwh_year: float, solar_kw: float) -> dict:
    """Setup, crop, area (m²), growing months, cooling (kWh/year), solar (kW) -> capex_qar, opex_qar_year, revenue_qar_year, profit_qar_year, payback_years, profit_10y_qar, water_l_day."""
    # TODO(Mustafa): real formulas reading data/setups.csv, crops.csv, prices.csv, settings.csv.
    capex_m2, profit_m2 = _FAKE[setup]
    capex = capex_m2 * area_m2
    profit = profit_m2 * area_m2 * growing_months / 12
    opex = 0.2 * profit
    return {
        "capex_qar": round(capex, 2),
        "opex_qar_year": round(opex, 2),
        "revenue_qar_year": round(profit + opex, 2),
        "profit_qar_year": round(profit, 2),
        "payback_years": round(capex / profit, 2) if profit > 0 else None,
        "profit_10y_qar": round(profit * 10 - capex, 2),
        "water_l_day": round(5.0 * area_m2, 2),
    }

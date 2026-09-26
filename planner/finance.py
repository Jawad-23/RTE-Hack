"""Investment view of each option: NPV, IRR, break-even crop price and what happens if things go worse.

Cash flows are in today's prices: year 0 pays the build cost (capex), years 1..YEARS earn the yearly
profit from economics.py. So they are discounted at the *real* rate: the country's World Bank lending
rate with its inflation taken out, (1 + lending) / (1 + inflation) - 1. If the World Bank has no data,
the fallback in data/settings.csv is used and the plan says so.
"""

from __future__ import annotations

YEARS = 10
PRICE_DOWN = 0.2   # downside case: crop price 20 % lower
CAPEX_UP = 0.2     # downside case: build cost 20 % higher


def real_rate(money: dict, cfg: dict) -> dict:
    """World Bank money data (site_data.money) + settings -> {"rate_pct", "basis", "lending_rate_pct", "inflation_pct"}."""
    if money.get("available"):
        real = (1 + money["lending_rate_pct"] / 100) / (1 + money["inflation_pct"] / 100) - 1
        return {"rate_pct": round(real * 100, 2), "basis": "world_bank", "lending_rate_pct": money["lending_rate_pct"],
                "lending_rate_year": money["lending_rate_year"], "inflation_pct": money["inflation_pct"],
                "inflation_year": money["inflation_year"]}
    return {"rate_pct": float(cfg["discount_rate_fallback_pct"]), "basis": "fallback", "lending_rate_pct": None,
            "inflation_pct": None}


def annuity(rate: float, years: int = YEARS) -> float:
    """Present value of 1 QAR a year for `years` years at `rate` (fraction)."""
    return float(years) if rate == 0 else (1 - (1 + rate) ** -years) / rate


def npv(capex: float, profit: float, rate: float, years: int = YEARS) -> float:
    return -capex + profit * annuity(rate, years)


def irr(capex: float, profit: float, years: int = YEARS) -> float | None:
    """Internal rate of return (fraction) of -capex then `profit` a year, or None if it never pays back within `years`."""
    if capex <= 0 or profit <= 0 or profit * years <= capex:
        return None
    lo, hi = 0.0, 10.0
    for _ in range(100):  # NPV falls as the rate rises, so bisect
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if npv(capex, profit, mid, years) > 0 else (lo, mid)
    return (lo + hi) / 2


def evaluate(option: dict, rate_pct: float, sell_qar_kwh: float = 0.0) -> dict:
    """One planner option + real discount rate (%) -> npv_qar, irr_pct, breakeven_price_qar_kg and downside cases."""
    keys = ("npv_qar", "irr_pct", "breakeven_price_qar_kg", "npv_price_down_qar", "payback_price_down_years", "npv_capex_up_qar")
    capex, profit, price = option.get("capex_qar"), option.get("profit_qar_year"), option.get("price_qar_kg")
    if capex is None or profit is None:
        return {k: None for k in keys}
    rate = rate_pct / 100
    crop_revenue = option["revenue_qar_year"] - option.get("export_kwh_year", 0) * sell_qar_kwh
    out = {"npv_qar": round(npv(capex, profit, rate), 2)}
    r = irr(capex, profit)
    out["irr_pct"] = None if r is None else round(r * 100, 1)
    # the price at which the option exactly breaks even over YEARS at this rate (revenue scales with price)
    if price and crop_revenue > 0:
        needed_revenue = capex / annuity(rate) - (profit - crop_revenue)
        out["breakeven_price_qar_kg"] = round(max(0.0, price * needed_revenue / crop_revenue), 2)
    else:
        out["breakeven_price_qar_kg"] = None
    worse = profit - PRICE_DOWN * crop_revenue
    out["npv_price_down_qar"] = round(npv(capex, worse, rate), 2)
    out["payback_price_down_years"] = round(capex / worse, 2) if worse > 0 else None
    out["npv_capex_up_qar"] = round(npv(capex * (1 + CAPEX_UP), profit, rate), 2)
    return out

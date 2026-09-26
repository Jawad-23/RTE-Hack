"""Extra open data about the pin: GIS solar, the coming week's heat, and the country's cost of money.

- pvgis(lat, lon): EU JRC PVGIS. Solar panel yield from satellite radiation (SARAH3) and ERA5 weather,
  including shading by the surrounding terrain (horizon from a digital elevation model), the best
  panel angle, and how much output heat costs.
- forecast(lat, lon): Open-Meteo. The next 7 days of maximum temperature, humidity, UV index,
  sunlight and FAO reference evapotranspiration.
- money(iso3): World Bank. The country's latest lending interest rate and inflation, which give the
  real discount rate used for NPV (see finance.py).

All free, no key. Every result is cached in data/cache/site/ (forecast 3 hours, the rest 30 days).
A failed call returns {"available": False, "reason": ...}, so the plan still works offline.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache" / "site"
TIMEOUT_S = 20
DAY_S = 24 * 3600

PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
PVGIS_PAGE = "https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis_en"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_PAGE = "https://open-meteo.com/en/docs"
WORLD_BANK_URL = "https://api.worldbank.org/v2/country/{iso3}/indicator/{indicator}"
WORLD_BANK_PAGE = "https://data.worldbank.org/indicator/{indicator}"
LENDING_RATE = "FR.INR.LEND"      # Lending interest rate (%)
INFLATION = "FP.CPI.TOTL.ZG"      # Inflation, consumer prices (annual %)
FORECAST_DAILY = ["temperature_2m_max", "relative_humidity_2m_mean", "uv_index_max", "shortwave_radiation_sum",
                  "et0_fao_evapotranspiration"]


def _cached(name: str, max_age_s: float, fetch) -> dict:
    """Read data/cache/site/<name>.json if younger than max_age_s, else call fetch() and cache a good result."""
    path = CACHE_DIR / f"{name}.json"
    try:
        if path.exists() and time.time() - path.stat().st_mtime < max_age_s:
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    try:
        result = {"available": True, **fetch()}
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result), encoding="utf-8")
    return result


def pvgis(lat: float, lon: float) -> dict:
    """Pin -> yearly and monthly PV yield per installed kW (terrain shading included), best tilt/azimuth, heat loss %."""
    def fetch():
        resp = requests.get(PVGIS_URL, params={"lat": round(lat, 4), "lon": round(lon, 4), "peakpower": 1, "loss": 14,
                                               "optimalangles": 1, "outputformat": "json"}, timeout=TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()
        fixed, mount = data["outputs"]["totals"]["fixed"], data["inputs"]["mounting_system"]["fixed"]
        meteo = data["inputs"]["meteo_data"]
        return {
            "kwh_per_kw_year": round(float(fixed["E_y"]), 1),
            "sun_on_panel_kwh_m2_year": round(float(fixed["H(i)_y"]), 1),
            "heat_loss_pct": round(-float(fixed["l_tg"]), 1),
            "tilt_deg": int(mount["slope"]["value"]),
            "azimuth_deg": int(mount["azimuth"]["value"]),
            "elevation_m": float(data["inputs"]["location"]["elevation"]),
            "terrain_horizon": bool(meteo.get("use_horizon")),
            "monthly_kwh_per_kw": {int(m["month"]): round(float(m["E_m"]), 1) for m in data["outputs"]["monthly"]["fixed"]},
            "years": f"{meteo['year_min']}–{meteo['year_max']}",
            "source": PVGIS_PAGE,
        }
    return _cached(f"pvgis_{lat:.3f}_{lon:.3f}", 30 * DAY_S, fetch)


def forecast(lat: float, lon: float) -> dict:
    """Pin -> the next 7 days: date, max °C, mean RH %, max UV index, sunlight MJ/m², ET0 mm."""
    def fetch():
        resp = requests.get(FORECAST_URL, params={"latitude": round(lat, 4), "longitude": round(lon, 4), "daily": ",".join(FORECAST_DAILY),
                                                  "timezone": "auto", "forecast_days": 7}, timeout=TIMEOUT_S)
        resp.raise_for_status()
        daily = resp.json()["daily"]
        keys = {"temperature_2m_max": "temp_max_c", "relative_humidity_2m_mean": "rh_mean_pct", "uv_index_max": "uv_max",
                "shortwave_radiation_sum": "sun_mj_m2", "et0_fao_evapotranspiration": "et0_mm"}
        days = [{"date": d, **{new: daily[old][i] for old, new in keys.items()}} for i, d in enumerate(daily["time"])]
        return {"days": days, "source": FORECAST_PAGE}
    return _cached(f"forecast_{lat:.2f}_{lon:.2f}", 3 * 3600, fetch)


def money(iso3: str | None) -> dict:
    """ISO3 country code -> latest lending rate % and inflation % (with years) from the World Bank."""
    if not iso3:
        return {"available": False, "reason": "No country for this pin"}

    def latest(indicator):
        resp = requests.get(WORLD_BANK_URL.format(iso3=iso3, indicator=indicator), params={"format": "json", "mrnev": 1},
                            timeout=TIMEOUT_S)
        resp.raise_for_status()
        row = resp.json()[1][0]
        return float(row["value"]), int(row["date"])

    def fetch():
        rate, rate_year = latest(LENDING_RATE)
        inflation, inflation_year = latest(INFLATION)
        return {"lending_rate_pct": round(rate, 2), "lending_rate_year": rate_year, "inflation_pct": round(inflation, 2),
                "inflation_year": inflation_year, "source": WORLD_BANK_PAGE.format(indicator=LENDING_RATE)}
    return _cached(f"money_{iso3}", 30 * DAY_S, fetch)

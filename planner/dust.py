"""Explicit soiling scenarios and recent CAMS dust exposure; never invented history."""

import numpy as np
import requests

from planner.solar import load_settings


def cleaning_scenario(area_m2: float, interval_days: int, hours: int = 8760) -> dict:
    """Area and cleaning interval (7/14/30 days) -> loss profile, yearly cost and water."""
    if interval_days not in (7, 14, 30):
        raise ValueError("Cleaning interval must be 7, 14 or 30 days")
    cfg = load_settings()
    age = (np.arange(hours) // 24) % interval_days
    loss = np.minimum(age * cfg["dust_daily_soiling_fraction"], cfg["dust_max_soiling_fraction"])
    cleans = (hours // 24 - 1) // interval_days
    return {"loss_fraction": loss, "cleanings": cleans,
            "cleaning_cost_qar_year": float(cleans * area_m2 * cfg["cleaning_cost_qar_m2"]),
            "cleaning_water_l_year": float(cleans * area_m2 * cfg["cleaning_water_l_m2"])}


def recent_exposure(lat: float, lon: float) -> dict:
    """Fetch the last 30 days of modelled dust; failure returns unavailable, never zero."""
    source = "https://open-meteo.com/en/docs/air-quality-api"
    try:
        response = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality",
                                params={"latitude": lat, "longitude": lon, "hourly": "dust",
                                        "past_days": 30, "forecast_days": 0, "timezone": "GMT"}, timeout=20)
        response.raise_for_status()
        body = response.json()
        values = np.asarray([np.nan if x is None else x for x in body["hourly"]["dust"]], dtype=float)
        times = body["hourly"]["time"]
        good = values[np.isfinite(values)]
        if not len(good) or len(times) != len(values):
            raise ValueError("No usable dust observations")
        return {"available": True, "source": source, "attribution": "CAMS / Open-Meteo",
                "start": times[0], "end": times[-1], "valid_hours": int(len(good)),
                "missing_hours": int(len(values) - len(good)), "mean_ug_m3": round(float(good.mean()), 2),
                "event_hours": int((good >= load_settings()["dust_event_threshold_ug_m3"]).sum())}
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        return {"available": False, "source": source, "reason": str(exc)}

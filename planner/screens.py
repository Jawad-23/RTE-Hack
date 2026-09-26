"""Screen choice on the Croptions Kit page: coated ETFE shade or dynamic aluminium-strip thermal screen.

For the chosen screen this module evaluates:
1. spectrum(): the PAR (growing light) to NIR (infrared heat) ratio outside and under the screen, from the
   site's NASA POWER hourly PAR and NIR, plus the light the crop still gets against its daily need.
2. canopy(): canopy heat and stress from the latest kit reading: CWSI band, hot-spot share of the thermal
   image above the crop limit, and the leaf temperature expected under the screen.
3. maintenance() and hazards(): when to clean or service the screen (dust soiling, coating ageing, drive
   cycles) and the safety briefings this week's forecast calls for (feels-like heat, UV, wind).

Screen properties live in data/screens.csv (all marked estimate); nothing is hard-coded here except
the published heat index formula (NWS Rothfusz regression).
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCREENS = ("etfe_coated", "aluminium_strip")
CWSI_BANDS = ((0.3, "low"), (0.6, "moderate"), (1.01, "severe"))


@lru_cache(maxsize=1)
def load_screens() -> pd.DataFrame:
    """data/screens.csv -> DataFrame indexed by screen name."""
    return pd.read_csv(DATA_DIR / "screens.csv").set_index("screen")


def transmission(screen: str, closure_pct: float = 100.0) -> dict:
    """Screen + closure (%, movable screens only) -> PAR, NIR and UV transmission fractions."""
    s = load_screens().loc[screen]
    share = closure_pct / 100 if s["movable"] else 1.0  # a fixed ETFE shade is always 'closed'
    return {band: round(1 - share * (1 - float(s[f"{band}_transmission"])), 3) for band in ("par", "nir", "uv")}


def _nir(climate_df: pd.DataFrame) -> np.ndarray:
    if "nir_w_m2" in climate_df:
        return climate_df["nir_w_m2"].fillna(0).to_numpy(float)
    if "heat_share" in climate_df:
        return (climate_df["ghi_wh_m2"] * climate_df["heat_share"].fillna(0)).to_numpy(float)
    return (climate_df["ghi_wh_m2"] - climate_df["par_w_m2"]).clip(lower=0).to_numpy(float)


# ---------- 1. spectrum ----------

def spectrum(climate_df: pd.DataFrame, screen: str, crop: dict, closure_pct: float, day: int, par_umol_j: float) -> dict:
    """Typical year + screen + crop + closure + day -> PAR:NIR ratio outside/inside, PAR kept %, NIR blocked %, DLI, monthly ratios."""
    tr = transmission(screen, closure_pct)
    par = climate_df["par_w_m2"].fillna(0).to_numpy(float)
    nir = _nir(climate_df)
    today = climate_df["hour_of_year"].between((day - 1) * 24, day * 24 - 1).to_numpy()
    par_day, nir_day = par[today].sum(), nir[today].sum()
    ratio_out = par_day / nir_day if nir_day > 0 else None
    ratio_in = (par_day * tr["par"]) / (nir_day * tr["nir"]) if nir_day > 0 else None
    dli_out = par_day * 3600 * par_umol_j / 1e6
    months = pd.DataFrame({"month": climate_df["month"].to_numpy(), "par": par, "nir": nir}).groupby("month").sum()
    return {
        "par_transmission": tr["par"], "nir_transmission": tr["nir"], "uv_transmission": tr["uv"],
        "ratio_outside": None if ratio_out is None else round(ratio_out, 2),
        "ratio_inside": None if ratio_in is None else round(ratio_in, 2),
        "par_kept_pct": round(tr["par"] * 100, 1),
        "nir_blocked_pct": round((1 - tr["nir"]) * 100, 1),
        "nir_blocked_kwh_m2_day": round(nir_day * (1 - tr["nir"]) / 1000, 2),
        "dli_outside": round(dli_out, 1),
        "dli_inside": round(dli_out * tr["par"], 1),
        "dli_need": float(crop.get("dli_min_mol_m2_day", float("nan"))),
        "monthly_ratio_outside": {int(m): round(r.par / r.nir, 2) for m, r in months.iterrows() if r.nir > 0},
        "monthly_ratio_inside": {int(m): round(r.par * tr["par"] / (r.nir * tr["nir"]), 2) for m, r in months.iterrows() if r.nir > 0},
    }


# ---------- 2. canopy heat and stress ----------

def cwsi_band(cwsi: float | None) -> str | None:
    return None if cwsi is None else next(label for limit, label in CWSI_BANDS if cwsi < limit)


def canopy(reading: dict, cwsi: float | None, grid: np.ndarray, crop: dict, screen: str, closure_pct: float) -> dict:
    """Latest reading, its CWSI, the thermal image, crop and screen -> stress band, hot-spot %, leaf temperature under the screen.

    Under the screen the sunlit leaf's excess over the air shrinks with the shortwave it still receives
    (PAR and NIR weighted by their share of today's reading); at night the screen changes nothing.
    """
    limit = float(crop["t_max_c"])
    hot_pct = round(float((grid > limit).mean() * 100), 1)
    excess = reading["leaf_c"] - reading["air_c"]
    tr = transmission(screen, closure_pct)
    sw = 0.45 * tr["par"] + 0.55 * tr["nir"]  # sunlight is roughly 45 % PAR and 55 % NIR+UV by energy
    under = reading["air_c"] + (excess * sw if reading["par_w_m2"] > 0 and excess > 0 else excess)
    return {
        "cwsi": cwsi, "band": cwsi_band(cwsi), "hotspot_pct": hot_pct,
        "leaf_now_c": reading["leaf_c"], "leaf_under_screen_c": round(float(under), 2),
        "cooling_c": round(float(reading["leaf_c"] - under), 2), "above_limit_now": reading["leaf_c"] > limit,
        "above_limit_under_screen": under > limit, "limit_c": limit,
    }


# ---------- 3. maintenance and hazards ----------

def days_until_clean(daily_soiling: float, soiling_factor: float, trigger_pct: float, dust_multiplier: float = 1.0) -> int | None:
    """Days of dust build-up before transmission drops by trigger_pct."""
    rate = daily_soiling * soiling_factor * dust_multiplier
    return None if rate <= 0 else max(1, math.ceil(trigger_pct / 100 / rate))


def maintenance(screen: str, cfg: dict, screen_moves: int, days_logged: float, dust: dict | None = None) -> dict:
    """Screen + settings + screen moves seen by the kit (over days_logged) + recent dust -> cleaning, ageing and drive service."""
    s = load_screens().loc[screen]
    multiplier = 1.0
    if dust and dust.get("available") and dust.get("valid_hours"):
        # each hour of a dust event counts as a day of normal soiling, spread over the 30-day record
        multiplier = 1 + dust["event_hours"] * 24 / dust["valid_hours"] / 30
    clean = days_until_clean(cfg["dust_daily_soiling_fraction"], float(s["soiling_factor"]), float(s["clean_trigger_loss_pct"]), multiplier)
    ageing = float(s["degradation_pct_year"])
    out = {"clean_every_days": clean, "dust_multiplier": round(multiplier, 2), "ageing_pct_year": ageing,
           "lifespan_years": int(s["lifespan_years"]), "loss_at_5_years_pct": round(ageing * 5, 1),
           "moves_per_day": None, "service_in_days": None}
    if s["movable"] and not pd.isna(s["drive_service_cycles"]):
        per_day = screen_moves / days_logged if days_logged > 0 else None
        out["moves_per_day"] = None if per_day is None else round(per_day, 1)
        out["service_in_days"] = None if not per_day else int(float(s["drive_service_cycles"]) / per_day)
        out["moves_year"] = screen_moves
    return out


def heat_index_c(temp_c: float, rh_pct: float) -> float:
    """US National Weather Service heat index (Rothfusz regression), °C in and out."""
    t = temp_c * 9 / 5 + 32
    hi = 0.5 * (t + 61 + (t - 68) * 1.2 + rh_pct * 0.094)
    if hi >= 80:
        hi = (-42.379 + 2.04901523 * t + 10.14333127 * rh_pct - 0.22475541 * t * rh_pct - 6.83783e-3 * t * t
              - 5.481717e-2 * rh_pct * rh_pct + 1.22874e-3 * t * t * rh_pct + 8.5282e-4 * t * rh_pct * rh_pct
              - 1.99e-6 * t * t * rh_pct * rh_pct)
    return round((hi - 32) * 5 / 9, 1)


def hazards(screen: str, forecast: dict | None) -> list[dict]:
    """Screen + 7-day forecast -> safety briefings, each {code, level, value, day}; generic briefings when no forecast."""
    s = load_screens().loc[screen]
    days = (forecast or {}).get("days") or []
    out = []
    if days:
        # Open-Meteo's apparent ("feels like") maximum; else the NWS heat index from the high and the mean humidity
        feels = [(d.get("feels_like_max_c") if d.get("feels_like_max_c") is not None else heat_index_c(d["temp_max_c"], d["rh_mean_pct"]), d)
                 for d in days]
        hi, worst = max(feels, key=lambda x: x[0])
        hi = round(float(hi), 1)
        level = "danger" if hi >= 54 else "high" if hi >= 41 else "caution" if hi >= 32 else "ok"  # NWS heat index bands
        out.append({"code": "heat", "level": level, "value": hi, "day": worst["date"]})
        uv = max((d["uv_max"] for d in days if d.get("uv_max") is not None), default=None)
        if uv is not None:
            out.append({"code": "uv", "level": "high" if uv >= 8 else "caution" if uv >= 6 else "ok", "value": uv, "day": None})
        winds = [d for d in days if d.get("wind_max_kmh") is not None]
        if winds:
            w = max(winds, key=lambda d: d["wind_max_kmh"])
            out.append({"code": "wind", "level": "high" if w["wind_max_kmh"] >= float(s["wind_limit_kmh"]) else "ok",
                        "value": w["wind_max_kmh"], "day": w["date"], "limit": float(s["wind_limit_kmh"])})
    out.append({"code": "height", "level": "caution", "value": None, "day": None})
    out.append({"code": "drive" if s["movable"] else "film", "level": "caution", "value": None, "day": None})
    return out

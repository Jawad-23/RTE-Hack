"""Croptions Kit, simulated: readings, what they mean, what to do, and what the kit costs. Owned by Me.

There is no hardware. A phone (or the dashboard itself) plays the kit and sends simulated readings
built from the site's NASA typical year, passed through the recommended setup's physics. Every
reading says it is simulated. The reading dict is the same shape a real pod would send later.

Parameters (scenarios, CWSI baseline, alert limits, noise, price) live in data/kit_scenarios.csv
and data/settings.csv, never in this file.
"""

from __future__ import annotations

import math
import secrets
import threading
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from planner import controller, cooling
from planner.agronomy import saturation_kpa
from planner.solar import load_settings

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SOURCE = "simulated"  # every reading carries this until a real pod exists
READING_KEYS = ("farm_code", "seq", "sent_at", "sim_day", "sim_hour", "scenario",
                "leaf_c", "air_c", "rh_pct", "par_w_m2", "source")
ALERTS = ("leaf_hot", "water_stress", "dry_air", "condensation")
GRID_SHAPE = (24, 32)  # rows × columns of the simulated thermal image (a 32 × 24 thermal sensor)


@lru_cache(maxsize=1)
def load_scenarios() -> pd.DataFrame:
    """data/kit_scenarios.csv -> DataFrame indexed by scenario name."""
    return pd.read_csv(DATA_DIR / "kit_scenarios.csv").set_index("scenario")


def scenarios() -> list[str]:
    return list(load_scenarios().index)


# ---------- the farm's day, as the kit would see it ----------

def day_conditions(climate_df: pd.DataFrame, setup: str, area_m2: float, crop: dict, day: int) -> list[dict]:
    """Typical year + setup + crop + day (1–365) -> 24 hourly dicts of inside air_c, rh_pct, par_w_m2 and outside_c."""
    if not 1 <= day <= 365:
        raise ValueError("Day must be between 1 and 365")
    hours = climate_df[climate_df["hour_of_year"].between((day - 1) * 24, day * 24 - 1)].reset_index(drop=True)
    if len(hours) != 24:
        raise ValueError("A complete day of weather is required")
    prof = cooling.hourly_profile(hours, setup, area_m2, crop)
    par = prof["par_inside_w_m2"].fillna(0)
    return [{"hour": h, "air_c": round(float(prof["inside_c"][h]), 2), "rh_pct": round(float(prof["inside_rh_pct"][h]), 1),
             "par_w_m2": round(float(par[h]), 1), "outside_c": round(float(prof["outside_c"][h]), 2)} for h in range(24)]


def simulate_reading(day: list[dict], hour: int | None, scenario: str, rng: np.random.Generator | None = None,
                     cfg: dict | None = None) -> dict:
    """The farm's day + hour (None = the scenario's own hour) + scenario -> one simulated reading (no farm_code/seq yet)."""
    cfg = load_settings() if cfg is None else cfg
    rng = np.random.default_rng() if rng is None else rng
    s = load_scenarios().loc[scenario]
    if hour is None:
        hour = 12 if pd.isna(s["hour"]) else int(s["hour"])
    base = day[int(hour) % 24]
    air = base["air_c"] + s["air_offset_c"] + rng.normal(0, cfg["kit_noise_temp_c"])
    rh = float(np.clip(base["rh_pct"] + s["rh_offset_pct"] + rng.normal(0, cfg["kit_noise_rh_pct"]), 5, 100))
    par = max(0.0, base["par_w_m2"] * s["par_factor"] * (1 + rng.normal(0, cfg["kit_noise_par_fraction"])))
    if par > 0:  # a sunlit leaf sits between the transpiring baseline and the non-transpiring limit
        lower = _lower_baseline(air, rh, cfg)
        leaf = air + lower + s["leaf_stress_fraction"] * (cfg["kit_cwsi_upper_delta_c"] - lower)
    else:
        leaf = air + s["night_leaf_offset_c"]
    leaf += rng.normal(0, cfg["kit_noise_temp_c"])
    return {"sim_hour": int(hour), "scenario": scenario, "leaf_c": round(float(leaf), 2), "air_c": round(float(air), 2),
            "rh_pct": round(rh, 1), "par_w_m2": round(float(par), 1), "source": SOURCE}


# ---------- what a reading means ----------

def _vpd_kpa(air_c: float, rh_pct: float) -> float:
    return float(saturation_kpa(air_c)) * (1 - rh_pct / 100)


def _lower_baseline(air_c: float, rh_pct: float, cfg: dict) -> float:
    """Leaf minus air temperature (°C) of a fully transpiring crop at this VPD (Idso-style baseline from settings.csv)."""
    return cfg["kit_cwsi_lower_intercept_c"] + cfg["kit_cwsi_lower_slope_c_kpa"] * _vpd_kpa(air_c, rh_pct)


def dew_point_c(air_c: float, rh_pct: float) -> float:
    """Air temperature (°C) and RH (%) -> dew point (°C), inverse of the Tetens equation used in agronomy.py."""
    g = math.log(max(rh_pct, 1.0) / 100) + 17.27 * air_c / (237.3 + air_c)
    return 237.3 * g / (17.27 - g)


def derive(reading: dict, crop: dict, cfg: dict | None = None) -> dict:
    """Reading + crop row -> vpd_kpa, dew_point_c, leaf_dew_gap_c, cwsi (None at night, with reason) and alert codes."""
    cfg = load_settings() if cfg is None else cfg
    air, rh, leaf = reading["air_c"], reading["rh_pct"], reading["leaf_c"]
    vpd = _vpd_kpa(air, rh)
    dew = dew_point_c(air, rh)
    cwsi, cwsi_reason = None, "night: CWSI needs a sunlit canopy"
    if reading["par_w_m2"] > 0:
        lower = _lower_baseline(air, rh, cfg)
        span = cfg["kit_cwsi_upper_delta_c"] - lower
        cwsi, cwsi_reason = (float(np.clip((leaf - air - lower) / span, 0, 1)), None) if span > 0 else (None, "baseline above upper limit")
    alerts = []
    if leaf > float(crop["t_max_c"]):
        alerts.append("leaf_hot")
    if cwsi is not None and cwsi >= cfg["kit_cwsi_alert"]:
        alerts.append("water_stress")
    vpd_max = float(crop.get("vpd_max_kpa", float("nan")))
    if math.isfinite(vpd_max) and vpd > vpd_max:
        alerts.append("dry_air")
    if leaf - dew < cfg["kit_dew_gap_alert_c"]:
        alerts.append("condensation")
    return {"vpd_kpa": round(vpd, 2), "dew_point_c": round(dew, 2), "leaf_dew_gap_c": round(leaf - dew, 2),
            "cwsi": None if cwsi is None else round(cwsi, 2), "cwsi_reason": cwsi_reason, "alerts": alerts}


def recommend(reading: dict, crop: dict, screen_pct: float, cfg: dict | None = None) -> dict:
    """Reading + crop + current screen (%) -> the screen position the shared controller settles on, and its reason code.

    Same rules as the planner's smart screen (controller.decide), run until it stops moving.
    """
    cfg = load_settings() if cfg is None else cfg
    row = {"temp_c": reading["air_c"], "par_w_m2": reading["par_w_m2"]}
    state = {"screen_pct": float(screen_pct)}
    for _ in range(int(cfg["screen_max_pct"] / cfg["screen_step_pct"]) + 1):
        nxt = controller.decide(row, crop, state, cfg)
        if nxt["screen_pct"] == state["screen_pct"]:
            state = nxt
            break
        state = nxt
    return {"screen_pct": state["screen_pct"], "reason": state["reason"]}


def dli_so_far(readings: list[dict], sim_day: int, cfg: dict | None = None) -> float:
    """Daily light integral (mol/m²) from the readings received for one simulated day: latest reading per hour × 1 hour."""
    cfg = load_settings() if cfg is None else cfg
    per_hour = {r["sim_hour"]: r["par_w_m2"] for r in readings if r.get("sim_day") == sim_day}
    return round(sum(per_hour.values()) * 3600 * cfg["par_umol_j"] / 1e6, 2)


def thermal_grid(reading: dict, seed: int = 0) -> np.ndarray:
    """Reading -> simulated 24 × 32 thermal image (°C): leaves around leaf_c, warmer gaps and a few stress hot spots.

    Illustration only: its mean canopy temperature equals the reading, the pattern is random.
    """
    rng = np.random.default_rng(seed)
    rows, cols = GRID_SHAPE
    y, x = np.mgrid[0:rows, 0:cols]
    canopy = np.zeros(GRID_SHAPE)
    for row in (4, 12, 20):  # three crop rows seen from above, soil showing between them
        for cx in np.arange(1, cols, 3.5):
            cy, r = row + rng.normal(0, 0.8), rng.uniform(1.6, 2.6)
            canopy += np.exp(-((y - cy) ** 2 + (x - cx - rng.normal(0, 0.6)) ** 2) / (2 * r ** 2))
    leaf_mask = canopy > 0.9
    stress = max(0.0, reading["leaf_c"] - reading["air_c"])
    hot = np.zeros(GRID_SHAPE)
    for _ in range(3):
        cy, cx = rng.uniform(0, rows), rng.uniform(0, cols)
        hot += np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / 12)
    # dense canopy is a little cooler than its thin edges; stressed plants show hot spots
    leaf = -0.8 * np.clip(canopy, 0, 2) + (0.5 + 0.5 * stress) * hot
    ground = reading["air_c"] + (4.0 if reading["par_w_m2"] > 0 else -0.5) + 0.5 * np.clip(0.9 - canopy, 0, None)
    image = np.where(leaf_mask, leaf, ground) + rng.normal(0, 0.05, GRID_SHAPE)
    image[leaf_mask] += reading["leaf_c"] - image[leaf_mask].mean()
    return np.round(image, 2)


# ---------- cost ----------

def costs(area_m2: float, recommended: dict | None, cfg: dict | None = None) -> dict:
    """Farm area (m²) + recommended option -> pods, kit capex and yearly cost, and the plan's build cost and payback with the kit."""
    cfg = load_settings() if cfg is None else cfg
    pods = max(1, math.ceil(area_m2 / cfg["kit_pod_area_m2"]))
    capex, opex = pods * cfg["kit_pod_price_qar"], pods * cfg["kit_service_qar_year"]
    out = {"pods": pods, "pod_area_m2": cfg["kit_pod_area_m2"], "kit_capex_qar": round(capex, 2), "kit_opex_qar_year": round(opex, 2),
           "capex_with_kit_qar": None, "profit_with_kit_qar_year": None, "payback_with_kit_years": None, "reason": None}
    if not recommended or recommended.get("capex_qar") is None:
        out["reason"] = "No recommended option to add the kit to"
        return out
    total = recommended["capex_qar"] + capex
    profit = recommended["profit_qar_year"] - opex
    out.update(capex_with_kit_qar=round(total, 2), profit_with_kit_qar_year=round(profit, 2),
               payback_with_kit_years=round(total / profit, 2) if profit > 0 else None)
    return out


# ---------- the shared inbox between the phone and the dashboard ----------

class KitStore:
    """In-memory mailbox shared by every browser session on one server: farm code -> context + readings.

    Lost on restart; fine for a demo. A real pod would post the same reading dicts to a database.
    """

    MAX_FARMS, MAX_READINGS, TTL_S = 200, 2000, 24 * 3600

    def __init__(self):
        self._lock = threading.Lock()
        self._farms: dict[str, dict] = {}

    def create(self, context: dict) -> str:
        """Register a farm context (site, crop, setup, day) -> new 4-digit farm code."""
        with self._lock:
            self._expire()
            code = next(c for c in (f"{secrets.randbelow(9000) + 1000}" for _ in range(100)) if c not in self._farms)
            self._farms[code] = {"context": context, "readings": [], "touched": time.time()}
            return code

    def context(self, code: str) -> dict | None:
        with self._lock:
            farm = self._farms.get(str(code))
            return None if farm is None else farm["context"]

    def set_context(self, code: str, context: dict) -> None:
        with self._lock:
            if code in self._farms:
                self._farms[code].update(context=context, touched=time.time())

    def push(self, code: str, reading: dict) -> dict | None:
        """Store a reading for a farm; stamps farm_code, seq and sent_at. None if the code is unknown."""
        with self._lock:
            farm = self._farms.get(str(code))
            if farm is None:
                return None
            seq = farm["readings"][-1]["seq"] + 1 if farm["readings"] else 1
            stored = {**reading, "farm_code": str(code), "seq": seq,
                      "sent_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            farm["readings"] = (farm["readings"] + [stored])[-self.MAX_READINGS:]
            farm["touched"] = time.time()
            return stored

    def readings(self, code: str, after_seq: int = 0) -> list[dict]:
        with self._lock:
            farm = self._farms.get(str(code))
            return [] if farm is None else [r for r in farm["readings"] if r["seq"] > after_seq]

    def _expire(self) -> None:
        now = time.time()
        for code in [c for c, f in self._farms.items() if now - f["touched"] > self.TTL_S]:
            del self._farms[code]
        while len(self._farms) >= self.MAX_FARMS:
            del self._farms[min(self._farms, key=lambda c: self._farms[c]["touched"])]

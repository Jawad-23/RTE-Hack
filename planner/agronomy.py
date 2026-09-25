"""Light and humidity diagnostics with explicit missing-data behaviour."""

import numpy as np
import pandas as pd

from planner.solar import load_settings


def saturation_kpa(temp_c):
    """Air temperature (°C) -> saturation vapour pressure (kPa), Tetens equation."""
    temp = np.asarray(temp_c, dtype=float)
    return 0.6108 * np.exp(17.27 * temp / (temp + 237.3))


def metrics(profile, crop, growing_months) -> dict:
    """Hourly profile -> daylight VPD stress hours and DLI coverage over growing days."""
    daylight = profile["par_inside_w_m2"] > 0
    vpd = profile["vpd_kpa"]
    limit = float(crop.get("vpd_max_kpa", np.nan))
    stress = int(((vpd > limit) & daylight).sum()) if np.isfinite(limit) else None
    daily = profile.groupby(profile["hour_of_year"] // 24).agg(
        month=("month", "first"), par=("par_inside_w_m2", lambda x: x.sum(min_count=len(x))))
    dli = daily["par"] * 3600 * load_settings()["par_umol_j"] / 1e6
    selected = dli[daily["month"].isin(growing_months)]
    minimum = float(crop.get("dli_min_mol_m2_day", np.nan))
    available = len(selected) > 0 and selected.notna().all() and np.isfinite(minimum)
    return {
        "light_ok_pct": round(float((selected >= minimum).mean() * 100), 2) if available else None,
        "dli_mean_mol_m2_day": round(float(selected.mean()), 2) if available else None,
        "vpd_stress_hours": stress,
        "inside_rh_mean_pct": round(float(profile["inside_rh_pct"].mean()), 2),
    }

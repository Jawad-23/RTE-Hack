"""What NASA POWER says about the pin: the climate numbers behind the recommendation. Owned by Me.

Every value summarises the typical-year table from climate.py. A value whose NASA column is missing is None,
and "missing" says why, so nothing is guessed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from planner import water
from planner.solar import load_settings


def summary(climate_df: pd.DataFrame, crops_df: pd.DataFrame) -> dict:
    """Typical year + crop table -> headline climate numbers, monthly series and outdoor hours above each crop's limit."""
    day = climate_df["hour_of_year"] // 24
    daily = climate_df.assign(day=day).groupby("day").agg(
        month=("month", "first"), t_max=("temp_c", "max"), t_min=("temp_c", "min"), ghi=("ghi_wh_m2", "sum"))
    by_month = daily.groupby("month")
    hottest = int(by_month["t_max"].mean().idxmax())
    missing = []

    dli = None
    monthly_dli = {}
    if "par_w_m2" in climate_df and climate_df["par_w_m2"].notna().all():
        par_day = climate_df["par_w_m2"].groupby(day).sum() * 3600 * load_settings()["par_umol_j"] / 1e6
        dli = round(float(par_day.mean()), 2)
        monthly_dli = {int(m): round(float(v), 2) for m, v in par_day.groupby(daily["month"]).mean().items()}
    else:
        missing.append("dli: NASA POWER PAR (ALLSKY_SFC_PAR_TOT) is not in this site's data")

    heat_share = None
    if "heat_share" in climate_df and climate_df["heat_share"].notna().any():
        ghi = climate_df["ghi_wh_m2"].to_numpy(float)
        share = climate_df["heat_share"].to_numpy(float)
        ok = np.isfinite(share) & (ghi > 0)
        heat_share = round(float((share[ok] * ghi[ok]).sum() / ghi[ok].sum() * 100), 1)
    else:
        missing.append("heat_share: NASA POWER PAR and UV are needed to split off the infrared part")

    haze = None
    if "clearsky_ghi_w_m2" in climate_df and climate_df["clearsky_ghi_w_m2"].notna().all():
        haze = round(float((1 - climate_df["ghi_wh_m2"].sum() / climate_df["clearsky_ghi_w_m2"].sum()) * 100), 1)
    else:
        missing.append("haze_loss: NASA POWER clear-sky sunlight (CLRSKY_SFC_SW_DWN) is not in this site's data")

    et0 = water.et0_mm_hour(climate_df["temp_c"], climate_df["rh_pct"], climate_df["ghi_wh_m2"], climate_df["wind_ms"],
                            water.cloud_ratio(climate_df))
    et0_day = pd.Series(et0).groupby(day.to_numpy()).sum()

    return {
        "hottest_month_temp_max_mean_c": round(float(by_month["t_max"].mean()[hottest]), 2),
        "monthly_temp_max_mean_c": {int(m): round(float(v), 2) for m, v in by_month["t_max"].mean().items()},
        "monthly_temp_min_mean_c": {int(m): round(float(v), 2) for m, v in by_month["t_min"].mean().items()},
        "monthly_rh_mean_pct": {int(m): round(float(v), 2) for m, v in climate_df.groupby("month")["rh_pct"].mean().items()},
        "hours_above_limit_outdoor": {str(r.crop): int((climate_df["temp_c"] > r.t_max_c).sum()) for r in crops_df.itertuples()},
        "peak_sun_hours_day": round(float(daily["ghi"].mean() / 1000), 2),
        "dli_outdoor_mol_m2_day": dli,
        "monthly_dli_outdoor_mol_m2_day": monthly_dli,
        "heat_share_pct": heat_share,
        "haze_loss_pct": haze,
        "wind_mean_ms": round(float(climate_df["wind_ms"].mean()), 2),
        "et0_mm_day": round(float(et0_day.mean()), 2),
        "monthly_et0_mm_day": {int(m): round(float(v), 2) for m, v in et0_day.groupby(daily["month"]).mean().items()},
        "missing": missing,
    }

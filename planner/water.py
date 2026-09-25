"""Water use calculated from the site's own weather: crop irrigation plus cooling-pad evaporation.

Crop water: FAO-56 hourly Penman-Monteith reference evapotranspiration (Allen et al. 1998, eq. 53),
computed from the conditions the crop actually sees (inside temperature, humidity and light for each
setup), times the crop's seasonal coefficient (FAO-56 Table 12), divided by irrigation efficiency.

Pad water: a wet pad evaporates exactly the moisture it adds to the air. The hourly profile gives
that moisture (kg water per kg air); the fan airflow per m² turns it into litres. Pads run only in
hours when the outside air is warmer than the crop's best-growth range.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from planner.agronomy import saturation_kpa

PSYCHROMETRIC_KPA_C = 0.0674     # γ at sea level (101.3 kPa), FAO-56 eq. 8
ALBEDO = 0.23                    # FAO-56 reference surface
STEFAN_BOLTZMANN_MJ_H = 2.043e-10  # MJ m⁻² h⁻¹ K⁻⁴, FAO-56 eq. 39 (hourly)
WH_TO_MJ = 0.0036
AIR_DENSITY_KG_M3 = 1.2
# FAO-56 Table 11: typical share of the season in each stage (initial, development, mid, late)
STAGE_SHARES = (0.2, 0.3, 0.3, 0.2)


def seasonal_kc(kc_ini: float, kc_mid: float, kc_end: float) -> float:
    """FAO-56 initial/mid/end crop coefficients -> season-average coefficient (linear through development and late stages)."""
    ini, dev, mid, late = STAGE_SHARES
    return ini * kc_ini + dev * (kc_ini + kc_mid) / 2 + mid * kc_mid + late * (kc_mid + kc_end) / 2


def et0_mm_hour(temp_c, rh_pct, solar_wh_m2, wind_ms, cloud_ratio=1.0, longwave_loss: bool = True) -> np.ndarray:
    """Hourly FAO-56 Penman-Monteith reference evapotranspiration (mm/h, never negative).

    temp °C, RH %, solar Wh/m² that hour, wind m/s at 2 m, cloud_ratio = actual / clear-sky solar (0.3–1).
    longwave_loss=False for closed greenhouses, whose cover traps most outgoing longwave radiation.
    """
    t = np.asarray(temp_c, dtype=float)
    es = saturation_kpa(t)
    ea = es * np.clip(np.asarray(rh_pct, dtype=float), 0, 100) / 100
    delta = 4098 * es / (t + 237.3) ** 2
    rs = np.asarray(solar_wh_m2, dtype=float) * WH_TO_MJ
    rn = (1 - ALBEDO) * rs
    if longwave_loss:
        rnl = STEFAN_BOLTZMANN_MJ_H * (t + 273.16) ** 4 * (0.34 - 0.14 * np.sqrt(ea)) * (1.35 * np.clip(cloud_ratio, 0.3, 1) - 0.35)
        rn = rn - rnl
    soil = np.where(rs > 0, 0.1, 0.5) * rn   # FAO-56 eq. 45-46
    u2 = np.asarray(wind_ms, dtype=float)
    num = 0.408 * delta * (rn - soil) + PSYCHROMETRIC_KPA_C * 37 / (t + 273) * u2 * (es - ea)
    return np.clip(num / (delta + PSYCHROMETRIC_KPA_C * (1 + 0.34 * u2)), 0, None)


def cloud_ratio(climate_df: pd.DataFrame) -> np.ndarray:
    """Hourly actual / clear-sky solar from NASA POWER; night hours use that day's daytime value. 1 (clear) if unavailable."""
    if "clearsky_ghi_w_m2" not in climate_df:
        return np.ones(len(climate_df))
    ghi, clear = climate_df["ghi_wh_m2"].to_numpy(float), climate_df["clearsky_ghi_w_m2"].to_numpy(float)
    ratio = pd.Series(np.where(clear > 0, ghi / np.where(clear > 0, clear, 1), np.nan))
    daily = ratio.groupby(climate_df["hour_of_year"].to_numpy() // 24).transform("mean")
    return ratio.fillna(daily).fillna(1.0).clip(0.3, 1).to_numpy()


def water_l_m2_day(climate_df: pd.DataFrame, profile: pd.DataFrame, crop: dict, setup_row, growing_months: list[int],
                   cfg: dict) -> dict:
    """Climate table, hourly profile for one setup, crop row, setup row, growing months, settings ->
    {"crop_l_m2_day", "pad_l_m2_day", "et0_mm_day"}: averages over growing days (the whole year if none)."""
    enclosed = float(setup_row["pad_efficiency"]) > 0
    par_out = climate_df.get("par_w_m2", pd.Series(np.nan, index=climate_df.index)).to_numpy(float)
    light = np.where(par_out > 0, profile["par_inside_w_m2"].to_numpy(float) / np.where(par_out > 0, par_out, 1),
                     float(setup_row["par_transmission"]))
    light = np.nan_to_num(light, nan=float(setup_row["par_transmission"]))
    wind = np.full(len(profile), cfg["greenhouse_air_speed_ms"]) if enclosed else climate_df["wind_ms"].to_numpy(float)

    et0 = et0_mm_hour(profile["inside_c"], profile["inside_rh_pct"], climate_df["ghi_wh_m2"].to_numpy(float) * light, wind,
                      cloud_ratio(climate_df), longwave_loss=not enclosed)
    kc = seasonal_kc(crop["kc_ini"], crop["kc_mid"], crop["kc_end"])
    crop_l = et0 * kc / cfg["irrigation_efficiency"]  # 1 mm of water on 1 m² is 1 litre

    pad_l = np.zeros(len(profile))
    if enclosed:
        pads_on = profile["outside_c"].to_numpy(float) > float(crop["t_opt_max_c"])
        kg_air_per_hour = cfg["pad_airflow_m3_s_m2"] * AIR_DENSITY_KG_M3 * 3600
        pad_l = profile["pad_moisture_kg_kg"].to_numpy(float) * kg_air_per_hour * pads_on

    day = profile["hour_of_year"].to_numpy() // 24
    daily = pd.DataFrame({"month": profile["month"].to_numpy(), "crop": crop_l, "pad": pad_l, "et0": et0}).groupby(day).agg(
        month=("month", "first"), crop=("crop", "sum"), pad=("pad", "sum"), et0=("et0", "sum"))
    season = daily[daily["month"].isin(growing_months)] if growing_months else daily
    return {
        "crop_l_m2_day": round(float(season["crop"].mean()), 2),
        "pad_l_m2_day": round(float(season["pad"].mean()), 2),
        "et0_mm_day": round(float(season["et0"].mean()), 2),
    }

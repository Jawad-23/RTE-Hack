"""Ten-minute simulation using typical-year weather, never live sensor data."""

import pandas as pd

from planner import cooling


def simulate_day(climate_df, day: int, crop: dict, area_m2: float) -> pd.DataFrame:
    """Typical year and day (1–365) -> 144 fixed/smart screen comparison steps."""
    if not 1 <= day <= 365:
        raise ValueError("Day must be between 1 and 365")
    hourly = climate_df[climate_df["hour_of_year"].between((day - 1) * 24, day * 24 - 1)]
    if len(hourly) != 24 or "par_w_m2" not in hourly or hourly["par_w_m2"].isna().any():
        raise ValueError("A complete day of temperature and PAR data is required")
    # Weather is held constant within each observed hour. The controller advances
    # every ten minutes; energy per step is one sixth of the hourly power output.
    ticks = hourly.loc[hourly.index.repeat(6)].reset_index(drop=True)
    fixed = cooling.hourly_profile(ticks, "agrivoltaic_fixed", area_m2, crop)
    smart = cooling.hourly_profile(ticks, "agrivoltaic_louver", area_m2, crop)
    return pd.DataFrame({
        "time": [f"{i // 6:02d}:{i % 6 * 10:02d}" for i in range(144)],
        "outside_c": ticks["temp_c"], "fixed_inside_c": fixed["inside_c"],
        "smart_inside_c": smart["inside_c"], "screen_pct": smart["screen_pct"],
        "reason": smart["screen_reason"], "fixed_par_w_m2": fixed["par_inside_w_m2"],
        "smart_par_w_m2": smart["par_inside_w_m2"], "vpd_kpa": smart["vpd_kpa"],
        "fixed_pv_kwh": fixed["pv_kwh"] / 6, "smart_pv_kwh": smart["pv_kwh"] / 6,
    })

"""Solar panel sizing for the cooling load. Owned by Mustafa.

STUB: returns fake but correctly shaped data until Mustafa replaces it
(docs/03-team-tasks.md, section 7, step 3).
"""

import pandas as pd


def size_solar(cooling_kwh_peak_day: float, climate_df: pd.DataFrame) -> dict:
    """Peak-day cooling energy (kWh) + climate table -> solar_kw, solar_kwh_year, peak_sun_hours."""
    # TODO(Mustafa): real sizing from ghi_wh_m2 and performance_ratio in data/settings.csv.
    if cooling_kwh_peak_day <= 0:
        return {"solar_kw": 0.0, "solar_kwh_year": 0.0, "peak_sun_hours": 0.0}
    return {"solar_kw": 10.0, "solar_kwh_year": 14600.0, "peak_sun_hours": 5.0}

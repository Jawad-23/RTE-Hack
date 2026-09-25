"""Crop table and month-by-month open-field crop check. Owned by Mustafa."""

from pathlib import Path

import pandas as pd

from planner.schemas import STATUS

CROPS_CSV = Path(__file__).resolve().parent.parent / "data" / "crops.csv"
RISKY_MARGIN_C = 3.0  # daily max up to this far above t_max_c is "risky", beyond it "impossible"


def load_crops() -> pd.DataFrame:
    """No input -> DataFrame from data/crops.csv, one row per crop."""
    return pd.read_csv(CROPS_CSV)


def monthly_daily_extremes(climate_df: pd.DataFrame) -> pd.DataFrame:
    """Climate table -> DataFrame indexed by month 1–12: tmax_c, tmin_c = average daily max/min temperature (°C)."""
    day = climate_df["hour_of_year"] // 24
    daily = climate_df.groupby(day).agg(month=("month", "first"), tmax_c=("temp_c", "max"), tmin_c=("temp_c", "min"))
    return daily.groupby("month")[["tmax_c", "tmin_c"]].mean()


def crop_status(tmax_c: float, tmin_c: float, t_min_c: float, t_max_c: float) -> str:
    """Average daily max/min (°C) and the crop's limits (°C) -> "good", "risky" or "impossible"."""
    if tmax_c <= t_max_c and tmin_c >= t_min_c:
        return STATUS[0]
    if tmax_c <= t_max_c + RISKY_MARGIN_C and tmin_c >= t_min_c:
        return STATUS[1]
    return STATUS[2]


def crop_calendar(climate_df: pd.DataFrame, crops_df: pd.DataFrame) -> pd.DataFrame:
    """Climate table + crop table -> DataFrame: rows = crop, columns = months 1–12, values from STATUS."""
    months = monthly_daily_extremes(climate_df)
    rows = {
        crop.crop: [crop_status(months.at[m, "tmax_c"], months.at[m, "tmin_c"], crop.t_min_c, crop.t_max_c) for m in range(1, 13)]
        for crop in crops_df.itertuples(index=False)
    }
    return pd.DataFrame.from_dict(rows, orient="index", columns=list(range(1, 13)))

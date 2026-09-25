"""Crop table and month-by-month open-field crop check. Owned by Mustafa."""

from pathlib import Path

import pandas as pd

from planner.schemas import STATUS

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CROPS_CSV = DATA_DIR / "crops.csv"


def load_crops() -> pd.DataFrame:
    """No input -> DataFrame from data/crops.csv, one row per crop."""
    return pd.read_csv(CROPS_CSV)


def monthly_daily_extremes(climate_df: pd.DataFrame) -> pd.DataFrame:
    """Climate table -> DataFrame indexed by month 1–12: tmax_c, tmin_c = average daily max/min temperature (°C)."""
    day = climate_df["hour_of_year"] // 24
    daily = climate_df.groupby(day).agg(month=("month", "first"), tmax_c=("temp_c", "max"), tmin_c=("temp_c", "min"))
    return daily.groupby("month")[["tmax_c", "tmin_c"]].mean()


def risky_margin_c() -> float:
    """How far (°C) the average daily max may exceed t_max_c and still be "risky", from data/settings.csv."""
    df = pd.read_csv(DATA_DIR / "settings.csv")
    return float(df.loc[df["key"] == "risky_margin_c", "value"].iloc[0])


def crop_status(tmax_c: float, tmin_c: float, t_min_c: float, t_max_c: float, margin_c: float | None = None) -> str:
    """Average daily max/min (°C), the crop's limits (°C) and the risky margin (°C) -> "good", "risky" or "impossible"."""
    margin_c = risky_margin_c() if margin_c is None else margin_c
    if tmax_c <= t_max_c and tmin_c >= t_min_c:
        return STATUS[0]
    if tmax_c <= t_max_c + margin_c and tmin_c >= t_min_c:
        return STATUS[1]
    return STATUS[2]


def crop_calendar(climate_df: pd.DataFrame, crops_df: pd.DataFrame) -> pd.DataFrame:
    """Climate table + crop table -> DataFrame: rows = crop, columns = months 1–12, values from STATUS."""
    months = monthly_daily_extremes(climate_df)
    margin_c = risky_margin_c()
    rows = {
        crop.crop: [crop_status(months.at[m, "tmax_c"], months.at[m, "tmin_c"], crop.t_min_c, crop.t_max_c, margin_c) for m in range(1, 13)]
        for crop in crops_df.itertuples(index=False)
    }
    return pd.DataFrame.from_dict(rows, orient="index", columns=list(range(1, 13)))

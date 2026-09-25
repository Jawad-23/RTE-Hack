"""Crop table and month-by-month crop check. Owned by Mustafa.

STUB: load_crops() is real; crop_calendar() returns fake but correctly shaped data
until Mustafa replaces it (docs/03-team-tasks.md, section 7, step 4).
"""

from pathlib import Path

import pandas as pd

from planner.schemas import STATUS

CROPS_CSV = Path(__file__).resolve().parent.parent / "data" / "crops.csv"


def load_crops() -> pd.DataFrame:
    """No input -> DataFrame from data/crops.csv, one row per crop."""
    return pd.read_csv(CROPS_CSV)


def crop_calendar(climate_df: pd.DataFrame, crops_df: pd.DataFrame) -> pd.DataFrame:
    """Climate table + crop table -> DataFrame: rows = crop, columns = months 1–12, values from STATUS."""
    # TODO(Mustafa): replace with the real good/risky/impossible check.
    months = list(range(1, 13))
    fake = [[STATUS[0] if m in (11, 12, 1, 2, 3) else STATUS[1] for m in months] for _ in crops_df["crop"]]
    return pd.DataFrame(fake, index=crops_df["crop"], columns=months)

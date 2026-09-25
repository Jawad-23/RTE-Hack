"""NASA POWER fetch and typical-year builder. Owned by Me.

get_typical_year(lat, lon) returns an 8,760-row hourly table (CLIMATE_COLUMNS) built by
averaging several recent years of NASA POWER data, cached under data/cache/.
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from planner.schemas import CLIMATE_COLUMNS, HOURS_PER_YEAR

POWER_URL = "https://power.larc.nasa.gov/api/temporal/hourly/point"
POWER_PARAMS = {
    "T2M": "temp_c",
    "RH2M": "rh_pct",
    "ALLSKY_SFC_SW_DWN": "ghi_wh_m2",
    "WS2M": "wind_ms",
}
FILL_VALUE = -999.0
N_YEARS = 5
REQUEST_TIMEOUT_S = 90
RETRIES = 3

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"

# Hourly irradiance unit -> factor to convert into Wh/m² for that hour
GHI_UNIT_FACTORS = {
    "wh/m^2": 1.0,
    "w/m^2": 1.0,  # mean W/m² over one hour == Wh/m² in that hour
    "kw-hr/m^2": 1000.0,
    "kwh/m^2": 1000.0,
    "mj/hr": 1e6 / 3600.0,
    "mj/m^2": 1e6 / 3600.0,
}

SOURCE = {
    "name": "NASA POWER hourly (T2M, RH2M, ALLSKY_SFC_SW_DWN, WS2M)",
    "url": "https://power.larc.nasa.gov/",
}


class ClimateUnavailable(RuntimeError):
    """Raised when no cached data exists and NASA POWER cannot be reached."""


def cache_path(lat: float, lon: float) -> Path:
    """Cache file for a pin, rounded to 2 decimals (about 1 km)."""
    return CACHE_DIR / f"{lat:.2f}_{lon:.2f}.csv"


def default_years(today: date | None = None) -> list[int]:
    """The N_YEARS most recent full calendar years."""
    last = (today or date.today()).year - 1
    return list(range(last - N_YEARS + 1, last + 1))


def get_typical_year(lat: float, lon: float, years: list[int] | None = None) -> pd.DataFrame:
    """lat, lon in degrees -> DataFrame with CLIMATE_COLUMNS, 8,760 hourly rows. Reads the cache first."""
    path = cache_path(lat, lon)
    if path.exists():
        return _validate(pd.read_csv(path))

    yearly = []
    errors = []
    for year in years or default_years():
        try:
            yearly.append(fetch_year(lat, lon, year))
        except requests.ConnectionError as exc:
            errors.append(f"{year}: {exc}")
            break  # offline: don't spend retries on every other year
        except (requests.RequestException, ValueError, KeyError) as exc:
            errors.append(f"{year}: {exc}")
    if not yearly:
        raise ClimateUnavailable(
            f"No climate data for ({lat:.2f}, {lon:.2f}): NASA POWER unreachable and no cache. "
            + "; ".join(errors)
        )

    typical = build_typical_year(pd.concat(yearly, ignore_index=True))
    path.parent.mkdir(parents=True, exist_ok=True)
    typical.to_csv(path, index=False)
    return typical


def fetch_year(lat: float, lon: float, year: int) -> pd.DataFrame:
    """One calendar year of hourly NASA POWER data -> DataFrame with timestamp + climate columns."""
    params = {
        "parameters": ",".join(POWER_PARAMS),
        "community": "AG",
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "start": f"{year}0101",
        "end": f"{year}1231",
        "format": "JSON",
        "time-standard": "LST",
    }
    last_exc: Exception | None = None
    for attempt in range(RETRIES):
        try:
            resp = requests.get(POWER_URL, params=params, timeout=REQUEST_TIMEOUT_S)
            resp.raise_for_status()
            return parse_power_json(resp.json())
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < RETRIES - 1:
                time.sleep(2**attempt)
    raise last_exc  # type: ignore[misc]


def parse_power_json(payload: dict) -> pd.DataFrame:
    """NASA POWER hourly JSON -> DataFrame(timestamp, temp_c, rh_pct, ghi_wh_m2, wind_ms), fill values as NaN."""
    series = payload["properties"]["parameter"]
    units = {k: str(v.get("units", "")).lower() for k, v in payload.get("parameters", {}).items()}

    frame = pd.DataFrame({col: pd.Series(series[name], dtype=float) for name, col in POWER_PARAMS.items()})
    frame = frame.mask(frame <= FILL_VALUE + 0.5)

    ghi_unit = units.get("ALLSKY_SFC_SW_DWN", "wh/m^2")
    if ghi_unit not in GHI_UNIT_FACTORS:
        raise ValueError(f"Unexpected ALLSKY_SFC_SW_DWN unit: {ghi_unit!r}")
    frame["ghi_wh_m2"] = frame["ghi_wh_m2"] * GHI_UNIT_FACTORS[ghi_unit]

    frame.index = pd.to_datetime(frame.index, format="%Y%m%d%H")
    frame.index.name = "timestamp"
    return frame.reset_index()


def build_typical_year(hourly: pd.DataFrame) -> pd.DataFrame:
    """Multi-year hourly data -> one typical year: drop 29 Feb, average each (month, day, hour) across years."""
    ts = pd.to_datetime(hourly["timestamp"])
    hourly = hourly[~((ts.dt.month == 2) & (ts.dt.day == 29))].copy()
    ts = pd.to_datetime(hourly["timestamp"])
    hourly["month"], hourly["day"], hourly["hour"] = ts.dt.month, ts.dt.day, ts.dt.hour

    values = [c for c in CLIMATE_COLUMNS if c not in ("hour_of_year", "month")]
    typical = hourly.groupby(["month", "day", "hour"], as_index=False)[values].mean()

    # Guarantee every hour of a non-leap year exists, then fill gaps no year covered.
    full = pd.date_range("2001-01-01 00:00", periods=HOURS_PER_YEAR, freq="h")
    grid = pd.DataFrame({"month": full.month, "day": full.day, "hour": full.hour})
    typical = grid.merge(typical, on=["month", "day", "hour"], how="left")
    typical[values] = typical[values].interpolate(limit_direction="both")

    typical["hour_of_year"] = np.arange(HOURS_PER_YEAR)
    typical["ghi_wh_m2"] = typical["ghi_wh_m2"].clip(lower=0)
    typical["rh_pct"] = typical["rh_pct"].clip(0, 100)
    return _validate(typical[CLIMATE_COLUMNS])


def _validate(df: pd.DataFrame) -> pd.DataFrame:
    """Check the table matches the shared contract."""
    missing = [c for c in CLIMATE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Climate table missing columns: {missing}")
    if len(df) != HOURS_PER_YEAR:
        raise ValueError(f"Climate table has {len(df)} rows, expected {HOURS_PER_YEAR}")
    if df[CLIMATE_COLUMNS].isna().any().any():
        raise ValueError("Climate table contains NaN values")
    df = df[CLIMATE_COLUMNS].copy()
    df["hour_of_year"] = df["hour_of_year"].astype(int)
    df["month"] = df["month"].astype(int)
    return df


def source_info(lat: float, lon: float) -> dict:
    """Source entry for the plan: dataset name, URL, and when the cached data was fetched."""
    path = cache_path(lat, lon)
    fetched = date.fromtimestamp(path.stat().st_mtime).isoformat() if path.exists() else None
    return {**SOURCE, "fetched": fetched}


if __name__ == "__main__":
    import sys

    lat_arg, lon_arg = float(sys.argv[1]), float(sys.argv[2])
    df = get_typical_year(lat_arg, lon_arg)
    print(df.describe().round(1))
    print(f"Cached at {cache_path(lat_arg, lon_arg)}")

"""NASA POWER fetch and typical-year builder. Owned by Me.

get_typical_year(lat, lon) returns an 8,760-row hourly table (CLIMATE_COLUMNS) built by
averaging several recent years of NASA POWER data, cached under data/cache/.
"""

from __future__ import annotations

import time
import json
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
SPECTRAL_PARAMS = {
    "ALLSKY_SFC_PAR_TOT": "par_w_m2",
    "ALLSKY_SFC_UVA": "uva_w_m2",
    "ALLSKY_SFC_UVB": "uvb_w_m2",
    "ALLSKY_SFC_LW_DWN": "lw_down_w_m2",
    "CLRSKY_SFC_SW_DWN": "clearsky_ghi_w_m2",
    "CLRSKY_SFC_PAR_TOT": "clearsky_par_w_m2",
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
    "name": "NASA POWER hourly weather and spectral irradiance (PAR, UV, longwave and clear sky)",
    "url": "https://power.larc.nasa.gov/",
}


class ClimateUnavailable(RuntimeError):
    """Raised when no cached data exists and NASA POWER cannot be reached."""


def cache_path(lat: float, lon: float) -> Path:
    """Cache file scoped by schema, requested years and four-decimal coordinates."""
    years = default_years()
    return CACHE_DIR / f"v2_{years[0]}-{years[-1]}_{lat:.4f}_{lon:.4f}.csv"


def default_years(today: date | None = None) -> list[int]:
    """The N_YEARS most recent full calendar years."""
    last = (today or date.today()).year - 1
    return list(range(last - N_YEARS + 1, last + 1))


def get_typical_year(lat: float, lon: float, years: list[int] | None = None) -> pd.DataFrame:
    """lat, lon in degrees -> DataFrame with CLIMATE_COLUMNS, 8,760 hourly rows. Reads the cache first."""
    if not np.isfinite([lat, lon]).all() or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Coordinates must be finite and within latitude/longitude bounds")
    path = cache_path(lat, lon)
    if years is not None:
        path = path.with_stem(path.stem + "_" + "-".join(map(str, sorted(set(years)))))
    if path.exists():
        try:
            return _validate(pd.read_csv(path))
        except (ValueError, pd.errors.ParserError):
            pass  # Re-fetch corrupt or incompatible cached data.

    yearly = []
    used_years = []
    errors = []
    for year in years or default_years():
        try:
            yearly.append(fetch_year(lat, lon, year))
            used_years.append(year)
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

    try:
        typical = build_typical_year(pd.concat(yearly, ignore_index=True))
    except (ValueError, KeyError) as exc:
        raise ClimateUnavailable(f"NASA data is incomplete for this site: {exc}") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    typical.to_csv(path, index=False)
    path.with_suffix(".json").write_text(json.dumps({"years": used_years, "warnings": errors,
        "fetched": date.today().isoformat(), "latitude": lat, "longitude": lon}), encoding="utf-8")
    return typical


def fetch_year(lat: float, lon: float, year: int) -> pd.DataFrame:
    """One calendar year of hourly NASA POWER data -> DataFrame with timestamp + climate columns."""
    params = {
        "parameters": ",".join({**POWER_PARAMS, **SPECTRAL_PARAMS}),
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
    for name, col in SPECTRAL_PARAMS.items():
        if name in series:
            unit = units.get(name, "")
            if unit not in GHI_UNIT_FACTORS:
                raise ValueError(f"Unexpected {name} unit: {unit!r}")
            values = pd.Series(series[name], dtype=float).reindex(frame.index)
            frame[col] = values.mask(values <= FILL_VALUE + 0.5) * GHI_UNIT_FACTORS[unit]

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
    values += [c for c in SPECTRAL_PARAMS.values() if c in hourly]
    typical = hourly.groupby(["month", "day", "hour"], as_index=False)[values].mean()

    # Guarantee every hour of a non-leap year exists, then fill gaps no year covered.
    full = pd.date_range("2001-01-01 00:00", periods=HOURS_PER_YEAR, freq="h")
    grid = pd.DataFrame({"month": full.month, "day": full.day, "hour": full.hour})
    typical = grid.merge(typical, on=["month", "day", "hour"], how="left")
    if typical[values].isna().mean().max() > 0.05:
        raise ValueError("More than 5% of hours are missing in at least one weather variable")
    typical[values] = typical[values].interpolate(limit_direction="both")

    typical["hour_of_year"] = np.arange(HOURS_PER_YEAR)
    typical["ghi_wh_m2"] = typical["ghi_wh_m2"].clip(lower=0)
    typical["rh_pct"] = typical["rh_pct"].clip(0, 100)
    cols = CLIMATE_COLUMNS + [c for c in SPECTRAL_PARAMS.values() if c in typical]
    result = typical[cols].copy()
    if {"par_w_m2", "uva_w_m2", "uvb_w_m2"} <= set(result):
        result["uv_w_m2"] = result["uva_w_m2"] + result["uvb_w_m2"]
        result["nir_w_m2"] = (result["ghi_wh_m2"] - result["par_w_m2"] - result["uv_w_m2"]).clip(lower=0)
        result["heat_share"] = result["nir_w_m2"].div(result["ghi_wh_m2"].where(result["ghi_wh_m2"] > 0))
    return _validate(result)


def _validate(df: pd.DataFrame) -> pd.DataFrame:
    """Check the table matches the shared contract."""
    missing = [c for c in CLIMATE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Climate table missing columns: {missing}")
    if len(df) != HOURS_PER_YEAR:
        raise ValueError(f"Climate table has {len(df)} rows, expected {HOURS_PER_YEAR}")
    if df[CLIMATE_COLUMNS].isna().any().any():
        raise ValueError("Climate table contains NaN values")
    df = df.copy()
    numeric = df.select_dtypes(include="number").drop(columns=["heat_share"], errors="ignore")
    if not np.isfinite(numeric.to_numpy()).all():
        raise ValueError("Climate table contains non-finite values")
    df["hour_of_year"] = df["hour_of_year"].astype(int)
    df["month"] = df["month"].astype(int)
    return df


def source_info(lat: float, lon: float) -> dict:
    """Source entry for the plan: dataset name, URL, and when the cached data was fetched."""
    path = cache_path(lat, lon)
    fetched = date.fromtimestamp(path.stat().st_mtime).isoformat() if path.exists() else None
    metadata = {}
    if path.with_suffix(".json").exists():
        try:
            metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {**SOURCE, "fetched": fetched, **metadata}


if __name__ == "__main__":
    import sys

    lat_arg, lon_arg = float(sys.argv[1]), float(sys.argv[2])
    df = get_typical_year(lat_arg, lon_arg)
    print(df.describe().round(1))
    print(f"Cached at {cache_path(lat_arg, lon_arg)}")

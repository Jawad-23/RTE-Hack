"""Live crop prices: FAOSTAT producer prices for the country under the pin.

prices_for(lat, lon) finds the pin's country (OpenStreetMap Nominatim), then reads that country's
latest FAOSTAT farm-gate price for every crop in data/crops.csv (column faostat_item_code).

Where the data comes from, freshest first:
1. data/cache/faostat_prices.csv, downloaded from FAOSTAT, or
2. data/snapshots/faostat_prices.csv, the same table committed to the repo so the app works offline.
   Regenerate it with:  python -m planner.market --refresh-snapshot
Whichever is newer is used. FAOSTAT is only downloaded when both are older than REFRESH_DAYS, and a
failed download is not retried for RETRY_AFTER_S, so no plan waits on FAOSTAT more than once.

If the country has no recent price for a crop, the price is estimated as the world median for that
crop times the country's price level (median of its own price / world median over the crops it does
report). If the pin has no country, or the country has no data at all, the world median is used.
Each price says which of these methods produced it.
"""

from __future__ import annotations

import io
import json
import time
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from planner import crops

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_CSV = DATA_DIR / "cache" / "faostat_prices.csv"
SNAPSHOT_CSV = DATA_DIR / "snapshots" / "faostat_prices.csv"
GEO_CACHE = DATA_DIR / "cache" / "countries.json"

FAOSTAT_ZIP = "https://bulks-faostat.fao.org/production/Prices_E_All_Data_(Normalized).zip"
FAOSTAT_PAGE = "https://www.fao.org/faostat/en/#data/PP"
NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "Croptions/1.0 (https://github.com/Jawad-23/RTE-Hack)"  # Nominatim requires an identifying agent

ELEMENT = "Producer Price (USD/tonne)"
REFRESH_DAYS = 30
MAX_AGE_YEARS = 6        # ignore a country's price if its latest year is older than this
DOWNLOAD_TIMEOUT_S = 60
RETRY_AFTER_S = 6 * 3600  # after a failed download, use the saved table for this long before trying again
GEO_TIMEOUT_S = 10

_last_failed_download: float | None = None  # time.monotonic() of this process's last failed download

METHODS = {
    "country": "FAOSTAT {year} farm-gate price for {country}",
    "scaled": "World median scaled by {country}'s price level (no recent {country} price for this crop)",
    "world": "World median FAOSTAT farm-gate price",
}


# ---------- FAOSTAT table ----------

def download_prices(item_codes: list[int]) -> pd.DataFrame:
    """FAOSTAT bulk zip -> tidy table (m49, area, item_code, item, year, usd_tonne), latest year per country and item."""
    resp = requests.get(FAOSTAT_ZIP, timeout=DOWNLOAD_TIMEOUT_S)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        name = next(n for n in z.namelist() if n.startswith("Prices_E_All_Data") and n.endswith(".csv"))
        with z.open(name) as f:
            raw = pd.read_csv(f, encoding="latin-1", usecols=["Area Code", "Area Code (M49)", "Area", "Item Code", "Item", "Element", "Year", "Value"])
    return tidy_prices(raw, item_codes)


def tidy_prices(raw: pd.DataFrame, item_codes: list[int]) -> pd.DataFrame:
    """Raw FAOSTAT rows -> latest USD/tonne price per (country, item) for the given items; regions and aggregates dropped."""
    df = raw[(raw["Element"] == ELEMENT) & raw["Item Code"].isin(item_codes) & raw["Value"].notna()].copy()
    df = df[df["Area Code"] < 5000]  # FAOSTAT codes 5000+ are regions and country groups, not countries
    df["m49"] = df["Area Code (M49)"].astype(str).str.strip("'").astype(int)
    df = df.sort_values("Year").groupby(["m49", "Item Code"], as_index=False).last()
    return (df.rename(columns={"Area": "area", "Item Code": "item_code", "Item": "item", "Year": "year", "Value": "usd_tonne"})
              [["m49", "area", "item_code", "item", "year", "usd_tonne"]].reset_index(drop=True))


def load_price_table(refresh: bool = True) -> tuple[pd.DataFrame, str]:
    """-> (price table, date it was fetched): the newer of cache and snapshot; downloads only when both are stale."""
    global _last_failed_download
    saved = [t for t in (_read_table(CACHE_CSV), _read_table(SNAPSHOT_CSV)) if t is not None]
    best = max(saved, key=lambda t: t[1], default=None)
    stale = best is None or (date.today() - best[1]).days >= REFRESH_DAYS
    failed_recently = _last_failed_download is not None and time.monotonic() - _last_failed_download < RETRY_AFTER_S
    if not refresh or not stale or failed_recently:
        return best or _missing()
    try:
        table = download_prices(_item_codes())
        _write_table(table, CACHE_CSV)
        return table, date.today().isoformat()
    except (requests.RequestException, zipfile.BadZipFile, ValueError, KeyError, StopIteration, OSError, MemoryError):
        _last_failed_download = time.monotonic()
        return best or _missing()


def _read_table(path: Path):
    if not path.exists():
        return None
    try:
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        return pd.read_csv(path), date.fromisoformat(meta["fetched"])
    except (OSError, ValueError, KeyError, pd.errors.ParserError):
        return None


def _write_table(table: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False)
    path.with_suffix(".json").write_text(json.dumps({"fetched": date.today().isoformat(), "url": FAOSTAT_ZIP}), encoding="utf-8")


def _missing():
    raise FileNotFoundError(f"No FAOSTAT prices: download failed and {SNAPSHOT_CSV} is missing")


def _item_codes() -> list[int]:
    return [int(c) for c in crops.load_crops()["faostat_item_code"].dropna()]


# ---------- Country under the pin ----------

def country_for(lat: float, lon: float) -> dict | None:
    """Pin (°) -> {"name", "m49"} of the country it falls in, or None (sea, or lookup failed). Cached per 0.1°."""
    key = f"{lat:.1f},{lon:.1f}"
    cache = {}
    if GEO_CACHE.exists():
        try:
            cache = json.loads(GEO_CACHE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cache = {}
    if key in cache:
        return cache[key]
    try:
        resp = requests.get(NOMINATIM_REVERSE, params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 3, "accept-language": "en"},
                            headers={"User-Agent": USER_AGENT}, timeout=GEO_TIMEOUT_S)
        resp.raise_for_status()
        address = resp.json().get("address", {})
    except (requests.RequestException, ValueError):
        return None  # not cached, so the next plan tries again
    found = _country_from_iso2(address.get("country_code"), address.get("country"))
    cache[key] = found
    GEO_CACHE.parent.mkdir(parents=True, exist_ok=True)
    GEO_CACHE.write_text(json.dumps(cache), encoding="utf-8")
    return found


def _country_from_iso2(iso2: str | None, name: str | None) -> dict | None:
    import pycountry

    country = pycountry.countries.get(alpha_2=iso2.upper()) if iso2 else None
    return {"name": name or country.name, "m49": int(country.numeric)} if country else None


# ---------- Prices for a pin ----------

def prices_for(lat: float, lon: float, usd_to_qar: float) -> dict:
    """Pin (°), QAR per USD -> {"country", "fetched", "prices": {crop: {price_qar_kg, method, year, note}}}."""
    table, fetched = load_price_table()
    country = country_for(lat, lon)
    return {"country": country, "fetched": str(fetched), "prices": price_per_crop(table, country, usd_to_qar)}


def price_per_crop(table: pd.DataFrame, country: dict | None, usd_to_qar: float) -> dict:
    """Price table, country (or None), QAR per USD -> {crop: {price_qar_kg, method, year, note}} for every crop in crops.csv."""
    recent = table[table["year"] >= table["year"].max() - MAX_AGE_YEARS]
    world = recent.groupby("item_code")["usd_tonne"].median()
    own = recent[recent["m49"] == country["m49"]].set_index("item_code") if country else recent.iloc[0:0].set_index("item_code")
    level = (own["usd_tonne"] / world.reindex(own.index)).median() if len(own) else None
    name = country["name"] if country else ""

    out = {}
    for row in crops.load_crops().itertuples(index=False):
        code = int(row.faostat_item_code)
        if code in own.index:
            usd, method, year = own.at[code, "usd_tonne"], "country", int(own.at[code, "year"])
        elif code in world.index and level is not None:
            usd, method, year = world[code] * level, "scaled", None
        elif code in world.index:
            usd, method, year = world[code], "world", None
        else:
            continue
        out[row.crop] = {
            "price_qar_kg": round(float(usd) * usd_to_qar / 1000, 2),
            "method": method,
            "year": year,
            "note": METHODS[method].format(year=year, country=name),
        }
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Show FAOSTAT prices for a pin, or refresh the committed snapshot.")
    ap.add_argument("lat", type=float, nargs="?", default=25.29)
    ap.add_argument("lon", type=float, nargs="?", default=51.53)
    ap.add_argument("--refresh-snapshot", action="store_true", help=f"download FAOSTAT and rewrite {SNAPSHOT_CSV.relative_to(DATA_DIR.parent)}")
    args = ap.parse_args()
    if args.refresh_snapshot:
        snap = download_prices(_item_codes())
        _write_table(snap, SNAPSHOT_CSV)
        print(f"Wrote {len(snap)} rows to {SNAPSHOT_CSV}")
    from planner.solar import load_settings

    result = prices_for(args.lat, args.lon, load_settings()["usd_to_qar"])
    print(f"Country: {result['country']}  (prices fetched {result['fetched']})")
    for crop, p in result["prices"].items():
        print(f"  {crop:12} {p['price_qar_kg']:6.2f} QAR/kg   {p['note']}")

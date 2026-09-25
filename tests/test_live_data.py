"""FAOSTAT prices by country and FAO-56 water use."""

import numpy as np
import pandas as pd
import pytest

from planner import cooling, crops, market, optimizer, solar, water


def _raw(rows):
    return pd.DataFrame(rows, columns=["Area Code", "Area Code (M49)", "Area", "Item Code", "Item", "Element", "Year", "Value"])


def test_tidy_prices_keeps_latest_country_rows_and_drops_regions():
    usd = market.ELEMENT
    raw = _raw([
        [179, "'634", "Qatar", 388, "Tomatoes", usd, 2021, 500.0],
        [179, "'634", "Qatar", 388, "Tomatoes", usd, 2023, 549.5],
        [179, "'634", "Qatar", 388, "Tomatoes", "Producer Price (LCU/tonne)", 2023, 2000.0],
        [5100, "'002", "Africa", 388, "Tomatoes", usd, 2023, 700.0],
        [179, "'634", "Qatar", 999, "Other", usd, 2023, 1.0],
    ])
    out = market.tidy_prices(raw, [388])
    assert out.to_dict(orient="records") == [
        {"m49": 634, "area": "Qatar", "item_code": 388, "item": "Tomatoes", "year": 2023, "usd_tonne": 549.5}]


def test_country_price_then_scaled_then_world():
    table = pd.DataFrame([
        # Country 1 reports tomato at double the world median; country 2 reports cucumber only.
        {"m49": 1, "area": "A", "item_code": 388, "item": "Tomatoes", "year": 2023, "usd_tonne": 1000.0},
        {"m49": 2, "area": "B", "item_code": 388, "item": "Tomatoes", "year": 2023, "usd_tonne": 500.0},
        {"m49": 3, "area": "C", "item_code": 388, "item": "Tomatoes", "year": 2023, "usd_tonne": 300.0},
        {"m49": 2, "area": "B", "item_code": 397, "item": "Cucumbers", "year": 2023, "usd_tonne": 400.0},
    ])
    a = market.price_per_crop(table, {"name": "A", "m49": 1}, usd_to_qar=1)
    assert a["tomato"] == {"price_qar_kg": 1.0, "method": "country", "year": 2023, "note": "FAOSTAT 2023 farm-gate price for A"}
    assert a["cucumber"]["method"] == "scaled" and a["cucumber"]["price_qar_kg"] == 0.8  # 400 × (1000 / 500)
    sea = market.price_per_crop(table, None, usd_to_qar=1)
    assert sea["tomato"]["method"] == "world" and sea["tomato"]["price_qar_kg"] == 0.5
    assert "lettuce" not in a  # no data anywhere: left out, so economics reports the missing price


def test_snapshot_gives_qatar_a_price_for_every_crop():
    table, _ = market._read_table(market.SNAPSHOT_CSV)
    prices = market.price_per_crop(table, {"name": "Qatar", "m49": 634}, solar.load_settings()["usd_to_qar"])
    assert set(prices) == set(crops.load_crops()["crop"])
    assert all(p["price_qar_kg"] > 0 for p in prices.values())


def test_et0_matches_fao56_example_19():
    # FAO-56 Example 19 (hourly, 14-15 h): 38 °C, 52 % RH, 2.450 MJ/m² solar, 3.3 m/s wind -> ET0 0.63 mm/h
    assert water.et0_mm_hour(38, 52, 2.45 / 0.0036, 3.3, 0.8) == pytest.approx(0.63, abs=0.02)


def test_et0_is_zero_or_more_at_night():
    assert water.et0_mm_hour(20, 90, 0, 0.5)[()] >= 0


def test_seasonal_kc_sits_between_initial_and_mid():
    assert 0.6 < water.seasonal_kc(0.6, 1.15, 0.8) < 1.15


def _water(year, setup, growing=range(1, 13)):
    crop = crops.load_crops().query("crop == 'tomato'").iloc[0].to_dict()
    prof = cooling.hourly_profile(year, setup, 500, crop)
    return water.water_l_m2_day(year, prof, crop, cooling.load_setups().loc[setup], list(growing), solar.load_settings())


def test_open_field_needs_no_pad_water_and_pads_evaporate_more_in_dry_air(dry_year, humid_year):
    assert _water(dry_year, "open_field")["pad_l_m2_day"] == 0
    assert _water(dry_year, "wet_pad")["pad_l_m2_day"] > _water(humid_year, "wet_pad")["pad_l_m2_day"] > 0


def test_shade_and_greenhouse_cut_crop_water_compared_with_open_field(dry_year):
    open_field = _water(dry_year, "open_field")["crop_l_m2_day"]
    assert _water(dry_year, "shade_net")["crop_l_m2_day"] < open_field
    assert _water(dry_year, "wet_pad")["crop_l_m2_day"] < open_field


def test_plan_reports_price_source_and_water_breakdown(dry_year, monkeypatch):
    monkeypatch.setattr(optimizer.climate, "get_typical_year", lambda lat, lon: dry_year)
    p = optimizer.plan(25.29, 51.53, 500, 250_000, "profit", crop="tomato")
    assert "Qatar" in p["sources"][1]["name"] and p["assumptions"]["prices"][0]["crop"] == "tomato"
    for o in p["options"]:
        assert o["price_qar_kg"] > 0
        assert o["water_l_day"] == pytest.approx(o["irrigation_l_day"] + o["pad_water_l_day"], abs=0.1)
    assert np.isfinite([o["et0_mm_day"] for o in p["options"]]).all()


# conftest replaces load_price_table with the snapshot for every test; keep the real one for these.
_REAL_LOAD_PRICE_TABLE = market.load_price_table


def _saved_table(path, fetched):
    table = pd.DataFrame([{"m49": 634, "area": "Qatar", "item_code": 388, "item": "Tomatoes", "year": 2023, "usd_tonne": 549.5}])
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False)
    path.with_suffix(".json").write_text(f'{{"fetched": "{fetched}"}}', encoding="utf-8")


@pytest.fixture
def price_files(tmp_path, monkeypatch):
    monkeypatch.setattr(market, "CACHE_CSV", tmp_path / "cache" / "faostat_prices.csv")
    monkeypatch.setattr(market, "SNAPSHOT_CSV", tmp_path / "snapshots" / "faostat_prices.csv")
    monkeypatch.setattr(market, "_last_failed_download", None)
    calls = []
    monkeypatch.setattr(market, "download_prices", lambda codes: calls.append(1) or (_ for _ in ()).throw(market.requests.Timeout("slow")))
    return calls


def test_fresh_snapshot_is_used_without_downloading(price_files):
    from datetime import date
    _saved_table(market.SNAPSHOT_CSV, date.today().isoformat())  # new container: no cache, recent snapshot
    table, fetched = _REAL_LOAD_PRICE_TABLE()
    assert len(table) == 1 and fetched == date.today() and price_files == []


def test_failed_download_is_not_retried_by_the_next_plan(price_files):
    _saved_table(market.SNAPSHOT_CSV, "2020-01-01")  # everything stale, FAOSTAT times out
    for _ in range(3):
        table, _ = _REAL_LOAD_PRICE_TABLE()
        assert len(table) == 1
    assert price_files == [1]

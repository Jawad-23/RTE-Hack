"""Kit page screen choice: PAR:NIR spectrum, canopy stress, maintenance and hazards (planner/screens.py)."""

import numpy as np
import pytest

from planner import crops, screens, solar

TOMATO = crops.load_crops().set_index("crop").loc["tomato"].to_dict()


def test_coated_etfe_raises_the_par_to_nir_ratio_and_aluminium_keeps_it(dry_year):
    cfg = solar.load_settings()
    etfe = screens.spectrum(dry_year, "etfe_coated", TOMATO, 100, 200, cfg["par_umol_j"])
    alu = screens.spectrum(dry_year, "aluminium_strip", TOMATO, 100, 200, cfg["par_umol_j"])
    assert etfe["ratio_inside"] > etfe["ratio_outside"] * 1.5          # 0.85 PAR / 0.45 NIR
    assert alu["ratio_inside"] == pytest.approx(alu["ratio_outside"] * 0.45 / 0.40, rel=0.01)
    assert etfe["dli_inside"] == pytest.approx(etfe["dli_outside"] * 0.85, rel=0.01)


def test_open_aluminium_screen_passes_everything():
    assert screens.transmission("aluminium_strip", 0) == {"par": 1.0, "nir": 1.0, "uv": 1.0}
    assert screens.transmission("etfe_coated", 0)["nir"] == 0.45  # fixed film ignores closure


def test_canopy_under_screen_is_cooler_by_day_and_unchanged_at_night():
    grid = np.full((24, 32), 40.0)
    day = screens.canopy({"leaf_c": 36.0, "air_c": 31.0, "par_w_m2": 300}, 0.7, grid, TOMATO, "etfe_coated", 100)
    assert day["band"] == "severe" and day["hotspot_pct"] == 100.0
    assert 31.0 < day["leaf_under_screen_c"] < 35.0 and day["above_limit_now"] and not day["above_limit_under_screen"]
    night = screens.canopy({"leaf_c": 25.0, "air_c": 26.0, "par_w_m2": 0}, None, grid, TOMATO, "etfe_coated", 100)
    assert night["leaf_under_screen_c"] == 25.0 and night["band"] is None


def test_maintenance_dust_speeds_up_cleaning_and_drive_service_counts_moves():
    cfg = solar.load_settings()
    calm = screens.maintenance("etfe_coated", cfg, 0, 1.0)
    dusty = screens.maintenance("etfe_coated", cfg, 0, 1.0, {"available": True, "event_hours": 72, "valid_hours": 720})
    assert dusty["clean_every_days"] < calm["clean_every_days"] and calm["service_in_days"] is None
    alu = screens.maintenance("aluminium_strip", cfg, 8, 1.0)
    assert alu["moves_per_day"] == 8 and alu["service_in_days"] == 1000


def test_heat_index_and_hazards_from_forecast():
    assert screens.heat_index_c(25, 50) == pytest.approx(24.9, abs=0.3)
    assert screens.heat_index_c(35, 60) > 40  # hot and humid feels much hotter
    fc = {"days": [{"date": "2026-09-29", "temp_max_c": 43, "rh_mean_pct": 40, "uv_max": 9, "feels_like_max_c": 47, "wind_max_kmh": 50}]}
    by = {h["code"]: h for h in screens.hazards("aluminium_strip", fc)}
    assert by["heat"]["level"] == "high" and by["heat"]["value"] == 47
    assert by["uv"]["level"] == "high" and by["wind"]["level"] == "high"  # 50 km/h is over the 45 km/h limit
    assert "drive" in by and "film" not in by
    assert {h["code"] for h in screens.hazards("etfe_coated", None)} == {"height", "film"}

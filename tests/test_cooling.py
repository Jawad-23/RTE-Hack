import pytest

from planner import cooling
from planner.schemas import HOURS_PER_YEAR, SETUPS


def test_wet_bulb_dry_vs_humid():
    dry, humid = cooling.wet_bulb_c([40.0, 40.0], [15.0, 60.0])
    assert dry == pytest.approx(20.4, abs=0.5)
    assert humid == pytest.approx(32.6, abs=0.5)


def test_wet_pad_much_cooler_at_dry_site(dry_year, humid_year):
    dry = max(cooling.simulate(dry_year, "wet_pad", 35, 500)["inside_temp_c"])
    humid = max(cooling.simulate(humid_year, "wet_pad", 35, 500)["inside_temp_c"])
    assert humid - dry > 8


@pytest.mark.parametrize("setup", SETUPS)
def test_simulate_matches_contract(dry_year, setup):
    out = cooling.simulate(dry_year, setup, 35, 500)
    assert set(out) == {"inside_temp_c", "coverage_pct", "cooling_kwh_year", "cooling_kwh_peak_day"}
    assert len(out["inside_temp_c"]) == HOURS_PER_YEAR
    assert 0 <= out["coverage_pct"] <= 100
    assert all(type(v) is float for v in out["inside_temp_c"][:10])


def test_chiller_holds_setpoint_and_uses_energy(humid_year):
    setpoint = cooling.load_setups().loc["chiller", "setpoint_c"]
    out = cooling.simulate(humid_year, "chiller", 35, 500)
    assert max(out["inside_temp_c"]) <= setpoint + 1e-6
    assert out["cooling_kwh_year"] > 0
    assert 0 < out["cooling_kwh_peak_day"] <= out["cooling_kwh_year"]


def test_only_chiller_uses_electricity(dry_year):
    for setup in ("open_field", "shade_net", "wet_pad"):
        assert cooling.simulate(dry_year, setup, 35, 500)["cooling_kwh_year"] == 0


def test_unknown_setup_rejected(dry_year):
    with pytest.raises(ValueError):
        cooling.simulate(dry_year, "igloo", 35, 500)

"""Investment maths (finance.py) and the extra open data (site_data.py)."""

import pytest
import requests

from planner import finance, site_data


def test_npv_irr_and_breakeven_are_consistent():
    option = {"capex_qar": 100_000.0, "profit_qar_year": 20_000.0, "revenue_qar_year": 50_000.0, "price_qar_kg": 5.0, "export_kwh_year": 0}
    out = finance.evaluate(option, rate_pct=5)
    assert out["npv_qar"] == pytest.approx(-100_000 + 20_000 * finance.annuity(0.05), abs=0.01)
    # at the IRR the NPV is zero
    assert finance.npv(100_000, 20_000, out["irr_pct"] / 100) == pytest.approx(0, abs=50)
    # at the break-even price, profit shifts by the revenue change and NPV is zero
    be = out["breakeven_price_qar_kg"]
    profit_at_be = 20_000 + 50_000 * (be / 5 - 1)
    assert finance.npv(100_000, profit_at_be, 0.05) == pytest.approx(0, abs=500)  # break-even is rounded to 0.01 QAR/kg
    assert out["payback_price_down_years"] == pytest.approx(100_000 / (20_000 - 0.2 * 50_000), abs=0.01)


def test_no_irr_when_it_never_pays_back():
    assert finance.irr(100_000, 5_000) is None
    assert finance.evaluate({"capex_qar": None, "profit_qar_year": None}, 5)["npv_qar"] is None


def test_real_rate_from_world_bank_or_fallback():
    wb = {"available": True, "lending_rate_pct": 4.75, "lending_rate_year": 2025, "inflation_pct": 1.27, "inflation_year": 2024}
    assert finance.real_rate(wb, {})["rate_pct"] == pytest.approx(3.44, abs=0.01)
    fallback = finance.real_rate({"available": False}, {"discount_rate_fallback_pct": 4.0})
    assert fallback == {"rate_pct": 4.0, "basis": "fallback", "lending_rate_pct": None, "inflation_pct": None}


class _Resp:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


PVGIS = {"inputs": {"location": {"elevation": 16.0}, "meteo_data": {"use_horizon": True, "year_min": 2005, "year_max": 2023},
                    "mounting_system": {"fixed": {"slope": {"value": 26}, "azimuth": {"value": 14}}}},
         "outputs": {"totals": {"fixed": {"E_y": 1711.92, "H(i)_y": 2312.48, "l_tg": -11.26}},
                     "monthly": {"fixed": [{"month": m, "E_m": 100.0 + m} for m in range(1, 13)]}}}


def test_pvgis_parses_and_caches(tmp_path, monkeypatch):
    import importlib
    real = importlib.reload(site_data)  # conftest stubs the fetchers for every other test; reload gives the real ones
    monkeypatch.setattr(real, "CACHE_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(real.requests, "get", lambda *a, **k: calls.append(1) or _Resp(PVGIS))
    out = real.pvgis(25.29, 51.53)
    assert out["available"] and out["kwh_per_kw_year"] == 1711.9 and out["heat_loss_pct"] == 11.3 and out["tilt_deg"] == 26
    assert out["monthly_kwh_per_kw"][7] == 107.0
    assert real.pvgis(25.29, 51.53)["kwh_per_kw_year"] == 1711.9 and len(calls) == 1  # second call from the cache


def test_failed_call_is_unavailable_not_an_error(tmp_path, monkeypatch):
    import importlib
    real = importlib.reload(site_data)
    monkeypatch.setattr(real, "CACHE_DIR", tmp_path)

    def boom(*a, **k):
        raise requests.ConnectionError("offline")
    monkeypatch.setattr(real.requests, "get", boom)
    assert real.forecast(25.29, 51.53)["available"] is False
    assert real.money("QAT")["available"] is False
    assert real.money(None)["available"] is False


def test_failed_service_is_not_retried_on_every_plan(tmp_path, monkeypatch):
    import importlib
    real = importlib.reload(site_data)
    monkeypatch.setattr(real, "CACHE_DIR", tmp_path)
    calls = []

    def boom(*a, **k):
        calls.append(1)
        raise requests.ConnectTimeout("slow")
    monkeypatch.setattr(real.requests, "get", boom)
    assert real.forecast(25.29, 51.53)["available"] is False
    assert real.forecast(24.0, 50.0)["available"] is False  # skipped: the service failed a moment ago
    assert len(calls) == 1


def test_pvgis_gives_a_compass_bearing(tmp_path, monkeypatch):
    import importlib
    real = importlib.reload(site_data)
    monkeypatch.setattr(real, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(real.requests, "get", lambda *a, **k: _Resp(PVGIS))
    assert real.pvgis(25.29, 51.53)["bearing_deg"] == 194  # PVGIS azimuth 14 (west of south) = compass 194


def test_scan_skips_online_extras(monkeypatch):
    from planner import scan
    seen = []
    monkeypatch.setattr(scan, "plan", lambda lat, lon, **kw: seen.append(kw.get("extras")) or {"reason": "", "recommended": None})
    scan.scan_area((25.0, 51.0, 25.2, 51.2), 2, area_m2=500, budget_qar=1, priority="profit")
    assert seen == [False] * 4

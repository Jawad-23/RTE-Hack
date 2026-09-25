"""Shared rule-based screen controller; this does not control real equipment."""

import math

from planner.solar import load_settings


def decide(hour_row, crop, state, settings=None) -> dict:
    """Climate hour, crop limits and previous position -> closure (%) and reason code."""
    cfg = load_settings() if settings is None else settings
    previous = float(state.get("screen_pct", 0))
    step = cfg["screen_step_pct"]
    par = float(hour_row.get("par_w_m2", float("nan")))
    temp = float(hour_row["temp_c"])
    if not math.isfinite(par):
        return {"screen_pct": 0.0, "reason": "light_unavailable"}
    if par <= 0:
        return {"screen_pct": 0.0, "reason": "night"}
    if par < cfg["screen_min_par_w_m2"]:
        target, reason = 0.0, "protect_light"
    elif temp > float(crop["t_max_c"]) - cfg["screen_heat_margin_c"]:
        target, reason = cfg["screen_max_pct"], "reduce_heat"
    elif temp < float(crop["t_max_c"]) - cfg["screen_heat_margin_c"] - cfg["screen_hysteresis_c"]:
        target, reason = 0.0, "release_shade"
    else:
        target, reason = previous, "hold"
    position = max(previous - step, min(previous + step, target))
    return {"screen_pct": float(max(0, min(cfg["screen_max_pct"], round(position / step) * step))), "reason": reason}

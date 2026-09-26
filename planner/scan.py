"""Bounded area scan; failures at one point do not discard other results."""

import numpy as np

from planner.optimizer import plan


def grid(south: float, west: float, north: float, east: float, side: int = 3) -> list[tuple[float, float]]:
    """Rectangle bounds -> up to 25 evenly spaced points, with valid world coordinates."""
    if not np.isfinite([south, west, north, east]).all() or not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("Choose a rectangle within valid coordinates; antimeridian crossing is unsupported")
    if side not in (2, 3, 4, 5):
        raise ValueError("Grid side must be 2 to 5")
    return [(float(lat), float(lon)) for lat in np.linspace(south, north, side) for lon in np.linspace(west, east, side)]


def scan_area(bounds, side=3, **inputs) -> list[dict]:
    """Rectangle and farm inputs -> one recommendation or explicit failure per point."""
    results = []
    for lat, lon in grid(*bounds, side):
        try:
            result = plan(lat, lon, extras=False, **inputs)
            results.append({"lat": lat, "lon": lon, "reason": result["reason"], **(result["recommended"] or {})})
        except ValueError as exc:
            results.append({"lat": lat, "lon": lon, "reason": str(exc)})
    return results

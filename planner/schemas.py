# planner/schemas.py  — owned by Me. Do not edit without asking.
"""Shared names, columns and units. Everyone imports from here; nobody renames them."""

# Climate table: 8,760 rows, one per hour of a typical year
CLIMATE_COLUMNS = [
    "hour_of_year",  # int 0..8759
    "month",         # int 1..12
    "temp_c",        # float, air temperature, °C
    "rh_pct",        # float, relative humidity, 0..100
    "ghi_wh_m2",     # float, solar energy that hour, Wh/m²
    "wind_ms",       # float, wind speed at 2 m, m/s
]

HOURS_PER_YEAR = 8760

# The four setups, always these exact strings
SETUPS = ["open_field", "shade_net", "wet_pad", "chiller"]

# Crop calendar statuses
STATUS = ["good", "risky", "impossible"]

# Coverage threshold for a setup to be acceptable
MIN_COVERAGE_PCT = 90.0

# Ranking priorities accepted by optimizer.plan()
PRIORITIES = ["profit", "payback", "water"]

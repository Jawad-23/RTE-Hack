"""Run real public-data checks explicitly; ordinary tests remain offline."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner import climate, dust, optimizer  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--five-sites", action="store_true")
    args = parser.parse_args()
    sites = [("Al Khor", 25.69, 51.50), ("Al Karaana", 25.01, 51.05)]
    if args.five_sites:
        sites += [("Doha", 25.29, 51.53), ("Dukhan", 25.42, 50.78), ("Mesaieed", 24.99, 51.55)]
    report = {"checked_utc": datetime.now(timezone.utc).isoformat(),
              "note": "Real NASA weather; equipment, crop and financial assumptions are estimates. No model API called.",
              "sites": []}
    for name, lat, lon in sites:
        result = optimizer.plan(lat, lon, 500, 250000, "profit")
        report["sites"].append({"name": name, "inputs": result["inputs"], "source": result["sources"][0],
                                "options": len(result["options"]), "recommended": result["recommended"],
                                "reason": result["reason"]})
        print(name, len(result["options"]), "options", flush=True)
    report["recent_dust"] = dust.recent_exposure(25.01, 51.05)
    target = Path(__file__).resolve().parents[1] / "docs" / "validation" / "live-data.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    if any(site["options"] != 56 for site in report["sites"]):
        raise SystemExit("One or more live weather checks failed; see report")
    print("Live weather checks passed; report:", target)


if __name__ == "__main__":
    main()

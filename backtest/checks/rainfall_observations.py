"""Write the rainfall attester rows for the frozen rule.

The decision is one catchment sum. It is copied onto each labeled zone so the
scorer can join it. Radar rows are not written here.
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "labels.csv"
RAINFALL = ROOT / "checks" / "chirps_daily_means.csv"
OUT = ROOT / "observations.csv"
EVENT_END = date(2024, 5, 6)
WINDOW_DAYS = 3
THRESHOLD_MM = 40.0


def catchment_mm(path: Path) -> float:
    by_day: dict[date, float] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            day = date.fromisoformat(row["date"])
            nandi = float(row["nandi_tinderet"])
            kericho = float(row["kericho_mau"])
            by_day[day] = (nandi + kericho) / 2
    total = 0.0
    for offset in range(WINDOW_DAYS):
        total += by_day[EVENT_END - timedelta(days=offset)]
    return total


def main() -> None:
    total = catchment_mm(RAINFALL)
    decision = "yes" if total >= THRESHOLD_MM else "no"
    reason = "threshold_met" if decision == "yes" else "below_threshold"
    with LABELS.open(newline="", encoding="utf-8") as handle:
        zones = list(csv.DictReader(handle))
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["zone_id", "event_start", "event_end", "source", "decision", "reason"],
        )
        writer.writeheader()
        for zone in zones:
            writer.writerow(
                {
                    "zone_id": zone["zone_id"],
                    "event_start": zone["event_start"],
                    "event_end": zone["event_end"],
                    "source": "rainfall",
                    "decision": decision,
                    "reason": reason,
                }
            )
    print(f"{total:.1f} mm -> {decision} ({reason}) on {len(zones)} zones")


if __name__ == "__main__":
    main()

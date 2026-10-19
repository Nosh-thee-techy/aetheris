"""Radar attester for one Sentinel-1 pass.

The fraction rule is the frozen prior in radar_fraction.py. This job only
chooses the orbit-130 RTC scene and signs when that fraction clears 0.05.
A missing pass or a missing outline does not sign.
"""

from __future__ import annotations

import csv
import json
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from backtest.pipeline.rule import ROOT

FRACTIONS = ROOT / "backtest" / "checks" / "radar_fractions.csv"
ZONES = ROOT / "backtest" / "checks" / "zones.json"
LABELS = ROOT / "backtest" / "labels.csv"
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
# The orbit the scene check kept. Orbit 28 does not cover the basin.
RELATIVE_ORBIT = 130
BASIN_BBOX = [34.75, -0.40, 35.55, 0.30]
PUBLISHED_SCENE = "2024-05-06"


def radar_action(decision: str, reason: str) -> str:
    if decision == "yes" and reason == "threshold_met":
        return "sign"
    return "silence"


def load_fractions(path: Path = FRACTIONS) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def labeled_zones(path: Path = LABELS) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row["zone_id"] for row in csv.DictReader(handle)]


def select_scene(features: list[dict]) -> dict | None:
    matches = []
    for feature in features:
        props = feature.get("properties") or {}
        orbit = props.get("sat:relative_orbit")
        if orbit != RELATIVE_ORBIT and str(orbit) != str(RELATIVE_ORBIT):
            continue
        href = (feature.get("assets") or {}).get("vv", {}).get("href")
        if not href:
            continue
        matches.append(feature)
    if not matches:
        return None
    ascending = [
        feature
        for feature in matches
        if (feature.get("properties") or {}).get("sat:orbit_state") == "ascending"
    ]
    return (ascending or matches)[0]


def scene_href(feature: dict) -> str:
    return feature["assets"]["vv"]["href"]


def search_scenes(day: date) -> list[dict]:
    start = f"{day.isoformat()}T00:00:00Z"
    end = f"{(day + timedelta(days=1)).isoformat()}T00:00:00Z"
    body = {
        "collections": ["sentinel-1-rtc"],
        "datetime": f"{start}/{end}",
        "bbox": BASIN_BBOX,
        "limit": 20,
    }
    request = urllib.request.Request(
        STAC,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "aetheris-build/1.0"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = json.loads(response.read().decode())
    return payload.get("features", [])


def actions_from_fractions(rows: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
    actions = []
    for row in rows if rows is not None else load_fractions():
        actions.append(
            {
                "zone_id": row["zone_id"],
                "action": radar_action(row["decision"], row["reason"]),
                "decision": row["decision"],
                "reason": row["reason"],
                "flooded_fraction": row.get("flooded_fraction", ""),
            }
        )
    return actions


def measure_scene(href: str, zone_ids: list[str] | None = None) -> list[dict]:
    """Windowed RTC read for a scene that is not the published 6 May pass."""
    from backtest.checks.radar_fraction import fraction_for, sign

    import rasterio

    zones = json.loads(ZONES.read_text(encoding="utf-8"))
    results = []
    with rasterio.open(sign(href)) as src:
        for zone_id in zone_ids or labeled_zones():
            box = zones.get(zone_id)
            if box is None:
                results.append(
                    {
                        "zone_id": zone_id,
                        "decision": "abstain",
                        "reason": "no_geometry",
                        "flooded_fraction": "",
                    }
                )
                continue
            measured = fraction_for(src, box)
            measured["zone_id"] = zone_id
            results.append(measured)
    return results

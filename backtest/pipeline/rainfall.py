"""CHIRPS catchment decision for the frozen rainfall rule.

IMERG is not connected. The checked product is CHIRPS 2.0, already used for
the lag check. Satellite rainfall products overestimate light rain and
underestimate heavy rain, so a millimetre total here is not a gauge total.

The scored 6 May 2024 total stays the published check. A later scene reads
UCSB-CHG/CHIRPS/DAILY on Earth Engine and averages the two headwater boxes.
The lag is the rule file's lag_days. This module does not download a CHIRPS GeoTIFF.
"""

from __future__ import annotations

import csv
import os
from datetime import date, timedelta
from pathlib import Path

from backtest.pipeline.rule import ROOT, load_rule

PUBLISHED = ROOT / "backtest" / "checks" / "chirps_daily_means.csv"
COLLECTION = "UCSB-CHG/CHIRPS/DAILY"
# CHIRPS is 0.05 degree. Earth Engine's scale is metres.
CHIRPS_SCALE_M = 5566


def window_dates(scene_date: date, window_days: int, lag_days: int) -> list[date]:
    if window_days < 1:
        raise ValueError("window_days must cover at least one day")
    if lag_days < 0:
        raise ValueError("lag_days cannot be negative")
    last = scene_date - timedelta(days=lag_days)
    return [last - timedelta(days=offset) for offset in range(window_days - 1, -1, -1)]


def catchment_mm(daily: dict[date, tuple[float, float]], days: list[date]) -> float:
    """Unweighted mean of the two headwater boxes, summed over the window."""
    total = 0.0
    for day in days:
        try:
            nandi, kericho = daily[day]
        except KeyError as error:
            raise KeyError(f"no CHIRPS mean for {day.isoformat()}") from error
        total += (nandi + kericho) / 2
    return total


def rainfall_action(total_mm: float, threshold_mm: float) -> str:
    if total_mm >= threshold_mm:
        return "sign"
    return "silence"


def published_daily(path: Path = PUBLISHED) -> dict[date, tuple[float, float]]:
    found: dict[date, tuple[float, float]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            found[date.fromisoformat(row["date"])] = (
                float(row["nandi_tinderet"]),
                float(row["kericho_mau"]),
            )
    return found


def published_total(scene_date: date = date(2024, 5, 6)) -> float:
    rule = load_rule()
    days = window_dates(scene_date, int(rule["rainfall"]["window_days"]), int(rule["rainfall"]["lag_days"]))
    return catchment_mm(published_daily(), days)


def fetch_gee(scene_date: date, project: str | None = None) -> float:
    """Mean the frozen headwater boxes on Earth Engine for this scene date."""
    rule = load_rule()
    rainfall = rule["rainfall"]
    days = window_dates(scene_date, int(rainfall["window_days"]), int(rainfall["lag_days"]))
    project_id = project or os.environ.get("EE_PROJECT", "")
    if not project_id:
        raise RuntimeError(
            "Set EE_PROJECT to an Earth Engine project. "
            "CHIRPS is read there. This job does not download CHIRPS files."
        )
    try:
        import ee
    except ImportError as error:
        raise RuntimeError(
            "Install earthengine-api and run earthengine authenticate. "
            "CHIRPS is read on Earth Engine, not from an Africa-wide file."
        ) from error
    ee.Initialize(project=project_id)
    boxes = {
        "nandi_tinderet": rainfall["nandi_tinderet"],
        "kericho_mau": rainfall["kericho_mau"],
    }
    daily = _gee_daily(ee, days[0], days[-1], boxes)
    return catchment_mm(daily, days)


def _gee_daily(ee, first: date, last: date, boxes: dict) -> dict[date, tuple[float, float]]:
    end_exclusive = (last + timedelta(days=1)).isoformat()
    images = (
        ee.ImageCollection(COLLECTION)
        .filterDate(first.isoformat(), end_exclusive)
        .select("precipitation")
    )
    geometries = {
        name: ee.Geometry.Rectangle(
            [box["west"], box["south"], box["east"], box["north"]],
            proj="EPSG:4326",
            geodesic=False,
        )
        for name, box in boxes.items()
    }

    def stamp(image):
        values = {
            "day": image.date().format("YYYY-MM-dd"),
        }
        for name, geometry in geometries.items():
            reduced = image.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=CHIRPS_SCALE_M,
                maxPixels=1_000_000,
            )
            values[name] = reduced.get("precipitation")
        return image.set(values)

    payload = images.map(stamp).getInfo()
    found: dict[date, tuple[float, float]] = {}
    for feature in payload.get("features", []):
        props = feature.get("properties", {})
        if props.get("day") is None:
            continue
        nandi = props.get("nandi_tinderet")
        kericho = props.get("kericho_mau")
        if nandi is None or kericho is None:
            continue
        found[date.fromisoformat(props["day"])] = (float(nandi), float(kericho))
    return found

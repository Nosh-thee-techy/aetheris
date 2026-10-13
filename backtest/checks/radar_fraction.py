"""Flooded fraction on the 6 May 2024 Sentinel-1 RTC scene.

The radar rule is the frozen prior: VV below -16 dB, on land, above a 0.05
fraction. Permanent water is JRC occurrence of at least 90 percent. That mask
cutoff was set before these fractions were read. Boxes are in zones.json.
A labeled place with no box is an abstention, not a missing satellite pass.
"""

from __future__ import annotations

import csv
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import from_bounds, transform as window_transform

os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
os.environ["GDAL_HTTP_TIMEOUT"] = "120"
os.environ["GDAL_HTTP_MERGE_CONSECUTIVE_RANGES"] = "YES"

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ZONES = HERE / "zones.json"
LABELS = ROOT / "labels.csv"
OBSERVATIONS = ROOT / "observations.csv"
FRACTIONS = HERE / "radar_fractions.csv"
SCENE_ID = "S1A_IW_GRDH_1SDV_20240506T155655_20240506T155720_053752_068803_rtc"
VV_HREF = (
    "https://sentinel1euwestrtc.blob.core.windows.net/sentinel1-grd-rtc/"
    "GRD/2024/5/6/IW/DV/"
    "S1A_IW_GRDH_1SDV_20240506T155655_20240506T155720_053752_068803_0742/"
    "measurement/iw-vv.rtc.tiff"
)
THRESHOLD_DB = -16.0
MIN_FRACTION = 0.05
PERMANENT_OCCURRENCE = 90
EVENT_START = "2024-05-04"
EVENT_END = "2024-05-06"
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
SIGN = "https://planetarycomputer.microsoft.com/api/sas/v1/sign?href="


def request_json(url: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode())


def sign(href: str) -> str:
    payload = request_json(SIGN + urllib.parse.quote(href, safe=""))
    return payload["href"]


def occurrence_href(west: float, south: float, east: float, north: float) -> str:
    payload = request_json(
        STAC,
        {
            "collections": ["jrc-gsw"],
            "bbox": [west, south, east, north],
            "limit": 8,
        },
    )
    center_lon = (west + east) / 2
    center_lat = (south + north) / 2
    for feature in payload.get("features", []):
        item_west, item_south, item_east, item_north = feature["bbox"]
        covers = (
            item_west <= center_lon <= item_east
            and item_south <= center_lat <= item_north
        )
        href = feature["assets"].get("occurrence", {}).get("href")
        if covers and href:
            return href
    raise RuntimeError("no JRC occurrence tile covers this box")


def read_window(src: rasterio.io.DatasetReader, west: float, south: float, east: float, north: float):
    left, bottom, right, top = transform_bounds(
        "EPSG:4326", src.crs, west, south, east, north, densify_pts=21
    )
    window = from_bounds(left, bottom, right, top, transform=src.transform).round_offsets().round_lengths()
    if window.width < 1 or window.height < 1:
        raise RuntimeError("box missed the scene grid")
    data = src.read(1, window=window, boundless=True, fill_value=0)
    transform = window_transform(window, src.transform)
    return data, transform


def permanent_mask(shape: tuple[int, int], transform, crs, west, south, east, north) -> np.ndarray:
    href = sign(occurrence_href(west, south, east, north))
    with rasterio.open(href) as src:
        occurrence, occurrence_transform = read_window(src, west, south, east, north)
        source_crs = src.crs
    aligned = np.zeros(shape, dtype="float32")
    reproject(
        occurrence,
        aligned,
        src_transform=occurrence_transform,
        src_crs=source_crs,
        dst_transform=transform,
        dst_crs=crs,
        resampling=Resampling.nearest,
    )
    return (aligned >= PERMANENT_OCCURRENCE) & (aligned <= 100)


def fraction_for(src: rasterio.io.DatasetReader, box: dict) -> dict:
    west, south, east, north = box["west"], box["south"], box["east"], box["north"]
    vv, transform = read_window(src, west, south, east, north)
    vv = vv.astype("float64")
    valid = np.isfinite(vv) & (vv > 0)
    if int(valid.sum()) < 100:
        return {"decision": "abstain", "reason": "no_scene", "flooded_fraction": "", "valid_pixels": int(valid.sum())}
    permanent = permanent_mask(vv.shape, transform, src.crs, west, south, east, north)
    land = valid & ~permanent
    decibels = 10 * np.log10(np.clip(vv, 1e-6, None))
    flooded = land & (decibels < THRESHOLD_DB)
    land_count = int(land.sum())
    if land_count == 0:
        return {"decision": "abstain", "reason": "no_data", "flooded_fraction": "", "valid_pixels": int(valid.sum())}
    share = float(flooded.sum()) / land_count
    return {
        "decision": "yes" if share >= MIN_FRACTION else "no",
        "reason": "threshold_met" if share >= MIN_FRACTION else "below_threshold",
        "flooded_fraction": round(share, 4),
        "valid_pixels": int(valid.sum()),
        "land_pixels": land_count,
        "flooded_pixels": int(flooded.sum()),
    }


def labeled_zones() -> list[str]:
    with LABELS.open(newline="", encoding="utf-8") as handle:
        return [row["zone_id"] for row in csv.DictReader(handle)]


def write_outputs(results: list[dict]) -> None:
    with FRACTIONS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "zone_id",
                "decision",
                "reason",
                "flooded_fraction",
                "valid_pixels",
                "land_pixels",
                "flooded_pixels",
                "scale",
            ],
        )
        writer.writeheader()
        writer.writerows(results)
    with OBSERVATIONS.open(newline="", encoding="utf-8") as handle:
        existing = [row for row in csv.DictReader(handle) if row["source"] != "radar"]
    with OBSERVATIONS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["zone_id", "event_start", "event_end", "source", "decision", "reason"],
        )
        writer.writeheader()
        writer.writerows(existing)
        for result in results:
            writer.writerow(
                {
                    "zone_id": result["zone_id"],
                    "event_start": EVENT_START,
                    "event_end": EVENT_END,
                    "source": "radar",
                    "decision": result["decision"],
                    "reason": result["reason"],
                }
            )


def main() -> None:
    zones = json.loads(ZONES.read_text(encoding="utf-8"))
    signed_vv = sign(VV_HREF)
    results = []
    with rasterio.open(signed_vv) as src:
        for zone_id in labeled_zones():
            box = zones.get(zone_id)
            if box is None:
                results.append(
                    {
                        "zone_id": zone_id,
                        "decision": "abstain",
                        "reason": "no_geometry",
                        "flooded_fraction": "",
                        "valid_pixels": "",
                        "land_pixels": "",
                        "flooded_pixels": "",
                        "scale": "no outline that matches the named place",
                    }
                )
                print(zone_id, "abstain no_geometry", flush=True)
                continue
            measured = fraction_for(src, box)
            measured["zone_id"] = zone_id
            measured["scale"] = box["scale"]
            measured.setdefault("land_pixels", "")
            measured.setdefault("flooded_pixels", "")
            results.append(measured)
            print(zone_id, measured["decision"], measured["flooded_fraction"], flush=True)
    write_outputs(results)


if __name__ == "__main__":
    main()

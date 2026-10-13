"""Save the report scene's VV asset href."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

BODY = {
    "collections": ["sentinel-1-rtc"],
    "ids": ["S1A_IW_GRDH_1SDV_20240506T155655_20240506T155720_053752_068803_rtc"],
    "limit": 1,
}
OUT = Path(__file__).with_name("scene_vv.json")


def main() -> None:
    request = urllib.request.Request(
        "https://planetarycomputer.microsoft.com/api/stac/v1/search",
        data=json.dumps(BODY).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = json.loads(response.read().decode())
    feature = payload["features"][0]
    asset = feature["assets"]["vv"]
    water_request = urllib.request.Request(
        "https://planetarycomputer.microsoft.com/api/stac/v1/search",
        data=json.dumps(
            {
                "collections": ["jrc-gsw"],
                "bbox": [34.7, -0.35, 35.15, 0.0],
                "limit": 5,
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(water_request, timeout=90) as response:
        water = json.loads(response.read().decode())
    record = {
        "scene_id": feature["id"],
        "vv_href": asset["href"],
        "vv_type": asset.get("type"),
        "water_items": [
            {
                "id": item["id"],
                "assets": sorted(item["assets"]),
            }
            for item in water.get("features", [])
        ],
    }
    OUT.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(record["scene_id"])
    print(record["vv_href"][:120])
    print("water", [item["id"] for item in record["water_items"]])


if __name__ == "__main__":
    main()

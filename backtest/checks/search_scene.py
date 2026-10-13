"""Find the 6 May 2024 Sentinel-1 RTC item that covers the Kano plain."""

from __future__ import annotations

import json
import urllib.request

BODY = {
    "collections": ["sentinel-1-rtc"],
    "datetime": "2024-05-06T15:50:00Z/2024-05-06T16:10:00Z",
    "bbox": [34.6, -0.45, 35.4, 0.2],
    "limit": 20,
}


def main() -> None:
    request = urllib.request.Request(
        "https://planetarycomputer.microsoft.com/api/stac/v1/search",
        data=json.dumps(BODY).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = json.loads(response.read().decode())
    features = payload.get("features", [])
    print("n", len(features))
    for feature in features:
        props = feature["properties"]
        assets = feature["assets"]
        print(
            feature["id"],
            props.get("datetime"),
            props.get("sat:orbit_state"),
            props.get("sat:relative_orbit"),
            "vv" in assets,
            assets.get("vv", {}).get("href", "")[:80],
        )


if __name__ == "__main__":
    main()

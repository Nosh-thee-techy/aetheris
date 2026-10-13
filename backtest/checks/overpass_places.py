"""Search OpenStreetMap for the three places the geocoders mismatched."""

from __future__ import annotations

import json
import urllib.request

QUERY = """
[out:json][timeout:40];
(
  node["name"~"Nyamasao",i]( -0.6,34.5,0.2,35.4);
  node["name"~"Ombaka",i]( -0.6,34.5,0.2,35.4);
  way["name"~"Ombaka",i]( -0.6,34.5,0.2,35.4);
  relation["name"~"Kadibo",i]( -0.6,34.5,0.2,35.4);
);
out tags center;
"""


ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)


def main() -> None:
    last_error: Exception | None = None
    payload = None
    for endpoint in ENDPOINTS:
        request = urllib.request.Request(
            endpoint,
            data=QUERY.encode(),
            headers={"User-Agent": "aetheris-build/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.loads(response.read().decode())
            break
        except Exception as error:
            last_error = error
            print(endpoint, error, flush=True)
    if payload is None:
        raise SystemExit(last_error)
    elements = payload.get("elements", [])
    print(f"elements {len(elements)}")
    for element in elements:
        tags = element.get("tags", {})
        center = element.get("center") or {}
        lat = element.get("lat", center.get("lat"))
        lon = element.get("lon", center.get("lon"))
        print(element["type"], tags.get("name"), tags.get("place"), lat, lon, tags.get("boundary"))


if __name__ == "__main__":
    main()

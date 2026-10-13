"""Find places Nominatim missed, using the Photon geocoder."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

QUERIES = [
    "Nyamasao Kenya",
    "Ombaka dispensary Nyando",
    "Kakola Ombaka",
    "Kobura village Ahero",
    "Kadibo subcounty Kisumu",
]


def one(query: str) -> list[dict]:
    url = "https://photon.komoot.io/api/?" + urllib.parse.urlencode({"q": query, "limit": 3})
    request = urllib.request.Request(url, headers={"User-Agent": "aetheris-build/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode())
    hits = []
    for feature in payload.get("features", []):
        props = feature.get("properties", {})
        lon, lat = feature["geometry"]["coordinates"]
        hits.append(
            {
                "query": query,
                "name": props.get("name"),
                "state": props.get("state"),
                "county": props.get("county"),
                "lat": lat,
                "lon": lon,
                "type": props.get("osm_value"),
            }
        )
    return hits


if __name__ == "__main__":
    found = []
    for query in QUERIES:
        found.extend(one(query))
    print(json.dumps(found, indent=2))

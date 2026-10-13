"""Second-pass place lookup for names the first query missed or mismatched."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

QUERIES = [
    "Kakola Ombaka, Nyando, Kenya",
    "Ombaka, Nyando, Kisumu, Kenya",
    "Nyamasao, Kisumu, Kenya",
    "Nyamasao dispensary, Kenya",
    "Kobura village, Nyando, Kenya",
    "Kadibo Sub-County, Kisumu, Kenya",
    "Kadibo, Kisumu County, Kenya",
]


def one(query: str) -> list[dict]:
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": query, "format": "json", "limit": 2}
    )
    request = urllib.request.Request(url, headers={"User-Agent": "aetheris-build/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        hits = json.loads(response.read().decode())
    return [
        {
            "query": query,
            "name": hit.get("display_name"),
            "lat": float(hit["lat"]),
            "lon": float(hit["lon"]),
            "type": hit.get("type"),
            "bbox": [float(value) for value in hit.get("boundingbox", [])],
        }
        for hit in hits
    ]


if __name__ == "__main__":
    found = []
    for query in QUERIES:
        found.extend(one(query))
        time.sleep(1.1)
    print(json.dumps(found, indent=2))

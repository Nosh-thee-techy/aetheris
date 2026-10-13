"""Look up the named flood places. Prints JSON. Not a boundary survey."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

QUERIES = {
    "ahero": "Ahero, Kisumu, Kenya",
    "kabonyo-kanyagwal": "Kabonyo, Nyando, Kenya",
    "kakola-ombaka": "Kakola, Nyando, Kenya",
    "nyamasao": "Nyamasao, Nyando, Kenya",
    "ombeyi": "Ombeyi, Muhoroni, Kenya",
    "kobura": "Kobura, Nyando, Kenya",
    "kadibo": "Kadibo, Kisumu, Kenya",
}


def one(query: str) -> dict:
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": query, "format": "json", "limit": 3}
    )
    request = urllib.request.Request(url, headers={"User-Agent": "aetheris-build/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        hits = json.loads(response.read().decode())
    return [
        {
            "name": hit.get("display_name"),
            "lat": float(hit["lat"]),
            "lon": float(hit["lon"]),
            "type": hit.get("type"),
            "class": hit.get("class"),
            "bbox": [float(value) for value in hit.get("boundingbox", [])],
        }
        for hit in hits
    ]


if __name__ == "__main__":
    found = {}
    for zone, query in QUERIES.items():
        found[zone] = one(query)
        time.sleep(1.1)
    print(json.dumps(found, indent=2))

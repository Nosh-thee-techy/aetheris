"""JSON for the data-producer desk and the local session.

Reads the same repository files the pages are built from. It does not invent
radar yes/no, rainfall totals, or chain state. The session is a labelled
demo gate: pick a desk. There is no password and no machine learning.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ROLES = {
    "icpac": {
        "label": "ICPAC",
        "org": "IGAD Climate Prediction and Applications Centre",
        "home": "/desk/data",
        "desk": "data",
    },
    "kenya-met": {
        "label": "Kenya Met",
        "org": "Kenya Meteorological Department",
        "home": "/desk/data",
        "desk": "data",
    },
    "insurer": {
        "label": "Insurer",
        "org": "Trigger analyst",
        "home": "/desk/insurer",
        "desk": "insurer",
    },
    "reinsurer": {
        "label": "Reinsurer",
        "org": "Event loss",
        "home": "/desk/reinsurer",
        "desk": "reinsurer",
    },
    "responder": {
        "label": "Responder",
        "org": "Second signal",
        "home": "/desk/responder",
        "desk": "responder",
    },
    "research": {
        "label": "Research",
        "org": "Open method",
        "home": "/desk/research",
        "desk": "research",
    },
    "farmer": {
        "label": "Farmer view",
        "org": "Plain language",
        "home": "/desk/farmer",
        "desk": "farmer",
    },
    "data": {
        "label": "Data desk",
        "org": "ICPAC / Kenya Met",
        "home": "/desk/data",
        "desk": "data",
    },
}

SESSIONS: dict[str, dict] = {}
PUBLIC_KEYS = ("role", "label", "org", "home", "desk", "name")


def public_session(who: dict) -> dict:
    shown = {key: who[key] for key in PUBLIC_KEYS if key in who}
    shown["role_label"] = who.get("label")
    return shown


def start_session(role: str, name: str = "") -> dict:
    if role not in ROLES:
        raise ValueError("unknown desk")
    token = secrets.token_hex(16)
    who = {
        "token": token,
        "role": role,
        "name": (name or "").strip()[:80],
        **ROLES[role],
    }
    SESSIONS[token] = who
    return who


def get_session(token: str | None) -> dict | None:
    if not token:
        return None
    return SESSIONS.get(token)


def end_session(token: str | None) -> None:
    if token:
        SESSIONS.pop(token, None)


def desk() -> dict:
    """One payload the data dashboard fetches from /api/desk."""
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    import json

    from backtest.pipeline import damage as vuln
    from backtest.pipeline.rainfall import published_total
    from backtest.pipeline.rule import load_rule, rule_id, thresholds_hash
    from web import build

    places = build.load_places()
    rule = load_rule()
    rain_mm = published_total()
    n = len(places)
    radar_yes = sum(1 for p in places if p["decision"] == "yes")
    radar_no = sum(1 for p in places if p["decision"] == "no")
    radar_off = sum(1 for p in places if p["decision"] == "abstain")
    rain_yes = sum(1 for p in places if p["rain"] == "yes")
    zones = json.loads((ROOT / "backtest" / "checks" / "zones.json").read_text(encoding="utf-8"))
    loss = vuln.totals()

    rows = []
    miss = []
    for p in places:
        modeled = p["decision"] == "yes" and p["rain"] == "yes"
        loss_row = _place_loss(p["slug"])
        box = p["fraction"] is not None
        if not box:
            miss.append({"slug": p["slug"], "name": p["name"]})
        marker, outcome, why = build.verdict(p)
        rows.append(
            {
                "slug": p["slug"],
                "name": p["name"],
                "scale": p["scale"],
                "radar": p["decision"],
                "rainfall": p["rain"],
                "rain": p["rain"],
                "both": "yes" if modeled else "no",
                "pixels": p["land"],
                "box": box,
                "zone": _zone_box(p["slug"], zones),
                "fraction": p["fraction"],
                "land_pixels": p["land"],
                "flooded_pixels": p["flooded"],
                "removed": p["removed"],
                "has_outline": box,
                "page": f"/claim/{p['slug']}",
                "modeled": modeled,
                "marker": marker,
                "outcome": outcome,
                "why": why,
                "claim_id": build.zone_claim_id(p["slug"]),
                "zone_id": build.hexed(build.zone_id(p["slug"])),
                "snapshot": build.snapshot_text(p["slug"], _raw_deployment()),
                "label_note": p["label_note"],
                "label_url": p["label_url"],
                "label_source": p["label_source"],
                "box_note": p["box_note"],
                "loss": loss_row,
                **loss_row,
            }
        )

    return {
        "week": build.WEEK_TEXT,
        "note": "Counts from the repository files. Not an accuracy figure.",
        "rainfall": {
            "product": "CHIRPS 2.0 daily",
            "mm": round(rain_mm, 1),
            "line_mm": float(rule["rainfall"]["threshold_mm"]),
            "signed": rain_yes,
            "places": n,
            "scope": "One upstream catchment, applied to every place",
            "catchment_id": rule["rainfall"]["catchment_id"],
            "window_days": rule["rainfall"]["window_days"],
            "lag_days": rule["rainfall"]["lag_days"],
        },
        "radar": {
            "product": "Sentinel-1 RTC",
            "line": float(rule["radar"]["min_flooded_fraction"]),
            "threshold_db": rule["radar"]["threshold_db"],
            "assessed": radar_yes + radar_no,
            "signed": radar_yes,
            "below": radar_no,
            "no_geometry": radar_off,
            "places": n,
        },
        "rule": {
            "id": rule["rule_id"],
            "name": rule["rule_id"],
            "frozen_on": str(rule["frozen_on"]),
            "rule_id": "0x" + rule_id().hex(),
            "thresholds_hash": "0x" + thresholds_hash().hex(),
            "week_id": build.hexed(build.event_week(build.WEEK)),
            "radar": "VV < −16 dB, fraction ≥ 0.05",
            "rain": "CHIRPS ≥ 40 mm / 3 days",
        },
        "counts": build.load_counts(),
        "chain": _chain_snapshot(),
        "zones": zones,
        "miss": miss,
        "loss": {
            "ground_up_label": vuln.kes(loss["ground_up_kes"]),
            "total_gu_label": vuln.kes(loss["ground_up_kes"]),
            "tiv_label": vuln.kes(loss["tiv_kes"]),
            "households": loss["households"],
            "places_with_tiv": loss["places_with_tiv"],
            "grant_eth": "0.001",
            "depth_m": vuln.WAIST_M,
            "note": "Indicative JRC/Huizinga at 0.9 m. Radar fraction is not depth. Not a stochastic cat model.",
        },
        "places": rows,
    }


def _zone_box(slug: str, zones: dict) -> dict | None:
    box = zones.get(slug)
    if not box:
        return None
    return {
        "min_lon": box["west"],
        "max_lon": box["east"],
        "min_lat": box["south"],
        "max_lat": box["north"],
        "west": box["west"],
        "east": box["east"],
        "south": box["south"],
        "north": box["north"],
        "scale": box.get("scale"),
        "source": box.get("source"),
    }


def _raw_deployment() -> dict | None:
    path = ROOT / "web" / "data" / "deployment.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _chain_snapshot() -> dict | None:
    raw = _raw_deployment()
    if not raw:
        return None
    return {
        "network": raw["network"],
        "chain_id": raw["chain_id"],
        "explorer": raw["explorer"],
        "snapshot_at": raw["snapshot_at"],
        "trigger": raw["trigger"],
        "escrow": raw["escrow"],
        "roles": raw["roles"],
        "rule_id": raw["rule_id"],
        "thresholds_hash": raw["thresholds_hash"],
        "pool_balance_eth": raw["pool_balance_eth"],
        "beneficiaries": raw["beneficiaries"],
        "claims": raw["claims"],
        "note": "Snapshot taken at deploy. Not a later live read. The page does not invent chain state.",
    }


def _place_loss(slug: str) -> dict:
    from backtest.pipeline import damage as vuln

    row = vuln.row_for(slug)
    return {
        "depth_m": row["depth_m"],
        "depth_provenance": row["depth_provenance"],
        "class_label": row["class_label"],
        "curve_label": row["curve_label"],
        "households": row["households"],
        "households_note": row["households_note"],
        "tiv_label": vuln.kes(row["tiv_kes"]),
        "damage_ratio": row["damage_ratio"],
        "ground_up_label": vuln.kes(row["ground_up_kes"]),
    }

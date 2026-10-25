"""Indicative vulnerability layer for the one Nyando week.

This is not a measured flood-depth map. The only depth words we have for
this event are “waist-high” at Ahero Police Station residences (Kenya News
Agency, 5 May 2024). We convert that to 0.9 m and, as an assumption, apply
the same depth to the other named places. Radar open-water fraction is not
used as depth.

Curves are the JRC/Huizinga points as transcribed in the Nairobi Urban Flood
CAT spec (8 Oct 2026). They are labelled adapted: we did not re-read the
JRC spreadsheet. TIV is households named in the news times a UNHCR Kenya
standard-shelter grant, labelled adapted: that grant is a Kakuma/Kalobeyei
figure, not a Nyando rebuild survey.

Huizinga, J., De Moel, H. and Szewczyk, W. (2017). Global flood depth-damage
functions. JRC. https://doi.org/10.2760/16510
"""

from __future__ import annotations

from typing import Literal

Provenance = Literal["researched", "adapted", "assumption"]

# JRC/Huizinga points as transcribed in the Nairobi CAT spec. Verify against
# the JRC spreadsheet before treating them as canonical.
DEPTH_POINTS_M = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0)
CURVES: dict[str, tuple[float, ...]] = {
    "africa_residential": (0.0, 0.22, 0.38, 0.53, 0.64, 0.82, 0.90, 0.96, 1.0),
    "global_commercial": (0.0, 0.32, 0.51, 0.63, 0.74, 0.86, 0.93, 0.98, 1.0),
    "weak_structure": (0.0, 0.49, 0.91, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
}

# Adult standing waist, used only to turn “waist-high” into metres.
WAIST_M = 0.9
WAIST_SOURCE = {
    "words": "waist-high in houses used by officers at Ahero Police Station",
    "who": "Nyando Deputy County Commissioner Elijah Maranga",
    "outlet": "Kenya News Agency, 5 May 2024",
    "url": "https://www.kenyanews.go.ke/floods-ravage-kisumu-county-as-homes-businesses-submerged/",
}

# UNHCR Kenya cash-for-shelter, standard house, Kalobeyei. Not a Nyando survey.
UNIT_TIV_KES = 153_500
UNIT_TIV_SOURCE = {
    "what": "UNHCR Kenya standard shelter cash grant",
    "amount": "KES 153,500",
    "url": "https://help.unhcr.org/kenya/kakuma/cash-based-interventions-cbi/",
}

# Sensitivity around the waist conversion. Knee-deep is mentioned in a broader
# Kisumu KRCS quote; 1.5 m is the lowest step on the Nairobi spec depth ladder.
SENSITIVITY_M = (0.5, 0.9, 1.5)

# One row per named place. Household counts are taken only where a report
# printed a number. People-counts are not turned into households.
BOOK: dict[str, dict] = {
    "ahero": {
        "housing_class": "permanent_masonry",
        "curve": "africa_residential",
        "depth_m": WAIST_M,
        "depth_provenance": "adapted",
        "households": None,
        "households_note": None,
        "households_source": None,
    },
    "kabonyo-kanyagwal": {
        "housing_class": "semi_permanent",
        "curve": "semi_permanent",
        "depth_m": WAIST_M,
        "depth_provenance": "assumption",
        "households": 700,
        "households_note": "more than 700 households",
        "households_source": "Daily Nation",
    },
    "kakola-ombaka": {
        "housing_class": "semi_permanent",
        "curve": "semi_permanent",
        "depth_m": WAIST_M,
        "depth_provenance": "assumption",
        "households": 300,
        "households_note": "more than 300 households",
        "households_source": "Daily Nation",
    },
    "nyamasao": {
        "housing_class": "semi_permanent",
        "curve": "semi_permanent",
        "depth_m": WAIST_M,
        "depth_provenance": "assumption",
        "households": None,
        "households_note": None,
        "households_source": None,
    },
    "ombeyi": {
        "housing_class": "semi_permanent",
        "curve": "semi_permanent",
        "depth_m": WAIST_M,
        "depth_provenance": "assumption",
        "households": None,
        "households_note": "over 600 people marooned; not a household count",
        "households_source": "Kenya News Agency",
    },
    "kobura": {
        "housing_class": "semi_permanent",
        "curve": "semi_permanent",
        "depth_m": WAIST_M,
        "depth_provenance": "assumption",
        "households": None,
        "households_note": None,
        "households_source": None,
    },
    "kadibo": {
        "housing_class": "semi_permanent",
        "curve": "semi_permanent",
        "depth_m": WAIST_M,
        "depth_provenance": "assumption",
        "households": 20,
        "households_note": "20 households",
        "households_source": "The Star",
    },
}

CLASS_LABEL = {
    "permanent_masonry": "Permanent masonry",
    "semi_permanent": "Semi-permanent",
}
CURVE_LABEL = {
    "africa_residential": "JRC Africa residential",
    "semi_permanent": "Blend of Africa residential and weak structure",
}


def damage_ratio(curve: str, depth_m: float) -> float:
    """Fractional damage at depth_m. Does not take a radar fraction."""
    if depth_m < 0:
        raise ValueError("depth cannot be negative")
    if curve == "semi_permanent":
        a = _lookup("africa_residential", depth_m)
        b = _lookup("weak_structure", depth_m)
        return (a + b) / 2
    return _lookup(curve, depth_m)


def _lookup(name: str, depth_m: float) -> float:
    ys = CURVES[name]
    xs = DEPTH_POINTS_M
    if depth_m <= xs[0]:
        return ys[0]
    if depth_m >= xs[-1]:
        return ys[-1]
    for i in range(len(xs) - 1):
        if xs[i] <= depth_m <= xs[i + 1]:
            span = xs[i + 1] - xs[i]
            t = (depth_m - xs[i]) / span
            return ys[i] + t * (ys[i + 1] - ys[i])
    raise AssertionError("depth fell between no pair of points")


def tiv_kes(households: int | None) -> int | None:
    if households is None:
        return None
    return households * UNIT_TIV_KES


def ground_up_kes(ratio: float, households: int | None) -> int | None:
    value = tiv_kes(households)
    if value is None:
        return None
    return round(ratio * value)


def row_for(slug: str) -> dict:
    spec = BOOK[slug]
    ratio = damage_ratio(spec["curve"], spec["depth_m"])
    households = spec["households"]
    return {
        "slug": slug,
        "housing_class": spec["housing_class"],
        "class_label": CLASS_LABEL[spec["housing_class"]],
        "curve": spec["curve"],
        "curve_label": CURVE_LABEL[spec["curve"]],
        "depth_m": spec["depth_m"],
        "depth_provenance": spec["depth_provenance"],
        "households": households,
        "households_note": spec["households_note"],
        "households_source": spec["households_source"],
        "tiv_kes": tiv_kes(households),
        "tiv_provenance": "adapted" if households is not None else None,
        "damage_ratio": ratio,
        "ground_up_kes": ground_up_kes(ratio, households),
        "sensitivity": {
            depth: {
                "damage_ratio": damage_ratio(spec["curve"], depth),
                "ground_up_kes": ground_up_kes(damage_ratio(spec["curve"], depth), households),
            }
            for depth in SENSITIVITY_M
        },
    }


def book() -> list[dict]:
    return [row_for(slug) for slug in BOOK]


def totals() -> dict:
    rows = book()
    valued = [r for r in rows if r["ground_up_kes"] is not None]
    return {
        "places_with_tiv": len(valued),
        "households": sum(r["households"] for r in valued),
        "tiv_kes": sum(r["tiv_kes"] for r in valued),
        "ground_up_kes": sum(r["ground_up_kes"] for r in valued),
        "sensitivity": {
            depth: {
                "ground_up_kes": sum(
                    r["sensitivity"][depth]["ground_up_kes"]
                    for r in valued
                    if r["sensitivity"][depth]["ground_up_kes"] is not None
                )
            }
            for depth in SENSITIVITY_M
        },
    }


def kes(amount: int | None) -> str:
    if amount is None:
        return "—"
    if amount >= 1_000_000:
        return f"KES {amount / 1_000_000:.1f} million"
    return f"KES {amount:,}"

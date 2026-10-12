"""Score radar-required flood triggers against a label log.

Unknown labels stay out of precision, recall, and basis risk. A missing
radar scene is a coverage gap, not a silent no. Disagreements are the rows
where the rainfall attester changes the decision.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

LABELS = {"flooded", "not_flooded", "unknown"}
DECISIONS = {"yes", "no", "abstain"}
SOURCES = {"radar", "rainfall"}
KEY = ("zone_id", "event_start", "event_end")

AGREEMENT_BUCKETS = (
    "both_yes",
    "radar_only",
    "rainfall_only",
    "both_no",
    "radar_abstain",
    "rainfall_abstain",
    "both_abstain",
)

MISS_BUCKETS = (
    "no_scene",
    "below_threshold",
    "uncorroborated",
    "rainfall_gap",
)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _key(row: dict[str, str]) -> tuple[str, str, str]:
    missing = [field for field in KEY if not row.get(field, "").strip()]
    if missing:
        raise ValueError(f"row is missing {', '.join(missing)}")
    return tuple(row[field].strip() for field in KEY)  # type: ignore[return-value]


def _label(row: dict[str, str]) -> str:
    value = row.get("label", "").strip() or "unknown"
    if value not in LABELS:
        raise ValueError(f"unknown label {value!r}")
    return value


def index_labels(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], str]:
    labels: dict[tuple[str, str, str], str] = {}
    for row in rows:
        key = _key(row)
        if key in labels:
            raise ValueError(f"duplicate label for {key}")
        labels[key] = _label(row)
    return labels


def index_observations(
    rows: list[dict[str, str]],
) -> dict[tuple[str, str, str], dict[str, dict[str, str]]]:
    observations: dict[tuple[str, str, str], dict[str, dict[str, str]]] = {}
    for row in rows:
        key = _key(row)
        source = row.get("source", "").strip()
        decision = row.get("decision", "").strip()
        if source not in SOURCES:
            raise ValueError(f"unknown source {source!r}")
        if decision not in DECISIONS:
            raise ValueError(f"unknown decision {decision!r}")
        slot = observations.setdefault(key, {})
        if source in slot:
            raise ValueError(f"duplicate {source} observation for {key}")
        slot[source] = {
            "decision": decision,
            "reason": row.get("reason", "").strip(),
        }
    return observations


def _decision(pair: dict[str, dict[str, str]], source: str) -> str:
    observed = pair.get(source)
    if observed is None:
        return "abstain"
    return observed["decision"]


def quorum(radar: str, rainfall: str) -> bool:
    """Radar must see open water, and rainfall must corroborate."""
    return radar == "yes" and rainfall == "yes"


def agreement_bucket(radar: str, rainfall: str) -> str:
    if radar == "abstain" and rainfall == "abstain":
        return "both_abstain"
    if radar == "abstain":
        return "radar_abstain"
    if rainfall == "abstain":
        return "rainfall_abstain"
    if radar == "yes" and rainfall == "yes":
        return "both_yes"
    if radar == "yes":
        return "radar_only"
    if rainfall == "yes":
        return "rainfall_only"
    return "both_no"


def miss_bucket(radar: str, rainfall: str) -> str:
    if radar == "abstain":
        return "no_scene"
    if radar == "no":
        return "below_threshold"
    if rainfall == "abstain":
        return "rainfall_gap"
    return "uncorroborated"


def score(
    labels: dict[tuple[str, str, str], str],
    observations: dict[tuple[str, str, str], dict[str, dict[str, str]]],
) -> dict:
    agreement = Counter({bucket: 0 for bucket in AGREEMENT_BUCKETS})
    misses = Counter({bucket: 0 for bucket in MISS_BUCKETS})
    counts = Counter(
        true_positive=0,
        false_trigger=0,
        miss=0,
        true_negative=0,
        unknown=0,
        fired_unknown=0,
    )

    keys = sorted(set(labels) | set(observations))
    for key in keys:
        label = labels.get(key, "unknown")
        pair = observations.get(key, {})
        radar = _decision(pair, "radar")
        rainfall = _decision(pair, "rainfall")
        fired = quorum(radar, rainfall)
        agreement[agreement_bucket(radar, rainfall)] += 1

        if label == "unknown":
            counts["unknown"] += 1
            if fired:
                counts["fired_unknown"] += 1
            continue

        if label == "flooded":
            if fired:
                counts["true_positive"] += 1
            else:
                counts["miss"] += 1
                misses[miss_bucket(radar, rainfall)] += 1
        elif fired:
            counts["false_trigger"] += 1
        else:
            counts["true_negative"] += 1

    decided = (
        agreement["both_yes"]
        + agreement["radar_only"]
        + agreement["rainfall_only"]
        + agreement["both_no"]
    )
    disagreements = agreement["radar_only"] + agreement["rainfall_only"]
    labeled_floods = counts["true_positive"] + counts["miss"]
    predicted_positive = counts["true_positive"] + counts["false_trigger"]

    return {
        "counts": dict(counts),
        "agreement": {bucket: agreement[bucket] for bucket in AGREEMENT_BUCKETS},
        "misses": {bucket: misses[bucket] for bucket in MISS_BUCKETS},
        "precision": _rate(counts["true_positive"], predicted_positive),
        "recall": _rate(counts["true_positive"], labeled_floods),
        "basis_risk": _rate(counts["miss"], labeled_floods),
        "disagreement_rate": _rate(disagreements, decided),
        "decided_pairs": decided,
        "disagreements": disagreements,
    }


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def format_report(result: dict) -> str:
    counts = result["counts"]
    lines = [
        "Aetheris backtest",
        f"true positives: {counts['true_positive']}",
        f"false triggers: {counts['false_trigger']}",
        f"misses: {counts['miss']}",
        f"true negatives: {counts['true_negative']}",
        f"unknown zone-weeks: {counts['unknown']}",
        f"fired on unknown: {counts['fired_unknown']}",
        f"precision: {_fmt(result['precision'])}",
        f"recall: {_fmt(result['recall'])}",
        f"basis risk: {_fmt(result['basis_risk'])}",
        f"disagreement rate: {_fmt(result['disagreement_rate'])}",
        "agreement: " + ", ".join(f"{k}={v}" for k, v in result["agreement"].items()),
        "misses: " + ", ".join(f"{k}={v}" for k, v in result["misses"].items()),
        "Open-water radar does not see flood under vegetation. That gap is not in the miss buckets.",
    ]
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def score_files(labels_path: Path, observations_path: Path) -> dict:
    return score(
        index_labels(load_csv(labels_path)),
        index_observations(load_csv(observations_path)),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the asymmetric flood rule.")
    parser.add_argument("--labels", type=Path, default=Path("backtest/labels.csv"))
    parser.add_argument("--observations", type=Path, default=Path("backtest/observations.csv"))
    args = parser.parse_args()
    print(format_report(score_files(args.labels, args.observations)))


if __name__ == "__main__":
    main()

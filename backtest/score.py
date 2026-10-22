"""Score radar-required flood triggers against a label log.

Unknown labels stay out of the flood and false-trigger counts. A missing
radar scene is a coverage gap, not a silent no. Disagreements are the rows
where the rainfall attester changes the decision. The printed report is
counts. It does not publish an accuracy percentage.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

# The log says flood / no_flood. Older rows said flooded / not_flooded.
# Both names are the same cell. Blank is unknown, never a dry label.
LABELS = {
    "flood": "flooded",
    "flooded": "flooded",
    "no_flood": "not_flooded",
    "not_flooded": "not_flooded",
    "unknown": "unknown",
    "": "unknown",
}
RULES = ("radar_only", "radar_plus_rainfall", "rainfall_only")
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
    "no_geometry",
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
    value = row.get("label", "").strip()
    try:
        return LABELS[value]
    except KeyError as error:
        raise ValueError(f"unknown label {value!r}") from error


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


def _reason(pair: dict[str, dict[str, str]], source: str) -> str:
    observed = pair.get(source)
    if observed is None:
        return "no_data"
    return observed["reason"]


def quorum(radar: str, rainfall: str) -> bool:
    """Radar must see open water, and rainfall must corroborate."""
    return _fired("radar_plus_rainfall", radar, rainfall)


def _fired(rule: str, radar: str, rainfall: str) -> bool:
    """Whether that rule would open a trigger. Abstain is not a yes."""
    if rule == "radar_only":
        return radar == "yes"
    if rule == "rainfall_only":
        return rainfall == "yes"
    if rule == "radar_plus_rainfall":
        return radar == "yes" and rainfall == "yes"
    raise ValueError(f"unknown rule {rule}")


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


def miss_bucket(radar: str, rainfall: str, radar_reason: str = "") -> str:
    if radar == "abstain":
        if radar_reason == "no_geometry":
            return "no_geometry"
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
                misses[miss_bucket(radar, rainfall, _reason(pair, "radar"))] += 1
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
        "rules": _rule_counts(labels, observations),
        "precision": _rate(counts["true_positive"], predicted_positive),
        "recall": _rate(counts["true_positive"], labeled_floods),
        "basis_risk": _rate(counts["miss"], labeled_floods),
        "disagreement_rate": _rate(disagreements, decided),
        "decided_pairs": decided,
        "disagreements": disagreements,
        "labeled_zone_weeks": labeled_floods + counts["true_negative"] + counts["false_trigger"],
        "flood_labels": labeled_floods,
    }


def _rule_counts(
    labels: dict[tuple[str, str, str], str],
    observations: dict[tuple[str, str, str], dict[str, dict[str, str]]],
) -> dict[str, dict[str, int]]:
    """Hits, misses, and false triggers for the three rules. Counts only."""
    compared = {rule: Counter(hits=0, misses=0, false_triggers=0, fired_unknown=0) for rule in RULES}
    keys = sorted(set(labels) | set(observations))
    for key in keys:
        label = labels.get(key, "unknown")
        pair = observations.get(key, {})
        radar = _decision(pair, "radar")
        rainfall = _decision(pair, "rainfall")
        for rule in RULES:
            fired = _fired(rule, radar, rainfall)
            bucket = compared[rule]
            if label == "unknown":
                if fired:
                    bucket["fired_unknown"] += 1
            elif label == "flooded":
                if fired:
                    bucket["hits"] += 1
                else:
                    bucket["misses"] += 1
            elif fired:
                bucket["false_triggers"] += 1
    return {rule: dict(bucket) for rule, bucket in compared.items()}


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def format_report(result: dict) -> str:
    """Counts and the agreement table. No accuracy percentage."""
    counts = result["counts"]
    misses = result["misses"]
    lines = [
        "Aetheris backtest (counts, indicative)",
        f"labeled zone-weeks: {result['labeled_zone_weeks']}",
        f"flood labels: {result['flood_labels']}",
        f"quorum hits: {counts['true_positive']}",
        f"false triggers: {counts['false_trigger']}",
        f"misses: {counts['miss']}",
        f"true negatives: {counts['true_negative']}",
        f"unknown zone-weeks: {counts['unknown']}",
        f"fired on unknown: {counts['fired_unknown']}",
        f"disagreements: {result['disagreements']} of {result['decided_pairs']} decided pairs",
        "agreement: " + ", ".join(f"{k}={v}" for k, v in result["agreement"].items()),
        "misses: " + ", ".join(f"{k}={v}" for k, v in misses.items()),
        f"misses because radar had no pass: {misses['no_scene']}",
        "rule comparison (hits / misses / false triggers on labeled cells):",
    ]
    for rule, bucket in result["rules"].items():
        lines.append(
            f"  {rule}: hits {bucket['hits']}, misses {bucket['misses']}, false triggers {bucket['false_triggers']}"
        )
    lines.append("Open-water radar does not see flood under vegetation. That gap is not in the miss buckets.")
    return "\n".join(lines)


def normalize_label_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Accept zone/week/flood rows and the older zone_id/event window rows."""
    if not rows or "week" not in rows[0]:
        return rows
    converted = []
    for row in rows:
        week = row.get("week", "").strip()
        start, separator, end = week.partition("/")
        if not separator or not start or not end:
            raise ValueError(f"week must be start/end, got {week!r}")
        converted.append(
            {
                "zone_id": row.get("zone", "").strip(),
                "event_start": start,
                "event_end": end,
                "label": row.get("label", ""),
            }
        )
    return converted


def write_results(result: dict, path: Path) -> None:
    """Write the count table. One row per rule, then the agreement buckets."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["table", "name", "hits", "misses", "false_triggers", "count"],
        )
        writer.writeheader()
        for rule, bucket in result["rules"].items():
            writer.writerow(
                {
                    "table": "rule",
                    "name": rule,
                    "hits": bucket["hits"],
                    "misses": bucket["misses"],
                    "false_triggers": bucket["false_triggers"],
                    "count": "",
                }
            )
        for name, count in result["agreement"].items():
            writer.writerow(
                {"table": "agreement", "name": name, "hits": "", "misses": "", "false_triggers": "", "count": count}
            )
        writer.writerow(
            {
                "table": "miss",
                "name": "no_scene",
                "hits": "",
                "misses": result["misses"]["no_scene"],
                "false_triggers": "",
                "count": result["misses"]["no_scene"],
            }
        )


def score_files(labels_path: Path, observations_path: Path) -> dict:
    return score(
        index_labels(normalize_label_rows(load_csv(labels_path))),
        index_observations(load_csv(observations_path)),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the asymmetric flood rule.")
    parser.add_argument("--labels", type=Path, default=Path("labels/label_log.csv"))
    parser.add_argument("--observations", type=Path, default=Path("backtest/observations.csv"))
    parser.add_argument("--results", type=Path, default=Path("backtest/results/counts.csv"))
    args = parser.parse_args()
    result = score_files(args.labels, args.observations)
    write_results(result, args.results)
    print(format_report(result))


if __name__ == "__main__":
    main()

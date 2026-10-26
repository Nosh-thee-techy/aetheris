"""Documented job for one scored week.

The website does not download rasters and does not live-score a GeoTIFF.
This module is the offline recipe: find the scene, write the radar CSV,
write the rainfall rows, then score. Default is to score the published
files that are already in the repository.

It does not invent gauges, does not invent a place outline, does not
tune config/rule.yaml, and does not call a language model.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from backtest.pipeline.rule import ROOT
from backtest.score import format_report, score_files, write_results

PUBLISHED_WEEK = "2024-05-04/2024-05-06"
LABELS = ROOT / "labels" / "label_log.csv"
OBSERVATIONS = ROOT / "backtest" / "observations.csv"
COUNTS = ROOT / "backtest" / "results" / "counts.csv"
GAUGES = ROOT / "backtest" / "checks" / "gauges.csv"

# Scene id is frozen in radar_fraction.py for the published week.
# A second week means pointing that script at a new scene, not this site.
STEPS = (
    (
        "1. Scene",
        "Find the orbit-130 Sentinel-1 RTC that covers the basin. "
        "Scripts: python backtest/checks/search_scene.py and "
        "python backtest/checks/fetch_scene_meta.py. "
        "The published week uses the 6 May 2024 scene already recorded.",
    ),
    (
        "2. Radar fractions",
        "python backtest/checks/radar_fraction.py  "
        "(needs network: Planetary Computer). "
        "Writes backtest/checks/radar_fractions.csv. "
        "A name without a box stays no_geometry. Do not invent an outline.",
    ),
    (
        "3. Rainfall",
        "python backtest/checks/sample_chirps.py then "
        "python backtest/checks/rainfall_observations.py. "
        "A later week needs Earth Engine. "
        "The published week uses backtest/checks/chirps_daily_means.csv (56.7 mm).",
    ),
    (
        "4. Score",
        "python -m backtest.week   (or python -m backtest.score). "
        "Reads the label log and observations. Writes counts. "
        "Leave config/rule.yaml unchanged. Do not tune on the week you score.",
    ),
    (
        "5. Site",
        "The website reads the CSVs. It does not re-score GeoTIFFs on load, "
        "does not run a RAG, and does not download a new scene for a visitor.",
    ),
)


def recipe() -> str:
    """How a new week is scored. Offline. Rule stays frozen."""
    lines = [
        "How a week is scored (offline job, not a page load)",
        f"Published week: {PUBLISHED_WEEK}",
        "Frozen rule: config/rule.yaml",
        "This is not a validation study. One week. Counts only.",
        "Radar is the reference for the check, not ground truth.",
        gauges_status(),
        "",
    ]
    for title, body in STEPS:
        lines.append(f"{title}")
        lines.append(f"  {body}")
        lines.append("")
    lines.append("A second week is allowed only if the rule file is unchanged.")
    lines.append("Do not stub TAHMO or Kenya Met stations. Add a real gauge file or say none.")
    return "\n".join(lines).rstrip() + "\n"


def gauges_status() -> str:
    if GAUGES.exists():
        return "Gauge file present: backtest/checks/gauges.csv. Use it as a third signer only after review."
    return (
        "No gauge file in this repository. "
        "Do not stub TAHMO or Kenya Met stations. Radar is the reference, not truth."
    )


def score_published(
    labels_path: Path = LABELS,
    observations_path: Path = OBSERVATIONS,
) -> dict:
    """Score the files already in git. Does not fetch a scene."""
    return score_files(labels_path, observations_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Documented week job: print the recipe and score the published files.",
    )
    parser.add_argument(
        "--recipe",
        action="store_true",
        help="Print the offline recipe only. Do not score.",
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=COUNTS,
        help="Where to write the count table when scoring.",
    )
    args = parser.parse_args()
    print(recipe(), end="")
    if args.recipe:
        return
    result = score_published()
    write_results(result, args.results)
    print()
    print(format_report(result))


if __name__ == "__main__":
    main()

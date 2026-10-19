"""What the two attesters would sign for the published 6 May 2024 scene."""

from __future__ import annotations

from datetime import date

from backtest.pipeline.ids import evidence_radar, evidence_rainfall, zone_id
from backtest.pipeline.radar import PUBLISHED_SCENE, actions_from_fractions
from backtest.pipeline.rainfall import published_total, rainfall_action, window_dates
from backtest.pipeline.rule import load_rule

# Item id of the RTC scene the fraction check measured.
PUBLISHED_ITEM = "S1A_IW_GRDH_1SDV_20240506T155655_20240506T155720_053752_068803_rtc"


def may_report() -> str:
    rule = load_rule()
    scene = date.fromisoformat(PUBLISHED_SCENE)
    days = window_dates(scene, int(rule["rainfall"]["window_days"]), int(rule["rainfall"]["lag_days"]))
    total = published_total(scene)
    rain = rainfall_action(total, float(rule["rainfall"]["threshold_mm"]))
    rain_evidence = evidence_rainfall(days[0], days[-1]).hex()
    radar_evidence = evidence_radar(PUBLISHED_ITEM).hex()
    lines = [
        f"scene {PUBLISHED_SCENE} item {PUBLISHED_ITEM}",
        f"rainfall {total:.1f} mm {rain} evidence {rain_evidence}",
    ]
    for row in actions_from_fractions():
        zone = zone_id(row["zone_id"]).hex()
        if row["action"] == "sign":
            lines.append(
                f"{row['zone_id']} radar sign fraction {row['flooded_fraction']} zone {zone} evidence {radar_evidence}"
            )
        else:
            lines.append(f"{row['zone_id']} radar silence {row['reason']} zone {zone}")
        lines.append(f"{row['zone_id']} rainfall {rain}")
    return "\n".join(lines)


def main() -> None:
    print(may_report())


if __name__ == "__main__":
    main()

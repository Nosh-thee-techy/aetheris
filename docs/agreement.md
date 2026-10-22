# Agreement table, 4–6 May 2024

One scene. Seven places a report named as flooded. No `no_flood` labels. The rule in `config/rule.yaml` was not changed after these fractions were read. The metric log is `labels/label_log.csv`.

The radar scene is the Sentinel-1A RTC on Planetary Computer, item `S1A_IW_GRDH_1SDV_20240506T155655_20240506T155720_053752_068803_rtc`, VV gamma0. Water is `10 * log10(VV) < -16` on pixels above zero. Permanent water is JRC Global Surface Water occurrence of at least 90 on tile `30E_0Nv1`, removed before the fraction. A zone is radar-yes when the flooded share of the remaining land pixels is at least 0.05. Rainfall is the same catchment decision on every row: 56.7 mm over the three days ending 6 May 2024, above the 40 mm prior, so rainfall is yes everywhere. The quorum is radar-yes and rainfall-yes. Here that means the quorum is the radar decision.

| Place | Flooded fraction | Radar | Rainfall | Quorum |
|---|---:|---|---|---|
| Ahero | 0.0066 | no, below threshold | yes | no |
| Kabonyo Kanyagwal | 0.0893 | yes | yes | yes |
| Kakola Ombaka | no outline | abstain, no geometry | yes | no |
| Nyamasao | no outline | abstain, no geometry | yes | no |
| Ombeyi | 0.0028 | no, below threshold | yes | no |
| Kobura | 0.0095 | no, below threshold | yes | no |
| Kadibo | no outline | abstain, no geometry | yes | no |

`python backtest/score.py` on `labels/label_log.csv` and `backtest/observations.csv`:

| Count | Value |
|---|---:|
| Labeled zone-weeks | 7 |
| Flood labels | 7 |
| Quorum hits | 1 |
| False triggers | 0 |
| Misses | 6 |
| True negatives | 0 |

Agreement buckets: `both_yes` 1, `rainfall_only` 3, `radar_abstain` 3. The other agreement buckets are 0. Disagreements are 3 of 4 decided pairs.

Miss buckets: `below_threshold` 3, `no_geometry` 3. `no_scene` is 0. The 6 May pass exists. The three abstentions are missing place outlines, not a missing satellite pass.

| Rule | Hits | Misses | False triggers |
|---|---:|---:|---:|
| Radar only | 1 | 6 | 0 |
| Radar plus rainfall | 1 | 6 | 0 |
| Rainfall only | 7 | 0 | 0 |

The same counts are in `backtest/results/counts.csv`.

## What these numbers can support

These are counts from one week. They are indicative. There is no dry label, so the zero false triggers do not test a payout on a dry place. The quorum hits 1 of 7 flood labels. The other 6 are misses.

Rainfall is yes on every row, so radar-only and radar-plus-rainfall have the same counts. Rainfall does change three decided rows: Ahero, Ombeyi, and Kobura are rainfall-yes and radar-no, and the quorum does not fire there. Rainfall alone would have counted all seven flood labels as hits. The three geometry abstentions are outside the 4 decided pairs.

## How the boxes were measured

Working extents are in `backtest/checks/zones.json`. Pixel counts are in `backtest/checks/radar_fractions.csv`.

| Place | Land pixels | Flooded pixels | Permanent-water pixels removed |
|---|---:|---:|---:|
| Ahero | 358,797 | 2,370 | 0 |
| Kabonyo Kanyagwal | 1,589,424 | 141,955 | 157,044 |
| Ombeyi | 1,586,442 | 4,427 | 0 |
| Kobura | 1,448,140 | 13,746 | 40,820 |

Ahero is a 3 km box around the town point, not the ward. On the JRC occurrence grid that box peaks at 73, so the 90 cutoff removes nothing. The reported flood includes lake backflow. The open-water fraction is still 0.0066.

Kabonyo Kanyagwal is the ward bbox. Occurrence reaches 99. This is the one place the frozen fraction clears.

Ombeyi is the ward bbox for the location Kenya News Agency named. Seven villages were submerged and not named. Occurrence inside this box peaks at 10, so almost none of it is mapped as water. The fraction is 0.0028.

Kobura is the ward bbox. The Star named a village, and that village point was not found. Occurrence in the ward reaches 100. The fraction on the remaining land is 0.0095.

Kakola Ombaka, Nyamasao, and Kadibo have no box. Nominatim and Photon returned different places (Nyamasaria, Kakola in Awasi, a Kadibo timber yard). Those coordinates were not measured. An Overpass search for Nyamasao, Ombaka, and Kadibo inside longitude 34.5–35.4 and latitude -0.6–0.2 returned no elements. Those three rows stay `no_geometry`.

## What the table leaves open

Open-water thresholding does not see flood under vegetation or inside buildings. That gap sits beside the table. It is not one of the miss buckets.

The boxes are OpenStreetMap extents, not a surveyed flood edge. Speckle is unfiltered. A filter would move the frozen threshold. Sentinel-1B was down, so the revisit is twelve days, and this table is only the 6 May scene. One season, with no dry labels, is not an accuracy claim.

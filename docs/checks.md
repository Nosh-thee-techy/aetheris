# Checks before the rule froze

These three checks were done on 12 October 2026, before any backtest score. The rule in `backtest/rule.toml` is frozen from this page. The label log is `docs/labels.md`. The scored table is `docs/agreement.md`. This page is the check that froze the rule.

## Eligibility

The hackathon is the [IEEE ClimateChain Global Hackathon 2026](https://ieee-climatechain-hack.devpost.com/). The track is Climate Data & Environmental Monitoring.

The Devpost badge and the written rules do not say the same thing.

The badge on the hackathon homepage says participants must be above the age of majority, students only, and that companies and professional organizations are excluded. It also says specific countries are excluded. The country names are not listed on the homepage, the rules page, or the organiser page.

The [rules page](https://ieee-climatechain-hack.devpost.com/rules) and the [organiser page](https://cmte.ieee.org/turkiye-blockchain/hackatlon/) list a wider set of people: students, academic researchers and faculty, independent developers and startups, and environmental professionals. Both exclude organisers, judges, and their immediate families. The organiser page also excludes anyone under 18. Previous grand-prize winners may enter only for the smaller awards.

Until that conflict is resolved, the safe reading is the badge: each person is a student, is 18 or older, and is not entering for a company. The organiser can be asked at tr-bchackhaton@ieee.org, which is the address printed on Devpost.

Devpost's judging criteria have no percentages. They are climate impact, innovation, technical execution, practical usefulness, and presentation. The organiser page prints two different weight tables, one of them the 30/30/10/10/10/10 split. That split is not on Devpost. Do not quote it as the Devpost rule.

The deadline Devpost's own schedule will enforce is 25 October 2026 at 5:00pm Moscow time. Submissions open on that schedule at 5 October 2026, 7:00am Moscow time. The rules page also says not to submit before 8:00am Pacific on 25 October, and the organiser page says 25 October at 11:59pm UTC. Those two clocks disagree with the schedule. Submit against the earlier Devpost deadline.

On 19 October 2026 the person building this confirmed they are a student and that the safe reading is met for them. The badge and the rules page still disagree. A second person, if one joins, has to pass the same reading.

## Sentinel-1 season

The report season is the 2024 long rains. The report scene is the Sentinel-1A pass on 6 May 2024.

Scenes were listed from the ASF DAAC catalogue, GRD HD, IW mode, intersecting the basin box from longitude 34.75 to 35.55 and latitude -0.40 to 0.30. A scene counts as covering the basin when its footprint includes the Kano plain and the Nandi and Kericho headwaters.

Relative orbit 130 does that. The 6 May 2024 slice runs from about longitude 34.3 to 36.9 and latitude -1.2 to 0.8. The same orbit repeats on 24 April and 18 May, twelve days either side. Ochieng (2025) mapped this flood with the Sentinel-1 acquisition on 6 May 2024, so the pass sits on the event rather than in a gap.

Relative orbit 28 does not cover the basin. Its eastern edge is near longitude 34.6 to 35.0, so it clips the lakeshore and misses the headwaters. Those passes are in the scene list and are marked rejected.

Sentinel-1B was not operating in 2024, so the usable revisit is twelve days. Water that rises and falls between 24 April and 6 May is invisible. That gap stays in the backtest as `no_scene` when a zone-week has no orbit-130 pass.

April 2020 is the other season. Sentinel-1A and Sentinel-1B were both flying, so orbit 130 and descending orbit 152 both cover the basin, on 5, 9, 17, 21, and 29 April. That season is for the rainfall check below. It is not the reported backtest.

The granules are in `backtest/checks/sentinel1_scenes.csv`.

## Where the rain fell

CHIRPS 2.0 daily Africa grids, 0.05 degree, were averaged over three boxes:

- Kano plain: longitude 34.85 to 35.10, latitude -0.28 to -0.05. Twenty-five pixels.
- Nandi and Tinderet: longitude 35.05 to 35.40, latitude 0.00 to 0.25. Thirty-five pixels.
- Kericho and Mau: longitude 35.15 to 35.50, latitude -0.45 to -0.15. Forty-two pixels.

The catchment value for a day is the unweighted mean of the two headwater box means. Daily means are in `backtest/checks/chirps_daily_means.csv`.

| Window | Kano plain | Headwaters |
|---|---:|---:|
| 1–11 April 2020, light rain | 30 mm | 16 mm |
| 12–26 April 2020, the wet spell | 209 mm | 260 mm |
| 20 April–6 May 2024, up to the report scene | 160 mm | 216 mm |
| 4–6 May 2024, the three days ending on the scene | 33 mm | 57 mm |

In both wet spells the headwaters received more rain than the plain. On 5 May 2024, the day before the report scene, the plain averaged 2.7 mm while Nandi–Tinderet averaged 18 mm and Kericho–Mau averaged 15 mm. On 26–28 April 2024 the plain was dry and the hills were not. The early, light days of April 2020 went the other way: the plain total was higher, on a small amount of rain.

A one-day lag does not describe these daily series. Correlation of headwater rain with plain rain in April 2020 is 0.91 on the same day, 0.56 one day later, and 0.33 two days later. The 2024 window has the same shape, 0.79 then 0.39. Daily CHIRPS cannot see a sub-daily travel time from the hills to the plain. The frozen lag is therefore zero days: the rainfall window ends on the radar acquisition date. High lake levels with little new rain remain a miss this rule will not catch.

The rainfall threshold is 40 mm, the sum of three daily catchment values ending on the scene date. It is a round prior placed between the dry 3-day total before 9 April 2020 (11 mm) and the wet 3-day totals on 21 April 2020 (41 mm) and 6 May 2024 (57 mm). It was not chosen to maximise a score. A slightly higher round number would have excluded the 21 April 2020 pass. The backtest can show whether 40 mm is too low. It should not be edited after the labels are filled.

## What was frozen

- Report scene: 6 May 2024, granule `S1A_IW_GRDH_1SDV_20240506T155655_20240506T155720_053752_068803_D2D7`.
- Rainfall reads the two headwater boxes, not the zone on the plain.
- Lag is 0 days. The sum is 3 days, ending on the acquisition date.
- The sum must reach 40 mm.
- Radar stays at the untuned prior: VV below -16 dB, flooded fraction above 0.05, permanent water removed, open water only.

## Sources

- ASF DAAC granule search, Sentinel-1 IW GRD HD, queried 12 October 2026.
- CHIRPS 2.0 Africa daily GeoTIFFs, `data.chc.ucsb.edu`.
- Ochieng, R. A. (2025). *Mapping flood spatiotemporal patterns and characteristics in the lower Nyando River basin, Kenya* (master's thesis, Miami University). The May 2024 flood map uses the 6 May 2024 Sentinel-1 acquisition.
- Devpost homepage, rules, and schedule for the IEEE ClimateChain Global Hackathon, and the IEEE Blockchain Türkiye organiser page, read 12 October 2026.

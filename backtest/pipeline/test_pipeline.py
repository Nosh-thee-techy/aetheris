import unittest
from datetime import date

from backtest.pipeline.ids import event_bounds, event_week, evidence_radar, evidence_rainfall, trigger_id, zone_id
from backtest.pipeline.keccak import keccak256
from backtest.pipeline.radar import radar_action, select_scene
from backtest.pipeline.rainfall import catchment_mm, published_total, rainfall_action, window_dates
from backtest.pipeline.rule import load_rule, rule_hash, rule_id, rule_id_text


class KeccakTests(unittest.TestCase):
    def test_empty_and_abc(self):
        self.assertEqual(
            keccak256(b"").hex(),
            "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470",
        )
        self.assertEqual(
            keccak256(b"abc").hex(),
            "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45",
        )


class RuleTests(unittest.TestCase):
    def test_frozen_thresholds_stay(self):
        rule = load_rule()
        self.assertEqual(rule["status"], "frozen")
        self.assertEqual(rule["radar"]["threshold_db"], -16.0)
        self.assertEqual(rule["radar"]["min_flooded_fraction"], 0.05)
        self.assertEqual(rule["rainfall"]["threshold_mm"], 40)
        self.assertEqual(rule["rainfall"]["lag_days"], 0)
        self.assertEqual(rule["rainfall"]["window_days"], 3)
        self.assertEqual(rule["rainfall"]["product"], "chirps")
        self.assertEqual(rule["radar"]["permanent_water_occurrence"], 90)
        self.assertEqual(rule_id_text(), "nyando-open-water-v1")
        self.assertEqual(len(rule_hash()), 32)
        self.assertEqual(len(rule_id()), 32)
        self.assertEqual(rule["event_weeks"], ["2024-05-04/2024-05-06"])
        self.assertIn("kabonyo-kanyagwal", rule["zones"])
        self.assertNotIn("nyamasaria", rule["zones"])


class IdTests(unittest.TestCase):
    def test_zone_and_evidence_are_stable(self):
        self.assertNotEqual(zone_id("kabonyo-kanyagwal"), zone_id("ahero"))
        self.assertEqual(zone_id("ahero"), zone_id("ahero"))
        scene = evidence_radar("item")
        self.assertEqual(scene, evidence_radar("item"))
        rain = evidence_rainfall(date(2024, 5, 4), date(2024, 5, 6))
        self.assertNotEqual(rain, scene)

    def test_event_window_covers_6_may(self):
        start, end = event_bounds(date(2024, 5, 4), date(2024, 5, 6))
        self.assertLess(start, end)
        self.assertEqual(end - start, 3 * 24 * 60 * 60)

    def test_trigger_id_binds_the_rule_file(self):
        week = event_week("2024-05-04/2024-05-06")
        first = trigger_id(zone_id("ahero"), week, rule_id(), rule_hash())
        second = trigger_id(zone_id("ahero"), week, rule_id(), keccak256(b"other-file"))
        self.assertEqual(len(first), 32)
        self.assertNotEqual(first, second)


class RainfallTests(unittest.TestCase):
    def test_window_ends_on_the_scene_date(self):
        days = window_dates(date(2024, 5, 6), 3, 0)
        self.assertEqual(days, [date(2024, 5, 4), date(2024, 5, 5), date(2024, 5, 6)])

    def test_published_may_total_clears_40(self):
        total = published_total(date(2024, 5, 6))
        self.assertEqual(round(total, 1), 56.7)
        self.assertEqual(rainfall_action(total, 40), "sign")

    def test_below_40_stays_silent(self):
        daily = {
            date(2024, 5, 4): (0.0, 0.0),
            date(2024, 5, 5): (10.0, 10.0),
            date(2024, 5, 6): (1.0, 1.0),
        }
        days = window_dates(date(2024, 5, 6), 3, 0)
        total = catchment_mm(daily, days)
        self.assertLess(total, 40)
        self.assertEqual(rainfall_action(total, 40), "silence")

    def test_catchment_is_the_mean_of_the_two_boxes(self):
        daily = {date(2024, 5, 6): (10.0, 30.0)}
        self.assertEqual(catchment_mm(daily, [date(2024, 5, 6)]), 20.0)


class RadarTests(unittest.TestCase):
    def test_only_a_clear_fraction_signs(self):
        self.assertEqual(radar_action("yes", "threshold_met"), "sign")
        self.assertEqual(radar_action("no", "below_threshold"), "silence")
        self.assertEqual(radar_action("abstain", "no_geometry"), "silence")
        self.assertEqual(radar_action("abstain", "no_scene"), "silence")

    def test_orbit_130_with_vv_is_the_scene(self):
        features = [
            {"properties": {"sat:relative_orbit": 28}, "assets": {"vv": {"href": "edge"}}},
            {
                "id": "keep",
                "properties": {"sat:relative_orbit": 130, "sat:orbit_state": "ascending"},
                "assets": {"vv": {"href": "vv.tif"}},
            },
        ]
        chosen = select_scene(features)
        self.assertEqual(chosen["id"], "keep")

    def test_missing_orbit_130_does_not_invent_a_scene(self):
        features = [{"properties": {"sat:relative_orbit": 28}, "assets": {"vv": {"href": "edge"}}}]
        self.assertIsNone(select_scene(features))


if __name__ == "__main__":
    unittest.main()

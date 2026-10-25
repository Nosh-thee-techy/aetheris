"""The vulnerability layer must stay a labelled adaptation, not a measurement."""

from __future__ import annotations

import inspect
import unittest

from backtest.pipeline import damage


class CurveTests(unittest.TestCase):
    def test_table_points_are_exact(self):
        self.assertEqual(damage.damage_ratio("africa_residential", 0.5), 0.22)
        self.assertEqual(damage.damage_ratio("africa_residential", 1.0), 0.38)
        self.assertEqual(damage.damage_ratio("weak_structure", 0.5), 0.49)

    def test_waist_depth_is_between_the_surrounding_points(self):
        ratio = damage.damage_ratio("africa_residential", 0.9)
        self.assertGreater(ratio, 0.22)
        self.assertLess(ratio, 0.38)
        expected = 0.22 + 0.8 * (0.38 - 0.22)
        self.assertAlmostEqual(ratio, expected)

    def test_semi_permanent_is_the_mean_of_the_two_curves(self):
        a = damage.damage_ratio("africa_residential", 0.9)
        b = damage.damage_ratio("weak_structure", 0.9)
        self.assertAlmostEqual(damage.damage_ratio("semi_permanent", 0.9), (a + b) / 2)

    def test_negative_depth_is_refused(self):
        with self.assertRaises(ValueError):
            damage.damage_ratio("africa_residential", -0.1)


class BookTests(unittest.TestCase):
    def test_ahero_depth_is_adapted_from_waist_high(self):
        row = damage.row_for("ahero")
        self.assertEqual(row["depth_m"], 0.9)
        self.assertEqual(row["depth_provenance"], "adapted")
        self.assertEqual(row["housing_class"], "permanent_masonry")
        self.assertIsNone(row["tiv_kes"])

    def test_other_places_borrow_ahero_depth_as_an_assumption(self):
        for slug in ("kabonyo-kanyagwal", "kakola-ombaka", "kadibo"):
            self.assertEqual(damage.row_for(slug)["depth_provenance"], "assumption")

    def test_tiv_only_where_a_report_named_households(self):
        self.assertEqual(damage.row_for("kabonyo-kanyagwal")["households"], 700)
        self.assertEqual(damage.row_for("kakola-ombaka")["households"], 300)
        self.assertEqual(damage.row_for("kadibo")["households"], 20)
        self.assertIsNone(damage.row_for("ombeyi")["households"])
        self.assertIsNone(damage.row_for("ahero")["households"])

    def test_ground_up_is_ratio_times_households_times_unit(self):
        row = damage.row_for("kadibo")
        self.assertEqual(row["tiv_kes"], 20 * 153_500)
        self.assertEqual(row["ground_up_kes"], round(row["damage_ratio"] * 20 * 153_500))

    def test_radar_fraction_is_not_an_argument(self):
        params = list(inspect.signature(damage.damage_ratio).parameters)
        self.assertEqual(params, ["curve", "depth_m"])


if __name__ == "__main__":
    unittest.main()

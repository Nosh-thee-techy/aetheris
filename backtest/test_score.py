import unittest

from backtest.score import (
    agreement_bucket,
    index_labels,
    index_observations,
    quorum,
    score,
)


def labels(*rows: tuple[str, str]) -> dict:
    parsed = [
        {
            "zone_id": zone,
            "event_start": "2020-04-01",
            "event_end": "2020-04-08",
            "label": label,
            "label_source": "fixture",
        }
        for zone, label in rows
    ]
    return index_labels(parsed)


def observations(*rows: tuple[str, str, str, str]) -> dict:
    parsed = [
        {
            "zone_id": zone,
            "event_start": "2020-04-01",
            "event_end": "2020-04-08",
            "source": source,
            "decision": decision,
            "reason": reason,
        }
        for zone, source, decision, reason in rows
    ]
    return index_observations(parsed)


class QuorumTest(unittest.TestCase):
    def test_radar_and_rainfall_fire(self):
        self.assertTrue(quorum("yes", "yes"))

    def test_radar_alone_does_not_fire(self):
        self.assertFalse(quorum("yes", "no"))
        self.assertFalse(quorum("yes", "abstain"))

    def test_rainfall_alone_does_not_fire(self):
        self.assertFalse(quorum("no", "yes"))
        self.assertFalse(quorum("abstain", "yes"))


class AgreementTest(unittest.TestCase):
    def test_buckets(self):
        self.assertEqual(agreement_bucket("yes", "yes"), "both_yes")
        self.assertEqual(agreement_bucket("yes", "no"), "radar_only")
        self.assertEqual(agreement_bucket("no", "yes"), "rainfall_only")
        self.assertEqual(agreement_bucket("no", "no"), "both_no")
        self.assertEqual(agreement_bucket("abstain", "yes"), "radar_abstain")
        self.assertEqual(agreement_bucket("yes", "abstain"), "rainfall_abstain")
        self.assertEqual(agreement_bucket("abstain", "abstain"), "both_abstain")


class ScoreTest(unittest.TestCase):
    def test_unknown_does_not_inflate_precision(self):
        result = score(
            labels(("a", "unknown"), ("b", "not_flooded"), ("c", "")),
            observations(
                ("a", "radar", "yes", "threshold_met"),
                ("a", "rainfall", "yes", "threshold_met"),
                ("b", "radar", "yes", "threshold_met"),
                ("b", "rainfall", "yes", "threshold_met"),
                ("c", "radar", "yes", "threshold_met"),
                ("c", "rainfall", "no", "below_threshold"),
            ),
        )
        self.assertEqual(result["counts"]["unknown"], 2)
        self.assertEqual(result["counts"]["fired_unknown"], 1)
        self.assertEqual(result["counts"]["false_trigger"], 1)
        self.assertEqual(result["counts"]["true_positive"], 0)
        self.assertEqual(result["precision"], 0.0)
        self.assertIsNone(result["recall"])

    def test_disagreement_and_miss_buckets(self):
        result = score(
            labels(
                ("paid", "flooded"),
                ("dark-soil", "not_flooded"),
                ("no-pass", "flooded"),
                ("dry-radar", "flooded"),
                ("rain-missing", "flooded"),
                ("local-rain", "not_flooded"),
            ),
            observations(
                ("paid", "radar", "yes", "threshold_met"),
                ("paid", "rainfall", "yes", "threshold_met"),
                ("dark-soil", "radar", "yes", "threshold_met"),
                ("dark-soil", "rainfall", "no", "below_threshold"),
                ("no-pass", "radar", "abstain", "no_scene"),
                ("no-pass", "rainfall", "yes", "threshold_met"),
                ("dry-radar", "radar", "no", "below_threshold"),
                ("dry-radar", "rainfall", "yes", "threshold_met"),
                ("rain-missing", "radar", "yes", "threshold_met"),
                ("rain-missing", "rainfall", "abstain", "no_data"),
                ("local-rain", "radar", "no", "below_threshold"),
                ("local-rain", "rainfall", "yes", "threshold_met"),
            ),
        )
        self.assertEqual(result["counts"]["true_positive"], 1)
        self.assertEqual(result["counts"]["false_trigger"], 0)
        self.assertEqual(result["counts"]["miss"], 3)
        self.assertEqual(result["counts"]["true_negative"], 2)
        self.assertEqual(result["misses"]["no_scene"], 1)
        self.assertEqual(result["misses"]["below_threshold"], 1)
        self.assertEqual(result["misses"]["rainfall_gap"], 1)
        self.assertEqual(result["agreement"]["both_yes"], 1)
        self.assertEqual(result["agreement"]["radar_only"], 1)
        self.assertEqual(result["agreement"]["rainfall_only"], 2)
        self.assertEqual(result["agreement"]["radar_abstain"], 1)
        self.assertEqual(result["agreement"]["rainfall_abstain"], 1)
        self.assertEqual(result["disagreements"], 3)
        self.assertAlmostEqual(result["recall"], 0.25)
        self.assertAlmostEqual(result["basis_risk"], 0.75)
        self.assertEqual(result["precision"], 1.0)

    def test_duplicate_label_is_rejected(self):
        with self.assertRaises(ValueError):
            index_labels(
                [
                    {"zone_id": "a", "event_start": "1", "event_end": "2", "label": "flooded"},
                    {"zone_id": "a", "event_start": "1", "event_end": "2", "label": "not_flooded"},
                ]
            )

    def test_missing_attester_abstains(self):
        result = score(
            labels(("a", "flooded")),
            observations(("a", "rainfall", "yes", "threshold_met")),
        )
        self.assertEqual(result["counts"]["miss"], 1)
        self.assertEqual(result["misses"]["no_scene"], 1)
        self.assertEqual(result["agreement"]["radar_abstain"], 1)


if __name__ == "__main__":
    unittest.main()

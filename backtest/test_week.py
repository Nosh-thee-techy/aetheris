"""The week job scores published files and does not invent a feed."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backtest import week
from backtest.score import MISS_BUCKETS, load_csv


class WeekJobTests(unittest.TestCase):
    def test_recipe_is_the_offline_job(self):
        text = week.recipe()
        self.assertIn("offline job", text)
        self.assertIn("not a page load", text)
        self.assertIn("radar_fraction.py", text)
        self.assertIn("rainfall_observations.py", text)
        self.assertIn("config/rule.yaml", text)
        self.assertIn("not a validation study", text)
        self.assertIn("does not run a RAG", text)
        self.assertIn("Do not invent an outline", text)
        self.assertNotIn("%", text)

    def test_no_gauge_file_is_said_plainly(self):
        self.assertFalse(week.GAUGES.exists())
        self.assertIn("No gauge file", week.gauges_status())
        self.assertIn("Do not stub", week.gauges_status())

    def test_score_published_matches_the_files(self):
        result = week.score_published()
        self.assertEqual(result["flood_labels"], 7)
        self.assertEqual(result["counts"]["true_positive"], 1)
        self.assertEqual(result["counts"]["miss"], 6)
        self.assertEqual(result["counts"]["false_trigger"], 0)
        self.assertEqual(result["misses"]["below_threshold"], 3)
        self.assertEqual(result["misses"]["no_geometry"], 3)
        self.assertEqual(result["misses"]["no_scene"], 0)
        self.assertEqual(result["rules"]["rainfall_only"]["hits"], 7)
        self.assertEqual(result["rules"]["radar_plus_rainfall"]["hits"], 1)

    def test_write_includes_every_miss_reason(self):
        result = week.score_published()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "counts.csv"
            from backtest.score import write_results

            write_results(result, path)
            rows = load_csv(path)
        names = {row["name"] for row in rows if row["table"] == "miss"}
        self.assertEqual(names, set(MISS_BUCKETS))

    def test_recipe_flag_does_not_score(self):
        buf = io.StringIO()
        with patch("sys.argv", ["week", "--recipe"]):
            with redirect_stdout(buf):
                week.main()
        out = buf.getvalue()
        self.assertIn("How a week is scored", out)
        self.assertNotIn("quorum hits:", out)


if __name__ == "__main__":
    unittest.main()

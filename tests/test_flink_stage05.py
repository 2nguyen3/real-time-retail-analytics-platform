"""Stage 05 checks for offset isolation, fixtures, and changelog materialization."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sql.flink.run_sql import render
from sql.flink.test_events import build_quality, build_window
from sql.flink.verify_results import expected, final_rows


class FlinkStage05Tests(unittest.TestCase):
    def test_specific_offset_boundaries_are_rendered(self):
        with tempfile.TemporaryDirectory() as directory:
            start = Path(directory) / "start.json"
            end = Path(directory) / "end.json"
            start.write_text(json.dumps({"topic": "retail.sales.transactions", "high_offsets": {"0": 5, "1": 0, "2": 9}}))
            end.write_text(json.dumps({"topic": "retail.sales.transactions", "high_offsets": {"0": 7, "1": 0, "2": 11}}))
            sql = render("test_01", start, end, "totals")
            self.assertIn("'scan.startup.mode' = 'specific-offsets'", sql)
            self.assertIn("partition:0,offset:5;partition:1,offset:0;partition:2,offset:9", sql)
            self.assertIn("partition:0,offset:7;partition:1,offset:0;partition:2,offset:11", sql)
            self.assertIn("SUM(line_revenue)", sql)
            self.assertNotIn("earliest-offset", sql)
            with self.assertRaisesRegex(ValueError, "end offsets precede"):
                render("test_01", end, start, "totals")

    def test_quality_fixture_expected_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quality.jsonl"
            build_quality(path)
            self.assertEqual(expected(path, None)["counts"], {
                "raw": 10, "valid_before_dedup": 5, "invalid": 5,
                "duplicate": 1, "unique_valid": 4,
            })

    def test_window_fixture_has_late_event_after_advancer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "window.jsonl"
            build_window(path, "test_window")
            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(records), 9)
            self.assertEqual(records[3]["event_time"], "2024-01-01T00:00:30Z")
            self.assertGreater(records[2]["event_time"], records[3]["event_time"])
            self.assertEqual(len({r["transaction_id"] for r in records}), 9)

    def test_changelog_retractions_are_not_summed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "changelog.log"
            path.write_text("| +I | demo | 1 | 2 | 3.00 |\n| -U | demo | 1 | 2 | 3.00 |\n| +U | demo | 2 | 3 | 5.00 |\n")
            self.assertEqual(final_rows(path, (0,)), {("demo",): ("demo", "2", "3", "5.00")})


if __name__ == "__main__":
    unittest.main()

"""Regression checks for Stage 06 independent source reconciliation."""

from __future__ import annotations

import unittest
from pathlib import Path

from sql.postgres.reconcile import expected


ROOT = Path(__file__).resolve().parents[1]


class ReconciliationTests(unittest.TestCase):
    def test_synthetic_1000_known_totals(self) -> None:
        groups, counts = expected(ROOT / "data/samples/synthetic_10000.jsonl", 1000,
                                  "stage06_test", replayed=True)
        self.assertEqual(counts, {"raw": 1000, "valid": 1000, "invalid": 0, "duplicate": 0})
        for table, size in (("sales_by_store", 5), ("sales_by_store_product", 373),
                            ("sales_by_store_minute", 334)):
            with self.subTest(table=table):
                self.assertEqual(len(groups[table]), size)
                self.assertEqual(sum(row[0] for row in groups[table].values()), 1000)
                self.assertEqual(sum(row[1] for row in groups[table].values()), 2985)
                self.assertEqual(str(sum(row[2] for row in groups[table].values())), "310265.83")

    def test_same_basket_distinct_lines_are_counted(self) -> None:
        groups, counts = expected(ROOT / "tests/fixtures/quality_cases.jsonl", None,
                                  "fixture_001", replayed=False)
        self.assertEqual(counts["valid"], 3)
        self.assertEqual(counts["duplicate"], 1)
        self.assertEqual(sum(row[0] for row in groups["sales_by_store"].values()), 3)


if __name__ == "__main__":
    unittest.main()

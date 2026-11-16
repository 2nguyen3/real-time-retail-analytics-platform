"""Stage 02 checks for reproducibility and independent ETL expectations."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from producer.audit_data import invalid_reason, summarize, utc_timestamp  # noqa: E402


class RetailDataTests(unittest.TestCase):
    def test_quality_fixture_expected_totals(self):
        path = ROOT / "tests/fixtures/quality_cases.jsonl"
        actual = summarize(path, seed=0, run_id="fixture_001")
        self.assertEqual(
            {key: actual[key] for key in ("message_count", "unique_transaction_id_count", "valid_count", "invalid_count", "duplicate_count", "expected_quantity", "expected_revenue")},
            {
                "message_count": 8,
                "unique_transaction_id_count": 7,
                "valid_count": 3,
                "invalid_count": 4,
                "duplicate_count": 1,
                "expected_quantity": 6,
                "expected_revenue": "6.50",
            },
        )
        self.assertEqual(actual["invalid_reasons"], {"event_time": 1, "missing_field": 1, "price": 1, "quantity": 1})
        self.assertEqual(actual["expected_by_store"], {"S001": {"quantity": 3, "revenue": "5.00"}, "S002": {"quantity": 3, "revenue": "1.50"}})
        self.assertEqual(actual["expected_by_product"], {"P00001": {"quantity": 5, "revenue": "4.50"}, "P00002": {"quantity": 1, "revenue": "2.00"}})
        self.assertEqual(actual["expected_by_hour_utc"], {"2024-01-01T00:00:00Z": {"quantity": 3, "revenue": "5.00"}, "2024-01-01T01:00:00Z": {"quantity": 3, "revenue": "1.50"}})
        raw = path.read_bytes()
        self.assertEqual(actual["raw_file_bytes"], len(raw))
        self.assertEqual(actual["sha256"], hashlib.sha256(raw).hexdigest())

    def test_same_basket_different_line_ids_are_valid(self):
        lines = (ROOT / "tests/fixtures/quality_cases.jsonl").read_text(encoding="utf-8").splitlines()
        first, second = map(json.loads, lines[:2])
        self.assertEqual(first["basket_id"], second["basket_id"])
        self.assertNotEqual(first["transaction_id"], second["transaction_id"])
        schema = json.loads((ROOT / "data/schema/transaction.schema.json").read_text(encoding="utf-8"))
        for record in (first, second):
            self.assertIsNone(invalid_reason(record, set(schema["required"]), "fixture_001"))

    def test_invalid_fields_and_utc(self):
        path = ROOT / "tests/fixtures/quality_cases.jsonl"
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        required = set(json.loads((ROOT / "data/schema/transaction.schema.json").read_text(encoding="utf-8"))["required"])
        self.assertEqual([invalid_reason(row, required, "fixture_001") for row in records[4:]], ["quantity", "price", "missing_field", "event_time"])
        self.assertTrue(utc_timestamp("2024-02-29T23:59:59Z"))
        self.assertFalse(utc_timestamp("2024-02-30T00:00:00Z"))
        self.assertFalse(utc_timestamp("2024-01-01T07:00:00+07:00"))
        self.assertFalse(utc_timestamp("2024-01-01T00:00:00"))

    def test_generator_is_reproducible_and_manifest_matches_file(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            outputs = []
            for index in (1, 2):
                output = directory / f"run{index}.jsonl"
                manifest = directory / f"run{index}.json"
                subprocess.run(
                    [sys.executable, str(ROOT / "producer/generate_data.py"), "--count", "30", "--seed", "123", "--run-id", "test_123", "--output", str(output), "--manifest", str(manifest)],
                    check=True, capture_output=True, text=True,
                )
                outputs.append((output, json.loads(manifest.read_text(encoding="utf-8"))))
            self.assertEqual(outputs[0][0].read_bytes(), outputs[1][0].read_bytes())
            for path, manifest in outputs:
                raw = path.read_bytes()
                self.assertEqual(manifest["message_count"], 30)
                self.assertEqual(manifest["valid_count"], 30)
                self.assertEqual(manifest["invalid_count"], 0)
                self.assertEqual(manifest["duplicate_count"], 0)
                self.assertEqual(manifest["raw_file_bytes"], len(raw))
                self.assertEqual(manifest["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(manifest["json_payload_bytes"], len(raw) - 30)
                self.assertEqual(manifest["expected_quantity"], sum(json.loads(line)["quantity"] for line in raw.splitlines()))
                self.assertEqual(sum(int(row["quantity"]) for row in manifest["expected_by_store"].values()), manifest["expected_quantity"])
                self.assertEqual(len({json.loads(line)["transaction_id"] for line in raw.splitlines()}), 30)
                self.assertEqual(manifest["source_types"], ["synthetic"])
                self.assertEqual(manifest["currencies"], ["USD"])
                self.assertTrue(utc_timestamp(manifest["generated_at_utc"]))
                self.assertTrue(utc_timestamp(manifest["file_modified_at_utc"]))

    def test_schema_file_has_contract_keys(self):
        schema = json.loads((ROOT / "data/schema/transaction.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertLessEqual(set(schema["required"]), set(schema["properties"]))
        row = json.loads((ROOT / "tests/fixtures/quality_cases.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(set(row), set(schema["required"]))


if __name__ == "__main__":
    unittest.main()

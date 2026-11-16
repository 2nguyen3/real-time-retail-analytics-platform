"""Converter checks using a tiny source-shaped CSV created in memory."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from producer.audit_data import summarize  # noqa: E402
from producer.convert_dunnhumby import convert_zip, source_offset  # noqa: E402


class DunnhumbyConversionTests(unittest.TestCase):
    def test_official_sample_when_present(self):
        source = ROOT / "data/raw/dunnhumby_sort_of_real_sample_2k.zip"
        if not source.is_file():
            self.skipTest("official ZIP is intentionally excluded from Git")
        self.assertEqual(source.stat().st_size, 162_979)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), "b0af7cfec179d994195ca1c6ec05d3f916fa9707704b61f8529b19324ccc28cd")
        source_rows = 0
        source_quantity = 0
        source_spend = Decimal("0")
        source_lines = []
        basket_values = set()
        with ZipFile(source) as archive:
            for entry in sorted(name for name in archive.namelist() if "transactions_" in name):
                with io.TextIOWrapper(archive.open(entry), encoding="utf-8-sig", newline="") as stream:
                    for row in csv.DictReader(stream):
                        source_lines.append(row)
                        source_rows += 1
                        source_quantity += int(row["QUANTITY"])
                        source_spend += Decimal(row["SPEND"])
                        basket_values.add(row["BASKET_ID"])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "converted.jsonl"
            counts = convert_zip(source, output, run_id="source_test", offset=source_offset("+00:00"))
            result = summarize(output, run_id="source_test")
            self.assertEqual((source_rows, source_quantity, source_spend), (12_905, 19_112, Decimal("23809.25")))
            self.assertEqual(basket_values, {"9.94E+14", "9.94102E+14"})
            self.assertEqual((counts["rows"], counts["missing_customer"], counts["unusable_basket_id"]), (12_905, 2_770, 12_905))
            self.assertEqual((result["message_count"], result["valid_count"], result["invalid_count"], result["duplicate_count"]), (12_905, 12_905, 0, 0))
            self.assertEqual((result["expected_quantity"], Decimal(result["expected_revenue"])), (source_quantity, source_spend))
            with output.open(encoding="utf-8") as converted:
                for original, line in zip(source_lines, converted, strict=True):
                    item = json.loads(line)
                    self.assertEqual(Decimal(item["line_revenue"]), Decimal(original["SPEND"]))
                    self.assertEqual(item["quantity"], int(original["QUANTITY"]))
                    self.assertIsNone(item["basket_id"])

    def test_converts_source_spend_without_rounding_loss(self):
        columns = ["SHOP_DATE", "SHOP_HOUR", "QUANTITY", "SPEND", "PROD_CODE", "PROD_CODE_40", "CUST_CODE", "BASKET_ID", "STORE_CODE", "STORE_REGION"]
        source_rows = [
            ["20060823", "1", "3", "0.10", "PRD1", "D01", "CUST1", "994100100000020", "STORE1", "E02"],
            ["20060823", "1", "2", "1.25", "PRD2", "D01", "CUST1", "994100100000020", "STORE1", "E02"],
            ["20060823", "2", "1", "2.00", "PRD3", "D02", "", "9.94E+14", "STORE2", "W01"],
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.zip"
            output = root / "converted.jsonl"
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(columns)
            writer.writerows(source_rows)
            with ZipFile(source, "w") as archive:
                archive.writestr("sample/transactions_200626.csv", buffer.getvalue())
            counts = convert_zip(source, output, run_id="source_test", offset=source_offset("+07:00"))
            records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(counts, {"rows": 3, "missing_customer": 1, "unusable_basket_id": 1})
            self.assertEqual(len({row["transaction_id"] for row in records}), 3)
            self.assertEqual(records[0]["basket_id"], records[1]["basket_id"])
            self.assertNotEqual(records[0]["transaction_id"], records[1]["transaction_id"])
            self.assertIsNone(records[2]["basket_id"])
            self.assertIsNone(records[2]["customer_id"])
            self.assertEqual(records[0]["store_region"], "E02")
            self.assertEqual(records[0]["event_time"], "2006-08-22T18:00:00Z")
            self.assertEqual(records[0]["event_time_precision"], "hour")
            self.assertEqual(records[0]["event_time_basis"], "assumed_timezone")
            self.assertEqual(records[0]["currency"], "XXX")
            self.assertEqual(records[0]["price"], "0.03333333")
            source_total = sum((Decimal(row[3]) for row in source_rows), Decimal("0"))
            converted_total = sum((Decimal(row["line_revenue"]) for row in records), Decimal("0"))
            self.assertEqual(source_total, converted_total)
            self.assertEqual([Decimal(row["line_revenue"]) for row in records], [Decimal(row[3]) for row in source_rows])
            manifest = summarize(output, run_id="source_test")
            self.assertEqual(manifest["valid_count"], 3)
            self.assertEqual(manifest["expected_revenue"], "3.35")
            self.assertEqual(manifest["expected_quantity"], 6)
            self.assertEqual(manifest["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())

    def test_invalid_offset_is_rejected(self):
        for value in ("UTC", "+14:01", "+25:00", "+07:70"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                source_offset(value)


if __name__ == "__main__":
    unittest.main()

"""Stage 04 unit checks; Kafka integration is run separately against the broker."""

from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import patch
from decimal import Decimal
from pathlib import Path

from producer.generate_data import rows
from producer.kafka_common import Publisher, check_positive, prepare, validate
from producer.replay import preflight, read_records
from producer.consumer_probe import probe, validate_message


class KafkaProducerTests(unittest.TestCase):
    def test_contract_and_replay_preserve_money_history_and_ids(self):
        source = next(rows(1, 41, "original_run"))
        original = dict(source)
        item, payload = prepare(source, "replay_run")
        self.assertEqual(source, original)
        self.assertEqual(item["transaction_id"], source["transaction_id"])
        self.assertEqual(item["event_time"], source["event_time"])
        self.assertEqual(Decimal(item["line_revenue"]), Decimal(source["line_revenue"]))
        self.assertEqual(item["run_id"], "replay_run")
        self.assertIsNotNone(item["emitted_at"])
        self.assertIsNone(validate_message(json.loads(payload)))

    def test_same_basket_distinct_transaction_ids(self):
        first, second = list(rows(2, 1, "test_run"))
        self.assertEqual(first["basket_id"], second["basket_id"])
        self.assertNotEqual(first["transaction_id"], second["transaction_id"])

    def test_replay_preflight_rejects_invalid_before_enqueue(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            good = next(rows(1, 1, "test_run"))
            bad = dict(good)
            del bad["store_id"]
            path.write_text(json.dumps(good) + "\n" + json.dumps(bad) + "\n")
            with self.assertRaisesRegex(ValueError, "store_id"):
                preflight(path, None, "replay_run")
            path.write_text(json.dumps(good) + "\n" + json.dumps(good) + "\n")
            with self.assertRaisesRegex(ValueError, "duplicate transaction_id"):
                preflight(path, None, "replay_run")
            with self.assertRaisesRegex(ValueError, "input does not exist"):
                preflight(path.with_name("absent.jsonl"), None, "replay_run")
            path.write_text("{broken json\n")
            with self.assertRaisesRegex(ValueError, "Expecting property name"):
                list(read_records(path, None))
            path.write_text("")
            with self.assertRaisesRegex(ValueError, "no messages"):
                preflight(path, None, "replay_run")

    def test_invalid_values_and_utc(self):
        item = next(rows(1, 1, "test_run"))
        for field, value in (("quantity", 0), ("price", -1), ("event_time", "2024-02-30T00:00:00Z")):
            with self.subTest(field=field):
                bad = dict(item)
                bad[field] = value
                with self.assertRaises(ValueError):
                    validate(bad)
        for value, name in ((0, "limit"), (-1, "rate")):
            with self.assertRaisesRegex(ValueError, name):
                check_positive(value, name)
        with self.assertRaisesRegex(ValueError, "rate"):
            check_positive(float("nan"), "rate")

    def test_dunnhumby_line_preservation_when_available(self):
        source = Path(__file__).resolve().parents[1] / "data/generated/sort_of_real_2k_assumed_utc.jsonl"
        if not source.exists():
            self.skipTest("converted official sample is intentionally Git ignored")
        record = next(read_records(source, 1))
        item, payload = prepare(record, "source_replay")
        self.assertIsNone(item["basket_id"])
        self.assertEqual(item["currency"], "XXX")
        self.assertEqual(item["event_time_precision"], "hour")
        self.assertEqual(item["line_revenue"], record["line_revenue"])
        self.assertEqual(item["event_time"], record["event_time"])
        self.assertIsNone(validate_message(json.loads(payload)))

    def test_delivery_callback_is_required_for_success(self):
        class FakeProducer:
            def __init__(self, config):
                self.callback = None

            def produce(self, topic, key, value, on_delivery):
                self.callback = on_delivery

            def poll(self, timeout):
                return 0

            def flush(self, timeout):
                return 1 if self.callback else 0

        with patch("producer.kafka_common.Producer", FakeProducer):
            publisher = Publisher("localhost:9094", "test", "test_run")
            publisher.send(next(rows(1, 1, "test_run")))
            result = publisher.finish()
            self.assertEqual((result["attempted"], result["enqueued"], result["delivered"], result["pending"]), (1, 1, 0, 1))
            self.assertEqual(result["test_status"], "FAIL")

    def test_consumer_rejects_duplicate_id_and_invalid_schema(self):
        first, second = list(rows(2, 1, "probe_run"))
        second["transaction_id"] = first["transaction_id"]
        for record in (first, second):
            record["emitted_at"] = "2026-11-16T00:00:00Z"

        class Message:
            def __init__(self, record, offset):
                self.record, self.number = record, offset

            def error(self): return None
            def value(self): return json.dumps(self.record).encode()
            def key(self): return self.record["store_id"].encode()
            def partition(self): return 0
            def offset(self): return self.number

        class Client:
            def __init__(self, records): self.messages = iter(records)
            def assign(self, partitions): pass
            def poll(self, timeout): return next(self.messages, None)

        baseline = {"topic": "test", "partition_count": 1, "high_offsets": {"0": 0}}
        result = probe(Client([Message(first, 0), Message(second, 1)]), baseline, "probe_run", 2, 1)
        self.assertEqual(result["consumed"], 2)
        self.assertEqual(result["unique_transaction_ids"], 1)
        self.assertEqual(result["test_status"], "FAIL")
        bad = dict(first, quantity=0)
        self.assertIsNotNone(validate_message(bad))
        changed = dict(first, line_revenue="0.00")
        result = probe(Client([Message(changed, 0)]), baseline, "probe_run", 1, 1,
                       {first["transaction_id"]: first})
        self.assertEqual(result["source_mismatch_count"], 1)
        self.assertEqual(result["test_status"], "FAIL")


if __name__ == "__main__":
    unittest.main()

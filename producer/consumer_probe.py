"""Capture Kafka end offsets, then independently verify one replay run."""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from confluent_kafka import Consumer, KafkaException, TopicPartition
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "data/schema/transaction.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def consumer(bootstrap: str) -> Consumer:
    config = {
        "bootstrap.servers": bootstrap,
        "group.id": f"retail-probe-{uuid.uuid4()}",
        "enable.auto.commit": False,
        "auto.offset.reset": "error",
    }
    if "localhost" in bootstrap:
        config["broker.address.family"] = "v4"
    return Consumer(config)


def capture(client: Consumer, topic: str) -> dict:
    metadata = client.list_topics(topic=topic, timeout=10)
    info = metadata.topics.get(topic)
    if info is None or info.error:
        raise RuntimeError(f"topic unavailable: {topic}: {info.error if info else 'missing'}")
    offsets = {}
    for partition in sorted(info.partitions):
        _, high = client.get_watermark_offsets(TopicPartition(topic, partition), timeout=10, cached=False)
        offsets[str(partition)] = high
    return {"topic": topic, "partition_count": len(offsets), "high_offsets": offsets,
            "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def validate_message(record: object) -> str | None:
    if not isinstance(record, dict):
        return "not_object"
    errors = list(VALIDATOR.iter_errors(record))
    if errors:
        return f"schema: {errors[0].message}"
    for field in ("event_time", "emitted_at"):
        value = record[field]
        if value is not None:
            try:
                datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                return f"invalid_{field}"
    if record["emitted_at"] is None:
        return "missing_emitted_at"
    return None


def probe(client: Consumer, baseline: dict, run_id: str, expected: int, timeout: float,
          source_records: dict[str, dict] | None = None) -> dict:
    topic = baseline["topic"]
    offsets = {int(p): int(n) for p, n in baseline["high_offsets"].items()}
    client.assign([TopicPartition(topic, p, offset) for p, offset in offsets.items()])
    seen: set[str] = set()
    observed_offsets: dict[int, list[int]] = {}
    count = 0
    invalid = 0
    key_mismatch = 0
    source_mismatch = 0
    unattributed_json_errors = 0
    quantity = 0
    revenue = Decimal("0.00")
    basket_null_count = 0
    currencies = Counter()
    sources = Counter()
    deadline = time.monotonic() + timeout
    while count < expected and time.monotonic() < deadline:
        message = client.poll(min(1.0, max(0.01, deadline - time.monotonic())))
        if message is None:
            continue
        if message.error():
            raise RuntimeError(str(message.error()))
        try:
            record = json.loads(message.value())
        except (UnicodeDecodeError, json.JSONDecodeError):
            unattributed_json_errors += 1
            continue
        if not isinstance(record, dict) or record.get("run_id") != run_id:
            continue
        count += 1
        observed_offsets.setdefault(message.partition(), []).append(message.offset())
        reason = validate_message(record)
        if reason is not None:
            invalid += 1
            continue
        if message.key() != record["store_id"].encode("utf-8"):
            key_mismatch += 1
        seen.add(record["transaction_id"])
        if source_records is not None:
            source = source_records.get(record["transaction_id"])
            actual = {key: value for key, value in record.items() if key not in ("run_id", "emitted_at")}
            reference = ({key: value for key, value in source.items() if key not in ("run_id", "emitted_at")}
                         if source is not None else None)
            if actual != reference:
                source_mismatch += 1
        quantity += record["quantity"]
        revenue += Decimal(record["line_revenue"])
        basket_null_count += record["basket_id"] is None
        currencies[record["currency"]] += 1
        sources[record["source_type"]] += 1
    return {
        "run_id": run_id, "topic": topic, "expected": expected, "consumed": count,
        "unique_transaction_ids": len(seen), "validation_error_count": invalid,
        "key_mismatch_count": key_mismatch, "unattributed_json_errors": unattributed_json_errors,
        "source_mismatch_count": source_mismatch,
        "quantity": quantity, "line_revenue": f"{revenue:.2f}",
        "basket_null_count": basket_null_count, "currencies": dict(currencies), "source_types": dict(sources),
        "partition_count": baseline["partition_count"],
        "observed_offsets": {str(p): {"first": min(values), "last": max(values), "count": len(values)}
                             for p, values in observed_offsets.items()},
        "test_status": "PASS" if count == expected and len(seen) == expected and invalid == 0
                                  and key_mismatch == 0 and source_mismatch == 0 else "FAIL",
    }


def load_source(path: Path, count: int) -> dict[str, dict]:
    records = {}
    with path.open(encoding="utf-8") as handle:
        for index in range(count):
            line = handle.readline()
            if not line:
                raise ValueError(f"source has fewer than {count} lines")
            record = json.loads(line)
            transaction_id = record["transaction_id"]
            if transaction_id in records:
                raise ValueError(f"source has duplicate transaction_id at line {index + 1}")
            records[transaction_id] = record
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap-servers", default="localhost:9094")
    parser.add_argument("--topic", default="retail.sales.transactions")
    parser.add_argument("--capture-baseline", type=Path)
    parser.add_argument("--baseline-file", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--expected", type=int)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--producer-stats", type=Path, help="Merge ACK metrics and check delivered = consumed")
    parser.add_argument("--source-input", type=Path, help="Compare every consumed record with first N source JSONL lines")
    args = parser.parse_args()
    if bool(args.capture_baseline) == bool(args.baseline_file):
        parser.error("choose exactly one of --capture-baseline and --baseline-file")
    if args.baseline_file and (not args.run_id or not args.expected or args.expected < 1 or args.timeout <= 0):
        parser.error("probe requires --run-id, positive --expected and --timeout")
    client = consumer(args.bootstrap_servers)
    try:
        if args.capture_baseline:
            result = capture(client, args.topic)
            path = args.capture_baseline
        else:
            baseline = json.loads(args.baseline_file.read_text(encoding="utf-8"))
            if baseline["topic"] != args.topic:
                raise ValueError("baseline topic does not match requested topic")
            source_records = load_source(args.source_input, args.expected) if args.source_input else None
            result = probe(client, baseline, args.run_id, args.expected, args.timeout, source_records)
            if args.producer_stats:
                producer_stats = json.loads(args.producer_stats.read_text(encoding="utf-8"))
                if producer_stats["run_id"] != args.run_id or producer_stats["topic"] != args.topic:
                    raise ValueError("producer stats run_id/topic do not match probe")
                result["producer"] = producer_stats
                if producer_stats["delivered"] != result["consumed"] or producer_stats["test_status"] != "PASS":
                    result["test_status"] = "FAIL"
            path = args.output
        rendered = json.dumps(result, sort_keys=True, indent=2) + "\n"
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0 if result.get("test_status", "PASS") == "PASS" else 1
    except (OSError, RuntimeError, ValueError, KeyError, KafkaException) as exc:
        print(f"consumer probe failed: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())

"""Shared Kafka publishing, contract validation, and measured delivery results."""

from __future__ import annotations

import json
import math
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from confluent_kafka import Producer
from dotenv import load_dotenv
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "data/schema/transaction.schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def settings(bootstrap: str | None, topic: str | None) -> tuple[str, str]:
    load_dotenv(ROOT / ".env", override=False)
    server = bootstrap or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9094")
    name = topic or os.getenv("KAFKA_TOPIC", "retail.sales.transactions")
    if not server.strip() or not name.strip():
        raise ValueError("bootstrap servers and topic must be nonempty")
    return server, name


def check_run_id(value: str) -> str:
    if not RUN_ID.fullmatch(value):
        raise ValueError("run_id must be 1-64 safe letters, digits, _, . or -")
    return value


def check_positive(value: float | int | None, name: str) -> None:
    if value is not None and (not math.isfinite(value) or value <= 0):
        raise ValueError(f"{name} must be positive")


def validate(record: object) -> dict:
    if not isinstance(record, dict):
        raise ValueError("record must be a JSON object")
    errors = sorted(VALIDATOR.iter_errors(record), key=lambda error: tuple(str(x) for x in error.path))
    if errors:
        error = errors[0]
        raise ValueError(f"schema: {'.'.join(map(str, error.path)) or '<root>'}: {error.message}")
    for field in ("event_time", "emitted_at"):
        value = record[field]
        if value is not None:
            try:
                datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError as exc:
                raise ValueError(f"invalid {field}: {value}") from exc
    return record


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def prepare(record: dict, run_id: str) -> tuple[dict, bytes]:
    item = dict(record)
    item["run_id"] = check_run_id(run_id)
    item["emitted_at"] = utc_now()
    validate(item)
    payload = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return item, payload


def write_json(path: Path | None, data: dict) -> None:
    rendered = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


class Publisher:
    def __init__(self, bootstrap: str, topic: str, run_id: str, *, timeout: float = 15.0):
        self.topic = topic
        self.run_id = check_run_id(run_id)
        self.timeout = timeout
        config = {
            "bootstrap.servers": bootstrap,
            "acks": "all",
            "enable.idempotence": True,
            "message.timeout.ms": int(timeout * 1000),
            "socket.timeout.ms": min(int(timeout * 1000), 10000),
            "retries": 3,
        }
        if "localhost" in bootstrap:
            config["broker.address.family"] = "v4"
        self.client = Producer(config)
        self.started = time.monotonic()
        self.attempted = 0
        self.enqueued = 0
        self.delivered = 0
        self.failed = 0
        self.payload_bytes = 0
        self.ack_latencies_ms: list[float] = []
        self.partition_counts: dict[int, int] = {}
        self.source_types: set[str] = set()

    def send(self, record: dict) -> None:
        item, payload = prepare(record, self.run_id)
        key = item["store_id"].encode("utf-8")
        self.attempted += 1
        queued_at = time.monotonic()

        def delivered(error, message) -> None:
            if error is not None:
                self.failed += 1
            else:
                self.delivered += 1
                self.payload_bytes += len(payload)
                partition = message.partition()
                self.partition_counts[partition] = self.partition_counts.get(partition, 0) + 1
                self.ack_latencies_ms.append((time.monotonic() - queued_at) * 1000)

        try:
            self.client.produce(self.topic, key=key, value=payload, on_delivery=delivered)
        except (BufferError, RuntimeError) as exc:
            self.failed += 1
            raise RuntimeError(f"Kafka enqueue failed: {exc}") from exc
        self.enqueued += 1
        self.source_types.add(item["source_type"])
        self.client.poll(0)

    def finish(self) -> dict:
        pending = self.client.flush(self.timeout + 2)
        elapsed = time.monotonic() - self.started
        latencies = sorted(self.ack_latencies_ms)
        p95 = latencies[max(0, (95 * len(latencies) + 99) // 100 - 1)] if latencies else None
        result = {
            "run_id": self.run_id, "source_type": sorted(self.source_types), "topic": self.topic,
            "attempted": self.attempted, "enqueued": self.enqueued,
            "delivered": self.delivered, "failed": self.failed, "pending": pending,
            "payload_bytes": self.payload_bytes,
            "elapsed_seconds": round(elapsed, 6),
            "throughput_events_per_second": round(self.delivered / elapsed, 3) if elapsed else 0,
            "producer_callback_latency_ms_average": round(sum(latencies) / len(latencies), 3) if latencies else None,
            "producer_callback_latency_ms_p95": round(p95, 3) if p95 is not None else None,
            "partition_counts": self.partition_counts,
            "test_status": "PASS" if pending == 0 and self.failed == 0 and self.delivered == self.attempted else "FAIL",
        }
        return result


def pace(started: float, index: int, rate: float) -> None:
    delay = started + index / rate - time.monotonic()
    if delay > 0:
        time.sleep(delay)

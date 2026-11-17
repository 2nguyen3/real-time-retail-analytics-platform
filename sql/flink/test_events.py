"""Build tiny Stage 05 fixtures and inject raw records for negative SQL tests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from confluent_kafka import Producer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from producer.generate_data import rows  # noqa: E402


def build_quality(path: Path) -> None:
    original = (ROOT / "tests/fixtures/quality_cases.jsonl").read_text(encoding="utf-8").splitlines()
    cross_run = json.loads(original[0])
    cross_run["run_id"] = "fixture_002"
    original.append(json.dumps(cross_run, sort_keys=True, separators=(",", ":")))
    original.append("{bad json")
    path.write_text("\n".join(original) + "\n", encoding="utf-8")


def build_window(path: Path, run_id: str) -> None:
    times = ("00:00:10", "00:00:50", "00:01:20", "00:00:30", "00:02:00", "00:03:00", "00:03:20", "00:04:00", "00:04:20")
    amounts = ((2, "1.50000000", "3.00"), (1, "2.00000000", "2.00"),
               (3, "0.50000000", "1.50"), (2, "2.00000000", "4.00"),
               (1, "5.00000000", "5.00"), (2, "3.00000000", "6.00"),
               (1, "1.00000000", "1.00"), (1, "2.00000000", "2.00"),
               (1, "1.00000000", "1.00"))
    with path.open("w", encoding="utf-8") as handle:
        for index, record in enumerate(rows(len(times), 42, run_id)):
            record["store_id"] = "S001"
            record["event_time"] = f"2024-01-01T{times[index]}Z"
            record["quantity"], record["price"], record["line_revenue"] = amounts[index]
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def send_raw(path: Path, bootstrap: str, topic: str, start_line: int, limit: int | None) -> None:
    lines = path.read_bytes().splitlines()[start_line - 1:]
    if limit is not None:
        lines = lines[:limit]
    if not 1 <= len(lines) <= 100 or path.stat().st_size > 100_000:
        raise ValueError("test injection is limited to 1-100 lines and 100 KB")
    stats = {"attempted": 0, "delivered": 0, "failed": 0}
    config = {"bootstrap.servers": bootstrap, "acks": "all", "enable.idempotence": True,
              "message.timeout.ms": 10000}
    if "localhost" in bootstrap:
        config["broker.address.family"] = "v4"
    client = Producer(config)

    def callback(error, message) -> None:
        stats["failed" if error else "delivered"] += 1

    for line in lines:
        try:
            record = json.loads(line)
            key = record.get("store_id", "INVALID") if isinstance(record, dict) else "INVALID"
        except json.JSONDecodeError:
            key = "INVALID"
        client.produce(topic, key=str(key).encode(), value=line, on_delivery=callback)
        stats["attempted"] += 1
        client.poll(0)
    pending = client.flush(12)
    stats["pending"] = pending
    stats["test_status"] = "PASS" if stats["delivered"] == len(lines) and not stats["failed"] and not pending else "FAIL"
    print(json.dumps(stats, indent=2))
    if stats["test_status"] != "PASS":
        raise RuntimeError("fixture delivery did not receive all ACKs")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("quality", "window"):
        command = commands.add_parser(action)
        command.add_argument("--output", type=Path, required=True)
        if action == "window":
            command.add_argument("--run-id", default="stage05_window_01")
    send = commands.add_parser("send")
    send.add_argument("--input", type=Path, required=True)
    send.add_argument("--bootstrap-servers", default="localhost:9094")
    send.add_argument("--topic", default="retail.sales.transactions")
    send.add_argument("--start-line", type=int, default=1)
    send.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.action == "send":
        if args.start_line < 1 or (args.limit is not None and args.limit < 1):
            parser.error("start-line and limit must be positive")
        send_raw(args.input, args.bootstrap_servers, args.topic, args.start_line, args.limit)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.action == "quality":
            build_quality(args.output)
        else:
            build_window(args.output, args.run_id)
        print(args.output)


if __name__ == "__main__":
    main()

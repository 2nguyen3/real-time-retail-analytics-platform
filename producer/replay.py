"""Validate a JSONL source and replay transaction lines to Kafka."""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from producer.kafka_common import Publisher, check_positive, check_run_id, pace, prepare, settings, validate, write_json


def read_records(path: Path, limit: int | None):
    with path.open(encoding="utf-8") as handle:
        count = 0
        for line_number, line in enumerate(handle, 1):
            if limit is not None and count >= limit:
                break
            try:
                record = json.loads(line)
                validate(record)
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
            count += 1
            yield record


def preflight(path: Path, limit: int | None, run_id: str) -> int:
    if not path.is_file():
        raise ValueError(f"input does not exist: {path}")
    count = 0
    with tempfile.TemporaryDirectory(prefix="retail-replay-") as directory:
        with sqlite3.connect(str(Path(directory) / "ids.sqlite3")) as db:
            db.execute("CREATE TABLE seen (transaction_id TEXT PRIMARY KEY)")
            for record in read_records(path, limit):
                prepare(record, run_id)
                try:
                    db.execute("INSERT INTO seen VALUES (?)", (record["transaction_id"],))
                except sqlite3.IntegrityError as exc:
                    raise ValueError(f"duplicate transaction_id at line {count + 1}") from exc
                count += 1
    if count == 0:
        raise ValueError("input contains no messages")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--rate", type=float, default=0, help="Events per second; 0 sends as fast as possible")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--bootstrap-servers")
    parser.add_argument("--topic")
    parser.add_argument("--stats-output", type=Path)
    parser.add_argument("--delivery-timeout", type=float, default=15.0)
    args = parser.parse_args()
    try:
        if not math.isfinite(args.rate) or args.rate < 0:
            raise ValueError("rate must be nonnegative")
        check_positive(args.limit, "limit")
        check_positive(args.delivery_timeout, "delivery-timeout")
        check_run_id(args.run_id)
        count = preflight(args.input, args.limit, args.run_id)
        bootstrap, topic = settings(args.bootstrap_servers, args.topic)
        publisher = Publisher(bootstrap, topic, args.run_id, timeout=args.delivery_timeout)
        started = time.monotonic()
        interrupted = False
        try:
            for index, record in enumerate(read_records(args.input, count)):
                if args.rate:
                    pace(started, index, args.rate)
                publisher.send(record)
        except KeyboardInterrupt:
            interrupted = True
        finally:
            result = publisher.finish()
            if interrupted:
                result["test_status"] = "INTERRUPTED"
            write_json(args.stats_output, result)
        return 0 if result["test_status"] == "PASS" else 1
    except (OSError, ValueError, RuntimeError, KeyboardInterrupt) as exc:
        print(f"replay failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

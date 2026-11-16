"""Generate synthetic transaction lines and publish them to local Kafka."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from producer.generate_data import rows
from producer.kafka_common import Publisher, check_positive, check_run_id, pace, settings, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rate", type=float, default=1.0, help="Events per second")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--duration", type=float, help="Maximum sending seconds")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--bootstrap-servers")
    parser.add_argument("--topic")
    parser.add_argument("--stats-output", type=Path)
    parser.add_argument("--delivery-timeout", type=float, default=15.0)
    args = parser.parse_args()
    try:
        check_positive(args.rate, "rate")
        check_positive(args.limit, "limit")
        check_positive(args.duration, "duration")
        check_positive(args.delivery_timeout, "delivery-timeout")
        check_run_id(args.run_id)
        if args.limit is None and args.duration is None:
            raise ValueError("--limit or --duration is required")
        if args.seed < 0:
            raise ValueError("seed must be nonnegative")
        bootstrap, topic = settings(args.bootstrap_servers, args.topic)
        maximum = args.limit or max(1, int(args.rate * args.duration) + 2)
        publisher = Publisher(bootstrap, topic, args.run_id, timeout=args.delivery_timeout)
        started = time.monotonic()
        interrupted = False
        try:
            for index, record in enumerate(rows(maximum, args.seed, args.run_id)):
                if args.duration is not None and time.monotonic() - started >= args.duration:
                    break
                pace(started, index, args.rate)
                if args.duration is not None and time.monotonic() - started >= args.duration:
                    break
                publisher.send(record)
        except KeyboardInterrupt:
            interrupted = True
        finally:
            result = publisher.finish()
            if interrupted:
                result["test_status"] = "INTERRUPTED"
            write_json(args.stats_output, result)
        return 0 if result["test_status"] == "PASS" else 1
    except (ValueError, RuntimeError, KeyboardInterrupt) as exc:
        print(f"live producer failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Generate a small, reproducible synthetic retail JSONL fixture.

This module does not publish to Kafka. audit_data.py independently reads the
written file and produces the manifest used by later ETL checks.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path


SCHEMA_VERSION = "1.0.0"
SOURCE_DATASET = "stage02-synthetic-v1"
BASE_TIME = datetime(2024, 1, 1, tzinfo=timezone.utc)
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def rows(count: int, seed: int, run_id: str):
    """Yield lines without retaining the generated dataset in memory."""
    rng = random.Random(seed)
    for index in range(count):
        basket_number = index // 3 + 1
        product_number = rng.randint(1, 80)
        quantity = rng.randint(1, 5)
        cents = rng.randint(50, 20_000)
        price = Decimal(cents) / 100
        event_time = BASE_TIME + timedelta(minutes=basket_number - 1)
        yield {
            "schema_version": SCHEMA_VERSION,
            "transaction_id": f"{run_id}:line:{index + 1:08d}",
            "basket_id": f"{run_id}:basket:{basket_number:06d}",
            "product_id": f"P{product_number:05d}",
            "customer_id": f"C{(basket_number - 1) % 250 + 1:05d}",
            "store_id": f"S{(basket_number - 1) % 5 + 1:03d}",
            "category_id": f"CAT{(product_number - 1) // 10 + 1:02d}",
            "quantity": quantity,
            "price": f"{price:.8f}",
            "line_revenue": f"{price * quantity:.2f}",
            "event_time": event_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event_time_basis": "synthetic",
            "emitted_at": None,
            "run_id": run_id,
            "source_type": "synthetic",
            "source_dataset": SOURCE_DATASET,
            "currency": "USD",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--run-id", default="stage02_demo")
    parser.add_argument("--output", type=Path, required=True, help="UTF-8 JSONL path")
    parser.add_argument("--manifest", type=Path, help="Defaults to <output>.manifest.json")
    args = parser.parse_args()

    if not 1 <= args.count <= 100_000:
        parser.error("--count must be between 1 and 100000 in Stage 02")
    if args.seed < 0:
        parser.error("--seed must be nonnegative")
    if not RUN_ID_PATTERN.fullmatch(args.run_id):
        parser.error("--run-id must be 1-64 safe letters, digits, _, . or -")
    if args.output.suffix != ".jsonl":
        parser.error("--output must end in .jsonl")

    output = args.output.resolve()
    manifest = (args.manifest or Path(str(args.output) + ".manifest.json")).resolve()
    if output == manifest:
        parser.error("output and manifest paths must differ")
    if output.exists() or manifest.exists():
        parser.error("output or manifest already exists; remove or choose a new name explicitly")

    output.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        for record in rows(args.count, args.seed, args.run_id):
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            handle.write("\n")

    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("audit_data.py")),
            "--input",
            str(output),
            "--manifest",
            str(manifest),
            "--seed",
            str(args.seed),
            "--run-id",
            args.run_id,
            "--generated-at",
            generated_at,
        ],
        check=True,
    )
    print(f"Generated {args.count} synthetic messages in {output}")
    print(f"Independent audit written to {manifest}")


if __name__ == "__main__":
    main()

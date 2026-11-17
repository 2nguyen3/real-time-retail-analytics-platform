"""Compare source JSONL with all three PostgreSQL aggregate tables for one run."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


TABLE_KEYS = {
    "sales_by_store": ("store_id", "currency"),
    "sales_by_store_product": ("store_id", "product_id", "currency"),
    "sales_by_store_minute": ("store_id", "window_start", "currency"),
}


def expected(path: Path, limit: int | None, run_id: str, replayed: bool) -> tuple[dict, dict]:
    values = {table: defaultdict(lambda: [0, 0, Decimal("0.00")]) for table in TABLE_KEYS}
    seen: set[tuple[str, str]] = set()
    counts = {"raw": 0, "valid": 0, "invalid": 0, "duplicate": 0}
    with path.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if limit is not None and index >= limit:
                break
            counts["raw"] += 1
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("not an object")
                if row.get("run_id") != run_id and not replayed:
                    continue
                if not row.get("transaction_id") or not row.get("store_id") or not row.get("product_id"):
                    raise ValueError("missing identifier")
                quantity = row["quantity"]
                revenue = Decimal(row["line_revenue"])
                if type(quantity) is not int or quantity <= 0 or Decimal(row["price"]) < 0 or revenue < 0:
                    raise ValueError("invalid amount")
                event = datetime.strptime(row["event_time"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                currency = row["currency"]
                if not re.fullmatch(r"[A-Z]{3}", currency):
                    raise ValueError("invalid currency")
            except (json.JSONDecodeError, KeyError, TypeError, ValueError, ArithmeticError):
                counts["invalid"] += 1
                continue
            key = (run_id, row["transaction_id"])
            if key in seen:
                counts["duplicate"] += 1
                continue
            seen.add(key)
            counts["valid"] += 1
            minute = event.replace(second=0, microsecond=0).isoformat()
            for table, group in (
                ("sales_by_store", (row["store_id"], currency)),
                ("sales_by_store_product", (row["store_id"], row["product_id"], currency)),
                ("sales_by_store_minute", (row["store_id"], minute, currency)),
            ):
                aggregate = values[table][group]
                aggregate[0] += 1
                aggregate[1] += quantity
                aggregate[2] += revenue
    return values, counts


def actual(table: str, run_id: str) -> dict:
    fields = ", ".join(TABLE_KEYS[table])
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", run_id):
        raise ValueError("invalid run ID")
    query = (f"COPY (SELECT {fields}, transaction_count, total_quantity, total_revenue "
             f"FROM {table} WHERE run_id = '{run_id}') TO STDOUT WITH (FORMAT csv)")
    result = subprocess.run(
        ["docker", "exec", "retail-local-postgres-1", "sh", "-c",
         'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "$1"',
         "sh", query], capture_output=True, check=True, text=True,
    )
    output = {}
    key_width = len(TABLE_KEYS[table])
    for row in csv.reader(io.StringIO(result.stdout)):
        key = tuple(row[:key_width])
        if table == "sales_by_store_minute":
            key = (key[0], datetime.fromisoformat(key[1].replace(" ", "T")).isoformat(), key[2])
        output[key] = [int(row[-3]), int(row[-2]), Decimal(row[-1])]
    return output


def reconcile(path: Path, limit: int | None, run_id: str, replayed: bool,
              closed_before: str | None = None) -> tuple[list[dict], dict]:
    wanted, counts = expected(path, limit, run_id, replayed)
    results = []
    for table in TABLE_KEYS:
        found = actual(table, run_id)
        if table == "sales_by_store_minute" and closed_before is not None:
            cutoff_time = datetime.fromisoformat(closed_before)
            if cutoff_time.tzinfo is None:
                raise ValueError("--closed-before requires an explicit timezone")
            cutoff = cutoff_time.astimezone(timezone.utc).isoformat()
            wanted[table] = {key: value for key, value in wanted[table].items() if key[1] < cutoff}
            found = {key: value for key, value in found.items() if key[1] < cutoff}
        all_keys = sorted(set(wanted[table]) | set(found))
        mismatch = sum(wanted[table].get(key) != found.get(key) for key in all_keys)
        results.append({
            "run_id": run_id, "table": table,
            "expected_rows": len(wanted[table]), "actual_rows": len(found),
            "expected_count": sum(x[0] for x in wanted[table].values()),
            "actual_count": sum(x[0] for x in found.values()),
            "expected_quantity": sum(x[1] for x in wanted[table].values()),
            "actual_quantity": sum(x[1] for x in found.values()),
            "expected_revenue": str(sum((x[2] for x in wanted[table].values()), Decimal("0.00"))),
            "actual_revenue": str(sum((x[2] for x in found.values()), Decimal("0.00"))),
            "key_mismatches": mismatch, "status": "PASS" if mismatch == 0 else "FAIL",
        })
    return results, counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--replayed", action="store_true", help="Producer replaced the source run_id during replay")
    parser.add_argument("--closed-before", help="Only compare minute windows starting before this UTC ISO timestamp")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows, counts = reconcile(args.input, args.limit, args.run_id, args.replayed, args.closed_before)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps({"source": counts, "tables": rows}, ensure_ascii=False, indent=2))
    return 0 if all(row["status"] == "PASS" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())

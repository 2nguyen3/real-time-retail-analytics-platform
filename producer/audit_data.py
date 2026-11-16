"""Independently validate retail JSONL and calculate expected ETL results.

Invalid records are counted first and do not reserve transaction IDs. A valid
record whose ID was already accepted is a duplicate. Only accepted records
contribute to quantity and revenue.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


CENT = Decimal("0.01")
PRICE = re.compile(r"^(0|[1-9][0-9]{0,9})\.[0-9]{8}$")
AMOUNT = re.compile(r"^(0|[1-9][0-9]{0,11})\.[0-9]{2}$")
UTC_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
TEXT_FIELDS = ("transaction_id", "product_id", "store_id", "source_dataset")
NULLABLE_TEXT_FIELDS = ("basket_id", "category_id", "customer_id")


def utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not UTC_TIME.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return True


def invalid_reason(record: object, required: set[str], expected_run_id: str | None, allowed: set[str] | None = None) -> str | None:
    if not isinstance(record, dict):
        return "not_object"
    if required - record.keys():
        return "missing_field"
    if record.keys() - (allowed or required):
        return "extra_field"
    if record["schema_version"] != "1.0.0":
        return "schema_version"
    for field in TEXT_FIELDS:
        value = record[field]
        if not isinstance(value, str) or not value or len(value) > 128:
            return field
    for field in NULLABLE_TEXT_FIELDS:
        value = record[field]
        if value is not None and (not isinstance(value, str) or not value or len(value) > 128):
            return field
    if "store_region" in record:
        region = record["store_region"]
        if region is not None and (not isinstance(region, str) or not region or len(region) > 128):
            return "store_region"
    if not isinstance(record["run_id"], str) or not RUN_ID.fullmatch(record["run_id"]):
        return "run_id"
    if expected_run_id is not None and record["run_id"] != expected_run_id:
        return "run_id_mismatch"
    if record["source_type"] not in ("original", "transformed", "synthetic"):
        return "source_type"
    if record["event_time_basis"] not in ("source_utc", "assumed_timezone", "synthetic"):
        return "event_time_basis"
    if "event_time_precision" in record and record["event_time_precision"] not in ("second", "hour"):
        return "event_time_precision"
    if record["source_type"] == "synthetic" and record["event_time_basis"] != "synthetic":
        return "time_provenance"
    if not isinstance(record["currency"], str) or not re.fullmatch(r"[A-Z]{3}", record["currency"]):
        return "currency"
    quantity = record["quantity"]
    if type(quantity) is not int or not 1 <= quantity <= 100_000:
        return "quantity"
    if not isinstance(record["price"], str) or not PRICE.fullmatch(record["price"]):
        return "price"
    if not isinstance(record["line_revenue"], str) or not AMOUNT.fullmatch(record["line_revenue"]):
        return "line_revenue"
    if not utc_timestamp(record["event_time"]):
        return "event_time"
    if record["emitted_at"] is not None and not utc_timestamp(record["emitted_at"]):
        return "emitted_at"
    try:
        calculated = (Decimal(record["price"]) * quantity).quantize(CENT, rounding=ROUND_HALF_UP)
        stated = Decimal(record["line_revenue"])
    except InvalidOperation:
        return "money"
    if calculated != stated:
        return "revenue_mismatch"
    return None


def summarize(path: Path, *, seed: int | None = None, run_id: str | None = None, generated_at: str | None = None) -> dict:
    schema_path = Path(__file__).resolve().parents[1] / "data/schema/transaction.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    required = set(schema["required"])
    allowed = set(schema["properties"])
    counts = Counter()
    reasons = Counter()
    seen_accepted: set[str] = set()
    seen_any_id: set[str] = set()
    grouped: dict[str, dict[str, list]] = {key: defaultdict(lambda: [0, Decimal("0.00")]) for key in ("store", "product", "hour")}
    sha = hashlib.sha256()
    byte_count = 0
    payload_bytes = 0
    sources: set[str] = set()
    currencies: set[str] = set()
    run_ids: set[str] = set()
    versions: set[str] = set()

    with path.open("rb") as handle:
        for raw_line in handle:
            sha.update(raw_line)
            byte_count += len(raw_line)
            payload = raw_line.rstrip(b"\r\n")
            payload_bytes += len(payload)
            counts["message_count"] += 1
            try:
                record = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                counts["invalid_count"] += 1
                reasons["invalid_json"] += 1
                continue
            if isinstance(record, dict) and isinstance(record.get("transaction_id"), str):
                seen_any_id.add(record["transaction_id"])
            reason = invalid_reason(record, required, run_id, allowed)
            if reason is not None:
                counts["invalid_count"] += 1
                reasons[reason] += 1
                continue
            if record["transaction_id"] in seen_accepted:
                counts["duplicate_count"] += 1
                continue
            seen_accepted.add(record["transaction_id"])
            counts["valid_count"] += 1
            quantity = record["quantity"]
            revenue = Decimal(record["line_revenue"])
            counts["expected_quantity"] += quantity
            counts["expected_revenue_cents"] += int(revenue * 100)
            sources.add(record["source_type"])
            currencies.add(record["currency"])
            run_ids.add(record["run_id"])
            versions.add(record["schema_version"])
            for group, key in (
                ("store", record["store_id"]),
                ("product", record["product_id"]),
                ("hour", record["event_time"][:13] + ":00:00Z"),
            ):
                grouped[group][key][0] += quantity
                grouped[group][key][1] += revenue

    if byte_count != path.stat().st_size:
        raise RuntimeError("file changed while being audited")

    def as_totals(values: dict[str, list]) -> dict[str, dict]:
        return {
            key: {"quantity": values[key][0], "revenue": f"{values[key][1]:.2f}"}
            for key in sorted(values)
        }

    repository_root = Path(__file__).resolve().parents[1]
    try:
        input_file = path.resolve().relative_to(repository_root).as_posix()
    except ValueError:
        input_file = path.as_posix()
    return {
        "manifest_version": "1.0.0",
        "schema_version": sorted(versions),
        "run_id": run_id or (next(iter(run_ids)) if len(run_ids) == 1 else None),
        "seed": seed,
        "source_types": sorted(sources),
        "currencies": sorted(currencies),
        "input_file": input_file,
        "generated_at_utc": generated_at,
        "file_modified_at_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "raw_file_bytes": byte_count,
        "json_payload_bytes": payload_bytes,
        "sha256": sha.hexdigest(),
        "message_count": counts["message_count"],
        "unique_transaction_id_count": len(seen_any_id),
        "valid_count": counts["valid_count"],
        "invalid_count": counts["invalid_count"],
        "duplicate_count": counts["duplicate_count"],
        "invalid_reasons": dict(sorted(reasons.items())),
        "expected_quantity": counts["expected_quantity"],
        "expected_revenue": f"{Decimal(counts['expected_revenue_cents']) / 100:.2f}",
        "expected_by_store": as_totals(grouped["store"]),
        "expected_by_product": as_totals(grouped["product"]),
        "expected_by_hour_utc": as_totals(grouped["hour"]),
        "audited_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "policy": "invalid-first; only accepted transaction_id duplicates; no late-event filtering",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--run-id")
    parser.add_argument("--generated-at", help="Actual UTC time when the generator started writing the file")
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error("input file does not exist")
    if args.manifest.exists():
        parser.error("manifest already exists; choose a new path")
    if args.generated_at is not None and not utc_timestamp(args.generated_at):
        parser.error("--generated-at must be a valid UTC timestamp ending in Z")
    result = summarize(args.input, seed=args.seed, run_id=args.run_id, generated_at=args.generated_at)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    print(
        f"Audited {result['message_count']} messages: "
        f"valid={result['valid_count']} invalid={result['invalid_count']} "
        f"duplicate={result['duplicate_count']}"
    )


if __name__ == "__main__":
    main()

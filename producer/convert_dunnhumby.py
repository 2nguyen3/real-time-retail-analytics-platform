"""Convert dunnhumby Sort-of-Real weekly CSVs to transaction JSONL.

The source sample obscures basket IDs and omits some customer IDs. This tool
preserves those gaps as null and never assigns an invented basket/customer ID.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from zipfile import ZipFile


SOURCE_DATASET = "dunnhumby-sort-of-real-sample-2k"
CENT = Decimal("0.01")
EIGHT_DP = Decimal("0.00000001")
REQUIRED_COLUMNS = {
    "SHOP_DATE", "SHOP_HOUR", "QUANTITY", "SPEND", "PROD_CODE",
    "PROD_CODE_40", "CUST_CODE", "BASKET_ID", "STORE_CODE", "STORE_REGION",
}
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
OFFSET = re.compile(r"^([+-])(\d{2}):(\d{2})$")


def source_offset(text: str) -> timezone:
    match = OFFSET.fullmatch(text)
    if not match:
        raise ValueError("offset must be +HH:MM or -HH:MM")
    sign, hours, minutes = match.groups()
    hours, minutes = int(hours), int(minutes)
    if hours > 14 or minutes > 59 or (hours == 14 and minutes):
        raise ValueError("UTC offset exceeds 14 hours")
    delta = timedelta(hours=hours, minutes=minutes)
    return timezone(delta if sign == "+" else -delta)


def convert_row(row: dict[str, str], *, zip_digest: str, entry: str, line_number: int,
                run_id: str, offset: timezone, currency: str = "XXX") -> dict:
    if not REQUIRED_COLUMNS <= row.keys():
        raise ValueError(f"missing source columns: {sorted(REQUIRED_COLUMNS - row.keys())}")
    try:
        quantity = int(row["QUANTITY"])
        spend = Decimal(row["SPEND"])
    except (ValueError, InvalidOperation) as exc:
        raise ValueError("invalid quantity or spend") from exc
    if not 1 <= quantity <= 100_000 or not spend.is_finite() or spend < 0 or spend != spend.quantize(CENT):
        raise ValueError("quantity/spend outside contract")
    try:
        local_hour = datetime.strptime(row["SHOP_DATE"], "%Y%m%d").replace(hour=int(row["SHOP_HOUR"]), tzinfo=offset)
    except ValueError as exc:
        raise ValueError("invalid source date/hour") from exc
    if not row["PROD_CODE"] or not row["STORE_CODE"]:
        raise ValueError("missing source product/store")
    price = (spend / quantity).quantize(EIGHT_DP, rounding=ROUND_HALF_UP)
    if (price * quantity).quantize(CENT, rounding=ROUND_HALF_UP) != spend:
        raise ValueError("unit price cannot reproduce source spend at 8 decimals")
    basket = row["BASKET_ID"].strip()
    return {
        "schema_version": "1.0.0",
        "transaction_id": f"sor:{zip_digest}:{Path(entry).stem}:{line_number:08d}",
        "basket_id": basket if basket.isdecimal() else None,
        "product_id": row["PROD_CODE"],
        "customer_id": row["CUST_CODE"].strip() or None,
        "store_id": row["STORE_CODE"],
        "store_region": row["STORE_REGION"].strip() or None,
        "category_id": row["PROD_CODE_40"].strip() or None,
        "quantity": quantity,
        "price": f"{price:.8f}",
        "line_revenue": f"{spend:.2f}",
        "event_time": local_hour.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_time_basis": "assumed_timezone",
        "event_time_precision": "hour",
        "emitted_at": None,
        "run_id": run_id,
        "source_type": "transformed",
        "source_dataset": SOURCE_DATASET,
        "currency": currency,
    }


def convert_zip(source: Path, output: Path, *, run_id: str, offset: timezone, currency: str = "XXX") -> dict:
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("invalid run_id")
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("currency must be a three-letter ISO 4217 code; use XXX if unverified")
    if output.exists():
        raise FileExistsError(output)
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    counts = {"rows": 0, "missing_customer": 0, "unusable_basket_id": 0}
    with ZipFile(source) as archive:
        entries = sorted(name for name in archive.namelist() if Path(name).name.startswith("transactions_") and name.endswith(".csv"))
        if not entries:
            raise ValueError("ZIP has no weekly transaction CSV")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8", newline="\n") as target:
            for entry in entries:
                with io.TextIOWrapper(archive.open(entry), encoding="utf-8-sig", newline="") as stream:
                    reader = csv.DictReader(stream)
                    if not REQUIRED_COLUMNS <= set(reader.fieldnames or []):
                        raise ValueError(f"unexpected header in {entry}")
                    for line_number, row in enumerate(reader, start=2):
                        converted = convert_row(row, zip_digest=digest.hexdigest(), entry=entry,
                                                line_number=line_number, run_id=run_id,
                                                offset=offset, currency=currency)
                        target.write(json.dumps(converted, sort_keys=True, separators=(",", ":")) + "\n")
                        counts["rows"] += 1
                        counts["missing_customer"] += converted["customer_id"] is None
                        counts["unusable_basket_id"] += converted["basket_id"] is None
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Official dunnhumby sample ZIP, kept outside Git")
    parser.add_argument("--output", type=Path, required=True, help="JSONL output; must not already exist")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-utc-offset", required=True, help="Explicit assumed source offset, e.g. +00:00; source timezone is undocumented")
    parser.add_argument("--currency", default="XXX", help="Explicit verified ISO code, or XXX when source unit is unknown")
    args = parser.parse_args()
    if not args.input.is_file() or args.input.stat().st_size > 10_000_000:
        parser.error("Stage 02 converter accepts an existing ZIP up to 10 MB")
    try:
        result = convert_zip(args.input, args.output, run_id=args.run_id,
                             offset=source_offset(args.source_utc_offset), currency=args.currency)
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

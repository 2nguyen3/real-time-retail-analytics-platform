"""R11: measure reading from Azure Blob Storage into an application, plain CSV vs gzip.

Runs on an Azure VM whose managed identity may read the storage account (no keys, no
secrets; the token is never printed). The clock starts before the first download request
and stops after the last CSV row has been parsed. Nothing is written to disk on the way.
Both variants must give the same row count and quantity sum.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

TOKEN_URL = ("http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01"
             "&resource=https%3A%2F%2Fstorage.azure.com%2F")
FIELDS = ["label", "variant", "round", "started_utc", "files", "stored_bytes", "transferred_bytes",
          "csv_bytes", "rows", "quantity_sum", "total_s", "first_byte_ms", "cpu_s", "rows_per_s",
          "csv_mb_per_s", "status"]


def token() -> str:
    with urlopen(Request(TOKEN_URL, headers={"Metadata": "true"}), timeout=20) as response:
        return json.load(response)["access_token"]


class Counted(io.RawIOBase):
    """Counts the bytes taken from an underlying binary stream."""

    def __init__(self, source) -> None:
        self.source, self.total = source, 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        data = self.source.read(len(buffer))
        buffer[:len(data)] = data
        self.total += len(data)
        return len(data)


def read_blob(url: str, bearer: str, compressed: bool) -> dict:
    request = Request(url, headers={"Authorization": f"Bearer {bearer}", "x-ms-version": "2021-08-06"})
    sent = time.perf_counter()
    with urlopen(request, timeout=300) as response:
        first_byte_ms = (time.perf_counter() - sent) * 1000
        stored = int(response.headers["Content-Length"])
        wire = Counted(response)
        stream = io.BufferedReader(wire, 1 << 20)
        content = Counted(gzip.GzipFile(fileobj=stream) if compressed else stream)
        text = io.TextIOWrapper(io.BufferedReader(content, 1 << 20), encoding="utf-8-sig", newline="")
        reader = csv.reader(text)
        column = next(reader).index("QUANTITY")
        rows = quantity = 0
        for row in reader:
            rows += 1
            quantity += int(row[column])
    if wire.total != stored:
        raise RuntimeError(f"transferred {wire.total} of {stored} bytes")
    return {"stored": stored, "transferred": wire.total, "csv": content.total, "rows": rows,
            "quantity": quantity, "first_byte_ms": first_byte_ms}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True)
    parser.add_argument("--container", default="benchmark-data")
    parser.add_argument("--plain-prefix", default="dunnhumby/raw")
    parser.add_argument("--gzip-prefix", default="dunnhumby/gzip")
    parser.add_argument("--files", nargs="+", required=True, help="CSV file names, without .gz")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--label", default="dry-run", choices=("dry-run", "official"))
    parser.add_argument("--out", type=Path, required=True, help="result CSV")
    args = parser.parse_args()
    base = f"https://{args.account}.blob.core.windows.net/{args.container}"
    bearer = token()
    results: dict[str, list[dict]] = {"plain": [], "gzip": []}
    reference = None
    args.out.parent.mkdir(parents=True, exist_ok=True)

    for number in range(0, args.rounds + 1):  # round 0 warms up and is not recorded
        for variant in ("plain", "gzip"):
            prefix, suffix = (args.plain_prefix, "") if variant == "plain" else (args.gzip_prefix, ".gz")
            started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            cpu, start = time.process_time(), time.perf_counter()
            parts = [read_blob(f"{base}/{prefix}/{quote(name)}{suffix}", bearer, variant == "gzip")
                     for name in args.files]
            elapsed, cpu = time.perf_counter() - start, time.process_time() - cpu
            totals = {key: sum(p[key] for p in parts)
                      for key in ("stored", "transferred", "csv", "rows", "quantity")}
            signature = (totals["rows"], totals["quantity"], totals["csv"])
            reference = reference or signature
            status = "PASS" if signature == reference else "FAIL"
            if number == 0:
                print(f"warm-up {variant}: {elapsed:.1f} s", flush=True)
                continue
            row = {"label": args.label, "variant": variant, "round": number, "started_utc": started,
                   "files": len(parts), "stored_bytes": totals["stored"],
                   "transferred_bytes": totals["transferred"], "csv_bytes": totals["csv"],
                   "rows": totals["rows"], "quantity_sum": totals["quantity"],
                   "total_s": round(elapsed, 2),
                   "first_byte_ms": round(statistics.median(p["first_byte_ms"] for p in parts), 1),
                   "cpu_s": round(cpu, 2), "rows_per_s": round(totals["rows"] / elapsed),
                   "csv_mb_per_s": round(totals["csv"] / 1e6 / elapsed, 2), "status": status}
            new = not args.out.exists()
            with args.out.open("a", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                if new:
                    writer.writeheader()
                writer.writerow(row)
            results[variant].append(row)
            print(f"round {number} {variant}: {status} {row['total_s']} s | stored "
                  f"{row['stored_bytes']} B | rows {row['rows']} | {row['rows_per_s']} rows/s | "
                  f"cpu {row['cpu_s']} s", flush=True)
    for variant, rows_ in results.items():
        print(f"{variant}: median total {statistics.median(r['total_s'] for r in rows_)} s, "
              f"median cpu {statistics.median(r['cpu_s'] for r in rows_)} s")
    return 0 if all(r["status"] == "PASS" for v in results.values() for r in v) else 1


if __name__ == "__main__":
    raise SystemExit(main())

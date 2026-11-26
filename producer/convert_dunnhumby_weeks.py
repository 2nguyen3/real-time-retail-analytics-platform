"""Convert extracted Sort-of-Real weekly CSVs into time-ordered JSONL chunks (Stage 10).

The source files are not ordered by time, so Flink would drop most rows as late data.
Rows are therefore ordered by (SHOP_DATE, SHOP_HOUR) and then by their position in the
source file. No source value is changed. Ordering uses one temporary file per hour, so
memory use stays small. Row conversion is the Stage 02 rule set (convert_dunnhumby.py).

Output: <prefix>_cNN.jsonl (each with its own run_id and audit manifest) and
<prefix>_summary.json with the raw CSV bytes and SHA-256 of every week that was read.
The data is dunnhumby simulated data: keep it outside Git.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from producer.convert_dunnhumby import REQUIRED_COLUMNS, convert_row, source_offset  # noqa: E402

SOURCE_DATASET = "dunnhumby-sort-of-real-weeks"
GIB = 1024 ** 3
WEEK_FILE = re.compile(r"^transactions_(\d{6})\.csv$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def ordered_lines(path: Path, digest: str, offset, work: Path, currency: str = "XXX"):
    """Yield (hour_key, record) for one weekly file in (date, hour, source line) order."""
    handles, counts = {}, {}
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not REQUIRED_COLUMNS <= set(reader.fieldnames or []):
                raise ValueError(f"unexpected header in {path.name}")
            for line_number, row in enumerate(reader, start=2):
                try:
                    record = convert_row(row, zip_digest=digest, entry=path.name, line_number=line_number,
                                         run_id="pending", offset=offset, currency=currency)
                except ValueError as exc:
                    raise ValueError(f"{path.name}:{line_number}: {exc}") from exc
                record["source_dataset"] = SOURCE_DATASET
                key = f"{row['SHOP_DATE']}{int(row['SHOP_HOUR']):02d}"
                if key not in handles:
                    handles[key] = (work / f"{key}.jsonl").open("w", encoding="utf-8", newline="\n")
                    counts[key] = 0
                handles[key].write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                counts[key] += 1
    finally:
        for handle in handles.values():
            handle.close()
    for key in sorted(handles):
        part = work / f"{key}.jsonl"
        with part.open(encoding="utf-8") as handle:
            for line in handle:
                yield key, json.loads(line)
        part.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True, help="folder with transactions_YYYYWW.csv")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--prefix", default="sor10", help="run_id prefix; chunk n is <prefix>_c<nn>")
    parser.add_argument("--rows-per-chunk", type=int, default=1_000_000)
    parser.add_argument("--max-chunks", type=int, default=0, help="stop after N chunks (trial runs); 0 = all")
    parser.add_argument("--source-utc-offset", required=True,
                        help="assumed source offset, e.g. +00:00; the source timezone is undocumented")
    parser.add_argument("--currency", default="XXX",
                        help="ISO code written to every row; XXX = unverified. Any other value is an assumption")
    parser.add_argument("--skip-audit", action="store_true")
    args = parser.parse_args()
    if args.rows_per_chunk < 1 or args.max_chunks < 0:
        parser.error("--rows-per-chunk must be positive and --max-chunks not negative")
    offset = source_offset(args.source_utc_offset)
    if not re.fullmatch(r"[A-Z]{3}", args.currency):
        parser.error("--currency must be a three-letter code")
    files = sorted(p for p in args.input_dir.iterdir() if WEEK_FILE.match(p.name))
    if not files:
        parser.error("no transactions_YYYYWW.csv in --input-dir")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.out_dir / f"{args.prefix}_summary.json"
    if summary_path.exists() or any(args.out_dir.glob(f"{args.prefix}_c*.jsonl")):
        parser.error("output for this --prefix already exists; choose another --out-dir/--prefix")

    chunks, weeks = [], []
    state = {"target": None, "path": None, "rows": 0, "number": 0, "first": None, "last": None}
    previous_key = ""
    started = time.monotonic()

    def close_chunk() -> None:
        state["target"].close()
        run_id, output = state["path"].stem, state["path"].resolve()
        item = {"run_id": run_id, "file": output.name, "rows": state["rows"], "bytes": output.stat().st_size,
                "first_hour": state["first"], "last_hour": state["last"]}
        if not args.skip_audit:
            subprocess.run([sys.executable, str(Path(__file__).with_name("audit_data.py")),
                            "--input", str(output), "--manifest", str(output) + ".manifest.json",
                            "--seed", "0", "--run-id", run_id,
                            "--generated-at", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")],
                           check=True)
        chunks.append(item)
        print(f"{run_id}: {item['rows']} rows, {item['bytes']} bytes, hours {item['first_hour']}-"
              f"{item['last_hour']}", flush=True)
        state["target"] = None

    full = False
    with tempfile.TemporaryDirectory(prefix="sor-order-", dir=args.out_dir) as directory:
        for path in files:
            if full:
                break
            digest = sha256(path)
            weeks.append({"file": path.name, "csv_bytes": path.stat().st_size, "sha256": digest,
                          "rows_used": 0})
            lines = ordered_lines(path, digest, offset, Path(directory), args.currency)
            for key, record in lines:
                if key < previous_key:
                    raise ValueError(f"{path.name} starts before the previous week ends; weeks overlap")
                previous_key = key
                if state["target"] is None:
                    state["number"] += 1
                    state.update(path=args.out_dir / f"{args.prefix}_c{state['number']:02d}.jsonl",
                                 rows=0, first=key)
                    state["target"] = state["path"].open("x", encoding="utf-8", newline="\n")
                record["run_id"] = state["path"].stem
                state["target"].write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
                state["rows"] += 1
                state["last"] = key
                weeks[-1]["rows_used"] += 1
                if state["rows"] == args.rows_per_chunk:
                    close_chunk()
                    if args.max_chunks and state["number"] >= args.max_chunks:
                        full = True
                        break
            lines.close()
            for leftover in Path(directory).glob("*.jsonl"):
                leftover.unlink()
        if state["target"] is not None:
            close_chunk()

    total_rows = sum(c["rows"] for c in chunks)
    raw_bytes = sum(w["csv_bytes"] for w in weeks)
    complete = not full and len(weeks) == len(files)
    result = {"source_type": "transformed", "source_dataset": SOURCE_DATASET,
              "assumed_utc_offset": args.source_utc_offset, "assumed_currency": args.currency, "ordering": "SHOP_DATE, SHOP_HOUR, source line",
              "complete": complete, "total_rows": total_rows,
              "total_bytes": sum(c["bytes"] for c in chunks),
              "source_csv_bytes_read": raw_bytes, "source_csv_gib_read": round(raw_bytes / GIB, 3),
              "source_exceeds_4_GiB": complete and raw_bytes > 4 * GIB,
              "convert_seconds": round(time.monotonic() - started, 1), "weeks": weeks, "chunks": chunks}
    summary_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{len(chunks)} chunks, {total_rows} rows, JSONL {result['total_bytes']} bytes, complete={complete}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

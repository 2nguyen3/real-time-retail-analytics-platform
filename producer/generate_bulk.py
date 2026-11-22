"""Generate large synthetic benchmark data as several independent JSONL chunks.

Stage 10 only. generate_data.py keeps its 100 000 row limit for Stage 02 fixtures; this
script reuses the same row generator (same schema and rules) but writes several chunks,
each with its own run_id and an independent audit manifest from audit_data.py.
Data is synthetic (source_type=synthetic), never real transactions.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from producer.generate_data import RUN_ID_PATTERN, rows  # noqa: E402

GIB = 1024 ** 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--prefix", default="bench10", help="run_id prefix; chunk n is <prefix>_c<nn>")
    parser.add_argument("--chunks", type=int, default=5)
    parser.add_argument("--rows-per-chunk", type=int, default=2_400_000)
    parser.add_argument("--seed", type=int, default=2026, help="chunk n uses seed + n - 1")
    parser.add_argument("--skip-audit", action="store_true", help="write chunks only (no manifest)")
    args = parser.parse_args()

    if args.chunks < 1 or args.rows_per_chunk < 1:
        parser.error("--chunks and --rows-per-chunk must be positive")
    if not RUN_ID_PATTERN.fullmatch(args.prefix + "_c01"):
        parser.error("--prefix must be a safe run_id prefix")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    summary = []
    for n in range(1, args.chunks + 1):
        run_id = f"{args.prefix}_c{n:02d}"
        output = (args.out_dir / f"{run_id}.jsonl").resolve()
        manifest = Path(str(output) + ".manifest.json")
        if output.exists() or manifest.exists():
            parser.error(f"{output.name} or its manifest exists; choose another --out-dir/--prefix")
        seed = args.seed + n - 1
        started = time.monotonic()
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with output.open("x", encoding="utf-8", newline="\n") as handle:
            for record in rows(args.rows_per_chunk, seed, run_id):
                handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
                handle.write("\n")
        generate_seconds = time.monotonic() - started
        audit_seconds = 0.0
        if not args.skip_audit:
            audit_start = time.monotonic()
            subprocess.run([sys.executable, str(Path(__file__).with_name("audit_data.py")),
                            "--input", str(output), "--manifest", str(manifest), "--seed", str(seed),
                            "--run-id", run_id, "--generated-at", generated_at], check=True)
            audit_seconds = time.monotonic() - audit_start
        size = output.stat().st_size
        summary.append({"run_id": run_id, "file": output.name, "rows": args.rows_per_chunk,
                        "bytes": size, "seed": seed,
                        "generate_seconds": round(generate_seconds, 1),
                        "audit_seconds": round(audit_seconds, 1)})
        print(f"{run_id}: {args.rows_per_chunk} rows, {size} bytes, "
              f"generate {generate_seconds:.1f}s, audit {audit_seconds:.1f}s", flush=True)

    total = sum(item["bytes"] for item in summary)
    result = {"source_type": "synthetic", "total_rows": sum(item["rows"] for item in summary),
              "total_bytes": total, "total_gib": round(total / GIB, 3),
              "exceeds_4_GiB": total > 4 * GIB, "chunks": summary}
    (args.out_dir / f"{args.prefix}_summary.json").write_text(json.dumps(result, indent=2) + "\n",
                                                               encoding="utf-8")
    print(f"total {total} bytes = {total / GIB:.3f} GiB; exceeds 4 GiB: {total > 4 * GIB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

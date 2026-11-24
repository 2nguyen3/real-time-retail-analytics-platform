"""Stage 11 region latency probe: run on a VM, measure the round trip to the fixed PostgreSQL.

Run the same command on every VM (one per region) with PG_HOST/PG_USER/PG_PASSWORD set in the
environment. The database stays where it is; only the VM region changes. Per round it records:

  tcp_connect : time to open a TCP connection to PG_HOST:PG_PORT (network round trip)
  select_1    : psql round trip of `SELECT 1` inside one open session (protocol round trip)
  <queries>   : the Stage 10 queries against an existing --run-id (client-observed time)

The database host and credentials are never written to the evidence files.
"""

from __future__ import annotations

import argparse
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from run_stage10 import QUERIES, append_csv, now, percentile, query_latency  # noqa: E402
from sql.postgres.reconcile import psql_argv  # noqa: E402

FIELDS = ["label", "region", "vm_sku", "round", "started_utc", "metric", "samples",
          "p50_ms", "p95_ms", "max_ms"]


def tcp_connect(host: str, port: int, samples: int) -> list[float]:
    times = []
    for _ in range(samples + 1):
        start = time.perf_counter()
        with socket.create_connection((host, port), timeout=10):
            pass
        times.append((time.perf_counter() - start) * 1000)
        time.sleep(0.2)
    return times[1:]  # first connection includes DNS resolution and is discarded


def select_one(samples: int) -> list[float]:
    script = "\\timing on\n\\o " + os.devnull + "\n" + "SELECT 1;\n" * (samples + 1)
    argv, env = psql_argv([], interactive=True)
    out = subprocess.run(argv, input=script, capture_output=True, text=True, env=env, timeout=300)
    if out.returncode:
        raise RuntimeError(f"SELECT 1 failed: {out.stderr[-300:]}")
    return [float(x) for x in re.findall(r"Time: ([0-9.]+) ms", out.stdout)][1:]


def record(path: Path, base: dict, metric: str, values: list[float]) -> str:
    row = {**base, "metric": metric, "samples": len(values), "p50_ms": round(percentile(values, 50), 2),
           "p95_ms": round(percentile(values, 95), 2), "max_ms": round(max(values), 2)}
    append_csv(path, FIELDS, row)
    return f"{metric}: p50 {row['p50_ms']} ms, p95 {row['p95_ms']} ms (n={row['samples']})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", required=True, help="Azure region of this VM, e.g. eastasia")
    parser.add_argument("--vm-sku", required=True)
    parser.add_argument("--run-id", required=True, help="run_id already loaded in PostgreSQL")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--tcp-samples", type=int, default=50)
    parser.add_argument("--label", default="dry-run", choices=("dry-run", "official"))
    parser.add_argument("--evidence-dir", type=Path, default=HERE.parents[1] / "reports/runtime/stage11")
    args = parser.parse_args()
    host, port = os.environ.get("PG_HOST"), int(os.environ.get("PG_PORT", "5432"))
    if not host:
        raise SystemExit("PG_HOST must point at the fixed PostgreSQL server")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", args.run_id):
        raise SystemExit("unsafe run ID")
    csv_path = args.evidence_dir / f"11-region-latency-{args.region}.csv"
    log_path = args.evidence_dir / f"11-benchmark-log-{args.region}.txt"
    args.evidence_dir.mkdir(parents=True, exist_ok=True)

    def log(message: str) -> None:
        line = f"{now()} {message}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")

    for number in range(1, args.rounds + 1):
        base = {"label": args.label, "region": args.region, "vm_sku": args.vm_sku,
                "round": number, "started_utc": now()}
        log(f"round {number}: region={args.region} sku={args.vm_sku}")
        log("  " + record(csv_path, base, "tcp_connect", tcp_connect(host, port, args.tcp_samples)))
        log("  " + record(csv_path, base, "select_1", select_one(args.samples)))
        for name, values in query_latency(args.run_id, args.samples).items():
            log("  " + record(csv_path, base, name, values))
    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

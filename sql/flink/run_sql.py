"""Render Stage 05 Flink SQL against explicit Kafka offset boundaries."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
QUERIES = {
    "raw": "SELECT COUNT(*) AS raw_count FROM kafka_lines",
    "quality": "SELECT quality_status, COUNT(*) AS row_count FROM classified_lines GROUP BY quality_status",
    "totals": "SELECT * FROM totals_by_run",
    "store": "SELECT * FROM revenue_by_store",
    "product": "SELECT * FROM revenue_by_product",
    "store_product": "SELECT * FROM revenue_by_store_product",
    "windows": "SELECT * FROM revenue_by_store_minute",
    "stream_windows": """CREATE TEMPORARY TABLE stage05_window_print (
  run_id STRING, store_id STRING, window_start TIMESTAMP(3), window_end TIMESTAMP(3),
  transaction_count BIGINT, total_quantity BIGINT, total_revenue DECIMAL(38, 2)
) WITH ('connector' = 'print', 'print-identifier' = 'stage05-window');
INSERT INTO stage05_window_print SELECT * FROM revenue_by_store_minute""",
}


def offsets(path: Path) -> tuple[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["topic"] != "retail.sales.transactions" or len(data["high_offsets"]) != 3:
        raise ValueError("expected the three partitions of retail.sales.transactions")
    mapping = {int(k): int(v) for k, v in data["high_offsets"].items()}
    if set(mapping) != {0, 1, 2} or any(v < 0 for v in mapping.values()):
        raise ValueError("invalid partition offsets")
    return data["topic"], ";".join(f"partition:{p},offset:{mapping[p]}" for p in sorted(mapping))


def render(name: str, start: Path, end: Path | None, query: str, restore_path: str | None = None) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]{1,40}", name):
        raise ValueError("name must contain only letters, digits and underscore")
    _, start_offsets = offsets(start)
    bound = ""
    if end:
        _, end_offsets = offsets(end)
        start_map = json.loads(start.read_text())["high_offsets"]
        end_map = json.loads(end.read_text())["high_offsets"]
        if any(int(end_map[p]) < int(start_map[p]) for p in start_map):
            raise ValueError("end offsets precede start offsets")
        bound = ",\n  'scan.bounded.mode' = 'specific-offsets',\n  'scan.bounded.specific-offsets' = '" + end_offsets + "'"
    if query == "stream_windows" and end is not None:
        raise ValueError("stream_windows must be unbounded; omit --end")
    source = (HERE / "01_kafka_source.sql").read_text(encoding="utf-8")
    source = source.replace("{{GROUP_ID}}", f"flink-stage05-{name}")
    source = source.replace("{{START_OFFSETS}}", start_offsets).replace("{{BOUND_OPTIONS}}", bound)
    common = "\n".join((HERE / file).read_text(encoding="utf-8") for file in
                       ("02_clean.sql", "03_aggregates.sql", "04_windows.sql"))
    settings = """SET 'sql-client.execution.result-mode' = 'tableau';
SET 'parallelism.default' = '1';
SET 'table.exec.source.idle-timeout' = '5 s';
SET 'table.exec.state.ttl' = '1 h';
SET 'execution.checkpointing.interval' = '10 s';
SET 'execution.checkpointing.dir' = 'file:///opt/flink/checkpoints';
"""
    if restore_path is not None:
        if query != "stream_windows" or not re.fullmatch(
            r"file:/opt/flink/checkpoints/savepoints/savepoint-[A-Za-z0-9-]+", restore_path
        ):
            raise ValueError("restore path must be a Stage 05 savepoint in the checkpoint volume")
        settings += f"SET 'execution.state-recovery.path' = '{restore_path}';\n"
    return settings + source + "\n" + common + "\n" + QUERIES[query] + ";\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--start", type=Path, required=True, help="Consumer probe baseline JSON")
    parser.add_argument("--end", type=Path, help="Consumer probe high offsets after publishing")
    parser.add_argument("--query", choices=QUERIES, required=True)
    parser.add_argument("--restore-path", help="Savepoint path for a streaming recovery test")
    args = parser.parse_args()
    try:
        output_dir = ROOT / "reports/runtime/flink"
        output_dir.mkdir(parents=True, exist_ok=True)
        sql = render(args.name, args.start, args.end, args.query, args.restore_path)
        local = output_dir / f"{args.name}_{args.query}.sql"
        local.write_text(sql, encoding="utf-8")
        remote = f"/tmp/stage05_{args.name}_{args.query}.sql"
        container = "retail-local-flink-jobmanager-1"
        subprocess.run(["docker", "cp", str(local), f"{container}:{remote}"], check=True)
        command = ["docker", "exec", container, "/opt/flink/bin/sql-client.sh", "-f", remote]
        log_path = output_dir / f"{args.name}_{args.query}.log"
        with log_path.open("w", encoding="utf-8") as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=120)
        output = log_path.read_text(encoding="utf-8")
        failed = result.returncode != 0 or "[ERROR]" in output or "Exception" in output
        print(f"SQL log: {log_path}; exit={result.returncode}; status={'FAIL' if failed else 'PASS'}")
        return 1 if failed else 0
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"Flink SQL failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

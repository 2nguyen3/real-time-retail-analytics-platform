"""R11 storage side: load detail and pre-aggregated rows into bench_r11, time each COPY, measure size.

Uses the application role from .env. Needs schema bench_r11 (01_admin_setup.sql) and Docker.
"""
import argparse
import csv
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

TABLES = {
    "tx_detail": """CREATE TABLE bench_r11.tx_detail (
  run_id TEXT NOT NULL, transaction_id TEXT NOT NULL, store_id TEXT NOT NULL, product_id TEXT NOT NULL,
  quantity BIGINT NOT NULL, price NUMERIC(28,8) NOT NULL, line_revenue NUMERIC(28,2) NOT NULL,
  currency VARCHAR(3) NOT NULL, event_time TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (run_id, transaction_id));
CREATE INDEX ON bench_r11.tx_detail (run_id, product_id);""",
    "agg_store_product": """CREATE TABLE bench_r11.agg_store_product (
  run_id TEXT NOT NULL, store_id TEXT NOT NULL, product_id TEXT NOT NULL, currency VARCHAR(3) NOT NULL,
  transaction_count BIGINT NOT NULL, total_quantity BIGINT NOT NULL, total_revenue NUMERIC(28,2) NOT NULL,
  PRIMARY KEY (run_id, store_id, product_id, currency));
CREATE INDEX ON bench_r11.agg_store_product (run_id, product_id);""",
}
FILES = {"tx_detail": "tx_detail.csv", "agg_store_product": "agg_store_product.csv"}

VIEW = """CREATE OR REPLACE VIEW bench_r11.tx_detail_v AS
SELECT run_id, store_id, product_id, currency, 1::bigint AS transaction_count,
       quantity AS total_quantity, line_revenue AS total_revenue
FROM bench_r11.tx_detail;"""


def env() -> dict:
    values = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
        match = re.match(r"\s*([A-Za-z_]\w*)=(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2).strip().strip("\"'")
    return values


CFG = env()


def psql(*args: str, stdin=None) -> str:
    child = {**os.environ, "PGPASSWORD": CFG["AZURE_PG_APP_PASSWORD"], "PGSSLMODE": "require"}
    command = ["docker", "run", "--rm", "-i", "-e", "PGPASSWORD", "-e", "PGSSLMODE", "postgres:17-alpine",
               "psql", "-X", "-v", "ON_ERROR_STOP=1", "-h", CFG["AZURE_PG_HOST"],
               "-U", CFG["AZURE_PG_APP_USER"], "-d", CFG["AZURE_PG_DB"], *args]
    out = subprocess.run(command, stdin=stdin or subprocess.DEVNULL, capture_output=True, env=child, timeout=3600)
    if out.returncode:
        message = out.stderr.decode("utf-8", "replace")[-600:]
        for key in ("AZURE_PG_HOST", "AZURE_PG_APP_USER", "AZURE_PG_APP_PASSWORD"):
            message = message.replace(CFG[key], "<hidden>")
        raise SystemExit("psql failed: " + message)
    return out.stdout.decode("utf-8")


def scalar_rows(sql: str) -> list:
    return [line.split("|") for line in psql("-At", "-c", sql).strip().splitlines()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=ROOT / "reports/runtime/r11")
    parser.add_argument("--out", type=Path, default=ROOT / "docs/evidence/11-r11-db-bi")
    parser.add_argument("--reps", type=int, default=3)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    expected = json.loads((args.data / "expected.json").read_text(encoding="utf-8"))
    rows_expected = {"tx_detail": expected["detail_rows"], "agg_store_product": expected["agg_rows"]}

    existing = {r[0] for r in scalar_rows("SELECT tablename FROM pg_tables WHERE schemaname='bench_r11'")}
    for table, ddl in TABLES.items():
        if table not in existing:
            psql("-q", "-c", ddl)

    loads = []
    for rep in range(1, args.reps + 1):
        for table, name in FILES.items():
            psql("-q", "-c", f"TRUNCATE bench_r11.{table}")
            with (args.data / name).open("rb") as source:
                output = psql("-c", "\\timing on", "-c",
                              f"\\copy bench_r11.{table} FROM pstdin WITH (FORMAT csv)", stdin=source)
            seconds = float(re.findall(r"Time: ([0-9.]+) ms", output)[-1]) / 1000
            count = int(scalar_rows(f"SELECT count(*) FROM bench_r11.{table}")[0][0])
            if count != rows_expected[table]:
                raise SystemExit(f"{table}: {count} rows, expected {rows_expected[table]}")
            loads.append({"table": table, "rep": rep, "rows": count, "csv_bytes": (args.data / name).stat().st_size,
                          "copy_seconds": round(seconds, 3), "rows_per_s": round(count / seconds, 1),
                          "finished_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
            print(table, rep, f"{seconds:.2f}s", flush=True)

    psql("-q", "-c", VIEW)
    reader = CFG["AZURE_PG_READER_USER"].replace('"', '""')
    psql("-q", "-c", f'GRANT SELECT ON bench_r11.agg_store_product, bench_r11.tx_detail_v TO "{reader}"')
    for table in TABLES:
        psql("-q", "-c", f"VACUUM (ANALYZE) bench_r11.{table}")
    sizes = []
    for table in TABLES:
        heap, index, total = scalar_rows(
            f"SELECT pg_table_size('bench_r11.{table}'), pg_indexes_size('bench_r11.{table}'), "
            f"pg_total_relation_size('bench_r11.{table}')")[0]
        sizes.append({"table": table, "rows": rows_expected[table], "table_bytes": heap,
                      "index_bytes": index, "total_bytes": total})

    q1 = expected["q1"]
    checks = []
    for source in ("tx_detail_v", "agg_store_product"):
        where = f"FROM bench_r11.{source} WHERE run_id='{expected['run_id']}'"
        got1 = scalar_rows(f"SELECT sum(transaction_count), sum(total_quantity), sum(total_revenue) {where}")[0]
        checks.append((source, "q1", got1 == [str(q1["transaction_count"]), str(q1["total_quantity"]),
                                              q1["total_revenue"]]))
        for label, column, key in (("q2", "product_id", "q2_top10_products"), ("q3", "store_id", "q3_top10_stores")):
            got = scalar_rows(f"SELECT {column}, sum(total_revenue) {where} GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 10")
            checks.append((source, label, got == expected[key]))

    for name, rows in (("r11-load.csv", loads), ("r11-size.csv", sizes),
                       ("r11-sql-check.csv", [{"source": s, "query": q, "match": m} for s, q, m in checks])):
        with (args.out / name).open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps(sizes))
    print("sql checks all match:", all(m for *_, m in checks))


if __name__ == "__main__":
    main()

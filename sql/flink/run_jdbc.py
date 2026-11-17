"""Submit Stage 06 JDBC SQL without storing or echoing PostgreSQL credentials."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
import json
from urllib.request import urlopen
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sql.flink.run_sql import HERE, ROOT, render_setup


CONTAINER = "retail-local-flink-jobmanager-1"
POSTGRES = "retail-local-postgres-1"


def container_env(name: str) -> str:
    result = subprocess.run(["docker", "exec", POSTGRES, "printenv", name],
                            capture_output=True, check=True)
    value = result.stdout.decode("utf-8").rstrip("\r\n")
    if not value:
        raise ValueError(f"{name} is empty in PostgreSQL container")
    return value


def sql_quote(value: str) -> str:
    return value.replace("'", "''")


def submit(name: str, start: Path, end: Path | None, restore_path: str | None) -> dict:
    username = container_env("POSTGRES_USER")
    password = container_env("POSTGRES_PASSWORD")
    template = (HERE / "05_jdbc_sinks.sql").read_text(encoding="utf-8")
    sql = render_setup(name, start, end, restore_path, group_prefix="flink-stage06")
    if end is not None:
        sql += "SET 'table.dml-sync' = 'true';\n"
    sql += template.replace("{{JDBC_USER}}", sql_quote(username)).replace(
        "{{JDBC_PASSWORD}}", sql_quote(password))
    remote = f"/tmp/stage06_{name}.sql"
    runtime = ROOT / "reports/runtime/flink"
    runtime.mkdir(parents=True, exist_ok=True)
    local_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".sql", delete=False) as local:
            local_path = local.name
            os.chmod(local.name, 0o600)
            local.write(sql)
            local.flush()
            local.close()
            subprocess.run(["docker", "cp", local.name, f"{CONTAINER}:{remote}"],
                           check=True, capture_output=True)
            subprocess.run(["docker", "exec", "-u", "0", CONTAINER, "chown", "9999:9999", remote],
                           check=True, capture_output=True)
            subprocess.run(["docker", "exec", "-u", "0", CONTAINER, "chmod", "600", remote],
                           check=True, capture_output=True)
            submitted_at_ms = int(time.time() * 1000)
            result = subprocess.run(
                ["docker", "exec", CONTAINER, "/opt/flink/bin/sql-client.sh", "-f", remote],
                capture_output=True, timeout=180,
            )
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        sanitized = output.replace(password, "<redacted>").replace(sql_quote(password), "<redacted>")
        log = runtime / f"jdbc_{name}.log"
        log.write_text(sanitized, encoding="utf-8")
        job_ids = re.findall(r"Job ID:\s*([0-9a-f]{32})", sanitized)
        failed = result.returncode != 0 or "[ERROR]" in sanitized or "Exception" in sanitized
        job_state = None
        if not failed:
            with urlopen("http://localhost:8081/jobs/overview", timeout=5) as response:
                jobs = json.load(response)["jobs"]
            matching = [job for job in jobs if job["start-time"] >= submitted_at_ms
                        and "pg_sales_by_store" in job["name"]]
            if matching:
                latest = max(matching, key=lambda job: job["start-time"])
                job_ids = [latest["jid"]]
                job_state = latest["state"]
        expected_state = "FINISHED" if end is not None else "RUNNING"
        return {"status": "PASS" if not failed and job_state == expected_state else "FAIL",
                "job_state": job_state, "job_ids": job_ids,
                "log": str(log), "exit_code": result.returncode}
    finally:
        if local_path:
            Path(local_path).unlink(missing_ok=True)
        subprocess.run(["docker", "exec", "-u", "0", CONTAINER, "rm", "-f", remote],
                       capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--start", type=Path, required=True)
    parser.add_argument("--end", type=Path, help="Omit for a running streaming job")
    parser.add_argument("--restore-path")
    args = parser.parse_args()
    try:
        result = submit(args.name, args.start, args.end, args.restore_path)
        print(f"status={result['status']} job_state={result['job_state']} "
              f"job_ids={','.join(result['job_ids'])} log={result['log']}")
        return 0 if result["status"] == "PASS" else 1
    except (OSError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"JDBC submit failed: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

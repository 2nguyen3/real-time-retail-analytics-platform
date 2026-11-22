"""Stage 10 benchmark driver: publish -> Flink bounded job -> reconcile -> query latency.

Reuses the Stage 07 helpers and the existing stack (local Docker, or the Azure VM with
PG_HOST/PG_USER/PG_PASSWORD and JDBC_URL/JDBC_USER/JDBC_PASSWORD set in the environment).
Results go to --evidence-dir. Default is reports/runtime/stage10 (Git ignored, dry run);
use --evidence-dir docs/evidence --label official for the recorded run.

  volume : run every chunk of a generate_bulk.py output, one after another
  repeat : run the same file N times with new run IDs (throughput and latency repeats)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tests/integration"))
sys.path.insert(0, str(HERE))

import run_stage07 as s7  # noqa: E402
from sample_metrics import MetricSampler  # noqa: E402
from sql.postgres.reconcile import psql_argv  # noqa: E402

QUERIES = {
    "revenue_by_store": "SELECT store_id, SUM(total_revenue) FROM sales_by_store_minute "
                        "WHERE run_id = '{run}' GROUP BY store_id",
    "top_products": "SELECT product_id, SUM(total_revenue) AS r FROM sales_by_store_product "
                    "WHERE run_id = '{run}' GROUP BY product_id ORDER BY r DESC LIMIT 10",
    "minute_window_1d": "SELECT window_start, SUM(total_revenue) FROM sales_by_store_minute "
                        "WHERE run_id = '{run}' AND window_start >= '2024-01-01' "
                        "AND window_start < '2024-01-02' GROUP BY window_start ORDER BY window_start",
    "store_totals": "SELECT * FROM sales_by_store WHERE run_id = '{run}'",
}
FIELDS = {
    "throughput": ["label", "environment", "rep", "run_id", "rows", "bytes", "publish_wall_s",
                   "publish_send_s", "publish_rows_per_s", "publish_mb_per_s", "flink_job_s",
                   "flink_rows_per_s", "flink_mb_per_s", "reconcile_s", "end_to_end_s", "status",
                   "started_utc", "job_id"],
    "latency": ["label", "environment", "rep", "run_id", "query", "samples", "p50_ms", "p95_ms",
                "max_ms"],
}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_csv(path: Path, fields: list[str], row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if new:
            writer.writeheader()
        writer.writerow(row)


def log(evidence: Path, message: str) -> None:
    line = f"{now()} {message}"
    print(line, flush=True)
    with (evidence / "10-benchmark-log.txt").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")


def percentile(values: list[float], pct: int) -> float:
    ordered = sorted(values)
    return ordered[max(0, (pct * len(ordered) + 99) // 100 - 1)]


def query_latency(run_id: str, samples: int) -> dict[str, list[float]]:
    """One psql session per query: \\timing gives the client-observed round trip per execution."""
    results = {}
    for name, template in QUERIES.items():
        sql = template.format(run=run_id)
        script = "\\timing on\n\\o " + os.devnull + "\n" + (sql + ";\n") * (samples + 1)
        argv, env = psql_argv([], interactive=True)
        out = subprocess.run(argv, input=script, capture_output=True, text=True, env=env, timeout=900)
        if out.returncode:
            raise RuntimeError(f"latency query {name} failed: {out.stderr[-300:]}")
        times = [float(x) for x in re.findall(r"Time: ([0-9.]+) ms", out.stdout)]
        results[name] = times[1:]  # first execution warms the cache and is discarded
    return results


def flink_get(path: str) -> dict:
    with urlopen("http://localhost:8081" + path, timeout=10) as response:
        return json.load(response)


def stray_processes() -> list[str]:
    """Benchmark-related processes other than this one (leftovers corrupt Kafka offsets)."""
    pattern = r"replay\.py|run_stage10|run_jdbc|sql-client"
    me = {os.getpid(), os.getppid()}
    found = []
    if platform.system() == "Windows":
        script = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match '" + pattern
                  + "' -and $_.CommandLine -notmatch 'Get-CimInstance' } | "
                  "ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }")
        out = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                             capture_output=True, text=True, timeout=60).stdout
    else:
        out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True,
                             timeout=30).stdout.replace(" ", "|", 1)
        out = "\n".join(f"{line.split(None, 1)[0]}|{line.split(None, 1)[1]}" for line in out.splitlines()
                        if len(line.split(None, 1)) == 2 and re.search(pattern, line))
    for line in out.splitlines():
        pid, _, cmd = line.partition("|")
        launcher = re.match(r'\s*"?(?:.*[\\/])?(bash|sh|ssh|powershell|pwsh)(?:\.exe)?"?\s', cmd + " ", re.I)
        if pid.strip().isdigit() and int(pid) not in me and "preflight" not in cmd and not launcher:
            found.append(f"{pid.strip()} {cmd[:120]}")
    return found


def preflight(min_heap_mb: int, min_disk_gb: int, evidence: Path) -> None:
    """Fail fast when the environment is not clean. Returns None when every check passes."""
    problems = []
    strays = stray_processes()
    if strays:
        problems.append("stray processes: " + "; ".join(strays))
    try:
        jobs = flink_get("/jobs/overview")["jobs"]
        active = [j["jid"] for j in jobs if j["state"] in ("RUNNING", "RESTARTING", "CREATED")]
        if active:
            problems.append(f"Flink jobs still active: {active}")
        managers = flink_get("/taskmanagers")["taskmanagers"]
        if not managers:
            problems.append("Flink has no TaskManager")
        elif min_heap_mb:
            detail = flink_get("/taskmanagers/" + managers[0]["id"])["memoryConfiguration"]
            heap_mb = (detail["frameworkHeap"] + detail["taskHeap"]) / 1024**2
            if heap_mb < min_heap_mb:
                problems.append(f"TaskManager heap {heap_mb:.0f} MB < {min_heap_mb} MB "
                                "(set FLINK_TM_PROCESS_MEMORY=3g and FLINK_TM_MANAGED_FRACTION=0.1)")
    except OSError as exc:
        problems.append(f"Flink REST unreachable: {exc}")
    free_gb = shutil.disk_usage(ROOT).free / 1024**3
    if free_gb < min_disk_gb:
        problems.append(f"free disk {free_gb:.0f} GB < {min_disk_gb} GB")
    try:
        s7.pg("SELECT 1")
    except Exception as exc:
        problems.append(f"PostgreSQL check failed: {type(exc).__name__}")
    if problems:
        for problem in problems:
            log(evidence, "PREFLIGHT FAIL: " + problem)
        raise SystemExit("preflight failed; fix the items above before running")
    log(evidence, f"PREFLIGHT PASS (free disk {free_gb:.0f} GB)")


def run_flink_watched(args: list[str], env: dict, started_ms: int, restart_grace: int,
                      overall_timeout: int, evidence: Path, run_id: str) -> tuple[str, str]:
    """Run run_jdbc.py; abort early if the job keeps restarting or fails instead of waiting."""
    proc = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=env)
    began = time.monotonic()
    bad_since: float | None = None
    try:
        while True:
            try:
                out, err = proc.communicate(timeout=10)
                return out, err
            except subprocess.TimeoutExpired:
                pass
            if time.monotonic() - began > overall_timeout:
                raise RuntimeError(f"Flink step exceeded {overall_timeout}s")
            try:
                jobs = [j for j in flink_get("/jobs/overview")["jobs"] if j["start-time"] >= started_ms]
            except OSError:
                continue
            bad = [j for j in jobs if j["state"] in ("RESTARTING", "FAILED")]
            if not bad:
                bad_since = None
                continue
            bad_since = bad_since or time.monotonic()
            if bad[0]["state"] == "FAILED" or time.monotonic() - bad_since > restart_grace:
                try:
                    entries = flink_get(f"/jobs/{bad[0]['jid']}/exceptions")["exceptionHistory"]["entries"]
                    cause = entries[-1]["exceptionName"] if entries else "unknown"
                except (OSError, KeyError):
                    cause = "unknown"
                log(evidence, f"{run_id}: Flink job {bad[0]['state']} for more than {restart_grace}s "
                              f"({cause}); cancelling")
                subprocess.run(["docker", "exec", s7.FLINK, "/opt/flink/bin/flink", "cancel", bad[0]["jid"]],
                               capture_output=True, timeout=60)
                raise RuntimeError(f"Flink job {bad[0]['state']} ({cause})")
    finally:
        if proc.poll() is None:
            proc.kill()
            subprocess.run(["docker", "exec", s7.FLINK, "pkill", "-f", "sql-client"],
                           capture_output=True, timeout=60)


def flink_duration(job_id: str) -> float:
    with urlopen(f"http://localhost:8081/jobs/{job_id}", timeout=10) as response:
        job = json.load(response)
    return job["duration"] / 1000.0


def run_one(source: Path, rows: int, run_id: str, evidence: Path, label: str, environment: str,
            rep: int, samples: int, interval: float, restart_grace: int = 180) -> dict:
    size = source.stat().st_size
    work = ROOT / "reports/runtime/stage10" / run_id
    work.mkdir(parents=True, exist_ok=True)
    sampler = MetricSampler(evidence / "10-resource-samples.csv", run_id, interval, ROOT).start()
    started = now()
    t0 = time.monotonic()
    row = {"label": label, "environment": environment, "rep": rep, "run_id": run_id, "rows": rows,
           "bytes": size, "started_utc": started, "status": "FAIL"}
    try:
        log(evidence, f"{run_id}: publish {rows} rows ({size} bytes)")
        sampler.set_phase("publish")
        start_path, end_path = work / "start.json", work / "end.json"
        start = s7.capture_offsets(start_path)
        t_publish = time.monotonic()
        stats = s7.publish(source, rows, run_id, work / "producer.json")
        row["publish_wall_s"] = round(time.monotonic() - t_publish, 2)
        row["publish_send_s"] = stats["elapsed_seconds"]
        row["publish_rows_per_s"] = round(rows / stats["elapsed_seconds"], 1)
        row["publish_mb_per_s"] = round(size / 1e6 / stats["elapsed_seconds"], 2)
        end = s7.capture_offsets(end_path)
        delta = s7.offset_delta(start, end)
        if delta != rows:
            raise AssertionError(f"Kafka offset delta {delta} differs from {rows} rows")

        log(evidence, f"{run_id}: Flink bounded job")
        sampler.set_phase("flink")
        env = {"JDBC_SUBMIT_TIMEOUT": "7200", **os.environ}
        t_flink = time.monotonic()
        stdout, stderr = run_flink_watched(
            [str(s7.PYTHON), str(ROOT / "sql/flink/run_jdbc.py"), "--name", run_id,
             "--start", str(start_path), "--end", str(end_path)],
            env, int(time.time() * 1000) - 5000, restart_grace, int(env["JDBC_SUBMIT_TIMEOUT"]) + 300,
            evidence, run_id)
        flink_wall = time.monotonic() - t_flink
        match = re.search(r"job_ids=([0-9a-f]{32})", stdout)
        if not match or "status=PASS" not in stdout:
            raise RuntimeError(f"Flink job failed: {(stdout + stderr)[-400:]}")
        row["job_id"] = match.group(1)
        row["flink_job_s"] = round(flink_duration(row["job_id"]), 2) or round(flink_wall, 2)
        row["flink_rows_per_s"] = round(rows / row["flink_job_s"], 1)
        row["flink_mb_per_s"] = round(size / 1e6 / row["flink_job_s"], 2)

        log(evidence, f"{run_id}: reconcile with source file")
        sampler.set_phase("reconcile")
        t_rec = time.monotonic()
        s7.database_check(source, rows, run_id, replayed=True)
        row["reconcile_s"] = round(time.monotonic() - t_rec, 2)
        row["end_to_end_s"] = round(time.monotonic() - t0 - row["reconcile_s"], 2)

        log(evidence, f"{run_id}: query latency ({samples} runs per query)")
        sampler.set_phase("queries")
        for name, times in query_latency(run_id, samples).items():
            append_csv(evidence / "10-query-latency.csv", FIELDS["latency"], {
                "label": label, "environment": environment, "rep": rep, "run_id": run_id,
                "query": name, "samples": len(times), "p50_ms": round(statistics.median(times), 2),
                "p95_ms": round(percentile(times, 95), 2), "max_ms": round(max(times), 2)})
        row["status"] = "PASS"
        log(evidence, f"{run_id}: PASS publish {row['publish_rows_per_s']} rows/s, "
                      f"flink {row['flink_rows_per_s']} rows/s")
    except Exception as exc:  # recorded as FAIL, then re-raised after the row is written
        log(evidence, f"{run_id}: FAIL {type(exc).__name__}: {str(exc)[:300]}")
        raise
    finally:
        sampler.set_phase("done")
        sampler.stop()
        append_csv(evidence / "10-throughput-runs.csv", FIELDS["throughput"], row)
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    pre = sub.add_parser("preflight", help="check the environment is clean, then exit")
    pre.add_argument("--evidence-dir", type=Path, default=ROOT / "reports/runtime/stage10")
    pre.add_argument("--min-heap-mb", type=int, default=1500, help="0 skips the TaskManager heap check")
    pre.add_argument("--min-disk-gb", type=int, default=20)
    for name in ("volume", "repeat"):
        p = sub.add_parser(name)
        p.add_argument("--skip-preflight", action="store_true")
        p.add_argument("--min-heap-mb", type=int, default=1500, help="0 skips the TaskManager heap check")
        p.add_argument("--min-disk-gb", type=int, default=20)
        p.add_argument("--restart-grace", type=int, default=180,
                       help="seconds a Flink job may stay RESTARTING/FAILED before the run is aborted")
        p.add_argument("--evidence-dir", type=Path, default=ROOT / "reports/runtime/stage10")
        p.add_argument("--label", default="dry-run", choices=("dry-run", "official"))
        p.add_argument("--environment", default="local", help="local or cloud (free text)")
        p.add_argument("--samples", type=int, default=30, help="runs per query")
        p.add_argument("--interval", type=float, default=5.0, help="resource sample seconds")
    v = sub.choices["volume"]
    v.add_argument("--dir", type=Path, required=True)
    v.add_argument("--prefix", default="bench10")
    r = sub.choices["repeat"]
    r.add_argument("--source", type=Path, required=True)
    r.add_argument("--rows", type=int, required=True)
    r.add_argument("--reps", type=int, default=3)
    r.add_argument("--run-prefix", default="bench10_rep")
    args = parser.parse_args()
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    if args.mode == "preflight":
        preflight(args.min_heap_mb, args.min_disk_gb, args.evidence_dir)
        return 0
    if not args.skip_preflight:
        preflight(args.min_heap_mb, args.min_disk_gb, args.evidence_dir)
    suffix = datetime.now(timezone.utc).strftime("%m%d%H%M")

    if args.mode == "volume":
        summary = json.loads((args.dir / f"{args.prefix}_summary.json").read_text(encoding="utf-8"))
        total_rows = total_bytes = 0
        for item in summary["chunks"]:
            source = args.dir / item["file"]
            manifest = json.loads(Path(str(source) + ".manifest.json").read_text(encoding="utf-8"))
            if manifest["raw_file_bytes"] != source.stat().st_size:
                raise SystemExit(f"{item['file']}: size differs from manifest")
            run = f"{item['run_id']}_{suffix}"
            run_one(source, manifest["message_count"], run, args.evidence_dir, args.label,
                    args.environment, 1, args.samples, args.interval, args.restart_grace)
            total_rows += manifest["message_count"]
            total_bytes += manifest["raw_file_bytes"]
            append_csv(args.evidence_dir / "10-volume-summary.csv",
                       ["label", "environment", "run_id", "rows", "bytes", "cumulative_rows",
                        "cumulative_bytes", "cumulative_gib", "status", "finished_utc"],
                       {"label": args.label, "environment": args.environment, "run_id": run,
                        "rows": manifest["message_count"], "bytes": manifest["raw_file_bytes"],
                        "cumulative_rows": total_rows, "cumulative_bytes": total_bytes,
                        "cumulative_gib": round(total_bytes / 1024**3, 3), "status": "PASS",
                        "finished_utc": now()})
        log(args.evidence_dir, f"volume done: {total_rows} rows, {total_bytes} bytes "
                               f"({total_bytes / 1024**3:.3f} GiB); exceeds 4 GiB: {total_bytes > 4 * 1024**3}")
    else:
        for rep in range(1, args.reps + 1):
            run_one(args.source, args.rows, f"{args.run_prefix}{rep}_{suffix}", args.evidence_dir,
                    args.label, args.environment, rep, args.samples, args.interval, args.restart_grace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

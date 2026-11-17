"""Run bounded and restart tests against the existing local Kafka/Flink/PostgreSQL stack.

No volumes, topics, or historical run IDs are deleted. Runtime details stay Git ignored.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from producer.consumer_probe import capture, consumer, load_source, probe  # noqa: E402
from producer.generate_data import rows as synthetic_rows  # noqa: E402
from sql.flink.verify_results import final_rows, verify as verify_flink  # noqa: E402
from sql.postgres.reconcile import reconcile  # noqa: E402

PYTHON = ROOT / (".venv/Scripts/python.exe" if (ROOT / ".venv/Scripts/python.exe").exists() else ".venv/bin/python")
SAMPLE = ROOT / "data/samples/synthetic_10000.jsonl"
TOPIC = "retail.sales.transactions"
FLINK = "retail-local-flink-jobmanager-1"
POSTGRES = "retail-local-postgres-1"
EVIDENCE = ROOT / "docs/evidence"
MATRIX_COLUMNS = ("test_id", "objective", "input", "run_id", "initial_condition", "steps",
                  "expected", "actual", "status", "started_at_utc", "duration_seconds",
                  "runtime_evidence", "notes")


class SkipCase(Exception):
    """A documented optional case cannot run with available local resources."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def command(args: list[str | Path], timeout: int = 120) -> str:
    result = subprocess.run([str(x) for x in args], cwd=ROOT, capture_output=True,
                            text=True, timeout=timeout)
    if result.returncode:
        tail = (result.stdout + result.stderr)[-1200:]
        raise RuntimeError(f"{' '.join(str(x) for x in args[:3])} exited {result.returncode}: {tail}")
    return result.stdout


def pg(sql: str) -> list[list[str]]:
    output = command(["docker", "exec", POSTGRES, "sh", "-c",
                      'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -F "|" -At -c "$1"',
                      "sh", sql], timeout=20)
    return [line.split("|") for line in output.splitlines() if line]


def pg_totals(run_id: str, table: str = "sales_by_store") -> tuple[int, int, int, Decimal]:
    if not re.fullmatch(r"[A-Za-z0-9_]{1,60}", run_id):
        raise ValueError("unsafe run ID")
    if table not in ("sales_by_store", "sales_by_store_product", "sales_by_store_minute"):
        raise ValueError("unsafe table")
    row = pg(f"SELECT COUNT(*), COALESCE(SUM(transaction_count),0), "
             f"COALESCE(SUM(total_quantity),0), COALESCE(SUM(total_revenue),0) "
             f"FROM {table} WHERE run_id = '{run_id}'")[0]
    return int(row[0]), int(row[1]), int(row[2]), Decimal(row[3])


def flink_rest(path: str) -> dict:
    with urlopen("http://localhost:8081" + path, timeout=5) as response:
        return json.load(response)


def wait_until(check, *, timeout: float = 45, interval: float = 1) -> object:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(interval)
    raise TimeoutError("expected state was not observed before timeout")


def readiness() -> dict:
    if shutil.disk_usage(ROOT).free < 5 * 1024**3:
        raise RuntimeError("less than 5 GiB SSD free")
    names = command(["docker", "ps", "--format", "{{.Names}} {{.Status}}"])
    for service in ("kafka", "flink-jobmanager", "flink-taskmanager", "postgres"):
        if not any(service in line and "Up" in line for line in names.splitlines()):
            raise RuntimeError(f"{service} is not running")
    if pg("SELECT 1")[0][0] != "1":
        raise RuntimeError("PostgreSQL SELECT 1 failed")
    if not flink_rest("/taskmanagers").get("taskmanagers"):
        raise RuntimeError("Flink has no TaskManager")
    running = [job["jid"] for job in flink_rest("/jobs/overview")["jobs"]
               if job["state"] in ("RUNNING", "RESTARTING", "CREATED")]
    if running:
        raise RuntimeError(f"existing Flink jobs require review: {running}")
    baseline = capture_offsets(ROOT / "reports/runtime/stage07/readiness_offsets.json")
    if baseline["partition_count"] != 3:
        raise RuntimeError("Kafka topic does not have three partitions")
    command([PYTHON, ROOT / "sql/postgres/seed_dimensions.py", "--input", SAMPLE,
             "--limit", "1000"])
    return {"docker": names.strip().splitlines(), "kafka_partitions": 3,
            "ssd_free_bytes": shutil.disk_usage(ROOT).free}


def capture_offsets(path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    client = consumer("localhost:9094")
    try:
        result = capture(client, TOPIC)
    finally:
        client.close()
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def offset_delta(start: dict, end: dict) -> int:
    return sum(int(end["high_offsets"][p]) - int(n)
               for p, n in start["high_offsets"].items())


def publish(source: Path, count: int, run_id: str, stats: Path, rate: int = 0) -> dict:
    command([PYTHON, ROOT / "producer/replay.py", "--input", source, "--limit", str(count),
             "--run-id", run_id, "--rate", str(rate), "--stats-output", stats], timeout=max(60, count // max(rate, 100) + 30))
    result = json.loads(stats.read_text(encoding="utf-8"))
    if result["delivered"] != count or result["pending"] or result["failed"]:
        raise AssertionError(f"Producer ACK mismatch: {result}")
    return result


def kafka_probe(baseline: dict, run_id: str, count: int, source: Path | None = None) -> dict:
    client = consumer("localhost:9094")
    try:
        references = load_source(source, count) if source is not None else None
        result = probe(client, baseline, run_id, count, 45, references)
    finally:
        client.close()
    if result["test_status"] != "PASS":
        raise AssertionError(f"Consumer probe mismatch: {result}")
    return result


def jdbc(name: str, start: Path, end: Path | None = None, restore: str | None = None) -> tuple[str, str]:
    args: list[str | Path] = [PYTHON, ROOT / "sql/flink/run_jdbc.py", "--name", name,
                              "--start", start]
    if end is not None:
        args += ["--end", end]
    if restore is not None:
        args += ["--restore-path", restore]
    output = command(args, timeout=210)
    job_id = re.search(r"job_ids=([0-9a-f]{32})", output)
    state = re.search(r"job_state=(RUNNING|FINISHED)", output)
    if not job_id or not state:
        raise RuntimeError(f"JDBC runner did not report a verified job: {output}")
    return job_id.group(1), state.group(1)


def stop_job(job_id: str) -> str:
    output = command(["docker", "exec", FLINK, "/opt/flink/bin/flink", "stop",
                      "--savepointPath", "file:///opt/flink/checkpoints/savepoints", job_id], timeout=90)
    match = re.search(r"Path: (file:/opt/flink/checkpoints/savepoints/savepoint-[A-Za-z0-9-]+)", output)
    if not match:
        raise RuntimeError(f"stop did not produce savepoint: {output[-500:]}")
    return match.group(1)


def database_check(source: Path, limit: int | None, run_id: str, *, replayed: bool,
                   closed_before: str | None = None) -> list[dict]:
    rows, counts = reconcile(source, limit, run_id, replayed, closed_before)
    if not counts["valid"] or any(row["status"] != "PASS" for row in rows):
        raise AssertionError(f"PostgreSQL reconciliation failed: {rows}")
    return rows


def split_jsonl(source: Path, target: Path, begin: int, count: int) -> None:
    with source.open(encoding="utf-8") as original, target.open("w", encoding="utf-8") as part:
        for index, line in enumerate(original):
            if begin <= index < begin + count:
                part.write(line)
            if index >= begin + count:
                break


class Stage07:
    def __init__(self, batch: str) -> None:
        if not re.fullmatch(r"[a-z0-9_]{1,30}", batch):
            raise ValueError("batch must contain lowercase letters, digits, underscore")
        self.batch = batch
        self.runtime = ROOT / "reports/runtime/stage07" / batch
        self.runtime.mkdir(parents=True, exist_ok=False)
        self.matrix: list[dict] = []
        self.validations: list[dict] = []
        self.restarts: list[str] = []
        self.normal: dict | None = None
        self.quality_counts: dict | None = None

    def path(self, name: str) -> Path:
        return self.runtime / name

    def run_id(self, suffix: str) -> str:
        # Flink SQL Client truncates long tableau cells; keep IDs short enough for verification.
        batch_key = hashlib.sha256(self.batch.encode("ascii")).hexdigest()[:10]
        return f"s07_{batch_key}_{suffix}"

    def add(self, test_id: str, objective: str, source: str, run_id: str, initial: str,
            steps: str, expected: str, actual: str, status: str, started: str,
            duration: float, notes: str = "") -> None:
        self.matrix.append(dict(zip(MATRIX_COLUMNS, (test_id, objective, source, run_id,
            initial, steps, expected, actual, status, started, f"{duration:.3f}",
            str(self.runtime.relative_to(ROOT)), notes))))

    def case(self, ids: list[str], func, meta: tuple[str, str, str, str, str]) -> None:
        started, clock = utc_now(), time.monotonic()
        try:
            result = func()
            status = "PASS"
            actual = json.dumps(result, ensure_ascii=False, sort_keys=True, default=str)
            run_ids = result.get("run_ids", result.get("run_id", self.run_id(ids[0].lower())))
            if isinstance(run_ids, list):
                run_ids = ",".join(run_ids)
            print(f"{','.join(ids)} PASS {actual[:500]}", flush=True)
        except SkipCase as exc:
            status, actual = "SKIPPED", str(exc)
            run_ids = self.run_id(ids[0].lower())
            print(f"{','.join(ids)} SKIPPED {actual}", flush=True)
        except Exception as exc:
            status, actual = "FAIL", f"{type(exc).__name__}: {exc}"
            run_ids = self.run_id(ids[0].lower())
            print(f"{','.join(ids)} FAIL {actual[:700]}", flush=True)
        objective, source, initial, steps, expected = meta
        for test_id in ids:
            specific = {
                "TC02": ("Deduplicate by run_id + transaction_id", "one same-run duplicate, one cross-run ID, same basket distinct lines"),
                "TC03": ("Reject invalid quantity", "quantity <= 0 classified invalid and excluded from DB totals"),
                "TC04": ("Reject malformed JSON, missing field and bad timestamp", "invalid_json and business-validation categories counted separately"),
            }.get(test_id, (objective, expected))
            notes = {
                "TC05": "Late count inferred from closed-window before/after; no direct late counter.",
                "TC06": "Controlled resume after ACK; no process crash or unconfirmed-message claim.",
                "TC08": "Database restarted while Flink jobs were stopped.",
                "TC09": "Idempotent final state; no exactly-once claim.",
                "TC11": "Small local integration run; not the >4 GiB cloud benchmark.",
            }.get(test_id, "")
            self.add(test_id, specific[0], source, run_ids, initial,
                     steps, specific[1], actual, status, started, time.monotonic() - clock, notes)
        self.flush_runtime()

    def flush_runtime(self) -> None:
        with self.path("matrix.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=MATRIX_COLUMNS)
            writer.writeheader()
            writer.writerows(self.matrix)
        if self.validations:
            with self.path("validation.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=self.validations[0].keys())
                writer.writeheader()
                writer.writerows(self.validations)
        self.path("restart.txt").write_text("\n".join(self.restarts) + "\n", encoding="utf-8")

    def publish_evidence(self) -> None:
        if len(self.matrix) != 11:
            raise RuntimeError("only a complete 11-case run may publish evidence")
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        mapping = {"matrix.csv": "07-test-matrix.csv",
                   "validation.csv": "07-validation-output.csv",
                   "restart.txt": "07-restart-log.txt"}
        for source, target in mapping.items():
            destination = EVIDENCE / target
            if destination.exists():
                raise FileExistsError(f"refusing to replace existing evidence: {destination}")
            shutil.copyfile(self.path(source), destination)

    def normal_test(self) -> dict:
        run = self.run_id("normal")
        start_path, end_path = self.path("normal_start.json"), self.path("normal_end.json")
        start = capture_offsets(start_path)
        stats = publish(SAMPLE, 1000, run, self.path("normal_producer.json"))
        end = capture_offsets(end_path)
        if offset_delta(start, end) != 1000:
            raise AssertionError("Kafka offset delta differs from 1000 ACKs")
        observed = kafka_probe(start, run, 1000, SAMPLE)
        job_id, state = jdbc(self.run_id("normal_job"), start_path, end_path)
        tables = database_check(SAMPLE, 1000, run, replayed=True)
        self.validations.extend(tables)
        self.normal = {"run_id": run, "start": start_path, "end": end_path,
                       "job_id": job_id, "tables": tables}
        return {"run_id": run, "ack": stats["delivered"], "kafka_offsets": offset_delta(start, end),
                "consumer": observed["consumed"], "job_id": job_id, "job_state": state,
                "quantity": tables[0]["actual_quantity"], "revenue": tables[0]["actual_revenue"],
                "store_rows": tables[0]["actual_rows"], "product_rows": tables[1]["actual_rows"],
                "minute_rows": tables[2]["actual_rows"]}

    def quality_test(self) -> dict:
        from sql.flink.test_events import build_quality, send_raw

        fixture = self.path("quality.jsonl")
        build_quality(fixture)
        a, b = self.run_id("quality_a"), self.run_id("quality_b")
        content = fixture.read_text(encoding="utf-8")
        fixture.write_text(content.replace("fixture_001", a).replace("fixture_002", b), encoding="utf-8")
        start_path, end_path = self.path("quality_start.json"), self.path("quality_end.json")
        start = capture_offsets(start_path)
        send_raw(fixture, "localhost:9094", TOPIC, 1, None)
        end = capture_offsets(end_path)
        if offset_delta(start, end) != 10:
            raise AssertionError("quality fixture not fully stored in Kafka")
        query_name = self.run_id("quality_sql")
        for query in ("raw", "quality", "totals"):
            command([PYTHON, ROOT / "sql/flink/run_sql.py", "--name", query_name,
                     "--start", start_path, "--end", end_path, "--query", query], timeout=150)
        flink = verify_flink(query_name, fixture, None, ["raw", "quality", "totals"])
        if flink["test_status"] != "PASS":
            raise AssertionError(f"Flink quality counts mismatch: {flink}")
        job_id, _ = jdbc(self.run_id("quality_job"), start_path, end_path)
        for run in (a, b):
            self.validations.extend(database_check(fixture, None, run, replayed=False))
        counts = flink["actual_counts"]
        if counts != {"raw": 10, "valid_before_dedup": 5, "invalid": 5,
                      "unique_valid": 4, "duplicate": 1}:
            raise AssertionError(f"unexpected quality classification: {counts}")
        reasons = {key[0]: int(value[1]) for key, value in final_rows(
            ROOT / "reports/runtime/flink" / f"{query_name}_quality.log", (0,)).items()}
        if reasons != {"valid": 5, "quantity": 1, "price": 1, "product_id": 1,
                       "event_time": 1, "invalid_json": 1}:
            raise AssertionError(f"Flink invalid JSON/business reasons differ: {reasons}")
        self.quality_counts = counts
        return {"run_ids": [a, b], "kafka_offsets": 10, "flink_counts": counts,
                "flink_reasons": reasons,
                "job_id": job_id, "accepted_quantity": 8, "accepted_revenue": "9.50"}

    def late_test(self) -> dict:
        from sql.flink.test_events import build_window, send_raw

        run = self.run_id("late")
        fixture = self.path("late.jsonl")
        build_window(fixture, run)
        original = fixture.read_text(encoding="utf-8").splitlines()
        within = json.loads(original[2])
        within["transaction_id"] = f"{run}:line:within_watermark"
        within["event_time"] = "2024-01-01T00:01:18Z"  # 2 seconds behind 00:01:20; watermark allows 5.
        within["quantity"] = 1
        within["price"] = "1.00000000"
        within["line_revenue"] = "1.00"
        original.insert(3, json.dumps(within, sort_keys=True, separators=(",", ":")))
        fixture.write_text("\n".join(original) + "\n", encoding="utf-8")
        start_path = self.path("late_start.json")
        start = capture_offsets(start_path)
        job_id, _ = jdbc(self.run_id("late_job"), start_path)
        try:
            send_raw(fixture, "localhost:9094", TOPIC, 1, 3)
            sql = ("SELECT transaction_count,total_quantity,total_revenue FROM sales_by_store_minute "
                   f"WHERE run_id='{run}' AND store_id='S001' AND "
                   "window_start='2024-01-01 00:00:00+00'")
            first = wait_until(lambda: pg(sql) or None, timeout=45)
            if first != [["2", "3", "5.00"]]:
                raise AssertionError(f"first window differs: {first}")
            send_raw(fixture, "localhost:9094", TOPIC, 4, 1)
            wait_until(lambda: pg_totals(run)[1] == 4, timeout=30)
            send_raw(fixture, "localhost:9094", TOPIC, 5, 1)
            wait_until(lambda: pg_totals(run)[1] == 5, timeout=30)
            after_late = pg(sql)
            if after_late != first:
                raise AssertionError("late event changed a closed window")
            send_raw(fixture, "localhost:9094", TOPIC, 6, 5)
            wait_until(lambda: pg_totals(run)[1] == 10, timeout=30)
            within_sql = ("SELECT transaction_count,total_quantity,total_revenue FROM sales_by_store_minute "
                          f"WHERE run_id='{run}' AND store_id='S001' AND "
                          "window_start='2024-01-01 00:01:00+00'")
            within_window = wait_until(lambda: pg(within_sql) or None, timeout=30)
            if within_window != [["2", "4", "2.50"]]:
                raise AssertionError(f"within-watermark event was not retained: {within_window}")
            end = capture_offsets(self.path("late_end.json"))
            if offset_delta(start, end) != 10:
                raise AssertionError("late fixture Kafka offsets differ")
            store = pg_totals(run)
            if store[1:] != (10, 15, Decimal("26.50")):
                raise AssertionError(f"store total differs: {store}")
            product = pg_totals(run, "sales_by_store_product")
            if product[1:] != store[1:]:
                raise AssertionError(f"store/product did not retain the valid late event: {product}")
            return {"run_id": run, "job_id": job_id, "store": list(map(str, store)),
                    "store_product": list(map(str, product)),
                    "closed_window_before": first, "closed_window_after": after_late,
                    "within_watermark_window": within_window,
                    "late_counter": "not implemented; exclusion inferred from closed window"}
        finally:
            self.restarts.append(f"{utc_now()} TC05 stop savepoint: {stop_job(job_id)}")

    def producer_restart_test(self) -> dict:
        run = self.run_id("producer_resume")
        first, second = self.path("producer_first10.jsonl"), self.path("producer_next10.jsonl")
        split_jsonl(SAMPLE, first, 0, 10)
        split_jsonl(SAMPLE, second, 10, 10)
        start_path, end_path = self.path("producer_start.json"), self.path("producer_end.json")
        start = capture_offsets(start_path)
        one = publish(first, 10, run, self.path("producer_first_stats.json"))
        middle = capture_offsets(self.path("producer_mid.json"))
        two = publish(second, 10, run, self.path("producer_second_stats.json"))
        end = capture_offsets(end_path)
        if offset_delta(start, middle) != 10 or offset_delta(middle, end) != 10:
            raise AssertionError("Kafka segments did not match the saved source position")
        observed = kafka_probe(start, run, 20, SAMPLE)
        job_id, _ = jdbc(self.run_id("producer_job"), start_path, end_path)
        tables = database_check(SAMPLE, 20, run, replayed=True)
        self.validations.extend(tables)
        self.restarts.append(f"{utc_now()} TC06: process 1 ACK={one['delivered']} pending={one['pending']}; "
                             f"resume from source line 11; process 2 ACK={two['delivered']} "
                             f"pending={two['pending']}; Kafka/DB=20; job={job_id}")
        return {"run_id": run, "first_ack": 10, "second_ack": 10,
                "kafka_offsets": 20, "consumer": observed["consumed"],
                "db_count": tables[0]["actual_count"], "job_id": job_id,
                "mode": "controlled source-line resume; no crash/unacknowledged-message claim"}

    def recovery_fixture(self, run: str) -> Path:
        path = self.path("recovery_21.jsonl")
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        data = list(synthetic_rows(21, 73, run))
        with path.open("w", encoding="utf-8") as handle:
            for index, record in enumerate(data):
                record["store_id"] = "S001"
                record["event_time"] = (base + timedelta(minutes=index if index < 20 else 21)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
                handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        return path

    def flink_recovery_test(self) -> dict:
        run = self.run_id("restore")
        source = self.recovery_fixture(run)
        first, second = self.path("restore_first10.jsonl"), self.path("restore_next11.jsonl")
        split_jsonl(source, first, 0, 10)
        split_jsonl(source, second, 10, 11)
        start_path = self.path("restore_start.json")
        start = capture_offsets(start_path)
        job_id, _ = jdbc(self.run_id("restore_job"), start_path)
        active_job = job_id
        try:
            one = publish(first, 10, run, self.path("restore_first_stats.json"), rate=10)
            wait_until(lambda: pg_totals(run)[1] == 10, timeout=45)
            checkpoint = wait_until(
                lambda: (data if data["counts"]["completed"] > 0 else None)
                if (data := flink_rest(f"/jobs/{job_id}/checkpoints")) else None,
                timeout=45)
            checkpoint_id = checkpoint["latest"]["completed"]["id"]
            middle = capture_offsets(self.path("restore_mid.json"))
            savepoint = stop_job(job_id)
            self.restarts.append(f"{utc_now()} TC07 before restore: ACK=10 Kafka_delta={offset_delta(start,middle)} "
                                 f"DB_store=10 job={job_id} checkpoint={checkpoint_id} savepoint={savepoint}")
            active_job = ""
            restored_id, _ = jdbc(self.run_id("restored_job"), start_path, restore=savepoint)
            active_job = restored_id
            restored = wait_until(lambda: (data if data["counts"]["restored"] == 1 else None)
                                  if (data := flink_rest(f"/jobs/{restored_id}/checkpoints")) else None,
                                  timeout=30)
            two = publish(second, 11, run, self.path("restore_second_stats.json"), rate=10)
            wait_until(lambda: pg_totals(run)[1] == 21 and pg_totals(run, "sales_by_store_minute")[1] == 20,
                       timeout=45)
            end = capture_offsets(self.path("restore_end.json"))
            if offset_delta(start, end) != 21:
                raise AssertionError("21 ACKs do not match Kafka offset delta")
            observed = kafka_probe(start, run, 21, source)
            tables = database_check(source, 21, run, replayed=False,
                                    closed_before="2024-01-01T00:21:00+00:00")
            self.validations.extend(tables)
            self.restarts.append(f"{utc_now()} TC07 after restore: ACK={one['delivered']}+{two['delivered']} "
                                 f"Kafka=21 DB_store=21 closed_windows=20 restored=1 job={restored_id}; "
                                 "all three comparable aggregates match")
            return {"run_id": run, "first_job": job_id, "restored_job": restored_id,
                    "checkpoint_id": checkpoint_id, "savepoint": savepoint,
                    "restored_count": restored["counts"]["restored"],
                    "ack": 21, "consumer": observed["consumed"],
                    "store_count": tables[0]["actual_count"],
                    "closed_minute_count": tables[2]["actual_count"]}
        finally:
            if active_job:
                self.restarts.append(f"{utc_now()} TC07 cleanup savepoint: {stop_job(active_job)}")

    def postgres_restart_test(self) -> dict:
        if self.normal is None:
            raise RuntimeError("TC01 must pass before PostgreSQL restart")
        run = self.normal["run_id"]
        before = pg_totals(run)
        begin = utc_now()
        command(["docker", "restart", POSTGRES], timeout=60)
        wait_until(lambda: "healthy" in command(["docker", "inspect", "--format",
                                                  "{{.State.Health.Status}}", POSTGRES]).strip(), timeout=60)
        after = pg_totals(run)
        if before != after:
            raise AssertionError(f"PostgreSQL changed across restart: {before} -> {after}")
        tables = database_check(SAMPLE, 1000, run, replayed=True)
        self.restarts.append(f"{begin} TC08 PostgreSQL restart; {utc_now()} healthy; "
                             f"before={before}, after={after}; three tables reconciled")
        return {"run_id": run, "before": list(map(str, before)),
                "after": list(map(str, after)), "tables": [r["status"] for r in tables],
                "scope": "database persistence with no active Flink job"}

    def upsert_test(self) -> dict:
        if self.normal is None:
            raise RuntimeError("TC01 must pass before UPSERT rerun")
        run = self.normal["run_id"]
        before = [pg_totals(run, table) for table in
                  ("sales_by_store", "sales_by_store_product", "sales_by_store_minute")]
        job_id, _ = jdbc(self.run_id("upsert_job"), self.normal["start"], self.normal["end"])
        after = [pg_totals(run, table) for table in
                 ("sales_by_store", "sales_by_store_product", "sales_by_store_minute")]
        if before != after:
            raise AssertionError(f"rerun changed aggregate final state: {before} -> {after}")
        tables = database_check(SAMPLE, 1000, run, replayed=True)
        return {"run_id": run, "job_id": job_id, "rows_before_after":
                [[str(x[0]), str(y[0])] for x, y in zip(before, after)],
                "reconciliation": [r["status"] for r in tables]}

    def large_test(self) -> dict:
        if shutil.disk_usage(ROOT).free < 8 * 1024**3:
            raise SkipCase("less than 8 GiB free for optional 10,000-row test")
        run = self.run_id("tenk")
        start_path, end_path = self.path("tenk_start.json"), self.path("tenk_end.json")
        start = capture_offsets(start_path)
        stats = publish(SAMPLE, 10000, run, self.path("tenk_producer.json"))
        end = capture_offsets(end_path)
        if offset_delta(start, end) != 10000:
            raise AssertionError("10,000 ACKs differ from Kafka offset delta")
        observed = kafka_probe(start, run, 10000)
        job_id, state = jdbc(self.run_id("tenk_job"), start_path, end_path)
        tables = database_check(SAMPLE, 10000, run, replayed=True)
        self.validations.extend(tables)
        return {"run_id": run, "ack": stats["delivered"], "consumer": observed["consumed"],
                "payload_bytes": stats["payload_bytes"], "producer_seconds": stats["elapsed_seconds"],
                "job_id": job_id, "job_state": state, "quantity": tables[0]["actual_quantity"],
                "revenue": tables[0]["actual_revenue"]}

    def execute(self, selected: set[str]) -> None:
        plans = [
            (["TC01"], self.normal_test, ("Normal end-to-end 1,000", "synthetic_10000 first 1,000",
             "healthy local stack; isolated Kafka offsets", "capture, replay, probe, bounded JDBC, reconcile",
             "1,000 ACK/consumer/DB; quantity 2,985; revenue 310265.83; all three tables match")),
            (["TC02", "TC03", "TC04"], self.quality_test, ("Duplicate and invalid classification",
             "10-line raw fixture", "fresh offsets and two run IDs", "inject raw, Flink classify, JDBC, reconcile",
             "raw10 invalid5 duplicate1 accepted4 quantity8 revenue9.50; JSON/quantity/field/time errors")),
            (["TC05"], self.late_test, ("Late event and watermark", "10 controlled-time events",
             "unbounded JDBC job running", "send first3, observe closed window, send within-watermark, send late, send remaining5",
             "00:00 remains count2 revenue5.00; 00:01 includes out-of-order line; store receives all10")),
            (["TC06"], self.producer_restart_test, ("Producer controlled restart", "source lines 1-20",
             "saved source line position", "send 10, end process, resume next 10, probe, JDBC, reconcile",
             "ACK 10+10, Kafka20, DB20; no pending client queue")),
            (["TC07"], self.flink_recovery_test, ("Flink savepoint and restore", "21 ordered-time events",
             "unbounded job and checkpoint volume", "send10, checkpoint, savepoint, restore, send11, reconcile",
             "restored=1; ACK/Kafka21; DB21 and 20 closed windows correct")),
            (["TC08"], self.postgres_restart_test, ("PostgreSQL persistence restart", "TC01 database rows",
             "TC01 PASS; no active Flink job", "record before, restart container, wait healthy, reconcile",
             "before=after; three aggregate tables match source")),
            (["TC09"], self.upsert_test, ("JDBC UPSERT same-offset replay", "TC01 Kafka offsets",
             "TC01 PASS", "rerun bounded JDBC job on same offsets; compare three tables",
             "same rows/count/quantity/revenue; no duplicate PK")),
            (["TC10"], self.reconciliation_test, ("Data quality reconciliation", "TC01 + quality evidence",
             "prior cases completed", "check source counts and validation CSV",
             "raw=invalid+duplicate+unique; all row-level aggregates match")),
            (["TC11"], self.large_test, ("10,000-row regression", "synthetic_10000",
             "at least 8 GiB free", "capture, replay, probe, bounded JDBC, reconcile",
             "10,000 ACK/consumer/DB; three tables match independent source")),
        ]
        for ids, func, meta in plans:
            active = [test_id for test_id in ids if test_id in selected]
            if active:
                self.case(active, func, meta)

    def reconciliation_test(self) -> dict:
        if self.normal is None:
            raise RuntimeError("TC01 result unavailable")
        run = self.normal["run_id"]
        rows, counts = reconcile(SAMPLE, 1000, run, replayed=True)
        if counts["raw"] != counts["invalid"] + counts["duplicate"] + counts["valid"]:
            raise AssertionError("source quality categories are not exhaustive")
        if any(row["status"] != "PASS" for row in rows):
            raise AssertionError("a sink differs from source")
        if self.quality_counts is None or self.quality_counts["raw"] != (
            self.quality_counts["invalid"] + self.quality_counts["duplicate"]
            + self.quality_counts["unique_valid"]
        ):
            raise AssertionError("invalid/duplicate/valid categories are not exhaustive")
        if not self.validations:
            raise AssertionError("validation output is empty")
        missing = pg(f"SELECT (SELECT COUNT(*) FROM sales_by_store s LEFT JOIN stores d USING(store_id) "
                     f"WHERE s.run_id='{run}' AND d.store_id IS NULL), "
                     f"(SELECT COUNT(*) FROM sales_by_store_product s LEFT JOIN products d USING(product_id) "
                     f"WHERE s.run_id='{run}' AND d.product_id IS NULL)")[0]
        if missing != ["0", "0"]:
            raise AssertionError(f"dimension gaps: {missing}")
        currencies = [r[0] for r in pg(f"SELECT DISTINCT currency FROM sales_by_store "
                                       f"WHERE run_id='{run}' ORDER BY currency")]
        if currencies != ["USD"]:
            raise AssertionError(f"unexpected currency partitioning: {currencies}")
        precision = pg("SELECT table_name,numeric_precision,numeric_scale "
                       "FROM information_schema.columns WHERE table_schema='public' "
                       "AND table_name IN ('sales_by_store','sales_by_store_product','sales_by_store_minute') "
                       "AND column_name='total_revenue' ORDER BY table_name")
        if len(precision) != 3 or any(row[1:] != ["28", "2"] for row in precision):
            raise AssertionError(f"revenue NUMERIC precision differs: {precision}")
        return {"run_id": run, "raw": counts["raw"], "invalid": counts["invalid"],
                "duplicate": counts["duplicate"], "unique_valid": counts["valid"],
                "quality_fixture": self.quality_counts, "currencies": currencies,
                "dimension_gaps": missing, "revenue_precision": "NUMERIC(28,2)",
                "compared_sink_rows": len(rows)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", default=[f"TC{i:02d}" for i in range(1, 12)])
    parser.add_argument("--batch", default=datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:5])
    parser.add_argument("--publish-evidence", action="store_true")
    args = parser.parse_args()
    allowed = {f"TC{i:02d}" for i in range(1, 12)}
    if not set(args.cases) <= allowed:
        parser.error("unknown test case")
    try:
        state = readiness()
        print(json.dumps({"readiness": state, "batch": args.batch}, ensure_ascii=False), flush=True)
        suite = Stage07(args.batch)
        suite.execute(set(args.cases))
        if args.publish_evidence:
            suite.publish_evidence()
        failed = [row["test_id"] for row in suite.matrix if row["status"] == "FAIL"]
        print(json.dumps({"batch": args.batch, "failed": failed,
                          "matrix": str(suite.path("matrix.csv")),
                          "validation": str(suite.path("validation.csv"))}, ensure_ascii=False))
        return 1 if failed else 0
    except Exception as exc:
        print(f"Stage07 setup failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

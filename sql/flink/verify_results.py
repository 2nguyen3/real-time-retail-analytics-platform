"""Compare final Flink SQL changelog state with an independent JSONL audit."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from producer.audit_data import invalid_reason  # noqa: E402


ROW = re.compile(r"^\| (\+I|\+U|-U|-D) \|")
SCHEMA = json.loads((ROOT / "data/schema/transaction.schema.json").read_text())


def final_rows(path: Path, keys: tuple[int, ...]) -> dict[tuple[str, ...], tuple[str, ...]]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if not match:
            continue
        cells = tuple(cell.strip() for cell in line.strip().strip("|").split("|"))
        operation, values = cells[0], cells[1:]
        key = tuple(values[index] for index in keys)
        if operation in ("+I", "+U"):
            result[key] = values
        elif operation in ("-U", "-D"):
            result.pop(key, None)
    return result


def expected(path: Path, limit: int | None, run_id_override: str | None = None) -> dict:
    seen: set[tuple[str, str]] = set()
    counts = Counter()
    groups: dict[str, dict[tuple, list]] = {
        name: defaultdict(lambda: [0, 0, Decimal("0.00")])
        for name in ("totals", "store", "product", "store_product", "windows")
    }
    with path.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if limit is not None and index >= limit:
                break
            counts["raw"] += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                counts["invalid"] += 1
                continue
            if run_id_override is not None and isinstance(record, dict):
                record["run_id"] = run_id_override
            reason = invalid_reason(record, set(SCHEMA["required"]), None, set(SCHEMA["properties"]))
            if reason is not None:
                counts["invalid"] += 1
                continue
            counts["valid_before_dedup"] += 1
            identity = (record["run_id"], record["transaction_id"])
            if identity in seen:
                counts["duplicate"] += 1
                continue
            seen.add(identity)
            counts["unique_valid"] += 1
            revenue = Decimal(record["line_revenue"])
            minute = record["event_time"][:16].replace("T", " ") + ":00.000"
            for group, key in (
                ("totals", (record["run_id"],)),
                ("store", (record["run_id"], record["store_id"])),
                ("product", (record["run_id"], record["product_id"])),
                ("store_product", (record["run_id"], record["store_id"], record["product_id"])),
                ("windows", (record["run_id"], record["store_id"], minute)),
            ):
                total = groups[group][key]
                total[0] += 1
                total[1] += record["quantity"]
                total[2] += revenue
    return {"counts": dict(counts), "groups": groups}


def verify(name: str, source: Path, limit: int | None, queries: list[str], run_id_override: str | None = None) -> dict:
    root = ROOT / "reports/runtime/flink"
    reference = expected(source, limit, run_id_override)
    results = {"name": name, "source": str(source), "expected": reference["counts"], "checks": {}}
    indices = {"raw": (), "quality": (0,), "totals": (0,), "store": (0, 1),
               "product": (0, 1), "store_product": (0, 1, 2), "windows": (0, 1, 2)}
    for query in queries:
        actual = final_rows(root / f"{name}_{query}.log", indices[query])
        if query == "raw":
            passed = len(actual) == 1 and int(next(iter(actual.values()))[0]) == reference["counts"]["raw"]
        elif query == "quality":
            valid = int(actual.get(("valid",), ("valid", "0"))[1])
            invalid = sum(int(row[1]) for key, row in actual.items() if key != ("valid",))
            passed = valid == reference["counts"].get("valid_before_dedup", 0) and invalid == reference["counts"].get("invalid", 0)
        else:
            expected_groups = reference["groups"][query]
            passed = len(actual) == len(expected_groups)
            for key, expected_values in expected_groups.items():
                row = actual.get(key)
                if row is None or (int(row[-3]), int(row[-2]), Decimal(row[-1])) != tuple(expected_values):
                    passed = False
                    break
        results["checks"][query] = {"status": "PASS" if passed else "FAIL", "actual_groups": len(actual)}
    if {"raw", "quality", "totals"}.issubset(queries):
        raw = final_rows(root / f"{name}_raw.log", ())
        quality = final_rows(root / f"{name}_quality.log", (0,))
        totals = final_rows(root / f"{name}_totals.log", (0,))
        actual_counts = {
            "raw": int(next(iter(raw.values()))[0]),
            "valid_before_dedup": int(quality.get(("valid",), ("valid", "0"))[1]),
            "invalid": sum(int(row[1]) for key, row in quality.items() if key != ("valid",)),
            "unique_valid": sum(int(row[-3]) for row in totals.values()),
        }
        actual_counts["duplicate"] = actual_counts["valid_before_dedup"] - actual_counts["unique_valid"]
        results["actual_counts"] = actual_counts
        results["actual_totals_by_run"] = {
            run_id: {"transaction_count": int(row[-3]), "quantity": int(row[-2]),
                     "revenue": row[-1]}
            for (run_id,), row in totals.items()
        }
        results["expected_totals_by_run"] = {
            run_id: {"transaction_count": values[0], "quantity": values[1],
                     "revenue": f"{values[2]:.2f}"}
            for (run_id,), values in reference["groups"]["totals"].items()
        }
        results["checks"]["counts"] = {
            "status": "PASS" if all(actual_counts[k] == reference["counts"].get(k, 0) for k in actual_counts) else "FAIL"
        }
    results["test_status"] = "PASS" if all(x["status"] == "PASS" for x in results["checks"].values()) else "FAIL"
    return results


def verify_live_window(path: Path) -> dict:
    expected_rows = {
        "2024-01-01T00:00": (2, 3, Decimal("5.00")),
        "2024-01-01T00:01": (1, 3, Decimal("1.50")),
        "2024-01-01T00:02": (1, 1, Decimal("5.00")),
        "2024-01-01T00:03": (2, 3, Decimal("7.00")),
    }
    actual = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^stage05-window> \+I\[(.*)\]$", line)
        if not match:
            continue
        cells = [cell.strip() for cell in match.group(1).split(",")]
        if cells[0] != "stage05_window_live_01":
            continue
        start = cells[2]
        actual[start] = (int(cells[4]), int(cells[5]), Decimal(cells[6]))
    passed = actual == expected_rows
    return {"test_status": "PASS" if passed else "FAIL", "expected_windows":
            {key: [n, q, str(revenue)] for key, (n, q, revenue) in expected_rows.items()},
            "actual_windows": {key: [n, q, str(revenue)] for key, (n, q, revenue) in actual.items()},
            "late_event": "00:00:30 was sent after 00:00 window emitted; excluded from its final count"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--run-id-override", help="Run ID used by replay.py when publishing this source")
    parser.add_argument("--queries", nargs="+", choices=("raw", "quality", "totals", "store", "product", "store_product", "windows"))
    parser.add_argument("--live-window-log", type=Path)
    args = parser.parse_args()
    if args.live_window_log:
        result = verify_live_window(args.live_window_log)
        output = ROOT / "reports/runtime/flink/window_live_verification.json"
    else:
        if not args.name or not args.source or not args.queries:
            parser.error("--name, --source and --queries are required for bounded verification")
        result = verify(args.name, args.source, args.limit, args.queries, args.run_id_override)
        output = ROOT / "reports/runtime/flink" / f"{args.name}_verification.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["test_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

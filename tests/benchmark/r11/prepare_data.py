"""Build the R11 detail and pre-aggregated CSV files from one JSONL chunk, plus expected query results."""
import argparse
import csv
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

RUN_ID = "r11_c01"
DETAIL = ["run_id", "transaction_id", "store_id", "product_id", "quantity", "price",
          "line_revenue", "currency", "event_time"]
AGG = ["run_id", "store_id", "product_id", "currency", "transaction_count", "total_quantity", "total_revenue"]


def top10(groups: dict) -> list:
    ranked = sorted(groups.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    return [[key, str(value)] for key, value in ranked]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    agg = defaultdict(lambda: [0, 0, Decimal("0")])
    by_product, by_store = defaultdict(Decimal), defaultdict(Decimal)
    seen, rows, quantity, revenue = set(), 0, 0, Decimal("0")
    with args.input.open(encoding="utf-8") as source, \
            (args.out / "tx_detail.csv").open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target, lineterminator="\n")
        for line in source:
            record = json.loads(line)
            record["run_id"] = RUN_ID
            writer.writerow([record[name] for name in DETAIL])
            amount = Decimal(record["line_revenue"])
            cell = agg[(record["store_id"], record["product_id"], record["currency"])]
            cell[0] += 1
            cell[1] += record["quantity"]
            cell[2] += amount
            by_product[record["product_id"]] += amount
            by_store[record["store_id"]] += amount
            seen.add(record["transaction_id"])
            rows += 1
            quantity += record["quantity"]
            revenue += amount

    if len(seen) != rows:
        raise SystemExit("duplicate transaction_id in source")
    with (args.out / "agg_store_product.csv").open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target, lineterminator="\n")
        for key in sorted(agg):
            writer.writerow([RUN_ID, *key, *agg[key]])

    expected = {
        "run_id": RUN_ID, "detail_rows": rows, "agg_rows": len(agg),
        "q1": {"transaction_count": rows, "total_quantity": quantity, "total_revenue": str(revenue)},
        "q2_top10_products": top10(by_product), "q3_top10_stores": top10(by_store),
        "detail_columns": DETAIL, "agg_columns": AGG,
    }
    (args.out / "expected.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    print(json.dumps({k: expected[k] for k in ("detail_rows", "agg_rows", "q1")}))
    print("reduction: %.2fx fewer rows" % (rows / len(agg)))
    for name in ("tx_detail.csv", "agg_store_product.csv"):
        print(name, (args.out / name).stat().st_size, "bytes")


if __name__ == "__main__":
    main()

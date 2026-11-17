"""Seed observed store/product IDs from a small JSONL sample through psql COPY."""

from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent


def observed(path: Path, limit: int | None) -> tuple[dict[str, str | None], dict[str, str | None], list[tuple]]:
    stores: dict[str, str | None] = {}
    products: dict[str, str | None] = {}
    rows = []
    with path.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if limit is not None and index >= limit:
                break
            record = json.loads(line)
            store_id, product_id = record["store_id"], record["product_id"]
            region, category = record.get("store_region"), record.get("category_id")
            for mapping, key, value in ((stores, store_id, region), (products, product_id, category)):
                old = mapping.get(key)
                if old is not None and value is not None and old != value:
                    raise ValueError(f"conflicting attributes for ID {key}")
                mapping[key] = old or value
            rows.append((store_id, region, product_id, category))
    if not rows:
        raise ValueError("source has no rows")
    return stores, products, rows


def seed(path: Path, limit: int | None) -> dict:
    stores, products, rows = observed(path, limit)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows(rows)
    sql = """BEGIN;
CREATE TEMP TABLE stage06_dimension_input (
  store_id TEXT NOT NULL, store_region TEXT, product_id TEXT NOT NULL, category_id TEXT
);
COPY stage06_dimension_input (store_id, store_region, product_id, category_id) FROM STDIN WITH (FORMAT csv);
""" + buffer.getvalue() + "\\.\n" + (HERE / "02_seed_dimensions.sql").read_text(encoding="utf-8") + "\nCOMMIT;\n"
    result = subprocess.run(
        ["docker", "exec", "-i", "retail-local-postgres-1", "sh", "-c",
         'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'],
        input=sql.encode("utf-8"), capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
    return {"source_rows": len(rows), "distinct_stores": len(stores),
            "distinct_products": len(products), "status": "PASS"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("limit must be positive")
    try:
        print(json.dumps(seed(args.input, args.limit), sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"dimension seed failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate eval and run metrics by experiment variant from the SQLite query store.")
    parser.add_argument("--db", default="logs/harness/query_store.sqlite")
    parser.add_argument("--experiment-id", default="", help="Optional experiment id filter.")
    parser.add_argument("--output", default="logs/query_store/variant_metrics.json")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"query store not found: {db_path}")

    where_clause = ""
    params: tuple[object, ...] = ()
    if args.experiment_id:
        where_clause = "WHERE experiment_id = ?"
        params = (args.experiment_id,)

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT variant,
                   COUNT(*) AS eval_count,
                   ROUND(AVG(score), 2) AS avg_score,
                   SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) AS passed_count
            FROM eval_results
            {where_clause}
            GROUP BY variant
            ORDER BY variant
            """,
            params,
        ).fetchall()

    payload = {
        "db_path": str(db_path),
        "experiment_id": args.experiment_id,
        "variants": [
            {
                "variant": row[0],
                "eval_count": row[1],
                "average_score": row[2] or 0.0,
                "passed_count": row[3] or 0,
            }
            for row in rows
        ],
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

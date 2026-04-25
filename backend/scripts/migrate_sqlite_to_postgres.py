#!/usr/bin/env python3
"""Copy data from a local SQLite WeeFarm DB to a Postgres database.

Usage:
  TARGET_DATABASE_URL='postgresql+psycopg://...' \
  python3 backend/scripts/migrate_sqlite_to_postgres.py \
    --source backend/weefarm.db
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine


TABLE_ORDER = [
    "cooperatives",
    "users",
    "products",
    "members",
    "fields",
    "stocks",
    "batches",
    "process_steps",
    "inputs",
    "recommendations",
    "reference_metrics",
    "knowledge_chunks",
    "ml_training_runs",
    "ml_model_registry",
    "ml_prediction_logs",
    "ml_recommendation_logs",
    "recommendation_feedback_logs",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate local SQLite WeeFarm data to Postgres.")
    parser.add_argument(
        "--source",
        default="backend/weefarm.db",
        help="Path to source SQLite file (default: backend/weefarm.db)",
    )
    parser.add_argument(
        "--target-url",
        default="",
        help="Target Postgres URL. If omitted, uses TARGET_DATABASE_URL env var.",
    )
    return parser.parse_args()


def quote_cols(columns: list[str]) -> str:
    return ", ".join(f'"{name}"' for name in columns)


def build_sqlite_engine(source_path: Path) -> Engine:
    if not source_path.exists():
        raise FileNotFoundError(f"SQLite source not found: {source_path}")
    return create_engine(f"sqlite:///{source_path.resolve()}")


def truncate_target_tables(target_engine: Engine, table_names: list[str]) -> None:
    with target_engine.begin() as conn:
        for table_name in reversed(table_names):
            conn.execute(text(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY CASCADE'))


def copy_table(source_engine: Engine, target_engine: Engine, table_name: str) -> int:
    src_inspector = inspect(source_engine)
    tgt_inspector = inspect(target_engine)

    source_columns = [c["name"] for c in src_inspector.get_columns(table_name)]
    target_columns = [c["name"] for c in tgt_inspector.get_columns(table_name)]
    common_columns = [name for name in source_columns if name in target_columns]

    if not common_columns:
        return 0

    select_sql = text(f'SELECT {quote_cols(common_columns)} FROM "{table_name}"')
    insert_placeholders = ", ".join(f":{name}" for name in common_columns)
    insert_sql = text(
        f'INSERT INTO "{table_name}" ({quote_cols(common_columns)}) VALUES ({insert_placeholders})'
    )

    with source_engine.connect() as source_conn:
        rows = source_conn.execute(select_sql).mappings().all()

    if not rows:
        return 0

    with target_engine.begin() as target_conn:
        target_conn.execute(insert_sql, rows)

    return len(rows)


def main() -> None:
    args = parse_args()
    target_url = args.target_url.strip()
    if not target_url:
        import os

        target_url = os.getenv("TARGET_DATABASE_URL", "").strip()

    if not target_url:
        raise ValueError(
            "Missing target database URL. Pass --target-url or set TARGET_DATABASE_URL."
        )

    source_path = Path(args.source)
    source_engine = build_sqlite_engine(source_path)
    target_engine = create_engine(target_url, pool_pre_ping=True)

    target_tables = set(inspect(target_engine).get_table_names())
    tables_to_migrate = [name for name in TABLE_ORDER if name in target_tables]

    if not tables_to_migrate:
        raise RuntimeError("No matching target tables found. Run Alembic migrations first.")

    truncate_target_tables(target_engine, tables_to_migrate)

    total = 0
    for table_name in tables_to_migrate:
        count = copy_table(source_engine, target_engine, table_name)
        total += count
        print(f"{table_name}: {count} rows")

    print(f"Done. Migrated {total} rows from {source_path}.")


if __name__ == "__main__":
    main()

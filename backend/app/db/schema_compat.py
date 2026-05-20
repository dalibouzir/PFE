from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_engine


BATCHES_ADDS = [
    "ADD COLUMN IF NOT EXISTS member_id UUID",
    "ADD COLUMN IF NOT EXISTS parcel_id UUID",
    "ADD COLUMN IF NOT EXISTS surface_ha DOUBLE PRECISION",
    "ADD COLUMN IF NOT EXISTS expected_yield_kg_per_ha DOUBLE PRECISION",
    "ADD COLUMN IF NOT EXISTS expected_losses_kg DOUBLE PRECISION",
    "ADD COLUMN IF NOT EXISTS estimated_qty_kg DOUBLE PRECISION",
    "ADD COLUMN IF NOT EXISTS estimated_qty_override_reason TEXT",
    "ADD COLUMN IF NOT EXISTS estimated_charge_fcfa DOUBLE PRECISION",
    "ADD COLUMN IF NOT EXISTS charge_approved_at TIMESTAMPTZ",
    "ADD COLUMN IF NOT EXISTS charge_approved_by_user_id UUID",
    "ADD COLUMN IF NOT EXISTS preharvest_activated_at TIMESTAMPTZ",
    "ADD COLUMN IF NOT EXISTS preharvest_step_statuses JSONB",
    "ADD COLUMN IF NOT EXISTS confirmed_weight_kg DOUBLE PRECISION",
    "ADD COLUMN IF NOT EXISTS preharvest_completed_at TIMESTAMPTZ",
    "ADD COLUMN IF NOT EXISTS postharvest_started_at TIMESTAMPTZ",
    "ADD COLUMN IF NOT EXISTS postharvest_reference VARCHAR(80)",
    "ADD COLUMN IF NOT EXISTS status_note TEXT",
]

INPUTS_ADDS = [
    "ADD COLUMN IF NOT EXISTS batch_id UUID",
    "ADD COLUMN IF NOT EXISTS source_type VARCHAR(64) DEFAULT 'manual_collecte' NOT NULL",
    "ADD COLUMN IF NOT EXISTS collecte_reference VARCHAR(80)",
]

FARMER_ADVANCES_ADDS = [
    "ADD COLUMN IF NOT EXISTS batch_id UUID",
    "ADD COLUMN IF NOT EXISTS parcel_id UUID",
    "ADD COLUMN IF NOT EXISTS product_id UUID",
    "ADD COLUMN IF NOT EXISTS source_type VARCHAR(80) DEFAULT 'manual' NOT NULL",
    "ADD COLUMN IF NOT EXISTS devis_file_id UUID",
]

TREASURY_TRANSACTIONS_ADDS = [
    "ADD COLUMN IF NOT EXISTS justificatif_file_id UUID",
    "ADD COLUMN IF NOT EXISTS receipt_reference VARCHAR(120)",
]

STOCKS_ADDS = [
    "ADD COLUMN IF NOT EXISTS grade VARCHAR(40) DEFAULT 'Non spécifié' NOT NULL",
]

STOCK_MOVEMENTS_ADDS = [
    "ADD COLUMN IF NOT EXISTS movement_reference VARCHAR(80)",
    "ADD COLUMN IF NOT EXISTS grade VARCHAR(40) DEFAULT 'Non spécifié' NOT NULL",
]


def ensure_runtime_schema_compat() -> None:
    """Emergency compatibility patch for environments where migrations lag behind code.

    This keeps API endpoints alive (notably dashboard) until alembic upgrade is run.
    """
    engine = get_engine()
    dialect = engine.dialect.name
    if dialect != "postgresql":
        return

    try:
        with engine.begin() as conn:
            inspector = inspect(conn)
            tables = set(inspector.get_table_names())
            if "batches" in tables:
                for ddl in BATCHES_ADDS:
                    conn.execute(text(f"ALTER TABLE batches {ddl}"))
            if "inputs" in tables:
                for ddl in INPUTS_ADDS:
                    conn.execute(text(f"ALTER TABLE inputs {ddl}"))
            if "farmer_advances" in tables:
                for ddl in FARMER_ADVANCES_ADDS:
                    conn.execute(text(f"ALTER TABLE farmer_advances {ddl}"))
            if "treasury_transactions" in tables:
                for ddl in TREASURY_TRANSACTIONS_ADDS:
                    conn.execute(text(f"ALTER TABLE treasury_transactions {ddl}"))
            if "stock_movements" in tables:
                for ddl in STOCK_MOVEMENTS_ADDS:
                    conn.execute(text(f"ALTER TABLE stock_movements {ddl}"))
            if "stocks" in tables:
                for ddl in STOCKS_ADDS:
                    conn.execute(text(f"ALTER TABLE stocks {ddl}"))
    except SQLAlchemyError as exc:
        # Keep API startup alive when DB is temporarily unreachable; endpoints that
        # require DB will still fail with explicit DB errors until connectivity returns.
        print(f"[schema_compat] skipped: {exc}")

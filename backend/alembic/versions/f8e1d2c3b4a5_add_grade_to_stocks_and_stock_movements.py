"""add grade-aware stock and stock movement buckets

Revision ID: f8e1d2c3b4a5
Revises: 6f7e8d9c1a22, 7a4d2e1c9b88, b6f2c1a4d9e0
Create Date: 2026-05-20 10:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f8e1d2c3b4a5"
down_revision = ("6f7e8d9c1a22", "7a4d2e1c9b88", "b6f2c1a4d9e0")
branch_labels = None
depends_on = None


DEFAULT_GRADE = "Non spécifié"


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    return (
        conn.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND column_name = :column_name
                LIMIT 1
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        ).first()
        is not None
    )


def _constraint_exists(conn, table_name: str, constraint_name: str) -> bool:
    return (
        conn.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = 'public'
                  AND t.relname = :table_name
                  AND c.conname = :constraint_name
                LIMIT 1
                """
            ),
            {"table_name": table_name, "constraint_name": constraint_name},
        ).first()
        is not None
    )


def _index_exists(conn, index_name: str) -> bool:
    return (
        conn.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND indexname = :index_name
                LIMIT 1
                """
            ),
            {"index_name": index_name},
        ).first()
        is not None
    )


def _raise_if_duplicate_grade_buckets(conn) -> None:
    rows = conn.execute(
        sa.text(
            """
            SELECT cooperative_id, product_id, COALESCE(NULLIF(BTRIM(grade), ''), :default_grade) AS grade_norm, COUNT(*) AS row_count
            FROM stocks
            GROUP BY cooperative_id, product_id, COALESCE(NULLIF(BTRIM(grade), ''), :default_grade)
            HAVING COUNT(*) > 1
            ORDER BY row_count DESC
            LIMIT 20
            """
        ),
        {"default_grade": DEFAULT_GRADE},
    ).fetchall()
    if rows:
        details = "; ".join(f"{r[0]}/{r[1]}/{r[2]} count={r[3]}" for r in rows)
        raise RuntimeError(
            "Cannot enforce unique (cooperative_id, product_id, grade): duplicate grade buckets found. "
            f"Examples: {details}"
        )


def upgrade() -> None:
    conn = op.get_bind()
    # Fail fast on lock waits instead of burning statement_timeout.
    conn.execute(sa.text("SET LOCAL lock_timeout = '10s'"))

    if not _column_exists(conn, "stocks", "grade"):
        op.add_column(
            "stocks",
            sa.Column("grade", sa.String(length=40), nullable=True),
        )
    conn.execute(
        sa.text(
            """
            UPDATE stocks
            SET grade = :default_grade
            WHERE grade IS NULL OR BTRIM(grade) = ''
            """
        ),
        {"default_grade": DEFAULT_GRADE},
    )
    op.alter_column("stocks", "grade", server_default=DEFAULT_GRADE, nullable=False)
    _raise_if_duplicate_grade_buckets(conn)

    if not _index_exists(conn, "uq_stocks_cooperative_product_grade_idx"):
        with op.get_context().autocommit_block():
            op.execute(
                sa.text(
                    """
                    CREATE UNIQUE INDEX CONCURRENTLY uq_stocks_cooperative_product_grade_idx
                    ON stocks (cooperative_id, product_id, grade)
                    """
                )
            )

    if _constraint_exists(conn, "stocks", "uq_stocks_cooperative_product"):
        op.drop_constraint("uq_stocks_cooperative_product", "stocks", type_="unique")
    if not _constraint_exists(conn, "stocks", "uq_stocks_cooperative_product_grade"):
        op.execute(
            sa.text(
                """
                ALTER TABLE stocks
                ADD CONSTRAINT uq_stocks_cooperative_product_grade
                UNIQUE USING INDEX uq_stocks_cooperative_product_grade_idx
                """
            )
        )

    if not _column_exists(conn, "stock_movements", "grade"):
        op.add_column(
            "stock_movements",
            sa.Column("grade", sa.String(length=40), nullable=True),
        )
    conn.execute(
        sa.text(
            """
            UPDATE stock_movements sm
            SET grade = COALESCE(NULLIF(BTRIM(i.grade), ''), :default_grade)
            FROM inputs i
            WHERE sm.input_id = i.id
              AND (sm.grade IS NULL OR BTRIM(sm.grade) = '')
            """
        ),
        {"default_grade": DEFAULT_GRADE},
    )
    conn.execute(
        sa.text(
            """
            UPDATE stock_movements
            SET grade = :default_grade
            WHERE grade IS NULL OR BTRIM(grade) = ''
            """
        ),
        {"default_grade": DEFAULT_GRADE},
    )
    op.alter_column("stock_movements", "grade", server_default=DEFAULT_GRADE, nullable=False)


def downgrade() -> None:
    conn = op.get_bind()
    if _column_exists(conn, "stock_movements", "grade"):
        op.drop_column("stock_movements", "grade")

    if _constraint_exists(conn, "stocks", "uq_stocks_cooperative_product_grade"):
        op.drop_constraint("uq_stocks_cooperative_product_grade", "stocks", type_="unique")
    if _index_exists(conn, "uq_stocks_cooperative_product_grade_idx"):
        with op.get_context().autocommit_block():
            op.execute(sa.text("DROP INDEX CONCURRENTLY IF EXISTS uq_stocks_cooperative_product_grade_idx"))
    if not _constraint_exists(conn, "stocks", "uq_stocks_cooperative_product"):
        op.create_unique_constraint(
            "uq_stocks_cooperative_product",
            "stocks",
            ["cooperative_id", "product_id"],
        )
    if _column_exists(conn, "stocks", "grade"):
        op.drop_column("stocks", "grade")

"""fix treasury status width and stock movement process step FK

Revision ID: aa4f6c2d9e10
Revises: b6f2c1a4d9e0, e5f7a9b1c3d4
Create Date: 2026-05-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "aa4f6c2d9e10"
down_revision: Union[str, Sequence[str], None] = ("b6f2c1a4d9e0", "e5f7a9b1c3d4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_fk(inspector, table_name: str, constrained_column: str, referred_table: str) -> bool:
    for fk in inspector.get_foreign_keys(table_name):
        constrained = fk.get("constrained_columns") or []
        if constrained_column in constrained and fk.get("referred_table") == referred_table:
            return True
    return False


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Runtime DBs may still have short varchar status width from earlier states.
    op.alter_column(
        "treasury_transactions",
        "status",
        existing_type=sa.String(length=9),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
    # Keep reference comfortably wide for generated IDs and future formats.
    op.alter_column(
        "treasury_transactions",
        "reference",
        existing_type=sa.String(length=40),
        type_=sa.String(length=64),
        existing_nullable=False,
    )

    if not _has_column(inspector, "stock_movements", "process_step_id"):
        op.add_column("stock_movements", sa.Column("process_step_id", sa.Uuid(), nullable=True))

    if not _has_fk(inspector, "stock_movements", "process_step_id", "process_steps"):
        op.create_foreign_key(
            op.f("fk_stock_movements_process_step_id_process_steps"),
            "stock_movements",
            "process_steps",
            ["process_step_id"],
            ["id"],
            ondelete="SET NULL",
        )

    index_name = op.f("ix_stock_movements_process_step_id")
    if not _has_index(inspector, "stock_movements", index_name):
        op.create_index(index_name, "stock_movements", ["process_step_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    index_name = op.f("ix_stock_movements_process_step_id")
    if _has_index(inspector, "stock_movements", index_name):
        op.drop_index(index_name, table_name="stock_movements")

    if _has_fk(inspector, "stock_movements", "process_step_id", "process_steps"):
        op.drop_constraint(
            op.f("fk_stock_movements_process_step_id_process_steps"),
            "stock_movements",
            type_="foreignkey",
        )

    if _has_column(inspector, "stock_movements", "process_step_id"):
        op.drop_column("stock_movements", "process_step_id")

    op.alter_column(
        "treasury_transactions",
        "reference",
        existing_type=sa.String(length=64),
        type_=sa.String(length=40),
        existing_nullable=False,
    )
    op.alter_column(
        "treasury_transactions",
        "status",
        existing_type=sa.String(length=32),
        type_=sa.String(length=9),
        existing_nullable=False,
    )

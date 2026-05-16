"""treasury statuses justificatif and locking fields

Revision ID: e5f7a9b1c3d4
Revises: d4e6f8a1b2c3
Create Date: 2026-05-16 22:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f7a9b1c3d4"
down_revision: Union[str, None] = "d4e6f8a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def _has_fk(inspector, table_name: str, fk_name: str) -> bool:
    return any((fk.get("name") or "") == fk_name for fk in inspector.get_foreign_keys(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "treasury_transactions", "justificatif_file_id"):
        op.add_column("treasury_transactions", sa.Column("justificatif_file_id", sa.Uuid(), nullable=True))
    if not _has_column(inspector, "treasury_transactions", "receipt_reference"):
        op.add_column("treasury_transactions", sa.Column("receipt_reference", sa.String(length=120), nullable=True))

    index_name = op.f("ix_treasury_transactions_justificatif_file_id")
    if not _has_index(inspector, "treasury_transactions", index_name):
        op.create_index(index_name, "treasury_transactions", ["justificatif_file_id"], unique=False)

    fk_name = op.f("fk_treasury_transactions_justificatif_file_id_uploaded_files")
    if not _has_fk(inspector, "treasury_transactions", fk_name):
        op.create_foreign_key(
            fk_name,
            "treasury_transactions",
            "uploaded_files",
            ["justificatif_file_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # Legacy DBs can still have status as varchar(9), which cannot store
    # the normalized values written below.
    op.alter_column(
        "treasury_transactions",
        "status",
        existing_type=sa.String(length=9),
        type_=sa.String(length=32),
        existing_nullable=False,
    )

    op.execute(
        """
        UPDATE treasury_transactions
        SET status = CASE
            WHEN status = 'RECORDED' THEN 'enregistre_sans_justificatif'
            WHEN status = 'recorded' THEN 'enregistre_sans_justificatif'
            WHEN status = 'CANCELLED' THEN 'cancelled'
            WHEN status = 'cancelled' THEN 'cancelled'
            ELSE status
        END
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE treasury_transactions
        SET status = CASE
            WHEN status = 'ENREGISTRE_COMPLET' THEN 'recorded'
            WHEN status = 'ENREGISTRE_SANS_JUSTIFICATIF' THEN 'recorded'
            WHEN status = 'NON_ENREGISTRE' THEN 'recorded'
            WHEN status IN ('non_enregistre','enregistre_sans_justificatif','enregistre_complet') THEN 'recorded'
            WHEN status = 'CANCELLED' THEN 'cancelled'
            WHEN status = 'cancelled' THEN 'cancelled'
            ELSE status
        END
        """
    )
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    fk_name = op.f("fk_treasury_transactions_justificatif_file_id_uploaded_files")
    if _has_fk(inspector, "treasury_transactions", fk_name):
        op.drop_constraint(fk_name, "treasury_transactions", type_="foreignkey")

    index_name = op.f("ix_treasury_transactions_justificatif_file_id")
    if _has_index(inspector, "treasury_transactions", index_name):
        op.drop_index(index_name, table_name="treasury_transactions")

    if _has_column(inspector, "treasury_transactions", "receipt_reference"):
        op.drop_column("treasury_transactions", "receipt_reference")
    if _has_column(inspector, "treasury_transactions", "justificatif_file_id"):
        op.drop_column("treasury_transactions", "justificatif_file_id")

"""add farmer advance devis uploaded file link

Revision ID: d4e6f8a1b2c3
Revises: c9f1a2b3d4e5
Create Date: 2026-05-16 20:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e6f8a1b2c3"
down_revision: Union[str, None] = "c9f1a2b3d4e5"
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

    if not _has_column(inspector, "farmer_advances", "devis_file_id"):
        op.add_column("farmer_advances", sa.Column("devis_file_id", sa.Uuid(), nullable=True))

    index_name = op.f("ix_farmer_advances_devis_file_id")
    if not _has_index(inspector, "farmer_advances", index_name):
        op.create_index(index_name, "farmer_advances", ["devis_file_id"], unique=False)

    fk_name = op.f("fk_farmer_advances_devis_file_id_uploaded_files")
    if not _has_fk(inspector, "farmer_advances", fk_name):
        op.create_foreign_key(
            fk_name,
            "farmer_advances",
            "uploaded_files",
            ["devis_file_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    fk_name = op.f("fk_farmer_advances_devis_file_id_uploaded_files")
    if _has_fk(inspector, "farmer_advances", fk_name):
        op.drop_constraint(fk_name, "farmer_advances", type_="foreignkey")

    index_name = op.f("ix_farmer_advances_devis_file_id")
    if _has_index(inspector, "farmer_advances", index_name):
        op.drop_index(index_name, table_name="farmer_advances")

    if _has_column(inspector, "farmer_advances", "devis_file_id"):
        op.drop_column("farmer_advances", "devis_file_id")

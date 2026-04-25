"""extend member profile fields

Revision ID: e2d7a41c9a6f
Revises: 6a2e9f4b7d11
Create Date: 2026-04-18 16:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e2d7a41c9a6f"
down_revision: Union[str, None] = "6a2e9f4b7d11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table)
    return any(item["name"] == column for item in columns)


def upgrade() -> None:
    if not _column_exists("members", "village"):
        op.add_column("members", sa.Column("village", sa.String(length=120), nullable=True))
    if not _column_exists("members", "main_product"):
        op.add_column("members", sa.Column("main_product", sa.String(length=120), nullable=True))
    if not _column_exists("members", "parcel_count"):
        op.add_column("members", sa.Column("parcel_count", sa.Integer(), nullable=False, server_default="0"))
    if not _column_exists("members", "area_hectares"):
        op.add_column("members", sa.Column("area_hectares", sa.Float(), nullable=False, server_default="0"))
    if not _column_exists("members", "join_date"):
        op.add_column("members", sa.Column("join_date", sa.Date(), nullable=True))


def downgrade() -> None:
    if _column_exists("members", "join_date"):
        op.drop_column("members", "join_date")
    if _column_exists("members", "area_hectares"):
        op.drop_column("members", "area_hectares")
    if _column_exists("members", "parcel_count"):
        op.drop_column("members", "parcel_count")
    if _column_exists("members", "main_product"):
        op.drop_column("members", "main_product")
    if _column_exists("members", "village"):
        op.drop_column("members", "village")

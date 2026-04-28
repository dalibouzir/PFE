"""add member secondary products

Revision ID: b8c2a4f3d7e1
Revises: a1f6b2c8d901
Create Date: 2026-04-27 19:25:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8c2a4f3d7e1"
down_revision: Union[str, None] = "a1f6b2c8d901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(item["name"] == column for item in inspector.get_columns(table))


def upgrade() -> None:
    if not _column_exists("members", "secondary_products"):
        op.add_column("members", sa.Column("secondary_products", sa.String(length=500), nullable=True))


def downgrade() -> None:
    if _column_exists("members", "secondary_products"):
        op.drop_column("members", "secondary_products")

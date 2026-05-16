"""add preharvest activated marker to batches

Revision ID: 5d9a2c7e4b11
Revises: 2c4b8f1a9d22
Create Date: 2026-05-16
"""

from alembic import op
import sqlalchemy as sa


revision = "5d9a2c7e4b11"
down_revision = "2c4b8f1a9d22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("batches", sa.Column("preharvest_activated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("batches", "preharvest_activated_at")

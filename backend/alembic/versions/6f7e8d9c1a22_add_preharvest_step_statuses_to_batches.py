"""add preharvest step statuses to batches

Revision ID: 6f7e8d9c1a22
Revises: 5d9a2c7e4b11
Create Date: 2026-05-16
"""

from alembic import op
import sqlalchemy as sa


revision = "6f7e8d9c1a22"
down_revision = "5d9a2c7e4b11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("batches", sa.Column("preharvest_step_statuses", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("batches", "preharvest_step_statuses")

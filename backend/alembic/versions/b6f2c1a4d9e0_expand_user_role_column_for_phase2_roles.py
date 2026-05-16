"""expand user role column for phase2 roles

Revision ID: b6f2c1a4d9e0
Revises: 9d3a1b7c4e22
Create Date: 2026-05-16 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b6f2c1a4d9e0"
down_revision = "9d3a1b7c4e22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "role",
        existing_type=sa.String(length=7),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "role",
        existing_type=sa.String(length=32),
        type_=sa.String(length=7),
        existing_nullable=False,
        postgresql_using="left(role, 7)",
    )

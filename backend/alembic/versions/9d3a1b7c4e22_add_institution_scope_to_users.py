"""add institution scope to users

Revision ID: 9d3a1b7c4e22
Revises: 7a4d2e1c9b88
Create Date: 2026-05-16 14:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d3a1b7c4e22"
down_revision: Union[str, None] = "7a4d2e1c9b88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("institution_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_users_institution_id"), "users", ["institution_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_users_institution_id_institutions"),
        "users",
        "institutions",
        ["institution_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_users_institution_id_institutions"), "users", type_="foreignkey")
    op.drop_index(op.f("ix_users_institution_id"), table_name="users")
    op.drop_column("users", "institution_id")

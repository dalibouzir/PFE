"""add institutions and cooperative institution fk

Revision ID: 4b1a7c9d2e3f
Revises: 1f3e5a7b9c21
Create Date: 2026-05-16 12:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4b1a7c9d2e3f"
down_revision: Union[str, None] = "1f3e5a7b9c21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "institutions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institutions")),
    )
    op.create_index(op.f("ix_institutions_name"), "institutions", ["name"], unique=True)

    op.add_column("cooperatives", sa.Column("institution_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_cooperatives_institution_id"), "cooperatives", ["institution_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_cooperatives_institution_id_institutions"),
        "cooperatives",
        "institutions",
        ["institution_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_cooperatives_institution_id_institutions"), "cooperatives", type_="foreignkey")
    op.drop_index(op.f("ix_cooperatives_institution_id"), table_name="cooperatives")
    op.drop_column("cooperatives", "institution_id")

    op.drop_index(op.f("ix_institutions_name"), table_name="institutions")
    op.drop_table("institutions")

"""add farmer advances and treasury tables

Revision ID: f1b7c3d9e4a2
Revises: c4d9f1a6b8e2
Create Date: 2026-04-21 16:55:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1b7c3d9e4a2"
down_revision: Union[str, None] = "c4d9f1a6b8e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "treasury_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cooperative_id", sa.Uuid(), nullable=False),
        sa.Column("reference", sa.String(length=40), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("INCOME", "EXPENSE", name="treasurytransactiontype", native_enum=False),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("amount_fcfa", sa.Float(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("RECORDED", "CANCELLED", name="treasurytransactionstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("farmer_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["cooperative_id"],
            ["cooperatives.id"],
            name=op.f("fk_treasury_transactions_cooperative_id_cooperatives"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["farmer_id"],
            ["members.id"],
            name=op.f("fk_treasury_transactions_farmer_id_members"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_treasury_transactions")),
        sa.UniqueConstraint("reference", name=op.f("uq_treasury_transactions_reference")),
    )
    op.create_index(op.f("ix_treasury_transactions_cooperative_id"), "treasury_transactions", ["cooperative_id"], unique=False)
    op.create_index(op.f("ix_treasury_transactions_farmer_id"), "treasury_transactions", ["farmer_id"], unique=False)
    op.create_index(op.f("ix_treasury_transactions_source_id"), "treasury_transactions", ["source_id"], unique=False)
    op.create_index(op.f("ix_treasury_transactions_source_type"), "treasury_transactions", ["source_type"], unique=False)
    op.create_index(op.f("ix_treasury_transactions_transaction_date"), "treasury_transactions", ["transaction_date"], unique=False)

    op.create_table(
        "farmer_advances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cooperative_id", sa.Uuid(), nullable=False),
        sa.Column("farmer_id", sa.Uuid(), nullable=False),
        sa.Column("amount_fcfa", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("advance_date", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "CANCELLED", name="farmeradvancestatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("treasury_transaction_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["cooperative_id"],
            ["cooperatives.id"],
            name=op.f("fk_farmer_advances_cooperative_id_cooperatives"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["farmer_id"],
            ["members.id"],
            name=op.f("fk_farmer_advances_farmer_id_members"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["treasury_transaction_id"],
            ["treasury_transactions.id"],
            name=op.f("fk_farmer_advances_treasury_transaction_id_treasury_transactions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_farmer_advances")),
        sa.UniqueConstraint("treasury_transaction_id", name=op.f("uq_farmer_advances_treasury_transaction_id")),
    )
    op.create_index(op.f("ix_farmer_advances_advance_date"), "farmer_advances", ["advance_date"], unique=False)
    op.create_index(op.f("ix_farmer_advances_cooperative_id"), "farmer_advances", ["cooperative_id"], unique=False)
    op.create_index(op.f("ix_farmer_advances_farmer_id"), "farmer_advances", ["farmer_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_farmer_advances_farmer_id"), table_name="farmer_advances")
    op.drop_index(op.f("ix_farmer_advances_cooperative_id"), table_name="farmer_advances")
    op.drop_index(op.f("ix_farmer_advances_advance_date"), table_name="farmer_advances")
    op.drop_table("farmer_advances")

    op.drop_index(op.f("ix_treasury_transactions_transaction_date"), table_name="treasury_transactions")
    op.drop_index(op.f("ix_treasury_transactions_source_type"), table_name="treasury_transactions")
    op.drop_index(op.f("ix_treasury_transactions_source_id"), table_name="treasury_transactions")
    op.drop_index(op.f("ix_treasury_transactions_farmer_id"), table_name="treasury_transactions")
    op.drop_index(op.f("ix_treasury_transactions_cooperative_id"), table_name="treasury_transactions")
    op.drop_table("treasury_transactions")

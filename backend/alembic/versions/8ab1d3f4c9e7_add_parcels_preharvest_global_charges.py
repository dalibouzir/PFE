"""add parcels, pre-harvest steps, and global charges

Revision ID: 8ab1d3f4c9e7
Revises: 7c9d2e4a1b3f
Create Date: 2026-04-30 16:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8ab1d3f4c9e7"
down_revision: Union[str, None] = "7c9d2e4a1b3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(col["name"] == column_name for col in columns)


def upgrade() -> None:
    if not _column_exists("members", "notes"):
        op.add_column("members", sa.Column("notes", sa.Text(), nullable=True))

    op.create_table(
        "parcels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cooperative_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("surface_ha", sa.Float(), nullable=False),
        sa.Column("main_culture", sa.String(length=120), nullable=False),
        sa.Column("variety", sa.String(length=120), nullable=True),
        sa.Column("tree_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cooperative_id"], ["cooperatives.id"], name=op.f("fk_parcels_cooperative_id_cooperatives"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], name=op.f("fk_parcels_member_id_members"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parcels")),
    )
    op.create_index(op.f("ix_parcels_cooperative_id"), "parcels", ["cooperative_id"], unique=False)
    op.create_index(op.f("ix_parcels_member_id"), "parcels", ["member_id"], unique=False)

    op.create_table(
        "pre_harvest_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cooperative_id", sa.Uuid(), nullable=False),
        sa.Column("parcel_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_key", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("icon", sa.String(length=16), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "COMPLETED", name="preharveststepstatus", native_enum=False), nullable=False),
        sa.Column("quantity_value", sa.Float(), nullable=True),
        sa.Column("quantity_unit", sa.String(length=32), nullable=True),
        sa.Column("operation_cost_fcfa", sa.Float(), nullable=True),
        sa.Column("realization_date", sa.Date(), nullable=True),
        sa.Column("observations", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cooperative_id"], ["cooperatives.id"], name=op.f("fk_pre_harvest_steps_cooperative_id_cooperatives"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name=op.f("fk_pre_harvest_steps_created_by_user_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], name=op.f("fk_pre_harvest_steps_member_id_members"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], name=op.f("fk_pre_harvest_steps_parcel_id_parcels"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], name=op.f("fk_pre_harvest_steps_updated_by_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pre_harvest_steps")),
    )
    op.create_index(op.f("ix_pre_harvest_steps_cooperative_id"), "pre_harvest_steps", ["cooperative_id"], unique=False)
    op.create_index(op.f("ix_pre_harvest_steps_member_id"), "pre_harvest_steps", ["member_id"], unique=False)
    op.create_index(op.f("ix_pre_harvest_steps_parcel_id"), "pre_harvest_steps", ["parcel_id"], unique=False)

    op.create_table(
        "global_charges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cooperative_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("parcel_id", sa.Uuid(), nullable=True),
        sa.Column("pre_harvest_step_id", sa.Uuid(), nullable=True),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("process_step_id", sa.Uuid(), nullable=True),
        sa.Column("charge_type", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("amount_fcfa", sa.Float(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("treasury_transaction_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], name=op.f("fk_global_charges_batch_id_batches"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cooperative_id"], ["cooperatives.id"], name=op.f("fk_global_charges_cooperative_id_cooperatives"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], name=op.f("fk_global_charges_member_id_members"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], name=op.f("fk_global_charges_parcel_id_parcels"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pre_harvest_step_id"], ["pre_harvest_steps.id"], name=op.f("fk_global_charges_pre_harvest_step_id_pre_harvest_steps"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["process_step_id"], ["process_steps.id"], name=op.f("fk_global_charges_process_step_id_process_steps"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["treasury_transaction_id"], ["treasury_transactions.id"], name=op.f("fk_global_charges_treasury_transaction_id_treasury_transactions"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_global_charges")),
        sa.UniqueConstraint("treasury_transaction_id", name=op.f("uq_global_charges_treasury_transaction_id")),
    )
    op.create_index(op.f("ix_global_charges_batch_id"), "global_charges", ["batch_id"], unique=False)
    op.create_index(op.f("ix_global_charges_cooperative_id"), "global_charges", ["cooperative_id"], unique=False)
    op.create_index(op.f("ix_global_charges_member_id"), "global_charges", ["member_id"], unique=False)
    op.create_index(op.f("ix_global_charges_parcel_id"), "global_charges", ["parcel_id"], unique=False)
    op.create_index(op.f("ix_global_charges_pre_harvest_step_id"), "global_charges", ["pre_harvest_step_id"], unique=False)
    op.create_index(op.f("ix_global_charges_process_step_id"), "global_charges", ["process_step_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_global_charges_process_step_id"), table_name="global_charges")
    op.drop_index(op.f("ix_global_charges_pre_harvest_step_id"), table_name="global_charges")
    op.drop_index(op.f("ix_global_charges_parcel_id"), table_name="global_charges")
    op.drop_index(op.f("ix_global_charges_member_id"), table_name="global_charges")
    op.drop_index(op.f("ix_global_charges_cooperative_id"), table_name="global_charges")
    op.drop_index(op.f("ix_global_charges_batch_id"), table_name="global_charges")
    op.drop_table("global_charges")

    op.drop_index(op.f("ix_pre_harvest_steps_parcel_id"), table_name="pre_harvest_steps")
    op.drop_index(op.f("ix_pre_harvest_steps_member_id"), table_name="pre_harvest_steps")
    op.drop_index(op.f("ix_pre_harvest_steps_cooperative_id"), table_name="pre_harvest_steps")
    op.drop_table("pre_harvest_steps")

    op.drop_index(op.f("ix_parcels_member_id"), table_name="parcels")
    op.drop_index(op.f("ix_parcels_cooperative_id"), table_name="parcels")
    op.drop_table("parcels")

    if _column_exists("members", "notes"):
        op.drop_column("members", "notes")

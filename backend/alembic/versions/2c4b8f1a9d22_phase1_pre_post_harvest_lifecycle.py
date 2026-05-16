"""phase1 pre/post harvest lifecycle

Revision ID: 2c4b8f1a9d22
Revises: c4d9f1a6b8e2
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa


revision = "2c4b8f1a9d22"
down_revision = "c4d9f1a6b8e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("batches", sa.Column("member_id", sa.Uuid(), nullable=True))
    op.add_column("batches", sa.Column("parcel_id", sa.Uuid(), nullable=True))
    op.add_column("batches", sa.Column("surface_ha", sa.Float(), nullable=True))
    op.add_column("batches", sa.Column("expected_yield_kg_ha", sa.Float(), nullable=True))
    op.add_column("batches", sa.Column("expected_losses_kg", sa.Float(), nullable=True))
    op.add_column("batches", sa.Column("estimated_qty_kg", sa.Float(), nullable=True))
    op.add_column("batches", sa.Column("estimated_qty_override_kg", sa.Float(), nullable=True))
    op.add_column("batches", sa.Column("estimated_qty_override_reason", sa.Text(), nullable=True))
    op.add_column("batches", sa.Column("estimated_charge_fcfa", sa.Float(), nullable=True))
    op.add_column("batches", sa.Column("charge_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("batches", sa.Column("charge_advance_id", sa.Uuid(), nullable=True))
    op.add_column("batches", sa.Column("preharvest_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("batches", sa.Column("confirmed_weight_kg", sa.Float(), nullable=True))
    op.add_column("batches", sa.Column("collecte_input_id", sa.Uuid(), nullable=True))
    op.add_column("batches", sa.Column("preharvest_notes", sa.Text(), nullable=True))
    op.create_index(op.f("ix_batches_member_id"), "batches", ["member_id"], unique=False)
    op.create_index(op.f("ix_batches_parcel_id"), "batches", ["parcel_id"], unique=False)
    op.create_unique_constraint("uq_batches_charge_advance_id", "batches", ["charge_advance_id"])
    op.create_unique_constraint("uq_batches_collecte_input_id", "batches", ["collecte_input_id"])
    op.create_foreign_key(op.f("fk_batches_member_id_members"), "batches", "members", ["member_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key(op.f("fk_batches_parcel_id_parcels"), "batches", "parcels", ["parcel_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key(op.f("fk_batches_charge_advance_id_farmer_advances"), "batches", "farmer_advances", ["charge_advance_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key(op.f("fk_batches_collecte_input_id_inputs"), "batches", "inputs", ["collecte_input_id"], ["id"], ondelete="SET NULL")

    op.add_column("inputs", sa.Column("batch_id", sa.Uuid(), nullable=True))
    op.add_column("inputs", sa.Column("source_type", sa.String(length=64), nullable=False, server_default="manual"))
    op.create_index(op.f("ix_inputs_batch_id"), "inputs", ["batch_id"], unique=False)
    op.create_foreign_key(op.f("fk_inputs_batch_id_batches"), "inputs", "batches", ["batch_id"], ["id"], ondelete="SET NULL")

    op.add_column("farmer_advances", sa.Column("batch_id", sa.Uuid(), nullable=True))
    op.add_column("farmer_advances", sa.Column("parcel_id", sa.Uuid(), nullable=True))
    op.add_column("farmer_advances", sa.Column("product_id", sa.Uuid(), nullable=True))
    op.add_column("farmer_advances", sa.Column("source_type", sa.String(length=64), nullable=False, server_default="manual"))
    op.create_index(op.f("ix_farmer_advances_batch_id"), "farmer_advances", ["batch_id"], unique=False)
    op.create_index(op.f("ix_farmer_advances_parcel_id"), "farmer_advances", ["parcel_id"], unique=False)
    op.create_index(op.f("ix_farmer_advances_product_id"), "farmer_advances", ["product_id"], unique=False)
    op.create_foreign_key(op.f("fk_farmer_advances_batch_id_batches"), "farmer_advances", "batches", ["batch_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key(op.f("fk_farmer_advances_parcel_id_parcels"), "farmer_advances", "parcels", ["parcel_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key(op.f("fk_farmer_advances_product_id_products"), "farmer_advances", "products", ["product_id"], ["id"], ondelete="SET NULL")

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cooperative_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("input_id", sa.Uuid(), nullable=True),
        sa.Column("process_step_id", sa.Uuid(), nullable=True),
        sa.Column("movement_type", sa.String(length=16), nullable=False),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("source_type", sa.String(length=120), nullable=False),
        sa.Column("quantity_kg", sa.Float(), nullable=False),
        sa.Column("movement_date", sa.Date(), nullable=False),
        sa.Column("external_key", sa.String(length=160), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cooperative_id"], ["cooperatives.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["input_id"], ["inputs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["process_step_id"], ["process_steps.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_movements")),
        sa.UniqueConstraint("external_key", name="uq_stock_movements_external_key"),
    )
    op.create_index(op.f("ix_stock_movements_batch_id"), "stock_movements", ["batch_id"], unique=False)
    op.create_index(op.f("ix_stock_movements_cooperative_id"), "stock_movements", ["cooperative_id"], unique=False)
    op.create_index(op.f("ix_stock_movements_external_key"), "stock_movements", ["external_key"], unique=False)
    op.create_index(op.f("ix_stock_movements_input_id"), "stock_movements", ["input_id"], unique=False)
    op.create_index(op.f("ix_stock_movements_process_step_id"), "stock_movements", ["process_step_id"], unique=False)
    op.create_index(op.f("ix_stock_movements_product_id"), "stock_movements", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_stock_movements_product_id"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_process_step_id"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_input_id"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_external_key"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_cooperative_id"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_batch_id"), table_name="stock_movements")
    op.drop_table("stock_movements")

    op.drop_constraint(op.f("fk_farmer_advances_product_id_products"), "farmer_advances", type_="foreignkey")
    op.drop_constraint(op.f("fk_farmer_advances_parcel_id_parcels"), "farmer_advances", type_="foreignkey")
    op.drop_constraint(op.f("fk_farmer_advances_batch_id_batches"), "farmer_advances", type_="foreignkey")
    op.drop_index(op.f("ix_farmer_advances_product_id"), table_name="farmer_advances")
    op.drop_index(op.f("ix_farmer_advances_parcel_id"), table_name="farmer_advances")
    op.drop_index(op.f("ix_farmer_advances_batch_id"), table_name="farmer_advances")
    op.drop_column("farmer_advances", "source_type")
    op.drop_column("farmer_advances", "product_id")
    op.drop_column("farmer_advances", "parcel_id")
    op.drop_column("farmer_advances", "batch_id")

    op.drop_constraint(op.f("fk_inputs_batch_id_batches"), "inputs", type_="foreignkey")
    op.drop_index(op.f("ix_inputs_batch_id"), table_name="inputs")
    op.drop_column("inputs", "source_type")
    op.drop_column("inputs", "batch_id")

    op.drop_constraint(op.f("fk_batches_collecte_input_id_inputs"), "batches", type_="foreignkey")
    op.drop_constraint(op.f("fk_batches_charge_advance_id_farmer_advances"), "batches", type_="foreignkey")
    op.drop_constraint(op.f("fk_batches_parcel_id_parcels"), "batches", type_="foreignkey")
    op.drop_constraint(op.f("fk_batches_member_id_members"), "batches", type_="foreignkey")
    op.drop_constraint("uq_batches_collecte_input_id", "batches", type_="unique")
    op.drop_constraint("uq_batches_charge_advance_id", "batches", type_="unique")
    op.drop_index(op.f("ix_batches_parcel_id"), table_name="batches")
    op.drop_index(op.f("ix_batches_member_id"), table_name="batches")
    op.drop_column("batches", "preharvest_notes")
    op.drop_column("batches", "collecte_input_id")
    op.drop_column("batches", "confirmed_weight_kg")
    op.drop_column("batches", "preharvest_completed_at")
    op.drop_column("batches", "charge_advance_id")
    op.drop_column("batches", "charge_approved_at")
    op.drop_column("batches", "estimated_charge_fcfa")
    op.drop_column("batches", "estimated_qty_override_reason")
    op.drop_column("batches", "estimated_qty_override_kg")
    op.drop_column("batches", "estimated_qty_kg")
    op.drop_column("batches", "expected_losses_kg")
    op.drop_column("batches", "expected_yield_kg_ha")
    op.drop_column("batches", "surface_ha")
    op.drop_column("batches", "parcel_id")
    op.drop_column("batches", "member_id")

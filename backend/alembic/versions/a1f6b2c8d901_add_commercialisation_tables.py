"""add commercialisation tables

Revision ID: a1f6b2c8d901
Revises: d3e8b92a1f07
Create Date: 2026-04-25 17:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1f6b2c8d901"
down_revision: Union[str, None] = "d3e8b92a1f07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COMMERCIAL_CATALOG_STATUS = sa.Enum("active", "hidden", name="commercialcatalogstatus", native_enum=False)
COMMERCIAL_ORDER_STATUS = sa.Enum(
    "received",
    "confirmed",
    "preparing",
    "ready",
    "delivered",
    "paid",
    "refused",
    name="commercialorderstatus",
    native_enum=False,
)
INVOICE_STATUS = sa.Enum("pending", "paid", name="invoicestatus", native_enum=False)


def upgrade() -> None:
    op.create_table(
        "commercial_catalog_products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cooperative_id", sa.Uuid(), nullable=False),
        sa.Column("source_product_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("sale_unit", sa.String(length=40), nullable=False),
        sa.Column("icon", sa.String(length=32), nullable=True),
        sa.Column("sale_price_fcfa", sa.Float(), nullable=False),
        sa.Column("cost_price_fcfa", sa.Float(), nullable=False),
        sa.Column("min_order_qty", sa.Float(), nullable=False),
        sa.Column("total_stock_kg", sa.Float(), nullable=False),
        sa.Column("reserved_stock_kg", sa.Float(), nullable=False),
        sa.Column("status", COMMERCIAL_CATALOG_STATUS, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cooperative_id"], ["cooperatives.id"], name=op.f("fk_commercial_catalog_products_cooperative_id_cooperatives"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_product_id"], ["products.id"], name=op.f("fk_commercial_catalog_products_source_product_id_products"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commercial_catalog_products")),
        sa.UniqueConstraint("cooperative_id", "name", name="uq_catalog_product_name_per_cooperative"),
    )
    op.create_index(op.f("ix_commercial_catalog_products_cooperative_id"), "commercial_catalog_products", ["cooperative_id"], unique=False)
    op.create_index(op.f("ix_commercial_catalog_products_source_product_id"), "commercial_catalog_products", ["source_product_id"], unique=False)

    op.create_table(
        "commercial_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cooperative_id", sa.Uuid(), nullable=False),
        sa.Column("order_number", sa.String(length=40), nullable=False),
        sa.Column("customer_name", sa.String(length=160), nullable=False),
        sa.Column("customer_phone", sa.String(length=32), nullable=True),
        sa.Column("customer_email", sa.String(length=160), nullable=True),
        sa.Column("customer_address", sa.String(length=255), nullable=True),
        sa.Column("payment_method", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", COMMERCIAL_ORDER_STATUS, nullable=False),
        sa.Column("subtotal_fcfa", sa.Float(), nullable=False),
        sa.Column("tax_rate", sa.Float(), nullable=False),
        sa.Column("tax_amount_fcfa", sa.Float(), nullable=False),
        sa.Column("total_amount_fcfa", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preparing_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refused_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cooperative_id"], ["cooperatives.id"], name=op.f("fk_commercial_orders_cooperative_id_cooperatives"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commercial_orders")),
        sa.UniqueConstraint("order_number", name=op.f("uq_commercial_orders_order_number")),
    )
    op.create_index(op.f("ix_commercial_orders_cooperative_id"), "commercial_orders", ["cooperative_id"], unique=False)
    op.create_index(op.f("ix_commercial_orders_order_number"), "commercial_orders", ["order_number"], unique=False)
    op.create_index(op.f("ix_commercial_orders_status"), "commercial_orders", ["status"], unique=False)

    op.create_table(
        "commercial_order_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("catalog_product_id", sa.Uuid(), nullable=False),
        sa.Column("product_name_snapshot", sa.String(length=120), nullable=False),
        sa.Column("unit_snapshot", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("quantity_kg", sa.Float(), nullable=False),
        sa.Column("unit_price_fcfa", sa.Float(), nullable=False),
        sa.Column("line_total_fcfa", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["catalog_product_id"], ["commercial_catalog_products.id"], name=op.f("fk_commercial_order_lines_catalog_product_id_commercial_catalog_products"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["commercial_orders.id"], name=op.f("fk_commercial_order_lines_order_id_commercial_orders"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commercial_order_lines")),
    )
    op.create_index(op.f("ix_commercial_order_lines_catalog_product_id"), "commercial_order_lines", ["catalog_product_id"], unique=False)
    op.create_index(op.f("ix_commercial_order_lines_order_id"), "commercial_order_lines", ["order_id"], unique=False)

    op.create_table(
        "commercial_invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cooperative_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_number", sa.String(length=40), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", INVOICE_STATUS, nullable=False),
        sa.Column("customer_name_snapshot", sa.String(length=160), nullable=False),
        sa.Column("customer_phone_snapshot", sa.String(length=32), nullable=True),
        sa.Column("customer_email_snapshot", sa.String(length=160), nullable=True),
        sa.Column("customer_address_snapshot", sa.String(length=255), nullable=True),
        sa.Column("subtotal_fcfa", sa.Float(), nullable=False),
        sa.Column("tax_rate", sa.Float(), nullable=False),
        sa.Column("tax_amount_fcfa", sa.Float(), nullable=False),
        sa.Column("total_amount_fcfa", sa.Float(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cooperative_id"], ["cooperatives.id"], name=op.f("fk_commercial_invoices_cooperative_id_cooperatives"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["commercial_orders.id"], name=op.f("fk_commercial_invoices_order_id_commercial_orders"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commercial_invoices")),
        sa.UniqueConstraint("invoice_number", name=op.f("uq_commercial_invoices_invoice_number")),
        sa.UniqueConstraint("order_id", name=op.f("uq_commercial_invoices_order_id")),
    )
    op.create_index(op.f("ix_commercial_invoices_cooperative_id"), "commercial_invoices", ["cooperative_id"], unique=False)
    op.create_index(op.f("ix_commercial_invoices_invoice_number"), "commercial_invoices", ["invoice_number"], unique=False)
    op.create_index(op.f("ix_commercial_invoices_issue_date"), "commercial_invoices", ["issue_date"], unique=False)
    op.create_index(op.f("ix_commercial_invoices_order_id"), "commercial_invoices", ["order_id"], unique=False)
    op.create_index(op.f("ix_commercial_invoices_status"), "commercial_invoices", ["status"], unique=False)

    op.create_table(
        "commercial_invoice_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.String(length=120), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit_price_fcfa", sa.Float(), nullable=False),
        sa.Column("line_total_fcfa", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["commercial_invoices.id"], name=op.f("fk_commercial_invoice_lines_invoice_id_commercial_invoices"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commercial_invoice_lines")),
    )
    op.create_index(op.f("ix_commercial_invoice_lines_invoice_id"), "commercial_invoice_lines", ["invoice_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_commercial_invoice_lines_invoice_id"), table_name="commercial_invoice_lines")
    op.drop_table("commercial_invoice_lines")

    op.drop_index(op.f("ix_commercial_invoices_status"), table_name="commercial_invoices")
    op.drop_index(op.f("ix_commercial_invoices_order_id"), table_name="commercial_invoices")
    op.drop_index(op.f("ix_commercial_invoices_issue_date"), table_name="commercial_invoices")
    op.drop_index(op.f("ix_commercial_invoices_invoice_number"), table_name="commercial_invoices")
    op.drop_index(op.f("ix_commercial_invoices_cooperative_id"), table_name="commercial_invoices")
    op.drop_table("commercial_invoices")

    op.drop_index(op.f("ix_commercial_order_lines_order_id"), table_name="commercial_order_lines")
    op.drop_index(op.f("ix_commercial_order_lines_catalog_product_id"), table_name="commercial_order_lines")
    op.drop_table("commercial_order_lines")

    op.drop_index(op.f("ix_commercial_orders_status"), table_name="commercial_orders")
    op.drop_index(op.f("ix_commercial_orders_order_number"), table_name="commercial_orders")
    op.drop_index(op.f("ix_commercial_orders_cooperative_id"), table_name="commercial_orders")
    op.drop_table("commercial_orders")

    op.drop_index(op.f("ix_commercial_catalog_products_source_product_id"), table_name="commercial_catalog_products")
    op.drop_index(op.f("ix_commercial_catalog_products_cooperative_id"), table_name="commercial_catalog_products")
    op.drop_table("commercial_catalog_products")

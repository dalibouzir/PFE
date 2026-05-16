from sqlalchemy import select

from app.models.commercial_catalog_product import CommercialCatalogProduct
from app.models.commercial_invoice import CommercialInvoice
from app.models.commercial_order import CommercialOrder
from app.models.enums import CommercialOrderStatus, InvoiceStatus, TreasuryTransactionStatus, TreasuryTransactionType
from app.models.product import Product
from app.models.stock import Stock
from app.models.stock_movement import StockMovement
from app.models.treasury_transaction import TreasuryTransaction
from app.models.user import User
from app.schemas.commercial import (
    CatalogProductCreate,
    CommercialOrderIntake,
    CommercialOrderStatusUpdate,
    OrderLineCreate,
)
from app.services import commercial as commercial_service


def test_catalog_order_invoice_payment_flow(db_session):
    manager = db_session.scalar(select(User).where(User.email == "manager@test.local"))
    product = db_session.scalar(select(Product).where(Product.name == "mango"))
    stock = db_session.scalar(select(Stock).where(Stock.product_id == product.id))

    assert manager is not None
    assert product is not None
    assert stock is not None
    assert stock.total_stock_kg == 500.0

    catalog = commercial_service.create_catalog_product(
        db_session,
        manager,
        CatalogProductCreate(
            source_product_id=product.id,
            name="Mangue Kent Premium",
            description="Produit premium",
            category="Fruits",
            sale_unit="kg",
            sale_price_fcfa=320,
            cost_price_fcfa=240,
            min_order_qty=5,
            allocated_quantity=100,
        ),
    )

    stock = db_session.scalar(select(Stock).where(Stock.product_id == product.id))
    assert stock.total_stock_kg == 400.0
    allocation_movement = db_session.scalar(
        select(StockMovement).where(
            StockMovement.product_id == product.id,
            StockMovement.source == "commercial_catalog",
            StockMovement.action_type == "commercial_catalog_allocation",
            StockMovement.movement_type == "out",
        )
    )
    assert allocation_movement is not None
    assert allocation_movement.quantity_kg == 100.0

    order = commercial_service.intake_order(
        db_session,
        manager,
        CommercialOrderIntake(
            customer_name="Awa Diop",
            customer_phone="+221774450000",
            payment_method="Mobile Money",
            lines=[OrderLineCreate(catalog_product_id=catalog.id, quantity=20)],
        ),
    )

    assert order.status == "received"

    order = commercial_service.update_order_status(
        db_session,
        manager,
        order.id,
        CommercialOrderStatusUpdate(status="confirmed"),
    )
    assert order.status == "confirmed"

    catalog_row = db_session.scalar(select(CommercialCatalogProduct).where(CommercialCatalogProduct.id == catalog.id))
    assert catalog_row is not None
    assert catalog_row.reserved_stock_kg == 20.0

    order = commercial_service.update_order_status(
        db_session,
        manager,
        order.id,
        CommercialOrderStatusUpdate(status="preparing"),
    )
    assert order.status == "preparing"

    order = commercial_service.update_order_status(
        db_session,
        manager,
        order.id,
        CommercialOrderStatusUpdate(status="ready"),
    )
    assert order.status == "ready"

    order = commercial_service.update_order_status(
        db_session,
        manager,
        order.id,
        CommercialOrderStatusUpdate(status="delivered"),
    )
    assert order.status == "delivered"

    catalog_row = db_session.scalar(select(CommercialCatalogProduct).where(CommercialCatalogProduct.id == catalog.id))
    assert catalog_row is not None
    assert catalog_row.total_stock_kg == 80.0
    assert catalog_row.reserved_stock_kg == 0.0

    invoice = db_session.scalar(select(CommercialInvoice).where(CommercialInvoice.order_id == order.id))
    assert invoice is not None
    assert invoice.status == InvoiceStatus.PENDING

    order = commercial_service.update_order_status(
        db_session,
        manager,
        order.id,
        CommercialOrderStatusUpdate(status="paid"),
    )
    assert order.status == CommercialOrderStatus.PAID.value

    invoice = db_session.scalar(select(CommercialInvoice).where(CommercialInvoice.order_id == order.id))
    assert invoice is not None
    assert invoice.status == InvoiceStatus.PAID

    treasury = db_session.scalar(
        select(TreasuryTransaction).where(
            TreasuryTransaction.source_type == "commercial_invoice",
            TreasuryTransaction.type == TreasuryTransactionType.INCOME,
        )
    )
    assert treasury is not None
    assert treasury.status == TreasuryTransactionStatus.ENREGISTRE_COMPLET
    assert treasury.receipt_reference == invoice.invoice_number

    # Idempotency guard: repeating "paid" should not duplicate invoice, lines, or treasury income
    order = commercial_service.update_order_status(
        db_session,
        manager,
        order.id,
        CommercialOrderStatusUpdate(status="paid"),
    )
    assert order.status == CommercialOrderStatus.PAID.value

    invoice_rows = db_session.scalars(select(CommercialInvoice).where(CommercialInvoice.order_id == order.id)).all()
    assert len(invoice_rows) == 1
    assert invoice_rows[0].status == InvoiceStatus.PAID
    assert len(invoice_rows[0].lines) == len(order.lines)

    treasury_rows = db_session.scalars(
        select(TreasuryTransaction).where(
            TreasuryTransaction.source_type == "commercial_invoice",
            TreasuryTransaction.type == TreasuryTransactionType.INCOME,
            TreasuryTransaction.source_id == invoice_rows[0].id,
            TreasuryTransaction.status != TreasuryTransactionStatus.CANCELLED,
        )
    ).all()
    assert len(treasury_rows) == 1
    assert treasury_rows[0].status == TreasuryTransactionStatus.ENREGISTRE_COMPLET

    # Create and remove an unused catalog product to validate stock journal IN release logging
    catalog_unused = commercial_service.create_catalog_product(
        db_session,
        manager,
        CatalogProductCreate(
            source_product_id=product.id,
            name="Mangue Kent Secondaire",
            description="Produit secondaire",
            category="Fruits",
            sale_unit="kg",
            sale_price_fcfa=300,
            cost_price_fcfa=220,
            min_order_qty=5,
            allocated_quantity=30,
        ),
    )
    deleted_catalog = commercial_service.delete_catalog_product(db_session, manager, catalog_unused.id)
    assert deleted_catalog.id == catalog_unused.id

    release_movement = db_session.scalar(
        select(StockMovement).where(
            StockMovement.product_id == product.id,
            StockMovement.source == "commercial_catalog",
            StockMovement.action_type == "commercial_catalog_release",
            StockMovement.movement_type == "in",
            StockMovement.quantity_kg == 30.0,
        )
    )
    assert release_movement is not None

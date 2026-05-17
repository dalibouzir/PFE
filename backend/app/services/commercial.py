from __future__ import annotations

import uuid
from collections import Counter
from datetime import date
from datetime import timedelta

from sqlalchemy import extract, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.commercial_catalog_product import CommercialCatalogProduct
from app.models.commercial_invoice import CommercialInvoice, CommercialInvoiceLine
from app.models.commercial_order import CommercialOrder, CommercialOrderLine
from app.models.enums import (
    CommercialCatalogStatus,
    CommercialOrderStatus,
    InvoiceStatus,
    TreasuryTransactionStatus,
    TreasuryTransactionType,
)
from app.models.mixins import current_utc
from app.models.product import Product
from app.models.stock import Stock
from app.models.stock_movement import StockMovement
from app.models.treasury_transaction import TreasuryTransaction
from app.models.user import User
from app.schemas.commercial import (
    CatalogProductRead,
    CommercialInvoiceLineRead,
    CommercialInvoiceRead,
    CommercialInvoiceStats,
    CommercialOrderLineRead,
    CommercialOrderRead,
    CommercialOrderStats,
)
from app.services.helpers import (
    from_kg,
    get_manager_cooperative_id,
    normalize_mass_unit,
    parse_enum_value,
    round_metric,
    to_kg,
)
from app.services.rag_reindex_hooks import reindex_commercial_if_needed
from app.services.stocks import apply_reserved_stock_delta, available_stock_kg
from app.utils.exceptions import NotFoundError, ValidationError

ORDER_TRANSITIONS: dict[CommercialOrderStatus, set[CommercialOrderStatus]] = {
    CommercialOrderStatus.RECEIVED: {CommercialOrderStatus.CONFIRMED, CommercialOrderStatus.REFUSED},
    CommercialOrderStatus.CONFIRMED: {CommercialOrderStatus.PREPARING, CommercialOrderStatus.REFUSED},
    CommercialOrderStatus.PREPARING: {CommercialOrderStatus.READY, CommercialOrderStatus.REFUSED},
    CommercialOrderStatus.READY: {CommercialOrderStatus.DELIVERED, CommercialOrderStatus.REFUSED},
    CommercialOrderStatus.DELIVERED: {CommercialOrderStatus.PAID},
    CommercialOrderStatus.PAID: set(),
    CommercialOrderStatus.REFUSED: set(),
}


def _catalog_available_kg(item: CommercialCatalogProduct) -> float:
    return round_metric(max(item.total_stock_kg - item.reserved_stock_kg, 0.0))


def _catalog_low_stock(item: CommercialCatalogProduct) -> bool:
    min_order_kg = to_kg(item.min_order_qty, item.sale_unit)
    threshold_kg = max(min_order_kg, round_metric(item.total_stock_kg * 0.1))
    return _catalog_available_kg(item) <= threshold_kg


def _margin_percent(item: CommercialCatalogProduct) -> float:
    if item.sale_price_fcfa <= 0:
        return 0.0
    return round_metric(((item.sale_price_fcfa - item.cost_price_fcfa) / item.sale_price_fcfa) * 100.0)


def _serialize_catalog(item: CommercialCatalogProduct) -> CatalogProductRead:
    available_kg = _catalog_available_kg(item)
    unit = normalize_mass_unit(item.sale_unit)
    source_name = item.source_product.name if item.source_product is not None else None
    return CatalogProductRead(
        id=item.id,
        cooperative_id=item.cooperative_id,
        source_product_id=item.source_product_id,
        source_product_name=source_name,
        name=item.name,
        description=item.description,
        category=item.category,
        sale_unit=unit,
        icon=item.icon,
        sale_price_fcfa=round_metric(item.sale_price_fcfa),
        cost_price_fcfa=round_metric(item.cost_price_fcfa),
        min_order_qty=round_metric(item.min_order_qty),
        total_stock=from_kg(item.total_stock_kg, unit),
        reserved_stock=from_kg(item.reserved_stock_kg, unit),
        available_stock=from_kg(available_kg, unit),
        total_stock_kg=round_metric(item.total_stock_kg),
        reserved_stock_kg=round_metric(item.reserved_stock_kg),
        available_stock_kg=available_kg,
        margin_percent=_margin_percent(item),
        status=item.status.value,
        low_stock=_catalog_low_stock(item),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _require_source_product(db: Session, cooperative_id, product_id) -> Product:
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.cooperative_id == cooperative_id)
    )
    if product is None:
        raise NotFoundError("Produit source introuvable pour cette cooperative.")
    return product


def _require_catalog_product(db: Session, cooperative_id, catalog_product_id) -> CommercialCatalogProduct:
    item = db.scalar(
        select(CommercialCatalogProduct)
        .options(selectinload(CommercialCatalogProduct.source_product))
        .where(
            CommercialCatalogProduct.id == catalog_product_id,
            CommercialCatalogProduct.cooperative_id == cooperative_id,
        )
    )
    if item is None:
        raise NotFoundError("Produit catalogue introuvable.")
    return item


def _require_order(db: Session, cooperative_id, order_id) -> CommercialOrder:
    order = db.scalar(
        select(CommercialOrder)
        .options(
            selectinload(CommercialOrder.lines).selectinload(CommercialOrderLine.catalog_product),
            selectinload(CommercialOrder.invoice).selectinload(CommercialInvoice.lines),
        )
        .where(CommercialOrder.id == order_id, CommercialOrder.cooperative_id == cooperative_id)
    )
    if order is None:
        raise NotFoundError("Commande introuvable.")
    return order


def _build_order_number(db: Session, year: int) -> str:
    prefix = f"CMD-{year}-"
    count = db.scalar(
        select(func.count(CommercialOrder.id)).where(CommercialOrder.order_number.like(f"{prefix}%"))
    )
    seq = int(count or 0) + 1
    return f"{prefix}{seq:03d}"


def _build_invoice_number(db: Session, year: int) -> str:
    prefix = f"FAC-{year}-"
    count = db.scalar(
        select(func.count(CommercialInvoice.id)).where(CommercialInvoice.invoice_number.like(f"{prefix}%"))
    )
    seq = int(count or 0) + 1
    return f"{prefix}{seq:03d}"


def _treasury_reference() -> str:
    return f"TRS-{uuid.uuid4().hex[:10].upper()}"


def _catalog_actor_label(manager: User) -> str:
    full_name = (manager.full_name or "").strip()
    email = (manager.email or "").strip().lower()
    if full_name and email:
        return f"{full_name} ({email})"
    if full_name:
        return full_name
    if email:
        return email
    return "manager_inconnu"


def _record_catalog_stock_movement(
    db: Session,
    *,
    cooperative_id,
    product_id,
    catalog_product_id,
    actor_name: str,
    movement_type: str,
    action_type: str,
    source: str,
    quantity_kg: float,
    notes: str,
):
    key = f"commercial:catalog:{catalog_product_id}:{action_type}:{movement_type}"
    existing = db.scalar(select(StockMovement).where(StockMovement.idempotency_key == key))
    if existing is not None:
        return existing

    movement = StockMovement(
        cooperative_id=cooperative_id,
        product_id=product_id,
        batch_id=None,
        input_id=None,
        process_step_id=None,
        workflow_step_id=None,
        movement_type=movement_type,
        action_type=action_type,
        source=source,
        quantity_kg=round_metric(abs(quantity_kg)),
        movement_date=date.today(),
        idempotency_key=key,
        notes=f"{notes} | manager:{actor_name}",
    )
    db.add(movement)
    return movement


def list_catalog_products(db: Session, manager: User) -> list[CatalogProductRead]:
    cooperative_id = get_manager_cooperative_id(manager)
    rows = db.scalars(
        select(CommercialCatalogProduct)
        .options(selectinload(CommercialCatalogProduct.source_product))
        .where(CommercialCatalogProduct.cooperative_id == cooperative_id)
        .order_by(CommercialCatalogProduct.created_at.desc())
    ).all()
    return [_serialize_catalog(item) for item in rows]


def create_catalog_product(db: Session, manager: User, payload) -> CatalogProductRead:
    cooperative_id = get_manager_cooperative_id(manager)
    source_product = _require_source_product(db, cooperative_id, payload.source_product_id)

    duplicate = db.scalar(
        select(CommercialCatalogProduct).where(
            CommercialCatalogProduct.cooperative_id == cooperative_id,
            func.lower(CommercialCatalogProduct.name) == payload.name.strip().lower(),
        )
    )
    if duplicate is not None:
        raise ValidationError("Un produit catalogue avec ce nom existe deja.")

    sale_unit = normalize_mass_unit(payload.sale_unit or source_product.unit)
    allocated_kg = to_kg(payload.allocated_quantity, sale_unit)

    source_stock = db.scalar(
        select(Stock).where(Stock.cooperative_id == cooperative_id, Stock.product_id == source_product.id)
    )
    if source_stock is None:
        raise ValidationError("Aucun stock principal disponible pour ce produit source.")

    if allocated_kg > available_stock_kg(source_stock):
        raise ValidationError("Quantite allouee superieure au stock principal disponible.")

    apply_reserved_stock_delta(db, cooperative_id, source_product, allocated_kg, create_if_missing=False)

    item = CommercialCatalogProduct(
        cooperative_id=cooperative_id,
        source_product_id=source_product.id,
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        category=payload.category.strip(),
        sale_unit=sale_unit,
        icon=payload.icon.strip() if payload.icon else None,
        sale_price_fcfa=round_metric(payload.sale_price_fcfa),
        cost_price_fcfa=round_metric(payload.cost_price_fcfa),
        min_order_qty=round_metric(payload.min_order_qty),
        total_stock_kg=round_metric(allocated_kg),
        reserved_stock_kg=0.0,
        status=CommercialCatalogStatus.ACTIVE,
    )
    db.add(item)
    db.flush()
    _record_catalog_stock_movement(
        db,
        cooperative_id=cooperative_id,
        product_id=source_product.id,
        catalog_product_id=item.id,
        actor_name=_catalog_actor_label(manager),
        movement_type="out",
        action_type="commercial_catalog_allocation",
        source="commercial_catalog",
        quantity_kg=allocated_kg,
        notes=f"Allocation vers catalogue commercial: {item.name}",
    )
    db.commit()
    db.refresh(item)
    return _serialize_catalog(item)


def update_catalog_product(db: Session, manager: User, catalog_product_id, payload) -> CatalogProductRead:
    cooperative_id = get_manager_cooperative_id(manager)
    item = _require_catalog_product(db, cooperative_id, catalog_product_id)
    data = payload.model_dump(exclude_unset=True)

    if "name" in data and data["name"] is not None:
        name = data["name"].strip()
        duplicate = db.scalar(
            select(CommercialCatalogProduct).where(
                CommercialCatalogProduct.cooperative_id == cooperative_id,
                func.lower(CommercialCatalogProduct.name) == name.lower(),
                CommercialCatalogProduct.id != item.id,
            )
        )
        if duplicate is not None:
            raise ValidationError("Un produit catalogue avec ce nom existe deja.")
        item.name = name

    if "description" in data:
        item.description = data["description"].strip() if data["description"] else None
    if "category" in data and data["category"] is not None:
        item.category = data["category"].strip()
    if "sale_unit" in data and data["sale_unit"] is not None:
        item.sale_unit = normalize_mass_unit(data["sale_unit"])
    if "icon" in data:
        item.icon = data["icon"].strip() if data["icon"] else None
    if "sale_price_fcfa" in data and data["sale_price_fcfa"] is not None:
        item.sale_price_fcfa = round_metric(data["sale_price_fcfa"])
    if "cost_price_fcfa" in data and data["cost_price_fcfa"] is not None:
        item.cost_price_fcfa = round_metric(data["cost_price_fcfa"])
    if "min_order_qty" in data and data["min_order_qty"] is not None:
        item.min_order_qty = round_metric(data["min_order_qty"])

    db.commit()
    db.refresh(item)
    return _serialize_catalog(item)


def set_catalog_status(db: Session, manager: User, catalog_product_id, status: str) -> CatalogProductRead:
    cooperative_id = get_manager_cooperative_id(manager)
    item = _require_catalog_product(db, cooperative_id, catalog_product_id)
    item.status = parse_enum_value(CommercialCatalogStatus, status.lower(), "catalog status")
    db.commit()
    db.refresh(item)
    return _serialize_catalog(item)


def delete_catalog_product(db: Session, manager: User, catalog_product_id) -> CatalogProductRead:
    cooperative_id = get_manager_cooperative_id(manager)
    item = _require_catalog_product(db, cooperative_id, catalog_product_id)

    linked_lines = db.scalar(
        select(func.count(CommercialOrderLine.id)).where(
            CommercialOrderLine.catalog_product_id == item.id
        )
    )
    if int(linked_lines or 0) > 0:
        raise ValidationError("Suppression impossible: ce produit est deja lie a des commandes.")

    if item.reserved_stock_kg > 0:
        raise ValidationError("Suppression impossible: une partie du stock est reservee.")

    source_product = item.source_product
    restock_kg = round_metric(max(item.total_stock_kg, 0.0))
    if source_product is not None and restock_kg > 0:
        apply_reserved_stock_delta(
            db,
            cooperative_id,
            source_product,
            -restock_kg,
            create_if_missing=True,
        )
        _record_catalog_stock_movement(
            db,
            cooperative_id=cooperative_id,
            product_id=source_product.id,
            catalog_product_id=item.id,
            actor_name=_catalog_actor_label(manager),
            movement_type="in",
            action_type="commercial_catalog_release",
            source="commercial_catalog",
            quantity_kg=restock_kg,
            notes=f"Retour du catalogue commercial: {item.name}",
        )

    snapshot = _serialize_catalog(item)
    db.delete(item)
    db.commit()
    return snapshot


def intake_order(db: Session, manager: User, payload) -> CommercialOrderRead:
    cooperative_id = get_manager_cooperative_id(manager)
    if not payload.lines:
        raise ValidationError("La commande doit contenir au moins une ligne.")

    ids = [line.catalog_product_id for line in payload.lines]
    rows = db.scalars(
        select(CommercialCatalogProduct)
        .where(
            CommercialCatalogProduct.cooperative_id == cooperative_id,
            CommercialCatalogProduct.id.in_(ids),
        )
    ).all()
    catalog_by_id = {row.id: row for row in rows}

    missing = [str(item_id) for item_id in ids if item_id not in catalog_by_id]
    if missing:
        raise ValidationError("Un ou plusieurs produits catalogue sont introuvables.")

    order = CommercialOrder(
        cooperative_id=cooperative_id,
        order_number=_build_order_number(db, date.today().year),
        customer_name=payload.customer_name.strip(),
        customer_phone=payload.customer_phone.strip() if payload.customer_phone else None,
        customer_email=payload.customer_email.strip() if payload.customer_email else None,
        customer_address=payload.customer_address.strip() if payload.customer_address else None,
        payment_method=payload.payment_method.strip() if payload.payment_method else None,
        notes=payload.notes.strip() if payload.notes else None,
        status=CommercialOrderStatus.RECEIVED,
    )
    db.add(order)
    db.flush()

    subtotal = 0.0
    for line in payload.lines:
        catalog = catalog_by_id[line.catalog_product_id]
        if catalog.status != CommercialCatalogStatus.ACTIVE:
            raise ValidationError(f"Le produit '{catalog.name}' est masque et ne peut pas etre commande.")
        if line.quantity < catalog.min_order_qty:
            raise ValidationError(
                f"Quantite insuffisante pour '{catalog.name}'. Minimum {catalog.min_order_qty} {catalog.sale_unit}."
            )
        qty_kg = to_kg(line.quantity, catalog.sale_unit)
        line_total = round_metric(line.quantity * catalog.sale_price_fcfa)
        subtotal += line_total

        db.add(
            CommercialOrderLine(
                order_id=order.id,
                catalog_product_id=catalog.id,
                product_name_snapshot=catalog.name,
                unit_snapshot=catalog.sale_unit,
                quantity=round_metric(line.quantity),
                quantity_kg=qty_kg,
                unit_price_fcfa=round_metric(catalog.sale_price_fcfa),
                line_total_fcfa=line_total,
            )
        )

    subtotal = round_metric(subtotal)
    tax_amount = round_metric(subtotal * order.tax_rate)
    order.subtotal_fcfa = subtotal
    order.tax_amount_fcfa = tax_amount
    order.total_amount_fcfa = round_metric(subtotal + tax_amount)

    db.commit()
    db.refresh(order)
    reindex_commercial_if_needed(
        db,
        current_user=manager,
        cooperative_id=cooperative_id,
        order_id=order.id,
    )
    order = _require_order(db, cooperative_id, order.id)
    return _serialize_order(order)


def _serialize_order(order: CommercialOrder) -> CommercialOrderRead:
    return CommercialOrderRead(
        id=order.id,
        cooperative_id=order.cooperative_id,
        order_number=order.order_number,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        customer_email=order.customer_email,
        customer_address=order.customer_address,
        payment_method=order.payment_method,
        notes=order.notes,
        status=order.status.value,
        subtotal_fcfa=round_metric(order.subtotal_fcfa),
        tax_rate=round_metric(order.tax_rate),
        tax_amount_fcfa=round_metric(order.tax_amount_fcfa),
        total_amount_fcfa=round_metric(order.total_amount_fcfa),
        source=order.source,
        locked=order.locked,
        received_at=order.received_at,
        confirmed_at=order.confirmed_at,
        preparing_at=order.preparing_at,
        ready_at=order.ready_at,
        delivered_at=order.delivered_at,
        paid_at=order.paid_at,
        refused_at=order.refused_at,
        refused_reason=order.refused_reason,
        lines=[
            CommercialOrderLineRead(
                id=line.id,
                catalog_product_id=line.catalog_product_id,
                product_name=line.product_name_snapshot,
                unit=line.unit_snapshot,
                quantity=round_metric(line.quantity),
                unit_price_fcfa=round_metric(line.unit_price_fcfa),
                line_total_fcfa=round_metric(line.line_total_fcfa),
            )
            for line in order.lines
        ],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def list_orders(db: Session, manager: User, status: str | None = None, search: str | None = None) -> list[CommercialOrderRead]:
    cooperative_id = get_manager_cooperative_id(manager)
    stmt = (
        select(CommercialOrder)
        .options(selectinload(CommercialOrder.lines))
        .where(CommercialOrder.cooperative_id == cooperative_id)
    )

    if status and status.lower() != "all":
        parsed = parse_enum_value(CommercialOrderStatus, status.lower(), "order status")
        stmt = stmt.where(CommercialOrder.status == parsed)

    if search and search.strip():
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(CommercialOrder.order_number).like(needle),
                func.lower(CommercialOrder.customer_name).like(needle),
                func.lower(func.coalesce(CommercialOrder.customer_phone, "")).like(needle),
            )
        )

    rows = db.scalars(stmt.order_by(CommercialOrder.created_at.desc())).all()
    return [_serialize_order(order) for order in rows]


def order_stats(db: Session, manager: User) -> CommercialOrderStats:
    cooperative_id = get_manager_cooperative_id(manager)
    rows = db.execute(
        select(CommercialOrder.status, func.count(CommercialOrder.id))
        .where(CommercialOrder.cooperative_id == cooperative_id)
        .group_by(CommercialOrder.status)
    ).all()
    counts = Counter({status.value: int(count) for status, count in rows})

    today = date.today()
    paid_this_month = db.scalar(
        select(func.coalesce(func.sum(CommercialOrder.total_amount_fcfa), 0.0)).where(
            CommercialOrder.cooperative_id == cooperative_id,
            CommercialOrder.status == CommercialOrderStatus.PAID,
            extract("year", CommercialOrder.paid_at) == today.year,
            extract("month", CommercialOrder.paid_at) == today.month,
        )
    )

    in_progress = counts[CommercialOrderStatus.CONFIRMED.value] + counts[CommercialOrderStatus.PREPARING.value] + counts[CommercialOrderStatus.READY.value]

    return CommercialOrderStats(
        total=sum(counts.values()),
        received=counts[CommercialOrderStatus.RECEIVED.value],
        confirmed=counts[CommercialOrderStatus.CONFIRMED.value],
        preparing=counts[CommercialOrderStatus.PREPARING.value],
        ready=counts[CommercialOrderStatus.READY.value],
        delivered=counts[CommercialOrderStatus.DELIVERED.value],
        paid=counts[CommercialOrderStatus.PAID.value],
        refused=counts[CommercialOrderStatus.REFUSED.value],
        new_count=counts[CommercialOrderStatus.RECEIVED.value],
        in_progress_count=in_progress,
        paid_this_month_fcfa=round_metric(paid_this_month or 0.0),
    )


def _reserve_for_order(order: CommercialOrder):
    for line in order.lines:
        catalog = line.catalog_product
        if catalog is None:
            raise ValidationError("Produit catalogue introuvable pour reservation.")
        available = _catalog_available_kg(catalog)
        if line.quantity_kg > available:
            raise ValidationError(
                f"Stock insuffisant pour '{line.product_name_snapshot}'. Disponible {from_kg(available, line.unit_snapshot)} {line.unit_snapshot}."
            )
        catalog.reserved_stock_kg = round_metric(catalog.reserved_stock_kg + line.quantity_kg)


def _release_for_order(order: CommercialOrder):
    for line in order.lines:
        catalog = line.catalog_product
        if catalog is None:
            continue
        catalog.reserved_stock_kg = round_metric(max(catalog.reserved_stock_kg - line.quantity_kg, 0.0))


def _deduct_on_delivery(order: CommercialOrder):
    for line in order.lines:
        catalog = line.catalog_product
        if catalog is None:
            raise ValidationError("Produit catalogue introuvable pour deduction.")
        if line.quantity_kg > catalog.reserved_stock_kg:
            raise ValidationError(f"Reservation incoherente pour '{line.product_name_snapshot}'.")
        if line.quantity_kg > catalog.total_stock_kg:
            raise ValidationError(f"Stock total insuffisant pour '{line.product_name_snapshot}'.")
        catalog.reserved_stock_kg = round_metric(catalog.reserved_stock_kg - line.quantity_kg)
        catalog.total_stock_kg = round_metric(catalog.total_stock_kg - line.quantity_kg)


def _create_invoice_for_order(db: Session, order: CommercialOrder) -> CommercialInvoice:
    if order.invoice is not None:
        invoice = order.invoice
    else:
        invoice = db.scalar(
            select(CommercialInvoice)
            .options(selectinload(CommercialInvoice.lines))
            .where(
                CommercialInvoice.cooperative_id == order.cooperative_id,
                CommercialInvoice.order_id == order.id,
            )
        )
    if invoice is not None:
        if len(invoice.lines) == 0:
            for line in order.lines:
                db.add(
                    CommercialInvoiceLine(
                        invoice_id=invoice.id,
                        description=line.product_name_snapshot,
                        unit=line.unit_snapshot,
                        quantity=round_metric(line.quantity),
                        unit_price_fcfa=round_metric(line.unit_price_fcfa),
                        line_total_fcfa=round_metric(line.line_total_fcfa),
                    )
                )
            db.flush()
        return invoice

    issue = date.today()
    due = issue + timedelta(days=30)
    invoice = CommercialInvoice(
        cooperative_id=order.cooperative_id,
        order_id=order.id,
        invoice_number=_build_invoice_number(db, issue.year),
        issue_date=issue,
        due_date=due,
        status=InvoiceStatus.PENDING,
        customer_name_snapshot=order.customer_name,
        customer_phone_snapshot=order.customer_phone,
        customer_email_snapshot=order.customer_email,
        customer_address_snapshot=order.customer_address,
        subtotal_fcfa=round_metric(order.subtotal_fcfa),
        tax_rate=round_metric(order.tax_rate),
        tax_amount_fcfa=round_metric(order.tax_amount_fcfa),
        total_amount_fcfa=round_metric(order.total_amount_fcfa),
        notes=order.notes,
    )
    db.add(invoice)
    db.flush()

    for line in order.lines:
        db.add(
            CommercialInvoiceLine(
                invoice_id=invoice.id,
                description=line.product_name_snapshot,
                unit=line.unit_snapshot,
                quantity=round_metric(line.quantity),
                unit_price_fcfa=round_metric(line.unit_price_fcfa),
                line_total_fcfa=round_metric(line.line_total_fcfa),
            )
        )
    db.flush()
    return invoice


def _mark_paid(db: Session, order: CommercialOrder):
    invoice = _create_invoice_for_order(db, order)
    if invoice.status != InvoiceStatus.PAID:
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = order.paid_at

    already = db.scalar(
        select(TreasuryTransaction).where(
            TreasuryTransaction.cooperative_id == order.cooperative_id,
            TreasuryTransaction.source_type == "commercial_invoice",
            or_(
                TreasuryTransaction.source_id == invoice.id,
                TreasuryTransaction.receipt_reference == invoice.invoice_number,
            ),
            TreasuryTransaction.type == TreasuryTransactionType.INCOME,
            TreasuryTransaction.status != TreasuryTransactionStatus.CANCELLED,
        )
    )
    if already is not None:
        if already.source_id is None:
            already.source_id = invoice.id
        if not already.receipt_reference:
            already.receipt_reference = invoice.invoice_number
        if already.status != TreasuryTransactionStatus.ENREGISTRE_COMPLET:
            already.status = TreasuryTransactionStatus.ENREGISTRE_COMPLET
        return

    db.add(
        TreasuryTransaction(
            cooperative_id=order.cooperative_id,
            reference=_treasury_reference(),
            transaction_date=date.today(),
            type=TreasuryTransactionType.INCOME,
            category="vente",
            label=f"Paiement facture {invoice.invoice_number}",
            amount_fcfa=round_metric(invoice.total_amount_fcfa),
            note=f"Commande {order.order_number}",
            status=TreasuryTransactionStatus.ENREGISTRE_COMPLET,
            source_type="commercial_invoice",
            source_id=invoice.id,
            receipt_reference=invoice.invoice_number,
            farmer_id=None,
        )
    )


def update_order_status(db: Session, manager: User, order_id, payload) -> CommercialOrderRead:
    cooperative_id = get_manager_cooperative_id(manager)
    order = _require_order(db, cooperative_id, order_id)
    next_status = parse_enum_value(CommercialOrderStatus, payload.status.lower(), "order status")

    if next_status == order.status:
        return _serialize_order(order)

    allowed = ORDER_TRANSITIONS.get(order.status, set())
    if next_status not in allowed:
        raise ValidationError(f"Transition invalide: {order.status.value} -> {next_status.value}")

    if next_status == CommercialOrderStatus.CONFIRMED:
        _reserve_for_order(order)
        order.confirmed_at = order.confirmed_at or current_utc()
    elif next_status == CommercialOrderStatus.PREPARING:
        order.preparing_at = order.preparing_at or current_utc()
    elif next_status == CommercialOrderStatus.READY:
        order.ready_at = order.ready_at or current_utc()
    elif next_status == CommercialOrderStatus.DELIVERED:
        _deduct_on_delivery(order)
        order.delivered_at = order.delivered_at or current_utc()
        _create_invoice_for_order(db, order)
    elif next_status == CommercialOrderStatus.PAID:
        order.paid_at = order.paid_at or current_utc()
        _mark_paid(db, order)
    elif next_status == CommercialOrderStatus.REFUSED:
        if order.status in {CommercialOrderStatus.CONFIRMED, CommercialOrderStatus.PREPARING, CommercialOrderStatus.READY}:
            _release_for_order(order)
        order.refused_reason = payload.refused_reason.strip() if payload.refused_reason else None
        order.refused_at = order.refused_at or current_utc()

    order.status = next_status
    db.commit()
    reindex_commercial_if_needed(
        db,
        current_user=manager,
        cooperative_id=cooperative_id,
        order_id=order.id,
        invoice_id=order.invoice.id if order.invoice else None,
    )

    order = _require_order(db, cooperative_id, order.id)
    return _serialize_order(order)


def _serialize_invoice(invoice: CommercialInvoice) -> CommercialInvoiceRead:
    order_number = invoice.order.order_number if invoice.order is not None else ""
    return CommercialInvoiceRead(
        id=invoice.id,
        cooperative_id=invoice.cooperative_id,
        order_id=invoice.order_id,
        order_number=order_number,
        invoice_number=invoice.invoice_number,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        status=invoice.status.value,
        customer_name=invoice.customer_name_snapshot,
        customer_phone=invoice.customer_phone_snapshot,
        customer_email=invoice.customer_email_snapshot,
        customer_address=invoice.customer_address_snapshot,
        subtotal_fcfa=round_metric(invoice.subtotal_fcfa),
        tax_rate=round_metric(invoice.tax_rate),
        tax_amount_fcfa=round_metric(invoice.tax_amount_fcfa),
        total_amount_fcfa=round_metric(invoice.total_amount_fcfa),
        paid_at=invoice.paid_at,
        lines=[
            CommercialInvoiceLineRead(
                id=line.id,
                description=line.description,
                unit=line.unit,
                quantity=round_metric(line.quantity),
                unit_price_fcfa=round_metric(line.unit_price_fcfa),
                line_total_fcfa=round_metric(line.line_total_fcfa),
            )
            for line in invoice.lines
        ],
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


def list_invoices(db: Session, manager: User, status: str | None = None, search: str | None = None) -> list[CommercialInvoiceRead]:
    cooperative_id = get_manager_cooperative_id(manager)
    stmt = (
        select(CommercialInvoice)
        .options(
            selectinload(CommercialInvoice.lines),
            selectinload(CommercialInvoice.order),
        )
        .where(CommercialInvoice.cooperative_id == cooperative_id)
    )

    if status and status.lower() != "all":
        parsed = parse_enum_value(InvoiceStatus, status.lower(), "invoice status")
        stmt = stmt.where(CommercialInvoice.status == parsed)

    if search and search.strip():
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.join(CommercialOrder, CommercialOrder.id == CommercialInvoice.order_id).where(
            or_(
                func.lower(CommercialInvoice.invoice_number).like(needle),
                func.lower(CommercialOrder.order_number).like(needle),
                func.lower(CommercialInvoice.customer_name_snapshot).like(needle),
            )
        )

    rows = db.scalars(stmt.order_by(CommercialInvoice.issue_date.desc(), CommercialInvoice.created_at.desc())).all()
    return [_serialize_invoice(invoice) for invoice in rows]


def get_invoice(db: Session, manager: User, invoice_id) -> CommercialInvoiceRead:
    cooperative_id = get_manager_cooperative_id(manager)
    invoice = db.scalar(
        select(CommercialInvoice)
        .options(selectinload(CommercialInvoice.lines), selectinload(CommercialInvoice.order))
        .where(CommercialInvoice.id == invoice_id, CommercialInvoice.cooperative_id == cooperative_id)
    )
    if invoice is None:
        raise NotFoundError("Facture introuvable.")
    return _serialize_invoice(invoice)


def invoice_stats(db: Session, manager: User) -> CommercialInvoiceStats:
    cooperative_id = get_manager_cooperative_id(manager)
    total = db.scalar(
        select(func.coalesce(func.sum(CommercialInvoice.total_amount_fcfa), 0.0)).where(
            CommercialInvoice.cooperative_id == cooperative_id
        )
    )
    paid = db.scalar(
        select(func.coalesce(func.sum(CommercialInvoice.total_amount_fcfa), 0.0)).where(
            CommercialInvoice.cooperative_id == cooperative_id,
            CommercialInvoice.status == InvoiceStatus.PAID,
        )
    )
    pending = round_metric((total or 0.0) - (paid or 0.0))
    paid_rate = round_metric(((paid or 0.0) / (total or 1.0)) * 100.0) if (total or 0.0) > 0 else 0.0

    return CommercialInvoiceStats(
        total_invoiced_fcfa=round_metric(total or 0.0),
        paid_fcfa=round_metric(paid or 0.0),
        pending_fcfa=pending,
        paid_rate_percent=paid_rate,
    )

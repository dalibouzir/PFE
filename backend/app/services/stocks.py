from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.input import Input
from app.models.product import Product
from app.models.stock import Stock
from app.models.user import User
from app.schemas.stock import StockAlertRead, StockRead
from app.services.helpers import from_kg, get_manager_cooperative_id, normalize_mass_unit, round_metric
from app.utils.exceptions import NotFoundError, ValidationError


CRITICAL_STOCK_RATIO = 0.2


def _require_product_in_scope(db: Session, manager: User, product_id):
    cooperative_id = get_manager_cooperative_id(manager)
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.cooperative_id == cooperative_id)
    )
    if product is None:
        raise NotFoundError("Product not found in the current cooperative.")
    return product


def get_stock_by_product(db: Session, cooperative_id, product_id):
    return db.scalar(
        select(Stock).where(Stock.cooperative_id == cooperative_id, Stock.product_id == product_id)
    )


def available_stock_kg(stock: Stock) -> float:
    return round_metric(max(stock.total_stock_kg - stock.reserved_in_lots_kg, 0.0))


def critical_threshold_kg(stock: Stock) -> float:
    return round_metric(max(stock.total_stock_kg, 0.0) * CRITICAL_STOCK_RATIO)


def _sync_available_snapshot(stock: Stock):
    stock.quantity = available_stock_kg(stock)


def _repair_legacy_stock_row(stock: Stock) -> bool:
    changed = False

    # Backward compatibility: older rows used `quantity` directly and left `total_stock_kg` at 0.
    if stock.total_stock_kg <= 0 and stock.quantity > 0:
        stock.total_stock_kg = round_metric(stock.quantity + max(stock.reserved_in_lots_kg, 0.0))
        changed = True

    if stock.reserved_in_lots_kg < 0:
        stock.reserved_in_lots_kg = 0.0
        changed = True

    if stock.processed_output_kg < 0:
        stock.processed_output_kg = 0.0
        changed = True

    expected_available = available_stock_kg(stock)
    if abs(stock.quantity - expected_available) > 1e-9:
        stock.quantity = expected_available
        changed = True

    return changed


def _hydrate_total_from_existing_inputs(db: Session, stock: Stock) -> bool:
    if stock.total_stock_kg > 0:
        return False
    total_from_inputs = db.scalar(
        select(func.coalesce(func.sum(Input.quantity), 0.0)).where(
            Input.cooperative_id == stock.cooperative_id,
            Input.product_id == stock.product_id,
        )
    )
    total_kg = round_metric(total_from_inputs or 0.0)
    if total_kg <= 0:
        return False
    stock.total_stock_kg = total_kg
    _sync_available_snapshot(stock)
    return True


def _serialize_stock(stock: Stock) -> StockRead:
    unit = normalize_mass_unit(stock.unit)
    available_kg = available_stock_kg(stock)
    threshold_kg = critical_threshold_kg(stock)
    return StockRead(
        id=stock.id,
        cooperative_id=stock.cooperative_id,
        product_id=stock.product_id,
        quantity=from_kg(available_kg, unit),
        threshold=from_kg(threshold_kg, unit),
        total_stock=from_kg(stock.total_stock_kg, unit),
        available_stock=from_kg(available_kg, unit),
        reserved_in_lots=from_kg(stock.reserved_in_lots_kg, unit),
        processed_output=from_kg(stock.processed_output_kg, unit),
        total_stock_kg=round_metric(stock.total_stock_kg),
        available_stock_kg=available_kg,
        reserved_in_lots_kg=round_metric(stock.reserved_in_lots_kg),
        processed_output_kg=round_metric(stock.processed_output_kg),
        threshold_kg=threshold_kg,
        unit=unit,
        last_updated=stock.last_updated,
        created_at=stock.created_at,
        updated_at=stock.updated_at,
    )


def serialize_stock_read(stock: Stock) -> StockRead:
    return _serialize_stock(stock)


def _create_stock_row(db: Session, cooperative_id, product: Product, unit=None) -> Stock:
    normalized_unit = normalize_mass_unit(unit or product.unit)
    stock = Stock(
        cooperative_id=cooperative_id,
        product_id=product.id,
        quantity=0.0,
        total_stock_kg=0.0,
        reserved_in_lots_kg=0.0,
        processed_output_kg=0.0,
        threshold=0.0,
        unit=normalized_unit,
    )
    db.add(stock)
    db.flush()
    return stock


def create_stock(db: Session, manager: User, payload) -> Stock:
    _require_product_in_scope(db, manager, payload.product_id)
    raise ValidationError(
        "Creation manuelle de stock desactivee. Le stock est calcule automatiquement a partir des collectes."
    )


def list_stocks(db: Session, manager: User):
    cooperative_id = get_manager_cooperative_id(manager)
    stocks = db.scalars(
        select(Stock).where(Stock.cooperative_id == cooperative_id).order_by(Stock.updated_at.desc())
    ).all()
    dirty = False
    for stock in stocks:
        changed = _hydrate_total_from_existing_inputs(db, stock)
        changed = _repair_legacy_stock_row(stock) or changed
        if changed:
            dirty = True
    if dirty:
        db.commit()
    return stocks


def require_stock(db: Session, manager: User, stock_id):
    cooperative_id = get_manager_cooperative_id(manager)
    stock = db.scalar(select(Stock).where(Stock.id == stock_id, Stock.cooperative_id == cooperative_id))
    if stock is None:
        raise NotFoundError("Stock not found in the current cooperative.")
    _sync_available_snapshot(stock)
    return stock


def update_stock(db: Session, manager: User, stock_id, payload) -> Stock:
    require_stock(db, manager, stock_id)
    raise ValidationError(
        "Modification manuelle des stocks desactivee. Les stocks sont calcules automatiquement via collectes et lots."
    )


def adjust_stock(db: Session, manager: User, stock_id, amount: float, increase: bool) -> Stock:
    require_stock(db, manager, stock_id)
    direction = "increase" if increase else "decrease"
    raise ValidationError(
        f"Manual stock {direction} is disabled. Use collecte/input flow and lot reservation workflow instead."
    )


def delete_stock(db: Session, manager: User, stock_id):
    require_stock(db, manager, stock_id)
    raise ValidationError("Suppression manuelle des stocks desactivee.")


def apply_total_stock_delta(
    db: Session,
    cooperative_id,
    product: Product,
    delta_kg: float,
    create_if_missing: bool = False,
) -> Stock:
    stock = get_stock_by_product(db, cooperative_id, product.id)
    if stock is None:
        if not create_if_missing:
            raise ValidationError("Stock row not found for the requested product.")
        stock = _create_stock_row(db, cooperative_id, product, unit=product.unit)
    else:
        # Avoid double-counting when caller already persisted a new input row and
        # is now applying its explicit delta.
        if abs(float(delta_kg)) < 1e-9:
            _hydrate_total_from_existing_inputs(db, stock)
        _repair_legacy_stock_row(stock)

    next_total = round_metric(stock.total_stock_kg + float(delta_kg))
    if next_total < 0:
        raise ValidationError("Stock total cannot become negative.")
    if next_total < stock.reserved_in_lots_kg:
        raise ValidationError("Stock total cannot be lower than reserved quantity in lots.")

    stock.total_stock_kg = next_total
    _sync_available_snapshot(stock)
    return stock


def reserve_stock_for_lot(db: Session, cooperative_id, product: Product, quantity_kg: float) -> Stock:
    stock = get_stock_by_product(db, cooperative_id, product.id)
    if stock is None:
        raise ValidationError("Stock row not found for the requested product.")

    qty = round_metric(float(quantity_kg))
    if qty <= 0:
        raise ValidationError("Reserved quantity must be greater than zero.")

    available_kg = available_stock_kg(stock)
    if qty > available_kg:
        raise ValidationError("Impossible de creer ce lot : quantite demandee superieure au stock disponible.")

    stock.reserved_in_lots_kg = round_metric(stock.reserved_in_lots_kg + qty)
    _sync_available_snapshot(stock)
    return stock


def release_reserved_stock_for_lot(db: Session, cooperative_id, product: Product, quantity_kg: float) -> Stock:
    stock = get_stock_by_product(db, cooperative_id, product.id)
    if stock is None:
        raise ValidationError("Stock row not found for the requested product.")

    qty = round_metric(float(quantity_kg))
    if qty <= 0:
        raise ValidationError("Released quantity must be greater than zero.")
    if qty > stock.reserved_in_lots_kg:
        raise ValidationError("Cannot release more reserved quantity than currently reserved.")

    stock.reserved_in_lots_kg = round_metric(stock.reserved_in_lots_kg - qty)
    _sync_available_snapshot(stock)
    return stock


def apply_processed_output_delta(db: Session, cooperative_id, product: Product, output_kg: float) -> Stock:
    stock = get_stock_by_product(db, cooperative_id, product.id)
    if stock is None:
        raise ValidationError("Stock row not found for the requested product.")
    next_output = round_metric(stock.processed_output_kg + float(output_kg))
    if next_output < 0:
        raise ValidationError("Processed output cannot become negative.")
    stock.processed_output_kg = next_output
    _sync_available_snapshot(stock)
    return stock


def list_low_stock_alerts(db: Session, cooperative_id):
    stocks = db.scalars(select(Stock).where(Stock.cooperative_id == cooperative_id)).all()
    alerts = []
    for stock in stocks:
        available_kg = available_stock_kg(stock)
        threshold_kg = critical_threshold_kg(stock)
        if available_kg >= threshold_kg:
            continue
        unit = normalize_mass_unit(stock.unit)
        deficit_kg = round_metric(threshold_kg - available_kg)
        alerts.append(
            StockAlertRead(
                stock_id=stock.id,
                product_id=stock.product_id,
                quantity=from_kg(available_kg, unit),
                threshold=from_kg(threshold_kg, unit),
                unit=unit,
                deficit=from_kg(deficit_kg, unit),
                deficit_kg=deficit_kg,
            )
        )
    return alerts

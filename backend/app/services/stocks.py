from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.stock import Stock
from app.models.user import User
from app.schemas.stock import StockAlertRead
from app.services.helpers import get_manager_cooperative_id, round_metric
from app.utils.exceptions import ConflictError, NotFoundError, ValidationError


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


def create_stock(db: Session, manager: User, payload) -> Stock:
    cooperative_id = get_manager_cooperative_id(manager)
    product = _require_product_in_scope(db, manager, payload.product_id)
    existing = get_stock_by_product(db, cooperative_id, payload.product_id)
    if existing is not None:
        raise ConflictError("A stock row already exists for this product in the cooperative.")
    stock = Stock(
        cooperative_id=cooperative_id,
        product_id=product.id,
        quantity=payload.quantity,
        threshold=payload.threshold,
        unit=payload.unit.strip(),
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


def list_stocks(db: Session, manager: User):
    cooperative_id = get_manager_cooperative_id(manager)
    return db.scalars(
        select(Stock).where(Stock.cooperative_id == cooperative_id).order_by(Stock.updated_at.desc())
    ).all()


def require_stock(db: Session, manager: User, stock_id):
    cooperative_id = get_manager_cooperative_id(manager)
    stock = db.scalar(select(Stock).where(Stock.id == stock_id, Stock.cooperative_id == cooperative_id))
    if stock is None:
        raise NotFoundError("Stock not found in the current cooperative.")
    return stock


def update_stock(db: Session, manager: User, stock_id, payload) -> Stock:
    stock = require_stock(db, manager, stock_id)
    data = payload.model_dump(exclude_unset=True)
    if "threshold" in data:
        stock.threshold = data["threshold"]
    if "unit" in data:
        stock.unit = data["unit"].strip()
    db.commit()
    db.refresh(stock)
    return stock


def adjust_stock(db: Session, manager: User, stock_id, amount: float, increase: bool) -> Stock:
    stock = require_stock(db, manager, stock_id)
    next_quantity = stock.quantity + amount if increase else stock.quantity - amount
    if next_quantity < 0:
        raise ValidationError("Stock quantity cannot become negative.")
    stock.quantity = round_metric(next_quantity)
    db.commit()
    db.refresh(stock)
    return stock


def apply_stock_delta(db: Session, cooperative_id, product: Product, delta: float, create_if_missing: bool = False) -> Stock:
    stock = get_stock_by_product(db, cooperative_id, product.id)
    if stock is None:
        if not create_if_missing:
            raise ValidationError("Stock row not found for the requested product.")
        stock = Stock(
            cooperative_id=cooperative_id,
            product_id=product.id,
            quantity=0.0,
            threshold=0.0,
            unit=product.unit,
        )
        db.add(stock)
        db.flush()

    next_quantity = stock.quantity + delta
    if next_quantity < 0:
        raise ValidationError("Insufficient stock for this operation.")
    stock.quantity = round_metric(next_quantity)
    return stock


def list_low_stock_alerts(db: Session, cooperative_id):
    stocks = db.scalars(
        select(Stock).where(Stock.cooperative_id == cooperative_id, Stock.quantity < Stock.threshold)
    ).all()
    return [
        StockAlertRead(
            stock_id=stock.id,
            product_id=stock.product_id,
            quantity=round_metric(stock.quantity),
            threshold=round_metric(stock.threshold),
            unit=stock.unit,
            deficit=round_metric(stock.threshold - stock.quantity),
        )
        for stock in stocks
    ]

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.batch import Batch
from app.models.enums import BatchStatus
from app.models.product import Product
from app.models.user import User
from app.services.helpers import get_manager_cooperative_id, parse_enum_value, round_metric
from app.services.stocks import apply_stock_delta
from app.utils.exceptions import ConflictError, NotFoundError, ValidationError


def require_batch(db: Session, manager: User, batch_id, with_steps: bool = False) -> Batch:
    cooperative_id = get_manager_cooperative_id(manager)
    stmt = select(Batch).where(Batch.id == batch_id, Batch.cooperative_id == cooperative_id)
    if with_steps:
        stmt = stmt.options(selectinload(Batch.process_steps), selectinload(Batch.product), selectinload(Batch.recommendation))
    batch = db.scalar(stmt)
    if batch is None:
        raise NotFoundError("Batch not found in the current cooperative.")
    return batch


def list_batches(db: Session, manager: User):
    cooperative_id = get_manager_cooperative_id(manager)
    return db.scalars(
        select(Batch).where(Batch.cooperative_id == cooperative_id).order_by(Batch.creation_date.desc(), Batch.created_at.desc())
    ).all()


def create_batch(db: Session, manager: User, payload) -> Batch:
    cooperative_id = get_manager_cooperative_id(manager)
    duplicate = db.scalar(select(Batch).where(func.lower(Batch.code) == payload.code.lower()))
    if duplicate is not None:
        raise ConflictError("A batch with this code already exists.")

    product = db.scalar(
        select(Product).where(Product.id == payload.product_id, Product.cooperative_id == cooperative_id)
    )
    if product is None:
        raise NotFoundError("Product not found in the current cooperative.")

    apply_stock_delta(db, cooperative_id, product, -payload.initial_qty, create_if_missing=False)
    batch = Batch(
        cooperative_id=cooperative_id,
        product_id=product.id,
        code=payload.code.strip(),
        creation_date=payload.creation_date,
        initial_qty=payload.initial_qty,
        current_qty=payload.initial_qty,
        status=BatchStatus.CREATED,
        created_by_user_id=manager.id,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def refresh_batch_current_qty(batch: Batch):
    if batch.process_steps:
        latest_step = sorted(batch.process_steps, key=lambda step: (step.date, step.created_at, step.id))[-1]
        batch.current_qty = round_metric(latest_step.qty_out)
    else:
        batch.current_qty = round_metric(batch.initial_qty)
    return batch.current_qty


def update_batch_status(db: Session, manager: User, batch_id, payload) -> Batch:
    batch = require_batch(db, manager, batch_id, with_steps=True)
    next_status = parse_enum_value(BatchStatus, payload.status, "batch status")
    transition_batch_status(db, batch, next_status)
    db.commit()
    db.refresh(batch)
    return batch


def transition_batch_status(db: Session, batch: Batch, next_status: BatchStatus):
    if batch.status == next_status:
        return batch
    if batch.status == BatchStatus.ARCHIVED and next_status != BatchStatus.ARCHIVED:
        raise ValidationError("Archived batches cannot be reopened.")
    if batch.status == BatchStatus.COMPLETED and next_status not in (BatchStatus.COMPLETED, BatchStatus.ARCHIVED):
        raise ValidationError("Completed batches can only be archived.")

    if next_status == BatchStatus.COMPLETED and batch.status != BatchStatus.COMPLETED:
        product = batch.product
        if product is None:
            raise ValidationError("Batch product must be loaded before completing the batch.")
        apply_stock_delta(db, batch.cooperative_id, product, batch.current_qty, create_if_missing=True)

    batch.status = next_status
    return batch

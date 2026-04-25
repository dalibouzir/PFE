from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.batch import Batch
from app.models.enums import BatchStatus
from app.models.product import Product
from app.models.user import User
from app.schemas.batch import BatchRead
from app.services.helpers import (
    from_kg,
    get_manager_cooperative_id,
    normalize_mass_unit,
    normalize_product_code,
    round_metric,
    to_kg,
)
from app.services.stocks import apply_processed_output_delta, release_reserved_stock_for_lot, reserve_stock_for_lot
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


def _normalize_steps(raw_steps: list[str]) -> list[str]:
    ordered = []
    for raw in raw_steps:
        value = str(raw).strip()
        if not value:
            continue
        ordered.append(value)
    if not ordered:
        raise ValidationError("A lot must define at least one ordered process step.")
    return ordered


def _generate_lot_reference(db: Session, product_name: str) -> str:
    product_code = normalize_product_code(product_name)
    prefix = f"LOT-{product_code}-"
    rows = db.scalars(select(Batch.code).where(func.lower(Batch.code).like(f"{prefix.lower()}%"))).all()

    max_increment = 0
    for code in rows:
        suffix = code[len(prefix) :]
        if suffix.isdigit():
            max_increment = max(max_increment, int(suffix))
    next_increment = max_increment + 1
    return f"{prefix}{next_increment:03d}"


def serialize_batch(batch: Batch) -> BatchRead:
    unit = normalize_mass_unit(batch.unit)
    initial_display = from_kg(batch.initial_qty, unit)
    current_display = from_kg(batch.current_qty, unit)
    return BatchRead(
        id=batch.id,
        cooperative_id=batch.cooperative_id,
        product_id=batch.product_id,
        code=batch.code,
        creation_date=batch.creation_date,
        unit=unit,
        ordered_process_steps=batch.ordered_process_steps or [],
        initial_qty=initial_display,
        current_qty=current_display,
        initial_qty_display=initial_display,
        current_qty_display=current_display,
        status=batch.status.value,
        created_by_user_id=batch.created_by_user_id,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def preview_next_batch_reference(db: Session, manager: User, product_id) -> str:
    cooperative_id = get_manager_cooperative_id(manager)
    product = db.scalar(select(Product).where(Product.id == product_id, Product.cooperative_id == cooperative_id))
    if product is None:
        raise NotFoundError("Product not found in the current cooperative.")
    return _generate_lot_reference(db, product.name)


def create_batch(db: Session, manager: User, payload) -> Batch:
    cooperative_id = get_manager_cooperative_id(manager)
    product = db.scalar(
        select(Product).where(Product.id == payload.product_id, Product.cooperative_id == cooperative_id)
    )
    if product is None:
        raise NotFoundError("Product not found in the current cooperative.")

    unit = normalize_mass_unit(payload.unit)
    initial_qty_kg = to_kg(payload.initial_qty, unit)
    if initial_qty_kg <= 0:
        raise ValidationError("Lot quantity must be greater than zero.")

    ordered_steps = _normalize_steps(payload.process_steps)

    reserve_stock_for_lot(db, cooperative_id, product, initial_qty_kg)

    attempts = 0
    while attempts < 5:
        attempts += 1
        code = _generate_lot_reference(db, product.name)
        batch = Batch(
            cooperative_id=cooperative_id,
            product_id=product.id,
            code=code,
            creation_date=payload.creation_date,
            unit=unit,
            ordered_process_steps=ordered_steps,
            initial_qty=initial_qty_kg,
            current_qty=initial_qty_kg,
            status=BatchStatus.CREATED,
            created_by_user_id=manager.id,
        )
        db.add(batch)
        try:
            db.commit()
            db.refresh(batch)
            return batch
        except IntegrityError:
            db.rollback()
            if attempts >= 5:
                raise ConflictError("Unable to generate a unique lot reference. Please retry.")
            reserve_stock_for_lot(db, cooperative_id, product, initial_qty_kg)

    raise ConflictError("Unable to create lot.")


def refresh_batch_current_qty(batch: Batch):
    if batch.process_steps:
        latest_step = sorted(batch.process_steps, key=lambda step: (step.sequence_order, step.date, step.created_at, step.id))[-1]
        batch.current_qty = round_metric(latest_step.qty_out)
    else:
        batch.current_qty = round_metric(batch.initial_qty)
    return batch.current_qty


def update_batch(db: Session, manager: User, batch_id, payload) -> Batch:
    batch = require_batch(db, manager, batch_id, with_steps=True)
    if batch.process_steps:
        raise ValidationError("Ordered process steps cannot be changed once execution has started.")

    data = payload.model_dump(exclude_unset=True)
    if "process_steps" in data:
        batch.ordered_process_steps = _normalize_steps(data["process_steps"])

    db.commit()
    db.refresh(batch)
    return batch


def update_batch_status(db: Session, manager: User, batch_id, payload) -> Batch:
    require_batch(db, manager, batch_id, with_steps=True)
    raise ValidationError(
        "Le statut du lot est calcule automatiquement depuis l'avancement des etapes. Modification manuelle desactivee."
    )


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
        apply_processed_output_delta(db, batch.cooperative_id, product, batch.current_qty)

    batch.status = next_status
    return batch


def sync_batch_status_from_steps(db: Session, batch: Batch):
    executed_steps = len(batch.process_steps or [])
    ordered_steps = [str(item).strip() for item in (batch.ordered_process_steps or []) if str(item).strip()]

    if executed_steps == 0:
        batch.status = BatchStatus.CREATED
        return batch

    if ordered_steps and executed_steps >= len(ordered_steps):
        transition_batch_status(db, batch, BatchStatus.COMPLETED)
        return batch

    batch.status = BatchStatus.IN_PROGRESS
    return batch


def delete_batch(db: Session, manager: User, batch_id):
    batch = require_batch(db, manager, batch_id, with_steps=True)
    product = batch.product
    if product is None:
        raise ValidationError("Batch product must be loaded before deletion.")

    release_reserved_stock_for_lot(db, batch.cooperative_id, product, batch.initial_qty)
    if batch.status == BatchStatus.COMPLETED:
        apply_processed_output_delta(db, batch.cooperative_id, product, -batch.current_qty)

    db.delete(batch)
    db.commit()

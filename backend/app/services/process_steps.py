from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.batch import Batch
from app.models.enums import BatchStatus, ProcessStepStatus
from app.models.mixins import current_utc
from app.models.process_step import ProcessStep
from app.models.user import User
from app.services import analytics
from app.services.batches import refresh_batch_current_qty, require_batch, sync_batch_status_from_steps
from app.services.helpers import get_manager_cooperative_id, normalize_mass_unit, round_metric, to_kg
from app.utils.exceptions import NotFoundError, ValidationError


def _require_step(db: Session, manager: User, step_id):
    cooperative_id = get_manager_cooperative_id(manager)
    step = db.scalar(
        select(ProcessStep)
        .join(Batch, Batch.id == ProcessStep.batch_id)
        .options(
            selectinload(ProcessStep.batch)
            .selectinload(Batch.process_steps),
            selectinload(ProcessStep.batch).selectinload(Batch.product),
        )
        .where(ProcessStep.id == step_id, Batch.cooperative_id == cooperative_id)
    )
    if step is None:
        raise NotFoundError("Process step not found in the current cooperative.")
    return step


def _sorted_steps(batch: Batch) -> list[ProcessStep]:
    return sorted(batch.process_steps, key=lambda item: (item.sequence_order, item.date, item.created_at, item.id))


def _ordered_plan(batch: Batch) -> list[str]:
    plan = [str(item).strip() for item in (batch.ordered_process_steps or []) if str(item).strip()]
    if not plan:
        raise ValidationError("This lot has no configured process steps.")
    return plan


def _validate_loss(loss_value: float, loss_unit: str, input_qty_kg: float) -> tuple[float, str, float]:
    unit = normalize_mass_unit(loss_unit)
    loss_value_normalized = round_metric(float(loss_value))
    if loss_value_normalized < 0:
        raise ValidationError("Loss must be greater than or equal to zero.")
    normalized_loss_kg = to_kg(loss_value_normalized, unit)
    if normalized_loss_kg > input_qty_kg:
        raise ValidationError("Perte invalide : elle depasse la quantite d'entree de cette etape.")
    return loss_value_normalized, unit, normalized_loss_kg


def list_process_steps(db: Session, manager: User, batch_id=None):
    cooperative_id = get_manager_cooperative_id(manager)
    stmt = (
        select(ProcessStep)
        .join(Batch, Batch.id == ProcessStep.batch_id)
        .where(Batch.cooperative_id == cooperative_id)
        .order_by(ProcessStep.sequence_order.asc(), ProcessStep.date.asc(), ProcessStep.created_at.asc())
    )
    if batch_id is not None:
        stmt = stmt.where(ProcessStep.batch_id == batch_id)
    return db.scalars(stmt).all()


def get_process_step(db: Session, manager: User, step_id):
    return _require_step(db, manager, step_id)


def create_process_step(db: Session, manager: User, payload) -> ProcessStep:
    batch = require_batch(db, manager, payload.batch_id, with_steps=True)
    if batch.status in (BatchStatus.COMPLETED, BatchStatus.ARCHIVED):
        raise ValidationError("Cannot execute steps for a completed or archived batch.")

    plan = _ordered_plan(batch)
    executed = _sorted_steps(batch)
    next_order = len(executed) + 1
    if next_order > len(plan):
        raise ValidationError("All configured steps have already been executed for this lot.")

    expected_step_type = plan[next_order - 1]
    requested_type = (payload.type or "").strip()
    if requested_type and requested_type.lower() != expected_step_type.lower():
        raise ValidationError("Cette etape ne peut pas etre executee avant la precedente.")

    input_qty_kg = batch.initial_qty if not executed else executed[-1].qty_out
    loss_value, loss_unit, normalized_loss_kg = _validate_loss(payload.loss_value, payload.loss_unit, input_qty_kg)
    output_qty_kg = round_metric(input_qty_kg - normalized_loss_kg)
    execution_date = payload.date or date.today()

    step = ProcessStep(
        batch_id=batch.id,
        sequence_order=next_order,
        type=expected_step_type,
        date=execution_date,
        qty_in=input_qty_kg,
        qty_out=output_qty_kg,
        waste_qty=normalized_loss_kg,
        loss_value=loss_value,
        loss_unit=loss_unit,
        normalized_loss_value=normalized_loss_kg,
        notes=payload.notes.strip() if payload.notes else None,
        status=ProcessStepStatus.COMPLETED,
        executed_at=current_utc(),
        duration_minutes=payload.duration_minutes,
    )
    db.add(step)
    db.flush()

    batch.process_steps.append(step)
    refresh_batch_current_qty(batch)
    sync_batch_status_from_steps(db, batch)

    analytics.generate_recommendation(db, batch.id)

    db.commit()
    db.refresh(step)
    return step


def update_process_step(db: Session, manager: User, step_id, payload) -> ProcessStep:
    step = _require_step(db, manager, step_id)
    batch = step.batch
    if batch.status in (BatchStatus.COMPLETED, BatchStatus.ARCHIVED):
        raise ValidationError("Cannot modify steps on a completed or archived batch.")

    ordered = _sorted_steps(batch)
    latest = ordered[-1] if ordered else None
    if latest is None or latest.id != step.id:
        raise ValidationError("This step is locked because a later step already exists.")

    data = payload.model_dump(exclude_unset=True)
    next_loss_value = data.get("loss_value", step.loss_value)
    next_loss_unit = data.get("loss_unit", step.loss_unit)
    loss_value, loss_unit, normalized_loss_kg = _validate_loss(next_loss_value, next_loss_unit, step.qty_in)

    step.loss_value = loss_value
    step.loss_unit = loss_unit
    step.normalized_loss_value = normalized_loss_kg
    step.waste_qty = normalized_loss_kg
    step.qty_out = round_metric(step.qty_in - normalized_loss_kg)
    if "notes" in data:
        step.notes = data["notes"].strip() if data["notes"] else None
    if "duration_minutes" in data:
        step.duration_minutes = data["duration_minutes"]
    if "date" in data and data["date"] is not None:
        step.date = data["date"]

    step.status = ProcessStepStatus.COMPLETED
    step.executed_at = current_utc()

    refresh_batch_current_qty(batch)
    analytics.generate_recommendation(db, batch.id)

    db.commit()
    db.refresh(step)
    return step


def complete_process_step(db: Session, manager: User, step_id, _mark_batch_completed: bool) -> ProcessStep:
    step = _require_step(db, manager, step_id)
    batch = step.batch
    if batch.status == BatchStatus.ARCHIVED:
        raise ValidationError("Cannot complete a step on an archived batch.")

    if step.status == ProcessStepStatus.PENDING:
        loss_value, loss_unit, normalized_loss_kg = _validate_loss(step.loss_value, step.loss_unit, step.qty_in)
        step.loss_value = loss_value
        step.loss_unit = loss_unit
        step.normalized_loss_value = normalized_loss_kg
        step.waste_qty = normalized_loss_kg
        step.qty_out = round_metric(step.qty_in - normalized_loss_kg)
    step.status = ProcessStepStatus.COMPLETED
    step.executed_at = step.executed_at or current_utc()

    refresh_batch_current_qty(batch)
    sync_batch_status_from_steps(db, batch)

    analytics.generate_recommendation(db, batch.id)
    db.commit()
    db.refresh(step)
    return step


def delete_process_step(db: Session, manager: User, step_id):
    step = _require_step(db, manager, step_id)
    batch = step.batch
    if batch.status in (BatchStatus.COMPLETED, BatchStatus.ARCHIVED):
        raise ValidationError("Cannot delete a step from a completed or archived batch.")

    ordered = _sorted_steps(batch)
    latest = ordered[-1] if ordered else None
    if latest is None or latest.id != step.id:
        raise ValidationError("Only the latest executed step can be deleted.")

    db.delete(step)
    db.flush()

    db.refresh(batch)
    remaining_steps = _sorted_steps(batch)
    if remaining_steps:
        batch.current_qty = round_metric(remaining_steps[-1].qty_out)
    else:
        batch.current_qty = round_metric(batch.initial_qty)
    sync_batch_status_from_steps(db, batch)

    if remaining_steps:
        analytics.generate_recommendation(db, batch.id)

    db.commit()

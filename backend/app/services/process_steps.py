from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.batch import Batch
from app.models.enums import BatchStatus, ProcessStepStatus
from app.models.process_step import ProcessStep
from app.models.user import User
from app.services import analytics
from app.services.batches import refresh_batch_current_qty, require_batch, transition_batch_status
from app.services.helpers import get_manager_cooperative_id, parse_enum_value
from app.models.enums import BatchStatus as BatchStatusEnum
from app.utils.exceptions import NotFoundError, ValidationError


def _validate_step_payload(qty_in: float, qty_out: float, notes, waste_qty):
    if qty_in <= 0:
        raise ValidationError("qty_in must be greater than zero.")
    if qty_out < 0:
        raise ValidationError("qty_out must be greater than or equal to zero.")
    warning = qty_out > qty_in
    if warning and not notes:
        raise ValidationError("qty_out cannot exceed qty_in unless justified in notes.")
    resolved_waste = waste_qty if waste_qty is not None else max(qty_in - qty_out, 0.0)
    if resolved_waste < 0:
        raise ValidationError("waste_qty cannot be negative.")
    return resolved_waste, warning


def _require_step(db: Session, manager: User, step_id):
    cooperative_id = get_manager_cooperative_id(manager)
    step = db.scalar(
        select(ProcessStep)
        .join(Batch, Batch.id == ProcessStep.batch_id)
        .options(selectinload(ProcessStep.batch).selectinload(Batch.product))
        .where(ProcessStep.id == step_id, Batch.cooperative_id == cooperative_id)
    )
    if step is None:
        raise NotFoundError("Process step not found in the current cooperative.")
    return step


def list_process_steps(db: Session, manager: User, batch_id=None):
    cooperative_id = get_manager_cooperative_id(manager)
    stmt = (
        select(ProcessStep)
        .join(Batch, Batch.id == ProcessStep.batch_id)
        .where(Batch.cooperative_id == cooperative_id)
        .order_by(ProcessStep.date.desc(), ProcessStep.created_at.desc())
    )
    if batch_id is not None:
        stmt = stmt.where(ProcessStep.batch_id == batch_id)
    return db.scalars(stmt).all()


def get_process_step(db: Session, manager: User, step_id):
    return _require_step(db, manager, step_id)


def create_process_step(db: Session, manager: User, payload) -> ProcessStep:
    batch = require_batch(db, manager, payload.batch_id, with_steps=True)
    if batch.status in (BatchStatus.COMPLETED, BatchStatus.ARCHIVED):
        raise ValidationError("Cannot add process steps to a completed or archived batch.")

    waste_qty, warning = _validate_step_payload(payload.qty_in, payload.qty_out, payload.notes, payload.waste_qty)
    step_status = parse_enum_value(ProcessStepStatus, payload.status, "process step status")
    if warning:
        step_status = ProcessStepStatus.FLAGGED

    step = ProcessStep(
        batch_id=batch.id,
        type=payload.type.strip(),
        date=payload.date,
        qty_in=payload.qty_in,
        qty_out=payload.qty_out,
        waste_qty=waste_qty,
        notes=payload.notes.strip() if payload.notes else None,
        status=step_status,
        duration_minutes=payload.duration_minutes,
    )
    db.add(step)
    db.flush()

    batch.process_steps.append(step)
    refresh_batch_current_qty(batch)
    if batch.status == BatchStatus.CREATED:
        batch.status = BatchStatus.IN_PROGRESS

    if step.status in (ProcessStepStatus.COMPLETED, ProcessStepStatus.FLAGGED):
        analytics.generate_recommendation(db, batch.id)

    db.commit()
    db.refresh(step)
    return step


def update_process_step(db: Session, manager: User, step_id, payload) -> ProcessStep:
    step = _require_step(db, manager, step_id)
    batch = step.batch
    if batch.status in (BatchStatus.COMPLETED, BatchStatus.ARCHIVED):
        raise ValidationError("Cannot modify steps on a completed or archived batch.")

    data = payload.model_dump(exclude_unset=True)
    qty_in = data.get("qty_in", step.qty_in)
    qty_out = data.get("qty_out", step.qty_out)
    notes = data.get("notes", step.notes)
    waste_input = data["waste_qty"] if "waste_qty" in data else step.waste_qty
    waste_qty, warning = _validate_step_payload(qty_in, qty_out, notes, waste_input)

    if "type" in data:
        step.type = data["type"].strip()
    if "date" in data:
        step.date = data["date"]
    step.qty_in = qty_in
    step.qty_out = qty_out
    step.waste_qty = waste_qty
    if "notes" in data:
        step.notes = notes.strip() if notes else None
    if "duration_minutes" in data:
        step.duration_minutes = data["duration_minutes"]
    if "status" in data:
        step.status = parse_enum_value(ProcessStepStatus, data["status"], "process step status")
    if warning:
        step.status = ProcessStepStatus.FLAGGED

    refresh_batch_current_qty(batch)
    if step.status in (ProcessStepStatus.COMPLETED, ProcessStepStatus.FLAGGED):
        analytics.generate_recommendation(db, batch.id)
    db.commit()
    db.refresh(step)
    return step


def complete_process_step(db: Session, manager: User, step_id, mark_batch_completed: bool) -> ProcessStep:
    step = _require_step(db, manager, step_id)
    batch = step.batch
    if batch.status == BatchStatus.ARCHIVED:
        raise ValidationError("Cannot complete a step on an archived batch.")

    waste_qty, warning = _validate_step_payload(step.qty_in, step.qty_out, step.notes, step.waste_qty)
    step.waste_qty = waste_qty
    step.status = ProcessStepStatus.FLAGGED if warning else ProcessStepStatus.COMPLETED

    refresh_batch_current_qty(batch)
    if batch.status == BatchStatus.CREATED:
        batch.status = BatchStatus.IN_PROGRESS

    analytics.generate_recommendation(db, batch.id)
    if mark_batch_completed:
        transition_batch_status(db, batch, BatchStatusEnum.COMPLETED)

    db.commit()
    db.refresh(step)
    return step

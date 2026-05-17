from datetime import date
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.batch import Batch
from app.models.enums import BatchStatus, ProcessStepStatus
from app.models.mixins import current_utc
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.services import analytics
from app.services.batches import refresh_batch_current_qty, require_batch, sync_batch_status_from_steps
from app.services.helpers import get_manager_cooperative_id, normalize_mass_unit, round_metric, to_kg
from app.services.rag_reindex_hooks import reindex_process_step_if_needed, reindex_recommendation_if_needed
from app.utils.exceptions import NotFoundError, ValidationError
from app.services.stocks import apply_total_stock_delta


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


def _normalize_token(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", str(value or ""))
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
        .lower()
    )


def _canonical_step_name(value: str) -> str:
    token = _normalize_token(value)
    aliases = {
        "nettoyage": "nettoyage",
        "cleaning": "nettoyage",
        "sechage": "sechage",
        "drying": "sechage",
        "tri": "tri",
        "sorting": "tri",
        "emballage": "emballage",
        "conditionnement": "emballage",
        "packaging": "emballage",
    }
    return aliases.get(token, token)


def _status_from_payload(raw_status: str | None, *, default_completed: bool = True) -> ProcessStepStatus:
    if raw_status is None:
        return ProcessStepStatus.COMPLETED if default_completed else ProcessStepStatus.PENDING
    token = _normalize_token(raw_status)
    if token in {"pending", "in_progress", "inprogress", "started"}:
        return ProcessStepStatus.PENDING
    if token in {"done", "completed", "complete"}:
        return ProcessStepStatus.COMPLETED
    if token in {"cancelled", "canceled", "flagged"}:
        return ProcessStepStatus.FLAGGED
    raise ValidationError("Invalid process step status.")


def _validate_loss(loss_value: float, loss_unit: str, input_qty_kg: float) -> tuple[float, str, float]:
    unit = normalize_mass_unit(loss_unit)
    loss_value_normalized = round_metric(float(loss_value))
    if loss_value_normalized < 0:
        raise ValidationError("Loss must be greater than or equal to zero.")
    normalized_loss_kg = to_kg(loss_value_normalized, unit)
    if normalized_loss_kg > input_qty_kg:
        raise ValidationError("Perte invalide : elle depasse la quantite d'entree de cette etape.")
    return loss_value_normalized, unit, normalized_loss_kg


def _resolve_step_outcomes(
    *,
    input_qty_kg: float,
    qty_out: float | None,
    loss_value: float | None,
    loss_unit: str,
    require_output: bool,
) -> tuple[float, float, str, float]:
    if input_qty_kg <= 0:
        raise ValidationError("qty_in must be greater than zero.")
    if qty_out is None and loss_value is None and require_output:
        raise ValidationError("qty_out is required to complete a step.")
    if qty_out is not None:
        output_qty_kg = round_metric(float(qty_out))
        if output_qty_kg < 0:
            raise ValidationError("qty_out must be greater than or equal to zero.")
        if require_output and output_qty_kg <= 0:
            raise ValidationError("qty_out must be greater than zero to complete a step.")
        if output_qty_kg > input_qty_kg:
            raise ValidationError("qty_out cannot exceed qty_in for this step.")
        normalized_loss_kg = round_metric(max(input_qty_kg - output_qty_kg, 0.0))
        return output_qty_kg, normalized_loss_kg, "kg", normalized_loss_kg

    if loss_value is None:
        # start/in-progress placeholder without output yet
        return round_metric(input_qty_kg), 0.0, "kg", 0.0
    parsed_loss, parsed_unit, normalized_loss_kg = _validate_loss(float(loss_value), loss_unit, input_qty_kg)
    output_qty_kg = round_metric(input_qty_kg - normalized_loss_kg)
    return output_qty_kg, parsed_loss, parsed_unit, normalized_loss_kg


def _apply_step_stock_effect(db: Session, batch: Batch, step: ProcessStep, delta_loss_kg: float):
    if abs(delta_loss_kg) < 1e-9:
        return
    product = db.scalar(select(Product).where(Product.id == batch.product_id, Product.cooperative_id == batch.cooperative_id))
    if product is None:
        raise ValidationError("Batch product not found while applying stock movement.")
    apply_total_stock_delta(db, batch.cooperative_id, product, -float(delta_loss_kg), create_if_missing=True)
    movement_key = f"step:{step.id}:loss"
    existing = db.scalar(select(StockMovement).where(StockMovement.idempotency_key == movement_key))
    if existing is not None:
        existing.quantity_kg = abs(round_metric(step.normalized_loss_value))
        existing.movement_date = step.date
        existing.action_type = step.type
        existing.notes = step.notes
        existing.process_step_id = step.id
        return
    db.add(
        StockMovement(
            cooperative_id=batch.cooperative_id,
            product_id=batch.product_id,
            batch_id=batch.id,
            process_step_id=step.id,
            movement_type="out",
            action_type=step.type,
            source="post_harvest_step",
            quantity_kg=abs(round_metric(step.normalized_loss_value)),
            movement_date=step.date,
            idempotency_key=movement_key,
            notes=step.notes,
        )
    )


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
    if batch.status == BatchStatus.ARCHIVED:
        raise ValidationError("Cannot execute steps for a completed or archived batch.")
    if (batch.member_id is not None or batch.parcel_id is not None) and (batch.preharvest_completed_at is None or batch.confirmed_weight_kg is None):
        raise ValidationError("Post-harvest is locked until pre-harvest completion with confirmed weight.")

    plan = _ordered_plan(batch)
    executed = _sorted_steps(batch)
    if executed and executed[-1].status != ProcessStepStatus.COMPLETED:
        raise ValidationError("Complete the current in-progress step before starting the next one.")
    next_order = len(executed) + 1
    if next_order > len(plan):
        raise ValidationError("All configured steps have already been executed for this lot.")

    expected_step_type = plan[next_order - 1]
    requested_type = (payload.type or "").strip()
    if requested_type and _canonical_step_name(requested_type) != _canonical_step_name(expected_step_type):
        raise ValidationError("Cette etape ne peut pas etre executee avant la precedente.")

    input_qty_kg = (batch.confirmed_weight_kg if batch.confirmed_weight_kg is not None else batch.initial_qty) if not executed else executed[-1].qty_out
    if payload.qty_in is not None and abs(float(payload.qty_in) - float(input_qty_kg)) > 1e-6:
        raise ValidationError("qty_in for this step must match the previous stage output.")

    status_value = _status_from_payload(payload.status, default_completed=True)
    output_qty_kg, loss_value, loss_unit, normalized_loss_kg = _resolve_step_outcomes(
        input_qty_kg=float(input_qty_kg),
        qty_out=payload.qty_out,
        loss_value=payload.loss_value,
        loss_unit=payload.loss_unit,
        require_output=status_value == ProcessStepStatus.COMPLETED,
    )
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
        status=status_value,
        executed_at=current_utc() if status_value == ProcessStepStatus.COMPLETED else None,
        duration_minutes=payload.duration_minutes,
    )
    db.add(step)
    db.flush()
    if status_value == ProcessStepStatus.COMPLETED:
        _apply_step_stock_effect(db, batch, step, normalized_loss_kg)

    batch.process_steps.append(step)
    batch.postharvest_started_at = batch.postharvest_started_at or current_utc()
    refresh_batch_current_qty(batch)
    sync_batch_status_from_steps(db, batch)

    analytics.generate_recommendation(db, batch.id)

    db.commit()
    db.refresh(step)
    reindex_process_step_if_needed(
        db,
        current_user=manager,
        process_step_id=step.id,
        batch_id=batch.id,
        cooperative_id=batch.cooperative_id,
    )
    reindex_recommendation_if_needed(
        db,
        current_user=manager,
        batch_id=batch.id,
        cooperative_id=batch.cooperative_id,
    )
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
    old_normalized_loss_kg = step.normalized_loss_value
    next_qty_in = float(data.get("qty_in", step.qty_in))
    if next_qty_in <= 0:
        raise ValidationError("qty_in must be greater than zero.")
    step.qty_in = round_metric(next_qty_in)
    next_status = _status_from_payload(data.get("status"), default_completed=(step.status == ProcessStepStatus.COMPLETED))
    output_qty_kg, loss_value, loss_unit, normalized_loss_kg = _resolve_step_outcomes(
        input_qty_kg=float(step.qty_in),
        qty_out=data.get("qty_out", step.qty_out),
        loss_value=data.get("loss_value", step.loss_value),
        loss_unit=data.get("loss_unit", step.loss_unit),
        require_output=next_status == ProcessStepStatus.COMPLETED,
    )
    step.loss_value = loss_value
    step.loss_unit = loss_unit
    step.normalized_loss_value = normalized_loss_kg
    step.waste_qty = normalized_loss_kg
    step.qty_out = output_qty_kg
    if "notes" in data:
        step.notes = data["notes"].strip() if data["notes"] else None
    if "duration_minutes" in data:
        step.duration_minutes = data["duration_minutes"]
    if "date" in data and data["date"] is not None:
        step.date = data["date"]
    step.status = next_status
    step.executed_at = current_utc() if next_status == ProcessStepStatus.COMPLETED else None
    if next_status == ProcessStepStatus.COMPLETED:
        _apply_step_stock_effect(db, batch, step, normalized_loss_kg - old_normalized_loss_kg)

    refresh_batch_current_qty(batch)
    batch.postharvest_started_at = batch.postharvest_started_at or current_utc()
    analytics.generate_recommendation(db, batch.id)

    db.commit()
    db.refresh(step)
    reindex_process_step_if_needed(
        db,
        current_user=manager,
        process_step_id=step.id,
        batch_id=batch.id,
        cooperative_id=batch.cooperative_id,
    )
    reindex_recommendation_if_needed(
        db,
        current_user=manager,
        batch_id=batch.id,
        cooperative_id=batch.cooperative_id,
    )
    return step


def complete_process_step(db: Session, manager: User, step_id, payload) -> ProcessStep:
    step = _require_step(db, manager, step_id)
    batch = step.batch
    if batch.status == BatchStatus.ARCHIVED:
        raise ValidationError("Cannot complete a step on an archived batch.")

    old_normalized_loss_kg = step.normalized_loss_value
    patch = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else {}
    output_qty_kg, loss_value, loss_unit, normalized_loss_kg = _resolve_step_outcomes(
        input_qty_kg=float(step.qty_in),
        qty_out=patch.get("qty_out"),
        loss_value=patch.get("loss_value"),
        loss_unit=patch.get("loss_unit", step.loss_unit),
        require_output=True,
    )
    if step.status == ProcessStepStatus.PENDING and patch.get("qty_out") is None and patch.get("loss_value") is None:
        raise ValidationError("Cannot complete a step without qty_out.")
    step.loss_value = loss_value
    step.loss_unit = loss_unit
    step.normalized_loss_value = normalized_loss_kg
    step.waste_qty = normalized_loss_kg
    step.qty_out = output_qty_kg
    if "date" in patch and patch["date"] is not None:
        step.date = patch["date"]
    if "notes" in patch:
        step.notes = patch["notes"].strip() if patch["notes"] else None
    if "duration_minutes" in patch:
        step.duration_minutes = patch["duration_minutes"]
    step.status = ProcessStepStatus.COMPLETED
    step.executed_at = current_utc()
    _apply_step_stock_effect(db, batch, step, normalized_loss_kg - old_normalized_loss_kg)

    refresh_batch_current_qty(batch)
    batch.postharvest_started_at = batch.postharvest_started_at or current_utc()
    sync_batch_status_from_steps(db, batch)

    analytics.generate_recommendation(db, batch.id)
    db.commit()
    db.refresh(step)
    reindex_process_step_if_needed(
        db,
        current_user=manager,
        process_step_id=step.id,
        batch_id=batch.id,
        cooperative_id=batch.cooperative_id,
    )
    reindex_recommendation_if_needed(
        db,
        current_user=manager,
        batch_id=batch.id,
        cooperative_id=batch.cooperative_id,
    )
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

    movement = db.scalar(select(StockMovement).where(StockMovement.idempotency_key == f"step:{step.id}:loss"))
    if movement is not None:
        db.delete(movement)
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
    reindex_process_step_if_needed(
        db,
        current_user=manager,
        process_step_id=step.id,
        batch_id=batch.id,
        cooperative_id=batch.cooperative_id,
    )
    reindex_recommendation_if_needed(
        db,
        current_user=manager,
        batch_id=batch.id,
        cooperative_id=batch.cooperative_id,
    )
    if step.normalized_loss_value > 0:
        product = db.scalar(select(Product).where(Product.id == batch.product_id, Product.cooperative_id == batch.cooperative_id))
        if product is not None:
            apply_total_stock_delta(db, batch.cooperative_id, product, float(step.normalized_loss_value), create_if_missing=True)

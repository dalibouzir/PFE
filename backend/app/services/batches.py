from datetime import date
import json

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, object_session, selectinload

from app.models.batch import Batch
from app.models.enums import BatchStatus, ProcessStepStatus
from app.models.input import Input
from app.models.member import Member
from app.models.parcel import Parcel
from app.models.product import Product
from app.models.farmer_advance import FarmerAdvance
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.models.mixins import current_utc
from app.schemas.batch import BatchMaterialBalanceRead, BatchMaterialBalanceStageRead, BatchRead
from app.schemas.farmer_advance import FarmerAdvanceCreate
from app.services import analytics as analytics_service
from app.services import farmer_advances as farmer_advance_service
from app.services.helpers import from_kg, get_manager_cooperative_id, normalize_mass_unit, normalize_product_code, round_metric, to_kg
from app.services.rag_reindex_hooks import reindex_batch_if_needed
from app.services.stocks import (
    apply_processed_output_delta,
    apply_reserved_stock_delta,
    available_stock_kg,
    get_stock_by_product,
    normalize_stock_grade,
    release_reserved_stock_for_lot,
    reserve_stock_for_lot,
)
from app.utils.exceptions import ConflictError, NotFoundError, ValidationError

ALLOWED_PREHARVEST_STEP_STATUSES = {"todo", "in_progress", "done"}
LINKED_COLLECTE_SOURCES = {"lot_linked_collecte", "pre_harvest_confirmed_weight"}
POSTHARVEST_STOCK_NOTE_PREFIX = "POSTHARVEST_STOCK:"


def _read_postharvest_stock_meta(batch: Batch) -> dict | None:
    note = (batch.status_note or "").strip()
    if not note.startswith(POSTHARVEST_STOCK_NOTE_PREFIX):
        return None
    payload = note[len(POSTHARVEST_STOCK_NOTE_PREFIX) :].strip()
    if not payload:
        return None
    try:
        parsed = json.loads(payload)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _write_postharvest_stock_meta(batch: Batch, *, product_id, grade: str, allocated_qty_kg: float):
    meta = {
        "product_id": str(product_id),
        "grade": normalize_stock_grade(grade),
        "allocated_qty_kg": round_metric(float(allocated_qty_kg)),
    }
    batch.status_note = f"{POSTHARVEST_STOCK_NOTE_PREFIX}{json.dumps(meta, ensure_ascii=False)}"


def _postharvest_status(batch: Batch) -> str:
    if batch.status in (BatchStatus.COMPLETED, BatchStatus.ARCHIVED):
        return "post_recolte_completed"
    if batch.postharvest_started_at is not None or len(batch.process_steps or []) > 0:
        return "in_post_recolte"
    if batch.preharvest_completed_at is not None and batch.confirmed_weight_kg is not None:
        return "ready_post_recolte"
    return "not_ready_post_recolte"


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
    return db.scalars(select(Batch).where(Batch.cooperative_id == cooperative_id).order_by(Batch.creation_date.desc(), Batch.created_at.desc())).all()


def _normalize_steps(raw_steps: list[str]) -> list[str]:
    ordered = [str(raw).strip() for raw in raw_steps if str(raw).strip()]
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
    return f"{prefix}{max_increment + 1:03d}"


def _generate_postharvest_reference(db: Session, product_name: str, *, year: int) -> str:
    product_code = normalize_product_code(product_name)
    prefix = f"POST-{product_code}-{year}-"
    rows = db.scalars(select(Batch.postharvest_reference).where(func.lower(Batch.postharvest_reference).like(f"{prefix.lower()}%"))).all()
    max_increment = 0
    for ref in rows:
        if not ref:
            continue
        suffix = ref[len(prefix) :]
        if suffix.isdigit():
            max_increment = max(max_increment, int(suffix))
    return f"{prefix}{max_increment + 1:03d}"


def _fallback_collecte_reference(input_row: Input | None) -> str | None:
    if input_row is None:
        return None
    if input_row.collecte_reference and input_row.collecte_reference.strip():
        return input_row.collecte_reference.strip()
    return f"COL-HIST-{str(input_row.id)[:8].upper()}"


def _compute_estimated_qty_kg(payload, unit: str) -> tuple[float, float | None, str | None]:
    surface_ha = payload.surface_ha
    expected_yield = payload.expected_yield_kg_per_ha
    expected_losses = payload.expected_losses_kg or 0.0
    estimated = to_kg(payload.initial_qty, unit)
    if surface_ha is not None and expected_yield is not None:
        estimated = round_metric(max((float(surface_ha) * float(expected_yield)) - float(expected_losses), 0.0))
    override = None
    override_reason = payload.estimated_qty_override_reason
    if override is not None:
        if not override_reason or not override_reason.strip():
            raise ValidationError("Estimated quantity override requires a justification.")
        estimated = round_metric(float(override))
    return estimated, override, override_reason.strip() if override_reason else None


def serialize_batch(batch: Batch) -> BatchRead:
    unit = normalize_mass_unit(batch.unit)
    initial_display = from_kg(batch.initial_qty, unit)
    current_display = from_kg(batch.current_qty, unit)
    collecte = None
    stock_in_exists = False
    try:
        db = object_session(batch)
        if db is not None:
            collecte = db.scalar(
                select(Input).where(
                    Input.cooperative_id == batch.cooperative_id,
                    Input.batch_id == batch.id,
                    Input.source_type.in_(tuple(LINKED_COLLECTE_SOURCES)),
                )
            )
            stock_in_exists = (
                db.scalar(
                    select(StockMovement.id).where(
                        StockMovement.cooperative_id == batch.cooperative_id,
                        StockMovement.batch_id == batch.id,
                        StockMovement.movement_type == "in",
                        StockMovement.source.in_(tuple(LINKED_COLLECTE_SOURCES)),
                    ).limit(1)
                )
                is not None
            )
    except Exception:
        collecte = None
        stock_in_exists = False

    postharvest_status = _postharvest_status(batch)
    status_note = batch.status_note
    if postharvest_status == "ready_post_recolte" and (collecte is not None or stock_in_exists):
        status_note = "Collecté · En attente Post-récolte"

    return BatchRead(
        id=batch.id,
        cooperative_id=batch.cooperative_id,
        product_id=batch.product_id,
        member_id=batch.member_id,
        parcel_id=batch.parcel_id,
        code=batch.code,
        preharvest_reference=batch.code,
        collecte_reference=_fallback_collecte_reference(collecte),
        postharvest_reference=batch.postharvest_reference,
        creation_date=batch.creation_date,
        unit=unit,
        ordered_process_steps=batch.ordered_process_steps or [],
        initial_qty=initial_display,
        current_qty=current_display,
        surface_ha=batch.surface_ha,
        expected_yield_kg_per_ha=batch.expected_yield_kg_per_ha,
        expected_losses_kg=batch.expected_losses_kg,
        estimated_qty_kg=batch.estimated_qty_kg,
        estimated_qty_override_reason=batch.estimated_qty_override_reason,
        estimated_charge_fcfa=batch.estimated_charge_fcfa,
        charge_approved_at=batch.charge_approved_at,
        charge_approved_by_user_id=batch.charge_approved_by_user_id,
        preharvest_activated_at=batch.preharvest_activated_at,
        preharvest_step_statuses=batch.preharvest_step_statuses,
        preharvest_completed_at=batch.preharvest_completed_at,
        confirmed_weight_kg=batch.confirmed_weight_kg,
        collecte_input_id=collecte.id if collecte is not None else None,
        collecte_created=collecte is not None,
        stock_in_created=stock_in_exists,
        postharvest_started_at=batch.postharvest_started_at,
        postharvest_status=postharvest_status,
        status_note=status_note,
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
    product = db.scalar(select(Product).where(Product.id == payload.product_id, Product.cooperative_id == cooperative_id))
    if product is None:
        raise NotFoundError("Product not found in the current cooperative.")

    if payload.member_id is not None:
        member = db.scalar(select(Member).where(Member.id == payload.member_id, Member.cooperative_id == cooperative_id))
        if member is None:
            raise NotFoundError("Farmer/member not found in the current cooperative.")
    if payload.parcel_id is not None:
        parcel = db.scalar(select(Parcel).where(Parcel.id == payload.parcel_id, Parcel.cooperative_id == cooperative_id))
        if parcel is None:
            raise NotFoundError("Parcel not found in the current cooperative.")

    unit = normalize_mass_unit(payload.unit)
    ordered_steps = _normalize_steps(payload.process_steps)
    estimated_qty_kg, override_kg, override_reason = _compute_estimated_qty_kg(payload, unit)
    # Auto-charge policy: when not explicitly provided (or invalid), align estimated charge
    # with computed estimated quantity so pre-harvest lots are never created with 0 FCFA by default.
    estimated_charge_fcfa = payload.estimated_charge_fcfa
    if estimated_charge_fcfa is None or float(estimated_charge_fcfa) <= 0:
        estimated_charge_fcfa = round_metric(max(float(estimated_qty_kg), 0.0))
    legacy_mode = payload.member_id is None and payload.parcel_id is None
    if legacy_mode:
        reserve_stock_for_lot(db, cooperative_id, product, estimated_qty_kg, grade=payload.grade)

    attempts = 0
    while attempts < 5:
        attempts += 1
        code = _generate_lot_reference(db, product.name)
        batch = Batch(
            cooperative_id=cooperative_id,
            product_id=product.id,
            member_id=payload.member_id,
            parcel_id=payload.parcel_id,
            code=code,
            creation_date=payload.creation_date,
            unit=unit,
            ordered_process_steps=ordered_steps,
            initial_qty=estimated_qty_kg,
            current_qty=estimated_qty_kg if legacy_mode else 0.0,
            surface_ha=payload.surface_ha,
            expected_yield_kg_per_ha=payload.expected_yield_kg_per_ha,
            expected_losses_kg=payload.expected_losses_kg,
            estimated_qty_kg=estimated_qty_kg,
            estimated_qty_override_reason=override_reason,
            estimated_charge_fcfa=estimated_charge_fcfa,
            preharvest_step_statuses=_build_default_preharvest_step_statuses(ordered_steps),
            status=BatchStatus.CREATED,
            created_by_user_id=manager.id,
        )
        db.add(batch)
        try:
            db.commit()
            db.refresh(batch)
            reindex_batch_if_needed(db, current_user=manager, batch_id=batch.id, cooperative_id=cooperative_id)
            return batch
        except IntegrityError:
            db.rollback()
            if attempts >= 5:
                raise ConflictError("Unable to generate a unique lot reference. Please retry.")

    raise ConflictError("Unable to create lot.")


def refresh_batch_current_qty(batch: Batch):
    if batch.process_steps:
        latest_step = sorted(batch.process_steps, key=lambda step: (step.sequence_order, step.date, step.created_at, step.id))[-1]
        batch.current_qty = round_metric(latest_step.qty_out)
    elif batch.confirmed_weight_kg is not None:
        batch.current_qty = round_metric(batch.confirmed_weight_kg)
    else:
        batch.current_qty = 0.0
    return batch.current_qty


def _completed_steps(batch: Batch):
    return [
        step
        for step in (batch.process_steps or [])
        if step.status == ProcessStepStatus.COMPLETED
    ]


def update_batch(db: Session, manager: User, batch_id, payload) -> Batch:
    batch = require_batch(db, manager, batch_id, with_steps=True)
    data = payload.model_dump(exclude_unset=True)
    if "process_steps" in data:
        if batch.process_steps:
            raise ValidationError("Ordered process steps cannot be changed once execution has started.")
        batch.ordered_process_steps = _normalize_steps(data["process_steps"])
        if batch.preharvest_activated_at is None and batch.preharvest_completed_at is None:
            batch.preharvest_step_statuses = _build_default_preharvest_step_statuses(batch.ordered_process_steps)
    if "estimated_charge_fcfa" in data:
        if batch.charge_approved_at is not None:
            raise ValidationError("Estimated charge cannot be changed after approval.")
        batch.estimated_charge_fcfa = round_metric(float(data["estimated_charge_fcfa"]))

    db.commit()
    db.refresh(batch)
    reindex_batch_if_needed(db, current_user=manager, batch_id=batch.id, cooperative_id=batch.cooperative_id)
    return batch


def approve_estimated_charge(db: Session, manager: User, batch_id):
    batch = require_batch(db, manager, batch_id, with_steps=True)
    if batch.estimated_charge_fcfa is None or batch.estimated_charge_fcfa <= 0:
        raise ValidationError("No estimated charge to approve for this lot.")
    existing_advance = db.scalar(
        select(FarmerAdvance).where(
            FarmerAdvance.cooperative_id == batch.cooperative_id,
            FarmerAdvance.batch_id == batch.id,
            FarmerAdvance.source_type == "pre_harvest_charge_approval",
        )
    )
    if existing_advance is not None:
        return batch
    if batch.member_id is None:
        raise ValidationError("Farmer/member is required to approve charge.")

    advance = farmer_advance_service.create_farmer_advance(
        db,
        manager,
        FarmerAdvanceCreate(
            farmer_id=batch.member_id,
            batch_id=batch.id,
            parcel_id=batch.parcel_id,
            product_id=batch.product_id,
            source_type="pre_harvest_charge_approval",
            amount_fcfa=batch.estimated_charge_fcfa,
            reason=f"Charge pre-recolte lot {batch.code}",
            advance_date=date.today(),
            note=f"Source: Pre-recolte charge approval ({batch.code})",
        ),
    )
    batch.charge_approved_at = batch.charge_approved_at or advance.created_at
    batch.charge_approved_by_user_id = manager.id
    db.commit()
    db.refresh(batch)
    return batch


def activate_preharvest(db: Session, manager: User, batch_id):
    batch = require_batch(db, manager, batch_id, with_steps=True)
    if batch.preharvest_completed_at is not None:
        raise ValidationError("Cannot activate pre-harvest: lot is already completed.")
    if batch.preharvest_activated_at is not None:
        return batch
    batch.preharvest_activated_at = current_utc()
    if not batch.preharvest_step_statuses:
        batch.preharvest_step_statuses = _build_default_preharvest_step_statuses(batch.ordered_process_steps or [])
    db.commit()
    db.refresh(batch)
    return batch


def _preharvest_execution_started(batch: Batch) -> bool:
    statuses = batch.preharvest_step_statuses or []
    for item in statuses:
        status = str(item.get("status", "")).strip().lower()
        if status in {"in_progress", "done"}:
            return True
    return False


def stop_preharvest(db: Session, manager: User, batch_id) -> Batch:
    batch = require_batch(db, manager, batch_id, with_steps=True)
    if batch.preharvest_activated_at is None:
        raise ValidationError("Cannot stop pre-harvest: lot is not active.")
    if batch.preharvest_completed_at is not None:
        raise ValidationError("Cannot stop pre-harvest: lot is already completed.")
    if batch.confirmed_weight_kg is not None:
        raise ValidationError("Cannot stop pre-harvest: confirmed weight already exists.")
    if _preharvest_execution_started(batch):
        raise ValidationError("Cannot stop pre-harvest once execution has started.")

    batch.preharvest_activated_at = None
    db.commit()
    db.refresh(batch)
    return batch

def _build_default_preharvest_step_statuses(ordered_steps: list[str]) -> list[dict]:
    return [
        {
            "index": index,
            "name": step.strip(),
            "status": "todo",
            "updated_at": None,
            "execution_date": None,
            "duration_minutes": None,
            "summary": None,
        }
        for index, step in enumerate(ordered_steps)
        if step and step.strip()
    ]

def _normalize_preharvest_step_statuses(statuses: list) -> list[dict]:
    normalized: list[dict] = []
    for raw in statuses:
        index = int(raw.index if hasattr(raw, "index") else raw.get("index"))
        name = str(raw.name if hasattr(raw, "name") else raw.get("name", "")).strip()
        status = str(raw.status if hasattr(raw, "status") else raw.get("status", "")).strip().lower()
        if index < 0:
            raise ValidationError("Invalid pre-harvest step status index.")
        if not name:
            raise ValidationError("Pre-harvest step name is required.")
        if status not in ALLOWED_PREHARVEST_STEP_STATUSES:
            raise ValidationError("Invalid pre-harvest step status value.")
        updated_at = raw.updated_at if hasattr(raw, "updated_at") else raw.get("updated_at")
        execution_date = raw.execution_date if hasattr(raw, "execution_date") else raw.get("execution_date")
        duration_minutes = raw.duration_minutes if hasattr(raw, "duration_minutes") else raw.get("duration_minutes")
        summary = raw.summary if hasattr(raw, "summary") else raw.get("summary")
        if duration_minutes is not None:
            try:
                duration_minutes = int(duration_minutes)
            except (TypeError, ValueError):
                raise ValidationError("Invalid pre-harvest step duration value.")
            if duration_minutes < 0:
                raise ValidationError("Invalid pre-harvest step duration value.")
        if summary is not None:
            summary = str(summary).strip()
            if not summary:
                summary = None
        normalized.append(
            {
                "index": index,
                "name": name,
                "status": status,
                "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") and updated_at is not None else None,
                "execution_date": execution_date.isoformat()
                if hasattr(execution_date, "isoformat") and execution_date is not None
                else (str(execution_date).strip() if execution_date else None),
                "duration_minutes": duration_minutes,
                "summary": summary,
            }
        )
    return sorted(normalized, key=lambda item: item["index"])

def update_preharvest_step_statuses(db: Session, manager: User, batch_id, statuses: list) -> Batch:
    batch = require_batch(db, manager, batch_id, with_steps=True)
    if batch.preharvest_activated_at is None:
        raise ValidationError("Cannot update pre-harvest step statuses while lot is in preparation.")
    if batch.preharvest_completed_at is not None:
        raise ValidationError("Cannot update pre-harvest step statuses for a ready post-harvest lot.")
    normalized = _normalize_preharvest_step_statuses(statuses)
    batch.preharvest_step_statuses = normalized
    db.commit()
    db.refresh(batch)
    return batch

def _all_preharvest_statuses_done(batch: Batch) -> bool:
    statuses = batch.preharvest_step_statuses or []
    if not statuses:
        return False
    return all(str(item.get("status", "")).lower() == "done" for item in statuses)


def complete_preharvest(db: Session, manager: User, batch_id, notes: str | None = None, collecte_date: date | None = None):
    batch = require_batch(db, manager, batch_id, with_steps=True)
    if batch.preharvest_activated_at is not None and not _all_preharvest_statuses_done(batch):
        raise ValidationError("Cannot complete pre-harvest before all active pre-harvest steps are done.")

    required = [item.strip().lower() for item in (batch.ordered_process_steps or []) if item.strip()]
    done = [item.type.strip().lower() for item in (batch.process_steps or [])]
    if done:
        missing = [step for step in required if step not in done]
        if missing:
            raise ValidationError("Cannot complete pre-harvest before all required steps are completed.")

    existing_collecte = db.scalar(
        select(Input).where(
            Input.cooperative_id == batch.cooperative_id,
            Input.batch_id == batch.id,
            Input.source_type.in_(tuple(LINKED_COLLECTE_SOURCES)),
        )
    )
    batch.preharvest_completed_at = batch.preharvest_completed_at or current_utc()
    if existing_collecte is not None:
        batch.confirmed_weight_kg = round_metric(existing_collecte.quantity)
        batch.current_qty = round_metric(existing_collecte.quantity)
    batch.status_note = notes.strip() if notes else batch.status_note
    db.commit()
    db.refresh(batch)
    return batch


def update_batch_status(db: Session, manager: User, batch_id, payload) -> Batch:
    require_batch(db, manager, batch_id, with_steps=True)
    raise ValidationError("Le statut du lot est calcule automatiquement depuis l'avancement des etapes. Modification manuelle desactivee.")


def transition_batch_status(db: Session, batch: Batch, next_status: BatchStatus):
    if batch.status == next_status:
        return batch
    if batch.status == BatchStatus.ARCHIVED and next_status != BatchStatus.ARCHIVED:
        raise ValidationError("Archived batches cannot be reopened.")
    if batch.status == BatchStatus.COMPLETED and next_status not in (BatchStatus.COMPLETED, BatchStatus.ARCHIVED):
        raise ValidationError("Completed batches can only be archived.")
    if next_status == BatchStatus.COMPLETED and batch.status != BatchStatus.COMPLETED:
        product = batch.product
        if product is not None:
            meta = _read_postharvest_stock_meta(batch)
            output_grade = None
            if meta is not None:
                output_grade = normalize_stock_grade(str(meta.get("grade") or "Non spécifié"))
            if (
                meta is None
                and batch.member_id is None
                and batch.parcel_id is None
                and batch.status in (BatchStatus.CREATED, BatchStatus.IN_PROGRESS)
            ):
                release_reserved_stock_for_lot(db, batch.cooperative_id, product, batch.initial_qty)
            if meta is not None:
                remaining = max(float(batch.current_qty or 0.0), 0.0)
                if remaining > 0:
                    apply_reserved_stock_delta(
                        db,
                        batch.cooperative_id,
                        product,
                        -remaining,
                        create_if_missing=False,
                        grade=output_grade,
                    )
            apply_processed_output_delta(db, batch.cooperative_id, product, batch.current_qty, grade=output_grade)
    batch.status = next_status
    return batch


def sync_batch_status_from_steps(db: Session, batch: Batch):
    executed_steps = len(_completed_steps(batch))
    ordered_steps = [str(item).strip() for item in (batch.ordered_process_steps or []) if str(item).strip()]
    if len(batch.process_steps or []) > 0 and batch.postharvest_started_at is None:
        batch.postharvest_started_at = current_utc()
    if executed_steps == 0:
        batch.status = BatchStatus.IN_PROGRESS if (batch.postharvest_started_at is not None or len(batch.process_steps or []) > 0) else BatchStatus.CREATED
        return batch
    if ordered_steps and executed_steps >= len(ordered_steps):
        transition_batch_status(db, batch, BatchStatus.COMPLETED)
        return batch
    batch.status = BatchStatus.IN_PROGRESS
    return batch


def start_postharvest(db: Session, manager: User, batch_id, payload=None):
    batch = require_batch(db, manager, batch_id, with_steps=True)
    if batch.status in (BatchStatus.COMPLETED, BatchStatus.ARCHIVED):
        raise ValidationError("Cannot start post-harvest on a completed/archived lot.")
    if payload is None:
        raise ValidationError("Sélectionnez un grade de stock et une quantité pour démarrer la post-récolte.")
    selected_product_id = payload.product_id
    selected_grade = normalize_stock_grade(payload.grade)
    requested_qty_kg = round_metric(float(payload.quantity_kg))

    if requested_qty_kg is not None and selected_grade is not None:
        if selected_product_id != batch.product_id:
            raise ValidationError("Le produit sélectionné doit correspondre au produit du lot.")
        stock_bucket = get_stock_by_product(db, batch.cooperative_id, selected_product_id, selected_grade)
        if stock_bucket is None:
            raise ValidationError("Bucket de stock introuvable pour le produit/grade sélectionné.")
        available_kg = available_stock_kg(stock_bucket)
        # Backward compatibility for free lots: creation historically reserved
        # `initial_qty` before post-harvest is started. In the merged UI flow
        # (create -> start), that reservation must be reused, not reserved twice.
        legacy_reserved_credit_kg = 0.0
        is_free_lot = batch.member_id is None and batch.parcel_id is None
        has_postharvest_meta = _read_postharvest_stock_meta(batch) is not None
        if is_free_lot and not has_postharvest_meta and batch.status == BatchStatus.CREATED:
            legacy_reserved_credit_kg = round_metric(float(batch.initial_qty or 0.0))
        effective_available_kg = round_metric(available_kg + legacy_reserved_credit_kg)
        if requested_qty_kg > effective_available_kg:
            raise ValidationError("Quantité demandée supérieure au stock disponible pour ce grade.")
        reserve_delta_kg = round_metric(requested_qty_kg - legacy_reserved_credit_kg)
        if abs(reserve_delta_kg) > 1e-9:
            apply_reserved_stock_delta(
                db,
                batch.cooperative_id,
                batch.product,
                reserve_delta_kg,
                create_if_missing=False,
                grade=selected_grade,
            )
        batch.confirmed_weight_kg = requested_qty_kg
        batch.current_qty = requested_qty_kg
        _write_postharvest_stock_meta(
            batch,
            product_id=batch.product_id,
            grade=selected_grade,
            allocated_qty_kg=requested_qty_kg,
        )
    if batch.postharvest_started_at is None:
        batch.postharvest_started_at = current_utc()
    if not (batch.postharvest_reference or "").strip():
        product_name = batch.product.name if batch.product is not None else "PROD"
        year = batch.postharvest_started_at.year if batch.postharvest_started_at is not None else date.today().year
        batch.postharvest_reference = _generate_postharvest_reference(db, product_name, year=year)
    if batch.status == BatchStatus.CREATED:
        batch.status = BatchStatus.IN_PROGRESS
    db.commit()
    db.refresh(batch)
    return batch


def _required_steps_for_batch(batch: Batch) -> list[str]:
    return [str(item).strip() for item in (batch.ordered_process_steps or []) if str(item).strip()]


def complete_postharvest(db: Session, manager: User, batch_id):
    batch = require_batch(db, manager, batch_id, with_steps=True)
    required = _required_steps_for_batch(batch)
    completed = _completed_steps(batch)
    if len(completed) < len(required):
        raise ValidationError("Cannot complete post-harvest before all required steps are completed.")
    transition_batch_status(db, batch, BatchStatus.COMPLETED)
    db.commit()
    db.refresh(batch)
    return batch


def get_material_balance(db: Session, manager: User, batch_id) -> BatchMaterialBalanceRead:
    batch = require_batch(db, manager, batch_id, with_steps=True)
    steps = sorted(batch.process_steps or [], key=lambda item: (item.sequence_order, item.date, item.created_at, item.id))
    completed = [step for step in steps if step.status == ProcessStepStatus.COMPLETED]

    initial_confirmed = float(batch.confirmed_weight_kg if batch.confirmed_weight_kg is not None else batch.initial_qty)
    current_qty = float(batch.current_qty or 0.0)
    total_loss_qty = max(initial_confirmed - current_qty, 0.0)
    total_loss_pct = (total_loss_qty / initial_confirmed) * 100.0 if initial_confirmed > 0 else 0.0
    total_efficiency_pct = (current_qty / initial_confirmed) * 100.0 if initial_confirmed > 0 else 0.0

    stage_rows: dict[str, dict] = {}
    for step in completed:
        key = str(step.type).strip().lower()
        bucket = stage_rows.setdefault(
            key,
            {"stage": key, "step_count": 0, "qty_in": 0.0, "qty_out": 0.0, "loss_qty": 0.0, "loss_pct_sum": 0.0, "efficiency_pct_sum": 0.0},
        )
        metrics = analytics_service.compute_process_metrics(step)
        bucket["step_count"] += 1
        bucket["qty_in"] += float(step.qty_in or 0.0)
        bucket["qty_out"] += float(step.qty_out or 0.0)
        bucket["loss_qty"] += float(metrics["waste_qty"])
        bucket["loss_pct_sum"] += float(metrics["loss_pct"])
        bucket["efficiency_pct_sum"] += float(metrics["efficiency_pct"])

    per_stage = [
        BatchMaterialBalanceStageRead(
            stage=item["stage"],
            step_count=int(item["step_count"]),
            qty_in=round_metric(item["qty_in"]),
            qty_out=round_metric(item["qty_out"]),
            loss_qty=round_metric(item["loss_qty"]),
            loss_pct=round_metric(item["loss_pct_sum"] / item["step_count"]) if item["step_count"] else 0.0,
            efficiency_pct=round_metric(item["efficiency_pct_sum"] / item["step_count"]) if item["step_count"] else 0.0,
        )
        for item in stage_rows.values()
    ]
    per_stage.sort(key=lambda item: item.stage)

    return BatchMaterialBalanceRead(
        batch_id=batch.id,
        cooperative_id=batch.cooperative_id,
        postharvest_status=_postharvest_status(batch),
        initial_confirmed_qty=round_metric(initial_confirmed),
        current_qty=round_metric(current_qty),
        final_output_qty=round_metric(current_qty) if batch.status in (BatchStatus.COMPLETED, BatchStatus.ARCHIVED) else None,
        total_loss_qty=round_metric(total_loss_qty),
        total_loss_pct=round_metric(total_loss_pct),
        total_efficiency_pct=round_metric(total_efficiency_pct),
        steps_completed=len(completed),
        steps_required=len(_required_steps_for_batch(batch)),
        per_stage=per_stage,
        process_steps=[analytics_service.serialize_process_step(step) for step in steps],
    )


def delete_batch(db: Session, manager: User, batch_id):
    batch = require_batch(db, manager, batch_id, with_steps=True)
    if batch.charge_approved_at is not None:
        raise ValidationError("Cannot delete lot: charge was already approved.")
    if batch.preharvest_activated_at is not None:
        raise ValidationError("Cannot delete lot: pre-harvest was already activated.")
    if batch.preharvest_completed_at is not None:
        raise ValidationError("Cannot delete lot: pre-harvest is already completed.")
    if batch.confirmed_weight_kg is not None:
        raise ValidationError("Cannot delete lot: confirmed weight already exists.")
    if _preharvest_execution_started(batch):
        raise ValidationError("Cannot delete lot: pre-harvest execution already started.")
    if batch.process_steps:
        raise ValidationError("Cannot delete lot: post-harvest execution already started.")
    existing_advance = db.scalar(
        select(FarmerAdvance.id).where(
            FarmerAdvance.cooperative_id == batch.cooperative_id,
            FarmerAdvance.batch_id == batch.id,
        ).limit(1)
    )
    if existing_advance is not None:
        raise ValidationError("Cannot delete lot: finance activity already exists.")
    existing_input = db.scalar(
        select(Input.id).where(
            Input.cooperative_id == batch.cooperative_id,
            Input.batch_id == batch.id,
        ).limit(1)
    )
    if existing_input is not None:
        raise ValidationError("Cannot delete lot: collecte/input activity already exists.")
    existing_movement = db.scalar(
        select(StockMovement.id).where(
            StockMovement.cooperative_id == batch.cooperative_id,
            StockMovement.batch_id == batch.id,
        ).limit(1)
    )
    if existing_movement is not None:
        raise ValidationError("Cannot delete lot: stock movement activity already exists.")
    input_rows = db.scalars(
        select(Input).where(
            Input.cooperative_id == batch.cooperative_id,
            Input.batch_id == batch.id,
            Input.source_type.in_(tuple(LINKED_COLLECTE_SOURCES)),
        )
    ).all()
    for input_row in input_rows:
        db.delete(input_row)
    db.delete(batch)
    db.commit()
    reindex_batch_if_needed(db, current_user=manager, batch_id=batch.id, cooperative_id=batch.cooperative_id)

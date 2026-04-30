from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import PreHarvestStepStatus
from app.models.member import Member
from app.models.mixins import current_utc
from app.models.parcel import Parcel
from app.models.pre_harvest_step import PreHarvestStep
from app.models.user import User
from app.schemas.pre_harvest import PreHarvestStepUpdate
from app.services.helpers import ensure_can_delete, ensure_can_write, get_manager_cooperative_id, round_metric
from app.utils.exceptions import NotFoundError, ValidationError

DEFAULT_STEP_TEMPLATE = [
    {"step_order": 1, "step_key": "pruning", "category": "entretien", "label": "Taille & élagage", "icon": "✂️"},
    {"step_order": 2, "step_key": "phytosanitary_treatment", "category": "traitement", "label": "Traitement phytosanitaire", "icon": "🧪"},
    {"step_order": 3, "step_key": "fertilization", "category": "fertilisation", "label": "Fertilisation", "icon": "🌿"},
    {"step_order": 4, "step_key": "irrigation", "category": "irrigation", "label": "Irrigation", "icon": "💧"},
    {"step_order": 5, "step_key": "harvest", "category": "recolte", "label": "Récolte", "icon": "🧺"},
    {"step_order": 6, "step_key": "transport_to_storage", "category": "transport", "label": "Transport vers magasin", "icon": "🚛"},
]


def _require_member_in_scope(db: Session, cooperative_id, member_id):
    member = db.scalar(
        select(Member).where(Member.id == member_id, Member.cooperative_id == cooperative_id)
    )
    if member is None:
        raise NotFoundError("Farmer not found in the current cooperative.")
    return member


def _require_parcel(db: Session, cooperative_id, parcel_id) -> Parcel:
    parcel = db.scalar(
        select(Parcel).where(Parcel.id == parcel_id, Parcel.cooperative_id == cooperative_id)
    )
    if parcel is None:
        raise NotFoundError("Parcel not found in the current cooperative.")
    return parcel


def _create_default_steps(db: Session, cooperative_id, parcel: Parcel, user_id) -> int:
    created = 0
    for step in DEFAULT_STEP_TEMPLATE:
        db.add(
            PreHarvestStep(
                cooperative_id=cooperative_id,
                parcel_id=parcel.id,
                member_id=parcel.member_id,
                step_order=step["step_order"],
                step_key=step["step_key"],
                category=step["category"],
                label=step["label"],
                icon=step["icon"],
                created_by_user_id=user_id,
                updated_by_user_id=user_id,
            )
        )
        created += 1
    return created


def list_parcels(db: Session, current_user: User, member_id=None):
    cooperative_id = get_manager_cooperative_id(current_user)
    stmt = select(Parcel).where(Parcel.cooperative_id == cooperative_id).order_by(Parcel.created_at.desc())
    if member_id is not None:
        stmt = stmt.where(Parcel.member_id == member_id)
    return db.scalars(stmt).all()


def create_parcel(db: Session, current_user: User, payload) -> Parcel:
    ensure_can_write(current_user)
    cooperative_id = get_manager_cooperative_id(current_user)
    member = _require_member_in_scope(db, cooperative_id, payload.farmer_id)

    parcel = Parcel(
        cooperative_id=cooperative_id,
        member_id=member.id,
        name=payload.name.strip(),
        surface_ha=float(payload.surface_ha),
        main_culture=payload.main_culture.strip(),
        variety=payload.variety.strip() if payload.variety else None,
        tree_count=payload.tree_count,
    )
    db.add(parcel)
    db.flush()
    _create_default_steps(db, cooperative_id, parcel, current_user.id)
    db.commit()
    db.refresh(parcel)
    return parcel


def update_parcel(db: Session, current_user: User, parcel_id, payload) -> Parcel:
    ensure_can_write(current_user)
    cooperative_id = get_manager_cooperative_id(current_user)
    parcel = _require_parcel(db, cooperative_id, parcel_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        parcel.name = data["name"].strip()
    if "surface_ha" in data and data["surface_ha"] is not None:
        parcel.surface_ha = float(data["surface_ha"])
    if "main_culture" in data and data["main_culture"] is not None:
        parcel.main_culture = data["main_culture"].strip()
    if "variety" in data:
        parcel.variety = data["variety"].strip() if data["variety"] else None
    if "tree_count" in data:
        if data["tree_count"] is not None and data["tree_count"] < 0:
            raise ValidationError("tree_count must be >= 0.")
        parcel.tree_count = data["tree_count"]
    db.commit()
    db.refresh(parcel)
    return parcel


def delete_parcel(db: Session, current_user: User, parcel_id):
    ensure_can_delete(current_user)
    cooperative_id = get_manager_cooperative_id(current_user)
    parcel = _require_parcel(db, cooperative_id, parcel_id)
    db.delete(parcel)
    db.commit()


def list_pre_harvest_steps(db: Session, current_user: User, parcel_id) -> Sequence[PreHarvestStep]:
    cooperative_id = get_manager_cooperative_id(current_user)
    _require_parcel(db, cooperative_id, parcel_id)
    return db.scalars(
        select(PreHarvestStep)
        .where(PreHarvestStep.cooperative_id == cooperative_id, PreHarvestStep.parcel_id == parcel_id)
        .order_by(PreHarvestStep.step_order.asc(), PreHarvestStep.created_at.asc())
    ).all()


def init_pre_harvest_steps(db: Session, current_user: User, parcel_id) -> int:
    ensure_can_write(current_user)
    cooperative_id = get_manager_cooperative_id(current_user)
    parcel = _require_parcel(db, cooperative_id, parcel_id)
    existing = db.scalar(
        select(func.count(PreHarvestStep.id)).where(
            PreHarvestStep.cooperative_id == cooperative_id,
            PreHarvestStep.parcel_id == parcel_id,
        )
    ) or 0
    if existing > 0:
        return 0
    created = _create_default_steps(db, cooperative_id, parcel, current_user.id)
    db.commit()
    return created


def _validate_step_editable(db: Session, cooperative_id, step: PreHarvestStep):
    latest = db.scalar(
        select(PreHarvestStep)
        .where(
            PreHarvestStep.cooperative_id == cooperative_id,
            PreHarvestStep.parcel_id == step.parcel_id,
        )
        .order_by(PreHarvestStep.step_order.desc(), PreHarvestStep.updated_at.desc())
        .limit(1)
    )
    if latest is None:
        return
    if latest.id != step.id and step.status.value == "completed":
        raise ValidationError("Only the latest completed step can be edited.")


def update_pre_harvest_step(db: Session, current_user: User, parcel_id, step_id, payload: PreHarvestStepUpdate) -> PreHarvestStep:
    ensure_can_write(current_user)
    cooperative_id = get_manager_cooperative_id(current_user)
    _require_parcel(db, cooperative_id, parcel_id)
    step = db.scalar(
        select(PreHarvestStep).where(
            PreHarvestStep.id == step_id,
            PreHarvestStep.parcel_id == parcel_id,
            PreHarvestStep.cooperative_id == cooperative_id,
        )
    )
    if step is None:
        raise NotFoundError("Pre-harvest step not found.")
    _validate_step_editable(db, cooperative_id, step)

    step.quantity_value = round_metric(payload.quantity_value) if payload.quantity_value is not None else None
    step.quantity_unit = payload.quantity_unit.strip() if payload.quantity_unit else None
    step.operation_cost_fcfa = round_metric(payload.operation_cost_fcfa) if payload.operation_cost_fcfa is not None else None
    step.realization_date = payload.realization_date
    step.observations = payload.observations.strip() if payload.observations else None
    step.status = PreHarvestStepStatus.COMPLETED
    step.completed_at = current_utc()
    step.updated_by_user_id = current_user.id
    db.commit()
    db.refresh(step)
    return step


def complete_pre_harvest_step(db: Session, current_user: User, parcel_id, step_id):
    ensure_can_write(current_user)
    cooperative_id = get_manager_cooperative_id(current_user)
    step = db.scalar(
        select(PreHarvestStep).where(
            PreHarvestStep.id == step_id,
            PreHarvestStep.parcel_id == parcel_id,
            PreHarvestStep.cooperative_id == cooperative_id,
        )
    )
    if step is None:
        raise NotFoundError("Pre-harvest step not found.")
    step.status = PreHarvestStepStatus.COMPLETED
    step.completed_at = step.completed_at or current_utc()
    step.updated_by_user_id = current_user.id
    db.commit()
    db.refresh(step)
    return step

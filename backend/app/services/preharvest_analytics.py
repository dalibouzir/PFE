from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import PreHarvestStepStatus
from app.models.global_charge import GlobalCharge
from app.models.member import Member
from app.models.parcel import Parcel
from app.models.pre_harvest_step import PreHarvestStep
from app.models.user import User
from app.services.helpers import get_manager_cooperative_id, round_metric


def _operation_cost_rows(db: Session, cooperative_id):
    return db.execute(
        select(
            PreHarvestStep.member_id,
            PreHarvestStep.parcel_id,
            func.coalesce(func.sum(PreHarvestStep.operation_cost_fcfa), 0.0).label("cost"),
        )
        .where(
            PreHarvestStep.cooperative_id == cooperative_id,
            PreHarvestStep.operation_cost_fcfa.is_not(None),
        )
        .group_by(PreHarvestStep.member_id, PreHarvestStep.parcel_id)
    ).all()


def _charge_rows(db: Session, cooperative_id):
    return db.execute(
        select(
            GlobalCharge.member_id,
            GlobalCharge.parcel_id,
            func.coalesce(func.sum(GlobalCharge.amount_fcfa), 0.0).label("amount"),
        )
        .where(GlobalCharge.cooperative_id == cooperative_id)
        .group_by(GlobalCharge.member_id, GlobalCharge.parcel_id)
    ).all()


def get_summary(db: Session, current_user: User):
    cooperative_id = get_manager_cooperative_id(current_user)

    step_total = db.scalar(
        select(func.coalesce(func.sum(PreHarvestStep.operation_cost_fcfa), 0.0)).where(
            PreHarvestStep.cooperative_id == cooperative_id,
            PreHarvestStep.operation_cost_fcfa.is_not(None),
        )
    ) or 0.0
    charge_total = db.scalar(
        select(func.coalesce(func.sum(GlobalCharge.amount_fcfa), 0.0)).where(
            GlobalCharge.cooperative_id == cooperative_id
        )
    ) or 0.0
    total_cost = round_metric(step_total + charge_total)

    completed_steps = int(db.scalar(
        select(func.count(PreHarvestStep.id)).where(
            PreHarvestStep.cooperative_id == cooperative_id,
            PreHarvestStep.status == PreHarvestStepStatus.COMPLETED,
        )
    ) or 0)
    pending_steps = int(db.scalar(
        select(func.count(PreHarvestStep.id)).where(
            PreHarvestStep.cooperative_id == cooperative_id,
            PreHarvestStep.status == PreHarvestStepStatus.PENDING,
        )
    ) or 0)

    member_totals = defaultdict(float)
    parcel_totals = defaultdict(float)
    for row in _operation_cost_rows(db, cooperative_id):
        member_totals[row.member_id] += float(row.cost or 0.0)
        parcel_totals[row.parcel_id] += float(row.cost or 0.0)
    for row in _charge_rows(db, cooperative_id):
        member_totals[row.member_id] += float(row.amount or 0.0)
        if row.parcel_id is not None:
            parcel_totals[row.parcel_id] += float(row.amount or 0.0)

    top_farmer_id = max(member_totals, key=member_totals.get, default=None)
    top_parcel_id = max(parcel_totals, key=parcel_totals.get, default=None)
    top_farmer = db.scalar(select(Member).where(Member.id == top_farmer_id)) if top_farmer_id else None
    top_parcel = db.scalar(select(Parcel).where(Parcel.id == top_parcel_id)) if top_parcel_id else None

    return {
        "total_pre_harvest_cost_fcfa": total_cost,
        "completed_steps_count": completed_steps,
        "pending_steps_count": pending_steps,
        "most_expensive_farmer_id": top_farmer.id if top_farmer else None,
        "most_expensive_farmer_name": top_farmer.full_name if top_farmer else None,
        "most_expensive_parcel_id": top_parcel.id if top_parcel else None,
        "most_expensive_parcel_name": top_parcel.name if top_parcel else None,
    }


def costs_by_farmer(db: Session, current_user: User):
    cooperative_id = get_manager_cooperative_id(current_user)
    member_totals = defaultdict(float)
    for row in _operation_cost_rows(db, cooperative_id):
        member_totals[row.member_id] += float(row.cost or 0.0)
    for row in _charge_rows(db, cooperative_id):
        member_totals[row.member_id] += float(row.amount or 0.0)
    members = db.scalars(select(Member).where(Member.cooperative_id == cooperative_id)).all()
    return sorted(
        [
            {"id": member.id, "label": member.full_name, "amount_fcfa": round_metric(member_totals.get(member.id, 0.0))}
            for member in members
        ],
        key=lambda x: x["amount_fcfa"],
        reverse=True,
    )


def costs_by_parcel(db: Session, current_user: User):
    cooperative_id = get_manager_cooperative_id(current_user)
    parcel_totals = defaultdict(float)
    for row in _operation_cost_rows(db, cooperative_id):
        parcel_totals[row.parcel_id] += float(row.cost or 0.0)
    for row in _charge_rows(db, cooperative_id):
        if row.parcel_id is not None:
            parcel_totals[row.parcel_id] += float(row.amount or 0.0)
    rows = db.scalars(select(Parcel).where(Parcel.cooperative_id == cooperative_id)).all()
    items = []
    for row in rows:
        total = float(parcel_totals.get(row.id, 0.0))
        area = float(row.surface_ha or 0.0)
        per_ha = round_metric(total / area) if area > 0 else None
        items.append(
            {
                "id": row.id,
                "label": row.name,
                "amount_fcfa": round_metric(total),
                "area_hectares": round_metric(area),
                "cost_per_hectare_fcfa": per_ha,
            }
        )
    return sorted(items, key=lambda x: x["amount_fcfa"], reverse=True)


def costs_by_crop(db: Session, current_user: User):
    cooperative_id = get_manager_cooperative_id(current_user)
    parcel_by_id = {
        parcel.id: parcel
        for parcel in db.scalars(select(Parcel).where(Parcel.cooperative_id == cooperative_id)).all()
    }
    crop_totals = defaultdict(float)
    for row in _operation_cost_rows(db, cooperative_id):
        parcel = parcel_by_id.get(row.parcel_id)
        if parcel is None:
            continue
        crop_totals[parcel.main_culture] += float(row.cost or 0.0)
    for row in _charge_rows(db, cooperative_id):
        parcel = parcel_by_id.get(row.parcel_id)
        if parcel is None:
            continue
        crop_totals[parcel.main_culture] += float(row.amount or 0.0)
    rows = sorted(crop_totals.items(), key=lambda x: x[1], reverse=True)
    return [
        {"id": None, "label": label, "amount_fcfa": round_metric(amount)}
        for label, amount in rows
    ]


def costs_by_hectare(db: Session, current_user: User):
    return costs_by_parcel(db, current_user)

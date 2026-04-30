from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import TreasuryTransactionStatus, TreasuryTransactionType
from app.models.global_charge import GlobalCharge
from app.models.member import Member
from app.models.parcel import Parcel
from app.models.treasury_transaction import TreasuryTransaction
from app.models.user import User
from app.services.helpers import ensure_can_delete, ensure_can_write, get_manager_cooperative_id, round_metric
from app.utils.exceptions import NotFoundError, ValidationError

GLOBAL_CHARGE_SOURCE = "global_charge"


def _build_reference() -> str:
    return f"TRS-{uuid.uuid4().hex[:10].upper()}"


def _require_farmer(db: Session, cooperative_id, farmer_id):
    farmer = db.scalar(
        select(Member).where(Member.id == farmer_id, Member.cooperative_id == cooperative_id)
    )
    if farmer is None:
        raise NotFoundError("Farmer not found in the current cooperative.")
    return farmer


def _require_parcel_for_farmer(db: Session, cooperative_id, farmer_id, parcel_id):
    if parcel_id is None:
        return None
    parcel = db.scalar(
        select(Parcel).where(
            Parcel.id == parcel_id,
            Parcel.cooperative_id == cooperative_id,
            Parcel.member_id == farmer_id,
        )
    )
    if parcel is None:
        raise ValidationError("Selected parcel does not belong to this farmer.")
    return parcel


def _serialize_charge(charge: GlobalCharge):
    return {
        "id": charge.id,
        "cooperative_id": charge.cooperative_id,
        "member_id": charge.member_id,
        "parcel_id": charge.parcel_id,
        "pre_harvest_step_id": charge.pre_harvest_step_id,
        "batch_id": charge.batch_id,
        "process_step_id": charge.process_step_id,
        "charge_type": charge.charge_type,
        "label": charge.label,
        "amount_fcfa": charge.amount_fcfa,
        "date": charge.date,
        "notes": charge.notes,
        "source_type": charge.source_type,
        "treasury_transaction_id": charge.treasury_transaction_id,
        "created_at": charge.created_at,
        "updated_at": charge.updated_at,
    }


def _create_or_sync_treasury_for_charge(db: Session, charge: GlobalCharge):
    transaction = None
    if charge.treasury_transaction_id:
        transaction = db.scalar(
            select(TreasuryTransaction).where(TreasuryTransaction.id == charge.treasury_transaction_id)
        )
    if transaction is None:
        transaction = TreasuryTransaction(
            cooperative_id=charge.cooperative_id,
            reference=_build_reference(),
            transaction_date=charge.date,
            type=TreasuryTransactionType.EXPENSE,
            category=f"charge_{charge.charge_type}",
            label=charge.label,
            amount_fcfa=round_metric(charge.amount_fcfa),
            note=charge.notes,
            status=TreasuryTransactionStatus.RECORDED,
            source_type=GLOBAL_CHARGE_SOURCE,
            source_id=charge.id,
            farmer_id=charge.member_id,
        )
        db.add(transaction)
        db.flush()
        charge.treasury_transaction_id = transaction.id
    else:
        transaction.transaction_date = charge.date
        transaction.type = TreasuryTransactionType.EXPENSE
        transaction.category = f"charge_{charge.charge_type}"
        transaction.label = charge.label
        transaction.amount_fcfa = round_metric(charge.amount_fcfa)
        transaction.note = charge.notes
        transaction.status = TreasuryTransactionStatus.RECORDED
        transaction.source_type = GLOBAL_CHARGE_SOURCE
        transaction.source_id = charge.id
        transaction.farmer_id = charge.member_id
    return transaction


def list_farmer_charges(db: Session, current_user: User, farmer_id):
    cooperative_id = get_manager_cooperative_id(current_user)
    _require_farmer(db, cooperative_id, farmer_id)
    items = db.scalars(
        select(GlobalCharge)
        .where(GlobalCharge.cooperative_id == cooperative_id, GlobalCharge.member_id == farmer_id)
        .order_by(GlobalCharge.date.desc(), GlobalCharge.created_at.desc())
    ).all()
    total = round_metric(sum(item.amount_fcfa for item in items))
    return {
        "total_amount_fcfa": total,
        "items": [_serialize_charge(item) for item in items],
    }


def list_charges(db: Session, current_user: User):
    cooperative_id = get_manager_cooperative_id(current_user)
    items = db.scalars(
        select(GlobalCharge)
        .where(GlobalCharge.cooperative_id == cooperative_id)
        .order_by(GlobalCharge.date.desc(), GlobalCharge.created_at.desc())
    ).all()
    return [_serialize_charge(item) for item in items]


def create_charge(db: Session, current_user: User, payload):
    ensure_can_write(current_user)
    cooperative_id = get_manager_cooperative_id(current_user)
    farmer = _require_farmer(db, cooperative_id, payload.farmer_id)
    parcel = _require_parcel_for_farmer(db, cooperative_id, farmer.id, payload.parcel_id)
    charge = GlobalCharge(
        cooperative_id=cooperative_id,
        member_id=farmer.id,
        parcel_id=parcel.id if parcel else None,
        charge_type=payload.charge_type.strip(),
        label=payload.label.strip(),
        amount_fcfa=round_metric(payload.amount_fcfa),
        date=payload.date,
        notes=payload.notes.strip() if payload.notes else None,
        source_type="manual",
    )
    db.add(charge)
    db.flush()
    _create_or_sync_treasury_for_charge(db, charge)
    db.commit()
    db.refresh(charge)
    return _serialize_charge(charge)


def update_charge(db: Session, current_user: User, charge_id, payload):
    ensure_can_write(current_user)
    cooperative_id = get_manager_cooperative_id(current_user)
    charge = db.scalar(
        select(GlobalCharge).where(GlobalCharge.id == charge_id, GlobalCharge.cooperative_id == cooperative_id)
    )
    if charge is None:
        raise NotFoundError("Charge not found in the current cooperative.")
    data = payload.model_dump(exclude_unset=True)
    if "parcel_id" in data:
        parcel = _require_parcel_for_farmer(db, cooperative_id, charge.member_id, data["parcel_id"])
        charge.parcel_id = parcel.id if parcel else None
    if "charge_type" in data and data["charge_type"] is not None:
        charge.charge_type = data["charge_type"].strip()
    if "label" in data and data["label"] is not None:
        charge.label = data["label"].strip()
    if "amount_fcfa" in data and data["amount_fcfa"] is not None:
        charge.amount_fcfa = round_metric(data["amount_fcfa"])
    if "date" in data and data["date"] is not None:
        charge.date = data["date"]
    if "notes" in data:
        charge.notes = data["notes"].strip() if data["notes"] else None
    _create_or_sync_treasury_for_charge(db, charge)
    db.commit()
    db.refresh(charge)
    return _serialize_charge(charge)


def delete_charge(db: Session, current_user: User, charge_id):
    ensure_can_delete(current_user)
    cooperative_id = get_manager_cooperative_id(current_user)
    charge = db.scalar(
        select(GlobalCharge).where(GlobalCharge.id == charge_id, GlobalCharge.cooperative_id == cooperative_id)
    )
    if charge is None:
        raise NotFoundError("Charge not found in the current cooperative.")
    if charge.treasury_transaction_id is not None:
        transaction = db.scalar(
            select(TreasuryTransaction).where(TreasuryTransaction.id == charge.treasury_transaction_id)
        )
        if transaction is not None:
            transaction.status = TreasuryTransactionStatus.CANCELLED
    db.delete(charge)
    db.commit()


def charges_total_by_farmer(db: Session, cooperative_id):
    return db.execute(
        select(
            GlobalCharge.member_id,
            func.coalesce(func.sum(GlobalCharge.amount_fcfa), 0.0).label("total"),
        )
        .where(GlobalCharge.cooperative_id == cooperative_id)
        .group_by(GlobalCharge.member_id)
    ).all()

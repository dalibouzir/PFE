from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import TreasuryTransactionStatus, TreasuryTransactionType
from app.models.member import Member
from app.models.treasury_transaction import TreasuryTransaction
from app.models.user import User
from app.schemas.treasury import TreasuryStatsRead, TreasuryTransactionRead
from app.services.helpers import get_manager_cooperative_id, parse_enum_value, round_metric
from app.utils.exceptions import NotFoundError, ValidationError

FARMER_ADVANCE_SOURCE = "farmer_advance"
MANUAL_SOURCE = "manual"


def _normalize_source_type(raw_source_type: str | None) -> str:
    value = (raw_source_type or MANUAL_SOURCE).strip().lower()
    if not value:
        return MANUAL_SOURCE
    return value


def _require_member_in_scope(db: Session, cooperative_id, farmer_id):
    if farmer_id is None:
        return None
    member = db.scalar(select(Member).where(Member.id == farmer_id, Member.cooperative_id == cooperative_id))
    if member is None:
        raise NotFoundError("Farmer not found in the current cooperative.")
    return member


def _build_reference() -> str:
    return f"TRS-{uuid.uuid4().hex[:10].upper()}"


def build_farmer_advance_label(farmer_name: str, reason: str) -> str:
    return f"Avance producteur - {farmer_name} - {reason}"


def serialize_treasury_transaction(transaction: TreasuryTransaction, farmer_name: str | None = None) -> TreasuryTransactionRead:
    return TreasuryTransactionRead(
        id=transaction.id,
        cooperative_id=transaction.cooperative_id,
        reference=transaction.reference,
        transaction_date=transaction.transaction_date,
        type=transaction.type.value,
        category=transaction.category,
        label=transaction.label,
        amount_fcfa=round_metric(transaction.amount_fcfa),
        note=transaction.note,
        status=transaction.status.value,
        source_type=transaction.source_type,
        source_id=transaction.source_id,
        farmer_id=transaction.farmer_id,
        farmer_name=farmer_name if farmer_name is not None else (transaction.farmer.full_name if transaction.farmer else None),
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
    )


def create_linked_farmer_advance_transaction(
    db: Session,
    cooperative_id,
    farmer: Member,
    amount_fcfa: float,
    transaction_date,
    reason: str,
    note: str | None,
    source_id,
) -> TreasuryTransaction:
    transaction = TreasuryTransaction(
        cooperative_id=cooperative_id,
        reference=_build_reference(),
        transaction_date=transaction_date,
        type=TreasuryTransactionType.EXPENSE,
        category="avance_producteur",
        label=build_farmer_advance_label(farmer.full_name, reason),
        amount_fcfa=round_metric(amount_fcfa),
        note=note.strip() if note else None,
        status=TreasuryTransactionStatus.RECORDED,
        source_type=FARMER_ADVANCE_SOURCE,
        source_id=source_id,
        farmer_id=farmer.id,
    )
    db.add(transaction)
    db.flush()
    return transaction


def sync_linked_farmer_advance_transaction(
    transaction: TreasuryTransaction,
    farmer: Member,
    amount_fcfa: float,
    transaction_date,
    reason: str,
    note: str | None,
) -> TreasuryTransaction:
    transaction.transaction_date = transaction_date
    transaction.amount_fcfa = round_metric(amount_fcfa)
    transaction.label = build_farmer_advance_label(farmer.full_name, reason)
    transaction.note = note.strip() if note else None
    transaction.farmer_id = farmer.id
    transaction.type = TreasuryTransactionType.EXPENSE
    transaction.category = "avance_producteur"
    transaction.source_type = FARMER_ADVANCE_SOURCE
    transaction.status = TreasuryTransactionStatus.RECORDED
    return transaction


def cancel_linked_farmer_advance_transaction(transaction: TreasuryTransaction):
    transaction.status = TreasuryTransactionStatus.CANCELLED
    return transaction


def _require_treasury_transaction(db: Session, manager: User, transaction_id):
    cooperative_id = get_manager_cooperative_id(manager)
    transaction = db.scalar(
        select(TreasuryTransaction).where(
            TreasuryTransaction.id == transaction_id,
            TreasuryTransaction.cooperative_id == cooperative_id,
        )
    )
    if transaction is None:
        raise NotFoundError("Treasury transaction not found in the current cooperative.")
    return transaction


def list_treasury_transactions(
    db: Session,
    manager: User,
    transaction_type: str | None = None,
    source_type: str | None = None,
    search: str | None = None,
    sort_order: str = "desc",
):
    cooperative_id = get_manager_cooperative_id(manager)
    stmt = (
        select(TreasuryTransaction, Member.full_name)
        .outerjoin(Member, Member.id == TreasuryTransaction.farmer_id)
        .where(TreasuryTransaction.cooperative_id == cooperative_id)
    )

    if transaction_type and transaction_type.lower() != "all":
        parsed_type = parse_enum_value(TreasuryTransactionType, transaction_type.lower(), "transaction type")
        stmt = stmt.where(TreasuryTransaction.type == parsed_type)
    if source_type and source_type.lower() != "all":
        normalized_source = source_type.lower()
        if normalized_source == MANUAL_SOURCE:
            stmt = stmt.where(TreasuryTransaction.source_type.in_([MANUAL_SOURCE, "other"]))
        else:
            stmt = stmt.where(TreasuryTransaction.source_type == normalized_source)
    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(TreasuryTransaction.label).like(needle),
                func.lower(func.coalesce(Member.full_name, "")).like(needle),
            )
        )

    is_asc = sort_order.lower() == "asc"
    if is_asc:
        stmt = stmt.order_by(TreasuryTransaction.transaction_date.asc(), TreasuryTransaction.created_at.asc())
    else:
        stmt = stmt.order_by(TreasuryTransaction.transaction_date.desc(), TreasuryTransaction.created_at.desc())

    rows = db.execute(stmt).all()
    return [serialize_treasury_transaction(transaction, farmer_name) for transaction, farmer_name in rows]


def create_treasury_transaction(db: Session, manager: User, payload) -> TreasuryTransactionRead:
    cooperative_id = get_manager_cooperative_id(manager)
    source_type = _normalize_source_type(payload.source_type)
    if source_type == FARMER_ADVANCE_SOURCE:
        raise ValidationError("Transactions de source farmer_advance sont créées uniquement via les avances producteurs.")

    farmer = _require_member_in_scope(db, cooperative_id, payload.farmer_id)
    transaction = TreasuryTransaction(
        cooperative_id=cooperative_id,
        reference=_build_reference(),
        transaction_date=payload.transaction_date,
        type=parse_enum_value(TreasuryTransactionType, payload.type.lower(), "transaction type"),
        category=payload.category.strip(),
        label=payload.label.strip(),
        amount_fcfa=round_metric(payload.amount_fcfa),
        note=payload.note.strip() if payload.note else None,
        status=TreasuryTransactionStatus.RECORDED,
        source_type=source_type,
        source_id=None,
        farmer_id=farmer.id if farmer else None,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return serialize_treasury_transaction(transaction)


def update_treasury_transaction(db: Session, manager: User, transaction_id, payload) -> TreasuryTransactionRead:
    cooperative_id = get_manager_cooperative_id(manager)
    transaction = _require_treasury_transaction(db, manager, transaction_id)
    if transaction.source_type == FARMER_ADVANCE_SOURCE:
        raise ValidationError("Cette transaction est liée à une avance producteur. Modifiez l'avance correspondante.")

    data = payload.model_dump(exclude_unset=True)
    if "transaction_date" in data and data["transaction_date"] is not None:
        transaction.transaction_date = data["transaction_date"]
    if "type" in data and data["type"] is not None:
        transaction.type = parse_enum_value(TreasuryTransactionType, data["type"].lower(), "transaction type")
    if "category" in data and data["category"] is not None:
        transaction.category = data["category"].strip()
    if "label" in data and data["label"] is not None:
        transaction.label = data["label"].strip()
    if "amount_fcfa" in data and data["amount_fcfa"] is not None:
        transaction.amount_fcfa = round_metric(data["amount_fcfa"])
    if "note" in data:
        transaction.note = data["note"].strip() if data["note"] else None
    if "source_type" in data and data["source_type"] is not None:
        normalized_source = _normalize_source_type(data["source_type"])
        if normalized_source == FARMER_ADVANCE_SOURCE:
            raise ValidationError("Le type de source farmer_advance est réservé aux avances producteurs.")
        transaction.source_type = normalized_source
    if "farmer_id" in data:
        farmer = _require_member_in_scope(db, cooperative_id, data["farmer_id"])
        transaction.farmer_id = farmer.id if farmer else None

    db.commit()
    db.refresh(transaction)
    return serialize_treasury_transaction(transaction)


def cancel_treasury_transaction(db: Session, manager: User, transaction_id) -> TreasuryTransactionRead:
    transaction = _require_treasury_transaction(db, manager, transaction_id)
    if transaction.source_type == FARMER_ADVANCE_SOURCE:
        raise ValidationError("Annulez l'avance producteur liée depuis la page Avances Producteurs.")
    transaction.status = TreasuryTransactionStatus.CANCELLED
    db.commit()
    db.refresh(transaction)
    return serialize_treasury_transaction(transaction)


def get_treasury_stats(db: Session, manager: User) -> TreasuryStatsRead:
    cooperative_id = get_manager_cooperative_id(manager)
    recorded_status = TreasuryTransactionStatus.RECORDED

    total_given = db.scalar(
        select(func.coalesce(func.sum(TreasuryTransaction.amount_fcfa), 0.0)).where(
            TreasuryTransaction.cooperative_id == cooperative_id,
            TreasuryTransaction.status == recorded_status,
            TreasuryTransaction.type == TreasuryTransactionType.EXPENSE,
            TreasuryTransaction.source_type == FARMER_ADVANCE_SOURCE,
        )
    )
    total_expenses = db.scalar(
        select(func.coalesce(func.sum(TreasuryTransaction.amount_fcfa), 0.0)).where(
            TreasuryTransaction.cooperative_id == cooperative_id,
            TreasuryTransaction.status == recorded_status,
            TreasuryTransaction.type == TreasuryTransactionType.EXPENSE,
        )
    )
    total_income = db.scalar(
        select(func.coalesce(func.sum(TreasuryTransaction.amount_fcfa), 0.0)).where(
            TreasuryTransaction.cooperative_id == cooperative_id,
            TreasuryTransaction.status == recorded_status,
            TreasuryTransaction.type == TreasuryTransactionType.INCOME,
        )
    )
    return TreasuryStatsRead(
        total_given=round_metric(total_given or 0.0),
        total_expenses=round_metric(total_expenses or 0.0),
        total_income=round_metric(total_income or 0.0),
        current_balance=round_metric((total_income or 0.0) - (total_expenses or 0.0)),
    )

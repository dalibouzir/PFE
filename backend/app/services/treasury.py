from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.models.enums import TreasuryTransactionStatus, TreasuryTransactionType
from app.models.member import Member
from app.models.treasury_transaction import TreasuryTransaction
from app.models.user import User
from app.schemas.treasury import TreasuryStatsRead, TreasuryTransactionRead
from app.services.helpers import get_manager_cooperative_id, parse_enum_value, round_metric
from app.services import uploads as upload_service
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


def _normalize_legacy_treasury_status_rows(db: Session, cooperative_id) -> None:
    # Older rows may persist lowercase status values while the ORM enum for this
    # column is name-backed. Normalize in-place to avoid read-time enum crashes.
    db.execute(
        text(
            """
            UPDATE treasury_transactions
            SET status = CASE
                WHEN status = 'non_enregistre' THEN 'NON_ENREGISTRE'
                WHEN status = 'enregistre_sans_justificatif' THEN 'ENREGISTRE_SANS_JUSTIFICATIF'
                WHEN status = 'enregistre_complet' THEN 'ENREGISTRE_COMPLET'
                WHEN status = 'cancelled' THEN 'CANCELLED'
                WHEN status = 'recorded' THEN 'RECORDED'
                ELSE status
            END
            WHERE cooperative_id = :cooperative_id
              AND status IN (
                'non_enregistre',
                'enregistre_sans_justificatif',
                'enregistre_complet',
                'cancelled',
                'recorded'
              )
            """
        ),
        {"cooperative_id": cooperative_id},
    )
    db.commit()


def build_farmer_advance_label(farmer_name: str, reason: str) -> str:
    return f"Avance producteur - {farmer_name} - {reason}"


def _public_treasury_status(status: TreasuryTransactionStatus) -> TreasuryTransactionStatus:
    if status == TreasuryTransactionStatus.RECORDED:
        return TreasuryTransactionStatus.ENREGISTRE_SANS_JUSTIFICATIF
    return status


def serialize_treasury_transaction(transaction: TreasuryTransaction, farmer_name: str | None = None) -> TreasuryTransactionRead:
    normalized_status = _public_treasury_status(transaction.status)
    is_locked = normalized_status == TreasuryTransactionStatus.ENREGISTRE_COMPLET
    linked_farmer_advance = transaction.farmer_advance if transaction.source_type == FARMER_ADVANCE_SOURCE else None
    has_linked_advance_devis = linked_farmer_advance is not None and linked_farmer_advance.devis_file_id is not None
    has_generated_ref = bool((transaction.receipt_reference or "").strip()) or (
        transaction.type == TreasuryTransactionType.INCOME
        and transaction.source_type in {"commercial_invoice", "commercial_order", "commercial_payment"}
        and transaction.source_id is not None
    )
    if transaction.justificatif_file_id is not None:
        justificatif_status = "justificatif_uploadé"
    elif has_linked_advance_devis:
        justificatif_status = "devis_avance_uploadé"
    elif has_generated_ref:
        justificatif_status = "référence_générée"
    else:
        justificatif_status = "manquant"
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
        receipt_reference=transaction.receipt_reference,
        status=normalized_status.value,
        is_locked=is_locked,
        justificatif_status=justificatif_status,
        justificatif_file=transaction.justificatif_file,
        source_type=transaction.source_type,
        source_id=transaction.source_id,
        linked_farmer_advance_id=linked_farmer_advance.id if linked_farmer_advance is not None else None,
        linked_advance_devis_file=linked_farmer_advance.devis_file if linked_farmer_advance is not None else None,
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
        status=TreasuryTransactionStatus.ENREGISTRE_SANS_JUSTIFICATIF,
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
    if transaction.status != TreasuryTransactionStatus.ENREGISTRE_COMPLET:
        transaction.status = TreasuryTransactionStatus.ENREGISTRE_SANS_JUSTIFICATIF
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


def _has_completion_evidence(transaction: TreasuryTransaction) -> bool:
    if transaction.justificatif_file_id is not None:
        return True
    if transaction.source_type == FARMER_ADVANCE_SOURCE and transaction.farmer_advance is not None:
        return transaction.farmer_advance.devis_file_id is not None
    if transaction.receipt_reference and transaction.receipt_reference.strip():
        return True
    if (
        transaction.type == TreasuryTransactionType.INCOME
        and transaction.source_type in {"commercial_invoice", "commercial_order", "commercial_payment"}
        and transaction.source_id is not None
    ):
        return True
    return False


def _apply_status_transition(transaction: TreasuryTransaction, next_status: TreasuryTransactionStatus):
    if transaction.status == TreasuryTransactionStatus.ENREGISTRE_COMPLET and next_status != TreasuryTransactionStatus.ENREGISTRE_COMPLET:
        raise ValidationError("Transaction verrouillée: impossible de modifier un enregistrement complet.")
    if next_status == TreasuryTransactionStatus.ENREGISTRE_COMPLET and not _has_completion_evidence(transaction):
        raise ValidationError("Enregistré complet exige un justificatif uploadé ou une référence externe générée.")
    if transaction.status == TreasuryTransactionStatus.CANCELLED and next_status != TreasuryTransactionStatus.CANCELLED:
        raise ValidationError("Impossible de réactiver une transaction annulée.")
    transaction.status = next_status


def list_treasury_transactions(
    db: Session,
    manager: User,
    transaction_type: str | None = None,
    source_type: str | None = None,
    search: str | None = None,
    sort_order: str = "desc",
):
    cooperative_id = get_manager_cooperative_id(manager)
    _normalize_legacy_treasury_status_rows(db, cooperative_id)
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
        receipt_reference=payload.receipt_reference.strip() if payload.receipt_reference else None,
        status=TreasuryTransactionStatus.NON_ENREGISTRE,
        source_type=source_type,
        source_id=None,
        farmer_id=farmer.id if farmer else None,
    )
    db.add(transaction)
    if payload.status:
        parsed_status = parse_enum_value(TreasuryTransactionStatus, payload.status.lower(), "treasury status")
        _apply_status_transition(transaction, parsed_status)
    db.commit()
    db.refresh(transaction)
    return serialize_treasury_transaction(transaction)


def update_treasury_transaction(db: Session, manager: User, transaction_id, payload) -> TreasuryTransactionRead:
    cooperative_id = get_manager_cooperative_id(manager)
    transaction = _require_treasury_transaction(db, manager, transaction_id)
    if transaction.status == TreasuryTransactionStatus.ENREGISTRE_COMPLET:
        raise ValidationError("Transaction verrouillée: enregistrement complet non modifiable.")
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
    if "receipt_reference" in data:
        transaction.receipt_reference = data["receipt_reference"].strip() if data["receipt_reference"] else None
    if "source_type" in data and data["source_type"] is not None:
        normalized_source = _normalize_source_type(data["source_type"])
        if normalized_source == FARMER_ADVANCE_SOURCE:
            raise ValidationError("Le type de source farmer_advance est réservé aux avances producteurs.")
        transaction.source_type = normalized_source
    if "farmer_id" in data:
        farmer = _require_member_in_scope(db, cooperative_id, data["farmer_id"])
        transaction.farmer_id = farmer.id if farmer else None
    if "status" in data and data["status"] is not None:
        parsed_status = parse_enum_value(TreasuryTransactionStatus, data["status"].lower(), "treasury status")
        _apply_status_transition(transaction, parsed_status)

    db.commit()
    db.refresh(transaction)
    return serialize_treasury_transaction(transaction)


def cancel_treasury_transaction(db: Session, manager: User, transaction_id) -> TreasuryTransactionRead:
    transaction = _require_treasury_transaction(db, manager, transaction_id)
    if transaction.status == TreasuryTransactionStatus.ENREGISTRE_COMPLET:
        raise ValidationError("Transaction verrouillée: enregistrement complet non annulable.")
    if transaction.source_type == FARMER_ADVANCE_SOURCE:
        raise ValidationError("Annulez l'avance producteur liée depuis la page Avances Producteurs.")
    transaction.status = TreasuryTransactionStatus.CANCELLED
    db.commit()
    db.refresh(transaction)
    return serialize_treasury_transaction(transaction)


def get_treasury_stats(db: Session, manager: User) -> TreasuryStatsRead:
    cooperative_id = get_manager_cooperative_id(manager)
    _normalize_legacy_treasury_status_rows(db, cooperative_id)
    active_statuses = [
        TreasuryTransactionStatus.NON_ENREGISTRE,
        TreasuryTransactionStatus.ENREGISTRE_SANS_JUSTIFICATIF,
        TreasuryTransactionStatus.ENREGISTRE_COMPLET,
        TreasuryTransactionStatus.RECORDED,
    ]

    total_given = db.scalar(
        select(func.coalesce(func.sum(TreasuryTransaction.amount_fcfa), 0.0)).where(
            TreasuryTransaction.cooperative_id == cooperative_id,
            TreasuryTransaction.status.in_(active_statuses),
            TreasuryTransaction.type == TreasuryTransactionType.EXPENSE,
            TreasuryTransaction.source_type == FARMER_ADVANCE_SOURCE,
        )
    )
    total_expenses = db.scalar(
        select(func.coalesce(func.sum(TreasuryTransaction.amount_fcfa), 0.0)).where(
            TreasuryTransaction.cooperative_id == cooperative_id,
            TreasuryTransaction.status.in_(active_statuses),
            TreasuryTransaction.type == TreasuryTransactionType.EXPENSE,
        )
    )
    total_income = db.scalar(
        select(func.coalesce(func.sum(TreasuryTransaction.amount_fcfa), 0.0)).where(
            TreasuryTransaction.cooperative_id == cooperative_id,
            TreasuryTransaction.status.in_(active_statuses),
            TreasuryTransaction.type == TreasuryTransactionType.INCOME,
        )
    )
    return TreasuryStatsRead(
        total_given=round_metric(total_given or 0.0),
        total_expenses=round_metric(total_expenses or 0.0),
        total_income=round_metric(total_income or 0.0),
        current_balance=round_metric((total_income or 0.0) - (total_expenses or 0.0)),
    )


def upload_treasury_justificatif(db: Session, manager: User, transaction_id, file) -> TreasuryTransactionRead:
    transaction = _require_treasury_transaction(db, manager, transaction_id)
    if transaction.status == TreasuryTransactionStatus.ENREGISTRE_COMPLET:
        raise ValidationError("Transaction verrouillée: justificatif non modifiable.")
    uploaded = upload_service.save_treasury_justificatif(
        db,
        manager,
        entity_id=transaction.id,
        file=file,
    )
    transaction.justificatif_file_id = uploaded.id
    if transaction.status in {TreasuryTransactionStatus.NON_ENREGISTRE, TreasuryTransactionStatus.ENREGISTRE_SANS_JUSTIFICATIF, TreasuryTransactionStatus.RECORDED}:
        transaction.status = TreasuryTransactionStatus.ENREGISTRE_COMPLET
    db.commit()
    db.refresh(transaction)
    return serialize_treasury_transaction(transaction)
    linked_farmer_advance = transaction.farmer_advance if transaction.source_type == FARMER_ADVANCE_SOURCE else None

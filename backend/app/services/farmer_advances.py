from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.enums import FarmerAdvanceStatus, InputStatus
from app.models.farmer_advance import FarmerAdvance
from app.models.input import Input
from app.models.member import Member
from app.models.user import User
from app.schemas.farmer_advance import (
    FarmerAdvanceFarmerDetailResponse,
    FarmerAdvanceFarmerSummary,
    FarmerAdvanceRead,
    FarmerAdvanceSummaryResponse,
    FarmerAdvanceSummaryRow,
    FarmerAdvanceSummaryStats,
)
from app.services.helpers import get_manager_cooperative_id, round_metric
from app.services import treasury as treasury_service
from app.utils.exceptions import NotFoundError, ValidationError


def _require_farmer_in_scope(db: Session, cooperative_id, farmer_id):
    farmer = db.scalar(select(Member).where(Member.id == farmer_id, Member.cooperative_id == cooperative_id))
    if farmer is None:
        raise NotFoundError("Farmer not found in the current cooperative.")
    return farmer


def _require_advance(db: Session, cooperative_id, advance_id):
    advance = db.scalar(
        select(FarmerAdvance).where(FarmerAdvance.id == advance_id, FarmerAdvance.cooperative_id == cooperative_id)
    )
    if advance is None:
        raise NotFoundError("Farmer advance not found in the current cooperative.")
    return advance


def _compute_cost_per_kg(total_amount: float, total_quantity: float):
    if total_quantity <= 0:
        return None
    return round_metric(total_amount / total_quantity)


def _active_amount_sum():
    return func.coalesce(
        func.sum(
            case(
                (FarmerAdvance.status == FarmerAdvanceStatus.ACTIVE, FarmerAdvance.amount_fcfa),
                else_=0.0,
            )
        ),
        0.0,
    )


def _validated_collecte_subquery(cooperative_id):
    return (
        select(
            Input.member_id.label("farmer_id"),
            func.coalesce(func.sum(Input.quantity), 0.0).label("total_collected_quantity"),
        )
        .where(Input.cooperative_id == cooperative_id, Input.status == InputStatus.VALIDATED)
        .group_by(Input.member_id)
        .subquery()
    )


def create_farmer_advance(db: Session, manager: User, payload) -> FarmerAdvanceRead:
    cooperative_id = get_manager_cooperative_id(manager)
    farmer = _require_farmer_in_scope(db, cooperative_id, payload.farmer_id)

    advance = FarmerAdvance(
        cooperative_id=cooperative_id,
        farmer_id=farmer.id,
        amount_fcfa=round_metric(payload.amount_fcfa),
        reason=payload.reason.strip(),
        advance_date=payload.advance_date,
        note=payload.note.strip() if payload.note else None,
        status=FarmerAdvanceStatus.ACTIVE,
    )
    db.add(advance)
    db.flush()

    linked_transaction = treasury_service.create_linked_farmer_advance_transaction(
        db=db,
        cooperative_id=cooperative_id,
        farmer=farmer,
        amount_fcfa=advance.amount_fcfa,
        transaction_date=advance.advance_date,
        reason=advance.reason,
        note=advance.note,
        source_id=advance.id,
    )
    advance.treasury_transaction_id = linked_transaction.id

    db.commit()
    db.refresh(advance)
    return FarmerAdvanceRead.model_validate(advance)


def update_farmer_advance(db: Session, manager: User, advance_id, payload) -> FarmerAdvanceRead:
    cooperative_id = get_manager_cooperative_id(manager)
    advance = _require_advance(db, cooperative_id, advance_id)
    if advance.status == FarmerAdvanceStatus.CANCELLED:
        raise ValidationError("Impossible de modifier une avance annulée.")

    data = payload.model_dump(exclude_unset=True)
    farmer = _require_farmer_in_scope(db, cooperative_id, data["farmer_id"]) if "farmer_id" in data else _require_farmer_in_scope(db, cooperative_id, advance.farmer_id)

    if "farmer_id" in data and data["farmer_id"] is not None:
        advance.farmer_id = farmer.id
    if "amount_fcfa" in data and data["amount_fcfa"] is not None:
        advance.amount_fcfa = round_metric(data["amount_fcfa"])
    if "reason" in data and data["reason"] is not None:
        advance.reason = data["reason"].strip()
    if "advance_date" in data and data["advance_date"] is not None:
        advance.advance_date = data["advance_date"]
    if "note" in data:
        advance.note = data["note"].strip() if data["note"] else None

    if advance.treasury_transaction_id is None:
        linked_transaction = treasury_service.create_linked_farmer_advance_transaction(
            db=db,
            cooperative_id=cooperative_id,
            farmer=farmer,
            amount_fcfa=advance.amount_fcfa,
            transaction_date=advance.advance_date,
            reason=advance.reason,
            note=advance.note,
            source_id=advance.id,
        )
        advance.treasury_transaction_id = linked_transaction.id
    else:
        if advance.treasury_transaction is None:
            raise NotFoundError("Linked treasury transaction not found for this advance.")
        treasury_service.sync_linked_farmer_advance_transaction(
            transaction=advance.treasury_transaction,
            farmer=farmer,
            amount_fcfa=advance.amount_fcfa,
            transaction_date=advance.advance_date,
            reason=advance.reason,
            note=advance.note,
        )

    db.commit()
    db.refresh(advance)
    return FarmerAdvanceRead.model_validate(advance)


def cancel_farmer_advance(db: Session, manager: User, advance_id) -> FarmerAdvanceRead:
    cooperative_id = get_manager_cooperative_id(manager)
    advance = _require_advance(db, cooperative_id, advance_id)
    advance.status = FarmerAdvanceStatus.CANCELLED
    if advance.treasury_transaction is not None:
        treasury_service.cancel_linked_farmer_advance_transaction(advance.treasury_transaction)
    db.commit()
    db.refresh(advance)
    return FarmerAdvanceRead.model_validate(advance)


def list_farmer_advances_summary(
    db: Session,
    manager: User,
    search: str | None = None,
    sort_by: str = "last_modified",
    order: str = "desc",
) -> FarmerAdvanceSummaryResponse:
    cooperative_id = get_manager_cooperative_id(manager)
    active_amount_given = _active_amount_sum()

    advances_subquery = (
        select(
            FarmerAdvance.farmer_id.label("farmer_id"),
            active_amount_given.label("total_amount_given"),
            func.count(FarmerAdvance.id).label("number_of_advances"),
            func.max(FarmerAdvance.updated_at).label("last_modified"),
        )
        .where(FarmerAdvance.cooperative_id == cooperative_id)
        .group_by(FarmerAdvance.farmer_id)
        .subquery()
    )
    collecte_subquery = _validated_collecte_subquery(cooperative_id)

    stmt = (
        select(
            Member.id.label("farmer_id"),
            Member.full_name.label("farmer_name"),
            func.coalesce(collecte_subquery.c.total_collected_quantity, 0.0).label("total_collected_quantity"),
            advances_subquery.c.total_amount_given,
            advances_subquery.c.last_modified,
            advances_subquery.c.number_of_advances,
        )
        .join(advances_subquery, advances_subquery.c.farmer_id == Member.id)
        .outerjoin(collecte_subquery, collecte_subquery.c.farmer_id == Member.id)
        .where(Member.cooperative_id == cooperative_id)
    )

    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(func.lower(Member.full_name).like(needle))

    sort_field = (sort_by or "last_modified").strip().lower()
    sort_desc = (order or "desc").strip().lower() != "asc"
    if sort_field == "total_amount":
        sort_column = advances_subquery.c.total_amount_given
    else:
        sort_column = advances_subquery.c.last_modified

    if sort_desc:
        stmt = stmt.order_by(sort_column.desc(), Member.full_name.asc())
    else:
        stmt = stmt.order_by(sort_column.asc(), Member.full_name.asc())

    rows = db.execute(stmt).all()
    items = []
    for row in rows:
        total_collected_quantity = round_metric(row.total_collected_quantity or 0.0)
        total_amount_given = round_metric(row.total_amount_given or 0.0)
        items.append(
            FarmerAdvanceSummaryRow(
                farmer_id=row.farmer_id,
                farmer_name=row.farmer_name,
                total_collected_quantity=total_collected_quantity,
                total_amount_given=total_amount_given,
                cost_per_kg=_compute_cost_per_kg(total_amount_given, total_collected_quantity),
                last_modified=row.last_modified,
                number_of_advances=int(row.number_of_advances or 0),
            )
        )

    total_advanced = round_metric(sum(item.total_amount_given for item in items))
    total_advances_count = sum(item.number_of_advances for item in items)
    affected_rows = [item for item in items if item.total_amount_given > 0]
    affected_farmers_count = len(affected_rows)
    affected_collected_qty = round_metric(sum(item.total_collected_quantity for item in affected_rows))
    average_cost_per_kg = _compute_cost_per_kg(total_advanced, affected_collected_qty)

    return FarmerAdvanceSummaryResponse(
        items=items,
        stats=FarmerAdvanceSummaryStats(
            total_advanced=total_advanced,
            total_advances_count=total_advances_count,
            affected_farmers_count=affected_farmers_count,
            average_cost_per_kg=average_cost_per_kg,
        ),
    )


def get_farmer_advances_detail(db: Session, manager: User, farmer_id) -> FarmerAdvanceFarmerDetailResponse:
    cooperative_id = get_manager_cooperative_id(manager)
    farmer = _require_farmer_in_scope(db, cooperative_id, farmer_id)

    advances = db.scalars(
        select(FarmerAdvance)
        .where(FarmerAdvance.cooperative_id == cooperative_id, FarmerAdvance.farmer_id == farmer.id)
        .order_by(FarmerAdvance.advance_date.desc(), FarmerAdvance.created_at.desc())
    ).all()

    total_collected_quantity = db.scalar(
        select(func.coalesce(func.sum(Input.quantity), 0.0)).where(
            Input.cooperative_id == cooperative_id,
            Input.member_id == farmer.id,
            Input.status == InputStatus.VALIDATED,
        )
    ) or 0.0
    total_collected_quantity = round_metric(total_collected_quantity)

    total_amount_given = round_metric(
        sum(item.amount_fcfa for item in advances if item.status == FarmerAdvanceStatus.ACTIVE)
    )
    last_modified = max((item.updated_at for item in advances), default=farmer.updated_at)

    return FarmerAdvanceFarmerDetailResponse(
        summary=FarmerAdvanceFarmerSummary(
            farmer_id=farmer.id,
            farmer_name=farmer.full_name,
            total_collected_quantity=total_collected_quantity,
            total_amount_given=total_amount_given,
            cost_per_kg=_compute_cost_per_kg(total_amount_given, total_collected_quantity),
            last_modified=last_modified,
            number_of_advances=len(advances),
        ),
        advances=[FarmerAdvanceRead.model_validate(item) for item in advances],
    )

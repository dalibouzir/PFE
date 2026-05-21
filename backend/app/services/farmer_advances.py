from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.batch import Batch
from app.models.enums import FarmerAdvanceStatus, InputStatus, TreasuryTransactionStatus
from app.models.farmer_advance import FarmerAdvance
from app.models.global_charge import GlobalCharge
from app.models.input import Input
from app.models.member import Member
from app.models.parcel import Parcel
from app.models.product import Product
from app.models.stock_movement import StockMovement
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
from app.services import uploads as upload_service
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


def _require_batch_in_scope(db: Session, cooperative_id, batch_id):
    batch = db.scalar(select(Batch).where(Batch.id == batch_id, Batch.cooperative_id == cooperative_id))
    if batch is None:
        raise NotFoundError("Lot non trouvé dans la coopérative courante.")
    return batch


def _require_parcel_in_scope(db: Session, cooperative_id, parcel_id):
    parcel = db.scalar(select(Parcel).where(Parcel.id == parcel_id, Parcel.cooperative_id == cooperative_id))
    if parcel is None:
        raise NotFoundError("Parcelle non trouvée dans la coopérative courante.")
    return parcel


def _require_product_in_scope(db: Session, cooperative_id, product_id):
    product = db.scalar(select(Product).where(Product.id == product_id, Product.cooperative_id == cooperative_id))
    if product is None:
        raise NotFoundError("Produit non trouvé dans la coopérative courante.")
    return product


def _validate_traceability_links(db: Session, cooperative_id, farmer: Member, *, batch_id, parcel_id, product_id):
    if batch_id is not None:
        batch = _require_batch_in_scope(db, cooperative_id, batch_id)
        if batch.member_id is not None and batch.member_id != farmer.id:
            raise ValidationError("Le lot sélectionné n'appartient pas au producteur choisi.")
        if product_id is not None and batch.product_id != product_id:
            raise ValidationError("Le produit ne correspond pas au lot sélectionné.")
    if parcel_id is not None:
        parcel = _require_parcel_in_scope(db, cooperative_id, parcel_id)
        if parcel.member_id != farmer.id:
            raise ValidationError("La parcelle sélectionnée n'appartient pas au producteur choisi.")
    if product_id is not None:
        _require_product_in_scope(db, cooperative_id, product_id)


def _serialize_advance(db: Session, advance: FarmerAdvance) -> FarmerAdvanceRead:
    batch = None
    if advance.batch_id is not None:
        batch = db.scalar(
            select(Batch).where(Batch.id == advance.batch_id, Batch.cooperative_id == advance.cooperative_id)
        )

    product_id = batch.product_id if batch is not None else advance.product_id
    product_name = None
    if product_id is not None:
        product = db.scalar(
            select(Product).where(Product.id == product_id, Product.cooperative_id == advance.cooperative_id)
        )
        product_name = product.name if product is not None else None
    parcel_name = None
    if advance.parcel_id is not None:
        parcel = db.scalar(
            select(Parcel).where(Parcel.id == advance.parcel_id, Parcel.cooperative_id == advance.cooperative_id)
        )
        parcel_name = parcel.name if parcel is not None else None

    collecte_created = False
    stock_in_created = False
    if batch is not None:
        collecte_created = (
            db.scalar(
                select(Input.id).where(
                    Input.cooperative_id == advance.cooperative_id,
                    Input.batch_id == batch.id,
                    Input.source_type.in_(("lot_linked_collecte", "pre_harvest_confirmed_weight")),
                ).limit(1)
            )
            is not None
        )
        stock_in_created = (
            db.scalar(
                select(StockMovement.id).where(
                    StockMovement.cooperative_id == advance.cooperative_id,
                    StockMovement.batch_id == batch.id,
                    StockMovement.movement_type == "in",
                    StockMovement.source.in_(("lot_linked_collecte", "pre_harvest_confirmed_weight")),
                ).limit(1)
            )
            is not None
        )

    if batch is None or batch.confirmed_weight_kg is None:
        return_status = "En attente de produit"
    elif stock_in_created or collecte_created:
        return_status = "Stock IN créé"
    else:
        return_status = "Produit reçu"

    linked_treasury_transaction = None
    if advance.treasury_transaction is not None:
        linked_treasury_transaction = treasury_service.serialize_treasury_transaction(advance.treasury_transaction)

    return FarmerAdvanceRead(
        id=advance.id,
        cooperative_id=advance.cooperative_id,
        farmer_id=advance.farmer_id,
        batch_id=advance.batch_id,
        parcel_id=advance.parcel_id,
        product_id=advance.product_id,
        amount_fcfa=advance.amount_fcfa,
        reason=advance.reason,
        advance_date=advance.advance_date,
        note=advance.note,
        status=advance.status.value,
        source_type=advance.source_type,
        treasury_transaction_id=advance.treasury_transaction_id,
        linked_treasury_transaction=linked_treasury_transaction,
        batch_code=batch.code if batch is not None else None,
        parcel_name=parcel_name,
        product_name=product_name,
        confirmed_weight_kg=batch.confirmed_weight_kg if batch is not None else None,
        preharvest_completed_at=batch.preharvest_completed_at if batch is not None else None,
        collecte_created=collecte_created,
        stock_in_created=stock_in_created,
        return_status=return_status,
        devis_file=advance.devis_file,
        created_at=advance.created_at,
        updated_at=advance.updated_at,
    )


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


def _charges_total_subquery(cooperative_id):
    return (
        select(
            GlobalCharge.member_id.label("farmer_id"),
            func.coalesce(func.sum(GlobalCharge.amount_fcfa), 0.0).label("charges_total"),
            func.max(GlobalCharge.updated_at).label("charges_last_modified"),
        )
        .where(GlobalCharge.cooperative_id == cooperative_id)
        .group_by(GlobalCharge.member_id)
        .subquery()
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
    _validate_traceability_links(
        db,
        cooperative_id,
        farmer,
        batch_id=payload.batch_id,
        parcel_id=payload.parcel_id,
        product_id=payload.product_id,
    )

    advance = FarmerAdvance(
        cooperative_id=cooperative_id,
        farmer_id=farmer.id,
        batch_id=payload.batch_id,
        parcel_id=payload.parcel_id,
        product_id=payload.product_id,
        source_type=(payload.source_type or "manual").strip(),
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
    return _serialize_advance(db, advance)


def update_farmer_advance(db: Session, manager: User, advance_id, payload) -> FarmerAdvanceRead:
    cooperative_id = get_manager_cooperative_id(manager)
    advance = _require_advance(db, cooperative_id, advance_id)
    if advance.status == FarmerAdvanceStatus.CANCELLED:
        raise ValidationError("Impossible de modifier une avance annulée.")

    data = payload.model_dump(exclude_unset=True)
    farmer = _require_farmer_in_scope(db, cooperative_id, data["farmer_id"]) if "farmer_id" in data else _require_farmer_in_scope(db, cooperative_id, advance.farmer_id)
    next_batch_id = data["batch_id"] if "batch_id" in data else advance.batch_id
    next_parcel_id = data["parcel_id"] if "parcel_id" in data else advance.parcel_id
    next_product_id = data["product_id"] if "product_id" in data else advance.product_id
    _validate_traceability_links(
        db,
        cooperative_id,
        farmer,
        batch_id=next_batch_id,
        parcel_id=next_parcel_id,
        product_id=next_product_id,
    )

    if "farmer_id" in data and data["farmer_id"] is not None:
        advance.farmer_id = farmer.id
    if "batch_id" in data:
        advance.batch_id = data["batch_id"]
    if "parcel_id" in data:
        advance.parcel_id = data["parcel_id"]
    if "product_id" in data:
        advance.product_id = data["product_id"]
    if "source_type" in data and data["source_type"] is not None:
        advance.source_type = data["source_type"].strip() or "manual"
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
    return _serialize_advance(db, advance)


def upload_farmer_advance_devis(db: Session, manager: User, advance_id, file) -> FarmerAdvanceRead:
    cooperative_id = get_manager_cooperative_id(manager)
    advance = _require_advance(db, cooperative_id, advance_id)
    uploaded = upload_service.save_farmer_advance_devis(
        db,
        manager,
        entity_id=advance.id,
        file=file,
    )
    advance.devis_file_id = uploaded.id
    if advance.treasury_transaction is not None and advance.treasury_transaction.status in {
        TreasuryTransactionStatus.NON_ENREGISTRE,
        TreasuryTransactionStatus.ENREGISTRE_SANS_JUSTIFICATIF,
        TreasuryTransactionStatus.RECORDED,
    }:
        advance.treasury_transaction.status = TreasuryTransactionStatus.ENREGISTRE_COMPLET
    db.commit()
    db.refresh(advance)
    return _serialize_advance(db, advance)


def cancel_farmer_advance(db: Session, manager: User, advance_id) -> FarmerAdvanceRead:
    cooperative_id = get_manager_cooperative_id(manager)
    advance = _require_advance(db, cooperative_id, advance_id)
    advance.status = FarmerAdvanceStatus.CANCELLED
    if advance.treasury_transaction is not None:
        treasury_service.cancel_linked_farmer_advance_transaction(advance.treasury_transaction)
    db.commit()
    db.refresh(advance)
    return _serialize_advance(db, advance)


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
    charges_subquery = _charges_total_subquery(cooperative_id)

    stmt = (
        select(
            Member.id.label("farmer_id"),
            Member.full_name.label("farmer_name"),
            func.coalesce(collecte_subquery.c.total_collected_quantity, 0.0).label("total_collected_quantity"),
            func.coalesce(advances_subquery.c.total_amount_given, 0.0).label("advances_total"),
            func.coalesce(charges_subquery.c.charges_total, 0.0).label("charges_total"),
            advances_subquery.c.last_modified.label("advances_last_modified"),
            charges_subquery.c.charges_last_modified.label("charges_last_modified"),
            func.coalesce(advances_subquery.c.number_of_advances, 0).label("number_of_advances"),
        )
        .outerjoin(advances_subquery, advances_subquery.c.farmer_id == Member.id)
        .outerjoin(collecte_subquery, collecte_subquery.c.farmer_id == Member.id)
        .outerjoin(charges_subquery, charges_subquery.c.farmer_id == Member.id)
        .where(
            Member.cooperative_id == cooperative_id,
            (advances_subquery.c.farmer_id.is_not(None) | charges_subquery.c.farmer_id.is_not(None)),
        )
    )

    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(func.lower(Member.full_name).like(needle))

    sort_field = (sort_by or "last_modified").strip().lower()
    sort_desc = (order or "desc").strip().lower() != "asc"
    if sort_field == "total_amount":
        sort_column = (
            func.coalesce(advances_subquery.c.total_amount_given, 0.0)
            + func.coalesce(charges_subquery.c.charges_total, 0.0)
        )
    else:
        sort_column = func.coalesce(advances_subquery.c.last_modified, charges_subquery.c.charges_last_modified)

    if sort_desc:
        stmt = stmt.order_by(sort_column.desc(), Member.full_name.asc())
    else:
        stmt = stmt.order_by(sort_column.asc(), Member.full_name.asc())

    rows = db.execute(stmt).all()
    items = []
    for row in rows:
        total_collected_quantity = round_metric(row.total_collected_quantity or 0.0)
        total_amount_given = round_metric((row.advances_total or 0.0) + (row.charges_total or 0.0))
        last_modified = row.advances_last_modified or row.charges_last_modified
        if row.advances_last_modified and row.charges_last_modified:
            last_modified = max(row.advances_last_modified, row.charges_last_modified)
        items.append(
            FarmerAdvanceSummaryRow(
                farmer_id=row.farmer_id,
                farmer_name=row.farmer_name,
                total_collected_quantity=total_collected_quantity,
                total_amount_given=total_amount_given,
                cost_per_kg=_compute_cost_per_kg(total_amount_given, total_collected_quantity),
                last_modified=last_modified,
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
    total_amount_given = round_metric(
        total_amount_given
        + (
            db.scalar(
                select(func.coalesce(func.sum(GlobalCharge.amount_fcfa), 0.0)).where(
                    GlobalCharge.cooperative_id == cooperative_id,
                    GlobalCharge.member_id == farmer.id,
                )
            )
            or 0.0
        )
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
        advances=[_serialize_advance(db, item) for item in advances],
    )

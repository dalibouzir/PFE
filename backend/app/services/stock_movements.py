from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.batch import Batch
from app.models.cooperative import Cooperative
from app.models.input import Input
from app.models.member import Member
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.schemas.stock_movement import StockMovementDetailRead, StockMovementRead
from app.services.helpers import get_manager_cooperative_id, round_metric
from app.utils.exceptions import NotFoundError


def _source_label(row: StockMovement) -> str:
    source = (row.source or "").strip().lower()
    movement_type = (row.movement_type or "").strip().lower()
    action_type = (row.action_type or "").strip().lower()
    if source == "lot_linked_collecte":
        return "Collecte liée au lot"
    if source in {"manual", "independent_collecte", "collecte_independante"}:
        return "Collecte indépendante"
    if source == "post_harvest_step":
        if any(token in action_type for token in ("perte", "loss", "rejet", "reject", "casse", "avarie")):
            return "Perte Post-récolte"
        if movement_type == "out":
            return "Sortie Post-récolte"
    return row.source


def _traceability_status(row: StockMovement, batch: Batch | None) -> str:
    source = (row.source or "").strip().lower()
    hints_lot_context = source in {
        "post_harvest_step",
        "lot_linked_collecte",
        "pre_harvest_confirmed_weight",
    }
    if row.batch_id is None:
        return "legacy_unlinked" if hints_lot_context else "missing_lot"
    if batch is None:
        return "unresolved_lot"
    return "linked_lot"


def _movement_reference(row: StockMovement, batch: Batch | None, input_row: Input | None) -> str:
    if input_row is not None:
        return f"COL-{str(input_row.id)[:8].upper()}"
    if batch is not None:
        return batch.code
    return f"MVT-{str(row.id)[:8].upper()}"


def _input_reference(input_row: Input | None) -> Optional[str]:
    if input_row is None:
        return None
    return f"COL-{str(input_row.id)[:8].upper()}"


def _extract_manager_name(notes: Optional[str]) -> Optional[str]:
    text = (notes or "").strip()
    if not text:
        return None
    marker = "| manager:"
    idx = text.lower().rfind(marker)
    if idx < 0:
        return None
    extracted = text[idx + len(marker) :].strip()
    return extracted or None


def _display_user_name(user: User | None) -> Optional[str]:
    if user is None:
        return None
    full_name = (user.full_name or "").strip()
    email = (user.email or "").strip()
    return full_name or email or None


def _serialize(
    row: StockMovement,
    cooperative: Cooperative | None,
    product: Product | None,
    batch: Batch | None,
    input_row: Input | None,
    member: Member | None,
    batch_owner: User | None = None,
) -> StockMovementRead:
    member_name = member.full_name if member is not None else None
    source = (row.source or "").strip().lower()
    if member_name is None and source == "commercial_catalog":
        member_name = _extract_manager_name(row.notes)
    if member_name is None and source == "post_harvest_step":
        member_name = _display_user_name(batch_owner)

    return StockMovementRead(
        id=row.id,
        cooperative_id=row.cooperative_id,
        cooperative_name=cooperative.name if cooperative is not None else None,
        movement_reference=_movement_reference(row, batch, input_row),
        movement_type=row.movement_type,
        action_type=row.action_type,
        source=row.source,
        source_label=_source_label(row),
        traceability_status=_traceability_status(row, batch),
        product_id=row.product_id,
        product_name=product.name if product is not None else None,
        batch_id=row.batch_id,
        batch_reference=batch.code if batch is not None else None,
        input_id=row.input_id,
        input_reference=_input_reference(input_row),
        input_reference_bl=(input_row.bl_number if input_row is not None else None),
        member_id=member.id if member is not None else None,
        member_name=member_name,
        process_step_id=row.process_step_id,
        workflow_step_id=row.workflow_step_id,
        quantity_kg=round_metric(row.quantity_kg),
        movement_date=row.movement_date,
        notes=row.notes,
        idempotency_key=row.idempotency_key,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_stock_movements(
    db: Session,
    manager: User,
    *,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    product_id: Optional[UUID] = None,
    movement_type: Optional[str] = None,
    source: Optional[str] = None,
    batch_reference: Optional[str] = None,
    input_reference: Optional[str] = None,
    member_id: Optional[UUID] = None,
    search: Optional[str] = None,
    sort: str = "desc",
) -> list[StockMovementRead]:
    cooperative_id = get_manager_cooperative_id(manager)
    stmt = select(StockMovement).where(StockMovement.cooperative_id == cooperative_id)

    if date_from is not None:
        stmt = stmt.where(StockMovement.movement_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(StockMovement.movement_date <= date_to)
    if product_id is not None:
        stmt = stmt.where(StockMovement.product_id == product_id)
    if movement_type:
        stmt = stmt.where(StockMovement.movement_type == movement_type.strip().lower())
    if source:
        stmt = stmt.where(StockMovement.source == source.strip())
    if member_id is not None:
        member_input_ids = db.scalars(
            select(Input.id).where(
                Input.cooperative_id == cooperative_id,
                Input.member_id == member_id,
            )
        ).all()
        if not member_input_ids:
            return []
        stmt = stmt.where(StockMovement.input_id.in_(member_input_ids))

    is_asc = sort.lower() == "asc"
    if is_asc:
        stmt = stmt.order_by(StockMovement.movement_date.asc(), StockMovement.created_at.asc())
    else:
        stmt = stmt.order_by(StockMovement.movement_date.desc(), StockMovement.created_at.desc())

    rows = db.scalars(stmt).all()
    if not rows:
        return []

    batch_ids = {row.batch_id for row in rows if row.batch_id is not None}
    input_ids = {row.input_id for row in rows if row.input_id is not None}
    product_ids = {row.product_id for row in rows}

    batches = {
        item.id: item
        for item in db.scalars(
            select(Batch).where(Batch.cooperative_id == cooperative_id, Batch.id.in_(batch_ids))
        ).all()
    } if batch_ids else {}

    inputs = {
        item.id: item
        for item in db.scalars(
            select(Input).where(Input.cooperative_id == cooperative_id, Input.id.in_(input_ids))
        ).all()
    } if input_ids else {}

    products = {
        item.id: item
        for item in db.scalars(
            select(Product).where(Product.cooperative_id == cooperative_id, Product.id.in_(product_ids))
        ).all()
    }

    member_ids = {input_row.member_id for input_row in inputs.values()}
    members = {
        item.id: item
        for item in db.scalars(
            select(Member).where(Member.cooperative_id == cooperative_id, Member.id.in_(member_ids))
        ).all()
    } if member_ids else {}
    batch_owner_ids = {batch.created_by_user_id for batch in batches.values() if batch is not None}
    batch_owners = {
        item.id: item
        for item in db.scalars(
            select(User).where(User.id.in_(batch_owner_ids))
        ).all()
    } if batch_owner_ids else {}

    cooperative = db.scalar(select(Cooperative).where(Cooperative.id == cooperative_id))

    needle = search.strip().lower() if search and search.strip() else None
    batch_ref_needle = batch_reference.strip().lower() if batch_reference and batch_reference.strip() else None
    input_ref_needle = input_reference.strip().lower() if input_reference and input_reference.strip() else None

    result: list[StockMovementRead] = []
    for row in rows:
        input_row = inputs.get(row.input_id) if row.input_id is not None else None
        member = members.get(input_row.member_id) if input_row is not None else None
        batch = batches.get(row.batch_id) if row.batch_id is not None else None
        batch_owner = batch_owners.get(batch.created_by_user_id) if batch is not None else None
        product = products.get(row.product_id)

        serialized = _serialize(row, cooperative, product, batch, input_row, member, batch_owner)

        if batch_ref_needle and not ((serialized.batch_reference or "").lower().find(batch_ref_needle) >= 0):
            continue
        if input_ref_needle and not ((serialized.input_reference or "").lower().find(input_ref_needle) >= 0):
            continue

        if needle:
            searchable = [
                serialized.movement_reference,
                serialized.action_type,
                serialized.source,
                serialized.batch_reference or "",
                serialized.input_reference or "",
                serialized.input_reference_bl or "",
                serialized.member_name or "",
                serialized.product_name or "",
                serialized.notes or "",
                serialized.idempotency_key,
            ]
            haystack = " ".join(searchable).lower()
            if needle not in haystack:
                continue

        result.append(serialized)

    return result


def get_stock_movement_detail(db: Session, manager: User, movement_id: UUID) -> StockMovementDetailRead:
    cooperative_id = get_manager_cooperative_id(manager)
    row = db.scalar(
        select(StockMovement).where(
            StockMovement.cooperative_id == cooperative_id,
            StockMovement.id == movement_id,
        )
    )
    if row is None:
        raise NotFoundError("Stock movement not found in the current cooperative.")

    cooperative = db.scalar(select(Cooperative).where(Cooperative.id == cooperative_id))
    product = db.scalar(
        select(Product).where(Product.cooperative_id == cooperative_id, Product.id == row.product_id)
    )
    batch = None
    if row.batch_id is not None:
        batch = db.scalar(
            select(Batch).where(Batch.cooperative_id == cooperative_id, Batch.id == row.batch_id)
        )
    input_row = None
    if row.input_id is not None:
        input_row = db.scalar(
            select(Input).where(Input.cooperative_id == cooperative_id, Input.id == row.input_id)
        )
    member = None
    if input_row is not None:
        member = db.scalar(
            select(Member).where(Member.cooperative_id == cooperative_id, Member.id == input_row.member_id)
        )
    batch_owner = None
    if batch is not None:
        batch_owner = db.scalar(select(User).where(User.id == batch.created_by_user_id))

    serialized = _serialize(row, cooperative, product, batch, input_row, member, batch_owner)
    return StockMovementDetailRead(**serialized.model_dump())

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.batch import Batch
from app.models.field import Field
from app.models.input import Input
from app.models.member import Member
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.services.helpers import get_manager_cooperative_id, normalize_mass_unit, normalize_product_code, parse_enum_value, to_kg
from app.services.stocks import apply_total_stock_delta, get_stock_by_product, normalize_stock_grade
from app.models.enums import InputStatus
from app.utils.exceptions import NotFoundError, ValidationError
from app.services.helpers import round_metric
from app.services import uploads as upload_service


def _normalize_member_product_token(value: str) -> str:
    return value.strip().lower()


def _validate_member_product_mapping(member: Member, product: Product):
    allowed_tokens = {
        _normalize_member_product_token(item)
        for item in member.products
        if item and item.strip()
    }
    if not allowed_tokens:
        return
    product_token = _normalize_member_product_token(product.name)
    if product_token not in allowed_tokens:
        raise ValidationError(
            "Selected product is not assigned to this member. Update the member products first."
        )


def _generate_collecte_reference(db: Session, product_name: str, year: int) -> str:
    product_code = normalize_product_code(product_name)
    prefix = f"COL-{product_code}-{year}-"
    rows = db.scalars(select(Input.collecte_reference).where(func.lower(Input.collecte_reference).like(f"{prefix.lower()}%"))).all()
    max_increment = 0
    for ref in rows:
        if not ref:
            continue
        suffix = ref[len(prefix) :]
        if suffix.isdigit():
            max_increment = max(max_increment, int(suffix))
    return f"{prefix}{max_increment + 1:03d}"


def _generate_movement_reference(db: Session, *, movement_kind: str, year: int) -> str:
    token = movement_kind.upper()
    prefix = f"MVT-{token}-{year}-"
    rows = db.scalars(
        select(StockMovement.movement_reference).where(func.lower(StockMovement.movement_reference).like(f"{prefix.lower()}%"))
    ).all()
    max_increment = 0
    for ref in rows:
        if not ref:
            continue
        suffix = ref[len(prefix) :]
        if suffix.isdigit():
            max_increment = max(max_increment, int(suffix))
    return f"{prefix}{max_increment + 1:03d}"


def record_input(db: Session, manager: User, payload) -> Input:
    cooperative_id = get_manager_cooperative_id(manager)
    linked_batch: Batch | None = None
    if payload.batch_id is not None:
        linked_batch = db.scalar(
            select(Batch).where(Batch.id == payload.batch_id, Batch.cooperative_id == cooperative_id)
        )
        if linked_batch is None:
            raise NotFoundError("Lot not found in the current cooperative.")
        if linked_batch.preharvest_completed_at is None:
            raise ValidationError("Ce lot n'est pas prêt pour collecte. Terminez d'abord la pré-récolte.")
        if linked_batch.member_id is None or linked_batch.product_id is None:
            raise ValidationError("Lot incomplet: member/product manquant pour collecte liée.")

        existing_linked_collecte = db.scalar(
            select(Input.id).where(
                Input.cooperative_id == cooperative_id,
                Input.batch_id == linked_batch.id,
                Input.source_type.in_(("lot_linked_collecte", "pre_harvest_confirmed_weight")),
            )
        )
        if existing_linked_collecte is not None:
            raise ValidationError("Une collecte liée existe déjà pour ce lot.")

        if payload.member_id != linked_batch.member_id:
            raise ValidationError("member_id doit correspondre au membre du lot pour une collecte liée.")
        if payload.product_id != linked_batch.product_id:
            raise ValidationError("product_id doit correspondre au produit du lot pour une collecte liée.")

    member = db.scalar(
        select(Member).where(Member.id == payload.member_id, Member.cooperative_id == cooperative_id)
    )
    if member is None:
        raise NotFoundError("Member not found in the current cooperative.")

    product = db.scalar(
        select(Product).where(Product.id == payload.product_id, Product.cooperative_id == cooperative_id)
    )
    if product is None:
        raise NotFoundError("Product not found in the current cooperative.")
    _validate_member_product_mapping(member, product)

    field_id = payload.field_id
    if field_id is not None:
        field = db.scalar(
            select(Field).where(
                Field.id == field_id,
                Field.cooperative_id == cooperative_id,
                Field.member_id == member.id,
            )
        )
        if field is None:
            raise NotFoundError("Field not found for this member in the current cooperative.")

    input_record = Input(
        cooperative_id=cooperative_id,
        member_id=member.id,
        product_id=product.id,
        batch_id=payload.batch_id,
        field_id=field_id,
        date=payload.date,
        quantity=to_kg(payload.quantity, normalize_mass_unit(payload.unit or product.unit)),
        grade=payload.grade.strip(),
        estimated_value=payload.estimated_value,
        bl_number=(payload.bl_number.strip() if payload.bl_number else None),
        collecte_reference=_generate_collecte_reference(db, product.name, payload.date.year),
        status=(
            InputStatus.VALIDATED
            if linked_batch is not None
            else parse_enum_value(InputStatus, payload.status, "input status")
        ),
        source_type=("lot_linked_collecte" if linked_batch is not None else (payload.source_type or "manual").strip()),
    )
    db.add(input_record)
    db.flush()

    if linked_batch is not None:
        movement = StockMovement(
            cooperative_id=cooperative_id,
            product_id=product.id,
            grade=normalize_stock_grade(input_record.grade),
            batch_id=linked_batch.id,
            input_id=input_record.id,
            movement_type="in",
            action_type="collecte",
            source="lot_linked_collecte",
            quantity_kg=round_metric(input_record.quantity),
            movement_date=input_record.date,
            movement_reference=_generate_movement_reference(db, movement_kind="IN", year=input_record.date.year),
            idempotency_key=f"input:{input_record.id}:stock_in",
            notes=f"Collecte liée au lot {linked_batch.code}",
        )
        db.add(movement)
        linked_batch.confirmed_weight_kg = round_metric(input_record.quantity)
        linked_batch.current_qty = round_metric(input_record.quantity)

    apply_total_stock_delta(
        db,
        cooperative_id,
        product,
        input_record.quantity,
        create_if_missing=True,
        grade=input_record.grade,
    )
    db.commit()
    db.refresh(input_record)
    return input_record


def list_inputs(db: Session, manager: User):
    cooperative_id = get_manager_cooperative_id(manager)
    return db.scalars(
        select(Input).where(Input.cooperative_id == cooperative_id).order_by(Input.date.desc(), Input.created_at.desc())
    ).all()


def get_input(db: Session, manager: User, input_id):
    cooperative_id = get_manager_cooperative_id(manager)
    input_record = db.scalar(
        select(Input).where(Input.id == input_id, Input.cooperative_id == cooperative_id)
    )
    if input_record is None:
        raise NotFoundError("Input record not found in the current cooperative.")
    return input_record


def update_input(db: Session, manager: User, input_id, payload) -> Input:
    cooperative_id = get_manager_cooperative_id(manager)
    input_record = get_input(db, manager, input_id)
    data = payload.model_dump(exclude_unset=True)

    member_changed = "member_id" in data
    product_changed = "product_id" in data
    field_changed = "field_id" in data
    quantity_changed = "quantity" in data
    unit_changed = "unit" in data
    touches_structure = member_changed or product_changed or field_changed or quantity_changed or unit_changed

    member = db.scalar(
        select(Member).where(
            Member.id == data.get("member_id", input_record.member_id),
            Member.cooperative_id == cooperative_id,
        )
    )
    if member is None:
        raise NotFoundError("Member not found in the current cooperative.")

    product = db.scalar(
        select(Product).where(
            Product.id == data.get("product_id", input_record.product_id),
            Product.cooperative_id == cooperative_id,
        )
    )
    if product is None:
        raise NotFoundError("Product not found in the current cooperative.")
    # Keep historical records editable (e.g. status/grade/date updates) even when
    # member-product assignments changed after the collection was created.
    if member_changed or product_changed:
        _validate_member_product_mapping(member, product)

    next_field_id = data.get("field_id", input_record.field_id)
    if touches_structure and next_field_id is not None:
        field = db.scalar(
            select(Field).where(
                Field.id == next_field_id,
                Field.cooperative_id == cooperative_id,
                Field.member_id == member.id,
            )
        )
        if field is None:
            raise NotFoundError("Field not found for this member in the current cooperative.")

    old_product = db.scalar(
        select(Product).where(Product.id == input_record.product_id, Product.cooperative_id == cooperative_id)
    )
    if old_product is None:
        raise NotFoundError("Product not found in the current cooperative.")
    old_quantity = float(input_record.quantity)
    old_grade = normalize_stock_grade(input_record.grade)
    new_grade = normalize_stock_grade(data.get("grade", input_record.grade))

    next_quantity = (
        to_kg(data["quantity"], normalize_mass_unit(data.get("unit") or product.unit))
        if "quantity" in data
        else input_record.quantity
    )

    if old_product.id == product.id and old_grade == new_grade:
        delta = float(next_quantity) - old_quantity
        if abs(delta) > 1e-9:
            apply_total_stock_delta(db, cooperative_id, product, delta, create_if_missing=True, grade=new_grade)
    else:
        apply_total_stock_delta(db, cooperative_id, old_product, -old_quantity, create_if_missing=True, grade=old_grade)
        apply_total_stock_delta(db, cooperative_id, product, float(next_quantity), create_if_missing=True, grade=new_grade)

    input_record.member_id = member.id
    input_record.product_id = product.id
    if "batch_id" in data:
        input_record.batch_id = data["batch_id"]
    input_record.field_id = next_field_id

    if "date" in data:
        input_record.date = data["date"]
    input_record.quantity = next_quantity
    if "grade" in data and data["grade"] is not None:
        input_record.grade = data["grade"].strip()
    if "estimated_value" in data:
        input_record.estimated_value = data["estimated_value"]
    if "bl_number" in data:
        input_record.bl_number = data["bl_number"].strip() if data["bl_number"] else None
    if "status" in data and data["status"] is not None:
        input_record.status = parse_enum_value(InputStatus, data["status"], "input status")
    if "source_type" in data and data["source_type"] is not None:
        input_record.source_type = data["source_type"].strip()

    db.commit()
    db.refresh(input_record)
    return input_record


def delete_input(db: Session, manager: User, input_id):
    cooperative_id = get_manager_cooperative_id(manager)
    input_record = get_input(db, manager, input_id)
    product = db.scalar(
        select(Product).where(Product.id == input_record.product_id, Product.cooperative_id == cooperative_id)
    )
    if product is None:
        raise NotFoundError("Product not found in the current cooperative.")

    linked_batch = None
    if input_record.batch_id is not None and input_record.source_type in {"lot_linked_collecte", "pre_harvest_confirmed_weight"}:
        linked_batch = db.scalar(
            select(Batch).where(Batch.id == input_record.batch_id, Batch.cooperative_id == cooperative_id)
        )
        if linked_batch is not None:
            postharvest_started = linked_batch.postharvest_started_at is not None
            postharvest_has_steps = len(linked_batch.process_steps or []) > 0
            if postharvest_started or postharvest_has_steps:
                raise ValidationError(
                    "Impossible de supprimer cette collecte: la Post-récolte du lot est déjà en cours."
                )

    stock = get_stock_by_product(db, cooperative_id, product.id, input_record.grade)
    if stock is not None:
        remaining_total = float(stock.total_stock_kg) - float(input_record.quantity)
        if remaining_total < float(stock.reserved_in_lots_kg):
            raise ValidationError(
                "Impossible de supprimer cette collecte: une partie de ce produit est reservee dans des lots. "
                "Supprimez ou reduisez d'abord les lots lies a ce produit."
            )

    snapshot = {
        "id": input_record.id,
        "cooperative_id": input_record.cooperative_id,
        "member_id": input_record.member_id,
        "product_id": input_record.product_id,
        "field_id": input_record.field_id,
        "batch_id": input_record.batch_id,
        "date": input_record.date,
        "quantity": input_record.quantity,
        "grade": input_record.grade,
        "estimated_value": input_record.estimated_value,
        "collecte_reference": input_record.collecte_reference,
        "status": input_record.status,
        "source_type": input_record.source_type,
        "created_at": input_record.created_at,
        "updated_at": input_record.updated_at,
    }

    apply_total_stock_delta(
        db,
        cooperative_id,
        product,
        -float(input_record.quantity),
        create_if_missing=True,
        grade=input_record.grade,
    )
    if input_record.id is not None:
        movement_rows = db.scalars(
            select(StockMovement).where(
                StockMovement.cooperative_id == cooperative_id,
                StockMovement.input_id == input_record.id,
            )
        ).all()
        for row in movement_rows:
            db.delete(row)
    db.delete(input_record)

    if linked_batch is not None:
        remaining_linked_collecte = db.scalar(
            select(Input.id).where(
                Input.cooperative_id == cooperative_id,
                Input.batch_id == linked_batch.id,
                Input.id != input_record.id,
                Input.source_type.in_(("lot_linked_collecte", "pre_harvest_confirmed_weight")),
            )
        )
        if remaining_linked_collecte is None:
            linked_batch.confirmed_weight_kg = None
            linked_batch.current_qty = 0.0

    db.commit()
    return snapshot


def upload_input_justificatif(db: Session, manager: User, input_id, file) -> Input:
    input_record = get_input(db, manager, input_id)
    uploaded = upload_service.save_collecte_justificatif(
        db=db,
        manager=manager,
        entity_id=input_record.id,
        file=file,
    )
    input_record.justificatif_file_id = uploaded.id
    db.commit()
    db.refresh(input_record)
    return input_record

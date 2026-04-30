from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.field import Field
from app.models.input import Input
from app.models.member import Member
from app.models.product import Product
from app.models.user import User
from app.services.helpers import get_manager_cooperative_id, normalize_mass_unit, parse_enum_value, to_kg
from app.services.stocks import apply_total_stock_delta, get_stock_by_product
from app.models.enums import InputStatus
from app.utils.exceptions import NotFoundError, ValidationError


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


def record_input(db: Session, manager: User, payload) -> Input:
    cooperative_id = get_manager_cooperative_id(manager)
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
        field_id=field_id,
        date=payload.date,
        quantity=to_kg(payload.quantity, normalize_mass_unit(payload.unit or product.unit)),
        grade=payload.grade.strip(),
        estimated_value=payload.estimated_value,
        status=parse_enum_value(InputStatus, payload.status, "input status"),
    )
    db.add(input_record)
    apply_total_stock_delta(db, cooperative_id, product, input_record.quantity, create_if_missing=True)
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
    _validate_member_product_mapping(member, product)

    next_field_id = data.get("field_id", input_record.field_id)
    if next_field_id is not None:
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

    next_quantity = (
        to_kg(data["quantity"], normalize_mass_unit(data.get("unit") or product.unit))
        if "quantity" in data
        else input_record.quantity
    )

    if old_product.id == product.id:
        delta = float(next_quantity) - old_quantity
        if abs(delta) > 1e-9:
            apply_total_stock_delta(db, cooperative_id, product, delta, create_if_missing=True)
    else:
        apply_total_stock_delta(db, cooperative_id, old_product, -old_quantity, create_if_missing=True)
        apply_total_stock_delta(db, cooperative_id, product, float(next_quantity), create_if_missing=True)

    input_record.member_id = member.id
    input_record.product_id = product.id
    input_record.field_id = next_field_id

    if "date" in data:
        input_record.date = data["date"]
    input_record.quantity = next_quantity
    if "grade" in data and data["grade"] is not None:
        input_record.grade = data["grade"].strip()
    if "estimated_value" in data:
        input_record.estimated_value = data["estimated_value"]
    if "status" in data and data["status"] is not None:
        input_record.status = parse_enum_value(InputStatus, data["status"], "input status")

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
    stock = get_stock_by_product(db, cooperative_id, product.id)
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
        "date": input_record.date,
        "quantity": input_record.quantity,
        "grade": input_record.grade,
        "estimated_value": input_record.estimated_value,
        "status": input_record.status,
        "created_at": input_record.created_at,
        "updated_at": input_record.updated_at,
    }
    apply_total_stock_delta(db, cooperative_id, product, -float(input_record.quantity), create_if_missing=True)
    db.delete(input_record)
    db.commit()
    return snapshot

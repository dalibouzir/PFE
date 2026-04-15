from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.field import Field
from app.models.input import Input
from app.models.member import Member
from app.models.product import Product
from app.models.user import User
from app.services.helpers import get_manager_cooperative_id, parse_enum_value
from app.services.stocks import apply_stock_delta
from app.models.enums import InputStatus
from app.utils.exceptions import NotFoundError


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
        quantity=payload.quantity,
        grade=payload.grade.strip(),
        estimated_value=payload.estimated_value,
        status=parse_enum_value(InputStatus, payload.status, "input status"),
    )
    db.add(input_record)
    db.flush()
    apply_stock_delta(db, cooperative_id, product, payload.quantity, create_if_missing=True)
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

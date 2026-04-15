from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.field import Field
from app.models.member import Member
from app.models.user import User
from app.services.helpers import get_manager_cooperative_id
from app.utils.exceptions import NotFoundError


def _require_member_in_scope(db: Session, manager: User, member_id):
    cooperative_id = get_manager_cooperative_id(manager)
    member = db.scalar(
        select(Member).where(Member.id == member_id, Member.cooperative_id == cooperative_id)
    )
    if member is None:
        raise NotFoundError("Member not found in the current cooperative.")
    return member


def create_field(db: Session, manager: User, payload) -> Field:
    member = _require_member_in_scope(db, manager, payload.member_id)
    field = Field(
        member_id=member.id,
        cooperative_id=member.cooperative_id,
        location=payload.location.strip(),
        area=payload.area,
        soil_type=payload.soil_type.strip() if payload.soil_type else None,
        irrigation_type=payload.irrigation_type.strip() if payload.irrigation_type else None,
    )
    db.add(field)
    db.commit()
    db.refresh(field)
    return field


def list_fields(db: Session, manager: User):
    cooperative_id = get_manager_cooperative_id(manager)
    return db.scalars(
        select(Field).where(Field.cooperative_id == cooperative_id).order_by(Field.created_at.desc())
    ).all()


def require_field(db: Session, manager: User, field_id):
    cooperative_id = get_manager_cooperative_id(manager)
    field = db.scalar(select(Field).where(Field.id == field_id, Field.cooperative_id == cooperative_id))
    if field is None:
        raise NotFoundError("Field not found in the current cooperative.")
    return field


def update_field(db: Session, manager: User, field_id, payload) -> Field:
    field = require_field(db, manager, field_id)
    data = payload.model_dump(exclude_unset=True)
    if "member_id" in data and data["member_id"] is not None:
        member = _require_member_in_scope(db, manager, data["member_id"])
        field.member_id = member.id
    if "location" in data:
        field.location = data["location"].strip()
    if "area" in data:
        field.area = data["area"]
    if "soil_type" in data:
        field.soil_type = data["soil_type"].strip() if data["soil_type"] else None
    if "irrigation_type" in data:
        field.irrigation_type = data["irrigation_type"].strip() if data["irrigation_type"] else None
    db.commit()
    db.refresh(field)
    return field

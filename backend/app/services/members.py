import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.member import Member
from app.models.user import User
from app.schemas.member import ContactMemberRequest
from app.services.helpers import get_manager_cooperative_id, parse_enum_value
from app.models.enums import MemberStatus
from app.utils.exceptions import ConflictError


logger = logging.getLogger(__name__)


def create_member(db: Session, manager: User, payload) -> Member:
    cooperative_id = get_manager_cooperative_id(manager)
    existing = db.scalar(
        select(Member).where(Member.cooperative_id == cooperative_id, Member.code == payload.code.strip())
    )
    if existing is not None:
        raise ConflictError("A member with this code already exists in this cooperative.")

    member = Member(
        cooperative_id=cooperative_id,
        code=payload.code.strip(),
        full_name=payload.full_name.strip(),
        phone=payload.phone.strip(),
        specialty=payload.specialty.strip() if payload.specialty else None,
        status=parse_enum_value(MemberStatus, payload.status, "member status"),
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def list_members(db: Session, manager: User):
    cooperative_id = get_manager_cooperative_id(manager)
    return db.scalars(
        select(Member).where(Member.cooperative_id == cooperative_id).order_by(Member.created_at.desc())
    ).all()


def get_member(db: Session, manager: User, member_id):
    cooperative_id = get_manager_cooperative_id(manager)
    return db.scalar(
        select(Member).where(Member.id == member_id, Member.cooperative_id == cooperative_id)
    )


def require_member(db: Session, manager: User, member_id):
    member = get_member(db, manager, member_id)
    if member is None:
        from app.utils.exceptions import NotFoundError

        raise NotFoundError("Member not found in the current cooperative.")
    return member


def update_member(db: Session, manager: User, member_id, payload) -> Member:
    member = require_member(db, manager, member_id)
    data = payload.model_dump(exclude_unset=True)
    if "code" in data:
        duplicate = db.scalar(
            select(Member).where(
                Member.cooperative_id == member.cooperative_id,
                Member.code == data["code"].strip(),
                Member.id != member.id,
            )
        )
        if duplicate is not None:
            raise ConflictError("A member with this code already exists in this cooperative.")
        member.code = data["code"].strip()
    if "full_name" in data:
        member.full_name = data["full_name"].strip()
    if "phone" in data:
        member.phone = data["phone"].strip()
    if "specialty" in data:
        member.specialty = data["specialty"].strip() if data["specialty"] else None
    if "status" in data:
        member.status = parse_enum_value(MemberStatus, data["status"], "member status")
    db.commit()
    db.refresh(member)
    return member


def contact_member(db: Session, manager: User, member_id, payload: ContactMemberRequest):
    member = require_member(db, manager, member_id)
    logger.info(
        "Contact member placeholder: manager_id=%s member_id=%s channel=%s message=%s",
        manager.id,
        member.id,
        payload.channel,
        payload.message,
    )
    return {
        "success": True,
        "member_id": member.id,
        "channel": payload.channel,
        "message": "Contact action logged successfully.",
    }

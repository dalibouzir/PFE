from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.member import Member
from app.models.parcel import Parcel
from app.models.user import User
from app.services.helpers import ensure_user_can_access_cooperative_by_institution_or_global


def _serialize_member(member: Member, parcel_count: int, area_hectares: float) -> dict:
    return {
        "id": member.id,
        "cooperative_id": member.cooperative_id,
        "code": member.code,
        "internal_code": member.code,
        "full_name": member.full_name,
        "phone": member.phone,
        "village": member.village,
        "notes": member.notes,
        "main_product": member.main_product,
        "secondary_products": member.secondary_products,
        "products": member.products,
        "parcel_count": int(parcel_count),
        "area_hectares": float(area_hectares),
        "join_date": member.join_date,
        "specialty": member.specialty,
        "status": member.status.value if hasattr(member.status, "value") else str(member.status),
        "created_at": member.created_at,
        "updated_at": member.updated_at,
    }


def _parcel_aggregates_for_members(db: Session, cooperative_id, member_ids: list):
    if not member_ids:
        return {}
    rows = db.execute(
        select(
            Parcel.member_id,
            func.count(Parcel.id).label("parcel_count"),
            func.coalesce(func.sum(Parcel.surface_ha), 0.0).label("total_surface"),
        )
        .where(Parcel.cooperative_id == cooperative_id, Parcel.member_id.in_(member_ids))
        .group_by(Parcel.member_id)
    ).all()
    return {
        row.member_id: {
            "parcel_count": int(row.parcel_count or 0),
            "total_surface": float(row.total_surface or 0.0),
        }
        for row in rows
    }


def list_members_for_cooperative_insights(db: Session, current_user: User, cooperative_id):
    cooperative = ensure_user_can_access_cooperative_by_institution_or_global(db, current_user, cooperative_id)
    members = db.scalars(
        select(Member).where(Member.cooperative_id == cooperative.id).order_by(Member.created_at.desc())
    ).all()
    aggregates = _parcel_aggregates_for_members(db, cooperative.id, [member.id for member in members])
    return [
        _serialize_member(
            member,
            aggregates.get(member.id, {}).get("parcel_count", 0),
            aggregates.get(member.id, {}).get("total_surface", 0.0),
        )
        for member in members
    ]

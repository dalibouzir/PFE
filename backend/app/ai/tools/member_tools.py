from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.tools.app_data_tools import (
    apply_date_filter,
    canonical_product_name,
    enum_value,
    source,
    tool_response,
    warnings_for_empty,
)
from app.models.input import Input
from app.models.member import Member
from app.models.product import Product
from app.models.user import User


class MemberTools:
    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.current_user = current_user

    def get_members_summary(self) -> dict[str, Any]:
        rows = self.db.execute(
            select(Member.status, func.count(Member.id))
            .where(Member.cooperative_id == self.current_user.cooperative_id)
            .group_by(Member.status)
        ).all()
        data = {
            "total_members": sum(int(count or 0) for _, count in rows),
            "by_status": {enum_value(status): int(count or 0) for status, count in rows},
        }
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="members", label="Membres enregistrés", record_count=data["total_members"])],
            warnings=warnings_for_empty(rows),
        )

    def get_member_detail(self, member_id: str | None = None, member_name: str | None = None) -> dict[str, Any]:
        stmt = select(Member).where(Member.cooperative_id == self.current_user.cooperative_id)
        if member_id:
            try:
                stmt = stmt.where(Member.id == UUID(str(member_id)))
            except ValueError:
                return tool_response(
                    ok=True,
                    data=None,
                    sources=[source(table="members", label="Membre recherché", record_count=0)],
                    warnings=["L’identifiant du membre est invalide."],
                )
        elif member_name:
            stmt = stmt.where(Member.full_name.ilike(f"%{member_name}%"))
        else:
            return tool_response(
                ok=True,
                data=None,
                sources=[source(table="members", label="Membre recherché", record_count=0)],
                warnings=["Aucun membre précis n’a été demandé."],
            )

        member = self.db.scalar(stmt.limit(1))
        data = _member_payload(member) if member else None
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="members", label="Détail du membre", record_count=1 if member else 0)],
            warnings=warnings_for_empty(data),
        )

    def get_member_collections(self, member_id: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        stmt = (
            select(Member.id, Member.full_name, Product.name, func.coalesce(func.sum(Input.quantity), 0.0), func.count(Input.id))
            .join(Input, Input.member_id == Member.id)
            .join(Product, Product.id == Input.product_id)
            .where(Member.cooperative_id == self.current_user.cooperative_id)
            .group_by(Member.id, Member.full_name, Product.name)
            .order_by(func.coalesce(func.sum(Input.quantity), 0.0).desc())
        )
        if member_id:
            try:
                stmt = stmt.where(Member.id == UUID(str(member_id)))
            except ValueError:
                return tool_response(ok=True, data=[], sources=[source(table="inputs,members", label="Collectes par membre", record_count=0)], warnings=["L’identifiant du membre est invalide."])
        stmt = apply_date_filter(stmt, Input.date, date_range)
        rows = self.db.execute(stmt.limit(30)).all()
        data = [
            {
                "member_id": str(member_id_value),
                "member_name": str(member_name),
                "product": str(product),
                "quantity_kg": float(quantity or 0.0),
                "record_count": int(count or 0),
            }
            for member_id_value, member_name, product, quantity, count in rows
        ]
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="inputs,members,products", label="Collectes par membre", record_count=len(data))],
            warnings=warnings_for_empty(data),
        )

    def get_top_members_by_collection(self, product: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        stmt = (
            select(Member.id, Member.full_name, Member.code, func.coalesce(func.sum(Input.quantity), 0.0))
            .join(Input, Input.member_id == Member.id)
            .join(Product, Product.id == Input.product_id)
            .where(Member.cooperative_id == self.current_user.cooperative_id)
            .group_by(Member.id, Member.full_name, Member.code)
            .order_by(func.coalesce(func.sum(Input.quantity), 0.0).desc())
        )
        if product:
            aliases = [alias.lower() for alias in _product_aliases(product)]
            stmt = stmt.where(func.lower(Product.name).in_(aliases))
        stmt = apply_date_filter(stmt, Input.date, date_range)
        rows = self.db.execute(stmt.limit(10)).all()
        data = [
            {
                "member_id": str(member_id),
                "member_name": str(member_name),
                "member_code": str(code),
                "quantity_kg": float(quantity or 0.0),
            }
            for member_id, member_name, code, quantity in rows
        ]
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="inputs,members", label="Principaux producteurs par collecte", record_count=len(data))],
            warnings=warnings_for_empty(data),
        )


def _member_payload(member: Member | None) -> dict[str, Any] | None:
    if member is None:
        return None
    return {
        "id": str(member.id),
        "code": member.code,
        "full_name": member.full_name,
        "village": member.village,
        "main_product": member.main_product,
        "products": member.products,
        "parcel_count": member.parcel_count,
        "area_hectares": float(member.area_hectares or 0.0),
        "status": enum_value(member.status),
    }


def _product_aliases(value: str | None) -> list[str]:
    canonical = canonical_product_name(value)
    if canonical == "mango":
        return ["mango", "mangue"]
    if canonical == "peanut":
        return ["peanut", "arachide"]
    if canonical == "millet":
        return ["millet", "mil"]
    return [canonical]

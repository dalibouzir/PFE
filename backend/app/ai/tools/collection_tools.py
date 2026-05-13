from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.tools.app_data_tools import apply_date_filter, canonical_product_name, enum_value, source, tool_response, warnings_for_empty
from app.models.input import Input
from app.models.member import Member
from app.models.product import Product
from app.models.user import User


class CollectionTools:
    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.current_user = current_user

    def get_collections_summary(self, product: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        stmt = (
            select(Product.name, func.coalesce(func.sum(Input.quantity), 0.0), func.count(Input.id))
            .join(Product, Product.id == Input.product_id)
            .where(Input.cooperative_id == self.current_user.cooperative_id)
            .group_by(Product.name)
            .order_by(func.coalesce(func.sum(Input.quantity), 0.0).desc())
        )
        stmt = apply_date_filter(stmt, Input.date, date_range)
        rows = self.db.execute(stmt).all()
        data = [
            {"product": str(name), "quantity_kg": float(quantity or 0.0), "record_count": int(count or 0)}
            for name, quantity, count in rows
            if not product or canonical_product_name(name) == canonical_product_name(product)
        ]
        return tool_response(ok=True, data=data, sources=[source(table="inputs,products", label="Résumé des collectes", record_count=len(data))], warnings=warnings_for_empty(data))

    def get_daily_collection_totals(self, date_range: list[str] | None = None) -> dict[str, Any]:
        stmt = (
            select(Input.date, func.coalesce(func.sum(Input.quantity), 0.0), func.count(Input.id))
            .where(Input.cooperative_id == self.current_user.cooperative_id)
            .group_by(Input.date)
            .order_by(Input.date.desc())
        )
        stmt = apply_date_filter(stmt, Input.date, date_range)
        rows = self.db.execute(stmt.limit(30)).all()
        data = [{"date": str(day), "quantity_kg": float(quantity or 0.0), "record_count": int(count or 0)} for day, quantity, count in rows]
        return tool_response(ok=True, data=data, sources=[source(table="inputs", label="Collectes journalières", record_count=len(data))], warnings=warnings_for_empty(data))

    def get_collection_by_member(self, member_id: str | None = None, product: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        stmt = (
            select(Member.id, Member.full_name, Product.name, func.coalesce(func.sum(Input.quantity), 0.0), func.count(Input.id))
            .join(Member, Member.id == Input.member_id)
            .join(Product, Product.id == Input.product_id)
            .where(Input.cooperative_id == self.current_user.cooperative_id)
            .group_by(Member.id, Member.full_name, Product.name)
            .order_by(func.coalesce(func.sum(Input.quantity), 0.0).desc())
        )
        if member_id:
            try:
                stmt = stmt.where(Member.id == UUID(str(member_id)))
            except ValueError:
                return tool_response(ok=True, data=[], sources=[source(table="inputs,members", label="Collectes par membre", record_count=0)], warnings=["L’identifiant du membre est invalide."])
        if product:
            stmt = stmt.where(func.lower(Product.name).in_(_product_aliases(product)))
        stmt = apply_date_filter(stmt, Input.date, date_range)
        rows = self.db.execute(stmt.limit(50)).all()
        data = [
            {
                "member_id": str(member_id_value),
                "member_name": str(member_name),
                "product": str(product_name),
                "quantity_kg": float(quantity or 0.0),
                "record_count": int(count or 0),
            }
            for member_id_value, member_name, product_name, quantity, count in rows
        ]
        return tool_response(ok=True, data=data, sources=[source(table="inputs,members,products", label="Collectes par membre", record_count=len(data))], warnings=warnings_for_empty(data))

    def get_collection_quality_summary(self, product: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        stmt = (
            select(Product.name, Input.grade, func.coalesce(func.sum(Input.quantity), 0.0), func.count(Input.id))
            .join(Product, Product.id == Input.product_id)
            .where(Input.cooperative_id == self.current_user.cooperative_id)
            .group_by(Product.name, Input.grade)
            .order_by(Product.name.asc(), Input.grade.asc())
        )
        if product:
            stmt = stmt.where(func.lower(Product.name).in_(_product_aliases(product)))
        stmt = apply_date_filter(stmt, Input.date, date_range)
        rows = self.db.execute(stmt).all()
        data = [
            {"product": str(product_name), "grade": str(grade), "quantity_kg": float(quantity or 0.0), "record_count": int(count or 0)}
            for product_name, grade, quantity, count in rows
        ]
        return tool_response(ok=True, data=data, sources=[source(table="inputs", label="Qualité des collectes", record_count=len(data))], warnings=warnings_for_empty(data))


def _product_aliases(value: str | None) -> list[str]:
    canonical = canonical_product_name(value)
    if canonical == "mango":
        return ["mango", "mangue"]
    if canonical == "peanut":
        return ["peanut", "arachide"]
    if canonical == "millet":
        return ["millet", "mil"]
    return [canonical]

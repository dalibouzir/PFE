from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import sys
from uuid import UUID

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.models.input import Input
from app.models.member import Member
from app.models.product import Product
from app.models.stock import Stock
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.schemas.commercial import CatalogProductCreate, CommercialOrderIntake, CommercialOrderStatusUpdate, OrderLineCreate
from app.schemas.input import InputCreate
from app.services import commercial as commercial_service
from app.services import inputs as inputs_service
from app.services.stocks import normalize_stock_grade

TAG = "GRADEVAL2026"


def _pick_manager(session) -> User:
    manager = session.scalar(
        select(User)
        .where(User.role.in_([UserRole.MANAGER, UserRole.OWNER, UserRole.ADMIN]))
        .order_by(User.created_at.asc())
    )
    if manager is not None and manager.cooperative_id is not None:
        return manager
    fallback = session.scalar(
        select(User)
        .where(User.cooperative_id.isnot(None))
        .order_by(User.created_at.asc())
    )
    if fallback is None:
        raise RuntimeError("No user with cooperative_id found.")
    return fallback


def _pick_member_and_product(session, cooperative_id: UUID) -> tuple[Member, Product]:
    member = session.scalar(
        select(Member)
        .where(Member.cooperative_id == cooperative_id)
        .order_by(Member.created_at.asc())
    )
    product = session.scalar(
        select(Product)
        .where(Product.cooperative_id == cooperative_id)
        .order_by(Product.created_at.asc())
    )
    if member is None or product is None:
        raise RuntimeError("Missing member/product in cooperative for grade validation.")
    return member, product


def main() -> None:
    with SessionLocal() as session:
        manager = _pick_manager(session)
        cooperative_id = manager.cooperative_id
        assert cooperative_id is not None
        member, product = _pick_member_and_product(session, cooperative_id)

        inputs_created: list[Input] = []
        for idx, (grade, qty) in enumerate([("A", 37.0), ("B", 29.0)], start=1):
            payload = InputCreate(
                member_id=member.id,
                product_id=product.id,
                date=date.today(),
                quantity=qty,
                grade=grade,
                status="validated",
                source_type="manual",
                bl_number=f"{TAG}-BL-{idx}",
            )
            rec = inputs_service.record_input(session, manager, payload)
            inputs_created.append(
                session.scalar(select(Input).where(Input.id == rec.id))  # type: ignore[arg-type]
            )

        grades = [normalize_stock_grade("A"), normalize_stock_grade("B"), normalize_stock_grade("C"), normalize_stock_grade("Non spécifié")]
        stock_rows = session.scalars(
            select(Stock)
            .where(Stock.cooperative_id == cooperative_id, Stock.product_id == product.id, Stock.grade.in_(grades))
            .order_by(Stock.grade.asc())
        ).all()

        movements = session.scalars(
            select(StockMovement)
            .where(
                StockMovement.cooperative_id == cooperative_id,
                StockMovement.input_id.in_([row.id for row in inputs_created if row is not None]),
            )
            .order_by(StockMovement.created_at.asc())
        ).all()

        catalog = commercial_service.create_catalog_product(
            session,
            manager,
            CatalogProductCreate(
                source_product_id=product.id,
                source_grade="A",
                name=f"{TAG}-CAT-{product.name}",
                description=f"{TAG} commercial grade validation",
                category="Validation",
                sale_unit="kg",
                sale_price_fcfa=1900,
                cost_price_fcfa=1100,
                min_order_qty=1,
                allocated_quantity=5,
            ),
        )
        order = commercial_service.intake_order(
            session,
            manager,
            CommercialOrderIntake(
                customer_name=f"{TAG} Client",
                customer_phone="+221700000000",
                lines=[OrderLineCreate(catalog_product_id=catalog.id, grade="A", quantity=2)],
            ),
        )
        for status in ["confirmed", "preparing", "ready", "delivered"]:
            order = commercial_service.update_order_status(
                session, manager, order.id, CommercialOrderStatusUpdate(status=status)
            )

        stock_after_delivery = session.scalars(
            select(Stock)
            .where(Stock.cooperative_id == cooperative_id, Stock.product_id == product.id)
            .order_by(Stock.grade.asc())
        ).all()

        report = {
            "tag": TAG,
            "cooperative_id": str(cooperative_id),
            "product_id": str(product.id),
            "product_name": product.name,
            "inputs_created": [
                {
                    "id": str(row.id),
                    "collecte_reference": row.collecte_reference,
                    "grade": row.grade,
                    "quantity": row.quantity,
                }
                for row in inputs_created
                if row is not None
            ],
            "stock_rows_for_product": [
                {
                    "grade": row.grade,
                    "total_stock_kg": row.total_stock_kg,
                    "available_stock_kg": max(row.total_stock_kg - row.reserved_in_lots_kg, 0.0),
                }
                for row in stock_rows
            ],
            "movements_from_inputs": [
                {
                    "movement_reference": row.movement_reference,
                    "movement_type": row.movement_type,
                    "source": row.source,
                    "grade": row.grade,
                    "quantity_kg": row.quantity_kg,
                }
                for row in movements
            ],
            "commercial_validation": {
                "catalog_id": str(catalog.id),
                "catalog_source_grade": catalog.source_grade,
                "order_id": str(order.id),
                "order_status": order.status,
                "line_grades": [line.grade for line in order.lines],
            },
            "stock_rows_after_delivery": [
                {
                    "grade": row.grade,
                    "total_stock_kg": row.total_stock_kg,
                    "reserved_in_lots_kg": row.reserved_in_lots_kg,
                }
                for row in stock_after_delivery
            ],
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

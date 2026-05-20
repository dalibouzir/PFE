from __future__ import annotations

import argparse
from datetime import date, timedelta
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
from app.models.member import Member
from app.models.parcel import Parcel
from app.models.product import Product
from app.models.stock import Stock
from app.models.batch import Batch
from app.models.input import Input
from app.models.commercial_catalog_product import CommercialCatalogProduct
from app.models.commercial_order import CommercialOrder
from app.models.cooperative import Cooperative
from app.models.farmer_advance import FarmerAdvance
from app.models.treasury_transaction import TreasuryTransaction
from app.models.user import User
from app.schemas.batch import BatchCreate, BatchStartPostHarvestRequest
from app.schemas.commercial import CatalogProductCreate, CommercialOrderIntake, CommercialOrderStatusUpdate, OrderLineCreate
from app.schemas.farmer_advance import FarmerAdvanceCreate
from app.schemas.input import InputCreate
from app.schemas.treasury import TreasuryTransactionCreate
from app.services import batches as batches_service
from app.services import commercial as commercial_service
from app.services import farmer_advances as advances_service
from app.services import inputs as inputs_service
from app.services import treasury as treasury_service

TAG = "DEMOGRADE26"


def _pick_manager(session, cooperative_name: str) -> User:
    coop = session.scalar(select(Cooperative).where(Cooperative.name == cooperative_name))
    if coop is None:
        raise RuntimeError(f"Cooperative not found: {cooperative_name}")
    manager = session.scalar(
        select(User)
        .where(
            User.cooperative_id == coop.id,
            User.role.in_([UserRole.MANAGER, UserRole.OWNER, UserRole.ADMIN]),
        )
        .order_by(User.created_at.asc())
    )
    if manager is not None and manager.cooperative_id is not None:
        return manager
    fallback = session.scalar(select(User).where(User.cooperative_id == coop.id).order_by(User.created_at.asc()))
    if fallback is None:
        raise RuntimeError(f"No user with cooperative_id found for {cooperative_name}.")
    return fallback


def _ensure_members_parcels(session, cooperative_id: UUID) -> tuple[list[Member], list[Parcel]]:
    members: list[Member] = []
    parcels: list[Parcel] = []
    names = ["Awa Diop", "Mamadou Fall", "Khadija Ndiaye", "Ibrahima Sarr"]
    villages = ["Ndiaganiao", "Thiès", "Mbour", "Fatick"]
    for idx, (name, village) in enumerate(zip(names, villages), start=1):
        code = f"{TAG}-M-{idx:02d}"
        member = session.scalar(select(Member).where(Member.cooperative_id == cooperative_id, Member.code == code))
        if member is None:
            member = Member(
                cooperative_id=cooperative_id,
                code=code,
                full_name=name,
                phone=f"+2217700{idx:04d}",
                village=village,
                main_product="Mangue",
                parcel_count=1,
                area_hectares=2.5 + idx,
                status="active",
            )
            session.add(member)
            session.flush()
        members.append(member)
        parcel_name = f"{TAG}-PARCEL-{idx:02d}"
        parcel = session.scalar(
            select(Parcel).where(Parcel.cooperative_id == cooperative_id, Parcel.member_id == member.id, Parcel.name == parcel_name)
        )
        if parcel is None:
            parcel = Parcel(
                cooperative_id=cooperative_id,
                member_id=member.id,
                name=parcel_name,
                surface_ha=1.8 + idx,
                main_culture="Mangue",
                variety="Kent",
                tree_count=80 + idx * 10,
            )
            session.add(parcel)
            session.flush()
        parcels.append(parcel)
    return members, parcels


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed controlled grade-aware demo data in one cooperative.")
    parser.add_argument("--cooperative-name", required=True)
    args = parser.parse_args()

    report: dict[str, object] = {"tag": TAG}
    with SessionLocal() as session:
        manager = _pick_manager(session, args.cooperative_name)
        cooperative_id = manager.cooperative_id
        assert cooperative_id is not None

        products = session.scalars(select(Product).where(Product.cooperative_id == cooperative_id).order_by(Product.created_at.asc())).all()
        if len(products) < 4:
            raise RuntimeError("Need at least 4 products in cooperative to seed grade demo.")
        members, parcels = _ensure_members_parcels(session, cooperative_id)
        member_products = "; ".join([p.name for p in products[:4]])
        for member in members:
            member.main_product = products[0].name
            member.secondary_products = member_products
        session.commit()

        batch_specs = [
            (products[0], members[0], parcels[0], 240.0),
            (products[1], members[1], parcels[1], 210.0),
            (products[2], members[2], parcels[2], 180.0),
            (products[3], members[3], parcels[3], 160.0),
            (products[0], members[1], parcels[1], 130.0),
        ]
        grades = ["A", "B", "C", "A"]

        batches = []
        linked_inputs = []
        postharvest_started = []

        for idx, (product, member, parcel, qty) in enumerate(batch_specs, start=1):
            note_tag = f"{TAG}-LOT-{idx:02d}"
            existing = session.scalar(
                select(Batch).where(
                    Batch.cooperative_id == cooperative_id,
                    Batch.status_note == note_tag,
                )
            )
            if existing is None:
                created = batches_service.create_batch(
                    session,
                    manager,
                    BatchCreate(
                        product_id=product.id,
                        member_id=member.id,
                        parcel_id=parcel.id,
                        creation_date=date.today() - timedelta(days=10 + idx),
                        initial_qty=qty,
                        unit="kg",
                        process_steps=["Nettoyage", "Séchage", "Tri", "Emballage"],
                    ),
                )
                existing = session.get(Batch, created.id)
                assert existing is not None
                existing.status_note = note_tag
                session.commit()
                session.refresh(existing)
            batches.append(existing)

        for idx, batch in enumerate(batches[:4], start=1):
            if batch.preharvest_completed_at is None:
                batches_service.complete_preharvest(session, manager, batch.id)
            grade = grades[idx - 1]
            linked = session.scalar(
                select(Input).where(
                    Input.cooperative_id == cooperative_id,
                    Input.batch_id == batch.id,
                    Input.source_type == "lot_linked_collecte",
                    Input.grade == grade,
                )
            )
            if linked is None:
                input_rec = inputs_service.record_input(
                    session,
                    manager,
                    InputCreate(
                        member_id=batch.member_id,
                        product_id=batch.product_id,
                        batch_id=batch.id,
                        date=date.today() - timedelta(days=5 - idx),
                        quantity=120 + idx * 15,
                        grade=grade,
                        status="validated",
                        source_type="lot_linked_collecte",
                        bl_number=f"{TAG}-BL-{idx:02d}",
                    ),
                )
                linked = session.get(Input, input_rec.id)
            linked_inputs.append(linked)
            if batch.postharvest_started_at is None:
                started = batches_service.start_postharvest(
                    session,
                    manager,
                    batch.id,
                    BatchStartPostHarvestRequest(
                        product_id=batch.product_id,
                        grade=grade,
                        quantity_kg=min(80.0, float(batch.confirmed_weight_kg or 80.0)),
                    ),
                )
                postharvest_started.append(str(started.id))

        # Catalog products from stock buckets.
        stock_rows = session.scalars(
            select(Stock)
            .where(Stock.cooperative_id == cooperative_id)
            .order_by(Stock.total_stock_kg.desc())
        ).all()
        bucket_rows = [
            row
            for row in stock_rows
            if float((row.total_stock_kg or 0.0) - (row.reserved_in_lots_kg or 0.0)) > 5 and row.grade != "Non spécifié"
        ]
        if not bucket_rows:
            raise RuntimeError("No non-legacy grade stock buckets available to build demo catalog products.")
        catalog_items: list[tuple[UUID, str]] = []
        for idx in range(1, 6):
            row = bucket_rows[(idx - 1) % len(bucket_rows)]
            name = f"{TAG}-CAT-{idx:02d}"
            existing_catalog = session.scalar(
                select(CommercialCatalogProduct).where(
                    CommercialCatalogProduct.cooperative_id == cooperative_id,
                    CommercialCatalogProduct.name == name,
                )
            )
            if existing_catalog is None:
                cat = commercial_service.create_catalog_product(
                    session,
                    manager,
                    CatalogProductCreate(
                        source_product_id=row.product_id,
                        source_grade=row.grade,
                        name=name,
                        description=f"{TAG} produit catalogue grade {row.grade}",
                        category="Démo",
                        sale_unit="kg",
                        sale_price_fcfa=2200 + idx * 120,
                        cost_price_fcfa=1400 + idx * 90,
                        min_order_qty=1,
                        allocated_quantity=8 + idx,
                    ),
                )
                catalog_items.append((cat.id, cat.source_grade))
            else:
                existing_grade = commercial_service._extract_grade_marker(existing_catalog.description)  # type: ignore[attr-defined]
                catalog_items.append((existing_catalog.id, existing_grade))

        orders = []
        for idx in range(4):
            customer = f"{TAG} Client {idx+1}"
            existing_order = session.scalar(
                select(CommercialOrder).where(
                    CommercialOrder.cooperative_id == cooperative_id,
                    CommercialOrder.customer_name == customer,
                )
            )
            if existing_order is not None:
                orders.append(existing_order)
                continue
            order = commercial_service.intake_order(
                session,
                manager,
                CommercialOrderIntake(
                    customer_name=customer,
                    customer_phone=f"+2217800{idx:04d}",
                    customer_email=f"client{idx+1}@demo.local",
                    lines=[
                        OrderLineCreate(
                            catalog_product_id=catalog_items[idx][0],
                            quantity=2,
                            grade=catalog_items[idx][1],
                        )
                    ],
                ),
            )
            for st in ["confirmed", "preparing", "ready", "delivered"]:
                order = commercial_service.update_order_status(
                    session, manager, order.id, CommercialOrderStatusUpdate(status=st)
                )
            orders.append(order)

        # 4 farmer advances (with linked treasury expense)
        advances = []
        for idx, member in enumerate(members, start=1):
            reason = f"{TAG} avance {idx}"
            existing_adv = session.scalar(
                select(advances_service.FarmerAdvance).where(
                    FarmerAdvance.cooperative_id == cooperative_id,
                    FarmerAdvance.reason == reason,
                )
            )
            if existing_adv is None:
                adv = advances_service.create_farmer_advance(
                    session,
                    manager,
                    FarmerAdvanceCreate(
                        farmer_id=member.id,
                        amount_fcfa=65000 + idx * 5000,
                        reason=reason,
                        advance_date=date.today() - timedelta(days=idx),
                        note=f"{TAG} seed",
                        source_type="demo_seed",
                    ),
                )
                advances.append(str(adv.id))
            else:
                advances.append(str(existing_adv.id))

        # 5 additional treasury transactions.
        treasury_ids = []
        for idx in range(1, 6):
            label = f"{TAG} trésorerie {idx}"
            existing_tx = session.scalar(
                select(treasury_service.TreasuryTransaction).where(
                    TreasuryTransaction.cooperative_id == cooperative_id,
                    TreasuryTransaction.label == label,
                )
            )
            if existing_tx is None:
                tx = treasury_service.create_treasury_transaction(
                    session,
                    manager,
                    TreasuryTransactionCreate(
                        transaction_date=date.today() - timedelta(days=idx),
                        type="expense" if idx % 2 else "income",
                        category="demo",
                        label=label,
                        amount_fcfa=12000 + idx * 3000,
                        note=f"{TAG} extra treasury movement",
                        source_type="demo_seed",
                        status="enregistre_sans_justificatif",
                    ),
                )
                treasury_ids.append(str(tx.id))
            else:
                treasury_ids.append(str(existing_tx.id))

        invoices = commercial_service.list_invoices(session, manager)
        tagged_invoices = [inv for inv in invoices if TAG in (inv.customer_name or "")]

        report.update(
            {
                "cooperative_id": str(cooperative_id),
                "members_count": len(members),
                "lots_count": len(batches),
                "linked_collectes_count": len([row for row in linked_inputs if row is not None]),
                "postharvest_started_count": len(postharvest_started),
                "catalog_products_count": len(catalog_items),
                "orders_count": len(orders),
                "invoices_count": len(tagged_invoices),
                "farmer_advances_count": len(advances),
                "extra_treasury_count": len(treasury_ids),
            }
        )

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
import sys
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.models.batch import Batch
from app.models.commercial_catalog_product import CommercialCatalogProduct
from app.models.commercial_invoice import CommercialInvoice, CommercialInvoiceLine
from app.models.commercial_order import CommercialOrder, CommercialOrderLine
from app.models.cooperative import Cooperative
from app.models.enums import (
    BatchStatus,
    CommercialCatalogStatus,
    CommercialOrderStatus,
    FarmerAdvanceStatus,
    InputStatus,
    InvoiceStatus,
    MemberStatus,
    PreHarvestStepStatus,
    ProcessStepStatus,
    RiskLevel,
    TreasuryTransactionStatus,
    TreasuryTransactionType,
    UserRole,
)
from app.models.farmer_advance import FarmerAdvance
from app.models.field import Field
from app.models.global_charge import GlobalCharge
from app.models.input import Input
from app.models.member import Member
from app.models.ml import MLPredictionLog, MLRecommendationLog, RecommendationFeedbackLog
from app.models.parcel import Parcel
from app.models.pre_harvest_step import PreHarvestStep
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.reference import KnowledgeChunk, ReferenceMetric
from app.models.stock import Stock
from app.models.treasury_transaction import TreasuryTransaction
from app.models.user import User

DEMO_TAG = "DEMOFP"
DEMO_BATCH_PREFIX = f"{DEMO_TAG}-LOT-"
DEMO_ORDER_PREFIX = f"{DEMO_TAG}-ORD-"
DEMO_INVOICE_PREFIX = f"{DEMO_TAG}-INV-"
DEMO_TREASURY_PREFIX = f"{DEMO_TAG}-TRX-"
DEMO_MEMBER_PREFIX = f"{DEMO_TAG}-M-"
DEMO_PARCEL_PREFIX = f"{DEMO_TAG}-PARCEL-"
DEMO_FIELD_PREFIX = f"{DEMO_TAG}-FIELD-"
DEMO_SOURCE_PREFIX = f"{DEMO_TAG}-SRC-"
DEMO_MODEL_VERSION = f"{DEMO_TAG}-v1.0"


def _upsert(session: Session, model, lookup: dict[str, Any], payload: dict[str, Any], counters: dict[str, dict[str, int]]):
    row = session.scalars(select(model).filter_by(**lookup)).first()
    table = model.__tablename__
    if row is None:
        row = model(**lookup, **payload)
        session.add(row)
        counters[table]["created"] += 1
    else:
        for key, value in payload.items():
            setattr(row, key, value)
        counters[table]["updated"] += 1
    session.flush()
    return row


def _ensure_manager_and_coop(session: Session) -> tuple[User, Cooperative]:
    manager = session.scalars(
        select(User)
        .where(User.role.in_([UserRole.MANAGER, UserRole.OWNER, UserRole.ADMIN]))
        .order_by(User.created_at.asc())
    ).first()
    if not manager or not manager.cooperative_id:
        raise RuntimeError("No manager/owner/admin user with cooperative_id found.")
    coop = session.get(Cooperative, manager.cooperative_id)
    if coop is None:
        raise RuntimeError("Manager cooperative not found.")
    return manager, coop


def _seed_products(session: Session, *, coop_id: UUID, counters: dict[str, dict[str, int]]) -> dict[str, Product]:
    products_spec = [
        ("Mangue", "Fruit", "kg", "A"),
        ("Arachide", "Oléagineux", "kg", "A"),
        ("Mil", "Céréale", "kg", "B"),
        ("Bissap", "Plante", "kg", "A"),
    ]
    out: dict[str, Product] = {}
    for name, category, unit, grade in products_spec:
        row = _upsert(
            session,
            Product,
            {"cooperative_id": coop_id, "name": name},
            {"category": category, "unit": unit, "quality_grade": grade},
            counters,
        )
        out[name] = row
    return out


def _seed_members(session: Session, *, coop_id: UUID, counters: dict[str, dict[str, int]]) -> list[Member]:
    names = [
        "Mamadou Ba",
        "Awa Ndiaye",
        "Cheikh Diop",
        "Fatou Sarr",
        "Ibrahima Fall",
        "Mariama Sow",
        "Ousmane Gueye",
        "Khady Kane",
        "Abdoulaye Sy",
        "Rokhaya Diallo",
        "Pape Mbaye",
        "Ndeye Fall",
        "Alioune Cisse",
        "Sokhna Diatta",
    ]
    product_cycle = ["Mangue", "Arachide", "Mil", "Bissap"]
    villages = ["Thies", "Mbour", "Tivaouane", "Pout", "Notto"]
    members: list[Member] = []
    for idx, full_name in enumerate(names, start=1):
        main_product = product_cycle[(idx - 1) % len(product_cycle)]
        row = _upsert(
            session,
            Member,
            {"cooperative_id": coop_id, "code": f"{DEMO_MEMBER_PREFIX}{idx:03d}"},
            {
                "full_name": full_name,
                "phone": f"+2217700{idx:04d}",
                "village": villages[(idx - 1) % len(villages)],
                "notes": f"{DEMO_TAG} synthetic member",
                "main_product": main_product,
                "secondary_products": "Mangue;Arachide" if idx % 3 == 0 else "Mil;Bissap",
                "parcel_count": 0,
                "area_hectares": float(1.2 + (idx % 5) * 0.8),
                "join_date": date(2023, (idx % 12) + 1, min(25, idx + 2)),
                "specialty": "Post-récolte",
                "status": MemberStatus.ACTIVE if idx % 5 != 0 else MemberStatus.SEASONAL,
            },
            counters,
        )
        members.append(row)
    return members


def _seed_fields_and_parcels(
    session: Session,
    *,
    coop_id: UUID,
    members: list[Member],
    counters: dict[str, dict[str, int]],
) -> tuple[list[Field], list[Parcel]]:
    fields: list[Field] = []
    parcels: list[Parcel] = []
    cultures = ["Mangue", "Arachide", "Mil", "Bissap"]
    for idx, member in enumerate(members, start=1):
        member_fields: list[Field] = []
        member_parcels: list[Parcel] = []
        parcel_count = 1 if idx % 4 else 2
        for j in range(parcel_count):
            f = _upsert(
                session,
                Field,
                {"cooperative_id": coop_id, "member_id": member.id, "location": f"{DEMO_FIELD_PREFIX}{idx:03d}-{j+1}"},
                {
                    "area": float(0.8 + ((idx + j) % 4) * 0.6),
                    "soil_type": ["sablo-limoneux", "argileux", "limoneux"][(idx + j) % 3],
                    "irrigation_type": ["goutte-à-goutte", "pluvial", "mixte"][(idx + j) % 3],
                },
                counters,
            )
            member_fields.append(f)
            p = _upsert(
                session,
                Parcel,
                {"cooperative_id": coop_id, "member_id": member.id, "name": f"{DEMO_PARCEL_PREFIX}{idx:03d}-{j+1}"},
                {
                    "surface_ha": float(0.7 + ((idx + j) % 5) * 0.5),
                    "main_culture": cultures[(idx + j) % len(cultures)],
                    "variety": ["Kent", "Valencia", "Souna", "Vimto"][(idx + j) % 4],
                    "tree_count": 40 + ((idx + j) % 6) * 15,
                },
                counters,
            )
            member_parcels.append(p)
        member.parcel_count = len(member_parcels)
        member.area_hectares = float(sum(p.surface_ha for p in member_parcels))
        fields.extend(member_fields)
        parcels.extend(member_parcels)
    session.flush()
    return fields, parcels


def _seed_preharvest_steps(
    session: Session,
    *,
    coop_id: UUID,
    manager_id: UUID,
    parcels: list[Parcel],
    counters: dict[str, dict[str, int]],
) -> list[PreHarvestStep]:
    steps: list[PreHarvestStep] = []
    step_specs = [
        ("observation", "Suivi parcelle", "Suivi", "eye"),
        ("intrants", "Application intrants", "Intrants", "flask"),
        ("sanitaire", "Contrôle sanitaire", "Contrôle", "shield"),
        ("recolte_plan", "Planification récolte", "Récolte", "calendar"),
    ]
    today = date.today()
    for parcel_idx, parcel in enumerate(parcels, start=1):
        for order, (step_key, label, category, icon) in enumerate(step_specs, start=1):
            status = PreHarvestStepStatus.COMPLETED if order <= 3 or parcel_idx % 3 else PreHarvestStepStatus.PENDING
            row = _upsert(
                session,
                PreHarvestStep,
                {
                    "cooperative_id": coop_id,
                    "parcel_id": parcel.id,
                    "member_id": parcel.member_id,
                    "step_order": order,
                    "step_key": step_key,
                },
                {
                    "category": category,
                    "label": label,
                    "icon": icon,
                    "status": status,
                    "quantity_value": float(12 + ((parcel_idx + order) % 5) * 4),
                    "quantity_unit": "kg",
                    "operation_cost_fcfa": float(4500 + ((parcel_idx + order) % 6) * 1200),
                    "realization_date": today - timedelta(days=(parcel_idx + order) % 20),
                    "observations": f"{DEMO_TAG} pré-récolte",
                    "completed_at": datetime.now(UTC) if status == PreHarvestStepStatus.COMPLETED else None,
                    "created_by_user_id": manager_id,
                    "updated_by_user_id": manager_id,
                },
                counters,
            )
            steps.append(row)
    return steps


def _seed_inputs(
    session: Session,
    *,
    coop_id: UUID,
    members: list[Member],
    products: dict[str, Product],
    fields: list[Field],
    counters: dict[str, dict[str, int]],
) -> list[Input]:
    grades = ["A", "B", "C"]
    statuses = [InputStatus.VALIDATED, InputStatus.QUALITY_CONTROL, InputStatus.PENDING]
    rows: list[Input] = []
    start = date.today() - timedelta(days=140)
    for idx in range(72):
        member = members[idx % len(members)]
        product = products[["Mangue", "Arachide", "Mil", "Bissap"][idx % 4]]
        field = fields[idx % len(fields)] if fields else None
        d = start + timedelta(days=idx * 2)
        qty = float(120 + (idx % 9) * 25 + ((idx // 8) % 4) * 40)
        estimated = qty * (850 + (idx % 5) * 110)
        key = {
            "cooperative_id": coop_id,
            "member_id": member.id,
            "product_id": product.id,
            "date": d,
            "grade": grades[idx % len(grades)],
        }
        row = session.scalars(select(Input).filter_by(**key)).first()
        payload = {
            "field_id": field.id if field else None,
            "quantity": qty,
            "estimated_value": float(estimated),
            "status": statuses[idx % len(statuses)],
        }
        if row is None:
            row = Input(**key, **payload)
            session.add(row)
            counters[Input.__tablename__]["created"] += 1
        else:
            for k, v in payload.items():
                setattr(row, k, v)
            counters[Input.__tablename__]["updated"] += 1
        rows.append(row)
    session.flush()
    return rows


def _seed_batches_and_steps(
    session: Session,
    *,
    coop_id: UUID,
    manager_id: UUID,
    products: dict[str, Product],
    counters: dict[str, dict[str, int]],
) -> tuple[list[Batch], list[ProcessStep]]:
    specs = [
        ("MANG", "Mangue", BatchStatus.IN_PROGRESS, 1200, [("Nettoyage", 0.02), ("Séchage", 0.09), ("Tri", 0.04)]),
        ("MANG", "Mangue", BatchStatus.COMPLETED, 950, [("Nettoyage", 0.01), ("Séchage", 0.05), ("Tri", 0.02), ("Emballage", 0.01)]),
        ("MANG", "Mangue", BatchStatus.IN_PROGRESS, 700, [("Nettoyage", 0.03), ("Séchage", 0.16)]),
        ("ARAC", "Arachide", BatchStatus.CREATED, 1100, []),
        ("ARAC", "Arachide", BatchStatus.IN_PROGRESS, 860, [("Nettoyage", 0.02), ("Tri", 0.03)]),
        ("ARAC", "Arachide", BatchStatus.COMPLETED, 780, [("Nettoyage", 0.01), ("Tri", 0.02), ("Conditionnement", 0.02)]),
        ("MIL", "Mil", BatchStatus.IN_PROGRESS, 980, [("Nettoyage", 0.03), ("Séchage", 0.08)]),
        ("MIL", "Mil", BatchStatus.COMPLETED, 860, [("Nettoyage", 0.02), ("Séchage", 0.04), ("Tri", 0.03)]),
        ("MIL", "Mil", BatchStatus.ARCHIVED, 650, [("Nettoyage", 0.05), ("Séchage", 0.14), ("Tri", 0.06)]),
        ("BISS", "Bissap", BatchStatus.IN_PROGRESS, 720, [("Nettoyage", 0.02), ("Tri", 0.04)]),
        ("BISS", "Bissap", BatchStatus.COMPLETED, 680, [("Nettoyage", 0.01), ("Tri", 0.02), ("Emballage", 0.01)]),
        ("BISS", "Bissap", BatchStatus.CREATED, 520, []),
        ("MANG", "Mangue", BatchStatus.IN_PROGRESS, 450, [("Nettoyage", 0.02), ("Séchage", 0.22)]),
        ("ARAC", "Arachide", BatchStatus.COMPLETED, 990, [("Nettoyage", 0.01), ("Tri", 0.015), ("Emballage", 0.01)]),
    ]
    batches: list[Batch] = []
    process_steps: list[ProcessStep] = []
    today = date.today()
    for idx, (code_key, product_name, status, initial_qty, step_losses) in enumerate(specs, start=1):
        code = f"{DEMO_BATCH_PREFIX}{code_key}-{idx:03d}"
        creation_date = today - timedelta(days=95 - idx * 3)
        running_qty = float(initial_qty)
        current_qty = float(initial_qty)
        ordered_steps = [name for name, _ in step_losses] or ["Nettoyage", "Séchage", "Tri", "Emballage"]
        for _, loss_ratio in step_losses:
            current_qty = current_qty * (1.0 - loss_ratio)
        batch = _upsert(
            session,
            Batch,
            {"code": code},
            {
                "cooperative_id": coop_id,
                "product_id": products[product_name].id,
                "creation_date": creation_date,
                "unit": "kg",
                "ordered_process_steps": ordered_steps,
                "initial_qty": float(initial_qty),
                "current_qty": round(float(current_qty), 2),
                "status": status,
                "created_by_user_id": manager_id,
            },
            counters,
        )
        batches.append(batch)

        session.execute(delete(ProcessStep).where(ProcessStep.batch_id == batch.id))
        counters[ProcessStep.__tablename__]["deleted"] += len(step_losses)
        for step_idx, (step_name, loss_ratio) in enumerate(step_losses, start=1):
            qty_in = round(running_qty, 2)
            qty_out = round(qty_in * (1.0 - loss_ratio), 2)
            waste = round(qty_in - qty_out, 2)
            step = ProcessStep(
                batch_id=batch.id,
                sequence_order=step_idx,
                type=step_name,
                date=creation_date + timedelta(days=step_idx),
                qty_in=qty_in,
                qty_out=qty_out,
                waste_qty=waste,
                loss_value=waste,
                loss_unit="kg",
                normalized_loss_value=waste,
                notes=f"{DEMO_TAG} process step",
                status=ProcessStepStatus.COMPLETED if status in {BatchStatus.IN_PROGRESS, BatchStatus.COMPLETED, BatchStatus.ARCHIVED} else ProcessStepStatus.PENDING,
                executed_at=datetime.now(UTC) if status in {BatchStatus.IN_PROGRESS, BatchStatus.COMPLETED, BatchStatus.ARCHIVED} else None,
                duration_minutes=45 + step_idx * 25,
            )
            running_qty = float(qty_out)
            session.add(step)
            process_steps.append(step)
            counters[ProcessStep.__tablename__]["created"] += 1
    session.flush()
    return batches, process_steps


def _seed_recommendations(
    session: Session,
    *,
    batches: list[Batch],
    counters: dict[str, dict[str, int]],
) -> list[Recommendation]:
    recos: list[Recommendation] = []
    for idx, batch in enumerate(batches, start=1):
        if batch.status == BatchStatus.CREATED:
            continue
        loss_pct = 0.0
        if batch.initial_qty > 0:
            loss_pct = max(0.0, (float(batch.initial_qty) - float(batch.current_qty)) * 100.0 / float(batch.initial_qty))
        efficiency = max(0.0, 100.0 - loss_pct)
        anomaly = round(min(0.95, loss_pct / 35.0), 3)
        risk = RiskLevel.HIGH if loss_pct >= 18 else RiskLevel.MEDIUM if loss_pct >= 9 else RiskLevel.LOW
        action = (
            "Renforcer le contrôle humidité et le tri sur lots en cours."
            if risk != RiskLevel.LOW
            else "Maintenir le protocole actuel et monitoring quotidien."
        )
        row = _upsert(
            session,
            Recommendation,
            {"batch_id": batch.id},
            {
                "loss_pct": round(loss_pct, 2),
                "efficiency_pct": round(efficiency, 2),
                "anomaly_score": anomaly,
                "risk_level": risk,
                "suggested_action": action,
                "rationale": f"{DEMO_TAG} recommandation synthétique pour lot {batch.code}",
            },
            counters,
        )
        recos.append(row)
    return recos


def _seed_stocks(
    session: Session,
    *,
    coop_id: UUID,
    products: dict[str, Product],
    batches: list[Batch],
    counters: dict[str, dict[str, int]],
) -> list[Stock]:
    active_reserved = defaultdict(float)
    for batch in batches:
        if batch.status in {BatchStatus.CREATED, BatchStatus.IN_PROGRESS}:
            product_name = next((name for name, p in products.items() if p.id == batch.product_id), None)
            if product_name:
                active_reserved[product_name] += float(batch.initial_qty or 0.0)
    stock_spec = {
        "Mangue": {"total": 5200.0, "threshold": 1200.0},
        "Arachide": {"total": 3100.0, "threshold": 900.0},
        "Mil": {"total": 2600.0, "threshold": 800.0},
        "Bissap": {"total": 1400.0, "threshold": 750.0},
    }
    rows: list[Stock] = []
    for name, spec in stock_spec.items():
        reserved = round(active_reserved.get(name, 0.0), 2)
        total = float(spec["total"])
        row = _upsert(
            session,
            Stock,
            {"cooperative_id": coop_id, "product_id": products[name].id},
            {
                "quantity": round(max(total - reserved, 0.0), 2),
                "total_stock_kg": total,
                "reserved_in_lots_kg": reserved,
                "processed_output_kg": round(max(0.0, total - reserved) * 0.35, 2),
                "threshold": float(spec["threshold"]),
                "unit": "kg",
                "last_updated": datetime.now(UTC),
            },
            counters,
        )
        rows.append(row)
    return rows


def _seed_catalog_orders_invoices(
    session: Session,
    *,
    coop_id: UUID,
    products: dict[str, Product],
    counters: dict[str, dict[str, int]],
) -> tuple[list[CommercialCatalogProduct], list[CommercialOrder], list[CommercialInvoice]]:
    catalog_rows: dict[str, CommercialCatalogProduct] = {}
    catalog_spec = [
        ("Mangue Séchée", "Mangue", 4500, 2900, 4200, 1900),
        ("Arachide Décortiquée", "Arachide", 2100, 1500, 2600, 1500),
        ("Mil Trié", "Mil", 1600, 1100, 1900, 700),
        ("Bissap Sélection", "Bissap", 3300, 2400, 900, 650),
    ]
    for name, source_name, sale_price, cost_price, total_stock, reserved_stock in catalog_spec:
        row = _upsert(
            session,
            CommercialCatalogProduct,
            {"cooperative_id": coop_id, "name": name},
            {
                "source_product_id": products[source_name].id,
                "description": f"{DEMO_TAG} produit commercial",
                "category": "Transformation",
                "sale_unit": "kg",
                "icon": "package",
                "sale_price_fcfa": float(sale_price),
                "cost_price_fcfa": float(cost_price),
                "min_order_qty": 5.0,
                "total_stock_kg": float(total_stock),
                "reserved_stock_kg": float(reserved_stock),
                "status": CommercialCatalogStatus.ACTIVE,
            },
            counters,
        )
        catalog_rows[name] = row

    statuses = [
        CommercialOrderStatus.RECEIVED,
        CommercialOrderStatus.CONFIRMED,
        CommercialOrderStatus.PREPARING,
        CommercialOrderStatus.READY,
        CommercialOrderStatus.DELIVERED,
        CommercialOrderStatus.PAID,
        CommercialOrderStatus.REFUSED,
    ]
    customers = [
        "Sunu Market",
        "Teranga Distribution",
        "Baobab Food",
        "Dakar Retail",
        "Sahel Export",
        "Jamm Shop",
        "Keur Saveurs",
        "Ndef Leng",
        "Ndogou Plus",
        "Sama Boutique",
    ]
    orders: list[CommercialOrder] = []
    invoices: list[CommercialInvoice] = []
    today = datetime.now(UTC)
    catalog_list = list(catalog_rows.values())
    for idx in range(1, 11):
        status = statuses[(idx - 1) % len(statuses)]
        number = f"{DEMO_ORDER_PREFIX}{idx:03d}"
        order = _upsert(
            session,
            CommercialOrder,
            {"order_number": number},
            {
                "cooperative_id": coop_id,
                "customer_name": customers[(idx - 1) % len(customers)],
                "customer_phone": f"+2217811{idx:04d}",
                "customer_email": f"client{idx}@demo.sn",
                "customer_address": "Dakar, Senegal",
                "payment_method": "virement",
                "notes": f"{DEMO_TAG} synthetic order",
                "status": status,
                "subtotal_fcfa": 0.0,
                "tax_rate": 0.18,
                "tax_amount_fcfa": 0.0,
                "total_amount_fcfa": 0.0,
                "source": "demo_script",
                "locked": True,
                "received_at": today - timedelta(days=35 - idx),
                "confirmed_at": (today - timedelta(days=33 - idx)) if status not in {CommercialOrderStatus.RECEIVED} else None,
                "preparing_at": (today - timedelta(days=30 - idx)) if status in {CommercialOrderStatus.PREPARING, CommercialOrderStatus.READY, CommercialOrderStatus.DELIVERED, CommercialOrderStatus.PAID} else None,
                "ready_at": (today - timedelta(days=27 - idx)) if status in {CommercialOrderStatus.READY, CommercialOrderStatus.DELIVERED, CommercialOrderStatus.PAID} else None,
                "delivered_at": (today - timedelta(days=24 - idx)) if status in {CommercialOrderStatus.DELIVERED, CommercialOrderStatus.PAID} else None,
                "paid_at": (today - timedelta(days=22 - idx)) if status == CommercialOrderStatus.PAID else None,
                "refused_at": (today - timedelta(days=25 - idx)) if status == CommercialOrderStatus.REFUSED else None,
                "refused_reason": "Rupture partielle de stock" if status == CommercialOrderStatus.REFUSED else None,
            },
            counters,
        )
        session.execute(delete(CommercialOrderLine).where(CommercialOrderLine.order_id == order.id))
        counters[CommercialOrderLine.__tablename__]["deleted"] += 2
        line_subtotal = 0.0
        for line_idx in range(2):
            catalog = catalog_list[(idx + line_idx) % len(catalog_list)]
            qty_kg = float(18 + ((idx + line_idx) % 5) * 12)
            unit_price = float(catalog.sale_price_fcfa)
            line_total = qty_kg * unit_price
            line_subtotal += line_total
            line = CommercialOrderLine(
                order_id=order.id,
                catalog_product_id=catalog.id,
                product_name_snapshot=str(catalog.name),
                unit_snapshot="kg",
                quantity=qty_kg,
                quantity_kg=qty_kg,
                unit_price_fcfa=unit_price,
                line_total_fcfa=line_total,
            )
            session.add(line)
            counters[CommercialOrderLine.__tablename__]["created"] += 1
        order.subtotal_fcfa = round(line_subtotal, 2)
        order.tax_amount_fcfa = round(order.subtotal_fcfa * order.tax_rate, 2)
        order.total_amount_fcfa = round(order.subtotal_fcfa + order.tax_amount_fcfa, 2)
        orders.append(order)

        if status in {CommercialOrderStatus.CONFIRMED, CommercialOrderStatus.PREPARING, CommercialOrderStatus.READY, CommercialOrderStatus.DELIVERED, CommercialOrderStatus.PAID}:
            inv_number = f"{DEMO_INVOICE_PREFIX}{idx:03d}"
            issue_date = (today - timedelta(days=28 - idx)).date()
            due_date = issue_date + timedelta(days=14)
            inv_status = InvoiceStatus.PAID if status == CommercialOrderStatus.PAID else InvoiceStatus.PENDING
            invoice = _upsert(
                session,
                CommercialInvoice,
                {"invoice_number": inv_number},
                {
                    "cooperative_id": coop_id,
                    "order_id": order.id,
                    "issue_date": issue_date,
                    "due_date": due_date,
                    "status": inv_status,
                    "customer_name_snapshot": order.customer_name,
                    "customer_phone_snapshot": order.customer_phone,
                    "customer_email_snapshot": order.customer_email,
                    "customer_address_snapshot": order.customer_address,
                    "subtotal_fcfa": order.subtotal_fcfa,
                    "tax_rate": order.tax_rate,
                    "tax_amount_fcfa": order.tax_amount_fcfa,
                    "total_amount_fcfa": order.total_amount_fcfa,
                    "notes": f"{DEMO_TAG} synthetic invoice",
                    "paid_at": (today - timedelta(days=20 - idx)) if inv_status == InvoiceStatus.PAID else None,
                },
                counters,
            )
            session.execute(delete(CommercialInvoiceLine).where(CommercialInvoiceLine.invoice_id == invoice.id))
            counters[CommercialInvoiceLine.__tablename__]["deleted"] += 2
            for line_idx in range(2):
                catalog = catalog_list[(idx + line_idx) % len(catalog_list)]
                qty_kg = float(18 + ((idx + line_idx) % 5) * 12)
                unit_price = float(catalog.sale_price_fcfa)
                line = CommercialInvoiceLine(
                    invoice_id=invoice.id,
                    description=str(catalog.name),
                    unit="kg",
                    quantity=qty_kg,
                    unit_price_fcfa=unit_price,
                    line_total_fcfa=qty_kg * unit_price,
                )
                session.add(line)
                counters[CommercialInvoiceLine.__tablename__]["created"] += 1
            invoices.append(invoice)
    session.flush()
    return list(catalog_rows.values()), orders, invoices


def _seed_treasury_charges_advances(
    session: Session,
    *,
    coop_id: UUID,
    members: list[Member],
    batches: list[Batch],
    parcels: list[Parcel],
    preharvest_steps: list[PreHarvestStep],
    counters: dict[str, dict[str, int]],
) -> tuple[list[TreasuryTransaction], list[GlobalCharge], list[FarmerAdvance]]:
    treasury_rows: list[TreasuryTransaction] = []
    charges_rows: list[GlobalCharge] = []
    advances_rows: list[FarmerAdvance] = []
    today = date.today()

    trx_specs = [
        ("income", "Vente local", 2250000),
        ("income", "Encaissement facture", 1540000),
        ("expense", "Logistique transport", 680000),
        ("expense", "Sacs et emballages", 420000),
        ("expense", "Main d'oeuvre tri", 390000),
        ("expense", "Maintenance séchoir", 265000),
    ]
    for idx, (trx_type, label, amount) in enumerate(trx_specs, start=1):
        row = _upsert(
            session,
            TreasuryTransaction,
            {"reference": f"{DEMO_TREASURY_PREFIX}{idx:03d}"},
            {
                "cooperative_id": coop_id,
                "transaction_date": today - timedelta(days=idx * 4),
                "type": TreasuryTransactionType.INCOME if trx_type == "income" else TreasuryTransactionType.EXPENSE,
                "category": "Commercialisation" if trx_type == "income" else "Opérations",
                "label": label,
                "amount_fcfa": float(amount),
                "note": f"{DEMO_TAG} synthetic treasury",
                "status": TreasuryTransactionStatus.RECORDED,
                "source_type": "demo_seed",
                "source_id": None,
                "farmer_id": members[idx % len(members)].id if trx_type == "expense" and idx % 2 else None,
            },
            counters,
        )
        treasury_rows.append(row)

    charge_types = ["logistique", "emballage", "énergie", "main_oeuvre", "qualité", "transport"]
    for idx in range(1, 25):
        member = members[idx % len(members)]
        parcel = parcels[idx % len(parcels)] if parcels else None
        pre = preharvest_steps[idx % len(preharvest_steps)] if preharvest_steps else None
        batch = batches[idx % len(batches)] if batches else None
        charge = _upsert(
            session,
            GlobalCharge,
            {
                "cooperative_id": coop_id,
                "member_id": member.id,
                "label": f"{DEMO_TAG} charge {idx:03d}",
                "date": today - timedelta(days=(idx * 3) % 90),
            },
            {
                "parcel_id": parcel.id if parcel else None,
                "pre_harvest_step_id": pre.id if pre else None,
                "batch_id": batch.id if batch else None,
                "process_step_id": None,
                "charge_type": charge_types[idx % len(charge_types)],
                "amount_fcfa": float(18000 + (idx % 7) * 5300),
                "notes": f"{DEMO_TAG} synthetic charge",
                "source_type": "demo_seed",
                "treasury_transaction_id": None,
            },
            counters,
        )
        charges_rows.append(charge)

    for idx in range(1, 16):
        member = members[idx % len(members)]
        adv = _upsert(
            session,
            FarmerAdvance,
            {
                "cooperative_id": coop_id,
                "farmer_id": member.id,
                "advance_date": today - timedelta(days=idx * 5),
                "reason": f"{DEMO_TAG} avance intrants {idx:02d}",
            },
            {
                "amount_fcfa": float(45000 + (idx % 6) * 17000),
                "note": f"{DEMO_TAG} synthetic farmer advance",
                "status": FarmerAdvanceStatus.ACTIVE if idx % 4 else FarmerAdvanceStatus.CANCELLED,
                "treasury_transaction_id": None,
            },
            counters,
        )
        advances_rows.append(adv)
    session.flush()
    return treasury_rows, charges_rows, advances_rows


def _seed_ml_logs(
    session: Session,
    *,
    batches: list[Batch],
    counters: dict[str, dict[str, int]],
) -> tuple[list[MLPredictionLog], list[MLRecommendationLog], list[RecommendationFeedbackLog]]:
    predictions: list[MLPredictionLog] = []
    rec_logs: list[MLRecommendationLog] = []
    feedback_logs: list[RecommendationFeedbackLog] = []
    for idx, batch in enumerate(batches[:12], start=1):
        product_name = batch.product.name if batch.product else ""
        critical_stage = ["Nettoyage", "Séchage", "Tri", "Emballage"][idx % 4]
        loss_pct = 6.0 + (idx % 7) * 2.4
        risk = RiskLevel.HIGH if loss_pct > 16 else RiskLevel.MEDIUM if loss_pct > 10 else RiskLevel.LOW
        snapshot = {"demo_tag": DEMO_TAG, "batch_code": batch.code, "idx": idx}
        pred = session.scalars(
            select(MLPredictionLog).where(
                MLPredictionLog.batch_id == batch.id,
                MLPredictionLog.model_version == DEMO_MODEL_VERSION,
            )
        ).first()
        payload = {
            "batch_id": batch.id,
            "model_version": DEMO_MODEL_VERSION,
            "product": product_name,
            "critical_stage": critical_stage,
            "predicted_loss_pct": round(loss_pct, 2),
            "expected_efficiency_pct": round(max(0.0, 100.0 - loss_pct), 2),
            "risk_level": risk,
            "anomaly_score": round(min(0.95, loss_pct / 28.0), 3),
            "is_anomalous": risk == RiskLevel.HIGH,
            "input_snapshot": snapshot,
            "output_snapshot": {"demo_tag": DEMO_TAG, "note": "synthetic prediction"},
            "created_at": datetime.now(UTC) - timedelta(days=idx),
        }
        if pred is None:
            pred = MLPredictionLog(**payload)
            session.add(pred)
            counters[MLPredictionLog.__tablename__]["created"] += 1
        else:
            for key, value in payload.items():
                setattr(pred, key, value)
            counters[MLPredictionLog.__tablename__]["updated"] += 1
        predictions.append(pred)

        rec = session.scalars(
            select(MLRecommendationLog).where(MLRecommendationLog.batch_id == batch.id)
        ).first()
        rec_payload = {
            "batch_id": batch.id,
            "structured_recommendation": {
                "demo_tag": DEMO_TAG,
                "priority": "high" if risk == RiskLevel.HIGH else "medium",
                "action": "Renforcer contrôle humidité" if critical_stage == "Séchage" else "Renforcer tri qualité",
            },
            "llm_explanation": f"{DEMO_TAG} recommandation ML synthétique lot {batch.code}",
            "created_at": datetime.now(UTC) - timedelta(days=idx),
        }
        if rec is None:
            rec = MLRecommendationLog(**rec_payload)
            session.add(rec)
            counters[MLRecommendationLog.__tablename__]["created"] += 1
        else:
            for key, value in rec_payload.items():
                setattr(rec, key, value)
            counters[MLRecommendationLog.__tablename__]["updated"] += 1
        session.flush()
        rec_logs.append(rec)

        feedback = session.scalars(
            select(RecommendationFeedbackLog).where(
                RecommendationFeedbackLog.recommendation_log_id == rec.id,
                RecommendationFeedbackLog.batch_id == batch.id,
            )
        ).first()
        fb_payload = {
            "recommendation_log_id": rec.id,
            "batch_id": batch.id,
            "stage": critical_stage,
            "context_snapshot": {"demo_tag": DEMO_TAG, "batch": batch.code},
            "recommendation_snapshot": {"demo_tag": DEMO_TAG, "action": rec_payload["structured_recommendation"]["action"]},
            "shown_at": datetime.now(UTC) - timedelta(days=idx - 1),
            "accepted": idx % 4 != 0,
            "executed": idx % 5 != 0,
            "outcome_window_hours": 48,
            "outcome_recorded_at": datetime.now(UTC) if idx % 2 == 0 else None,
            "loss_before": round(loss_pct + 2.0, 2),
            "loss_after": round(max(0.0, loss_pct - 1.3), 2),
            "delta_loss": round(-1.3, 2),
            "operator_reason": f"{DEMO_TAG} feedback synthétique",
            "outcome_label": "improved" if idx % 3 else "neutral",
            "confidence_score": round(0.52 + (idx % 4) * 0.1, 3),
            "confidence_bucket": "medium" if idx % 2 else "high",
            "harmful_probability": round(0.05 + (idx % 4) * 0.03, 3),
            "manual_review_required": idx % 6 == 0,
            "is_holdout": idx % 7 == 0,
            "model_version": DEMO_MODEL_VERSION,
            "rating": 3 + (idx % 2),
            "comment": f"{DEMO_TAG} avis opérateur",
            "created_at": datetime.now(UTC) - timedelta(days=idx - 1),
        }
        if feedback is None:
            feedback = RecommendationFeedbackLog(**fb_payload)
            session.add(feedback)
            counters[RecommendationFeedbackLog.__tablename__]["created"] += 1
        else:
            for key, value in fb_payload.items():
                setattr(feedback, key, value)
            counters[RecommendationFeedbackLog.__tablename__]["updated"] += 1
        feedback_logs.append(feedback)

    session.flush()
    return predictions, rec_logs, feedback_logs


def _seed_reference_knowledge(session: Session, *, counters: dict[str, dict[str, int]]) -> tuple[list[KnowledgeChunk], list[ReferenceMetric]]:
    knowledge_specs = [
        ("Mangue", "Séchage", "Contrôler humidité finale < 15% et homogénéiser la circulation d'air pour limiter les pertes."),
        ("Mangue", "Tri", "Renforcer tri par maturité et retirer lots contaminés pour éviter propagation."),
        ("Arachide", "Stockage", "Maintenir taux d'humidité bas et ventilation pour réduire moisissures."),
        ("Mil", "Séchage", "Privilégier séchage progressif avec contrôle journalier du poids."),
        ("Bissap", "Tri", "Nettoyage et tri visuel améliorent la qualité marchande."),
        ("Multi-produit", "Emballage", "Utiliser emballages respirants adaptés à chaque produit."),
        ("Multi-produit", "Humidité", "Mettre en place check-list humidité avant stockage."),
        ("Multi-produit", "Prévention pertes", "Appliquer SOP post-récolte avec suivi des écarts."),
    ]
    chunks: list[KnowledgeChunk] = []
    metrics: list[ReferenceMetric] = []
    for idx, (crop, topic, content) in enumerate(knowledge_specs, start=1):
        source_id = f"{DEMO_SOURCE_PREFIX}KNOW-{idx:03d}"
        chunk = _upsert(
            session,
            KnowledgeChunk,
            {"source_id": source_id, "crop": crop, "topic": topic},
            {
                "source_url": f"https://demo.local/{DEMO_TAG.lower()}/{source_id.lower()}",
                "country": "Senegal",
                "region": "Thies",
                "content": f"[{DEMO_TAG}] {content}",
            },
            counters,
        )
        chunks.append(chunk)
    metric_specs = [
        ("Mangue", "loss_pct_drying", "2025-Q4", 8.5, "%"),
        ("Arachide", "loss_pct_storage", "2025-Q4", 6.2, "%"),
        ("Mil", "loss_pct_drying", "2025-Q4", 7.9, "%"),
        ("Bissap", "loss_pct_sorting", "2025-Q4", 5.4, "%"),
        ("Multi-produit", "target_efficiency_pct", "2025-Q4", 88.0, "%"),
    ]
    for idx, (crop, metric, period, value, unit) in enumerate(metric_specs, start=1):
        source_id = f"{DEMO_SOURCE_PREFIX}MET-{idx:03d}"
        rm = _upsert(
            session,
            ReferenceMetric,
            {"source_id": source_id, "crop": crop, "metric": metric, "period": period},
            {
                "country": "Senegal",
                "region": "Thies",
                "value": float(value),
                "unit": unit,
                "notes": f"[{DEMO_TAG}] synthetic benchmark metric",
            },
            counters,
        )
        metrics.append(rm)
    return chunks, metrics


def main() -> None:
    session = SessionLocal()
    counters: dict[str, dict[str, int]] = defaultdict(lambda: {"created": 0, "updated": 0, "deleted": 0})
    try:
        manager, coop = _ensure_manager_and_coop(session)
        products = _seed_products(session, coop_id=coop.id, counters=counters)
        members = _seed_members(session, coop_id=coop.id, counters=counters)
        fields, parcels = _seed_fields_and_parcels(session, coop_id=coop.id, members=members, counters=counters)
        pre_steps = _seed_preharvest_steps(session, coop_id=coop.id, manager_id=manager.id, parcels=parcels, counters=counters)
        _seed_inputs(session, coop_id=coop.id, members=members, products=products, fields=fields, counters=counters)
        batches, _ = _seed_batches_and_steps(session, coop_id=coop.id, manager_id=manager.id, products=products, counters=counters)
        _seed_recommendations(session, batches=batches, counters=counters)
        _seed_stocks(session, coop_id=coop.id, products=products, batches=batches, counters=counters)
        _seed_catalog_orders_invoices(session, coop_id=coop.id, products=products, counters=counters)
        _seed_treasury_charges_advances(
            session,
            coop_id=coop.id,
            members=members,
            batches=batches,
            parcels=parcels,
            preharvest_steps=pre_steps,
            counters=counters,
        )
        _seed_ml_logs(session, batches=batches, counters=counters)
        _seed_reference_knowledge(session, counters=counters)

        session.commit()
        print(f"Seed complete for cooperative={coop.name} ({coop.id}) with tag {DEMO_TAG}")
        print("Records created/updated/deleted by table:")
        for table in sorted(counters.keys()):
            payload = counters[table]
            print(
                f"- {table}: created={payload['created']} updated={payload['updated']} deleted={payload['deleted']}"
            )
    finally:
        session.close()


if __name__ == "__main__":
    main()

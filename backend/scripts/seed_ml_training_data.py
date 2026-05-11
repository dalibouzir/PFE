#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys
from typing import Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.models.batch import Batch
from app.models.cooperative import Cooperative
from app.models.enums import BatchStatus, CooperativeStatus, ProcessStepStatus, UserRole, UserStatus
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.stock import Stock
from app.models.user import User


DEMO_COOP_NAME = "Coop Demo ML Seed"
DEMO_MANAGER_EMAIL = "ml-demo-manager@weefarm.local"
DEMO_BATCH_PREFIX = "DEMO-ML-"
DEMO_NOTE_MARKER = "[ML_DEMO_SEED]"
ORDERED_STAGES = ["Nettoyage", "Séchage", "Tri", "Emballage"]
PRODUCTS = ["Mangue", "Arachide", "Mil"]
TARGET_ROW_FLOOR = 500


@dataclass
class SeedContext:
    cooperative: Cooperative
    manager: User
    products: Dict[str, Product]
    stocks: Dict[str, Stock]


def _ensure_demo_cooperative(db: Session) -> Cooperative:
    coop = db.scalar(select(Cooperative).where(Cooperative.name == DEMO_COOP_NAME))
    if coop is None:
        coop = Cooperative(
            name=DEMO_COOP_NAME,
            region="Thies",
            address="Seeded demo cooperative for ML training",
            phone="+221770009999",
            status=CooperativeStatus.ACTIVE,
        )
        db.add(coop)
        db.flush()
    return coop


def _ensure_demo_manager(db: Session, cooperative_id) -> User:
    manager = db.scalar(select(User).where(User.email == DEMO_MANAGER_EMAIL))
    if manager is None:
        manager = User(
            full_name="ML Demo Manager",
            email=DEMO_MANAGER_EMAIL,
            password_hash="not-used-for-login",
            phone="+221770009998",
            role=UserRole.MANAGER,
            status=UserStatus.ACTIVE,
            cooperative_id=cooperative_id,
        )
        db.add(manager)
        db.flush()
    else:
        manager.cooperative_id = cooperative_id
        manager.role = UserRole.MANAGER
        manager.status = UserStatus.ACTIVE
        db.flush()
    return manager


def _ensure_products_and_stocks(db: Session, cooperative_id) -> Tuple[Dict[str, Product], Dict[str, Stock]]:
    product_map: Dict[str, Product] = {}
    stock_map: Dict[str, Stock] = {}

    for product_name in PRODUCTS:
        product = db.scalar(
            select(Product).where(
                Product.cooperative_id == cooperative_id,
                Product.name == product_name,
            )
        )
        if product is None:
            product = Product(
                cooperative_id=cooperative_id,
                name=product_name,
                category="Agri",
                unit="kg",
                quality_grade="A",
            )
            db.add(product)
            db.flush()
        product_map[product_name] = product

        stock = db.scalar(
            select(Stock).where(
                Stock.cooperative_id == cooperative_id,
                Stock.product_id == product.id,
            )
        )
        if stock is None:
            stock = Stock(
                cooperative_id=cooperative_id,
                product_id=product.id,
                quantity=2000.0,
                total_stock_kg=2000.0,
                reserved_in_lots_kg=0.0,
                processed_output_kg=0.0,
                threshold=200.0,
                unit="kg",
            )
            db.add(stock)
            db.flush()
        stock_map[product_name] = stock

    # Controlled stock-pressure scenarios.
    stock_map["Mangue"].quantity = 2500.0
    stock_map["Arachide"].quantity = 900.0
    stock_map["Mil"].quantity = 120.0
    for stock in stock_map.values():
        stock.total_stock_kg = max(stock.total_stock_kg, stock.quantity)
        stock.unit = "kg"
    db.flush()

    return product_map, stock_map


def _ensure_context(db: Session) -> SeedContext:
    cooperative = _ensure_demo_cooperative(db)
    manager = _ensure_demo_manager(db, cooperative.id)
    products, stocks = _ensure_products_and_stocks(db, cooperative.id)
    return SeedContext(
        cooperative=cooperative,
        manager=manager,
        products=products,
        stocks=stocks,
    )


def _loss_for_stage(rng: random.Random, stage: str, scenario: str) -> float:
    if scenario == "low_loss_good_practice":
        table = {
            "Nettoyage": (1.0, 2.8),
            "Séchage": (3.2, 6.0),
            "Tri": (2.0, 5.0),
            "Emballage": (0.5, 2.0),
        }
        lo, hi = table[stage]
        return rng.uniform(lo, hi)

    if scenario == "unexpected_low_drying":
        table = {
            "Nettoyage": (1.4, 3.8),
            "Séchage": (2.8, 5.2),
            "Tri": (3.0, 8.5),
            "Emballage": (0.8, 3.2),
        }
        lo, hi = table[stage]
        return rng.uniform(lo, hi)

    if scenario == "unexpected_high_packaging":
        if stage == "Emballage":
            return rng.uniform(8.0, 16.0)

    if scenario == "noisy_normal":
        table = {
            "Nettoyage": (1.0, 8.0),
            "Séchage": (3.8, 19.5),
            "Tri": (2.5, 18.5),
            "Emballage": (0.7, 10.0),
        }
        lo, hi = table[stage]
        return rng.uniform(lo, hi)

    if stage == "Nettoyage":
        base = rng.uniform(1.0, 5.0)
        if scenario == "process_issue":
            base = rng.uniform(6.5, 13.5)
        return base

    if stage == "Séchage":
        if scenario == "high_drying":
            return rng.uniform(20.0, 34.0)
        if scenario == "medium_drying":
            return rng.uniform(11.5, 17.5)
        return rng.uniform(4.0, 16.0)

    if stage == "Tri":
        if scenario == "high_sorting_rejection" or scenario == "high_sorting":
            return rng.uniform(18.0, 26.0)
        if scenario == "process_issue":
            return rng.uniform(14.0, 22.0)
        if scenario == "medium_sorting":
            return rng.uniform(11.5, 17.5)
        return rng.uniform(3.0, 13.0)

    # Emballage
    if scenario == "process_issue":
        return rng.uniform(10.0, 20.0)
    return rng.uniform(0.5, 4.0)


def _scenario_for_batch(rng: random.Random, idx: int) -> str:
    cycle_idx = idx % 50
    if cycle_idx == 0:
        cycle_idx = 50
    forced = {
        6: "high_drying",
        11: "high_sorting_rejection",
        17: "process_issue",
        24: "medium_drying",
        31: "medium_sorting",
        37: "unexpected_high_packaging",
        43: "unexpected_low_drying",
        49: "noisy_normal",
    }
    if cycle_idx in forced:
        return forced[cycle_idx]

    pick = rng.random()
    if pick < 0.20:
        return "normal"
    if pick < 0.25:
        return "low_loss_good_practice"
    if pick < 0.43:
        return "noisy_normal"
    if pick < 0.65:
        return "medium_drying"
    if pick < 0.80:
        return "medium_sorting"
    if pick < 0.83:
        return "unexpected_low_drying"
    if pick < 0.92:
        return "high_drying"
    if pick < 0.97:
        return "high_sorting"
    if pick < 0.985:
        return "unexpected_high_packaging"
    if pick < 0.993:
        return "high_sorting_rejection"
    return "process_issue"


def _next_demo_batch_index(db: Session) -> int:
    codes = db.scalars(select(Batch.code).where(Batch.code.like(f"{DEMO_BATCH_PREFIX}%"))).all()
    highest = 0
    for code in codes:
        suffix = code[len(DEMO_BATCH_PREFIX):]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return highest + 1


def seed_ml_training_data(
    db: Session,
    target_rows: int = 500,
    random_seed: int = 42,
    demo_only: bool = True,
) -> Dict:
    if not demo_only:
        raise ValueError("For safety, this script requires --demo-only.")
    if target_rows < TARGET_ROW_FLOOR:
        target_rows = TARGET_ROW_FLOOR

    rng = random.Random(random_seed)
    context = _ensure_context(db)
    batches_needed = (target_rows + len(ORDERED_STAGES) - 1) // len(ORDERED_STAGES)

    start_index = _next_demo_batch_index(db)
    base_date = date.today() - timedelta(days=max(240, batches_needed * 3))

    created_batches = 0
    created_steps = 0
    created_batch_codes: List[str] = []
    scenario_counts: Dict[str, int] = {}

    for offset in range(batches_needed):
        batch_index = start_index + offset
        scenario = _scenario_for_batch(rng, batch_index)
        scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1

        product_name = PRODUCTS[offset % len(PRODUCTS)]
        product = context.products[product_name]
        initial_qty = rng.uniform(420.0, 980.0)
        batch_code = f"{DEMO_BATCH_PREFIX}{batch_index:04d}"
        created_batch_codes.append(batch_code)
        creation_date = base_date + timedelta(days=offset * 2)

        batch = Batch(
            cooperative_id=context.cooperative.id,
            product_id=product.id,
            code=batch_code,
            creation_date=creation_date,
            unit="kg",
            ordered_process_steps=list(ORDERED_STAGES),
            initial_qty=round(initial_qty, 3),
            current_qty=round(initial_qty, 3),
            status=BatchStatus.COMPLETED,
            created_by_user_id=context.manager.id,
        )
        db.add(batch)
        db.flush()
        created_batches += 1

        qty_in = float(batch.initial_qty)
        for seq, stage in enumerate(ORDERED_STAGES, start=1):
            loss_pct = _loss_for_stage(rng, stage, scenario)
            qty_out = round(max(0.0, qty_in * (1.0 - loss_pct / 100.0)), 3)
            loss_kg = round(max(0.0, qty_in - qty_out), 3)
            duration_base = {
                "Nettoyage": 95,
                "Séchage": 430,
                "Tri": 130,
                "Emballage": 75,
            }[stage]
            duration_jitter = int(rng.uniform(-15, 25))
            if scenario in {"high_drying", "high_sorting_rejection", "process_issue"}:
                duration_jitter += int(rng.uniform(10, 35))

            step_date = creation_date + timedelta(days=seq - 1)
            step = ProcessStep(
                batch_id=batch.id,
                sequence_order=seq,
                type=stage,
                date=step_date,
                qty_in=round(qty_in, 3),
                qty_out=qty_out,
                waste_qty=loss_kg,
                loss_value=loss_kg,
                loss_unit="kg",
                normalized_loss_value=loss_kg,
                notes=f"{DEMO_NOTE_MARKER} scenario={scenario} stage={stage}",
                status=ProcessStepStatus.COMPLETED,
                executed_at=datetime.combine(step_date, datetime.min.time(), tzinfo=timezone.utc),
                duration_minutes=max(30, duration_base + duration_jitter),
            )
            db.add(step)
            created_steps += 1
            qty_in = qty_out

        batch.current_qty = round(qty_in, 3)

    db.commit()
    return {
        "demo_only": demo_only,
        "cooperative_id": str(context.cooperative.id),
        "created_batches": created_batches,
        "created_process_steps": created_steps,
        "created_batch_codes": created_batch_codes,
        "start_batch_code": created_batch_codes[0] if created_batch_codes else None,
        "end_batch_code": created_batch_codes[-1] if created_batch_codes else None,
        "target_rows": target_rows,
        "scenario_distribution": scenario_counts,
        "batch_code_prefix": DEMO_BATCH_PREFIX,
        "note_marker": DEMO_NOTE_MARKER,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed realistic ML demo training data.")
    parser.add_argument("--target-rows", type=int, default=500, help="Target number of process-step rows to create.")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed.")
    parser.add_argument("--demo-only", action="store_true", help="Required safety mode to avoid touching live-like data.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        summary = seed_ml_training_data(
            db=db,
            target_rows=args.target_rows,
            random_seed=args.seed,
            demo_only=args.demo_only,
        )
    finally:
        db.close()

    print("ML training seed completed.")
    print(summary)


if __name__ == "__main__":
    main()

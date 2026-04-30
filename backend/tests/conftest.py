import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.batch import Batch
from app.models.chat import ChatMessage, ChatSession  # noqa: F401
from app.models.commercial_catalog_product import CommercialCatalogProduct  # noqa: F401
from app.models.commercial_invoice import CommercialInvoice, CommercialInvoiceLine  # noqa: F401
from app.models.commercial_order import CommercialOrder, CommercialOrderLine  # noqa: F401
from app.models.cooperative import Cooperative
from app.models.global_charge import GlobalCharge  # noqa: F401
from app.models.enums import BatchStatus, ProcessStepStatus, UserRole, UserStatus
from app.models.member import Member  # noqa: F401
from app.models.parcel import Parcel  # noqa: F401
from app.models.pre_harvest_step import PreHarvestStep as ParcelPreHarvestStep  # noqa: F401
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.stock import Stock
from app.models.user import User


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = SessionLocal()

    cooperative = Cooperative(
        name="Test Coop",
        region="Thies",
        address="Test address",
        phone="+221770000000",
    )
    session.add(cooperative)
    session.flush()

    product = Product(
        cooperative_id=cooperative.id,
        name="mango",
        category="fruit",
        unit="kg",
        quality_grade="A",
    )
    session.add(product)

    manager = User(
        full_name="Test Manager",
        email="manager@test.local",
        password_hash="hash",
        phone="+221770000001",
        role=UserRole.MANAGER,
        status=UserStatus.ACTIVE,
        cooperative_id=cooperative.id,
    )
    session.add(manager)
    session.flush()

    stock = Stock(
        cooperative_id=cooperative.id,
        product_id=product.id,
        quantity=500.0,
        total_stock_kg=500.0,
        reserved_in_lots_kg=0.0,
        processed_output_kg=0.0,
        threshold=200.0,
        unit="kg",
    )
    session.add(stock)
    session.flush()

    base_date = date.today() - timedelta(days=20)
    for idx in range(3):
        batch = Batch(
            cooperative_id=cooperative.id,
            product_id=product.id,
            code=f"BATCH-{idx + 1:04d}",
            creation_date=base_date + timedelta(days=idx * 2),
            unit="kg",
            ordered_process_steps=["cleaning", "drying", "sorting", "packaging"],
            initial_qty=600.0,
            current_qty=600.0,
            status=BatchStatus.COMPLETED,
            created_by_user_id=manager.id,
        )
        session.add(batch)
        session.flush()

        qty_in = 600.0
        for stage_index, stage in enumerate(["cleaning", "drying", "sorting", "packaging"]):
            loss_rate = 4.0 + stage_index
            qty_out = round(qty_in * (1 - loss_rate / 100), 2)
            step = ProcessStep(
                batch_id=batch.id,
                sequence_order=stage_index + 1,
                type=stage,
                date=batch.creation_date + timedelta(days=stage_index),
                qty_in=qty_in,
                qty_out=qty_out,
                waste_qty=max(qty_in - qty_out, 0.0),
                loss_value=max(qty_in - qty_out, 0.0),
                loss_unit="kg",
                normalized_loss_value=max(qty_in - qty_out, 0.0),
                notes=None,
                status=ProcessStepStatus.COMPLETED,
                executed_at=batch.created_at,
                duration_minutes=90 + stage_index * 20,
            )
            session.add(step)
            qty_in = qty_out
        batch.current_qty = qty_in

    session.commit()

    try:
        yield session
    finally:
        session.close()

import uuid
import os
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.ai_audit import AIChatAuditLog  # noqa: F401
from app.models.batch import Batch
from app.models.chat import ChatMessage, ChatSession  # noqa: F401
from app.models.commercial_catalog_product import CommercialCatalogProduct  # noqa: F401
from app.models.commercial_invoice import CommercialInvoice, CommercialInvoiceLine  # noqa: F401
from app.models.commercial_order import CommercialOrder, CommercialOrderLine  # noqa: F401
from app.models.cooperative import Cooperative
from app.models.global_charge import GlobalCharge  # noqa: F401
from app.models.ml import MLModelRegistry, MLPredictionLog, MLRecommendationLog, MLTrainingRun  # noqa: F401
from app.models.enums import BatchStatus, ProcessStepStatus, UserRole, UserStatus
from app.models.member import Member  # noqa: F401
from app.models.parcel import Parcel  # noqa: F401
from app.models.pre_harvest_step import PreHarvestStep as ParcelPreHarvestStep  # noqa: F401
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.stock import Stock
from app.models.user import User


def pytest_addoption(parser):
    """Add --env option to pytest."""
    parser.addoption(
        "--env",
        action="store",
        default="local_test",
        help="Audit environment mode: local_test or supabase_readonly",
        choices=["local_test", "supabase_readonly"],
    )


def pytest_configure(config):
    """Configure audit mode from pytest option and initialize database if needed."""
    from pathlib import Path
    from app.core.config import settings
    from app.db.session import reset_engine
    
    audit_mode = config.getoption("--env")
    os.environ["AUDIT_MODE"] = audit_mode
    print(f"\n✓ Audit mode set to: {audit_mode}")
    
    # Reset the lazy engine/session globals to ensure clean state for audit mode
    reset_engine()

    # Initialize SQLite database schema for local_test mode
    if audit_mode == "local_test":
        from app.db.base import Base
        backend_dir = Path(__file__).resolve().parents[1]
        sqlite_path = backend_dir / "weefarm.db"
        sqlite_url = f"sqlite:///{sqlite_path}"
        
        try:
            engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
            Base.metadata.create_all(engine)
            print(f"✓ SQLite database schema initialized at {sqlite_path}")
            engine.dispose()
        except Exception as e:
            print(f"⚠️  Failed to initialize SQLite schema: {e}")


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


@pytest.fixture(scope="session", autouse=True)
def initialize_test_db():
    """Initialize the test SQLite database with seed data if in local_test mode."""
    from app.core.config import settings
    
    if settings.audit_mode != "local_test":
        return
    
    from pathlib import Path
    backend_dir = Path(__file__).resolve().parents[1]
    sqlite_path = backend_dir / "weefarm.db"
    sqlite_url = f"sqlite:///{sqlite_path}"
    
    try:
        # Create engine and initialize schema
        engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        
        # Create session and seed data
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        session = SessionLocal()
        
        # Check if data already exists
        existing_count = session.query(Batch).count()
        if existing_count == 0:
            # Seed test data
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
            print(f"✓ Test data seeded in {sqlite_path}")
        
        session.close()
        engine.dispose()
    except Exception as e:
        print(f"⚠️  Failed to seed test database: {e}")

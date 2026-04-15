from datetime import date, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_password_hash
from app.crud.user import get_user_by_email
from app.db.session import SessionLocal
from app.models.batch import Batch
from app.models.cooperative import Cooperative
from app.models.enums import CooperativeStatus, UserRole, UserStatus
from app.models.field import Field
from app.models.input import Input
from app.models.member import Member
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.stock import Stock
from app.models.user import User
from app.schemas.batch import BatchCreate
from app.schemas.input import InputCreate
from app.schemas.process_step import ProcessStepCompleteRequest, ProcessStepCreate
from app.services import analytics as analytics_service
from app.services import batches as batch_service
from app.services import inputs as input_service
from app.services import process_steps as process_step_service


COOPERATIVE_NAME = "Cooperative Deggo Thies"


def ensure_admin(db):
    admin = get_user_by_email(db, settings.seed_admin_email)
    if admin is None:
        admin = User(
            full_name="WeeFarm Admin",
            email=settings.seed_admin_email.lower(),
            password_hash=get_password_hash(settings.seed_admin_password),
            phone="+221700000001",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            cooperative_id=None,
        )
        db.add(admin)
    else:
        admin.full_name = "WeeFarm Admin"
        admin.password_hash = get_password_hash(settings.seed_admin_password)
        admin.role = UserRole.ADMIN
        admin.status = UserStatus.ACTIVE
        admin.cooperative_id = None
    db.commit()
    db.refresh(admin)
    return admin


def ensure_cooperative(db):
    cooperative = db.scalar(select(Cooperative).where(Cooperative.name == COOPERATIVE_NAME))
    if cooperative is None:
        cooperative = Cooperative(
            name=COOPERATIVE_NAME,
            region="Thies",
            address="Route de Mbour, Thies",
            phone="+221770000001",
            status=CooperativeStatus.ACTIVE,
        )
        db.add(cooperative)
        db.commit()
        db.refresh(cooperative)
    return cooperative


def ensure_manager(db, cooperative):
    manager = get_user_by_email(db, settings.seed_manager_email)
    if manager is None:
        manager = User(
            full_name="Aissatou Ndiaye",
            email=settings.seed_manager_email.lower(),
            password_hash=get_password_hash(settings.seed_manager_password),
            phone="+221770000002",
            role=UserRole.MANAGER,
            status=UserStatus.ACTIVE,
            cooperative_id=cooperative.id,
        )
        db.add(manager)
    else:
        manager.full_name = "Aissatou Ndiaye"
        manager.password_hash = get_password_hash(settings.seed_manager_password)
        manager.phone = "+221770000002"
        manager.role = UserRole.MANAGER
        manager.status = UserStatus.ACTIVE
        manager.cooperative_id = cooperative.id
    db.commit()
    db.refresh(manager)
    return manager


def ensure_products(db, cooperative):
    products = {
        "Mangue": ("Fruit transforme", "kg", "A"),
        "Arachide": ("Legumineuse", "kg", "A"),
        "Mil": ("Cereale", "kg", "B"),
    }
    result = {}
    for name, (category, unit, grade) in products.items():
        product = db.scalar(
            select(Product).where(Product.cooperative_id == cooperative.id, Product.name == name)
        )
        if product is None:
            product = Product(
                cooperative_id=cooperative.id,
                name=name,
                category=category,
                unit=unit,
                quality_grade=grade,
            )
            db.add(product)
            db.commit()
            db.refresh(product)
        result[name] = product
    return result


def ensure_members(db, cooperative):
    sample_members = [
        ("MBR-001", "Awa Diop", "+221770000101", "Mangue export"),
        ("MBR-002", "Moussa Ndour", "+221770000102", "Sechage"),
        ("MBR-003", "Fatou Fall", "+221770000103", "Tri qualite"),
    ]
    members = {}
    for code, full_name, phone, specialty in sample_members:
        member = db.scalar(
            select(Member).where(Member.cooperative_id == cooperative.id, Member.code == code)
        )
        if member is None:
            member = Member(
                cooperative_id=cooperative.id,
                code=code,
                full_name=full_name,
                phone=phone,
                specialty=specialty,
            )
            db.add(member)
            db.commit()
            db.refresh(member)
        members[code] = member
    return members


def ensure_fields(db, cooperative, members):
    samples = [
        ("MBR-001", "Parcelle Nord - Thies", 3.4, "sableux", "goutte-a-goutte"),
        ("MBR-002", "Parcelle Est - Khombole", 2.1, "argileux", "aspersion"),
        ("MBR-003", "Parcelle Sud - Pout", 4.0, "limoneux", "mixte"),
    ]
    fields = {}
    for member_code, location, area, soil_type, irrigation_type in samples:
        member = members[member_code]
        field = db.scalar(
            select(Field).where(Field.member_id == member.id, Field.location == location)
        )
        if field is None:
            field = Field(
                member_id=member.id,
                cooperative_id=cooperative.id,
                location=location,
                area=area,
                soil_type=soil_type,
                irrigation_type=irrigation_type,
            )
            db.add(field)
            db.commit()
            db.refresh(field)
        fields[member_code] = field
    return fields


def ensure_inputs(db, manager, products, members, fields):
    existing_inputs = db.scalar(
        select(Input).where(Input.cooperative_id == manager.cooperative_id).limit(1)
    )
    if existing_inputs is not None:
        return

    today = date.today()
    sample_inputs = [
        InputCreate(
            member_id=members["MBR-001"].id,
            product_id=products["Mangue"].id,
            field_id=fields["MBR-001"].id,
            date=today - timedelta(days=5),
            quantity=420.0,
            grade="A",
            estimated_value=315000.0,
            status="validated",
        ),
        InputCreate(
            member_id=members["MBR-002"].id,
            product_id=products["Arachide"].id,
            field_id=fields["MBR-002"].id,
            date=today - timedelta(days=4),
            quantity=280.0,
            grade="A",
            estimated_value=196000.0,
            status="validated",
        ),
        InputCreate(
            member_id=members["MBR-003"].id,
            product_id=products["Mil"].id,
            field_id=fields["MBR-003"].id,
            date=today - timedelta(days=3),
            quantity=190.0,
            grade="B",
            estimated_value=85500.0,
            status="quality_control",
        ),
    ]
    for payload in sample_inputs:
        input_service.record_input(db, manager, payload)


def ensure_stock_thresholds(db, cooperative, products):
    thresholds = {
        "Mangue": 180.0,
        "Arachide": 120.0,
        "Mil": 100.0,
    }
    for name, product in products.items():
        stock = db.scalar(
            select(Stock).where(Stock.cooperative_id == cooperative.id, Stock.product_id == product.id)
        )
        if stock is not None:
            stock.threshold = thresholds[name]
            stock.unit = product.unit
    db.commit()


def ensure_batch_and_steps(db, manager, products):
    batch = db.scalar(select(Batch).where(Batch.code == "BATCH-MANG-001"))
    if batch is None:
        batch = batch_service.create_batch(
            db,
            manager,
            BatchCreate(
                product_id=products["Mangue"].id,
                code="BATCH-MANG-001",
                creation_date=date.today() - timedelta(days=2),
                initial_qty=250.0,
            ),
        )

        process_step_service.create_process_step(
            db,
            manager,
            ProcessStepCreate(
                batch_id=batch.id,
                type="cleaning",
                date=date.today() - timedelta(days=2),
                qty_in=250.0,
                qty_out=230.0,
                waste_qty=None,
                notes="Initial cleaning and sorting.",
                status="completed",
                duration_minutes=120,
            ),
        )

        drying_step = process_step_service.create_process_step(
            db,
            manager,
            ProcessStepCreate(
                batch_id=batch.id,
                type="drying",
                date=date.today() - timedelta(days=1),
                qty_in=230.0,
                qty_out=192.0,
                waste_qty=None,
                notes="Controlled tray drying after cleaning.",
                status="pending",
                duration_minutes=420,
            ),
        )
        process_step_service.complete_process_step(
            db,
            manager,
            drying_step.id,
            ProcessStepCompleteRequest(mark_batch_completed=True).mark_batch_completed,
        )
    else:
        cleaning_step = db.scalar(
            select(ProcessStep).where(ProcessStep.batch_id == batch.id, ProcessStep.type == "cleaning")
        )
        if cleaning_step is None:
            process_step_service.create_process_step(
                db,
                manager,
                ProcessStepCreate(
                    batch_id=batch.id,
                    type="cleaning",
                    date=date.today() - timedelta(days=2),
                    qty_in=250.0,
                    qty_out=230.0,
                    waste_qty=None,
                    notes="Initial cleaning and sorting.",
                    status="completed",
                    duration_minutes=120,
                ),
            )

        drying_step = db.scalar(
            select(ProcessStep).where(ProcessStep.batch_id == batch.id, ProcessStep.type == "drying")
        )
        if drying_step is None:
            drying_step = process_step_service.create_process_step(
                db,
                manager,
                ProcessStepCreate(
                    batch_id=batch.id,
                    type="drying",
                    date=date.today() - timedelta(days=1),
                    qty_in=230.0,
                    qty_out=192.0,
                    waste_qty=None,
                    notes="Controlled tray drying after cleaning.",
                    status="pending",
                    duration_minutes=420,
                ),
            )

        if drying_step.status.value not in ("completed", "flagged"):
            process_step_service.complete_process_step(
                db,
                manager,
                drying_step.id,
                ProcessStepCompleteRequest(mark_batch_completed=True).mark_batch_completed,
            )
    analytics_service.generate_recommendation(db, batch.id)
    db.commit()


def run_seed():
    db = SessionLocal()
    try:
        admin = ensure_admin(db)
        cooperative = ensure_cooperative(db)
        manager = ensure_manager(db, cooperative)
        products = ensure_products(db, cooperative)
        members = ensure_members(db, cooperative)
        fields = ensure_fields(db, cooperative, members)
        ensure_inputs(db, manager, products, members, fields)
        ensure_stock_thresholds(db, cooperative, products)
        ensure_batch_and_steps(db, manager, products)
        print("Seed completed successfully.")
        print(f"Admin: {admin.email} / {settings.seed_admin_password}")
        print(f"Manager: {manager.email} / {settings.seed_manager_password}")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()

from datetime import date

import pytest
from sqlalchemy import select

from app.models.enums import InputStatus
from app.models.member import Member
from app.models.parcel import Parcel
from app.models.stock_movement import StockMovement
from app.models.enums import UserRole
from app.models.product import Product
from app.models.stock import Stock
from app.models.user import User
from app.schemas.batch import BatchCreate, BatchStartPostHarvestRequest, BatchStatusUpdate
from app.schemas.input import InputCreate
from app.schemas.process_step import ProcessStepCreate, ProcessStepUpdate
from app.schemas.stock import StockCreate
from app.schemas.stock_movement import ManualStockMovementCreate
from app.services import batches as batch_service
from app.services import inputs as inputs_service
from app.services import process_steps as process_step_service
from app.services import stock_movements as stock_movement_service
from app.services import stocks as stock_service
from app.utils.exceptions import ValidationError


def _manager_and_product(db_session):
    manager = db_session.scalar(select(User).where(User.role == UserRole.MANAGER))
    assert manager is not None
    product = db_session.scalar(select(Product).where(Product.cooperative_id == manager.cooperative_id))
    assert product is not None
    stock = db_session.scalar(
        select(Stock).where(Stock.cooperative_id == manager.cooperative_id, Stock.product_id == product.id)
    )
    assert stock is not None
    return manager, product, stock


def _create_batch(db_session, manager, product, initial_qty: float, unit: str = "kg", steps=None):
    if steps is None:
        steps = ["tri", "emballage"]
    payload = BatchCreate(
        product_id=product.id,
        creation_date=date.today(),
        initial_qty=initial_qty,
        unit=unit,
        process_steps=steps,
    )
    return batch_service.create_batch(db_session, manager, payload)


def test_create_lot_reserves_available_stock(db_session):
    manager, product, stock = _manager_and_product(db_session)
    stock.total_stock_kg = 500.0
    stock.reserved_in_lots_kg = 0.0
    stock.quantity = 500.0
    db_session.commit()

    batch = _create_batch(db_session, manager, product, initial_qty=100.0, unit="kg", steps=["tri", "emballage"])

    updated_stock = db_session.scalar(select(Stock).where(Stock.id == stock.id))
    assert updated_stock is not None
    assert updated_stock.reserved_in_lots_kg == pytest.approx(100.0)
    assert updated_stock.quantity == pytest.approx(400.0)
    assert batch.initial_qty == pytest.approx(100.0)
    assert batch.current_qty == pytest.approx(100.0)
    assert batch.ordered_process_steps == ["tri", "emballage"]
    assert batch.code.startswith("LOT-MANG-")


def test_reject_lot_creation_when_requested_qty_exceeds_available(db_session):
    manager, product, stock = _manager_and_product(db_session)
    stock.total_stock_kg = 200.0
    stock.reserved_in_lots_kg = 0.0
    stock.quantity = 200.0
    db_session.commit()

    with pytest.raises(ValidationError, match="superieure au stock disponible"):
        _create_batch(db_session, manager, product, initial_qty=201.0, unit="kg")


def test_auto_generated_reference_is_incremental(db_session):
    manager, product, stock = _manager_and_product(db_session)
    stock.total_stock_kg = 600.0
    stock.reserved_in_lots_kg = 0.0
    stock.quantity = 600.0
    db_session.commit()

    first = _create_batch(db_session, manager, product, initial_qty=100.0)
    second = _create_batch(db_session, manager, product, initial_qty=120.0)

    first_num = int(first.code.rsplit("-", 1)[-1])
    second_num = int(second.code.rsplit("-", 1)[-1])
    assert second_num == first_num + 1


def test_post_harvest_lot_creation_uses_selected_grade_bucket(db_session):
    manager, product, stock = _manager_and_product(db_session)
    stock.total_stock_kg = 0.0
    stock.reserved_in_lots_kg = 0.0
    stock.quantity = 0.0

    grade_a = Stock(
        cooperative_id=manager.cooperative_id,
        product_id=product.id,
        grade="A",
        quantity=100.0,
        total_stock_kg=100.0,
        reserved_in_lots_kg=0.0,
        processed_output_kg=0.0,
        threshold=0.0,
        unit="kg",
    )
    grade_b = Stock(
        cooperative_id=manager.cooperative_id,
        product_id=product.id,
        grade="B",
        quantity=80.0,
        total_stock_kg=80.0,
        reserved_in_lots_kg=0.0,
        processed_output_kg=0.0,
        threshold=0.0,
        unit="kg",
    )
    db_session.add_all([grade_a, grade_b])
    db_session.commit()

    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            creation_date=date.today(),
            initial_qty=40.0,
            unit="kg",
            grade="A",
            process_steps=["tri", "emballage"],
        ),
    )
    started = batch_service.start_postharvest(
        db_session,
        manager,
        batch.id,
        payload=BatchStartPostHarvestRequest(product_id=product.id, grade="A", quantity_kg=40.0),
    )

    db_session.refresh(grade_a)
    db_session.refresh(grade_b)
    assert started.postharvest_started_at is not None
    assert grade_a.reserved_in_lots_kg == pytest.approx(40.0)
    assert grade_a.quantity == pytest.approx(60.0)
    assert grade_b.reserved_in_lots_kg == pytest.approx(0.0)


def test_final_post_harvest_step_completes_selected_grade_bucket(db_session):
    manager, product, stock = _manager_and_product(db_session)
    stock.total_stock_kg = 0.0
    stock.reserved_in_lots_kg = 0.0
    stock.quantity = 0.0

    grade_a = Stock(
        cooperative_id=manager.cooperative_id,
        product_id=product.id,
        grade="A",
        quantity=100.0,
        total_stock_kg=100.0,
        reserved_in_lots_kg=0.0,
        processed_output_kg=0.0,
        threshold=0.0,
        unit="kg",
    )
    grade_b = Stock(
        cooperative_id=manager.cooperative_id,
        product_id=product.id,
        grade="B",
        quantity=80.0,
        total_stock_kg=80.0,
        reserved_in_lots_kg=0.0,
        processed_output_kg=0.0,
        threshold=0.0,
        unit="kg",
    )
    db_session.add_all([grade_a, grade_b])
    db_session.commit()

    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            creation_date=date.today(),
            initial_qty=40.0,
            unit="kg",
            grade="A",
            process_steps=["tri", "emballage"],
        ),
    )
    batch_service.start_postharvest(
        db_session,
        manager,
        batch.id,
        payload=BatchStartPostHarvestRequest(product_id=product.id, grade="A", quantity_kg=40.0),
    )
    process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(batch_id=batch.id, type="tri", date=date.today(), loss_value=5.0, loss_unit="kg"),
    )
    process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(batch_id=batch.id, type="emballage", date=date.today(), loss_value=3.0, loss_unit="kg"),
    )

    completed = batch_service.require_batch(db_session, manager, batch.id, with_steps=True)
    db_session.refresh(grade_a)
    db_session.refresh(grade_b)
    assert completed.status.value == "completed"
    assert completed.current_qty == pytest.approx(32.0)
    assert grade_a.total_stock_kg == pytest.approx(92.0)
    assert grade_a.reserved_in_lots_kg == pytest.approx(0.0)
    assert grade_a.quantity == pytest.approx(92.0)
    assert grade_a.processed_output_kg == pytest.approx(32.0)
    assert grade_b.reserved_in_lots_kg == pytest.approx(0.0)
    assert grade_b.processed_output_kg == pytest.approx(0.0)


def test_step_execution_propagates_quantities_and_converts_units(db_session):
    manager, product, stock = _manager_and_product(db_session)
    stock.total_stock_kg = 3000.0
    stock.reserved_in_lots_kg = 0.0
    stock.quantity = 3000.0
    db_session.commit()

    batch = _create_batch(db_session, manager, product, initial_qty=1.0, unit="ton", steps=["tri", "emballage"])
    assert batch.initial_qty == pytest.approx(1000.0)

    step1 = process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(
            batch_id=batch.id,
            type="tri",
            date=date.today(),
            loss_value=0.1,
            loss_unit="ton",
            notes="tri perte",
        ),
    )
    assert step1.qty_in == pytest.approx(1000.0)
    assert step1.normalized_loss_value == pytest.approx(100.0)
    assert step1.qty_out == pytest.approx(900.0)

    step2 = process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(
            batch_id=batch.id,
            type="emballage",
            date=date.today(),
            loss_value=50.0,
            loss_unit="kg",
            notes="emballage perte",
        ),
    )
    assert step2.qty_in == pytest.approx(900.0)
    assert step2.qty_out == pytest.approx(850.0)

    refreshed_batch = batch_service.require_batch(db_session, manager, batch.id, with_steps=True)
    assert refreshed_batch.current_qty == pytest.approx(850.0)


def test_lot_status_auto_updates_from_step_progress(db_session):
    manager, product, stock = _manager_and_product(db_session)
    stock.total_stock_kg = 1000.0
    stock.reserved_in_lots_kg = 0.0
    stock.processed_output_kg = 0.0
    stock.quantity = 1000.0
    db_session.commit()

    batch = _create_batch(db_session, manager, product, initial_qty=100.0, unit="kg", steps=["tri", "emballage"])
    assert batch.status.value == "created"

    process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(batch_id=batch.id, type="tri", date=date.today(), loss_value=10.0, loss_unit="kg"),
    )
    in_progress = batch_service.require_batch(db_session, manager, batch.id, with_steps=True)
    assert in_progress.status.value == "in_progress"

    process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(batch_id=batch.id, type="emballage", date=date.today(), loss_value=5.0, loss_unit="kg"),
    )
    completed = batch_service.require_batch(db_session, manager, batch.id, with_steps=True)
    assert completed.status.value == "completed"

    updated_stock = db_session.scalar(select(Stock).where(Stock.id == stock.id))
    assert updated_stock is not None
    assert updated_stock.processed_output_kg == pytest.approx(completed.current_qty)


def test_reject_step_when_loss_exceeds_input(db_session):
    manager, product, stock = _manager_and_product(db_session)
    stock.total_stock_kg = 600.0
    stock.reserved_in_lots_kg = 0.0
    stock.quantity = 600.0
    db_session.commit()

    batch = _create_batch(db_session, manager, product, initial_qty=100.0, unit="kg", steps=["tri"])

    with pytest.raises(ValidationError, match="Perte invalide"):
        process_step_service.create_process_step(
            db_session,
            manager,
            ProcessStepCreate(
                batch_id=batch.id,
                type="tri",
                date=date.today(),
                loss_value=0.2,
                loss_unit="ton",
            ),
        )


def test_reject_step_out_of_order(db_session):
    manager, product, stock = _manager_and_product(db_session)
    stock.total_stock_kg = 600.0
    stock.reserved_in_lots_kg = 0.0
    stock.quantity = 600.0
    db_session.commit()

    batch = _create_batch(db_session, manager, product, initial_qty=100.0, unit="kg", steps=["tri", "sechage"])

    with pytest.raises(ValidationError, match="ne peut pas etre executee"):
        process_step_service.create_process_step(
            db_session,
            manager,
            ProcessStepCreate(
                batch_id=batch.id,
                type="sechage",
                date=date.today(),
                loss_value=5.0,
                loss_unit="kg",
            ),
        )


def test_non_latest_step_update_is_blocked(db_session):
    manager, product, stock = _manager_and_product(db_session)
    stock.total_stock_kg = 800.0
    stock.reserved_in_lots_kg = 0.0
    stock.quantity = 800.0
    db_session.commit()

    batch = _create_batch(db_session, manager, product, initial_qty=200.0, unit="kg", steps=["tri", "emballage"])
    step1 = process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(batch_id=batch.id, type="tri", date=date.today(), loss_value=10.0, loss_unit="kg"),
    )
    process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(batch_id=batch.id, type="emballage", date=date.today(), loss_value=5.0, loss_unit="kg"),
    )

    with pytest.raises(ValidationError, match="locked|completed or archived batch"):
        process_step_service.update_process_step(
            db_session,
            manager,
            step1.id,
            ProcessStepUpdate(loss_value=2.0, loss_unit="kg"),
        )


def test_manual_stock_adjustment_is_blocked(db_session):
    manager, _product, stock = _manager_and_product(db_session)

    with pytest.raises(ValidationError, match="Manual stock"):
        stock_service.adjust_stock(db_session, manager, stock.id, amount=10.0, increase=True)


def test_create_stock_is_blocked_for_manual_creation(db_session):
    manager, _product, _stock = _manager_and_product(db_session)

    new_product = Product(
        cooperative_id=manager.cooperative_id,
        name="Sesame",
        category="grain",
        unit="kg",
        quality_grade="A",
    )
    db_session.add(new_product)
    db_session.commit()
    db_session.refresh(new_product)

    with pytest.raises(ValidationError, match="Creation manuelle de stock desactivee"):
        stock_service.create_stock(
            db_session,
            manager,
            StockCreate(product_id=new_product.id, quantity=0.0, threshold=20.0, unit="kg"),
        )


def test_manual_batch_status_update_is_blocked(db_session):
    manager, product, stock = _manager_and_product(db_session)
    stock.total_stock_kg = 300.0
    stock.reserved_in_lots_kg = 0.0
    stock.quantity = 300.0
    db_session.commit()

    batch = _create_batch(db_session, manager, product, initial_qty=50.0, unit="kg", steps=["tri"])

    with pytest.raises(ValidationError, match="calcule automatiquement"):
        batch_service.update_batch_status(
            db_session,
            manager,
            batch.id,
            BatchStatusUpdate(status="completed"),
        )


def test_linked_collecte_movement_has_linked_lot_traceability(db_session):
    manager, product, stock = _manager_and_product(db_session)
    stock.total_stock_kg = 2000.0
    stock.reserved_in_lots_kg = 0.0
    stock.quantity = 2000.0
    db_session.commit()

    member = db_session.scalar(select(Member).where(Member.cooperative_id == manager.cooperative_id))
    parcel = db_session.scalar(select(Parcel).where(Parcel.cooperative_id == manager.cooperative_id))
    if member is None:
        member = Member(
            cooperative_id=manager.cooperative_id,
            code="MBR-TST-001",
            full_name="Test Producer",
            phone="+221700000000",
            main_product=product.name,
        )
        db_session.add(member)
        db_session.flush()
    if parcel is None:
        parcel = Parcel(
            cooperative_id=manager.cooperative_id,
            member_id=member.id,
            name="Parcelle Test",
            surface_ha=1.0,
            main_culture=product.name,
        )
        db_session.add(parcel)
        db_session.flush()
    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1.0,
            unit="kg",
            process_steps=["tri"],
            surface_ha=1,
            expected_yield_kg_per_ha=1200,
            expected_losses_kg=0,
            estimated_charge_fcfa=1000,
        ),
    )
    batch_service.complete_preharvest(db_session, manager, batch.id)
    collecte = inputs_service.record_input(
        db_session,
        manager,
        InputCreate(
            member_id=member.id,
            product_id=product.id,
            batch_id=batch.id,
            date=date.today(),
            quantity=250,
            grade="A",
            status=InputStatus.PENDING.value,
            source_type="manual",
        ),
    )
    assert collecte.collecte_reference is not None
    assert collecte.collecte_reference.startswith("COL-MANG-")

    movements = stock_movement_service.list_stock_movements(db_session, manager)
    linked = next(item for item in movements if item.source == "lot_linked_collecte")
    assert linked.traceability_status == "linked_lot"
    assert linked.grade == "A"
    assert linked.batch_reference == batch.code
    assert linked.collecte_reference == collecte.collecte_reference
    assert linked.movement_reference.startswith("MVT-IN-")


def test_post_harvest_loss_movement_keeps_batch_and_step_reference(db_session):
    manager, product, stock = _manager_and_product(db_session)
    stock.total_stock_kg = 1500.0
    stock.reserved_in_lots_kg = 0.0
    stock.quantity = 1500.0
    db_session.commit()

    batch = _create_batch(db_session, manager, product, initial_qty=100.0, unit="kg", steps=["tri"])
    step = process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(batch_id=batch.id, type="tri", date=date.today(), loss_value=5.0, loss_unit="kg"),
    )
    movement = db_session.scalar(
        select(StockMovement).where(StockMovement.idempotency_key == f"step:{step.id}:loss")
    )
    assert movement is not None
    assert movement.batch_id == batch.id
    assert movement.process_step_id == step.id

    movements = stock_movement_service.list_stock_movements(db_session, manager)
    row = next(item for item in movements if item.id == movement.id)
    assert row.traceability_status == "linked_lot"


def test_missing_or_legacy_lot_traceability_statuses(db_session):
    manager, product, stock = _manager_and_product(db_session)
    stock.total_stock_kg = 1000.0
    stock.reserved_in_lots_kg = 0.0
    stock.quantity = 1000.0
    db_session.commit()

    missing = StockMovement(
        cooperative_id=manager.cooperative_id,
        product_id=product.id,
        batch_id=None,
        input_id=None,
        workflow_step_id=None,
        movement_type="in",
        action_type="manual",
        source="manual",
        quantity_kg=10.0,
        movement_date=date.today(),
        idempotency_key="test:missing-lot",
    )
    legacy = StockMovement(
        cooperative_id=manager.cooperative_id,
        product_id=product.id,
        batch_id=None,
        input_id=None,
        workflow_step_id=None,
        movement_type="out",
        action_type="perte",
        source="post_harvest_step",
        quantity_kg=3.0,
        movement_date=date.today(),
        idempotency_key="test:legacy-unlinked",
    )
    db_session.add_all([missing, legacy])
    db_session.commit()

    movements = stock_movement_service.list_stock_movements(db_session, manager)
    by_key = {m.idempotency_key: m for m in movements}
    assert by_key["test:missing-lot"].traceability_status == "missing_lot"
    assert by_key["test:legacy-unlinked"].traceability_status == "legacy_unlinked"
    assert by_key["test:legacy-unlinked"].movement_reference.startswith("MVT-HIST-")


def test_manual_in_movement_increases_selected_grade_stock(db_session):
    manager, product, _stock = _manager_and_product(db_session)
    stock_service.apply_total_stock_delta(db_session, manager.cooperative_id, product, 0, create_if_missing=True, grade="A")
    before = stock_service.get_stock_by_product(db_session, manager.cooperative_id, product.id, "A")
    assert before is not None
    before_total = float(before.total_stock_kg)
    created = stock_movement_service.create_manual_stock_movement(
        db_session,
        manager,
        ManualStockMovementCreate(
            product_id=product.id,
            grade="A",
            movement_type="in",
            quantity_kg=12,
            notes="manual test in",
        ),
    )
    after = stock_service.get_stock_by_product(db_session, manager.cooperative_id, product.id, "A")
    assert after is not None
    assert after.total_stock_kg == pytest.approx(before_total + 12)
    assert created.source == "manual_adjustment"
    assert created.movement_reference.startswith("MVT-MAN-")


def test_manual_out_movement_decreases_selected_grade_stock(db_session):
    manager, product, _stock = _manager_and_product(db_session)
    stock_service.apply_total_stock_delta(db_session, manager.cooperative_id, product, 40, create_if_missing=True, grade="B")
    before = stock_service.get_stock_by_product(db_session, manager.cooperative_id, product.id, "B")
    assert before is not None
    before_total = float(before.total_stock_kg)
    created = stock_movement_service.create_manual_stock_movement(
        db_session,
        manager,
        ManualStockMovementCreate(
            product_id=product.id,
            grade="B",
            movement_type="out",
            quantity_kg=10,
            notes="manual test out",
        ),
    )
    after = stock_service.get_stock_by_product(db_session, manager.cooperative_id, product.id, "B")
    assert after is not None
    assert after.total_stock_kg == pytest.approx(before_total - 10)
    assert created.source == "manual_adjustment"


def test_manual_out_cannot_exceed_available_stock(db_session):
    manager, product, _stock = _manager_and_product(db_session)
    stock_service.apply_total_stock_delta(db_session, manager.cooperative_id, product, 5, create_if_missing=True, grade="C")
    with pytest.raises(ValidationError):
        stock_movement_service.create_manual_stock_movement(
            db_session,
            manager,
            ManualStockMovementCreate(
                product_id=product.id,
                grade="C",
                movement_type="out",
                quantity_kg=9999,
                notes="too much out",
            ),
        )


def test_manual_movement_requires_reason(db_session):
    manager, product, _stock = _manager_and_product(db_session)
    with pytest.raises(Exception):
        ManualStockMovementCreate(
            product_id=product.id,
            grade="A",
            movement_type="in",
            quantity_kg=2,
            notes="",
        )


def test_manual_movement_appears_with_source_manual_adjustment(db_session):
    manager, product, _stock = _manager_and_product(db_session)
    stock_movement_service.create_manual_stock_movement(
        db_session,
        manager,
        ManualStockMovementCreate(
            product_id=product.id,
            grade="A",
            movement_type="in",
            quantity_kg=3,
            notes="manual source check",
        ),
    )
    rows = stock_movement_service.list_stock_movements(db_session, manager, source="manual_adjustment")
    assert any(row.source == "manual_adjustment" for row in rows)

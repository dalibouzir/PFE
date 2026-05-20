from datetime import date

import pytest
from sqlalchemy import select

from app.models.batch import Batch
from app.models.enums import MemberStatus, UserRole
from app.models.input import Input
from app.models.member import Member
from app.models.parcel import Parcel
from app.models.product import Product
from app.models.stock import Stock
from app.models.stock_movement import StockMovement
from app.models.farmer_advance import FarmerAdvance
from app.models.treasury_transaction import TreasuryTransaction
from app.models.user import User
from app.schemas.batch import BatchCreate
from app.schemas.process_step import ProcessStepCreate
from app.schemas.treasury import TreasuryTransactionCreate
from app.services import batches as batch_service
from app.services import inputs as inputs_service
from app.services import process_steps as process_step_service
from app.services import treasury as treasury_service
from app.schemas.input import InputCreate
from app.utils.exceptions import ValidationError
from app.services import stocks as stock_service


def _manager(db_session):
    manager = db_session.scalar(select(User).where(User.role == UserRole.MANAGER))
    assert manager is not None
    return manager


def _member_parcel_product(db_session, manager):
    member = Member(
        cooperative_id=manager.cooperative_id,
        code="FARM-PHASE1",
        full_name="Test Farmer",
        phone="+221770000001",
        status=MemberStatus.ACTIVE,
    )
    db_session.add(member)
    db_session.flush()
    parcel = Parcel(
        cooperative_id=manager.cooperative_id,
        member_id=member.id,
        name="Test Parcel",
        surface_ha=2.0,
        main_culture="mango",
    )
    db_session.add(parcel)
    db_session.flush()
    product = db_session.scalar(select(Product).where(Product.cooperative_id == manager.cooperative_id))
    assert product is not None
    stock = db_session.scalar(select(Stock).where(Stock.cooperative_id == manager.cooperative_id, Stock.product_id == product.id))
    if stock is not None and stock.total_stock_kg < 10000:
        stock.total_stock_kg = 10000
        stock.quantity = 10000
    db_session.commit()
    return member, parcel, product


def test_estimated_quantity_does_not_increase_stock(db_session):
    manager = _manager(db_session)
    member, parcel, product = _member_parcel_product(db_session, manager)
    stock_before = db_session.scalar(select(Stock).where(Stock.cooperative_id == manager.cooperative_id, Stock.product_id == product.id))
    assert stock_before is not None
    before_total = stock_before.total_stock_kg

    created = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1,
            unit="kg",
            process_steps=["sorting"],
            surface_ha=2,
            expected_yield_kg_per_ha=4000,
            expected_losses_kg=500,
            estimated_charge_fcfa=25000,
        ),
    )
    assert created.estimated_qty_kg == pytest.approx(7500)
    stock_after = db_session.scalar(select(Stock).where(Stock.id == stock_before.id))
    assert stock_after is not None
    assert stock_after.total_stock_kg == pytest.approx(before_total)


def test_complete_preharvest_marks_ready_for_collecte_without_creating_stock(db_session):
    manager = _manager(db_session)
    member, parcel, product = _member_parcel_product(db_session, manager)
    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1,
            unit="kg",
            process_steps=["sorting"],
            surface_ha=2,
            expected_yield_kg_per_ha=4000,
            expected_losses_kg=500,
            estimated_charge_fcfa=15000,
        ),
    )
    stock_before = db_session.scalar(select(Stock).where(Stock.cooperative_id == manager.cooperative_id, Stock.product_id == product.id))
    assert stock_before is not None
    total_before = stock_before.total_stock_kg

    batch_service.complete_preharvest(db_session, manager, batch.id)
    batch_service.complete_preharvest(db_session, manager, batch.id)

    refreshed = batch_service.require_batch(db_session, manager, batch.id, with_steps=True)
    assert refreshed.preharvest_completed_at is not None
    assert refreshed.confirmed_weight_kg is None
    serialized = batch_service.serialize_batch(refreshed)
    assert serialized.collecte_created is False
    assert serialized.stock_in_created is False

    inputs = db_session.scalars(select(Input).where(Input.batch_id == batch.id)).all()
    assert len(inputs) == 0
    movements = db_session.scalars(
        select(StockMovement).where(StockMovement.batch_id == batch.id, StockMovement.movement_type == "in")
    ).all()
    assert len(movements) == 0
    stock_after = db_session.scalar(select(Stock).where(Stock.id == stock_before.id))
    assert stock_after is not None
    assert stock_after.total_stock_kg == pytest.approx(total_before)


def test_approve_estimated_charge_creates_farmer_advance_and_treasury_out(db_session):
    manager = _manager(db_session)
    member, parcel, product = _member_parcel_product(db_session, manager)
    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1,
            unit="kg",
            process_steps=["sorting"],
            surface_ha=2,
            expected_yield_kg_per_ha=4000,
            expected_losses_kg=500,
            estimated_charge_fcfa=15000,
        ),
    )

    refreshed = batch_service.approve_estimated_charge(db_session, manager, batch.id)
    assert refreshed.charge_approved_at is not None

    advance = db_session.scalar(
        select(FarmerAdvance).where(
            FarmerAdvance.cooperative_id == manager.cooperative_id,
            FarmerAdvance.batch_id == batch.id,
            FarmerAdvance.source_type == "pre_harvest_charge_approval",
        )
    )
    assert advance is not None
    assert advance.amount_fcfa == pytest.approx(15000)
    assert advance.treasury_transaction_id is not None

    treasury_row = db_session.scalar(
        select(TreasuryTransaction).where(
            TreasuryTransaction.cooperative_id == manager.cooperative_id,
            TreasuryTransaction.id == advance.treasury_transaction_id,
        )
    )
    assert treasury_row is not None
    assert treasury_row.source_type == "farmer_advance"
    assert treasury_row.farmer_id == member.id
    assert treasury_row.amount_fcfa == pytest.approx(15000)

    movements = db_session.scalars(select(StockMovement).where(StockMovement.batch_id == batch.id)).all()
    assert len(movements) == 0


def test_activate_preharvest_is_idempotent_and_does_not_change_stock(db_session):
    manager = _manager(db_session)
    member, parcel, product = _member_parcel_product(db_session, manager)
    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1,
            unit="kg",
            process_steps=["sorting"],
            surface_ha=2,
            expected_yield_kg_per_ha=4000,
            expected_losses_kg=500,
            estimated_charge_fcfa=15000,
        ),
    )
    stock_before = db_session.scalar(select(Stock).where(Stock.cooperative_id == manager.cooperative_id, Stock.product_id == product.id))
    assert stock_before is not None
    total_before = stock_before.total_stock_kg
    movement_count_before = len(
        db_session.scalars(select(StockMovement).where(StockMovement.batch_id == batch.id)).all()
    )

    first = batch_service.activate_preharvest(db_session, manager, batch.id)
    assert first.preharvest_activated_at is not None
    first_marker = first.preharvest_activated_at

    second = batch_service.activate_preharvest(db_session, manager, batch.id)
    assert second.preharvest_activated_at == first_marker

    stock_after = db_session.scalar(select(Stock).where(Stock.id == stock_before.id))
    assert stock_after is not None
    assert stock_after.total_stock_kg == pytest.approx(total_before)
    movement_count_after = len(
        db_session.scalars(select(StockMovement).where(StockMovement.batch_id == batch.id)).all()
    )
    assert movement_count_after == movement_count_before


def test_cannot_activate_completed_preharvest_batch(db_session):
    manager = _manager(db_session)
    member, parcel, product = _member_parcel_product(db_session, manager)
    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1,
            unit="kg",
            process_steps=["sorting"],
            surface_ha=2,
            expected_yield_kg_per_ha=4000,
            expected_losses_kg=500,
            estimated_charge_fcfa=15000,
        ),
    )
    batch_service.complete_preharvest(db_session, manager, batch.id)

    with pytest.raises(ValidationError, match="already completed|Cannot activate pre-harvest"):
        batch_service.activate_preharvest(db_session, manager, batch.id)


def test_preharvest_step_statuses_update_allowed_only_when_active(db_session):
    manager = _manager(db_session)
    member, parcel, product = _member_parcel_product(db_session, manager)
    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1,
            unit="kg",
            process_steps=["sorting", "transport"],
            surface_ha=2,
            expected_yield_kg_per_ha=4000,
            expected_losses_kg=500,
            estimated_charge_fcfa=15000,
        ),
    )
    with pytest.raises(ValidationError, match="in preparation"):
        batch_service.update_preharvest_step_statuses(
            db_session,
            manager,
            batch.id,
            [{"index": 0, "name": "sorting", "status": "in_progress"}],
        )

    activated = batch_service.activate_preharvest(db_session, manager, batch.id)
    assert activated.preharvest_activated_at is not None

    updated = batch_service.update_preharvest_step_statuses(
        db_session,
        manager,
        batch.id,
        [
            {"index": 0, "name": "sorting", "status": "done"},
            {"index": 1, "name": "transport", "status": "done"},
        ],
    )
    assert updated.preharvest_step_statuses is not None
    assert len(updated.preharvest_step_statuses) == 2
    assert updated.preharvest_step_statuses[0]["status"] == "done"

    batch_service.complete_preharvest(db_session, manager, batch.id)
    with pytest.raises(ValidationError, match="ready post-harvest"):
        batch_service.update_preharvest_step_statuses(
            db_session,
            manager,
            batch.id,
            [{"index": 0, "name": "sorting", "status": "done"}],
        )


def test_preharvest_step_statuses_update_does_not_change_stock(db_session):
    manager = _manager(db_session)
    member, parcel, product = _member_parcel_product(db_session, manager)
    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1,
            unit="kg",
            process_steps=["sorting"],
            surface_ha=2,
            expected_yield_kg_per_ha=4000,
            expected_losses_kg=500,
            estimated_charge_fcfa=15000,
        ),
    )
    batch_service.activate_preharvest(db_session, manager, batch.id)
    stock_before = db_session.scalar(select(Stock).where(Stock.cooperative_id == manager.cooperative_id, Stock.product_id == product.id))
    assert stock_before is not None
    total_before = stock_before.total_stock_kg
    movement_before = len(db_session.scalars(select(StockMovement).where(StockMovement.batch_id == batch.id)).all())
    input_before = len(db_session.scalars(select(Input).where(Input.batch_id == batch.id)).all())

    batch_service.update_preharvest_step_statuses(
        db_session,
        manager,
        batch.id,
        [{"index": 0, "name": "sorting", "status": "done"}],
    )

    stock_after = db_session.scalar(select(Stock).where(Stock.id == stock_before.id))
    assert stock_after is not None
    assert stock_after.total_stock_kg == pytest.approx(total_before)
    movement_after = len(db_session.scalars(select(StockMovement).where(StockMovement.batch_id == batch.id)).all())
    input_after = len(db_session.scalars(select(Input).where(Input.batch_id == batch.id)).all())
    assert movement_after == movement_before
    assert input_after == input_before


def test_collecte_grade_creates_distinct_stock_buckets(db_session):
    manager = _manager(db_session)
    member, _parcel, product = _member_parcel_product(db_session, manager)

    grade_a = inputs_service.record_input(
        db_session,
        manager,
        InputCreate(
            member_id=member.id,
            product_id=product.id,
            date=date.today(),
            quantity=120,
            grade="A",
            status="pending",
            source_type="manual",
        ),
    )
    grade_b = inputs_service.record_input(
        db_session,
        manager,
        InputCreate(
            member_id=member.id,
            product_id=product.id,
            date=date.today(),
            quantity=80,
            grade="B",
            status="pending",
            source_type="manual",
        ),
    )

    stock_a = stock_service.get_stock_by_product(db_session, manager.cooperative_id, product.id, "A")
    stock_b = stock_service.get_stock_by_product(db_session, manager.cooperative_id, product.id, "B")
    assert stock_a is not None
    assert stock_b is not None
    assert stock_a.total_stock_kg == pytest.approx(grade_a.quantity)
    assert stock_b.total_stock_kg == pytest.approx(grade_b.quantity)


def test_collecte_linked_movement_persists_input_grade(db_session):
    manager = _manager(db_session)
    member, parcel, product = _member_parcel_product(db_session, manager)
    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1,
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
            quantity=50,
            grade="B",
            status="pending",
            source_type="manual",
        ),
    )

    movement = db_session.scalar(
        select(StockMovement).where(StockMovement.input_id == collecte.id)
    )
    assert movement is not None
    assert movement.grade == "B"


def test_legacy_non_specifie_grade_bucket_is_supported(db_session):
    manager = _manager(db_session)
    member, _parcel, product = _member_parcel_product(db_session, manager)
    stock_before = stock_service.get_stock_by_product(
        db_session, manager.cooperative_id, product.id, "Non spécifié"
    )
    before_total = float(stock_before.total_stock_kg if stock_before is not None else 0.0)
    created = inputs_service.record_input(
        db_session,
        manager,
        InputCreate(
            member_id=member.id,
            product_id=product.id,
            date=date.today(),
            quantity=33,
            grade="Non spécifié",
            status="pending",
            source_type="manual",
        ),
    )

    stock = stock_service.get_stock_by_product(
        db_session, manager.cooperative_id, product.id, "Non spécifié"
    )
    assert stock is not None
    assert stock.grade == "Non spécifié"
    assert stock.total_stock_kg == pytest.approx(before_total + created.quantity)


def test_complete_preharvest_requires_all_persisted_statuses_done_for_active_lot(db_session):
    manager = _manager(db_session)
    member, parcel, product = _member_parcel_product(db_session, manager)
    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1,
            unit="kg",
            process_steps=["sorting", "transport"],
            surface_ha=2,
            expected_yield_kg_per_ha=4000,
            expected_losses_kg=500,
            estimated_charge_fcfa=15000,
        ),
    )
    batch_service.activate_preharvest(db_session, manager, batch.id)
    batch_service.update_preharvest_step_statuses(
        db_session,
        manager,
        batch.id,
        [
            {"index": 0, "name": "sorting", "status": "done"},
            {"index": 1, "name": "transport", "status": "in_progress"},
        ],
    )
    with pytest.raises(ValidationError, match="all active pre-harvest steps are done"):
        batch_service.complete_preharvest(db_session, manager, batch.id)

    batch_service.update_preharvest_step_statuses(
        db_session,
        manager,
        batch.id,
        [
            {"index": 0, "name": "sorting", "status": "done"},
            {"index": 1, "name": "transport", "status": "done"},
        ],
    )
    completed = batch_service.complete_preharvest(db_session, manager, batch.id)
    assert completed.preharvest_completed_at is not None


def test_linked_collecte_creates_stock_in_and_updates_batch_weight(db_session):
    manager = _manager(db_session)
    member, parcel, product = _member_parcel_product(db_session, manager)
    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1,
            unit="kg",
            process_steps=["sorting"],
            surface_ha=2,
            expected_yield_kg_per_ha=4000,
            expected_losses_kg=500,
            estimated_charge_fcfa=15000,
        ),
    )
    stock_before = stock_service.get_stock_by_product(db_session, manager.cooperative_id, product.id, "A")
    total_before = float(stock_before.total_stock_kg if stock_before is not None else 0.0)

    batch_service.complete_preharvest(db_session, manager, batch.id)
    created = inputs_service.record_input(
        db_session,
        manager,
        InputCreate(
            member_id=member.id,
            product_id=product.id,
            batch_id=batch.id,
            date=date.today(),
            quantity=1200,
            grade="A",
            status="pending",
            source_type="manual",
        ),
    )

    assert created.batch_id == batch.id
    assert created.source_type == "lot_linked_collecte"
    assert created.status.value == "validated"
    assert created.collecte_reference is not None
    assert created.collecte_reference.startswith("COL-MANG-")
    batch_after = batch_service.require_batch(db_session, manager, batch.id, with_steps=True)
    assert batch_after.confirmed_weight_kg == pytest.approx(1200)
    assert batch_after.current_qty == pytest.approx(1200)
    serialized = batch_service.serialize_batch(batch_after)
    assert serialized.collecte_created is True
    assert serialized.stock_in_created is True

    movements = db_session.scalars(
        select(StockMovement).where(StockMovement.batch_id == batch.id, StockMovement.movement_type == "in")
    ).all()
    assert len(movements) == 1
    assert movements[0].movement_reference is not None
    assert movements[0].movement_reference.startswith("MVT-IN-")
    stock_after = stock_service.get_stock_by_product(db_session, manager.cooperative_id, product.id, "A")
    assert stock_after is not None
    assert stock_after.total_stock_kg == pytest.approx(total_before + 1200)


def test_duplicate_linked_collecte_for_same_batch_is_rejected(db_session):
    manager = _manager(db_session)
    member, parcel, product = _member_parcel_product(db_session, manager)
    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1,
            unit="kg",
            process_steps=["sorting"],
            surface_ha=2,
            expected_yield_kg_per_ha=4000,
            expected_losses_kg=500,
            estimated_charge_fcfa=15000,
        ),
    )
    batch_service.complete_preharvest(db_session, manager, batch.id)
    inputs_service.record_input(
        db_session,
        manager,
        InputCreate(
            member_id=member.id,
            product_id=product.id,
            batch_id=batch.id,
            date=date.today(),
            quantity=1100,
            grade="A",
            status="validated",
            source_type="lot_linked_collecte",
        ),
    )
    with pytest.raises(ValidationError, match="collecte liée existe déjà"):
        inputs_service.record_input(
            db_session,
            manager,
            InputCreate(
                member_id=member.id,
                product_id=product.id,
                batch_id=batch.id,
                date=date.today(),
                quantity=900,
                grade="A",
                status="validated",
                source_type="lot_linked_collecte",
            ),
        )


def test_postharvest_step_requires_explicit_start(db_session):
    manager = _manager(db_session)
    member, parcel, product = _member_parcel_product(db_session, manager)
    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1,
            unit="kg",
            process_steps=["sorting"],
            surface_ha=2,
            expected_yield_kg_per_ha=4000,
            expected_losses_kg=500,
            estimated_charge_fcfa=15000,
        ),
    )
    batch_service.complete_preharvest(db_session, manager, batch.id)
    inputs_service.record_input(
        db_session,
        manager,
        InputCreate(
            member_id=member.id,
            product_id=product.id,
            batch_id=batch.id,
            date=date.today(),
            quantity=920,
            grade="A",
            status="validated",
            source_type="lot_linked_collecte",
        ),
    )

    with pytest.raises(ValidationError, match="Démarrez Post-récolte"):
        process_step_service.create_process_step(
            db_session,
            manager,
            ProcessStepCreate(
                batch_id=batch.id,
                type="sorting",
                date=date.today(),
                loss_value=10,
                loss_unit="kg",
            ),
        )

    started = batch_service.start_postharvest(db_session, manager, batch.id)
    assert started.postharvest_started_at is not None
    assert started.postharvest_reference is not None

    step = process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(
            batch_id=batch.id,
            type="sorting",
            date=date.today(),
            loss_value=10,
            loss_unit="kg",
        ),
    )
    assert step.sequence_order == 1


def test_delete_linked_collecte_reopens_lot_for_collecte(db_session):
    manager = _manager(db_session)
    member, parcel, product = _member_parcel_product(db_session, manager)
    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1,
            unit="kg",
            process_steps=["sorting"],
            surface_ha=2,
            expected_yield_kg_per_ha=4000,
            expected_losses_kg=500,
            estimated_charge_fcfa=15000,
        ),
    )
    batch_service.complete_preharvest(db_session, manager, batch.id)
    linked = inputs_service.record_input(
        db_session,
        manager,
        InputCreate(
            member_id=member.id,
            product_id=product.id,
            batch_id=batch.id,
            date=date.today(),
            quantity=950,
            grade="A",
            status="validated",
            source_type="lot_linked_collecte",
        ),
    )
    batch_with_collecte = batch_service.require_batch(db_session, manager, batch.id, with_steps=True)
    assert batch_with_collecte.confirmed_weight_kg == pytest.approx(950)
    assert batch_service.serialize_batch(batch_with_collecte).stock_in_created is True

    deleted = inputs_service.delete_input(db_session, manager, linked.id)
    assert deleted["id"] == linked.id

    batch_after_delete = batch_service.require_batch(db_session, manager, batch.id, with_steps=True)
    serialized = batch_service.serialize_batch(batch_after_delete)
    assert batch_after_delete.preharvest_completed_at is not None
    assert batch_after_delete.confirmed_weight_kg is None
    assert batch_after_delete.current_qty == pytest.approx(0.0)
    assert serialized.collecte_created is False
    assert serialized.stock_in_created is False


def test_delete_linked_collecte_blocked_when_postharvest_started(db_session):
    manager = _manager(db_session)
    member, parcel, product = _member_parcel_product(db_session, manager)
    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1,
            unit="kg",
            process_steps=["sorting"],
            surface_ha=2,
            expected_yield_kg_per_ha=4000,
            expected_losses_kg=500,
            estimated_charge_fcfa=15000,
        ),
    )
    batch_service.complete_preharvest(db_session, manager, batch.id)
    linked = inputs_service.record_input(
        db_session,
        manager,
        InputCreate(
            member_id=member.id,
            product_id=product.id,
            batch_id=batch.id,
            date=date.today(),
            quantity=980,
            grade="A",
            status="validated",
            source_type="lot_linked_collecte",
        ),
    )
    batch_service.start_postharvest(db_session, manager, batch.id)

    process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(
            batch_id=batch.id,
            type="sorting",
            date=date.today(),
            loss_value=10,
            loss_unit="kg",
            notes="Demarrage post-recolte",
            duration_minutes=30,
        ),
    )

    with pytest.raises(ValidationError, match="Post-récolte du lot est déjà en cours"):
        inputs_service.delete_input(db_session, manager, linked.id)


def test_independent_collecte_without_batch_still_works(db_session):
    manager = _manager(db_session)
    member, _parcel, product = _member_parcel_product(db_session, manager)
    stock_before = stock_service.get_stock_by_product(db_session, manager.cooperative_id, product.id, "B")
    total_before = float(stock_before.total_stock_kg if stock_before is not None else 0.0)

    created = inputs_service.record_input(
        db_session,
        manager,
        InputCreate(
            member_id=member.id,
            product_id=product.id,
            batch_id=None,
            date=date.today(),
            quantity=350,
            grade="B",
            status="validated",
            source_type="manual",
        ),
    )
    assert created.batch_id is None
    stock_after = stock_service.get_stock_by_product(db_session, manager.cooperative_id, product.id, "B")
    assert stock_after is not None
    assert stock_after.total_stock_kg == pytest.approx(total_before + 350)


def test_stop_preharvest_returns_active_lot_to_preparation_when_execution_not_started(db_session):
    manager = _manager(db_session)
    member, parcel, product = _member_parcel_product(db_session, manager)
    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1,
            unit="kg",
            process_steps=["sorting", "transport"],
            surface_ha=2,
            expected_yield_kg_per_ha=4000,
            expected_losses_kg=500,
            estimated_charge_fcfa=15000,
        ),
    )
    activated = batch_service.activate_preharvest(db_session, manager, batch.id)
    assert activated.preharvest_activated_at is not None

    stock_before = db_session.scalar(
        select(Stock).where(Stock.cooperative_id == manager.cooperative_id, Stock.product_id == product.id)
    )
    assert stock_before is not None
    total_before = stock_before.total_stock_kg
    input_before = len(db_session.scalars(select(Input).where(Input.batch_id == batch.id)).all())
    movement_before = len(db_session.scalars(select(StockMovement).where(StockMovement.batch_id == batch.id)).all())

    stopped = batch_service.stop_preharvest(db_session, manager, batch.id)
    assert stopped.preharvest_activated_at is None
    assert stopped.preharvest_completed_at is None
    assert stopped.confirmed_weight_kg is None

    stock_after = db_session.scalar(select(Stock).where(Stock.id == stock_before.id))
    assert stock_after is not None
    assert stock_after.total_stock_kg == pytest.approx(total_before)
    input_after = len(db_session.scalars(select(Input).where(Input.batch_id == batch.id)).all())
    movement_after = len(db_session.scalars(select(StockMovement).where(StockMovement.batch_id == batch.id)).all())
    assert input_after == input_before
    assert movement_after == movement_before


def test_stop_preharvest_rejected_once_execution_started(db_session):
    manager = _manager(db_session)
    member, parcel, product = _member_parcel_product(db_session, manager)
    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1,
            unit="kg",
            process_steps=["sorting", "transport"],
            surface_ha=2,
            expected_yield_kg_per_ha=4000,
            expected_losses_kg=500,
            estimated_charge_fcfa=15000,
        ),
    )
    batch_service.activate_preharvest(db_session, manager, batch.id)
    batch_service.update_preharvest_step_statuses(
        db_session,
        manager,
        batch.id,
        [
            {"index": 0, "name": "sorting", "status": "in_progress"},
            {"index": 1, "name": "transport", "status": "todo"},
        ],
    )

    with pytest.raises(ValidationError, match="execution has started"):
        batch_service.stop_preharvest(db_session, manager, batch.id)


def test_treasury_create_auto_generates_reference_without_manual_receipt_reference(db_session):
    manager = _manager(db_session)
    created = treasury_service.create_treasury_transaction(
        db_session,
        manager,
        TreasuryTransactionCreate(
            transaction_date=date.today(),
            type="expense",
            category="gestion",
            label="Carburant",
            amount_fcfa=18000,
            note="Achat carburant",
            source_type="manual",
        ),
    )
    assert created.reference.startswith("TRS-")
    assert created.receipt_reference is None


def test_legacy_collecte_without_reference_keeps_batch_serialization_stable(db_session):
    manager = _manager(db_session)
    member, parcel, product = _member_parcel_product(db_session, manager)
    batch = batch_service.create_batch(
        db_session,
        manager,
        BatchCreate(
            product_id=product.id,
            member_id=member.id,
            parcel_id=parcel.id,
            creation_date=date.today(),
            initial_qty=1,
            unit="kg",
            process_steps=["sorting"],
            surface_ha=2,
            expected_yield_kg_per_ha=4000,
            expected_losses_kg=500,
            estimated_charge_fcfa=15000,
        ),
    )
    batch_service.complete_preharvest(db_session, manager, batch.id)
    linked_collecte = inputs_service.record_input(
        db_session,
        manager,
        InputCreate(
            member_id=member.id,
            product_id=product.id,
            batch_id=batch.id,
            date=date.today(),
            quantity=950,
            grade="A",
            status="validated",
            source_type="lot_linked_collecte",
        ),
    )

    linked_collecte.collecte_reference = None
    db_session.commit()
    db_session.refresh(linked_collecte)

    serialized = batch_service.serialize_batch(batch_service.require_batch(db_session, manager, batch.id, with_steps=True))
    assert serialized.collecte_reference is not None
    assert serialized.collecte_reference.startswith("COL-HIST-")

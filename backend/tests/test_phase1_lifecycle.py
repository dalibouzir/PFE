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
from app.models.user import User
from app.schemas.batch import BatchCreate
from app.services import batches as batch_service
from app.utils.exceptions import ValidationError


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


def test_complete_preharvest_creates_single_collecte_and_stock_in(db_session):
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

    batch_service.complete_preharvest(db_session, manager, batch.id, confirmed_weight_kg=7200)
    batch_service.complete_preharvest(db_session, manager, batch.id, confirmed_weight_kg=7200)

    inputs = db_session.scalars(select(Input).where(Input.batch_id == batch.id)).all()
    assert len(inputs) == 1
    movements = db_session.scalars(select(StockMovement).where(StockMovement.batch_id == batch.id, StockMovement.movement_type == "in")).all()
    assert len(movements) == 1
    stock_after = db_session.scalar(select(Stock).where(Stock.id == stock_before.id))
    assert stock_after is not None
    assert stock_after.total_stock_kg == pytest.approx(total_before + 7200)


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
    batch_service.complete_preharvest(db_session, manager, batch.id, confirmed_weight_kg=7200)

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

    batch_service.complete_preharvest(db_session, manager, batch.id, confirmed_weight_kg=7200)
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
        batch_service.complete_preharvest(db_session, manager, batch.id, confirmed_weight_kg=7200)

    batch_service.update_preharvest_step_statuses(
        db_session,
        manager,
        batch.id,
        [
            {"index": 0, "name": "sorting", "status": "done"},
            {"index": 1, "name": "transport", "status": "done"},
        ],
    )
    completed = batch_service.complete_preharvest(db_session, manager, batch.id, confirmed_weight_kg=7200)
    assert completed.preharvest_completed_at is not None


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

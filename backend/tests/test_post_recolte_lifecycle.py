from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.models.cooperative import Cooperative
from app.models.enums import MemberStatus, UserRole, UserStatus
from app.models.member import Member
from app.models.parcel import Parcel
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.user import User
from app.schemas.batch import BatchCreate
from app.schemas.input import InputCreate
from app.schemas.process_step import ProcessStepCompleteRequest, ProcessStepCreate
from app.services import batches as batch_service
from app.services import inputs as inputs_service
from app.services import process_steps as process_step_service
from app.utils.exceptions import NotFoundError, ValidationError


def _manager(db_session):
    manager = db_session.scalar(select(User).where(User.role == UserRole.MANAGER))
    assert manager is not None
    return manager


def _setup_ready_post_recolte_batch(db_session):
    manager = _manager(db_session)
    product = db_session.scalar(select(Product).where(Product.cooperative_id == manager.cooperative_id))
    assert product is not None

    member = Member(
        cooperative_id=manager.cooperative_id,
        code="POSTR-001",
        full_name="Post Recolte Farmer",
        phone="+221770000321",
        status=MemberStatus.ACTIVE,
    )
    db_session.add(member)
    db_session.flush()

    parcel = Parcel(
        cooperative_id=manager.cooperative_id,
        member_id=member.id,
        name="Post Parcel",
        surface_ha=1.8,
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
            initial_qty=1,
            unit="kg",
            process_steps=["nettoyage", "sechage", "tri", "emballage"],
            surface_ha=2,
            expected_yield_kg_per_ha=700,
            expected_losses_kg=10,
            estimated_charge_fcfa=2000,
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
            quantity=1000,
            grade="A",
            status="pending",
            source_type="manual",
        ),
    )
    ready = batch_service.require_batch(db_session, manager, batch.id, with_steps=True)
    return manager, product, ready


def test_ready_lot_exposes_ready_post_recolte_status(db_session):
    manager, _product, batch = _setup_ready_post_recolte_batch(db_session)
    serialized = batch_service.serialize_batch(batch)
    assert serialized.postharvest_status == "ready_post_recolte"
    assert serialized.confirmed_weight_kg == pytest.approx(1000)


def test_start_post_recolte_updates_status(db_session):
    manager, _product, batch = _setup_ready_post_recolte_batch(db_session)
    started = batch_service.start_postharvest(db_session, manager, batch.id)
    assert started.postharvest_started_at is not None
    assert started.status.value == "in_progress"
    assert batch_service.serialize_batch(started).postharvest_status == "in_post_recolte"


def test_complete_step_computes_loss_and_efficiency(db_session):
    manager, _product, batch = _setup_ready_post_recolte_batch(db_session)
    batch_service.start_postharvest(db_session, manager, batch.id)
    step = process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(
            batch_id=batch.id,
            type="nettoyage",
            date=date.today(),
            qty_in=1000,
            loss_unit="kg",
            status="in_progress",
            notes="start",
        ),
    )
    completed = process_step_service.complete_process_step(
        db_session,
        manager,
        step.id,
        ProcessStepCompleteRequest(qty_out=900, loss_unit="kg"),
    )
    assert completed.qty_in == pytest.approx(1000)
    assert completed.qty_out == pytest.approx(900)
    assert completed.normalized_loss_value == pytest.approx(100)


def test_step_output_feeds_next_step_input(db_session):
    manager, _product, batch = _setup_ready_post_recolte_batch(db_session)
    batch_service.start_postharvest(db_session, manager, batch.id)
    step1 = process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(
            batch_id=batch.id,
            type="nettoyage",
            date=date.today(),
            qty_out=920,
            loss_unit="kg",
        ),
    )
    assert step1.qty_out == pytest.approx(920)

    step2 = process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(
            batch_id=batch.id,
            type="sechage",
            date=date.today(),
            qty_out=880,
            loss_unit="kg",
        ),
    )
    assert step2.qty_in == pytest.approx(920)


def test_complete_post_recolte_requires_all_steps_done(db_session):
    manager, _product, batch = _setup_ready_post_recolte_batch(db_session)
    batch_service.start_postharvest(db_session, manager, batch.id)

    with pytest.raises(ValidationError, match="required steps"):
        batch_service.complete_postharvest(db_session, manager, batch.id)

    flow = [
        ("nettoyage", 950),
        ("sechage", 900),
        ("tri", 870),
        ("emballage", 850),
    ]
    for step_type, qty_out in flow:
        process_step_service.create_process_step(
            db_session,
            manager,
            ProcessStepCreate(
                batch_id=batch.id,
                type=step_type,
                date=date.today(),
                qty_out=qty_out,
                loss_unit="kg",
            ),
        )

    completed = batch_service.complete_postharvest(db_session, manager, batch.id)
    assert completed.status.value == "completed"
    assert batch_service.serialize_batch(completed).postharvest_status == "post_recolte_completed"


def test_reject_qty_out_greater_than_qty_in(db_session):
    manager, _product, batch = _setup_ready_post_recolte_batch(db_session)
    batch_service.start_postharvest(db_session, manager, batch.id)
    step = process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(
            batch_id=batch.id,
            type="nettoyage",
            date=date.today(),
            qty_in=1000,
            loss_unit="kg",
            status="in_progress",
        ),
    )

    with pytest.raises(ValidationError, match="qty_out cannot exceed qty_in"):
        process_step_service.complete_process_step(
            db_session,
            manager,
            step.id,
            ProcessStepCompleteRequest(qty_out=1200),
        )


def test_repeated_completion_does_not_duplicate_stock_movements(db_session):
    manager, _product, batch = _setup_ready_post_recolte_batch(db_session)
    batch_service.start_postharvest(db_session, manager, batch.id)
    step = process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(
            batch_id=batch.id,
            type="nettoyage",
            date=date.today(),
            qty_in=1000,
            loss_unit="kg",
            status="in_progress",
        ),
    )

    payload = ProcessStepCompleteRequest(qty_out=930)
    process_step_service.complete_process_step(db_session, manager, step.id, payload)
    process_step_service.complete_process_step(db_session, manager, step.id, payload)

    rows = db_session.scalars(
        select(StockMovement).where(StockMovement.idempotency_key == f"step:{step.id}:loss")
    ).all()
    assert len(rows) == 1



def test_material_balance_endpoint_totals(db_session):
    manager, _product, batch = _setup_ready_post_recolte_batch(db_session)
    batch_service.start_postharvest(db_session, manager, batch.id)
    process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(batch_id=batch.id, type="nettoyage", date=date.today(), qty_out=900, loss_unit="kg"),
    )
    process_step_service.create_process_step(
        db_session,
        manager,
        ProcessStepCreate(batch_id=batch.id, type="sechage", date=date.today(), qty_out=850, loss_unit="kg"),
    )

    balance = batch_service.get_material_balance(db_session, manager, batch.id)
    assert balance.initial_confirmed_qty == pytest.approx(1000)
    assert balance.current_qty == pytest.approx(850)
    assert balance.total_loss_qty == pytest.approx(150)
    assert balance.total_loss_pct == pytest.approx(15)
    assert balance.total_efficiency_pct == pytest.approx(85)
    assert balance.steps_completed == 2
    assert balance.per_stage



def test_cooperative_scoping_enforced_for_material_balance(db_session):
    manager, _product, batch = _setup_ready_post_recolte_batch(db_session)

    other_coop = Cooperative(name="Other Coop", region="Dakar", address="A", phone="+221771000000")
    db_session.add(other_coop)
    db_session.flush()

    outsider = User(
        full_name="Outside",
        email="outside@test.local",
        password_hash="hash",
        role=UserRole.MANAGER,
        status=UserStatus.ACTIVE,
        cooperative_id=other_coop.id,
    )
    db_session.add(outsider)
    db_session.commit()

    with pytest.raises(NotFoundError):
        batch_service.get_material_balance(db_session, outsider, batch.id)

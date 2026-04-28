from datetime import date

import pytest
from sqlalchemy import select

from app.models.product import Product
from app.models.stock import Stock
from app.models.user import User
from app.schemas.input import InputCreate, InputUpdate
from app.schemas.member import MemberCreate
from app.services import inputs as input_service
from app.services import members as member_service
from app.utils.exceptions import ValidationError


def _manager_product_stock(db_session):
    manager = db_session.scalar(select(User).where(User.email == "manager@test.local"))
    assert manager is not None
    product = db_session.scalar(select(Product).where(Product.name == "mango"))
    assert product is not None
    stock = db_session.scalar(select(Stock).where(Stock.product_id == product.id))
    assert stock is not None
    return manager, product, stock


def _create_member(db_session, manager):
    return member_service.create_member(
        db_session,
        manager,
        MemberCreate(
            full_name="Input Member",
            phone="+221770088000",
            status="active",
        ),
    )


def test_update_input_status_persists(db_session):
    manager, product, stock = _manager_product_stock(db_session)
    member = _create_member(db_session, manager)

    created = input_service.record_input(
        db_session,
        manager,
        InputCreate(
            member_id=member.id,
            product_id=product.id,
            date=date.today(),
            quantity=50,
            grade="A",
            status="pending",
        ),
    )
    assert stock.total_stock_kg == 550.0

    updated = input_service.update_input(
        db_session,
        manager,
        created.id,
        InputUpdate(status="validated"),
    )
    assert updated.status == "validated"
    assert stock.total_stock_kg == 550.0


def test_update_input_quantity_adjusts_stock(db_session):
    manager, product, stock = _manager_product_stock(db_session)
    member = _create_member(db_session, manager)

    created = input_service.record_input(
        db_session,
        manager,
        InputCreate(
            member_id=member.id,
            product_id=product.id,
            date=date.today(),
            quantity=25,
            grade="B",
            status="pending",
        ),
    )
    assert stock.total_stock_kg == 525.0

    input_service.update_input(
        db_session,
        manager,
        created.id,
        InputUpdate(quantity=80),
    )
    assert stock.total_stock_kg == 580.0


def test_delete_input_reverts_stock(db_session):
    manager, product, stock = _manager_product_stock(db_session)
    member = _create_member(db_session, manager)

    created = input_service.record_input(
        db_session,
        manager,
        InputCreate(
            member_id=member.id,
            product_id=product.id,
            date=date.today(),
            quantity=90,
            grade="A",
            status="validated",
        ),
    )
    assert stock.total_stock_kg == 590.0

    deleted = input_service.delete_input(db_session, manager, created.id)
    assert deleted["id"] == created.id
    assert stock.total_stock_kg == 500.0


def test_record_input_does_not_double_count_when_stock_total_needs_hydration(db_session):
    manager, product, stock = _manager_product_stock(db_session)
    member = _create_member(db_session, manager)

    # Simulate a legacy row that has not initialized total_stock_kg yet.
    stock.quantity = 0.0
    stock.total_stock_kg = 0.0
    stock.reserved_in_lots_kg = 0.0
    db_session.commit()

    input_service.record_input(
        db_session,
        manager,
        InputCreate(
            member_id=member.id,
            product_id=product.id,
            date=date.today(),
            quantity=500,
            grade="A",
            status="validated",
        ),
    )

    assert stock.total_stock_kg == 500.0
    assert stock.quantity == 500.0


def test_delete_input_blocked_when_lot_reservation_would_become_invalid(db_session):
    manager, product, stock = _manager_product_stock(db_session)
    member = _create_member(db_session, manager)

    created = input_service.record_input(
        db_session,
        manager,
        InputCreate(
            member_id=member.id,
            product_id=product.id,
            date=date.today(),
            quantity=90,
            grade="A",
            status="validated",
        ),
    )
    assert stock.total_stock_kg == 590.0

    stock.reserved_in_lots_kg = 550.0
    stock.quantity = 40.0
    db_session.commit()

    with pytest.raises(ValidationError, match="reservee dans des lots"):
        input_service.delete_input(db_session, manager, created.id)

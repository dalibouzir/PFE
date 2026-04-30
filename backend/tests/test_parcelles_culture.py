from datetime import date

import pytest
from sqlalchemy import select

from app.models.enums import MemberStatus, PreHarvestStepStatus, UserRole, UserStatus
from app.models.member import Member
from app.models.parcel import Parcel
from app.models.pre_harvest_step import PreHarvestStep
from app.models.product import Product
from app.models.treasury_transaction import TreasuryTransaction
from app.models.user import User
from app.schemas.global_charge import GlobalChargeCreate
from app.schemas.member import MemberCreate
from app.schemas.parcel import ParcelCreate
from app.schemas.pre_harvest import PreHarvestStepUpdate
from app.services import farmer_advances as farmer_advances_service
from app.services import global_charges as global_charges_service
from app.services import members as member_service
from app.services import parcels as parcel_service
from app.services import preharvest_analytics
from app.utils.exceptions import ForbiddenError


def _build_member_payload():
    return MemberCreate(
        full_name="Mamadou Diallo",
        phone="+221771111111",
        village="Thies",
        notes=None,
        products=["Mangue"],
        join_date=date.today(),
        specialty=None,
        status="active",
    )


def _build_parcel_payload(farmer_id):
    return ParcelCreate(
        farmer_id=farmer_id,
        name="Champ Nord",
        surface_ha=2.5,
        main_culture="Mangue",
        variety="Kent",
        tree_count=80,
    )


def test_parcel_creation_updates_member_derived_fields(db_session):
    manager = db_session.scalar(select(User).where(User.role == UserRole.MANAGER))
    member_service.create_member(db_session, manager, _build_member_payload())
    farmer = db_session.scalar(select(Member).where(Member.full_name == "Mamadou Diallo"))
    parcel_service.create_parcel(db_session, manager, _build_parcel_payload(farmer.id))

    listed = member_service.list_members(db_session, manager)
    row = next(item for item in listed if item["id"] == farmer.id)
    assert row["parcel_count"] == 1
    assert row["area_hectares"] == pytest.approx(2.5)


def test_parcel_creation_initializes_default_steps(db_session):
    manager = db_session.scalar(select(User).where(User.role == UserRole.MANAGER))
    member_service.create_member(db_session, manager, _build_member_payload())
    farmer = db_session.scalar(select(Member).where(Member.full_name == "Mamadou Diallo"))
    parcel = parcel_service.create_parcel(db_session, manager, _build_parcel_payload(farmer.id))

    steps = db_session.scalars(
        select(PreHarvestStep).where(PreHarvestStep.parcel_id == parcel.id).order_by(PreHarvestStep.step_order.asc())
    ).all()
    assert len(steps) == 6
    assert [item.step_key for item in steps] == [
        "pruning",
        "phytosanitary_treatment",
        "fertilization",
        "irrigation",
        "harvest",
        "transport_to_storage",
    ]


def test_viewer_cannot_create_parcel(db_session):
    manager = db_session.scalar(select(User).where(User.role == UserRole.MANAGER))
    member_service.create_member(db_session, manager, _build_member_payload())
    farmer = db_session.scalar(select(Member).where(Member.full_name == "Mamadou Diallo"))
    viewer = User(
        full_name="Read Only",
        email="viewer@test.local",
        password_hash="hash",
        role=UserRole.VIEWER,
        status=UserStatus.ACTIVE,
        cooperative_id=manager.cooperative_id,
    )
    db_session.add(viewer)
    db_session.commit()
    with pytest.raises(ForbiddenError):
        parcel_service.create_parcel(db_session, viewer, _build_parcel_payload(farmer.id))


def test_owner_can_delete_parcel_and_manager_cannot(db_session):
    manager = db_session.scalar(select(User).where(User.role == UserRole.MANAGER))
    member_service.create_member(db_session, manager, _build_member_payload())
    farmer = db_session.scalar(select(Member).where(Member.full_name == "Mamadou Diallo"))
    parcel = parcel_service.create_parcel(db_session, manager, _build_parcel_payload(farmer.id))

    with pytest.raises(ForbiddenError):
        parcel_service.delete_parcel(db_session, manager, parcel.id)

    owner = User(
        full_name="Owner Coop",
        email="owner@test.local",
        password_hash="hash",
        role=UserRole.OWNER,
        status=UserStatus.ACTIVE,
        cooperative_id=manager.cooperative_id,
    )
    db_session.add(owner)
    db_session.commit()
    parcel_service.delete_parcel(db_session, owner, parcel.id)
    assert db_session.scalar(select(Parcel).where(Parcel.id == parcel.id)) is None


def test_step_completion_updates_progress_and_cost_analytics(db_session):
    manager = db_session.scalar(select(User).where(User.role == UserRole.MANAGER))
    member_service.create_member(db_session, manager, _build_member_payload())
    farmer = db_session.scalar(select(Member).where(Member.full_name == "Mamadou Diallo"))
    parcel = parcel_service.create_parcel(db_session, manager, _build_parcel_payload(farmer.id))
    step = db_session.scalar(
        select(PreHarvestStep).where(PreHarvestStep.parcel_id == parcel.id, PreHarvestStep.step_key == "pruning")
    )

    payload = PreHarvestStepUpdate(
        quantity_value=500,
        quantity_unit="arbres",
        operation_cost_fcfa=25000,
        realization_date=date.today(),
        observations="Done",
    )
    parcel_service.update_pre_harvest_step(db_session, manager, parcel.id, step.id, payload)

    refreshed = db_session.scalar(select(PreHarvestStep).where(PreHarvestStep.id == step.id))
    assert refreshed.status == PreHarvestStepStatus.COMPLETED
    summary = preharvest_analytics.get_summary(db_session, manager)
    assert summary["completed_steps_count"] >= 1
    assert summary["total_pre_harvest_cost_fcfa"] >= 25000


def test_cross_cooperative_scope_is_blocked_for_manager(db_session):
    manager = db_session.scalar(select(User).where(User.role == UserRole.MANAGER))
    other_coop = manager.cooperative.__class__(
        name="Other Coop",
        region="Dakar",
        address="Addr",
        phone="+221770000099",
    )
    db_session.add(other_coop)
    db_session.flush()

    outsider_farmer = Member(
        cooperative_id=other_coop.id,
        code="FARM-9999",
        full_name="Outside Farmer",
        phone="+221770009999",
        status=MemberStatus.ACTIVE,
    )
    db_session.add(outsider_farmer)
    db_session.commit()

    rows = parcel_service.list_parcels(db_session, manager, member_id=outsider_farmer.id)
    assert rows == []


def test_global_charge_syncs_to_treasury_and_farmer_advances_summary(db_session):
    manager = db_session.scalar(select(User).where(User.role == UserRole.MANAGER))
    member_service.create_member(db_session, manager, _build_member_payload())
    farmer = db_session.scalar(select(Member).where(Member.full_name == "Mamadou Diallo"))

    created = global_charges_service.create_charge(
        db_session,
        manager,
        GlobalChargeCreate(
            farmer_id=farmer.id,
            charge_type="Engrais",
            label="Achat NPK",
            amount_fcfa=18000,
            date=date.today(),
            notes=None,
        ),
    )

    assert created["treasury_transaction_id"] is not None
    treasury_tx = db_session.scalar(
        select(TreasuryTransaction).where(TreasuryTransaction.id == created["treasury_transaction_id"])
    )
    assert treasury_tx is not None
    assert treasury_tx.source_type == "global_charge"
    assert treasury_tx.farmer_id == farmer.id
    assert treasury_tx.amount_fcfa == pytest.approx(18000)

    summary = farmer_advances_service.list_farmer_advances_summary(db_session, manager)
    row = next(item for item in summary.items if item.farmer_id == farmer.id)
    assert row.total_amount_given == pytest.approx(18000)
    assert row.number_of_advances == 0

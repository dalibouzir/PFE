import uuid

import pytest

from app.models.cooperative import Cooperative
from app.models.enums import UserRole, UserStatus
from app.models.institution import Institution
from app.models.user import User
from app.services.helpers import (
    ensure_user_can_access_cooperative_by_institution_or_global,
    ensure_user_can_access_institution,
    get_manager_cooperative_id,
    get_user_institution_scope,
    is_institution_admin,
    is_super_admin,
)
from app.utils.exceptions import ForbiddenError


def _create_user(
    db_session,
    *,
    role: UserRole,
    cooperative_id=None,
    institution_id=None,
) -> User:
    user = User(
        full_name=f"{role.value} user",
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@test.local",
        password_hash="hash",
        phone=None,
        role=role,
        status=UserStatus.ACTIVE,
        cooperative_id=cooperative_id,
        institution_id=institution_id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_super_admin_passes_global_scope(db_session):
    super_admin = _create_user(db_session, role=UserRole.SUPER_ADMIN)
    assert is_super_admin(super_admin) is True
    assert get_user_institution_scope(super_admin) is None


def test_institution_admin_passes_institution_guard(db_session):
    institution = Institution(name="Inst A", status="active")
    db_session.add(institution)
    db_session.flush()
    institution_admin = _create_user(
        db_session,
        role=UserRole.INSTITUTION_ADMIN,
        institution_id=institution.id,
    )

    assert is_institution_admin(institution_admin) is True
    scoped = ensure_user_can_access_institution(db_session, institution_admin, institution.id)
    assert scoped.id == institution.id


def test_institution_admin_cannot_access_unrelated_institution(db_session):
    institution_a = Institution(name="Inst A", status="active")
    institution_b = Institution(name="Inst B", status="active")
    db_session.add_all([institution_a, institution_b])
    db_session.flush()
    institution_admin = _create_user(
        db_session,
        role=UserRole.INSTITUTION_ADMIN,
        institution_id=institution_a.id,
    )

    with pytest.raises(ForbiddenError):
        ensure_user_can_access_institution(db_session, institution_admin, institution_b.id)


def test_institution_admin_cannot_access_cooperative_outside_own_institution(db_session):
    institution_a = Institution(name="Inst A", status="active")
    institution_b = Institution(name="Inst B", status="active")
    db_session.add_all([institution_a, institution_b])
    db_session.flush()

    coop_a = Cooperative(
        name=f"Coop A-{uuid.uuid4().hex[:6]}",
        region="R1",
        address="Addr",
        phone="+2211",
        institution_id=institution_a.id,
    )
    coop_b = Cooperative(
        name=f"Coop B-{uuid.uuid4().hex[:6]}",
        region="R2",
        address="Addr",
        phone="+2212",
        institution_id=institution_b.id,
    )
    db_session.add_all([coop_a, coop_b])
    db_session.flush()

    institution_admin = _create_user(
        db_session,
        role=UserRole.INSTITUTION_ADMIN,
        institution_id=institution_a.id,
    )

    allowed = ensure_user_can_access_cooperative_by_institution_or_global(db_session, institution_admin, coop_a.id)
    assert allowed.id == coop_a.id

    with pytest.raises(ForbiddenError):
        ensure_user_can_access_cooperative_by_institution_or_global(db_session, institution_admin, coop_b.id)


def test_manager_owner_viewer_keep_cooperative_scope(db_session):
    base_coop = db_session.query(Cooperative).first()
    other_coop = Cooperative(
        name=f"Other Coop-{uuid.uuid4().hex[:6]}",
        region="Kaolack",
        address="Addr",
        phone="+2213",
    )
    db_session.add(other_coop)
    db_session.flush()

    manager = _create_user(db_session, role=UserRole.MANAGER, cooperative_id=base_coop.id)
    owner = _create_user(db_session, role=UserRole.OWNER, cooperative_id=base_coop.id)
    viewer = _create_user(db_session, role=UserRole.VIEWER, cooperative_id=base_coop.id)

    assert get_manager_cooperative_id(manager) == base_coop.id
    assert get_manager_cooperative_id(owner) == base_coop.id
    assert get_manager_cooperative_id(viewer) == base_coop.id

    with pytest.raises(ForbiddenError):
        ensure_user_can_access_cooperative_by_institution_or_global(db_session, manager, other_coop.id)


def test_admin_keeps_compatibility_global_access(db_session):
    institution = Institution(name="Inst Compat", status="active")
    db_session.add(institution)
    db_session.flush()
    coop = Cooperative(
        name=f"Compat Coop-{uuid.uuid4().hex[:6]}",
        region="Dakar",
        address="Addr",
        phone="+2214",
        institution_id=institution.id,
    )
    db_session.add(coop)
    db_session.flush()

    admin = _create_user(db_session, role=UserRole.ADMIN)
    scoped = ensure_user_can_access_cooperative_by_institution_or_global(db_session, admin, coop.id)
    assert scoped.id == coop.id

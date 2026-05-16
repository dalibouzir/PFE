from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.cooperative import Cooperative
from app.models.enums import UserRole, UserStatus
from app.models.institution import Institution
from app.models.user import User


def _override_db(db_session):
    def _inner():
        try:
            yield db_session
        finally:
            pass

    return _inner


def _set_current_user(user):
    app.dependency_overrides[get_current_user] = lambda: user


def _create_user(db_session, role: UserRole, *, institution_id=None, cooperative_id=None, email_prefix="user"):
    user = User(
        full_name=f"{role.value} test",
        email=f"{email_prefix}.{role.value}.{institution_id or cooperative_id or 'none'}@test.local",
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


def test_super_admin_can_create_list_enable_disable_institution_admins(db_session):
    app.dependency_overrides[get_db] = _override_db(db_session)
    client = TestClient(app)

    institution = Institution(name="Inst IA Manage", status="active")
    db_session.add(institution)
    db_session.flush()

    super_admin = _create_user(db_session, UserRole.SUPER_ADMIN, email_prefix="sa-inst-admin")
    _set_current_user(super_admin)

    create_resp = client.post(
        f"/super-admin/institutions/{institution.id}/admins",
        json={
            "full_name": "Institution Admin One",
            "email": "institution.admin.one@test.local",
            "password": "Password123!",
            "phone": "+221770500001",
        },
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["role"] == "institution_admin"
    assert created["institution_id"] == str(institution.id)
    assert created["cooperative_id"] is None
    assert created["status"] == "active"

    list_resp = client.get(f"/super-admin/institutions/{institution.id}/admins")
    assert list_resp.status_code == 200
    assert any(item["email"] == "institution.admin.one@test.local" for item in list_resp.json())

    disabled = client.patch(f"/super-admin/institution-admins/{created['id']}/disable")
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"

    enabled = client.patch(f"/super-admin/institution-admins/{created['id']}/enable")
    assert enabled.status_code == 200
    assert enabled.json()["status"] == "active"

    app.dependency_overrides.clear()


def test_duplicate_email_and_inactive_institution_are_rejected(db_session):
    app.dependency_overrides[get_db] = _override_db(db_session)
    client = TestClient(app)

    active_institution = Institution(name="Inst Active Duplicate", status="active")
    inactive_institution = Institution(name="Inst Inactive Block", status="inactive")
    db_session.add_all([active_institution, inactive_institution])
    db_session.flush()

    super_admin = _create_user(db_session, UserRole.SUPER_ADMIN, email_prefix="sa-dup")
    _set_current_user(super_admin)

    first = client.post(
        f"/super-admin/institutions/{active_institution.id}/admins",
        json={
            "full_name": "Admin Dup",
            "email": "dup.admin@test.local",
            "password": "Password123!",
        },
    )
    assert first.status_code == 200

    duplicate = client.post(
        f"/super-admin/institutions/{active_institution.id}/admins",
        json={
            "full_name": "Admin Dup 2",
            "email": "dup.admin@test.local",
            "password": "Password123!",
        },
    )
    assert duplicate.status_code == 409

    blocked = client.post(
        f"/super-admin/institutions/{inactive_institution.id}/admins",
        json={
            "full_name": "Blocked Admin",
            "email": "blocked.admin@test.local",
            "password": "Password123!",
        },
    )
    assert blocked.status_code in {400, 422}

    app.dependency_overrides.clear()


def test_non_platform_roles_cannot_access_and_non_institution_admin_targets_blocked(db_session):
    app.dependency_overrides[get_db] = _override_db(db_session)
    client = TestClient(app)

    institution = Institution(name="Inst Access Guard", status="active")
    db_session.add(institution)
    db_session.flush()

    coop = Cooperative(name="Coop Guard", region="R1", address="Addr", phone="+221770500002", institution_id=institution.id)
    db_session.add(coop)
    db_session.flush()

    manager = _create_user(db_session, UserRole.MANAGER, cooperative_id=coop.id, institution_id=institution.id, email_prefix="mgr-forbid-inst-admin")
    _set_current_user(manager)

    forbidden = client.get(f"/super-admin/institutions/{institution.id}/admins")
    assert forbidden.status_code == 403

    super_admin = _create_user(db_session, UserRole.SUPER_ADMIN, email_prefix="sa-guard-inst-admin")
    coop_user = _create_user(db_session, UserRole.VIEWER, cooperative_id=coop.id, institution_id=institution.id, email_prefix="viewer-target")
    _set_current_user(super_admin)

    wrong_target_disable = client.patch(f"/super-admin/institution-admins/{coop_user.id}/disable")
    assert wrong_target_disable.status_code == 403

    app.dependency_overrides.clear()

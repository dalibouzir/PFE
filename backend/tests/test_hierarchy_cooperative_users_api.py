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


def test_super_admin_can_create_list_enable_disable_cooperative_users(db_session):
    app.dependency_overrides[get_db] = _override_db(db_session)
    client = TestClient(app)

    institution = Institution(name="Inst SA Users", status="active")
    db_session.add(institution)
    db_session.flush()

    coop = Cooperative(
        name="Coop SA Users",
        region="R1",
        address="Addr",
        phone="+221770100001",
        institution_id=institution.id,
    )
    db_session.add(coop)
    db_session.flush()

    super_admin = _create_user(db_session, UserRole.SUPER_ADMIN, email_prefix="sa")
    _set_current_user(super_admin)

    create_resp = client.post(
        f"/super-admin/cooperatives/{coop.id}/users",
        json={
            "full_name": "Manager SA",
            "email": "manager.sa@test.local",
            "password": "Password123!",
            "phone": "+221770100002",
            "role": "manager",
        },
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["role"] == "manager"
    assert created["cooperative_id"] == str(coop.id)
    assert created["institution_id"] == str(institution.id)

    list_resp = client.get(f"/super-admin/cooperatives/{coop.id}/users")
    assert list_resp.status_code == 200
    assert any(item["email"] == "manager.sa@test.local" for item in list_resp.json())

    user_id = created["id"]
    disable_resp = client.patch(f"/super-admin/users/{user_id}/disable")
    assert disable_resp.status_code == 200
    assert disable_resp.json()["status"] == "disabled"

    enable_resp = client.patch(f"/super-admin/users/{user_id}/enable")
    assert enable_resp.status_code == 200
    assert enable_resp.json()["status"] == "active"

    app.dependency_overrides.clear()


def test_institution_admin_scope_enforced_for_cooperative_users(db_session):
    app.dependency_overrides[get_db] = _override_db(db_session)
    client = TestClient(app)

    institution_a = Institution(name="Inst A Users", status="active")
    institution_b = Institution(name="Inst B Users", status="active")
    db_session.add_all([institution_a, institution_b])
    db_session.flush()

    coop_a = Cooperative(
        name="Coop A Users",
        region="R1",
        address="Addr",
        phone="+221770200001",
        institution_id=institution_a.id,
    )
    coop_b = Cooperative(
        name="Coop B Users",
        region="R2",
        address="Addr",
        phone="+221770200002",
        institution_id=institution_b.id,
    )
    coop_independent = Cooperative(
        name="Coop Indep Users",
        region="R3",
        address="Addr",
        phone="+221770200003",
        institution_id=None,
    )
    db_session.add_all([coop_a, coop_b, coop_independent])
    db_session.flush()

    institution_admin = _create_user(
        db_session,
        UserRole.INSTITUTION_ADMIN,
        institution_id=institution_a.id,
        email_prefix="inst-admin",
    )
    _set_current_user(institution_admin)

    create_ok = client.post(
        f"/institution-admin/cooperatives/{coop_a.id}/users",
        json={
            "full_name": "Owner A",
            "email": "owner.a@test.local",
            "password": "Password123!",
            "role": "owner",
        },
    )
    assert create_ok.status_code == 200
    assert create_ok.json()["institution_id"] == str(institution_a.id)

    create_other = client.post(
        f"/institution-admin/cooperatives/{coop_b.id}/users",
        json={
            "full_name": "Owner B",
            "email": "owner.b@test.local",
            "password": "Password123!",
            "role": "owner",
        },
    )
    assert create_other.status_code == 403

    create_independent = client.post(
        f"/institution-admin/cooperatives/{coop_independent.id}/users",
        json={
            "full_name": "Owner Indep",
            "email": "owner.ind@test.local",
            "password": "Password123!",
            "role": "owner",
        },
    )
    assert create_independent.status_code == 403

    outsider_user = _create_user(
        db_session,
        UserRole.MANAGER,
        cooperative_id=coop_b.id,
        institution_id=institution_b.id,
        email_prefix="outsider",
    )

    disable_outside = client.patch(f"/institution-admin/users/{outsider_user.id}/disable")
    assert disable_outside.status_code == 403

    disable_inside = client.patch(f"/institution-admin/users/{create_ok.json()['id']}/disable")
    assert disable_inside.status_code == 200
    assert disable_inside.json()["status"] == "disabled"

    app.dependency_overrides.clear()


def test_invalid_roles_and_non_admin_access_are_blocked(db_session):
    app.dependency_overrides[get_db] = _override_db(db_session)
    client = TestClient(app)

    institution = Institution(name="Inst Role Guard", status="active")
    db_session.add(institution)
    db_session.flush()

    coop = Cooperative(
        name="Coop Role Guard",
        region="R1",
        address="Addr",
        phone="+221770300001",
        institution_id=institution.id,
    )
    db_session.add(coop)
    db_session.flush()

    super_admin = _create_user(db_session, UserRole.SUPER_ADMIN, email_prefix="sa-guard")
    _set_current_user(super_admin)

    invalid_role = client.post(
        f"/super-admin/cooperatives/{coop.id}/users",
        json={
            "full_name": "Invalid Role",
            "email": "invalid.role@test.local",
            "password": "Password123!",
            "role": "super_admin",
        },
    )
    assert invalid_role.status_code in {400, 422}

    manager = _create_user(db_session, UserRole.MANAGER, cooperative_id=coop.id, email_prefix="manager-guard")
    _set_current_user(manager)

    forbidden_super_admin_route = client.get(f"/super-admin/cooperatives/{coop.id}/users")
    assert forbidden_super_admin_route.status_code == 403

    forbidden_institution_admin_route = client.get(f"/institution-admin/cooperatives/{coop.id}/users")
    assert forbidden_institution_admin_route.status_code == 403

    app.dependency_overrides.clear()

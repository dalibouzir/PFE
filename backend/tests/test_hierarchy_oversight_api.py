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


def test_super_admin_oversight_returns_global_snapshot(db_session):
    app.dependency_overrides[get_db] = _override_db(db_session)
    client = TestClient(app)

    institution = Institution(name="Inst Oversight SA", status="active")
    db_session.add(institution)
    db_session.flush()

    coop_linked = Cooperative(name="Coop Linked SA", region="R1", address="Addr", phone="+221770910001", institution_id=institution.id)
    coop_independent = Cooperative(name="Coop Indep SA", region="R2", address="Addr", phone="+221770910002", institution_id=None)
    db_session.add_all([coop_linked, coop_independent])
    db_session.flush()

    _create_user(db_session, UserRole.MANAGER, cooperative_id=coop_linked.id, institution_id=institution.id, email_prefix="mgr1")
    _create_user(db_session, UserRole.VIEWER, cooperative_id=coop_independent.id, institution_id=None, email_prefix="vw1")
    _create_user(db_session, UserRole.SUPER_ADMIN, email_prefix="sa")
    super_admin = _create_user(db_session, UserRole.ADMIN, email_prefix="compat-admin")
    _set_current_user(super_admin)

    response = client.get("/super-admin/oversight/cooperatives")
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_cooperatives"] >= 2
    assert payload["summary"]["total_lots"] >= 0
    assert payload["summary"]["total_users"] >= 2
    assert len(payload["cooperatives"]) >= 2

    names = {row["cooperative_name"] for row in payload["cooperatives"]}
    assert "Coop Linked SA" in names
    assert "Coop Indep SA" in names

    app.dependency_overrides.clear()


def test_institution_admin_oversight_is_scoped_to_own_institution(db_session):
    app.dependency_overrides[get_db] = _override_db(db_session)
    client = TestClient(app)

    institution_a = Institution(name="Inst A Oversight", status="active")
    institution_b = Institution(name="Inst B Oversight", status="active")
    db_session.add_all([institution_a, institution_b])
    db_session.flush()

    coop_a = Cooperative(name="Coop A", region="R1", address="Addr", phone="+221770920001", institution_id=institution_a.id)
    coop_b = Cooperative(name="Coop B", region="R2", address="Addr", phone="+221770920002", institution_id=institution_b.id)
    coop_independent = Cooperative(name="Coop Indep", region="R3", address="Addr", phone="+221770920003", institution_id=None)
    db_session.add_all([coop_a, coop_b, coop_independent])
    db_session.flush()

    _create_user(db_session, UserRole.MANAGER, cooperative_id=coop_a.id, institution_id=institution_a.id, email_prefix="mgr-a")
    _create_user(db_session, UserRole.MANAGER, cooperative_id=coop_b.id, institution_id=institution_b.id, email_prefix="mgr-b")
    _create_user(db_session, UserRole.VIEWER, cooperative_id=coop_independent.id, institution_id=None, email_prefix="vw-ind")

    institution_admin = _create_user(db_session, UserRole.INSTITUTION_ADMIN, institution_id=institution_a.id, email_prefix="inst-admin")
    _set_current_user(institution_admin)

    response = client.get("/institution-admin/oversight/cooperatives")
    assert response.status_code == 200
    payload = response.json()

    assert payload["summary"]["total_cooperatives"] == 1
    assert len(payload["cooperatives"]) == 1
    assert payload["cooperatives"][0]["cooperative_id"] == str(coop_a.id)

    app.dependency_overrides.clear()


def test_manager_and_viewer_cannot_access_oversight_endpoints(db_session):
    app.dependency_overrides[get_db] = _override_db(db_session)
    client = TestClient(app)

    institution = Institution(name="Inst Forbidden", status="active")
    db_session.add(institution)
    db_session.flush()

    coop = Cooperative(name="Coop Forbidden", region="R1", address="Addr", phone="+221770930001", institution_id=institution.id)
    db_session.add(coop)
    db_session.flush()

    manager = _create_user(db_session, UserRole.MANAGER, cooperative_id=coop.id, institution_id=institution.id, email_prefix="mgr-forbid")
    _set_current_user(manager)
    assert client.get("/super-admin/oversight/cooperatives").status_code == 403
    assert client.get("/institution-admin/oversight/cooperatives").status_code == 403

    viewer = _create_user(db_session, UserRole.VIEWER, cooperative_id=coop.id, institution_id=institution.id, email_prefix="vw-forbid")
    _set_current_user(viewer)
    assert client.get("/super-admin/oversight/cooperatives").status_code == 403
    assert client.get("/institution-admin/oversight/cooperatives").status_code == 403

    app.dependency_overrides.clear()

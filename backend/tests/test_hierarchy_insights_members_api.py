from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.cooperative import Cooperative
from app.models.enums import UserRole, UserStatus
from app.models.institution import Institution
from app.models.member import Member
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


def _create_member(db_session, cooperative_id, name: str, phone: str):
    db_session.add(
        Member(
            cooperative_id=cooperative_id,
            code=f"{name[:2].upper()}-1",
            full_name=name,
            phone=phone,
            parcel_count=0,
            area_hectares=0.0,
            status="active",
        )
    )
    db_session.flush()


def test_super_admin_can_read_members_for_any_cooperative(db_session):
    app.dependency_overrides[get_db] = _override_db(db_session)
    client = TestClient(app)

    institution = Institution(name="Inst Members SA", status="active")
    db_session.add(institution)
    db_session.flush()
    coop = Cooperative(name="Coop SA Members", region="R1", address="Addr", phone="+221770940001", institution_id=institution.id)
    db_session.add(coop)
    db_session.flush()
    _create_member(db_session, coop.id, "Producer One", "+221770940002")

    user = _create_user(db_session, UserRole.SUPER_ADMIN, email_prefix="sa")
    _set_current_user(user)

    resp = client.get(f"/super-admin/insights/cooperatives/{coop.id}/members")
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload) == 1
    assert payload[0]["full_name"] == "Producer One"

    app.dependency_overrides.clear()


def test_institution_admin_members_scope_and_independent_block(db_session):
    app.dependency_overrides[get_db] = _override_db(db_session)
    client = TestClient(app)

    inst_a = Institution(name="Inst A Members", status="active")
    inst_b = Institution(name="Inst B Members", status="active")
    db_session.add_all([inst_a, inst_b])
    db_session.flush()

    coop_a = Cooperative(name="Coop A Members", region="R1", address="Addr", phone="+221770950001", institution_id=inst_a.id)
    coop_b = Cooperative(name="Coop B Members", region="R2", address="Addr", phone="+221770950002", institution_id=inst_b.id)
    coop_ind = Cooperative(name="Coop Indep Members", region="R3", address="Addr", phone="+221770950003", institution_id=None)
    db_session.add_all([coop_a, coop_b, coop_ind])
    db_session.flush()

    _create_member(db_session, coop_a.id, "Producer A", "+221770950004")
    _create_member(db_session, coop_b.id, "Producer B", "+221770950005")
    _create_member(db_session, coop_ind.id, "Producer Indep", "+221770950006")

    user = _create_user(db_session, UserRole.INSTITUTION_ADMIN, institution_id=inst_a.id, email_prefix="inst-admin")
    _set_current_user(user)

    ok = client.get(f"/institution-admin/insights/cooperatives/{coop_a.id}/members")
    assert ok.status_code == 200
    assert len(ok.json()) == 1

    forbidden_other = client.get(f"/institution-admin/insights/cooperatives/{coop_b.id}/members")
    assert forbidden_other.status_code == 403

    forbidden_independent = client.get(f"/institution-admin/insights/cooperatives/{coop_ind.id}/members")
    assert forbidden_independent.status_code == 403

    app.dependency_overrides.clear()


def test_manager_and_viewer_cannot_access_members_insights_routes(db_session):
    app.dependency_overrides[get_db] = _override_db(db_session)
    client = TestClient(app)

    institution = Institution(name="Inst Members Denied", status="active")
    db_session.add(institution)
    db_session.flush()
    coop = Cooperative(name="Coop Members Denied", region="R1", address="Addr", phone="+221770960001", institution_id=institution.id)
    db_session.add(coop)
    db_session.flush()

    manager = _create_user(db_session, UserRole.MANAGER, cooperative_id=coop.id, institution_id=institution.id, email_prefix="mgr")
    _set_current_user(manager)
    assert client.get(f"/super-admin/insights/cooperatives/{coop.id}/members").status_code == 403
    assert client.get(f"/institution-admin/insights/cooperatives/{coop.id}/members").status_code == 403

    viewer = _create_user(db_session, UserRole.VIEWER, cooperative_id=coop.id, institution_id=institution.id, email_prefix="vw")
    _set_current_user(viewer)
    assert client.get(f"/super-admin/insights/cooperatives/{coop.id}/members").status_code == 403
    assert client.get(f"/institution-admin/insights/cooperatives/{coop.id}/members").status_code == 403

    app.dependency_overrides.clear()

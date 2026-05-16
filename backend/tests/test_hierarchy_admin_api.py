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


def _create_user(db_session, role: UserRole, *, institution_id=None):
    user = User(
        full_name=f"{role.value} test",
        email=f"{role.value}.{institution_id or 'none'}@test.local",
        password_hash="hash",
        phone=None,
        role=role,
        status=UserStatus.ACTIVE,
        cooperative_id=None,
        institution_id=institution_id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_super_admin_can_manage_hierarchy_and_view_overview(db_session):
    app.dependency_overrides[get_db] = _override_db(db_session)
    super_admin = _create_user(db_session, UserRole.SUPER_ADMIN)
    _set_current_user(super_admin)
    client = TestClient(app)

    institution_payload = {
        "name": "Institution SA",
        "description": "platform",
        "region": "Dakar",
        "address": "addr",
        "phone": "+221770000111",
        "email": "institution-sa@test.local",
    }
    create_inst = client.post("/super-admin/institutions", json=institution_payload)
    assert create_inst.status_code == 200
    institution_id = create_inst.json()["id"]

    create_coop = client.post(
        "/super-admin/cooperatives",
        json={
            "name": "Coop SA Linked",
            "region": "Thies",
            "address": "addr",
            "phone": "+221770000112",
            "institution_id": institution_id,
        },
    )
    assert create_coop.status_code == 200

    create_independent = client.post(
        "/super-admin/cooperatives",
        json={
            "name": "Coop SA Independent",
            "region": "Kaolack",
            "address": "addr",
            "phone": "+221770000113",
            "institution_id": None,
        },
    )
    assert create_independent.status_code == 200
    independent_id = create_independent.json()["id"]

    assign = client.patch(
        f"/super-admin/cooperatives/{independent_id}/assign-institution",
        json={"institution_id": institution_id},
    )
    assert assign.status_code == 200
    assert assign.json()["institution_id"] == institution_id

    make_independent = client.patch(f"/super-admin/cooperatives/{independent_id}/make-independent")
    assert make_independent.status_code == 200
    assert make_independent.json()["institution_id"] is None

    hierarchy = client.get("/super-admin/hierarchy")
    assert hierarchy.status_code == 200
    payload = hierarchy.json()
    assert any(item["id"] == institution_id for item in payload["institutions"])
    assert any(item["id"] == independent_id for item in payload["independent_cooperatives"])

    app.dependency_overrides.clear()


def test_institution_admin_scope_restrictions(db_session):
    app.dependency_overrides[get_db] = _override_db(db_session)
    client = TestClient(app)

    institution_a = Institution(name="Institution A", status="active")
    institution_b = Institution(name="Institution B", status="active")
    db_session.add_all([institution_a, institution_b])
    db_session.flush()

    coop_a = Cooperative(
        name="Scope Coop A",
        region="R1",
        address="addr",
        phone="+221770000201",
        institution_id=institution_a.id,
    )
    coop_b = Cooperative(
        name="Scope Coop B",
        region="R2",
        address="addr",
        phone="+221770000202",
        institution_id=institution_b.id,
    )
    independent = Cooperative(
        name="Scope Coop Independent",
        region="R3",
        address="addr",
        phone="+221770000203",
        institution_id=None,
    )
    db_session.add_all([coop_a, coop_b, independent])
    db_session.flush()

    institution_admin = _create_user(db_session, UserRole.INSTITUTION_ADMIN, institution_id=institution_a.id)
    _set_current_user(institution_admin)

    own_inst = client.get("/institution-admin/institution")
    assert own_inst.status_code == 200
    assert own_inst.json()["id"] == str(institution_a.id)

    own_coops = client.get("/institution-admin/cooperatives")
    assert own_coops.status_code == 200
    listed_ids = {item["id"] for item in own_coops.json()}
    assert str(coop_a.id) in listed_ids
    assert str(coop_b.id) not in listed_ids

    allowed = client.get(f"/institution-admin/cooperatives/{coop_a.id}")
    assert allowed.status_code == 200

    forbidden_other = client.get(f"/institution-admin/cooperatives/{coop_b.id}")
    assert forbidden_other.status_code == 403

    forbidden_independent = client.get(f"/institution-admin/cooperatives/{independent.id}")
    assert forbidden_independent.status_code == 403

    create_linked = client.post(
        "/institution-admin/cooperatives",
        json={
            "name": "Created by Institution Admin",
            "region": "Thiadiaye",
            "address": "addr",
            "phone": "+221770000204",
            "institution_id": str(institution_a.id),
        },
    )
    assert create_linked.status_code == 200
    assert create_linked.json()["institution_id"] == str(institution_a.id)

    create_other = client.post(
        "/institution-admin/cooperatives",
        json={
            "name": "Wrong institution assignment",
            "region": "Mbour",
            "address": "addr",
            "phone": "+221770000205",
            "institution_id": str(institution_b.id),
        },
    )
    assert create_other.status_code == 403

    update_forbidden = client.patch(
        f"/institution-admin/cooperatives/{coop_a.id}",
        json={"institution_id": str(institution_b.id)},
    )
    assert update_forbidden.status_code == 403

    app.dependency_overrides.clear()


def test_compat_admin_can_access_super_admin_routes(db_session):
    app.dependency_overrides[get_db] = _override_db(db_session)
    compat_admin = _create_user(db_session, UserRole.ADMIN)
    _set_current_user(compat_admin)
    client = TestClient(app)

    response = client.get("/super-admin/cooperatives")
    assert response.status_code == 200

    app.dependency_overrides.clear()

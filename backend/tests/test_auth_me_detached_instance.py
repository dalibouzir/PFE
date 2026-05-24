from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.security import get_password_hash
from app.db.session import get_db
from app.main import app
from app.models.cooperative import Cooperative
from app.models.enums import UserRole, UserStatus
from app.models.user import User


def _override_db(db_session):
    def override_db():
        try:
            yield db_session
        finally:
            pass

    return override_db


def test_auth_me_returns_safe_profile_for_detached_user(db_session):
    manager_email = os.getenv("SEED_MANAGER_EMAIL", "manager@weefarm.local")
    manager_password = os.getenv("SEED_MANAGER_PASSWORD", "Manager123!")

    cooperative = db_session.query(Cooperative).first()
    if cooperative is None:
        cooperative = Cooperative(
            name="Auth Test Coop",
            region="Thies",
            address="Auth test address",
            phone="+221770000000",
        )
        db_session.add(cooperative)
        db_session.flush()

    user = db_session.query(User).filter(User.email == manager_email).one_or_none()
    if user is None:
        user = User(
            full_name="Auth Test Manager",
            email=manager_email,
            password_hash=get_password_hash(manager_password),
            phone="+221770000010",
            role=UserRole.MANAGER,
            status=UserStatus.ACTIVE,
            cooperative_id=cooperative.id,
        )
        db_session.add(user)
    else:
        user.full_name = user.full_name or "Auth Test Manager"
        user.password_hash = get_password_hash(manager_password)
        user.phone = user.phone or "+221770000010"
        user.role = UserRole.MANAGER
        user.status = UserStatus.ACTIVE
        user.cooperative_id = cooperative.id

    db_session.commit()

    app.dependency_overrides[get_db] = _override_db(db_session)
    try:
        with TestClient(app) as client:
            login_response = client.post(
                "/auth/login",
                json={"email": manager_email, "password": manager_password},
            )
            assert login_response.status_code == 200

            token = login_response.json()["access_token"]
            me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert me_response.status_code == 200

            payload = me_response.json()
            assert payload["id"]
            assert payload["email"] == manager_email
            assert payload["role"]
            assert "cooperative_id" in payload
            assert "institution_id" in payload
            assert "full_name" in payload
            assert payload["cooperative_id"] is None or isinstance(payload["cooperative_id"], str)
            assert payload["institution_id"] is None or isinstance(payload["institution_id"], str)
            if "cooperative_name" in payload:
                assert payload["cooperative_name"] is None or isinstance(payload["cooperative_name"], str)
    finally:
        app.dependency_overrides.clear()
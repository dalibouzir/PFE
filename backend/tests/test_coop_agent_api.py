from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.user import User


def _setup_overrides(db_session):
    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: db_session.query(User).first()


def test_chat_agent_endpoint_returns_expected_schema(db_session):
    _setup_overrides(db_session)
    client = TestClient(app)

    response = client.post(
        "/chat/agent",
        json={"message": "Analyse les pertes du lot MANG-004"},
    )
    assert response.status_code == 200
    payload = response.json()

    for key in ("answer", "route", "agents_used", "sources", "confidence", "warnings", "metadata"):
        assert key in payload

    assert payload["route"] in {"HYBRID_SQL_ML", "HYBRID_FULL", "SQL_ONLY"}
    assert "SQLAnalyticsAgent" in payload["agents_used"]
    if payload["route"] in {"HYBRID_SQL_ML", "HYBRID_FULL"}:
        assert "MLLossAgent" in payload["agents_used"]

    assert isinstance(payload["sources"], list)
    assert isinstance(payload["confidence"], float)
    assert 0.0 <= payload["confidence"] <= 1.0

    app.dependency_overrides.clear()


def test_chat_agent_routes_small_talk(db_session):
    _setup_overrides(db_session)
    client = TestClient(app)

    response = client.post("/chat/agent", json={"message": "Bonjour"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "SMALL_TALK"
    assert payload["agents_used"] == ["SmallTalkAgent"]

    app.dependency_overrides.clear()

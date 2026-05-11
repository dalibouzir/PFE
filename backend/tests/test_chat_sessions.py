from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.enums import InputStatus, MemberStatus
from app.models.input import Input
from app.models.member import Member
from app.models.reference import KnowledgeChunk
from app.models.user import User
from app.services import assistant as assistant_service


class DummyLLMClient:
    def __init__(self):
        self.calls: list[list[dict[str, str]]] = []

    def chat(self, messages: list[dict[str, str]]) -> SimpleNamespace:
        self.calls.append(messages)
        return SimpleNamespace(content=f"Reponse mock {len(self.calls)}")


def test_chat_session_persists_history_and_uses_session_memory(db_session, monkeypatch):
    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: db_session.query(User).first()

    llm_client = DummyLLMClient()
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: llm_client)

    client = TestClient(app)

    create_response = client.post("/chat/sessions", json={"title": "Conversation test"})
    assert create_response.status_code == 200
    session_id = create_response.json()["id"]

    first_response = client.post(
        "/chat",
        json={"session_id": session_id, "message": "Comment reduire les pertes de sechage?"},
    )
    assert first_response.status_code == 200
    assert first_response.json()["mode"] == "llm"
    assert first_response.json()["session_id"] == session_id

    second_response = client.post(
        "/chat",
        json={"session_id": session_id, "message": "Et quel est le prochain pas concret?"},
    )
    assert second_response.status_code == 200
    assert second_response.json()["mode"] == "llm"
    assert second_response.json()["session_id"] == session_id

    assert len(llm_client.calls) == 2
    second_call_messages = llm_client.calls[1]
    assert any(msg["role"] == "user" and "Comment reduire les pertes de sechage?" in msg["content"] for msg in second_call_messages)
    assert any(msg["role"] == "assistant" and "Reponse mock 1" in msg["content"] for msg in second_call_messages)

    history_response = client.get(f"/chat/sessions/{session_id}/messages")
    assert history_response.status_code == 200
    payload = history_response.json()
    assert len(payload) == 4
    assert [item["role"] for item in payload] == ["user", "assistant", "user", "assistant"]

    app.dependency_overrides.clear()


def test_chat_prompt_uses_intent_based_style_for_quick_questions(db_session, monkeypatch):
    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: db_session.query(User).first()

    llm_client = DummyLLMClient()
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: llm_client)

    client = TestClient(app)
    response = client.post("/chat", json={"message": "10 + 1"})
    assert response.status_code == 200
    assert response.json()["mode"] == "llm"

    assert len(llm_client.calls) == 1
    prompt = llm_client.calls[0][-1]["content"]
    assert "Response mode: quick" in prompt
    assert "No numbered list" in prompt
    assert "1) reponse directe" not in prompt

    app.dependency_overrides.clear()


def test_delete_chat_session_removes_history(db_session):
    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: db_session.query(User).first()

    client = TestClient(app)

    create_response = client.post("/chat/sessions", json={"title": "To delete"})
    assert create_response.status_code == 200
    session_id = create_response.json()["id"]

    delete_response = client.delete(f"/chat/sessions/{session_id}")
    assert delete_response.status_code == 204

    sessions_response = client.get("/chat/sessions")
    assert sessions_response.status_code == 200
    assert all(item["id"] != session_id for item in sessions_response.json())

    messages_response = client.get(f"/chat/sessions/{session_id}/messages")
    assert messages_response.status_code == 404
    assert "Chat session not found" in messages_response.json().get("detail", "")

    app.dependency_overrides.clear()


def test_chat_keeps_french_prompt_even_when_query_is_english(db_session, monkeypatch):
    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: db_session.query(User).first()

    llm_client = DummyLLMClient()
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: llm_client)

    client = TestClient(app)
    response = client.post("/chat", json={"message": "What is the current stock status?"})
    assert response.status_code == 200
    payload = response.json()
    if payload["mode"] in {"sql_only", "sql_only_no_data"}:
        assert llm_client.calls == []
        assert payload["message"]
    else:
        assert len(llm_client.calls) == 1
        system_prompt = llm_client.calls[0][0]["content"]
        user_prompt = llm_client.calls[0][-1]["content"]
        assert "français" in system_prompt.lower()
        assert "Language: fr" in user_prompt

    app.dependency_overrides.clear()


def test_chat_uses_reference_knowledge_citations_when_pgvector_is_not_available(db_session, monkeypatch):
    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: db_session.query(User).first()

    chunk = KnowledgeChunk(
        source_id="ref-loss-001",
        source_url="https://example.org/ref-loss-001",
        country="Senegal",
        region="Thies",
        crop="mango",
        topic="loss reduction",
        content="Use calibrated drying to reduce post-harvest loss by controlling moisture.",
    )
    db_session.add(chunk)
    db_session.commit()

    llm_client = DummyLLMClient()
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: llm_client)

    client = TestClient(app)
    response = client.post("/chat", json={"message": "Comment reduire les pertes post recolte?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["grounded"] is True
    assert payload["mode"] == "llm-rag"
    assert any(citation["source_id"] == "ref-loss-001" for citation in payload["citations"])

    app.dependency_overrides.clear()


def test_chat_adds_member_efficiency_metrics_for_member_queries(db_session, monkeypatch):
    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: db_session.query(User).first()

    cooperative = db_session.query(User).first().cooperative
    product = cooperative.products[0]
    member = Member(
        cooperative_id=cooperative.id,
        code="M-001",
        full_name="Alice Farmer",
        phone="+221770000099",
        village="Village A",
        main_product=product.name,
        secondary_products=None,
        parcel_count=2,
        area_hectares=1.4,
        specialty="quality",
        status=MemberStatus.ACTIVE,
    )
    db_session.add(member)
    db_session.flush()
    db_session.add(
        Input(
            cooperative_id=cooperative.id,
            member_id=member.id,
            product_id=product.id,
            field_id=None,
            date=cooperative.created_at.date(),
            quantity=100.0,
            grade="A",
            estimated_value=50000.0,
            status=InputStatus.VALIDATED,
        )
    )
    db_session.commit()

    llm_client = DummyLLMClient()
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: llm_client)

    client = TestClient(app)
    response = client.post("/chat", json={"message": "Qui est le membre le plus efficace en cout par kg ?"})
    assert response.status_code == 200
    payload = response.json()
    metric_names = {metric["metric"] for metric in payload["context_metrics"]}
    assert "best_net_cost_per_kg_fcfa" in metric_names
    assert "top_collected_kg" in metric_names
    assert any(block["title"] == "Collecte et coût/kg par membre" for block in payload["ui_blocks"])

    app.dependency_overrides.clear()

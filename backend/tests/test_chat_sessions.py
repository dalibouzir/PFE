from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
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

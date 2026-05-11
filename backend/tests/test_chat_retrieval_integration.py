from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.enums import MemberStatus
from app.models.member import Member
from app.models.chat import ChatMessage
from app.models.reference import KnowledgeChunk
from app.schemas.chat import ChatCitation
from app.models.user import User
from app.services import assistant as assistant_service
from app.utils.exceptions import ValidationError


class DummyLLMClient:
    def __init__(self):
        self.calls: list[list[dict[str, str]]] = []

    def chat(self, messages: list[dict[str, str]]) -> SimpleNamespace:
        self.calls.append(messages)
        return SimpleNamespace(content=f"Mock answer {len(self.calls)}")


class UnavailableLLMClient:
    def chat(self, messages: list[dict[str, str]]) -> SimpleNamespace:
        raise ValidationError("LLM unavailable")


def _setup_overrides(db_session):
    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: db_session.query(User).first()


def test_chat_exact_stock_question_persists_sql_retrieval_plan(db_session, monkeypatch):
    _setup_overrides(db_session)
    llm_client = DummyLLMClient()
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: llm_client)
    client = TestClient(app)

    response = client.post("/chat", json={"message": "current stock of mango"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True

    metrics = {metric["metric"]: metric for metric in payload["context_metrics"]}
    assert "retrieval_plan.intent_type" in metrics
    assert metrics["retrieval_plan.intent_type"]["unit"] == "SQL_ONLY"
    assert metrics["retrieval_plan.sql_needed"]["value"] == 1.0
    assert payload["mode"] in {"sql_only", "sql_only_no_data"}
    assert "benchmark" not in payload["message"].lower()
    assert "ml " not in payload["message"].lower()
    if payload["mode"] == "sql_only":
        assert "total" in payload["message"].lower()
        assert "réserv" in payload["message"].lower()
        assert "disponible" in payload["message"].lower()
        assert "statut" in payload["message"].lower()
    assert payload.get("ui_blocks", []) == []

    assistant_message = (
        db_session.query(ChatMessage)
        .filter(ChatMessage.id == UUID(payload["assistant_message_id"]))
        .one()
    )
    assert isinstance(assistant_message.context_metrics_json, list)
    assert any(item.get("metric") == "retrieval_plan.intent_type" for item in assistant_message.context_metrics_json)

    app.dependency_overrides.clear()


def test_sql_only_batch_status_uses_lot_facts_without_llm(db_session, monkeypatch):
    _setup_overrides(db_session)
    llm_client = DummyLLMClient()
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: llm_client)
    client = TestClient(app)

    response = client.post("/chat", json={"message": "what is the status of BATCH-0001?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] in {"sql_only", "sql_only_no_data"}
    assert "BATCH-0001" in payload["message"]
    assert "status" not in payload["message"].lower() or "statut" in payload["message"].lower()
    assert payload.get("ui_blocks", []) == []
    assert llm_client.calls == []

    app.dependency_overrides.clear()


def test_chat_explanation_question_persists_rag_or_hybrid_plan(db_session, monkeypatch):
    _setup_overrides(db_session)
    llm_client = DummyLLMClient()
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: llm_client)
    client = TestClient(app)

    response = client.post("/chat", json={"message": "why did drying losses increase this week"})
    assert response.status_code == 200
    payload = response.json()
    metrics = {metric["metric"]: metric for metric in payload["context_metrics"]}
    assert metrics["retrieval_plan.rag_needed"]["value"] == 1.0
    assert metrics["retrieval_plan.intent_type"]["unit"] in {"HYBRID", "RAG_ONLY"}
    titles = {item["title"] for item in payload.get("ui_blocks", [])}
    assert "Résumé exécutif" in titles
    assert "Niveau de confiance" in titles

    app.dependency_overrides.clear()


def test_chat_unsupported_question_returns_safe_response_without_llm(db_session, monkeypatch):
    _setup_overrides(db_session)
    llm_client = DummyLLMClient()
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: llm_client)
    client = TestClient(app)

    response = client.post("/chat", json={"message": "what movies should I watch tonight?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "unsupported"
    assert "sort du périmètre actuel" in payload["message"]
    assert llm_client.calls == []

    app.dependency_overrides.clear()


def test_chat_small_talk_returns_safe_greeting_without_cards_or_llm(db_session, monkeypatch):
    _setup_overrides(db_session)
    llm_client = DummyLLMClient()
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: llm_client)
    client = TestClient(app)

    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "small_talk"
    assert payload["message"].startswith("Bonjour.")
    assert payload["ui_blocks"] == []
    assert payload["citations"] == []
    assert payload["context_metrics"] == []
    assert llm_client.calls == []

    app.dependency_overrides.clear()


def test_chat_clarification_needed_returns_safe_prompt_without_llm(db_session, monkeypatch):
    _setup_overrides(db_session)
    llm_client = DummyLLMClient()
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: llm_client)
    client = TestClient(app)

    response = client.post("/chat", json={"message": "analyse"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "clarification_needed"
    assert "Pouvez-vous préciser votre demande" in payload["message"]
    assert payload["ui_blocks"] == []
    assert payload["citations"] == []
    assert payload["context_metrics"] == []
    assert llm_client.calls == []

    app.dependency_overrides.clear()


def test_fake_product_stock_returns_missing_data_without_hallucination(db_session, monkeypatch):
    _setup_overrides(db_session)
    llm_client = DummyLLMClient()
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: llm_client)
    client = TestClient(app)

    response = client.post("/chat", json={"message": "Quel est le stock actuel de FAKE_PRODUCT_9619 ?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] in {"sql_only_no_data", "hybrid_no_data"}
    assert "Je ne trouve pas cette donnée dans la base opérationnelle" in payload["message"]
    assert payload["citations"] == []
    assert payload["ui_blocks"] == []
    assert llm_client.calls == []

    app.dependency_overrides.clear()


def test_fake_lot_status_returns_missing_data_without_hallucination(db_session, monkeypatch):
    _setup_overrides(db_session)
    llm_client = DummyLLMClient()
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: llm_client)
    client = TestClient(app)

    response = client.post("/chat", json={"message": "Quel est le statut du lot LOT_FAKE_7456 ?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] in {"sql_only_no_data", "hybrid_no_data"}
    assert "Je ne trouve pas cette donnée dans la base opérationnelle" in payload["message"]
    assert payload["citations"] == []
    assert payload["ui_blocks"] == []
    assert llm_client.calls == []

    app.dependency_overrides.clear()


def test_fake_member_collection_returns_missing_data_without_hallucination(db_session, monkeypatch):
    _setup_overrides(db_session)
    llm_client = DummyLLMClient()
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: llm_client)
    client = TestClient(app)

    response = client.post("/chat", json={"message": "Quel est le total de collecte pour le producteur MEMBER_FAKE_7102 ?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] in {"sql_only_no_data", "hybrid_no_data"}
    assert "Je ne trouve pas cette donnée dans la base opérationnelle" in payload["message"]
    assert payload["citations"] == []
    assert payload["ui_blocks"] == []
    assert llm_client.calls == []

    app.dependency_overrides.clear()


def test_fake_stage_losses_returns_missing_data_without_hallucination(db_session, monkeypatch):
    _setup_overrides(db_session)
    llm_client = DummyLLMClient()
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: llm_client)
    client = TestClient(app)

    response = client.post("/chat", json={"message": "Explique les pertes à l'étape STAGE_FAKE_8126 cette semaine."})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] in {"sql_only_no_data", "hybrid_no_data"}
    assert "Je ne trouve pas cette donnée dans la base opérationnelle" in payload["message"]
    assert payload["citations"] == []
    assert payload["ui_blocks"] == []
    assert llm_client.calls == []

    app.dependency_overrides.clear()


def test_chat_session_behavior_and_citation_schema_remain_compatible(db_session, monkeypatch):
    _setup_overrides(db_session)
    llm_client = DummyLLMClient()
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: llm_client)

    db_session.add(
        KnowledgeChunk(
            source_id="ref-001",
            source_url="https://example.org/ref-001",
            country="Senegal",
            region="Thies",
            crop="mango",
            topic="drying best practices",
            content="Use controlled drying and staged sorting to reduce losses.",
        )
    )
    db_session.commit()

    client = TestClient(app)
    created = client.post("/chat/sessions", json={"title": "Routing test"})
    assert created.status_code == 200
    session_id = created.json()["id"]

    first = client.post("/chat", json={"session_id": session_id, "message": "best practices for drying mango"})
    assert first.status_code == 200
    second = client.post("/chat", json={"session_id": session_id, "message": "current stock of mango"})
    assert second.status_code == 200
    assert first.json()["session_id"] == second.json()["session_id"] == session_id

    history = client.get(f"/chat/sessions/{session_id}/messages")
    assert history.status_code == 200
    assert len(history.json()) == 4
    citations = first.json()["citations"]
    assert isinstance(citations, list)
    if citations:
        sample = citations[0]
        for key in ("source_id", "source_url", "region", "crop", "topic", "excerpt"):
            assert key in sample

    app.dependency_overrides.clear()


def test_rag_only_benchmark_query_returns_reference_citations(db_session, monkeypatch):
    _setup_overrides(db_session)
    llm_client = DummyLLMClient()
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: llm_client)
    client = TestClient(app)

    response = client.post("/chat", json={"message": "what does benchmark say about millet losses?"})
    assert response.status_code == 200
    payload = response.json()
    metrics = {metric["metric"]: metric for metric in payload["context_metrics"]}
    assert metrics["retrieval_plan.intent_type"]["unit"] == "RAG_ONLY"
    if payload["mode"] == "rag_only_no_evidence":
        assert "preuve" in payload["message"].lower() or "référence" in payload["message"].lower()
    else:
        assert payload["citations"]
    assert all(title != "Executive Summary" for title in [item["title"] for item in payload.get("ui_blocks", [])])

    app.dependency_overrides.clear()


def test_member_list_prompt_returns_member_table_without_lot_loss_text(db_session, monkeypatch):
    _setup_overrides(db_session)
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: DummyLLMClient())
    client = TestClient(app)

    manager = db_session.query(User).first()
    cooperative_id = manager.cooperative_id
    db_session.add_all(
        [
            Member(
                cooperative_id=cooperative_id,
                code="MEM-001",
                full_name="Alpha Member",
                phone="+221770001001",
                village="Village A",
                main_product="mango",
                secondary_products=None,
                parcel_count=2,
                area_hectares=1.5,
                specialty="quality",
                status=MemberStatus.ACTIVE,
            ),
            Member(
                cooperative_id=cooperative_id,
                code="MEM-002",
                full_name="Bravo Member",
                phone="+221770001002",
                village="Village B",
                main_product="mango",
                secondary_products=None,
                parcel_count=1,
                area_hectares=0.8,
                specialty="sorting",
                status=MemberStatus.ACTIVE,
            ),
        ]
    )
    db_session.commit()

    response = client.post("/chat", json={"message": "liste les membres actifs avec code et statut"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "sql_only"
    assert "pertes moyennes" not in payload["message"].lower()
    assert "lots" not in payload["message"].lower()
    tables = [block for block in payload["ui_blocks"] if block.get("type") == "table"]
    assert len(tables) == 1
    table = tables[0]
    assert table["payload"]["columns"] == ["code", "nom", "produit principal", "statut", "parcelles", "surface_ha"]
    assert len(table["payload"]["rows"]) >= 2
    assert table["payload"]["rows"][0][0].startswith("MEM-")

    app.dependency_overrides.clear()


def test_lot_table_prompt_returns_table_block_in_sql_only_mode(db_session, monkeypatch):
    _setup_overrides(db_session)
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: DummyLLMClient())
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={"message": "Affiche-moi un tableau des 10 derniers lots avec code lot, produit, quantité entrée, quantité sortie, taux de perte, statut et date de mise à jour."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "sql_only"
    tables = [block for block in payload["ui_blocks"] if block.get("type") == "table"]
    assert len(tables) == 1
    table = tables[0]
    assert table["payload"]["columns"] == ["lot_code", "produit", "qty_in", "qty_out", "loss_pct", "statut", "updated_at"]
    assert len(table["payload"]["rows"]) >= 1
    assert "lots trouvés" in payload["message"].lower()

    app.dependency_overrides.clear()


def test_lot_table_active_filter_no_data_returns_empty_schema_and_explicit_message(db_session, monkeypatch):
    _setup_overrides(db_session)
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: DummyLLMClient())
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={"message": "Donne-moi un tableau des lots actifs triés par taux de perte décroissant."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "sql_only"
    assert "aucun lot actif disponible" in payload["message"].lower()
    tables = [block for block in payload["ui_blocks"] if block.get("type") == "table"]
    assert len(tables) == 1
    table = tables[0]
    assert table["payload"]["columns"] == ["lot_code", "produit", "qty_in", "qty_out", "loss_pct", "statut", "updated_at"]
    assert table["payload"]["rows"] == []

    app.dependency_overrides.clear()


def test_member_list_no_data_returns_empty_schema_and_explicit_message(db_session, monkeypatch):
    _setup_overrides(db_session)
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: DummyLLMClient())
    client = TestClient(app)

    response = client.post("/chat", json={"message": "lister les membres de la cooperative"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "sql_only"
    assert "aucun membre trouvé" in payload["message"].lower()
    tables = [block for block in payload["ui_blocks"] if block.get("type") == "table"]
    assert len(tables) == 1
    table = tables[0]
    assert table["payload"]["columns"] == ["code", "nom", "produit principal", "statut", "parcelles", "surface_ha"]
    assert table["payload"]["rows"] == []

    app.dependency_overrides.clear()


def test_rag_only_fallback_with_llm_unavailable_is_citation_grounded(db_session, monkeypatch):
    _setup_overrides(db_session)
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: UnavailableLLMClient())
    monkeypatch.setattr(
        assistant_service,
        "_retrieve_reference_context",
        lambda *args, **kwargs: assistant_service.ReferenceContext(
            citations=[
                ChatCitation(
                    source_id="SRC-RAG-001",
                    source_url="https://example.org/rag-001",
                    region="Thies",
                    crop="mango",
                    topic="Séchage",
                    excerpt="Sécher la mangue sur claies ventilées réduit l'humidité résiduelle.",
                )
            ],
            metrics=[],
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={"message": "donne des références agronomiques sur le séchage de la mangue avec sources"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "fallback_rag"
    assert payload["citations"]
    message_lower = payload["message"].lower()
    assert "src-rag-001" in message_lower
    assert "références récupérées" in message_lower
    assert "pertes globales" not in message_lower
    assert "efficacité" not in message_lower

    app.dependency_overrides.clear()


def test_stock_status_regression_still_returns_sql_only_without_tables(db_session, monkeypatch):
    _setup_overrides(db_session)
    monkeypatch.setattr(assistant_service, "get_llm_client", lambda: DummyLLMClient())
    client = TestClient(app)

    response = client.post("/chat", json={"message": "current stock of mango"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] in {"sql_only", "sql_only_no_data"}
    assert [block for block in payload.get("ui_blocks", []) if block.get("type") == "table"] == []

    app.dependency_overrides.clear()

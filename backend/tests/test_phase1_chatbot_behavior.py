import re

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.process_step import ProcessStep
from app.models.user import User


def _setup_overrides(db_session):
    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: db_session.query(User).first()


def _post_agent(client: TestClient, message: str) -> dict:
    response = client.post("/chat/agent", json={"message": message})
    assert response.status_code == 200
    return response.json()


def test_general_risk_question_does_not_search_fake_avons_nous_batch(db_session):
    _setup_overrides(db_session)
    client = TestClient(app)

    try:
        payload = _post_agent(client, "Avons-nous des lots à risque ?")
    finally:
        app.dependency_overrides.clear()

    detected = payload["metadata"]["detected_entities"]
    assert detected.get("batch_ref") is None
    assert detected.get("specific_batch_requested") is False
    assert payload["route"] == "HYBRID_SQL_ML"
    assert "AVONS-NOUS" not in payload["answer"]
    assert "référence AVONS-NOUS" not in payload["answer"]


def test_chatbot_public_warnings_are_french_not_internal_codes(db_session):
    _setup_overrides(db_session)
    client = TestClient(app)

    try:
        payload = _post_agent(client, "Avons-nous des lots à risque ?")
    finally:
        app.dependency_overrides.clear()

    assert payload["warnings"]
    for warning in payload["warnings"]:
        assert not re.fullmatch(r"[A-Z0-9_]+", warning)
    assert "warning_codes" in payload["metadata"]


def test_valid_missing_lot_returns_missing_batch_message_only_for_specific_lot(db_session):
    _setup_overrides(db_session)
    client = TestClient(app)

    try:
        payload = _post_agent(client, "Analyse le lot MANG-999")
    finally:
        app.dependency_overrides.clear()

    assert payload["metadata"]["detected_entities"]["batch_ref"] == "MANG-999"
    assert "Je n’ai pas trouvé de lot avec la référence MANG-999." in payload["answer"]
    assert "Les données opérationnelles sont incomplètes." in payload["warnings"]


def test_english_user_question_still_gets_french_answer(db_session):
    _setup_overrides(db_session)
    client = TestClient(app)

    try:
        payload = _post_agent(client, "What are the risky batches today?")
    finally:
        app.dependency_overrides.clear()

    assert payload["route"] in {"HYBRID_SQL_ML", "SQL_ONLY", "ML_ONLY"}
    assert "Résultat principal" in payload["answer"] or "lots" in payload["answer"].lower()
    assert "risky batches" not in payload["answer"].lower()


def test_out_of_scope_answer_is_french(db_session):
    _setup_overrides(db_session)
    client = TestClient(app)

    try:
        payload = _post_agent(client, "Who won the Champions League?")
    finally:
        app.dependency_overrides.clear()

    assert payload["route"] == "OUT_OF_SCOPE"
    assert "Je suis conçu pour analyser les données de la coopérative" in payload["answer"]


def test_stage_loss_answer_uses_highest_loss_step_not_latest_row(db_session):
    older_drying_step = (
        db_session.query(ProcessStep)
        .filter(ProcessStep.type == "drying")
        .order_by(ProcessStep.date.asc())
        .first()
    )
    older_drying_step.qty_out = older_drying_step.qty_in * 0.5
    db_session.commit()

    _setup_overrides(db_session)
    client = TestClient(app)

    try:
        payload = _post_agent(client, "Quelle étape cause le plus de pertes ?")
    finally:
        app.dependency_overrides.clear()

    assert "drying" in payload["answer"]
    assert "50.0% de pertes" in payload["answer"]

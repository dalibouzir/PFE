from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.integration
def test_chat_agent_sql_runtime_dispatch_contract():
    os.environ["AI_AUDIT_DEBUG"] = "1"
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"email": "manager@weefarm.local", "password": "Manager123!"},
        )
        if login.status_code != 200:
            pytest.skip("Manager seed credentials unavailable for runtime integration check")

        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        cases = [
            ("Quel est le stock actuel par produit et par qualité ?", "STOCK_CURRENT", "get_current_stock"),
            ("Quels lots post-récolte sont disponibles actuellement ?", "POSTHARVEST_AVAILABLE_LOTS", "get_available_postharvest_lots"),
            ("Quels lots ont les pertes les plus élevées ?", "LOSS_RANKING", "get_canonical_material_balance"),
            ("Quels lots ont le plus grand écart entre entrée et sortie ?", "INPUT_OUTPUT_GAP", "get_canonical_material_balance"),
            ("Quelles erreurs faut-il éviter pendant le tri du mil ?", "BEST_PRACTICES", None),
        ]

        for question, expected_family, expected_operation in cases:
            response = client.post(
                "/chat/agent",
                headers=headers,
                json={"message": question, "language": "fr", "conversation_id": None, "user_id": None},
            )
            assert response.status_code == 200
            payload = response.json()
            metadata = payload.get("metadata", {}) or {}
            entities = metadata.get("detected_entities", {}) or {}
            sql_trace = (
                (((metadata.get("agent_debug") or {}).get("SQLAnalyticsAgent") or {}).get("data") or {}).get("sql_dispatch_trace")
                or {}
            )

            assert entities.get("intent_family") == expected_family
            if expected_operation is not None:
                assert sql_trace.get("sql_operation") == expected_operation
            if expected_family == "BEST_PRACTICES":
                assert payload.get("route") == "RAG_ONLY"
                assert (metadata.get("answer_contract") or {}).get("route") == "RAG_ONLY"
            if expected_family in {"STOCK_CURRENT", "POSTHARVEST_AVAILABLE_LOTS", "LOSS_RANKING"}:
                warnings = payload.get("warnings") or []
                assert "La réponse signale une donnée manquante." not in warnings

        # Available lots query must not be substituted by ranking narrative.
        lots_resp = client.post(
            "/chat/agent",
            headers=headers,
            json={"message": "Quels lots post-récolte sont disponibles actuellement ?", "language": "fr"},
        )
        lots_answer = (lots_resp.json().get("answer") or "").lower()
        assert "plus de pertes" not in lots_answer

        # Explicit reset phrase must avoid stale lot follow-up context.
        first = client.post(
            "/chat/agent",
            headers=headers,
            json={"message": "Quel lot a la perte la plus élevée ?", "language": "fr"},
        )
        conv_id = (first.json().get("metadata") or {}).get("conversation_id")
        reset = client.post(
            "/chat/agent",
            headers=headers,
            json={
                "message": "Maintenant oublie ce lot et parle-moi seulement du stock de mangue.",
                "language": "fr",
                "conversation_id": conv_id,
            },
        )
        reset_payload = reset.json()
        reset_meta = reset_payload.get("metadata", {}) or {}
        assert reset_payload.get("route") == "SQL_ONLY"
        assert (reset_meta.get("detected_entities") or {}).get("intent_family") == "STOCK_CURRENT"

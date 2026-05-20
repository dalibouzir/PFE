from __future__ import annotations

import pytest

from app.ai.orchestrator.intent_router import IntentRouter
from app.ai.schemas.agent_schemas import AgentRoute


router = IntentRouter()


def _assert_route_and_family(query: str, expected_route: AgentRoute, expected_family: str):
    decision = router.classify(query)
    assert decision.route == expected_route
    assert decision.detected_entities.get("intent_family") == expected_family


@pytest.mark.parametrize(
    "query",
    [
        "Stock actuel par produit ?",
        "Donne-moi l'inventaire courant de la coopérative.",
        "Combien reste-t-il en stock aujourd'hui ?",
        "Vue rapide des stocks disponibles maintenant.",
        "Etat stock mangue + arachide, s'il te plaît.",
    ],
)
def test_stock_current_paraphrases(query: str):
    _assert_route_and_family(query, AgentRoute.SQL_ONLY, "STOCK_CURRENT")


@pytest.mark.parametrize(
    "query",
    [
        "Quels sont les lots post-récolte disponibles ?",
        "Liste les lots disponibles en post récolte.",
        "Je veux les postharvest lots available.",
        "Montre les lots enregistrés après récolte.",
        "Lots disponibles de transformation, stp.",
    ],
)
def test_postharvest_available_lots_paraphrases(query: str):
    _assert_route_and_family(query, AgentRoute.SQL_ONLY, "POSTHARVEST_AVAILABLE_LOTS")


@pytest.mark.parametrize(
    "query",
    [
        "Quels lots ont les pertes les plus élevées ?",
        "Top lots avec le pire rendement.",
        "Classement des lots les plus pénalisés.",
        "Quels sont les lots les moins efficaces ?",
        "Donne le ranking des pertes par lot.",
    ],
)
def test_loss_ranking_paraphrases(query: str):
    _assert_route_and_family(query, AgentRoute.SQL_ONLY, "LOSS_RANKING")


@pytest.mark.parametrize(
    "query",
    [
        "Quel lot a le plus grand écart entre entrée et sortie ?",
        "Montre le gap input/output par lot.",
        "Différence entrée sortie la plus forte ?",
        "Comparatif entrée vs sortie des lots.",
        "Où l'écart matière est maximal ?",
    ],
)
def test_input_output_gap_paraphrases(query: str):
    _assert_route_and_family(query, AgentRoute.SQL_ONLY, "INPUT_OUTPUT_GAP")


@pytest.mark.parametrize(
    "query",
    [
        "Quelles sont les étapes pré-récolte enregistrées ?",
        "Historique pré-récolte des parcelles.",
        "Statut pre-harvest des cultures ?",
        "Où en sont les parcelles avant récolte ?",
        "Lifecycle pré récolte par parcelle.",
    ],
)
def test_preharvest_steps_paraphrases(query: str):
    _assert_route_and_family(query, AgentRoute.SQL_ONLY, "PREHARVEST_STEPS")


@pytest.mark.parametrize(
    "query",
        [
            "Quelles bonnes pratiques appliquer avant l'emballage ?",
            "Conseils de séchage et tri pour la qualité produit.",
            "Meilleures pratiques post-récolte, version simple.",
            "Procédure recommandée avant conditionnement ?",
            "Check-list qualité avant emballage.",
    ],
)
def test_best_practices_paraphrases(query: str):
    _assert_route_and_family(query, AgentRoute.RAG_ONLY, "BEST_PRACTICES")


@pytest.mark.parametrize(
    "query",
    [
        "Quels lots présentent un risque élevé ?",
        "Y a-t-il des anomalies critiques sur les lots ?",
        "Lots dangereux selon la prédiction ?",
        "Probabilité de risque par lot aujourd'hui ?",
        "Quels batches sont classés high risk ?",
    ],
)
def test_risk_analysis_paraphrases(query: str):
    _assert_route_and_family(query, AgentRoute.HYBRID_SQL_ML, "RISK_ANALYSIS")


@pytest.mark.parametrize(
    "query",
    [
        "Que recommandes-tu pour réduire les pertes ?",
        "Quelles actions appliquer dès cette semaine ?",
        "On fait quoi concrètement pour améliorer l'efficacité ?",
        "Plan d'action pour limiter les pertes de lots.",
        "Donne des actions prioritaires pour cette coopérative.",
    ],
)
def test_recommendation_paraphrases(query: str):
    decision = router.classify(query)
    assert decision.detected_entities.get("intent_family") == "RECOMMENDATION"
    assert decision.route in {AgentRoute.HYBRID_FULL, AgentRoute.RECOMMENDATION_ONLY}


def test_negative_available_lots_not_loss_ranking():
    decision = router.classify("lots disponibles")
    assert decision.detected_entities.get("intent_family") == "POSTHARVEST_AVAILABLE_LOTS"


def test_negative_loss_ranking_not_available_lots():
    decision = router.classify("pertes les plus élevées")
    assert decision.detected_entities.get("intent_family") == "LOSS_RANKING"


def test_negative_best_practices_not_sql_only():
    decision = router.classify("bonnes pratiques de séchage")
    assert decision.route == AgentRoute.RAG_ONLY


def test_negative_risk_not_simple_loss_ranking():
    decision = router.classify("lots à risque élevé")
    assert decision.route == AgentRoute.HYBRID_SQL_ML


def test_negative_pourquoi_specific_lot_not_generic_rag():
    decision = router.classify("Pourquoi le lot MANG-004 a une mauvaise efficacité ?")
    assert decision.route == AgentRoute.HYBRID_SQL_RAG
    assert decision.detected_entities.get("intent_family") == "EXPLANATION_CAUSAL"


def test_followup_changes_product_avoids_unsafe_reuse():
    decision = router.classify(
        "Et pour le même produit, quelles actions appliquer ?",
        previous_user_query="Analyse le lot MANG-004 de mangue",
        known_batch_refs={"MANG-004", "ARACH-001"},
    )
    assert decision.detected_entities.get("intent_family") == "FOLLOW_UP"
    assert decision.route in {AgentRoute.HYBRID_FULL, AgentRoute.HYBRID_SQL_RAG, AgentRoute.HYBRID_SQL_ML, AgentRoute.SQL_ONLY}


@pytest.mark.parametrize(
    ("question", "family", "route"),
    [
        ("Quel est le stock actuel par produit ?", "STOCK_CURRENT", AgentRoute.SQL_ONLY),
        ("Quels sont les lots post-récolte disponibles dans cette coopérative ?", "POSTHARVEST_AVAILABLE_LOTS", AgentRoute.SQL_ONLY),
        ("Quels lots ont les pertes les plus élevées ?", "LOSS_RANKING", AgentRoute.SQL_ONLY),
        ("Quels lots ont le plus grand écart entre entrée et sortie ?", "INPUT_OUTPUT_GAP", AgentRoute.SQL_ONLY),
        ("Quelles sont les étapes pré-récolte enregistrées ?", "PREHARVEST_STEPS", AgentRoute.SQL_ONLY),
        ("Quelles bonnes pratiques appliquer avant l’emballage ?", "BEST_PRACTICES", AgentRoute.RAG_ONLY),
        ("Quels lots présentent un risque élevé ?", "RISK_ANALYSIS", AgentRoute.HYBRID_SQL_ML),
        ("Que recommandes-tu pour réduire les pertes ?", "RECOMMENDATION", AgentRoute.HYBRID_FULL),
        ("Pourquoi ce lot a une mauvaise efficacité ?", "EXPLANATION_CAUSAL", AgentRoute.HYBRID_SQL_RAG),
        ("Et pour le même produit, quelles actions appliquer ?", "FOLLOW_UP", AgentRoute.HYBRID_FULL),
    ],
)
def test_smoke_questions_route_contracts(question: str, family: str, route: AgentRoute):
    previous = "Analyse le lot MANG-004" if family == "FOLLOW_UP" else None
    decision = router.classify(question, previous_user_query=previous)
    assert decision.detected_entities.get("intent_family") == family
    assert decision.route == route

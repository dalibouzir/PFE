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
        "Quels lots sont encore utilisables pour lancer une transformation ?",
        "Liste-moi uniquement les lots prêts pour la post-récolte, sans parler des pertes.",
        "Quels lots sont prêts à transformer ?",
        "Lots disponibles à traiter actuellement ?",
        "Lots avec quantité restante pour transformation ?",
    ],
)
def test_postharvest_available_lots_generalization(query: str):
    _assert_route_and_family(query, AgentRoute.SQL_ONLY, "POSTHARVEST_AVAILABLE_LOTS")


def test_postharvest_available_lots_low_remaining_quantity_phrase():
    decision = router.classify("Quels lots sont prêts à traiter mais avec peu de quantité restante ?")
    assert decision.route == AgentRoute.SQL_ONLY
    assert decision.detected_entities.get("intent_family") == "POSTHARVEST_AVAILABLE_LOTS"


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
        "Quels lots ont les plus fortes pertes ?",
        "Classe les lots par taux de perte.",
        "Donne les lots avec le taux de perte le plus élevé.",
        "Quels lots ont perdu le plus en pourcentage ?",
        "Quels lots ont les pertes les plus élevées ? Donne entrée sortie perte.",
    ],
)
def test_loss_ranking_additional_paraphrases(query: str):
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
        "Classe les lots par écart de matière en kg.",
        "Classe les lots par perte en kg.",
        "Range les lots selon la quantité perdue.",
        "Classe les lots par différence entrée sortie.",
    ],
)
def test_input_output_gap_material_gap_variants(query: str):
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
    ("query", "expected_route"),
    [
        ("Quelles erreurs faut-il éviter pendant le tri du mil ?", AgentRoute.RAG_ONLY),
        ("Bonnes pratiques de tri du mil ?", AgentRoute.RAG_ONLY),
        ("Conseils et checklist pour le tri ?", AgentRoute.RAG_ONLY),
    ],
)
def test_advice_phrasing_routes_to_rag(query: str, expected_route: AgentRoute):
    decision = router.classify(query)
    assert decision.route == expected_route


@pytest.mark.parametrize(
    "query",
    [
        "Quelle étape perd le plus ?",
        "Combien de perte au tri ?",
        "Quel taux de perte pendant le tri ?",
    ],
)
def test_loss_analysis_phrasing_stays_sql(query: str):
    decision = router.classify(query)
    assert decision.route == AgentRoute.SQL_ONLY
    assert decision.detected_entities.get("intent_family") not in {"BEST_PRACTICES", "EXPLANATION_CAUSAL"}


@pytest.mark.parametrize(
    "query",
    [
        "Compare LOT-MILX-001 et LOT-MANG-001 en perte et efficacité.",
        "Comparaison des lots LOT-A et LOT-B sur perte/efficacité.",
    ],
)
def test_lot_comparison_routes_to_sql(query: str):
    decision = router.classify(query)
    assert decision.route == AgentRoute.SQL_ONLY
    assert decision.detected_entities.get("intent_family") == "LOT_COMPARISON"


@pytest.mark.parametrize(
    "query",
    [
        "À quelle étape LOT-MILX-001 perd le plus de matière ?",
        "Quelle étape a la plus mauvaise efficacité dans les lots post-récolte ?",
    ],
)
def test_stage_loss_analysis_routes_to_sql(query: str):
    decision = router.classify(query)
    assert decision.route == AgentRoute.SQL_ONLY
    assert decision.detected_entities.get("intent_family") == "STAGE_LOSS_ANALYSIS"


@pytest.mark.parametrize(
    "query",
    [
        "Comment réduire les pertes pendant le séchage ?",
        "Comment améliorer le rendement pendant le tri ?",
        "Que faire pour limiter les pertes à l’emballage ?",
        "Pourquoi les pertes sont élevées au séchage ?",
    ],
)
def test_hybrid_sql_rag_advisory_loss_routes_with_operational_grounding(query: str):
    decision = router.classify(query)
    assert decision.route == AgentRoute.HYBRID_SQL_RAG
    assert decision.detected_entities.get("intent_family") == "EXPLANATION_CAUSAL"


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


def test_lot_specific_recommendation_routes_hybrid_full():
    decision = router.classify("Donne-moi 3 actions concrètes pour réduire les pertes de LOT-MILX-001 avec les preuves utilisées.")
    assert decision.route == AgentRoute.HYBRID_FULL
    assert decision.detected_entities.get("intent_family") == "LOT_SPECIFIC_RECOMMENDATION"


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


def test_followup_marker_with_recommendation_prefers_followup_route():
    decision = router.classify("Et pour ce lot, quelles actions appliquer ?")
    assert decision.detected_entities.get("intent_family") == "FOLLOW_UP"
    assert decision.route == AgentRoute.HYBRID_FULL


def test_reset_phrase_avoids_followup_and_routes_stock():
    decision = router.classify(
        "Maintenant oublie ce lot et parle-moi seulement du stock de mangue.",
        previous_user_query="Quel lot a la perte la plus élevée ?",
    )
    assert decision.route == AgentRoute.SQL_ONLY
    assert decision.detected_entities.get("intent_family") == "STOCK_CURRENT"


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

from app.ai.orchestrator.intent_router import IntentRouter
from app.ai.schemas.agent_schemas import AgentRoute


router = IntentRouter()


def test_stock_question_routes_sql_only():
    decision = router.classify("Quel est le stock actuel de mangue ?")
    assert decision.route == AgentRoute.SQL_ONLY
    assert "SQLAnalyticsAgent" in decision.required_agents


def test_loss_best_practice_question_routes_hybrid_sql_rag():
    decision = router.classify("Explique comment réduire les pertes pendant le séchage.")
    assert decision.route == AgentRoute.HYBRID_SQL_RAG
    assert decision.required_agents == ["SQLAnalyticsAgent", "RAGKnowledgeAgent"]


def test_anomaly_question_routes_hybrid_sql_ml():
    decision = router.classify("Y a-t-il une anomalie dans les pertes du lot MANG-004 ?")
    assert decision.route == AgentRoute.HYBRID_SQL_ML
    assert "SQLAnalyticsAgent" in decision.required_agents
    assert "MLLossAgent" in decision.required_agents


def test_full_analysis_routes_hybrid_full():
    decision = router.classify("Analyse la situation de la coopérative aujourd’hui et donne-moi des actions.")
    assert decision.route == AgentRoute.HYBRID_FULL
    assert set(decision.required_agents) == {
        "SQLAnalyticsAgent",
        "MLLossAgent",
        "RAGKnowledgeAgent",
        "RecommendationAgent",
    }


def test_indirect_action_question_routes_hybrid_full():
    decision = router.classify("On devrait faire quoi maintenant pour limiter les pertes ?")
    assert decision.route == AgentRoute.HYBRID_FULL
    assert "RecommendationAgent" in decision.required_agents


def test_stock_plus_best_practice_routes_hybrid_sql_rag():
    decision = router.classify("Donne le stock actuel et comment améliorer le séchage de la mangue.")
    assert decision.route == AgentRoute.HYBRID_SQL_RAG
    assert set(decision.required_agents) == {"SQLAnalyticsAgent", "RAGKnowledgeAgent"}


def test_greeting_routes_small_talk():
    decision = router.classify("Bonjour")
    assert decision.route == AgentRoute.SMALL_TALK


def test_salut_cava_routes_small_talk():
    decision = router.classify("salut cava")
    assert decision.route == AgentRoute.SMALL_TALK


def test_capability_question_routes_small_talk():
    decision = router.classify("tu peux m’aider à faire quoi ?")
    assert decision.route == AgentRoute.SMALL_TALK


def test_indirect_conseil_question_routes_non_sql_only():
    decision = router.classify("J’ai un problème de pertes, tu me conseilles quoi ?")
    assert decision.route in {AgentRoute.HYBRID_FULL, AgentRoute.HYBRID_SQL_RAG, AgentRoute.RECOMMENDATION_ONLY}
    assert decision.route != AgentRoute.SQL_ONLY


def test_referential_followup_routes_operational():
    decision = router.classify("et celui-ci ?")
    assert decision.route in {AgentRoute.SQL_ONLY, AgentRoute.HYBRID_SQL_RAG, AgentRoute.HYBRID_FULL}
    assert decision.route != AgentRoute.OUT_OF_SCOPE


def test_unrelated_question_routes_out_of_scope():
    decision = router.classify("Who won the Champions League?")
    assert decision.route == AgentRoute.OUT_OF_SCOPE

from app.ai.orchestrator.intent_router import IntentRouter
from app.ai.schemas.agent_schemas import AgentRoute


router = IntentRouter()


def test_stock_question_routes_sql_only():
    decision = router.classify("Quel est le stock actuel de mangue ?")
    assert decision.route == AgentRoute.SQL_ONLY
    assert "SQLAnalyticsAgent" in decision.required_agents


def test_best_practice_question_routes_rag_only():
    decision = router.classify("Explique comment réduire les pertes pendant le séchage.")
    assert decision.route == AgentRoute.RAG_ONLY
    assert decision.required_agents == ["RAGKnowledgeAgent"]


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


def test_greeting_routes_small_talk():
    decision = router.classify("Bonjour")
    assert decision.route == AgentRoute.SMALL_TALK


def test_unrelated_question_routes_out_of_scope():
    decision = router.classify("Who won the Champions League?")
    assert decision.route == AgentRoute.OUT_OF_SCOPE

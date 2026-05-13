from app.ai.orchestrator.response_verifier import ResponseVerifier
from app.ai.schemas.agent_schemas import AgentContext, AgentResult, AgentRoute


def _context(route: AgentRoute) -> AgentContext:
    return AgentContext(user_query="q", language="fr", route=route)


def test_numeric_answer_without_sql_or_ml_source_adds_warning():
    verifier = ResponseVerifier()
    result = verifier.verify(
        context=_context(AgentRoute.SQL_ONLY),
        answer="Le stock est de 120 kg.",
        route=AgentRoute.SQL_ONLY,
        results=[
            AgentResult(
                agent_name="RAGKnowledgeAgent",
                route=AgentRoute.RAG_ONLY,
                answer_part="",
                data={},
                sources=[{"type": "rag", "title": "x"}],
                confidence=0.8,
                warnings=[],
                execution_time_ms=1,
            )
        ],
    )
    assert "NUMERIC_CLAIMS_NOT_GROUNDED" in result.warnings


def test_recommendation_without_evidence_adds_warning():
    verifier = ResponseVerifier()
    result = verifier.verify(
        context=_context(AgentRoute.RECOMMENDATION_ONLY),
        answer="Recommandation: faire une action.",
        route=AgentRoute.RECOMMENDATION_ONLY,
        results=[
            AgentResult(
                agent_name="RecommendationAgent",
                route=AgentRoute.RECOMMENDATION_ONLY,
                answer_part="",
                data={"recommendations": [{"title": "A", "evidence": []}]},
                sources=[],
                confidence=0.6,
                warnings=[],
                execution_time_ms=1,
            )
        ],
    )
    assert "RECOMMENDATION_WITHOUT_EVIDENCE" in result.warnings


def test_rag_route_without_rag_source_adds_warning():
    verifier = ResponseVerifier()
    result = verifier.verify(
        context=_context(AgentRoute.RAG_ONLY),
        answer="Explication textuelle.",
        route=AgentRoute.RAG_ONLY,
        results=[],
    )
    assert "MISSING_RAG_SOURCE" in result.warnings

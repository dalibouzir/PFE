from __future__ import annotations

from app.ai.orchestrator.source_formatter import build_source_contract
from app.ai.schemas.agent_schemas import AgentResult, AgentRoute


def _result(*, agent_name: str, route: AgentRoute, sources: list[dict]) -> AgentResult:
    return AgentResult(
        agent_name=agent_name,
        route=route,
        answer_part="",
        data={},
        sources=sources,
        confidence=0.8,
        warnings=[],
        execution_time_ms=1,
    )


def test_sql_only_contract_drops_ml_source_pollution():
    sql_result = _result(
        agent_name="SQLAnalyticsAgent",
        route=AgentRoute.SQL_ONLY,
        sources=[{"type": "sql", "table": "members", "label": "Liste des membres", "record_count": 4}],
    )
    accidental_ml = _result(
        agent_name="UnknownAgent",
        route=AgentRoute.SQL_ONLY,
        sources=[{"type": "ml", "model": "ml_signal", "risk_level": "UNKNOWN"}],
    )
    sources, _warnings = build_source_contract(route=AgentRoute.SQL_ONLY, agent_results=[sql_result, accidental_ml])
    types = {str(item.get("type") or "").lower() for item in sources}
    assert "sql" in types
    assert "ml" not in types


def test_ml_only_contract_keeps_ml_source():
    ml_result = _result(
        agent_name="MLLossAgent",
        route=AgentRoute.ML_ONLY,
        sources=[{"type": "ml", "model": "loss_anomaly_detector", "risk_level": "HIGH"}],
    )
    sources, _warnings = build_source_contract(route=AgentRoute.ML_ONLY, agent_results=[ml_result])
    types = {str(item.get("type") or "").lower() for item in sources}
    assert "ml" in types

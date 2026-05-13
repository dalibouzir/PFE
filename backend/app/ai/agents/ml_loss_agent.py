from __future__ import annotations

import time

from app.ai.agents.base_agent import BaseAgent
from app.ai.schemas.agent_schemas import AgentContext, AgentResult
from app.ai.tools.ml_tools import MLTools


class MLLossAgent(BaseAgent):
    name = "MLLossAgent"
    description = "Runs anomaly and loss risk analysis with uncertainty exposure."

    def __init__(self, ml_tools: MLTools):
        self.ml_tools = ml_tools

    async def run(self, query: str, context: AgentContext) -> AgentResult:
        start = time.perf_counter()
        entities = context.detected_entities or {}
        batch_ref = entities.get("batch_ref")
        stage = (entities.get("stage") or [None])[0] if isinstance(entities.get("stage"), list) else entities.get("stage")

        result = self.ml_tools.analyze_loss_risk(batch_ref=batch_ref, stage=stage)
        warnings = result.get("warnings", [])
        confidence = float(result.get("confidence", 0.4))

        answer = (
            f"Risque {_format_risk_level(result.get('risk_level'))}"
            + (" avec anomalie détectée." if result.get("anomaly_detected") else " sans anomalie confirmée.")
        )

        return AgentResult(
            agent_name=self.name,
            route=context.route,
            answer_part=answer,
            data=result,
            sources=result.get("sources", []),
            confidence=confidence,
            warnings=warnings,
            execution_time_ms=int((time.perf_counter() - start) * 1000),
        )


def _format_risk_level(value) -> str:
    normalized = str(value or "").strip().upper()
    labels = {
        "LOW": "faible",
        "MEDIUM": "moyen",
        "HIGH": "élevé",
        "UNKNOWN": "non confirmé",
    }
    return labels.get(normalized, str(value or "non confirmé"))

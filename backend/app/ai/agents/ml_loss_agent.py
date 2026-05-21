from __future__ import annotations

import time
import re
import unicodedata

from app.ai.agents.base_agent import BaseAgent
from app.ai.schemas.agent_schemas import AgentContext, AgentResult
from app.ai.tools.ml_tools import MLTools

EVIDENCE_HAS = "HAS_EVIDENCE"
EVIDENCE_NO_DATA = "PROVEN_NO_DATA"
EVIDENCE_PARTIAL = "PARTIAL_EVIDENCE"


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
        lowered = str(query or "").lower()
        normalized = _normalize_text(query)

        asks_max_anomaly = (
            ("anomaly_score" in normalized and any(token in normalized for token in ("plus grand", "max", "plus eleve", "plus élevé", "top")))
            or ("lot" in normalized and "anormal" in normalized and "ml" in normalized)
            or ("anomaly" in normalized and "lot" in normalized and any(token in normalized for token in ("plus", "max", "top", "eleve", "élevé")))
        )
        if asks_max_anomaly:
            result = self.ml_tools.max_anomaly_score_lot()
            rows = result.get("data", []) or []
            evidence_status = str(result.get("evidence_status") or (EVIDENCE_HAS if rows else EVIDENCE_NO_DATA))
            answer = (
                f"Lot avec anomaly_score max: {rows[0].get('lot_code')} ({float(rows[0].get('anomaly_score', 0.0)):.4f})."
                if rows
                else "Aucun signal ML élevé n’est enregistré dans les journaux disponibles. Cela ne signifie pas absence de risque, seulement absence de signal ML enregistré."
            )
            return AgentResult(
                agent_name=self.name,
                route=context.route,
                answer_part=answer,
                data={"max_anomaly_score_lot": rows, "evidence_status": evidence_status},
                sources=result.get("sources", []),
                confidence=0.86 if rows else 0.72,
                warnings=result.get("warnings", []),
                execution_time_ms=int((time.perf_counter() - start) * 1000),
            )
        asks_high_count = (
            "combien" in normalized
            and "high" in normalized
            and ("ml" in normalized or "modele" in normalized)
            and (re.search(r"\bsigna(?:l|ux)\b", normalized) or "alerte" in normalized or "alertes" in normalized)
        )
        if asks_high_count:
            days = _extract_days(normalized, default=60)
            result = self.ml_tools.ml_high_signal_count(days=days)
            rows = result.get("data", []) or []
            count = int(rows[0].get("high_signal_count", 0) or 0) if rows else 0
            evidence_status = str(result.get("evidence_status") or (EVIDENCE_HAS if count > 0 else EVIDENCE_NO_DATA))
            if rows and count > 0:
                answer = f"Signaux ML HIGH sur {days} jours: {count}."
            else:
                answer = "Aucun signal ML élevé n’est enregistré dans les journaux disponibles. Cela ne signifie pas absence de risque, seulement absence de signal ML enregistré."
            return AgentResult(
                agent_name=self.name,
                route=context.route,
                answer_part=answer,
                data={"ml_high_signal_count": rows, "evidence_status": evidence_status},
                sources=result.get("sources", []),
                confidence=0.84 if rows and count > 0 else 0.72,
                warnings=result.get("warnings", []),
                execution_time_ms=int((time.perf_counter() - start) * 1000),
            )

        asks_anomaly_chart = (
            any(token in normalized for token in ("graph", "graphe", "graphique", "chart"))
            and "anomaly_score" in normalized
            and any(token in normalized for token in ("lot", "lots", "batch"))
        )
        if asks_anomaly_chart:
            limit = _extract_top_limit(normalized, default=5)
            result = self.ml_tools.get_ml_insight_summary()
            rows = result.get("data", []) or []
            rows = sorted(rows, key=lambda row: float(row.get("anomaly_score", 0.0) or 0.0), reverse=True)[:limit]
            answer = (
                f"Top {limit} anomaly_score ML par lot prêt."
                if rows
                else "Donnée non disponible pour cette requête précise."
            )
            return AgentResult(
                agent_name=self.name,
                route=context.route,
                answer_part=answer,
                data={"ml_insight_summary": rows, "evidence_status": str(result.get("evidence_status") or (EVIDENCE_HAS if rows else EVIDENCE_NO_DATA))},
                sources=result.get("sources", []),
                confidence=0.8 if rows else 0.72,
                warnings=result.get("warnings", []),
                execution_time_ms=int((time.perf_counter() - start) * 1000),
            )

        result = self.ml_tools.analyze_loss_risk(batch_ref=batch_ref, stage=stage)
        warnings = result.get("warnings", [])
        evidence_status = str(result.get("evidence_status") or EVIDENCE_PARTIAL)
        confidence = float(result.get("confidence", 0.4))

        if evidence_status == EVIDENCE_NO_DATA:
            answer = "Aucun signal ML élevé n’est enregistré dans les journaux disponibles. Cela ne signifie pas absence de risque, seulement absence de signal ML enregistré."
        else:
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


def _normalize_text(value: str) -> str:
    raw = str(value or "").lower()
    raw = unicodedata.normalize("NFKD", raw)
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return " ".join(raw.split())


def _extract_days(text: str, default: int) -> int:
    match = re.search(r"(\d+)\s*jour", text)
    if match:
        return max(1, int(match.group(1)))
    match = re.search(r"(\d+)\s*mois", text)
    if match:
        return max(1, int(match.group(1)) * 30)
    return default


def _extract_top_limit(text: str, default: int) -> int:
    match = re.search(r"\btop\s*(\d+)\b", text)
    if match:
        return max(1, min(int(match.group(1)), 20))
    match = re.search(r"\b(\d+)\s+lots?\b", text)
    if match:
        return max(1, min(int(match.group(1)), 20))
    return default

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.ai.orchestrator.agent_context import build_agent_context
from app.ai.orchestrator.agent_registry import AgentRegistry
from app.ai.orchestrator.agent_types import IntentRouteDecision
from app.ai.orchestrator.audit_logger import AuditLogger
from app.ai.orchestrator.confidence import compute_final_confidence
from app.ai.orchestrator.intent_router import IntentRouter
from app.ai.orchestrator.evidence_pipeline import (
    build_evidence_pack,
    collapse_user_warning_items,
    compose_answer,
    plan_answer,
    verify_evidence,
)
from app.ai.orchestrator.response_verifier import ResponseVerifier
from app.ai.orchestrator.source_formatter import build_source_contract, merge_and_dedupe_sources
from app.ai.schemas.agent_schemas import AgentResult, AgentRoute, FinalAgentResponse
from app.models.user import User
from app.models.batch import Batch
from app.models.chat import ChatMessage

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """This module implements a lightweight domain-specific agent orchestration layer inspired by modern multi-agent systems such as Ruflo.

    It adapts routing, specialized agents, memory, retrieval, and verification to a cooperative decision-support assistant
    with controlled tool execution, grounded response generation, hybrid SQL/RAG/ML reasoning, response verification,
    and auditability.
    """

    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.current_user = current_user
        self.router = IntentRouter()
        self.registry = AgentRegistry(db, current_user)
        self.verifier = ResponseVerifier()
        self.audit_logger = AuditLogger(db)

    async def handle(
        self,
        *,
        message: str,
        language: str | None,
        conversation_id: str | None,
        user_id: str | None,
    ) -> FinalAgentResponse:
        started_at = time.perf_counter()
        route_started_at = time.perf_counter()
        previous_user_query = self._get_previous_user_message(conversation_id) if conversation_id else None
        pre_route_entities: dict = {}
        if conversation_id and _needs_pre_route_memory_handoff(message) and not _is_reset_phrase(previous_user_query or ""):
            pre_route_entities = await self._pre_route_memory_entities(
                message=message,
                conversation_id=conversation_id,
                language=language,
            )
            memory_batch_ref = str(pre_route_entities.get("batch_ref") or "").strip().upper()
            if memory_batch_ref:
                if previous_user_query:
                    previous_user_query = f"{previous_user_query} || {memory_batch_ref}"
                else:
                    previous_user_query = memory_batch_ref
        decision: IntentRouteDecision = self.router.classify(
            message,
            language_hint=language,
            known_batch_refs=self._known_batch_refs(),
            previous_user_query=previous_user_query,
        )
        if pre_route_entities:
            merged_detected = dict(pre_route_entities)
            merged_detected.update(decision.detected_entities or {})
            decision.detected_entities = merged_detected
        route_ms = int((time.perf_counter() - route_started_at) * 1000)

        context_started_at = time.perf_counter()
        context = build_agent_context(
            query=message,
            language=decision.detected_entities.get("language") or (language or "fr"),
            decision=decision,
            conversation_id=conversation_id,
            user_id=user_id,
            previous_messages=None,
        )
        context_ms = int((time.perf_counter() - context_started_at) * 1000)

        warnings_from_runtime: list[str] = []
        agent_timings: list[dict[str, int | str]] = []
        timeout_s = _agent_timeout_seconds()

        if conversation_id:
            memory_started_at = time.perf_counter()
            try:
                memory_result = await asyncio.wait_for(
                    self.registry.memory_agent.run(message, context),
                    timeout=_memory_timeout_seconds(),
                )
                context.detected_entities = memory_result.data.get("entities", context.detected_entities)
            except TimeoutError:
                warnings_from_runtime.append("MEMORY_TIMEOUT")
            except Exception:
                warnings_from_runtime.append("MEMORY_ERROR")
            memory_ms = int((time.perf_counter() - memory_started_at) * 1000)
        else:
            memory_ms = 0

        agent_results: list[AgentResult] = []
        for agent in self.registry.agents_for_route(decision.route):
            agent_label = str(getattr(agent, "name", agent.__class__.__name__))
            agent_started_at = time.perf_counter()
            try:
                result = await asyncio.wait_for(agent.run(message, context), timeout=timeout_s)
            except TimeoutError:
                runtime_ms = int((time.perf_counter() - agent_started_at) * 1000)
                warning_code = f"AGENT_TIMEOUT_{agent_label.upper()}"
                warnings_from_runtime.append(warning_code)
                agent_timings.append({"agent": agent_label, "execution_ms": runtime_ms, "status": "timeout"})
                result = AgentResult(
                    agent_name=agent_label,
                    route=decision.route,
                    answer_part="Couche temporairement indisponible (timeout).",
                    data={},
                    sources=[],
                    confidence=0.0,
                    warnings=[warning_code],
                    execution_time_ms=runtime_ms,
                )
            except Exception:
                runtime_ms = int((time.perf_counter() - agent_started_at) * 1000)
                warning_code = f"AGENT_ERROR_{agent_label.upper()}"
                warnings_from_runtime.append(warning_code)
                agent_timings.append({"agent": agent_label, "execution_ms": runtime_ms, "status": "error"})
                result = AgentResult(
                    agent_name=agent_label,
                    route=decision.route,
                    answer_part="Couche temporairement indisponible.",
                    data={},
                    sources=[],
                    confidence=0.0,
                    warnings=[warning_code],
                    execution_time_ms=runtime_ms,
                )
            else:
                runtime_ms = int((time.perf_counter() - agent_started_at) * 1000)
                agent_timings.append({"agent": agent_label, "execution_ms": runtime_ms, "status": "ok"})
            agent_results.append(result)
            if result.agent_name == "SQLAnalyticsAgent":
                context.sql_results = {"data": result.data, "sources": result.sources}
            elif result.agent_name == "RAGKnowledgeAgent":
                context.rag_results = result.sources
            elif result.agent_name == "MLLossAgent":
                context.ml_results = result.data
            elif result.agent_name == "RecommendationAgent":
                context.recommendation_results = result.data.get("recommendations")

        response_blocks: list[dict] = []
        evidence_metadata: dict = {}
        if decision.route in {AgentRoute.SMALL_TALK, AgentRoute.OUT_OF_SCOPE}:
            answer = _build_final_answer(
                route=decision.route,
                agent_results=agent_results,
                language=context.language,
                detected_entities=context.detected_entities,
            )
            plan_ms = evidence_pack_ms = evidence_verify_ms = compose_ms = 0
        else:
            plan_started_at = time.perf_counter()
            plan = plan_answer(
                query=message,
                detected_entities=context.detected_entities,
                route=decision.route,
            )
            plan_ms = int((time.perf_counter() - plan_started_at) * 1000)
            evidence_pack_started_at = time.perf_counter()
            evidence_pack = build_evidence_pack(
                question=message,
                plan=plan,
                route=decision.route,
                agent_results=agent_results,
            )
            evidence_pack_ms = int((time.perf_counter() - evidence_pack_started_at) * 1000)
            evidence_verify_started_at = time.perf_counter()
            evidence_verification = verify_evidence(evidence_pack)
            evidence_verify_ms = int((time.perf_counter() - evidence_verify_started_at) * 1000)
            compose_started_at = time.perf_counter()
            answer, response_blocks, evidence_metadata = compose_answer(evidence_pack, evidence_verification)
            compose_ms = int((time.perf_counter() - compose_started_at) * 1000)
            if str(answer or "").strip() == "Donnée non disponible pour cette requête précise.":
                sql_result = _find_agent(agent_results, "SQLAnalyticsAgent")
                if sql_result and "Je n’ai pas trouvé de lot avec la référence" in str(sql_result.answer_part or ""):
                    lot_match = re.search(r"référence\s+([A-Za-z0-9\-_]+)\.?$", str(sql_result.answer_part))
                    if lot_match:
                        lot = lot_match.group(1).upper()
                        answer = f"Je n’ai pas trouvé de lot avec la référence {lot}."
                    else:
                        answer = str(sql_result.answer_part)
            sql_result = _find_agent(agent_results, "SQLAnalyticsAgent")
            normalized_message = (message or "").lower()
            if (
                sql_result
                and ("étape" in normalized_message or "etape" in normalized_message)
                and ("plus de pertes" in normalized_message or "cause le plus" in normalized_message)
                and str(sql_result.answer_part or "").strip()
            ):
                answer = str(sql_result.answer_part)

            # Keep the previous text builder as a fallback guard if composition returns an empty body.
            if not str(answer or "").strip():
                answer = _build_final_answer(
                    route=decision.route,
                    agent_results=agent_results,
                    language=context.language,
                    detected_entities=context.detected_entities,
                )

        verify_started_at = time.perf_counter()
        verification = self.verifier.verify(
            context=context,
            answer=answer,
            route=decision.route,
            results=agent_results,
        )
        verify_ms = int((time.perf_counter() - verify_started_at) * 1000)

        rag_insufficient_answer = "Je n’ai pas assez de contexte documentaire fiable pour répondre précisément à cette question."
        if (
            verification.missing_expected_source
            and decision.route not in {AgentRoute.SMALL_TALK, AgentRoute.OUT_OF_SCOPE}
            and str(answer or "").strip() != rag_insufficient_answer
        ):
            if "Les données disponibles ne permettent pas de confirmer ce point." not in answer:
                answer = f"{answer}\n\nLes données disponibles ne permettent pas de confirmer ce point."

        confidence_started_at = time.perf_counter()
        final_confidence = compute_final_confidence(
            agent_results=agent_results,
            route_confidence=decision.confidence,
            missing_expected_source=verification.missing_expected_source,
            weak_retrieval=verification.weak_retrieval,
            incomplete_sql=verification.incomplete_sql,
            contradiction=verification.contradiction,
            weak_ml_confidence=verification.weak_ml_confidence,
        )
        confidence_ms = int((time.perf_counter() - confidence_started_at) * 1000)

        source_started_at = time.perf_counter()
        sources, source_contract_warnings = build_source_contract(
            route=decision.route,
            agent_results=agent_results,
        )
        source_contract_ms = int((time.perf_counter() - source_started_at) * 1000)
        agents_used = [item.agent_name for item in agent_results]
        warning_codes = sorted(set([*verification.warnings, *source_contract_warnings, *warnings_from_runtime]))
        # Internal formatting marker: keep in metadata traces if needed upstream, but hide from user warning list.
        warning_codes = [code for code in warning_codes if code != "MISSING_OPERATION_RESULT"]
        warning_codes = _filter_warning_codes_for_manager(
            warning_codes=warning_codes,
            route=decision.route,
            intent_family=(context.detected_entities or {}).get("intent_family"),
            response_blocks=response_blocks,
            sources=sources,
            agent_results=agent_results,
        )
        french_warnings = collapse_user_warning_items(warning_codes)

        execution_time_ms = int((time.perf_counter() - started_at) * 1000)
        sql_ms = _sum_agent_ms(agent_timings, "SQLAnalyticsAgent")
        rag_ms = _sum_agent_ms(agent_timings, "RAGKnowledgeAgent")
        ml_ms = _sum_agent_ms(agent_timings, "MLLossAgent")
        recommendation_ms = _sum_agent_ms(agent_timings, "RecommendationAgent")
        llm_ms = compose_ms
        sql_dispatch_trace = _extract_sql_dispatch_trace(agent_results)
        metadata = {
            "execution_time_ms": execution_time_ms,
            "total_duration_ms": execution_time_ms,
            "conversation_id": conversation_id,
            "detected_entities": context.detected_entities,
            "intent_family": (context.detected_entities or {}).get("intent_family"),
            "route_explanation": decision.explanation,
            "route_confidence": decision.confidence,
            "warning_codes": warning_codes,
            "source_contract_warnings": source_contract_warnings,
            "sql_dispatch_trace": sql_dispatch_trace,
            # Compatibility alias for consumers that expect sql_operation at metadata top-level.
            "sql_operation": sql_dispatch_trace.get("sql_operation"),
            "evidence_status": _extract_evidence_status_summary(agent_results),
            "final_response_source": "evidence_pipeline",
            "timing_ms": {
                "route_planning": route_ms,
                "context_build": context_ms,
                "memory": memory_ms,
                "agents": agent_timings,
                "plan_answer": plan_ms,
                "evidence_pack": evidence_pack_ms,
                "evidence_verify": evidence_verify_ms,
                "compose_answer": compose_ms,
                "response_verify": verify_ms,
                "confidence": confidence_ms,
                "source_contract": source_contract_ms,
                "total": execution_time_ms,
            },
            "durations_ms": {
                "routing_duration_ms": route_ms,
                "sql_duration_ms": sql_ms,
                "rag_duration_ms": rag_ms,
                "ml_duration_ms": ml_ms,
                "recommendation_duration_ms": recommendation_ms,
                "llm_duration_ms": llm_ms,
                "composition_duration_ms": compose_ms,
                "total_duration_ms": execution_time_ms,
            },
            **evidence_metadata,
        }

        if execution_time_ms > 5000:
            logger.warning("chat.slow_request total_ms=%s route=%s", execution_time_ms, decision.route.value)
        if sql_ms > 1000:
            logger.warning("chat.slow_sql duration_ms=%s route=%s", sql_ms, decision.route.value)
        if rag_ms > 2000:
            logger.warning("chat.slow_rag duration_ms=%s route=%s", rag_ms, decision.route.value)
        if llm_ms > 3000:
            logger.warning("chat.slow_llm duration_ms=%s route=%s", llm_ms, decision.route.value)

        if os.environ.get("AI_AUDIT_DEBUG") == "1":
            metadata["agent_debug"] = _build_agent_debug(agent_results)

        response = FinalAgentResponse(
            answer=answer,
            route=decision.route,
            agents_used=agents_used,
            response_blocks=response_blocks,
            sources=sources,
            confidence=final_confidence,
            warnings=french_warnings,
            metadata=metadata,
        )

        self.audit_logger.log(
            current_user=self.current_user,
            conversation_id=conversation_id,
            user_query=message,
            language=context.language,
            detected_entities=context.detected_entities,
            selected_route=decision.route.value,
            route_confidence=decision.confidence,
            agents_used=agents_used,
            sources=sources,
            final_confidence=final_confidence,
            warnings=french_warnings,
            response_preview=answer,
            execution_time_ms=execution_time_ms,
        )

        return response

    async def _pre_route_memory_entities(self, *, message: str, conversation_id: str, language: str | None) -> dict:
        try:
            bootstrap_decision = IntentRouteDecision(
                route=AgentRoute.SQL_ONLY,
                confidence=0.0,
                detected_entities=self.router.entity_extractor.extract(
                    message,
                    language_hint=language,
                    known_batch_refs=self._known_batch_refs(),
                ).as_dict(),
                required_agents=["MemoryAgent"],
                explanation="pre-route-memory-handoff",
            )
            bootstrap_context = build_agent_context(
                query=message,
                language=bootstrap_decision.detected_entities.get("language") or (language or "fr"),
                decision=bootstrap_decision,
                conversation_id=conversation_id,
                user_id=None,
                previous_messages=None,
            )
            memory_result = await asyncio.wait_for(
                self.registry.memory_agent.run(message, bootstrap_context),
                timeout=_memory_timeout_seconds(),
            )
            entities = memory_result.data.get("entities")
            return dict(entities) if isinstance(entities, dict) else {}
        except Exception:
            return {}

    def _known_batch_refs(self) -> set[str]:
        if self.current_user.cooperative_id is None:
            return set()
        try:
            rows = self.db.scalars(select(Batch.code).where(Batch.cooperative_id == self.current_user.cooperative_id)).all()
        except Exception:
            return set()
        return {str(row).upper() for row in rows if str(row or "").strip()}

    def _get_previous_user_message(self, conversation_id: str | None) -> str | None:
        if not conversation_id:
            return None
        try:
            session_id = UUID(str(conversation_id))
        except ValueError:
            return None
        try:
            rows = self.db.scalars(
                select(ChatMessage.content)
                .where(ChatMessage.session_id == session_id, ChatMessage.role == "user")
                .order_by(ChatMessage.created_at.desc())
                .limit(4)
            ).all()
        except Exception:
            return None
        snippets = [str(item).strip() for item in rows if str(item or "").strip()]
        if len(snippets) <= 1:
            return None
        # The current user message is already persisted before orchestration.
        # Drop it so "previous" context only reflects earlier turns.
        snippets = snippets[1:]
        # Keep oldest->newest in the hint string to preserve conversational progression.
        snippets.reverse()
        return " || ".join(snippets)


def _build_final_answer(*, route: AgentRoute, agent_results: list[AgentResult], language: str, detected_entities: dict | None = None) -> str:
    if route in {AgentRoute.SMALL_TALK, AgentRoute.OUT_OF_SCOPE}:
        return agent_results[0].answer_part if agent_results else ""

    sql_result = _find_agent(agent_results, "SQLAnalyticsAgent")
    rag_result = _find_agent(agent_results, "RAGKnowledgeAgent")
    ml_result = _find_agent(agent_results, "MLLossAgent")
    reco_result = _find_agent(agent_results, "RecommendationAgent")

    lines = []
    lines.append("1. Résultat principal")
    entity_module = str((detected_entities or {}).get("module") or "")
    rag_primary = route == AgentRoute.RAG_ONLY or (
        route == AgentRoute.HYBRID_SQL_RAG and entity_module == "rag_knowledge"
    )

    if rag_primary and rag_result and rag_result.answer_part:
        lines.append(_summarize_rag_result(rag_result))
    elif sql_result and sql_result.answer_part:
        lines.append(sql_result.answer_part)
    elif ml_result and ml_result.answer_part:
        lines.append(ml_result.answer_part)
    elif rag_result and rag_result.answer_part:
        lines.append(_summarize_rag_result(rag_result))
    else:
        lines.append("Les données disponibles ne permettent pas de confirmer ce point.")

    lines.append("")
    lines.append("2. Explication courte")
    if ml_result:
        ml_data = ml_result.data
        sql_signal = _derive_sql_operational_signal(sql_result.data if sql_result else {})
        ml_signal = _derive_ml_signal(ml_data)
        lines.append(
            f"Lecture opérationnelle (prioritaire): {sql_signal['summary']}"
        )
        lines.append(
            f"Signal ML (secondaire): risque {ml_signal['risk_label']} | anomalie {'oui' if ml_data.get('anomaly_detected') else 'non'}."
        )
        if ml_data.get("observed_loss_pct") is not None:
            lines.append(
                f"Perte observée: {float(ml_data.get('observed_loss_pct')):.1f}% | "
                f"Perte attendue: {float(ml_data.get('expected_loss_pct') or 0.0):.1f}%"
            )
        contradiction_pattern = _is_sql_ml_contradiction_payload(sql_result.data if sql_result else {}, ml_data)
        if contradiction_pattern:
            lines.append(
                "Contradiction SQL/ML: les mesures SQL et le signal ML divergent. "
                "Décision: priorité aux mesures SQL observées; le ML reste un signal d’alerte secondaire."
            )
    elif rag_result:
        rag_summary = _summarize_rag_result(rag_result)
        if "sources de connaissance récupérées donnent un contexte post-récolte" not in rag_summary:
            lines.append(rag_summary)
        else:
            # Keep concise generic wording only when truly no chunk content is available.
            lines.append("Aucune explication détaillée n’a pu être extraite des sources RAG disponibles.")

    if reco_result and reco_result.data.get("recommendations"):
        lines.append("")
        lines.append("3. Recommandations si pertinentes")
        for idx, rec in enumerate(reco_result.data.get("recommendations", [])[:3], start=1):
            lines.append(f"{idx}. {rec.get('title')} - {rec.get('action')}")
    else:
        lines.append("")
        lines.append("3. Recommandations si pertinentes")
        lines.append("Aucune recommandation prioritaire confirmée.")

    lines.append("")
    lines.append("4. Sources utilisées")
    for source in merge_and_dedupe_sources(*[res.sources for res in agent_results])[:6]:
        if source.get("type") == "sql":
            label = _humanize_sql_table(source.get('table', 'source opérationnelle'))
            lines.append(f"- {_humanize_source_type('SQL')}: {label}")
        elif source.get("type") == "rag":
            title = source.get('title', 'source documentaire')
            lines.append(f"- {_humanize_source_type('RAG')}: {title}")
        elif source.get("type") == "ml":
            risk_level = _format_risk_level(source.get('risk_level', 'n/a'))
            lines.append(f"- {_humanize_source_type('ML')}: {risk_level}")

    warnings = sorted({warning for res in agent_results for warning in res.warnings})
    lines.append("")
    lines.append("5. Avertissements si nécessaires")
    if warnings:
        for warning in warnings:
            lines.append(f"- {_humanize_warning(warning)}")
    else:
        lines.append("Aucun avertissement critique.")

    return "\n".join(lines)


def _find_agent(agent_results: list[AgentResult], name: str) -> AgentResult | None:
    for result in agent_results:
        if result.agent_name == name:
            return result
    return None


def _summarize_rag_result(rag_result: AgentResult) -> str:
    direct = str(rag_result.answer_part or "").strip()
    if direct and "Aucune source de connaissance exploitable" not in direct:
        compact = " ".join(direct.split())
        return compact[:520] + ("..." if len(compact) > 520 else "")
    chunks = rag_result.data.get("chunks") if isinstance(rag_result.data, dict) else []
    if isinstance(chunks, list) and chunks:
        for chunk in chunks[:5]:
            content = str((chunk or {}).get("content") or "").strip()
            if content:
                compact = " ".join(content.split())
                return compact[:420] + ("..." if len(compact) > 420 else "")
    return "Les sources de connaissance récupérées donnent un contexte post-récolte, mais elles restent limitées pour cette question."


def _format_risk_level(value) -> str:
    normalized = str(value or "").strip().upper()
    labels = {
        "LOW": "faible",
        "MEDIUM": "moyen",
        "HIGH": "élevé",
        "UNKNOWN": "non confirmé",
        "NONE": "non confirmé",
        "NULL": "non confirmé",
    }
    return labels.get(normalized, str(value or "non confirmé"))


def _derive_sql_operational_signal(sql_data: dict) -> dict[str, str]:
    max_loss = None
    min_eff = None

    if isinstance(sql_data, dict):
        for row in sql_data.get("process_step_losses", []) or []:
            if isinstance(row, dict) and isinstance(row.get("loss_pct"), (int, float)):
                val = float(row.get("loss_pct"))
                max_loss = val if max_loss is None else max(max_loss, val)
        for row in sql_data.get("material_balance", []) or []:
            if isinstance(row, dict):
                if isinstance(row.get("loss_percentage"), (int, float)):
                    val = float(row.get("loss_percentage"))
                    max_loss = val if max_loss is None else max(max_loss, val)
                if isinstance(row.get("efficiency_percentage"), (int, float)):
                    val = float(row.get("efficiency_percentage"))
                    min_eff = val if min_eff is None else min(min_eff, val)
        for row in sql_data.get("batch_summary", []) or []:
            if isinstance(row, dict):
                if isinstance(row.get("loss_pct"), (int, float)):
                    val = float(row.get("loss_pct"))
                    max_loss = val if max_loss is None else max(max_loss, val)
                if isinstance(row.get("efficiency_pct"), (int, float)):
                    val = float(row.get("efficiency_pct"))
                    min_eff = val if min_eff is None else min(min_eff, val)

    if max_loss is None and min_eff is None:
        return {"risk_level": "unknown", "summary": "pas de mesure SQL exploitable sur pertes/efficacité."}
    if (max_loss is not None and max_loss >= 12.0) or (min_eff is not None and min_eff <= 85.0):
        return {
            "risk_level": "high",
            "summary": f"pertes/efficacité mesurées indiquent un risque élevé (perte max {float(max_loss or 0.0):.1f}% ; efficacité min {float(min_eff or 0.0):.1f}%).",
        }
    return {
        "risk_level": "low",
        "summary": f"mesures SQL stables (perte max {float(max_loss or 0.0):.1f}% ; efficacité min {float(min_eff or 0.0):.1f}%).",
    }


def _derive_ml_signal(ml_data: dict) -> dict[str, str]:
    risk_text = str(ml_data.get("risk_level") or "").strip().upper()
    if risk_text in {"HIGH", "ELEVÉ", "ELEVEE"}:
        return {"risk_level": "high", "risk_label": "élevé"}
    if risk_text in {"LOW", "FAIBLE"}:
        return {"risk_level": "low", "risk_label": "faible"}
    if risk_text in {"MEDIUM", "MOYEN"}:
        return {"risk_level": "medium", "risk_label": "moyen"}
    return {"risk_level": "unknown", "risk_label": "non confirmé"}


def _is_sql_ml_contradiction_payload(sql_data: dict, ml_data: dict) -> bool:
    sql_values = _flatten_numeric_values(sql_data)
    ml_values = _flatten_numeric_values(ml_data)
    if not sql_values or not ml_values:
        return False
    sql_span = max(sql_values) - min(sql_values)
    ml_span = max(ml_values) - min(ml_values)
    if sql_span <= 0 or ml_span <= 0:
        return False
    return abs(max(sql_values) - max(ml_values)) > max(5.0, sql_span * 0.5)


def _flatten_numeric_values(payload) -> list[float]:
    values: list[float] = []
    stack = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
        elif isinstance(current, (int, float)):
            values.append(float(current))
    return values


def _agent_timeout_seconds() -> float:
    raw = os.environ.get("AGENT_LAYER_TIMEOUT_SECONDS", "").strip()
    try:
        value = float(raw) if raw else 25.0
    except ValueError:
        value = 25.0
    return max(5.0, min(value, 120.0))


def _memory_timeout_seconds() -> float:
    raw = os.environ.get("AGENT_MEMORY_TIMEOUT_SECONDS", "").strip()
    try:
        value = float(raw) if raw else 8.0
    except ValueError:
        value = 8.0
    return max(2.0, min(value, 30.0))


def _humanize_warning(value) -> str:
    text = str(value or "").strip()
    if not text:
        return "Un avertissement non précisé a été détecté."
    mapping = {
        "INCOMPLETE_SQL_DATA": "Les données opérationnelles sont incomplètes.",
        "SQL_DATA_INCOMPLETE": "Les données opérationnelles sont incomplètes.",
        "NO_SQL_DATA": "Aucune donnée opérationnelle exploitable n’a été trouvée pour cette recherche.",
        "WEAK_ML_CONFIDENCE": "La confiance du modèle ML est limitée.",
        "ML_SERVICE_UNAVAILABLE": "L’analyse ML n’est pas disponible avec les données actuelles.",
        "NO_MATCHING_BATCH_FOR_ML": "Le modèle ML n’a pas trouvé le lot demandé.",
        "MISSING_RAG_SOURCE": "Aucune source de connaissance fiable n’a été trouvée.",
        "MISSING_SQL_SOURCE": "Aucune source opérationnelle SQL n’a été trouvée pour cette réponse.",
        "MISSING_ML_SOURCE": "Aucun signal ML exploitable n’a été trouvé pour cette réponse.",
        "MISSING_RECOMMENDATION_SOURCE": "Aucune source de recommandation n’a été produite.",
        "WEAK_RETRIEVAL": "Les sources de connaissance récupérées sont limitées ou peu pertinentes.",
        "WEAK_SOURCE": "Certaines sources utilisées sont faibles ou peu fiables.",
        "SOURCE_DATA_EMPTY": "Une source attendue est présente mais sans données exploitables.",
        "MISSING_DATA_SIGNALLED": "La réponse signale une donnée manquante.",
        "NUMERIC_CLAIMS_NOT_GROUNDED": "Une valeur numérique n’est pas suffisamment justifiée par les sources disponibles.",
        "RECOMMENDATION_WITHOUT_EVIDENCE": "Une recommandation manque de preuve suffisante.",
        "RECOMMENDATION_EVIDENCE_WEAK": "Les preuves associées aux recommandations sont limitées.",
        "SQL_ML_CONTRADICTION": "Les signaux SQL et ML ne sont pas parfaitement alignés.",
        "PROMPT_INJECTION_DETECTED": "Une source de connaissance suspecte a été ignorée.",
        "CONTRADICTORY_CONTEXT_POSSIBLE": "Les sources récupérées peuvent contenir des informations contradictoires.",
        "NO_HIGH_RISK_BATCH_FOUND": "Aucun lot à risque confirmé n’a été trouvé avec les données disponibles.",
        "INCOMPLETE_DATA": "Certaines données nécessaires sont incomplètes.",
        "MISSING_EXPECTED_ROUTE_EVIDENCE": "Certaines preuves attendues pour cette route sont indisponibles.",
        "PRODUCT_FILTER_IGNORED": "Le filtre produit détecté était ambigu et a été ignoré.",
        "MISSING_OPERATION_RESULT": "Le format de réponse attendu n’a pas été entièrement produit.",
        "RAG_QUALITY_INSUFFICIENT": "Le contexte documentaire est insuffisant pour répondre avec certitude.",
        "RAG_EVIDENCE_REJECTED": "Une partie des preuves documentaires a été rejetée pour faible qualité.",
    }
    if text in mapping:
        return mapping[text]
    technical = (
        text.startswith("AGENT_ERROR_")
        or text.startswith("AGENT_TIMEOUT_")
        or text.endswith("_ERROR")
        or text.endswith("_TIMEOUT")
        or text.endswith("_EXCEPTION")
        or text.startswith("DB_")
        or text.startswith("LLM_PROVIDER_")
    )
    if technical:
        return "Un avertissement technique a été détecté. Les détails sont disponibles dans les métadonnées."
    if re.fullmatch(r"[A-Z0-9_]+", text):
        return "Avertissement de fiabilité: informations partielles ou insuffisantes pour cette requête."
    return text


def _humanize_source_type(source_type: str) -> str:
    """Ensure source types are French in user-visible output."""
    mapping = {
        "sql": "Source opérationnelle",
        "SQL": "Source opérationnelle",
        "rag": "Source documentaire",
        "RAG": "Source documentaire",
        "ml": "Analyse ML",
        "ML": "Analyse ML",
    }
    return mapping.get(str(source_type).strip(), str(source_type))


def _humanize_sql_table(table_name: str) -> str:
    """Convert SQL table names to French labels."""
    mapping = {
        "mango": "Mangue",
        "peanut": "Arachide",
        "millet": "Mil",
        "members": "membres",
        "farmers": "producteurs",
        "stocks": "stocks",
        "batches": "lots",
        "process_steps": "étapes de transformation",
        "pre_harvest": "pré-récolte",
        "pre_harvest_steps": "étapes de pré-récolte",
        "post_harvest": "post-récolte",
        "high_risk_lots": "lots à risque élevé",
        "members_list": "liste des membres",
        "inputs": "collectes et intrants",
        "parcels": "parcelles",
        "material_balance": "bilan matière",
        "stage_efficiency": "efficacité par étape",
    }
    raw = str(table_name or "").strip().lower()
    if not raw:
        return "source opérationnelle"
    if "," in raw:
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        translated = [mapping.get(part, part) for part in parts]
        return ", ".join(translated)
    return mapping.get(raw, raw.replace("_", " "))


def _build_agent_debug(agent_results: list[AgentResult]) -> dict:
    debug: dict[str, dict] = {}
    for result in agent_results:
        entry = {
            "agent_name": result.agent_name,
            "confidence": result.confidence,
            "warnings": result.warnings,
            "sources": result.sources,
            "answer_part": result.answer_part,
        }

        if result.agent_name == "RAGKnowledgeAgent" and isinstance(result.data, dict):
            chunks = result.data.get("chunks") or []
            trimmed_chunks = []
            for chunk in chunks[:6]:
                trimmed_chunks.append(
                    {
                        "document_id": chunk.get("document_id"),
                        "chunk_id": chunk.get("chunk_id"),
                        "title": chunk.get("title"),
                        "final_score": chunk.get("final_score"),
                        "hybrid_score": chunk.get("hybrid_score"),
                        "metadata": chunk.get("metadata"),
                        "content_preview": str(chunk.get("content") or "")[:320],
                    }
                )
            entry["data"] = {
                "rewrite": result.data.get("rewrite"),
                "filters": result.data.get("filters"),
                "weak_retrieval": result.data.get("weak_retrieval"),
                "chunks": trimmed_chunks,
            }
        else:
            entry["data"] = result.data

        debug[result.agent_name] = entry
    return debug


def _sum_agent_ms(agent_timings: list[dict[str, int | str]], agent_name: str) -> int:
    total = 0
    for item in agent_timings:
        if str(item.get("agent") or "") != agent_name:
            continue
        try:
            total += int(item.get("execution_ms") or 0)
        except Exception:
            continue
    return total


def _extract_sql_dispatch_trace(agent_results: list[AgentResult]) -> dict:
    for result in agent_results:
        if result.agent_name != "SQLAnalyticsAgent" or not isinstance(result.data, dict):
            continue
        trace = result.data.get("sql_dispatch_trace")
        if isinstance(trace, dict):
            return {
                key: trace.get(key)
                for key in ("route", "intent_family", "sql_operation", "tool_name", "module", "row_count", "evidence_status")
                if key in trace
            }
    return {}


def _extract_evidence_status_summary(agent_results: list[AgentResult]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for result in agent_results:
        if not isinstance(result.data, dict):
            continue
        if result.agent_name == "SQLAnalyticsAgent":
            trace = result.data.get("sql_dispatch_trace") or {}
            if isinstance(trace, dict) and trace.get("evidence_status"):
                statuses["sql"] = str(trace.get("evidence_status"))
        elif result.agent_name == "RAGKnowledgeAgent" and result.data.get("evidence_status"):
            statuses["rag"] = str(result.data.get("evidence_status"))
        elif result.agent_name == "MLLossAgent" and result.data.get("evidence_status"):
            statuses["ml"] = str(result.data.get("evidence_status"))
    return statuses


def _filter_warning_codes_for_manager(
    *,
    warning_codes: list[str],
    route: AgentRoute,
    intent_family: str | None,
    response_blocks: list[dict],
    sources: list[dict],
    agent_results: list[AgentResult],
) -> list[str]:
    codes = [str(code or "").strip() for code in warning_codes if str(code or "").strip()]
    if route != AgentRoute.HYBRID_FULL:
        return codes
    intent = str(intent_family or "").strip().upper()
    if intent not in {"RECOMMENDATION", "LOT_SPECIFIC_RECOMMENDATION", "ACTION_RECOMMENDATION"}:
        return codes
    has_recommendation_block = any(
        str((block or {}).get("type") or "").lower() in {"recommendations", "recommendation_cards"}
        for block in (response_blocks or [])
        if isinstance(block, dict)
    )
    if not has_recommendation_block:
        return codes
    source_types = {
        str((src or {}).get("type") or "").strip().upper()
        for src in (sources or [])
        if isinstance(src, dict)
    }
    if not {"SQL", "RAG", "RECOMMENDATION"}.issubset(source_types):
        return codes
    if not _recommendation_has_grounded_evidence(agent_results):
        return codes

    drop_codes = {"RECOMMENDATION_EVIDENCE_WEAK"}
    if "RAG" in source_types:
        drop_codes.add("MISSING_RAG_SOURCE")
    return [code for code in codes if str(code).strip().upper() not in drop_codes]


def _recommendation_has_grounded_evidence(agent_results: list[AgentResult]) -> bool:
    reco = _find_agent(agent_results, "RecommendationAgent")
    if not reco or not isinstance(reco.data, dict):
        return False
    recommendations = reco.data.get("recommendations") or []
    for item in recommendations:
        if not isinstance(item, dict):
            continue
        refs = item.get("evidence_refs")
        if isinstance(refs, list):
            for ref in refs:
                if not isinstance(ref, dict):
                    continue
                ref_type = str(ref.get("type") or "").upper()
                source_id = str(ref.get("source_id") or "").strip()
                if ref_type == "RAG" and str(ref.get("quality_status") or "").upper() in {"WEAK", "REJECTED"}:
                    continue
                if source_id and ref_type in {"SQL", "RAG", "RULE"}:
                    return True
    return False


def _needs_pre_route_memory_handoff(message: str) -> bool:
    lowered = str(message or "").lower()
    has_followup_ref = any(token in lowered for token in ("ce lot", "pour ce lot", "celui-ci", "celui ci"))
    has_recommendation_intent = any(
        token in lowered
        for token in (
            "recommand",
            "action",
            "actions",
            "que faire",
            "que dois-je faire",
            "que dois je faire",
            "sans inventer",
        )
    )
    has_reset = any(token in lowered for token in ("oublie ce lot", "oublier ce lot", "change de sujet", "maintenant oublie"))
    return has_followup_ref and has_recommendation_intent and not has_reset


def _is_reset_phrase(message: str) -> bool:
    lowered = str(message or "").lower()
    return any(token in lowered for token in ("oublie ce lot", "oublier ce lot", "change de sujet", "parlons du stock", "passons au stock"))

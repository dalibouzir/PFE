from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app


@dataclass
class EvalCase:
    question_id: str
    question: str
    expected_intent_family: str
    expected_route: str
    expected_sql_operation: str | None = None
    expect_sql_data: bool = False
    expect_rag: bool = False
    expect_recommendation: bool = False
    expect_shape: str | None = None
    sequence_key: str | None = None


def _cases() -> list[EvalCase]:
    return [
        # 10 SQL factual
        EvalCase("SQL01", "Quel est le stock actuel par produit et qualité ?", "STOCK_CURRENT", "SQL_ONLY", "get_current_stock", True, expect_shape="SQL_INTENT_TEMPLATE"),
        EvalCase("SQL02", "Quel produit a le plus de stock disponible actuellement ?", "STOCK_CURRENT", "SQL_ONLY", "get_current_stock", True, expect_shape="SQL_INTENT_TEMPLATE"),
        EvalCase("SQL03", "Est-ce que la mangue a encore du stock disponible ?", "STOCK_CURRENT", "SQL_ONLY", "get_current_stock", True, expect_shape="SQL_INTENT_TEMPLATE"),
        EvalCase("SQL04", "Quels lots post-récolte sont disponibles actuellement ?", "POSTHARVEST_AVAILABLE_LOTS", "SQL_ONLY", "get_available_postharvest_lots", True, expect_shape="SQL_INTENT_TEMPLATE"),
        EvalCase("SQL05", "Quels lots sont prêts à traiter avec peu de quantité restante ?", "POSTHARVEST_AVAILABLE_LOTS", "SQL_ONLY", "get_available_postharvest_lots", True, expect_shape="SQL_INTENT_TEMPLATE"),
        EvalCase("SQL06", "Quelles étapes pré-récolte sont enregistrées ?", "PREHARVEST_STEPS", "SQL_ONLY", "get_parcel_preharvest_status", False),
        EvalCase("SQL07", "Quel lot a la perte la plus élevée ?", "LOSS_RANKING", "SQL_ONLY", "get_canonical_material_balance", True, expect_shape="SQL_INTENT_TEMPLATE"),
        EvalCase("SQL08", "Quel lot a le plus grand écart entrée/sortie ?", "INPUT_OUTPUT_GAP", "SQL_ONLY", "get_canonical_material_balance", True, expect_shape="SQL_INTENT_TEMPLATE"),
        EvalCase("SQL09", "À quelle étape LOT-MILX-001 perd le plus ?", "STAGE_LOSS_ANALYSIS", "SQL_ONLY", "get_stage_loss_analysis", True, expect_shape="SQL_INTENT_TEMPLATE"),
        EvalCase("SQL10", "Quelle étape a la plus mauvaise efficacité en post-récolte ?", "STAGE_LOSS_ANALYSIS", "SQL_ONLY", "get_stage_loss_analysis", True, expect_shape="SQL_INTENT_TEMPLATE"),
        # 5 ranking/comparison
        EvalCase("RC01", "Quels lots ont le pire rendement ?", "LOSS_RANKING", "SQL_ONLY", "get_canonical_material_balance", True, expect_shape="SQL_INTENT_TEMPLATE"),
        EvalCase("RC02", "Quel lot a perdu le plus de kg entre entrée et sortie ?", "INPUT_OUTPUT_GAP", "SQL_ONLY", "get_canonical_material_balance", True, expect_shape="SQL_INTENT_TEMPLATE"),
        EvalCase("RC03", "Compare LOT-MILX-001 et LOT-MANG-001 en perte et efficacité.", "LOT_COMPARISON", "SQL_ONLY", "get_canonical_material_balance_for_lots", True, expect_shape="SQL_INTENT_TEMPLATE"),
        EvalCase("RC04", "Classe les lots du pire au meilleur selon la perte.", "LOSS_RANKING", "SQL_ONLY", "get_canonical_material_balance", True, expect_shape="SQL_INTENT_TEMPLATE"),
        EvalCase("RC05", "Classe les lots par écart de matière en kg.", "INPUT_OUTPUT_GAP", "SQL_ONLY", "get_canonical_material_balance", True, expect_shape="SQL_INTENT_TEMPLATE"),
        # 5 RAG best practices
        EvalCase("RAG01", "Quelles erreurs faut-il éviter pendant le tri du mil ?", "BEST_PRACTICES", "RAG_ONLY", None, False, True, expect_shape="RAG_OR_INSUFF"),
        EvalCase("RAG02", "Donne une checklist avant l’emballage des mangues.", "BEST_PRACTICES", "RAG_ONLY", None, False, True, expect_shape="RAG_OR_INSUFF"),
        EvalCase("RAG03", "Quelles précautions de stockage après conditionnement ?", "BEST_PRACTICES", "RAG_ONLY", None, False, True, expect_shape="RAG_OR_INSUFF"),
        EvalCase("RAG04", "Bonnes pratiques de tri pour limiter la casse ?", "BEST_PRACTICES", "RAG_ONLY", None, False, True, expect_shape="RAG_OR_INSUFF"),
        EvalCase("RAG05", "Check-list qualité avant la vente en lot ?", "BEST_PRACTICES", "RAG_ONLY", None, False, True, expect_shape="RAG_OR_INSUFF"),
        # 5 HYBRID_SQL_RAG advisory
        EvalCase("HYB01", "Comment réduire les pertes pendant le séchage ?", "EXPLANATION_CAUSAL", "HYBRID_SQL_RAG", "get_stage_loss_analysis", True, True),
        EvalCase("HYB02", "Comment améliorer le rendement pendant le tri ?", "EXPLANATION_CAUSAL", "HYBRID_SQL_RAG", "get_stage_loss_analysis", True, True),
        EvalCase("HYB03", "Que faire pour limiter les pertes à l’emballage ?", "EXPLANATION_CAUSAL", "HYBRID_SQL_RAG", "get_stage_loss_analysis", True, True),
        EvalCase("HYB04", "Pourquoi les pertes sont élevées au séchage ?", "EXPLANATION_CAUSAL", "HYBRID_SQL_RAG", "get_stage_loss_analysis", True, True),
        EvalCase("HYB05", "Conseils pour réduire les pertes post-récolte avec les données disponibles.", "EXPLANATION_CAUSAL", "HYBRID_SQL_RAG", "get_canonical_material_balance", True, True),
        # 3 recommendation
        EvalCase("REC01", "Donne-moi 3 actions concrètes pour réduire les pertes de LOT-MILX-001 avec les preuves utilisées.", "LOT_SPECIFIC_RECOMMENDATION", "HYBRID_FULL", "get_canonical_material_balance", True, True, True, "HYBRID_FULL_TEMPLATE"),
        EvalCase("REC02", "Quelles actions prioritaires cette semaine pour améliorer le rendement global ?", "RECOMMENDATION", "HYBRID_FULL", "get_canonical_material_balance", True, True, True, "HYBRID_FULL_TEMPLATE"),
        EvalCase("REC03", "Et pour ce lot, quelles actions appliquer ?", "FOLLOW_UP", "HYBRID_FULL", "get_canonical_material_balance", True, True, True, "HYBRID_FULL_TEMPLATE", sequence_key="followup"),
        # 2 memory sequence
        EvalCase("MEM01", "Quel lot a la perte la plus élevée ?", "LOSS_RANKING", "SQL_ONLY", "get_canonical_material_balance", True, sequence_key="followup"),
        EvalCase("MEM02", "Maintenant oublie ce lot et parle-moi seulement du stock de mangue.", "STOCK_CURRENT", "SQL_ONLY", "get_current_stock", True, sequence_key="followup"),
    ]


def _shape(answer: str) -> str:
    txt = (answer or "").lower()
    if "checklist pratique" in txt:
        return "RAG_CHECKLIST"
    if "je n’ai pas assez de contexte documentaire fiable" in txt:
        return "RAG_INSUFF"
    if "1. données mesurées" in txt and "3. recommandations validées" in txt:
        return "HYBRID_FULL_TEMPLATE"
    if "1. données mesurées" in txt and "2. interprétation" in txt:
        return "SQL_INTENT_TEMPLATE"
    return "GENERIC"


def _groundedness(case: EvalCase, answer: str, rec_refs: int) -> float:
    txt = (answer or "").lower()
    if case.expect_recommendation and rec_refs <= 0:
        return 0.0
    if any(token in txt for token in ("agronomic knowledge reference", "```", "| ---")):
        return 0.0
    return 1.0


def _warning_score(warnings: list[str]) -> float:
    if not warnings:
        return 1.0
    joined = " ".join(warnings).lower()
    noisy = "avertissement de fiabilité" in joined and len(warnings) > 2
    return 0.0 if noisy else 1.0


def _visual_blocks_score(case: EvalCase, blocks: list[dict[str, Any]]) -> float:
    types = {str((b or {}).get("type") or "").lower() for b in (blocks or [])}
    if case.expected_intent_family == "STOCK_CURRENT":
        return 1.0 if {"kpi_cards", "table", "chart"} & types and "table" in types else 0.0
    if case.expected_intent_family == "POSTHARVEST_AVAILABLE_LOTS":
        return 1.0 if "table" in types and ("kpi_cards" in types or "chart" in types) else 0.0
    if case.expected_intent_family in {"LOSS_RANKING", "INPUT_OUTPUT_GAP", "STAGE_LOSS_ANALYSIS"}:
        return 1.0 if "table" in types and "chart" in types else 0.0
    if case.expected_intent_family == "LOT_COMPARISON":
        return 1.0 if ("comparison_table" in types or "table" in types) else 0.0
    if case.expect_recommendation:
        return 1.0 if "recommendations" in types and "limits_block" in types else 0.0
    if case.expected_intent_family == "BEST_PRACTICES":
        return 1.0 if ("best_practices" in types or "limits_block" in types) else 0.0
    return 1.0


def _manager_clarity_score(answer: str, warnings: list[str]) -> float:
    txt = str(answer or "").strip()
    if not txt:
        return 0.0
    lines = [line.strip() for line in txt.splitlines() if line.strip()]
    first = lines[0].lower() if lines else ""
    starts_clear = any(token in first for token in ("1. données mesurées", "résumé", "je n’ai pas assez", "donnée non disponible", "produit avec le plus"))
    jargon = any(token in txt.lower() for token in ("sql_dispatch_trace", "agent_debug", "metadata:", "chunk_id", "document_id"))
    concise_limits = sum(1 for w in warnings if len(w) <= 120) == len(warnings)
    score = 0.0
    score += 0.4 if starts_clear else 0.0
    score += 0.4 if not jargon else 0.0
    score += 0.2 if concise_limits else 0.0
    return score


def evaluate_case_result(
    *,
    case: EvalCase,
    actual_route: str,
    actual_intent: str,
    actual_op: str | None,
    row_count: int | None,
    rag_quality: str | None,
    rec_refs: int,
    warnings: list[str],
    confidence: float,
    answer: str,
    blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    route_score = 1.0 if actual_route == case.expected_route else 0.0
    operation_score = 1.0 if (case.expected_sql_operation is None or actual_op == case.expected_sql_operation) else 0.0
    evidence_score = 1.0
    if case.expect_sql_data:
        evidence_score = 1.0 if (row_count or 0) > 0 else 0.0
    if case.expect_rag and evidence_score > 0:
        evidence_score = 1.0 if rag_quality in {"STRONG", "PARTIAL", None} else 0.0
    if case.expect_recommendation and evidence_score > 0:
        evidence_score = 1.0 if rec_refs > 0 else 0.0
    groundedness_score = _groundedness(case, answer, rec_refs)
    answer_shape = _shape(answer)
    answer_shape_score = 1.0
    if case.expect_shape == "SQL_INTENT_TEMPLATE":
        answer_shape_score = 1.0 if answer_shape == "SQL_INTENT_TEMPLATE" else 0.0
    elif case.expect_shape == "HYBRID_FULL_TEMPLATE":
        answer_shape_score = 1.0 if answer_shape == "HYBRID_FULL_TEMPLATE" else 0.0
    elif case.expect_shape == "RAG_OR_INSUFF":
        answer_shape_score = 1.0 if answer_shape in {"RAG_CHECKLIST", "RAG_INSUFF"} else 0.0
    warn_score = _warning_score(warnings)
    visual_score = _visual_blocks_score(case, blocks)
    clarity_score = _manager_clarity_score(answer, warnings)

    critical_failure = None
    if case.expected_route in {"SQL_ONLY", "HYBRID_SQL_RAG", "HYBRID_FULL"} and case.expected_sql_operation and not actual_op:
        critical_failure = "SQL_OPERATION_ERROR"
    if actual_op is None and float(confidence or 0.0) >= 0.7 and case.expected_route in {"SQL_ONLY", "HYBRID_SQL_RAG"}:
        critical_failure = "SQL_OPERATION_ERROR"
    if case.expect_recommendation and rec_refs <= 0:
        critical_failure = "RECOMMENDATION_NOT_GROUNDED"
    if "agronomic knowledge reference" in answer.lower():
        critical_failure = "RAG_RAW_LEAKAGE"
    if case.question_id == "MEM02" and actual_intent != "STOCK_CURRENT":
        critical_failure = "MEMORY_CONTEXT_ERROR"

    score_values = [route_score, operation_score, evidence_score, groundedness_score, answer_shape_score, warn_score, visual_score, clarity_score]
    overall_score = sum(score_values) / len(score_values)
    passed = overall_score >= 0.80 and critical_failure is None

    failure_category = "NO_FAILURE"
    if not passed:
        if critical_failure:
            failure_category = critical_failure
        elif route_score == 0:
            failure_category = "ROUTING_ERROR"
        elif operation_score == 0:
            failure_category = "SQL_OPERATION_ERROR"
        elif groundedness_score == 0:
            failure_category = "COMPOSITION_QUALITY"
        elif warn_score == 0:
            failure_category = "WARNING_NOISE"
        else:
            failure_category = "COMPOSITION_QUALITY"
    return {
        "answer_shape": answer_shape,
        "scores": {
            "route_score": route_score,
            "operation_score": operation_score,
            "evidence_score": evidence_score,
            "groundedness_score": groundedness_score,
            "answer_shape_score": answer_shape_score,
            "warning_score": warn_score,
            "visual_blocks_score": visual_score,
            "manager_clarity_score": clarity_score,
            "overall_score": round(overall_score, 4),
        },
        "pass": passed,
        "failure_category": failure_category,
    }


def run() -> dict[str, Any]:
    os.environ["AI_AUDIT_DEBUG"] = "1"
    results: list[dict[str, Any]] = []
    with TestClient(app) as client:
        login = client.post("/auth/login", json={"email": "manager@weefarm.local", "password": "Manager123!"})
        if login.status_code != 200:
            raise RuntimeError(f"Login failed: {login.status_code} {login.text}")
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        conv_ids: dict[str, str] = {}
        for case in _cases():
            payload = {"message": case.question, "language": "fr"}
            if case.sequence_key and case.sequence_key in conv_ids:
                payload["conversation_id"] = conv_ids[case.sequence_key]
            resp = client.post("/chat/agent", headers=headers, json=payload)
            data = resp.json()
            meta = data.get("metadata") or {}
            if case.sequence_key and meta.get("conversation_id"):
                conv_ids[case.sequence_key] = meta.get("conversation_id")
            entities = meta.get("detected_entities") or {}
            debug = meta.get("agent_debug") or {}
            sql_trace = (((debug.get("SQLAnalyticsAgent") or {}).get("data") or {}).get("sql_dispatch_trace") or {})
            row_count = sql_trace.get("row_count")
            rag_quality = ((debug.get("RAGKnowledgeAgent") or {}).get("data") or {}).get("quality_status")
            rec_refs = int(meta.get("recommendation_refs_count") or 0)
            warnings = data.get("warnings") or []
            answer = data.get("answer") or ""
            blocks = data.get("response_blocks") or []
            actual_route = data.get("route")
            actual_intent = str(entities.get("intent_family") or "")
            actual_op = sql_trace.get("sql_operation")

            eval_scores = evaluate_case_result(
                case=case,
                actual_route=actual_route,
                actual_intent=actual_intent,
                actual_op=actual_op,
                row_count=row_count,
                rag_quality=rag_quality,
                rec_refs=rec_refs,
                warnings=warnings,
                confidence=float(data.get("confidence") or 0.0),
                answer=answer,
                blocks=blocks,
            )

            results.append(
                {
                    "question_id": case.question_id,
                    "question": case.question,
                    "expected_intent_family": case.expected_intent_family,
                    "expected_route": case.expected_route,
                    "expected_sql_operation": case.expected_sql_operation,
                    "actual_intent_family": actual_intent,
                    "actual_route": actual_route,
                    "actual_sql_operation": actual_op,
                    "row_count": row_count,
                    "rag_quality_status": rag_quality,
                    "recommendation_refs_count": rec_refs,
                    "warning_count": len(warnings),
                    "confidence": data.get("confidence"),
                    "answer_summary": answer[:220].replace("\n", " | "),
                    "answer_shape": eval_scores["answer_shape"],
                    "scores": eval_scores["scores"],
                    "pass": eval_scores["pass"],
                    "failure_category": eval_scores["failure_category"],
                    "warnings": warnings,
                    "block_types": [str((b or {}).get("type") or "") for b in blocks if isinstance(b, dict)],
                }
            )

    metrics = {
        "route_correctness": round(sum(r["scores"]["route_score"] for r in results) / len(results), 4),
        "sql_operation_correctness": round(sum(r["scores"]["operation_score"] for r in results) / len(results), 4),
        "evidence_quality": round(sum(r["scores"]["evidence_score"] for r in results) / len(results), 4),
        "groundedness": round(sum(r["scores"]["groundedness_score"] for r in results) / len(results), 4),
        "answer_shape": round(sum(r["scores"]["answer_shape_score"] for r in results) / len(results), 4),
        "warning_quality": round(sum(r["scores"]["warning_score"] for r in results) / len(results), 4),
        "visual_blocks_quality": round(sum(r["scores"]["visual_blocks_score"] for r in results) / len(results), 4),
        "manager_clarity": round(sum(r["scores"]["manager_clarity_score"] for r in results) / len(results), 4),
        "overall_score": round(sum(r["scores"]["overall_score"] for r in results) / len(results), 4),
    }
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "count": len(results), "metrics": metrics, "results": results}


if __name__ == "__main__":
    report = run()
    out_dir = Path("artifacts/evals")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"supabase_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out_path))
    print(json.dumps(report["metrics"], ensure_ascii=False))

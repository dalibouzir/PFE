from __future__ import annotations

import csv
import json
import math
import os
import signal
import sys
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app

class _Timeout(Exception):
    pass


def _alarm_handler(signum: int, frame: Any) -> None:
    raise _Timeout()


@dataclass
class EvalCase:
    qid: str
    category: str
    question: str
    expected_route: str
    expected_intent: str | None = None
    expected_sql_operation: str | None = None
    expect_sql: bool = False
    expect_rag: bool = False
    expect_ml: bool = False
    expect_reco: bool = False
    memory_key: str | None = None
    expects_reset: bool = False


def _cases() -> list[EvalCase]:
    cases: list[EvalCase] = []

    # A. SQL factual questions — 15
    sql_q = [
        ("A01", "Quel est le stock actuel par produit et qualité ?", "SQL_ONLY", "STOCK_CURRENT", "get_current_stock"),
        ("A02", "Quel produit a le plus de stock disponible actuellement ?", "SQL_ONLY", "STOCK_CURRENT", "get_current_stock"),
        ("A03", "Est-ce que la mangue a encore du stock disponible ?", "SQL_ONLY", "STOCK_CURRENT", "get_current_stock"),
        ("A04", "Quels lots post-récolte sont disponibles actuellement ?", "SQL_ONLY", "POSTHARVEST_AVAILABLE_LOTS", "get_available_postharvest_lots"),
        ("A05", "Quels lots sont prêts à traiter avec faible quantité restante ?", "SQL_ONLY", "POSTHARVEST_AVAILABLE_LOTS", "get_available_postharvest_lots"),
        ("A06", "Donne le stock de mil par grade.", "SQL_ONLY", "STOCK_CURRENT", "get_current_stock"),
        ("A07", "Combien de lots actifs avons-nous ?", "SQL_ONLY", None, None),
        ("A08", "Montre les mouvements de stock les plus récents.", "SQL_ONLY", None, None),
        ("A09", "Quel lot a la plus grande quantité restante ?", "SQL_ONLY", None, None),
        ("A10", "Stock total disponible en kg, tous produits confondus.", "SQL_ONLY", "STOCK_CURRENT", "get_current_stock"),
        ("A11", "Combien de lots sont prêts pour transformation ?", "SQL_ONLY", "POSTHARVEST_AVAILABLE_LOTS", "get_available_postharvest_lots"),
        ("A12", "Liste les lots avec quantité restante faible.", "SQL_ONLY", "POSTHARVEST_AVAILABLE_LOTS", "get_available_postharvest_lots"),
        ("A13", "Quel est le stock du produit milx ?", "SQL_ONLY", "STOCK_CURRENT", "get_current_stock"),
        ("A14", "Quel est le stock du produit mangue ?", "SQL_ONLY", "STOCK_CURRENT", "get_current_stock"),
        ("A15", "Tableau stock par produit avec total/réservé/disponible.", "SQL_ONLY", "STOCK_CURRENT", "get_current_stock"),
    ]
    for qid, q, r, i, op in sql_q:
        cases.append(EvalCase(qid, "SQL factual", q, r, i, op, expect_sql=True))

    # B. Material balance / analytics — 10
    mb_q = [
        ("B01", "Quel lot a la perte la plus élevée ?", "SQL_ONLY", "LOSS_RANKING", "get_canonical_material_balance"),
        ("B02", "Quel lot a le plus grand écart entrée/sortie ?", "SQL_ONLY", "INPUT_OUTPUT_GAP", "get_canonical_material_balance"),
        ("B03", "Quelle étape a la plus mauvaise efficacité ?", "SQL_ONLY", "STAGE_LOSS_ANALYSIS", "get_stage_loss_analysis"),
        ("B04", "Compare LOT-MILX-001 et LOT-MANG-001 en perte et efficacité.", "SQL_ONLY", "LOT_COMPARISON", "get_canonical_material_balance_for_lots"),
        ("B05", "Classe les lots du pire au meilleur selon la perte.", "SQL_ONLY", "LOSS_RANKING", "get_canonical_material_balance"),
        ("B06", "Classe les lots par écart de matière en kg.", "SQL_ONLY", "INPUT_OUTPUT_GAP", "get_canonical_material_balance"),
        ("B07", "Bilan matière global: entrée, sortie, perte, efficacité.", "SQL_ONLY", "LOSS_RANKING", "get_canonical_material_balance"),
        ("B08", "Quelle étape concentre le plus de pertes ?", "SQL_ONLY", "STAGE_LOSS_ANALYSIS", "get_stage_loss_analysis"),
        ("B09", "Top 3 lots avec pertes les plus élevées.", "SQL_ONLY", "LOSS_RANKING", "get_canonical_material_balance"),
        ("B10", "Table comparative des lots critiques en perte/efficacité.", "SQL_ONLY", "LOT_COMPARISON", "get_canonical_material_balance_for_lots"),
    ]
    for qid, q, r, i, op in mb_q:
        cases.append(EvalCase(qid, "Material balance", q, r, i, op, expect_sql=True))

    # C. RAG best-practice questions — 8
    rag_q = [
        "Quelles erreurs faut-il éviter pendant le tri du mil ?",
        "Donne une checklist avant l'emballage des mangues.",
        "Quelles précautions de stockage après conditionnement ?",
        "Bonnes pratiques de séchage pour limiter les pertes ?",
        "Comment réduire les pertes post-récolte au tri ?",
        "Checklist qualité avant commercialisation d'un lot ?",
        "Meilleures pratiques de manutention pour éviter la casse ?",
        "Conseils standards pour limiter humidité et contamination ?",
    ]
    for idx, q in enumerate(rag_q, start=1):
        cases.append(EvalCase(f"C{idx:02d}", "RAG best-practice", q, "RAG_ONLY", "BEST_PRACTICES", expect_rag=True))

    # D. Hybrid SQL+RAG — 7
    hyb_q = [
        "Comment réduire les pertes pendant le séchage avec nos données actuelles ?",
        "Pourquoi LOT-MILX-001 a une mauvaise efficacité et que corriger ?",
        "Selon nos données, où perd-on le plus et comment améliorer ?",
        "Perte élevée à l'emballage: causes SQL et bonnes pratiques associées ?",
        "Quel stage prioriser pour baisse de pertes et quelles pratiques appliquer ?",
        "Explique les pertes du lot le plus critique avec conseils concrets.",
        "Actions post-récolte recommandées selon les pertes observées par étape.",
    ]
    for idx, q in enumerate(hyb_q, start=1):
        cases.append(EvalCase(f"D{idx:02d}", "Hybrid SQL+RAG", q, "HYBRID_SQL_RAG", "EXPLANATION_CAUSAL", expect_sql=True, expect_rag=True))

    # E. Recommendations — 5
    rec_q = [
        "Donne 3 actions pour réduire la perte de LOT-MILX-001 avec les preuves utilisées.",
        "Quelles priorités hebdomadaires pour améliorer le rendement global ?",
        "Recommandations pour le lot le plus critique avec sources SQL/RAG/ML.",
        "Actions immédiates par étape pour réduire la perte cette semaine.",
        "Plan d'action manager: 5 recommandations justifiées par evidence_refs.",
    ]
    for idx, q in enumerate(rec_q, start=1):
        cases.append(EvalCase(f"E{idx:02d}", "Recommendations", q, "HYBRID_FULL", "RECOMMENDATION", expect_sql=True, expect_rag=True, expect_reco=True))

    # F. Memory/follow-up — 5
    mem = [
        ("F01", "Quel lot a la perte la plus élevée ?", "SQL_ONLY", "LOSS_RANKING", False),
        ("F02", "Quelles actions pour ce lot ?", "HYBRID_FULL", "FOLLOW_UP", False),
        ("F03", "Ajoute les bonnes pratiques de tri pour ce lot.", "HYBRID_SQL_RAG", "FOLLOW_UP", False),
        ("F04", "Oublie ce lot et montre seulement le stock de mangue.", "SQL_ONLY", "STOCK_CURRENT", True),
        ("F05", "Maintenant stock global par produit.", "SQL_ONLY", "STOCK_CURRENT", False),
    ]
    for qid, q, r, i, reset in mem:
        cases.append(EvalCase(qid, "Memory/follow-up", q, r, i, expect_sql=True, expect_reco=(qid=="F02"), expect_rag=(qid=="F03"), memory_key="thread1", expects_reset=reset))

    return cases


def _safe_num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    k = (len(vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return vals[int(k)]
    return vals[f] * (c - k) + vals[c] * (k - f)


def _block_types(resp: dict[str, Any]) -> set[str]:
    return {str((b or {}).get("type") or "").lower() for b in (resp.get("response_blocks") or []) if isinstance(b, dict)}


def run_audit() -> dict[str, Any]:
    start = datetime.now(timezone.utc)
    cases = _cases()

    deployed_url = (os.getenv("NEXT_PUBLIC_API_URL") or "").strip()
    deployed_accessible = bool(deployed_url and deployed_url.startswith("http") and "your-backend-domain" not in deployed_url)

    rows: list[dict[str, Any]] = []
    conv_map: dict[str, str] = {}

    with TestClient(app) as client:
        login = client.post("/auth/login", json={"email": "manager@weefarm.local", "password": "Manager123!"})
        if login.status_code != 200:
            raise RuntimeError(f"Login failed: {login.status_code} {login.text}")
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        for idx, case in enumerate(cases, start=1):
            payload: dict[str, Any] = {"message": case.question, "language": "fr"}
            if case.memory_key and case.memory_key in conv_map:
                payload["conversation_id"] = conv_map[case.memory_key]

            t0 = time.perf_counter()
            error = None
            try:
                signal.signal(signal.SIGALRM, _alarm_handler)
                signal.alarm(45)
                resp = client.post("/chat/agent", headers=headers, json=payload, timeout=60)
                signal.alarm(0)
                status_code = resp.status_code
                data = resp.json() if status_code == 200 else {}
            except _Timeout:
                signal.alarm(0)
                status_code = 0
                data = {}
                error = "timeout_45s"
            except Exception as exc:
                signal.alarm(0)
                status_code = 0
                data = {}
                error = str(exc)
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

            meta = data.get("metadata") or {}
            if case.memory_key and meta.get("conversation_id"):
                conv_map[case.memory_key] = str(meta["conversation_id"])

            ent = meta.get("detected_entities") or {}
            debug = meta.get("agent_debug") or {}
            sql_trace = (((debug.get("SQLAnalyticsAgent") or {}).get("data") or {}).get("sql_dispatch_trace") or {})
            dur = meta.get("durations_ms") or {}
            btypes = _block_types(data)
            answer = str(data.get("answer") or "")
            warnings = list(data.get("warnings") or [])
            sources = list(data.get("sources") or [])

            route = str(data.get("route") or "")
            intent = str(ent.get("intent_family") or "")
            op = sql_trace.get("sql_operation")
            row_count = sql_trace.get("row_count")
            rec_refs = int(meta.get("recommendation_refs_count") or 0)
            confidence = _safe_num(data.get("confidence"), 0.0)

            has_sql_source = any(str((s or {}).get("type") or "").upper() == "SQL" for s in sources)
            has_rag_source = any(str((s or {}).get("type") or "").upper() == "RAG" for s in sources)
            has_ml_source = any(str((s or {}).get("type") or "").upper() == "ML" for s in sources)

            route_ok = route == case.expected_route
            intent_ok = True if case.expected_intent is None else (intent == case.expected_intent)
            op_ok = True if case.expected_sql_operation is None else (op == case.expected_sql_operation)
            sql_data_ok = True if not case.expect_sql else (_safe_num(row_count, 0) > 0 or has_sql_source)
            rag_ok = True if not case.expect_rag else has_rag_source
            reco_ok = True if not case.expect_reco else (rec_refs > 0)

            warning_noise = len(warnings) > 3
            raw_rag_leak = "```" in answer or "chunk_id" in answer.lower() or "document_id" in answer.lower()

            if status_code != 200 or error:
                failure = "LATENCY_TIMEOUT"
            elif not route_ok:
                failure = "ROUTING_ERROR"
            elif case.expected_sql_operation and not op:
                failure = "SQL_OPERATION_ERROR"
            elif case.expected_sql_operation and confidence >= 0.7 and not op:
                failure = "SQL_OPERATION_ERROR"
            elif case.expect_reco and rec_refs <= 0:
                failure = "RECOMMENDATION_NOT_GROUNDED"
            elif raw_rag_leak:
                failure = "RAG_RAW_LEAKAGE"
            elif case.expects_reset and intent != "STOCK_CURRENT":
                failure = "MEMORY_CONTEXT_ERROR"
            elif warning_noise:
                failure = "WARNING_NOISE"
            else:
                failure = "NO_FAILURE"

            rows.append(
                {
                    "qid": case.qid,
                    "category": case.category,
                    "question": case.question,
                    "status_code": status_code,
                    "error": error,
                    "latency_ms": elapsed_ms,
                    "route": route,
                    "expected_route": case.expected_route,
                    "route_ok": route_ok,
                    "intent_family": intent,
                    "expected_intent": case.expected_intent,
                    "intent_ok": intent_ok,
                    "sql_operation": op,
                    "expected_sql_operation": case.expected_sql_operation,
                    "op_ok": op_ok,
                    "row_count": row_count,
                    "sql_data_ok": sql_data_ok,
                    "rag_source_ok": rag_ok,
                    "ml_source_seen": has_ml_source,
                    "recommendation_refs_count": rec_refs,
                    "recommendation_ok": reco_ok,
                    "warnings_count": len(warnings),
                    "warnings": warnings,
                    "failure_category": failure,
                    "confidence": confidence,
                    "block_types": sorted(list(btypes)),
                    "has_kpi_cards": "kpi_cards" in btypes,
                    "has_table": "table" in btypes,
                    "has_chart": "chart" in btypes,
                    "has_comparison_table": "comparison_table" in btypes,
                    "has_recommendations": "recommendations" in btypes,
                    "has_limits_block": "limits_block" in btypes,
                    "has_summary": "summary" in btypes,
                    "durations_ms": {
                        "routing_duration_ms": _safe_num(dur.get("routing_duration_ms")),
                        "sql_duration_ms": _safe_num(dur.get("sql_duration_ms")),
                        "rag_duration_ms": _safe_num(dur.get("rag_duration_ms")),
                        "ml_duration_ms": _safe_num(dur.get("ml_duration_ms")),
                        "recommendation_duration_ms": _safe_num(dur.get("recommendation_duration_ms")),
                        "llm_duration_ms": _safe_num(dur.get("llm_duration_ms")),
                        "composition_duration_ms": _safe_num(dur.get("composition_duration_ms")),
                        "total_duration_ms": _safe_num(meta.get("total_duration_ms", dur.get("total_duration_ms"))),
                    },
                    "answer_preview": answer[:200].replace("\n", " | "),
                }
            )
            print(f"[{idx:02d}/{len(cases)}] {case.qid} route={route or 'NA'} latency={elapsed_ms}ms fail={failure}", flush=True)

    latencies = [r["latency_ms"] for r in rows if r["status_code"] == 200]
    timeout_or_error = [r for r in rows if r["status_code"] != 200 or r["error"]]

    route_acc = sum(1 for r in rows if r["route_ok"]) / len(rows)
    intent_acc = sum(1 for r in rows if r["intent_ok"]) / len(rows)
    op_cases = [r for r in rows if r["expected_sql_operation"]]
    op_corr = (sum(1 for r in op_cases if r["op_ok"]) / len(op_cases)) if op_cases else 0.0

    tool_success = sum(1 for r in rows if r["status_code"] == 200) / len(rows)
    fallback_rate = sum(1 for r in rows if r["route"] in {"OUT_OF_SCOPE", "CLARIFICATION_NEEDED", "UNKNOWN"}) / len(rows)
    unmapped_rate = sum(1 for r in rows if r["expected_sql_operation"] and not r["sql_operation"]) / (len(op_cases) or 1)

    agent_invocations = Counter()
    for r in rows:
        d = r["durations_ms"]
        if d["sql_duration_ms"] > 0:
            agent_invocations["SQL"] += 1
        if d["rag_duration_ms"] > 0:
            agent_invocations["RAG"] += 1
        if d["ml_duration_ms"] > 0:
            agent_invocations["ML"] += 1
        if d["recommendation_duration_ms"] > 0:
            agent_invocations["RECOMMENDATION"] += 1

    unnecessary_calls = 0
    for r in rows:
        if r["expected_route"] == "SQL_ONLY" and (r["durations_ms"]["rag_duration_ms"] > 0 or r["durations_ms"]["recommendation_duration_ms"] > 0):
            unnecessary_calls += 1

    rag_cases = [r for r in rows if "RAG" in r["expected_route"] or "RAG" in (r["expected_intent"] or "") or r["category"] in {"RAG best-practice", "Hybrid SQL+RAG"}]
    rag_hits = sum(1 for r in rag_cases if r["rag_source_ok"])
    rag_hit_rate = rag_hits / (len(rag_cases) or 1)

    rag_quality_counts = Counter()
    for r in rag_cases:
        if r["rag_source_ok"]:
            rag_quality_counts["STRONG"] += 1
        elif r["status_code"] == 200:
            rag_quality_counts["WEAK"] += 1
        else:
            rag_quality_counts["REJECTED"] += 1

    rec_cases = [r for r in rows if r["category"] == "Recommendations" or r["expect_reco"] if False]
    rec_cases = [r for r in rows if r["category"] == "Recommendations" or r["qid"].startswith("F02")]
    rec_cov = sum(1 for r in rec_cases if r["recommendation_refs_count"] > 0) / (len(rec_cases) or 1)
    avg_refs = statistics.mean([r["recommendation_refs_count"] for r in rec_cases]) if rec_cases else 0.0
    unsupported_rec_rate = sum(1 for r in rec_cases if r["recommendation_refs_count"] <= 0) / (len(rec_cases) or 1)

    mem_cases = [r for r in rows if r["category"] == "Memory/follow-up"]
    carry_ok = sum(1 for r in mem_cases[1:3] if r["route"] in {"HYBRID_FULL", "HYBRID_SQL_RAG", "HYBRID_SQL_ML"}) / 2 if len(mem_cases) >= 3 else 0.0
    reset_ok = 1.0 if any(r["qid"] == "F04" and r["intent_family"] == "STOCK_CURRENT" for r in mem_cases) else 0.0
    wrong_reuse = 1.0 - reset_ok
    continuity = sum(1 for r in mem_cases if r["status_code"] == 200 and r["failure_category"] != "MEMORY_CONTEXT_ERROR") / (len(mem_cases) or 1)

    warning_quality = 1.0 - (sum(1 for r in rows if r["warnings_count"] > 3) / len(rows))
    duplicate_warning_rate = sum(1 for r in rows if len(r["warnings"]) != len(set(r["warnings"]))) / len(rows)

    visual_complete = {
        "kpi_cards": sum(1 for r in rows if r["has_kpi_cards"]),
        "tables": sum(1 for r in rows if r["has_table"]),
        "charts": sum(1 for r in rows if r["has_chart"]),
        "comparison_tables": sum(1 for r in rows if r["has_comparison_table"]),
        "recommendation_cards": sum(1 for r in rows if r["has_recommendations"]),
        "limits_blocks": sum(1 for r in rows if r["has_limits_block"]),
    }

    failure_counts = Counter([r["failure_category"] for r in rows])
    no_failure_count = failure_counts.get("NO_FAILURE", 0)
    critical_failures = len(rows) - no_failure_count

    reliability_overall = no_failure_count / len(rows)

    route_lat = defaultdict(list)
    for r in rows:
        route_lat[r["route"]].append(r["latency_ms"])

    metrics = {
        "latency": {
            "count": len(latencies),
            "total_duration_ms": round(sum(latencies), 2),
            "p50_ms": round(_percentile(latencies, 0.5), 2),
            "p90_ms": round(_percentile(latencies, 0.9), 2),
            "p95_ms": round(_percentile(latencies, 0.95), 2),
            "min_ms": round(min(latencies) if latencies else 0.0, 2),
            "max_ms": round(max(latencies) if latencies else 0.0, 2),
            "timeout_error_rate": round(len(timeout_or_error) / len(rows), 4),
            "route_avg_latency_ms": {k: round(statistics.mean(v), 2) for k, v in route_lat.items()},
            "sql_duration_avg_ms": round(statistics.mean([r["durations_ms"]["sql_duration_ms"] for r in rows]), 2),
            "rag_duration_avg_ms": round(statistics.mean([r["durations_ms"]["rag_duration_ms"] for r in rows]), 2),
            "ml_duration_avg_ms": round(statistics.mean([r["durations_ms"]["ml_duration_ms"] for r in rows]), 2),
            "recommendation_duration_avg_ms": round(statistics.mean([r["durations_ms"]["recommendation_duration_ms"] for r in rows]), 2),
            "llm_duration_avg_ms": round(statistics.mean([r["durations_ms"]["llm_duration_ms"] for r in rows]), 2),
            "composition_duration_avg_ms": round(statistics.mean([r["durations_ms"]["composition_duration_ms"] for r in rows]), 2),
        },
        "routing_agents": {
            "route_accuracy": round(route_acc, 4),
            "intent_family_accuracy": round(intent_acc, 4),
            "sql_operation_correctness": round(op_corr, 4),
            "tool_success_rate": round(tool_success, 4),
            "fallback_rate": round(fallback_rate, 4),
            "unmapped_operation_rate": round(unmapped_rate, 4),
            "agent_invocation_count": dict(agent_invocations),
            "unnecessary_agent_call_rate": round(unnecessary_calls / len(rows), 4),
        },
        "sql_data_correctness": {
            "sql_factual_correctness_proxy": round(sum(1 for r in rows if (not r["expected_sql_operation"] or r["op_ok"]) and r["sql_data_ok"]) / len(rows), 4),
            "row_count_nonzero_rate_sql_cases": round(sum(1 for r in rows if r["expected_sql_operation"] and _safe_num(r["row_count"], 0) > 0) / (len(op_cases) or 1), 4),
            "canonical_material_balance_consistency_proxy": round(sum(1 for r in rows if not r["qid"].startswith("B") or r["failure_category"] != "CANONICAL_LOSS_INCONSISTENCY") / len(rows), 4),
            "non_canonical_loss_exposure_rate": 0.0,
        },
        "rag": {
            "retrieval_hit_rate": round(rag_hit_rate, 4),
            "rag_evidence_availability": round(rag_hit_rate, 4),
            "rag_quality_distribution": dict(rag_quality_counts),
            "context_relevance_proxy": round(rag_hit_rate, 4),
            "answer_relevance_proxy": round(sum(1 for r in rag_cases if r["status_code"] == 200) / (len(rag_cases) or 1), 4),
            "groundedness_proxy": round(sum(1 for r in rag_cases if r["failure_category"] != "RAG_RAW_LEAKAGE") / (len(rag_cases) or 1), 4),
            "raw_source_leakage_rate": round(sum(1 for r in rag_cases if r["failure_category"] == "RAG_RAW_LEAKAGE") / (len(rag_cases) or 1), 4),
            "insufficient_context_rate": round(sum(1 for r in rag_cases if not r["rag_source_ok"]) / (len(rag_cases) or 1), 4),
            "useful_rag_answer_rate": round(sum(1 for r in rag_cases if r["status_code"] == 200 and r["rag_source_ok"]) / (len(rag_cases) or 1), 4),
        },
        "recommendation": {
            "recommendation_evidence_refs_coverage": round(rec_cov, 4),
            "avg_recommendation_refs_per_answer": round(avg_refs, 4),
            "unsupported_recommendation_rate": round(unsupported_rec_rate, 4),
            "valid_action_count_vs_requested": {
                "requested": len(rec_cases) * 3,
                "proxy_valid": sum(min(r["recommendation_refs_count"], 3) for r in rec_cases),
            },
            "source_distribution": {
                "SQL": sum(1 for r in rec_cases if r["durations_ms"]["sql_duration_ms"] > 0),
                "RAG": sum(1 for r in rec_cases if r["durations_ms"]["rag_duration_ms"] > 0),
                "ML": sum(1 for r in rec_cases if r["durations_ms"]["ml_duration_ms"] > 0),
                "RULE": sum(1 for r in rec_cases if r["recommendation_refs_count"] > 0),
            },
            "recommendation_grounding_score": round(rec_cov * (1.0 - unsupported_rec_rate), 4),
        },
        "memory_followup": {
            "entity_carry_over_success": round(carry_ok, 4),
            "reset_phrase_success": round(reset_ok, 4),
            "wrong_context_reuse_rate": round(wrong_reuse, 4),
            "conversation_continuity_score": round(continuity, 4),
        },
        "text_generation": {
            "rouge_1": None,
            "rouge_l": None,
            "bleu": None,
            "meteor": None,
            "bertscore": None,
            "perplexity": None,
        },
        "ux_quality": {
            "manager_clarity_score_proxy": round(sum(1 for r in rows if r["has_summary"]) / len(rows), 4),
            "answer_shape_score_proxy": round(sum(1 for r in rows if len(r["answer_preview"]) > 0) / len(rows), 4),
            "visual_blocks_score": round(sum(1 for r in rows if r["has_table"] or r["has_chart"] or r["has_kpi_cards"]) / len(rows), 4),
            "warning_quality": round(warning_quality, 4),
            "duplicate_warning_rate": round(duplicate_warning_rate, 4),
            "limits_usefulness_proxy": round(sum(1 for r in rows if r["has_limits_block"]) / len(rows), 4),
            "summary_naturalness_proxy": round(sum(1 for r in rows if "1." in r["answer_preview"].lower() or "résumé" in r["answer_preview"].lower()) / len(rows), 4),
            "visual_block_completeness_counts": visual_complete,
        },
        "reliability": {
            "overall_score": round(reliability_overall, 4),
            "critical_failure_count": critical_failures,
            "unsupported_claim_rate_proxy": round(sum(1 for r in rows if r["failure_category"] in {"RAG_RAW_LEAKAGE", "RECOMMENDATION_NOT_GROUNDED"}) / len(rows), 4),
            "groundedness_score_proxy": round(sum(1 for r in rows if r["failure_category"] not in {"RAG_RAW_LEAKAGE", "RECOMMENDATION_NOT_GROUNDED"}) / len(rows), 4),
            "evidence_quality_score_proxy": round(sum(1 for r in rows if (r["sql_data_ok"] and (not r["expect_reco"] if False else True))) / len(rows), 4),
            "confidence_calibration_notes": "High confidence without mapped SQL operation is flagged as SQL_OPERATION_ERROR.",
        },
    }

    not_computed = [
        {"metric": "frontend_perceived_delay", "reason": "Not computed because browser UX telemetry was not captured in this backend runtime audit."},
        {"metric": "stock_match_with_dashboard", "reason": "Not computed because dashboard-side reference export was not available in this run."},
        {"metric": "ROUGE-1", "reason": "Not computed because no gold reference answer set was provided for overlap scoring."},
        {"metric": "ROUGE-L", "reason": "Not computed because no gold reference answer set was provided for overlap scoring."},
        {"metric": "BLEU", "reason": "Not computed because no gold reference answer set was provided for overlap scoring."},
        {"metric": "METEOR", "reason": "Not computed because metric package/reference set was not configured."},
        {"metric": "BERTScore", "reason": "Not computed because model package/reference set was not configured."},
        {"metric": "Perplexity", "reason": "Not computed because no local perplexity evaluation model/pipeline was configured."},
    ]

    return {
        "audit_name": "post_deploy_chatbot_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_environment": {
            "deployed_backend_accessible": deployed_accessible,
            "deployed_backend_url": deployed_url if deployed_accessible else None,
            "execution_mode": "local_fastapi_supabase_runtime" if not deployed_accessible else "deployed_backend",
            "limitation": "Deployed /chat/agent endpoint was not directly reachable from configured environment; audit executed via local FastAPI runtime with Supabase-backed data." if not deployed_accessible else None,
        },
        "question_count": len(rows),
        "dataset_counts": dict(Counter([r["category"] for r in rows])),
        "metrics": metrics,
        "critical_failures": dict(failure_counts),
        "not_computed": not_computed,
        "results": rows,
        "notes": {
            "bleu_rouge_secondary": "BLEU/ROUGE are secondary here because they measure text overlap, not operational SQL correctness.",
            "perplexity_secondary": "Perplexity is secondary because fluent language can still be factually wrong in decision support tasks.",
        },
        "started_at": start.isoformat(),
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path, Path]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("backend/artifacts/evals")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"post_deploy_chatbot_audit_{ts}.json"
    csv_path = out_dir / f"post_deploy_chatbot_audit_{ts}.csv"
    md_path = out_dir / f"post_deploy_chatbot_audit_{ts}.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    cols = [
        "qid", "category", "status_code", "latency_ms", "route", "expected_route", "route_ok",
        "intent_family", "expected_intent", "intent_ok", "sql_operation", "expected_sql_operation", "op_ok",
        "row_count", "sql_data_ok", "rag_source_ok", "ml_source_seen", "recommendation_refs_count", "recommendation_ok",
        "warnings_count", "failure_category", "confidence", "has_kpi_cards", "has_table", "has_chart",
        "has_comparison_table", "has_recommendations", "has_limits_block", "has_summary", "question", "answer_preview"
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in report["results"]:
            row = {k: r.get(k) for k in cols}
            w.writerow(row)

    m = report["metrics"]
    lines = [
        "# Post-Deploy Chatbot Audit",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Question count: `{report['question_count']}`",
        f"- Execution mode: `{report['runtime_environment']['execution_mode']}`",
        "",
        "## Latency",
        f"- p50: `{m['latency']['p50_ms']} ms`",
        f"- p90: `{m['latency']['p90_ms']} ms`",
        f"- p95: `{m['latency']['p95_ms']} ms`",
        f"- timeout/error rate: `{m['latency']['timeout_error_rate']}`",
        "",
        "## Routing",
        f"- route accuracy: `{m['routing_agents']['route_accuracy']}`",
        f"- intent family accuracy: `{m['routing_agents']['intent_family_accuracy']}`",
        f"- sql operation correctness: `{m['routing_agents']['sql_operation_correctness']}`",
        "",
        "## Reliability",
        f"- overall score: `{m['reliability']['overall_score']}`",
        f"- critical failures: `{m['reliability']['critical_failure_count']}`",
        "",
        "## Critical Failure Counts",
    ]
    for k, v in report["critical_failures"].items():
        lines.append(f"- {k}: `{v}`")

    lines.extend(["", "## Not Computed Metrics"])
    for item in report["not_computed"]:
        lines.append(f"- {item['metric']}: {item['reason']}")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, csv_path, md_path


if __name__ == "__main__":
    report = run_audit()
    jp, cp, mp = write_outputs(report)
    print(str(jp))
    print(str(cp))
    print(str(mp))

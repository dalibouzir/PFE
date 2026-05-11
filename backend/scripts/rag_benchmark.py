from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import time
import sys

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.models.user import User
from app.services.assistant import debug_retrieval_context
from app.services.rag_evaluation import EvaluationScenario, evaluate_scenario_result


ARTIFACT_DIR = ROOT_DIR / "artifacts"
JSON_REPORT = ARTIFACT_DIR / "rag_benchmark_report.json"
MD_REPORT = ARTIFACT_DIR / "rag_benchmark_report.md"


def _scenarios() -> list[EvaluationScenario]:
    return [
        EvaluationScenario(
            question="current stock of mango",
            expected_retrieval_domains=["stocks", "dashboard"],
            expected_chunk_types=[],
            expected_sql_usage=True,
            expected_grounding_behavior="sql_first",
        ),
        EvaluationScenario(
            question="why are drying losses high this week for mango?",
            expected_retrieval_domains=["process_steps", "recommendations", "ml_prediction_logs"],
            expected_chunk_types=[
                "product_stage_summary",
                "lot_status_summary",
                "process_step_summary",
                "recommendation_context",
                "benchmark_reference",
            ],
            expected_sql_usage=True,
            expected_grounding_behavior="hybrid",
        ),
        EvaluationScenario(
            question="which lot is most risky and what should we do?",
            expected_retrieval_domains=["batches", "recommendations"],
            expected_chunk_types=[
                "lot_status_summary",
                "operational_risk_summary",
                "lot_recommendation_summary",
                "recommendation_context",
            ],
            expected_sql_usage=True,
            expected_grounding_behavior="hybrid",
        ),
        EvaluationScenario(
            question="what does benchmark say about millet losses?",
            expected_retrieval_domains=["reference_metrics", "knowledge_chunks"],
            expected_chunk_types=["benchmark_reference", "agronomic_knowledge"],
            expected_sql_usage=False,
            expected_grounding_behavior="rag_only",
        ),
        EvaluationScenario(
            question="what happened to LOT-MANG-004?",
            expected_retrieval_domains=["batches", "process_steps"],
            expected_chunk_types=["lot_status_summary", "process_step_summary", "lot_recommendation_summary"],
            expected_sql_usage=True,
            expected_grounding_behavior="stale_context_check",
        ),
        EvaluationScenario(
            question="why do recommendations conflict with current losses?",
            expected_retrieval_domains=["recommendations", "process_steps", "ml_prediction_logs"],
            expected_chunk_types=["recommendation_context", "scoped_loss_summary", "operational_risk_summary"],
            expected_sql_usage=True,
            expected_grounding_behavior="contradiction_check",
        ),
        EvaluationScenario(
            question="why are mango drying losses high compared with bissap losses?",
            expected_retrieval_domains=["process_steps", "batches", "recommendations"],
            expected_chunk_types=["product_stage_summary", "scoped_loss_summary", "operational_risk_summary"],
            expected_sql_usage=True,
            expected_grounding_behavior="scope_contamination_check",
        ),
        EvaluationScenario(
            question="what happened to LOT-MANG-004 and which stage caused losses?",
            expected_retrieval_domains=["batches", "process_steps"],
            expected_chunk_types=["lot_status_summary", "product_stage_summary", "scoped_loss_summary", "process_step_summary"],
            expected_sql_usage=True,
            expected_grounding_behavior="lot_specific",
        ),
        EvaluationScenario(
            question="best practices benchmark for peanut storage losses in west africa",
            expected_retrieval_domains=["reference_metrics", "knowledge_chunks"],
            expected_chunk_types=["benchmark_reference", "agronomic_knowledge"],
            expected_sql_usage=False,
            expected_grounding_behavior="benchmark_only",
        ),
        EvaluationScenario(
            question="compare cooperative losses versus mango drying losses this month",
            expected_retrieval_domains=["process_steps", "batches", "dashboard"],
            expected_chunk_types=["product_stage_summary", "scoped_loss_summary", "operational_risk_summary"],
            expected_sql_usage=True,
            expected_grounding_behavior="comparative",
        ),
    ]


def _render_markdown(report: dict) -> str:
    lines = [
        "# RAG Benchmark Report",
        "",
        f"Generated at: {report['generated_at']}",
        "",
        "## Summary",
        f"- scenarios: {report['summary']['scenario_count']}",
        f"- avg_retrieval_relevance_score: {report['summary']['avg_retrieval_relevance_score']}",
        f"- avg_grounding_score: {report['summary']['avg_grounding_score']}",
        f"- avg_freshness_score: {report['summary']['avg_freshness_score']}",
        f"- avg_SQL_alignment_score: {report['summary']['avg_SQL_alignment_score']}",
        f"- avg_expected_chunk_coverage: {report['summary']['avg_expected_chunk_coverage']}",
        f"- avg_scope_purity_score: {report['summary']['avg_scope_purity_score']}",
        f"- avg_contamination_rate: {report['summary']['avg_contamination_rate']}",
        f"- avg_operational_priority_score: {report['summary']['avg_operational_priority_score']}",
        "",
        "## Scenario Results",
    ]
    for row in report["results"]:
        lines.extend(
            [
                "",
                f"### {row['question']}",
                f"- intent_type: {row['retrieval_plan'].get('intent_type')}",
                f"- sql_needed: {row['retrieval_plan'].get('sql_needed')}",
                f"- rag_needed: {row['retrieval_plan'].get('rag_needed')}",
                f"- warning_flags: {row['orchestration'].get('warning_flags')}",
                f"- confidence_estimate: {row['orchestration'].get('confidence_estimate')}",
                f"- hit_count: {row['retrieval_diagnostics'].get('hit_count')}",
                f"- chunk_types: {row['retrieval_diagnostics'].get('chunk_types')}",
                f"- freshness: {row['retrieval_diagnostics'].get('freshness')}",
                f"- metrics: {row['metrics']}",
                f"- latency_ms: {row['latency_ms']}",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        current_user = db.scalar(select(User).where(User.role == UserRole.MANAGER).limit(1))
        if current_user is None:
            raise RuntimeError("No manager user available for benchmark.")

        results = []
        for scenario in _scenarios():
            started = time.perf_counter()
            debug_payload = debug_retrieval_context(
                db,
                current_user=current_user,
                message=scenario.question,
                top_k=6,
            )
            latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
            metrics = evaluate_scenario_result(scenario=scenario, debug_payload=debug_payload)
            results.append(
                {
                    "question": scenario.question,
                    "retrieval_plan": debug_payload.get("retrieval_plan"),
                    "filters": debug_payload.get("filters"),
                    "retrieval_diagnostics": debug_payload.get("retrieval_diagnostics"),
                    "orchestration": debug_payload.get("orchestration"),
                    "hits": debug_payload.get("hits"),
                    "metrics": metrics,
                    "latency_ms": latency_ms,
                }
            )

        def _avg(key: str) -> float:
            vals = [float(item["metrics"].get(key, 0.0) or 0.0) for item in results]
            return round(sum(vals) / len(vals), 4) if vals else 0.0

        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {
                "scenario_count": len(results),
                "avg_retrieval_relevance_score": _avg("retrieval_relevance_score"),
                "avg_grounding_score": _avg("grounding_score"),
                "avg_freshness_score": _avg("freshness_score"),
                "avg_SQL_alignment_score": _avg("SQL_alignment_score"),
                "avg_expected_chunk_coverage": _avg("expected_chunk_coverage"),
                "avg_scope_purity_score": _avg("scope_purity_score"),
                "avg_contamination_rate": _avg("contamination_rate"),
                "avg_operational_priority_score": _avg("operational_priority_score"),
            },
            "results": results,
        }
        JSON_REPORT.write_text(json.dumps(_json_safe(report), indent=2, ensure_ascii=True), encoding="utf-8")
        MD_REPORT.write_text(_render_markdown(report), encoding="utf-8")
        print(f"Saved {JSON_REPORT}")
        print(f"Saved {MD_REPORT}")
    finally:
        db.close()


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, set):
        return sorted(_json_safe(item) for item in value)
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


if __name__ == "__main__":
    main()

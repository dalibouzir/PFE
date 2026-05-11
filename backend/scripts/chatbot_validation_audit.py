from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
import re
import sys
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.deps import get_current_user, get_db
from app.db.session import SessionLocal
from app.main import app
from app.models.batch import Batch
from app.models.enums import UserRole
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.reference import ReferenceMetric
from app.models.stock import Stock
from app.models.user import User
from app.services.assistant import debug_retrieval_context

ARTIFACT_DIR = ROOT_DIR / "artifacts"
JSON_REPORT = ARTIFACT_DIR / "chatbot_validation_audit.json"
MD_REPORT = ARTIFACT_DIR / "chatbot_validation_audit.md"


@dataclass
class AuditQuestion:
    question: str
    category: str
    expected_intent: str


QUESTIONS: list[AuditQuestion] = [
    AuditQuestion("current stock of mango", "SQL_ONLY", "SQL_ONLY"),
    AuditQuestion("how much arachide stock is remaining?", "SQL_ONLY", "SQL_ONLY"),
    AuditQuestion("what is the status of LOT-MANG-001?", "SQL_ONLY", "SQL_ONLY"),
    AuditQuestion("what does benchmark say about millet losses?", "RAG_ONLY", "RAG_ONLY"),
    AuditQuestion("best practices for mango drying", "RAG_ONLY", "RAG_ONLY"),
    AuditQuestion("why are drying losses high this week for mango?", "HYBRID", "HYBRID"),
    AuditQuestion("compare current mango drying losses with benchmark references", "HYBRID", "HYBRID"),
    AuditQuestion("which lot is most risky and what should we do?", "HYBRID", "HYBRID"),
    AuditQuestion("why does the ML prediction differ from current operational losses?", "HYBRID", "HYBRID"),
    AuditQuestion("what is the best movie this week?", "UNSUPPORTED", "UNSUPPORTED"),
]


def _to_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(_to_json_safe(v) for v in value)
    return value


def _parse_notes_as_mapping(text: str | None) -> dict[str, Any]:
    if not text:
        return {}
    raw = str(text).strip()
    if not raw:
        return {}
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return {}


def _extract_context_signals(context_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    metric_map = {str(item.get("metric")): item for item in context_metrics}

    intent_unit = str(metric_map.get("retrieval_plan.intent_type", {}).get("unit", "UNKNOWN"))
    sql_needed = float(metric_map.get("retrieval_plan.sql_needed", {}).get("value", 0.0) or 0.0) >= 0.5
    rag_needed = float(metric_map.get("retrieval_plan.rag_needed", {}).get("value", 0.0) or 0.0) >= 0.5
    confidence_score = float(metric_map.get("orchestration.confidence_score", {}).get("value", 0.0) or 0.0)
    confidence_label = str(metric_map.get("orchestration.confidence_score", {}).get("unit", "UNKNOWN"))
    contamination_risk = float(metric_map.get("orchestration.contamination_risk_score", {}).get("value", 0.0) or 0.0)

    warning_notes = str(metric_map.get("orchestration.warning_count", {}).get("notes", "") or "")
    warning_flags = [item for item in warning_notes.split("|") if item and item != "none"]

    chunk_type_notes = str(metric_map.get("retrieval_diagnostics.chunk_type_count", {}).get("notes", "") or "")
    chunk_types = _parse_notes_as_mapping(chunk_type_notes)

    return {
        "intent_type": intent_unit,
        "sql_needed": sql_needed,
        "rag_needed": rag_needed,
        "orchestration_confidence_score": confidence_score,
        "orchestration_confidence_label": confidence_label,
        "contamination_risk": contamination_risk,
        "warning_flags": warning_flags,
        "chunk_types": chunk_types,
    }


def _extract_numbers(text: str) -> list[float]:
    nums: list[float] = []
    for token in re.findall(r"\b\d+(?:[\.,]\d+)?\b", text or ""):
        try:
            nums.append(float(token.replace(",", ".")))
        except Exception:
            continue
    return nums


def _contains_close_number(answer: str, expected: float, *, pct_tolerance: float = 0.15) -> bool:
    numbers = _extract_numbers(answer)
    if expected == 0:
        return any(abs(item) < 0.01 for item in numbers)
    lower = expected * (1.0 - pct_tolerance)
    upper = expected * (1.0 + pct_tolerance)
    return any(lower <= item <= upper for item in numbers)


def _build_data_snapshot(db: Session) -> dict[str, Any]:
    manager = db.scalar(select(User).where(User.role == UserRole.MANAGER).limit(1))
    if manager is None or manager.cooperative_id is None:
        raise RuntimeError("No manager with cooperative_id available for validation audit.")

    coop_id = manager.cooperative_id

    stocks = db.execute(
        select(Product.name, Stock.total_stock_kg, Stock.reserved_in_lots_kg, Stock.threshold)
        .join(Stock, Stock.product_id == Product.id)
        .where(Stock.cooperative_id == coop_id)
    ).all()

    batches = db.execute(
        select(Batch.code, Batch.status, Batch.initial_qty, Batch.current_qty, Product.name)
        .join(Product, Product.id == Batch.product_id)
        .where(Batch.cooperative_id == coop_id)
    ).all()

    week_start = date.today() - timedelta(days=7)
    mango_drying_rows = db.execute(
        select(ProcessStep.qty_in, ProcessStep.qty_out)
        .join(Batch, Batch.id == ProcessStep.batch_id)
        .join(Product, Product.id == Batch.product_id)
        .where(
            Batch.cooperative_id == coop_id,
            func.lower(Product.name).like("%mango%") | func.lower(Product.name).like("%mangue%"),
            func.lower(ProcessStep.type).in_(["drying", "sechage", "séchage"]),
            ProcessStep.date >= week_start,
        )
    ).all()
    mango_drying_losses: list[float] = []
    for qty_in, qty_out in mango_drying_rows:
        in_val = float(qty_in or 0.0)
        out_val = float(qty_out or 0.0)
        if in_val > 0:
            mango_drying_losses.append(max(0.0, (in_val - out_val) / in_val * 100.0))

    ref_metrics = db.execute(
        select(ReferenceMetric.crop, ReferenceMetric.metric, ReferenceMetric.value, ReferenceMetric.unit, ReferenceMetric.period)
        .order_by(ReferenceMetric.period.desc())
        .limit(50)
    ).all()

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "cooperative_id": str(coop_id),
        "manager_user_id": str(manager.id),
        "stocks": [
            {
                "product_name": str(name),
                "total_stock_kg": float(total or 0.0),
                "reserved_in_lots_kg": float(reserved or 0.0),
                "available_stock_kg": float((total or 0.0) - (reserved or 0.0)),
                "threshold": float(threshold or 0.0),
            }
            for name, total, reserved, threshold in stocks
        ],
        "batches": [
            {
                "code": str(code),
                "status": str(status.value if hasattr(status, "value") else status),
                "initial_qty": float(initial or 0.0),
                "current_qty": float(current or 0.0),
                "product_name": str(product_name),
            }
            for code, status, initial, current, product_name in batches
        ],
        "mango_drying_week": {
            "step_count": len(mango_drying_losses),
            "avg_loss_pct": round(sum(mango_drying_losses) / len(mango_drying_losses), 4) if mango_drying_losses else None,
            "max_loss_pct": round(max(mango_drying_losses), 4) if mango_drying_losses else None,
        },
        "reference_metric_count": len(ref_metrics),
        "reference_metrics_preview": [
            {
                "crop": str(crop),
                "metric": str(metric),
                "value": float(value or 0.0),
                "unit": str(unit),
                "period": str(period),
            }
            for crop, metric, value, unit, period in ref_metrics[:12]
        ],
    }


def _score_question(
    question: AuditQuestion,
    *,
    answer_text: str,
    route_info: dict[str, Any],
    citations: list[dict[str, Any]],
    ui_blocks: list[dict[str, Any]],
    debug_payload: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    answer_lower = (answer_text or "").lower()
    expected_intent = question.expected_intent

    route_correct = route_info.get("intent_type") == expected_intent

    sql_expected = question.category in {"SQL_ONLY", "HYBRID"}
    rag_expected = question.category in {"RAG_ONLY", "HYBRID"}

    sql_used_correctly = (bool(route_info.get("sql_needed")) == sql_expected) or (
        sql_expected and bool(route_info.get("sql_needed"))
    )
    rag_used_correctly = (bool(route_info.get("rag_needed")) == rag_expected) or (
        rag_expected and bool(route_info.get("rag_needed"))
    )

    contamination_risk = float(route_info.get("contamination_risk", 0.0) or 0.0)
    scope_purity_score = round(max(0.0, 1.0 - contamination_risk), 4)

    contamination_detected = False
    if "mango" in question.question.lower() and "compared with bissap" not in question.question.lower():
        contamination_detected = "bissap" in answer_lower and "mango" in answer_lower
    if contamination_risk >= 0.35:
        contamination_detected = True

    factual_accuracy_score = 0.5
    evidence_missing_response = any(
        token in answer_lower
        for token in [
            "no benchmark/agronomic evidence",
            "cannot provide a grounded reference answer",
            "aucune evidence benchmark/agronomique",
            "reponse referencee fiable",
        ]
    )

    if question.question == "current stock of mango":
        stock_row = next((row for row in snapshot["stocks"] if "mango" in row["product_name"].lower() or "mangue" in row["product_name"].lower()), None)
        if stock_row is None:
            factual_accuracy_score = 0.4 if any(token in answer_lower for token in ["no data", "not found", "aucun", "introuvable"]) else 0.2
        else:
            factual_accuracy_score = 1.0 if _contains_close_number(answer_text, float(stock_row["available_stock_kg"])) else 0.55
    elif question.question == "how much arachide stock is remaining?":
        stock_row = next((row for row in snapshot["stocks"] if "arachide" in row["product_name"].lower() or "peanut" in row["product_name"].lower()), None)
        if stock_row is None:
            factual_accuracy_score = 0.85 if any(token in answer_lower for token in ["no data", "not found", "aucun", "introuvable", "not available"]) else 0.3
        else:
            factual_accuracy_score = 1.0 if _contains_close_number(answer_text, float(stock_row["available_stock_kg"])) else 0.55
    elif question.question == "what is the status of LOT-MANG-001?":
        batch_row = next((row for row in snapshot["batches"] if row["code"].upper() == "LOT-MANG-001"), None)
        if batch_row is None:
            factual_accuracy_score = 0.85 if any(token in answer_lower for token in ["not found", "no data", "aucun", "introuvable"]) else 0.35
        else:
            status = str(batch_row["status"]).lower()
            factual_accuracy_score = 1.0 if status in answer_lower else 0.55
    elif question.question == "what does benchmark say about millet losses?":
        if evidence_missing_response and not citations:
            factual_accuracy_score = 0.85
        else:
            has_benchmark_citation = any(
                ("benchmark" in str(item.get("topic", "")).lower())
                or ("reference" in str(item.get("topic", "")).lower())
                or ("aphlis" in str(item.get("source_id", "")).lower())
                for item in citations
            )
            factual_accuracy_score = 0.95 if has_benchmark_citation else 0.35
    elif question.question == "best practices for mango drying":
        if evidence_missing_response and not citations:
            factual_accuracy_score = 0.85
        else:
            factual_accuracy_score = 0.9 if any(token in answer_lower for token in ["dry", "drying", "sechage", "séchage", "humidity", "airflow", "humid"]) else 0.45
    elif question.question == "why are drying losses high this week for mango?":
        snapshot_avg = snapshot.get("mango_drying_week", {}).get("avg_loss_pct")
        mentions_mango = "mango" in answer_lower or "mangue" in answer_lower
        mentions_drying = any(token in answer_lower for token in ["drying", "sechage", "séchage"])
        has_number_match = _contains_close_number(answer_text, float(snapshot_avg)) if snapshot_avg is not None else False
        factual_accuracy_score = 0.95 if mentions_mango and mentions_drying and (has_number_match or snapshot_avg is None) else 0.55
    elif question.question == "what is the best movie this week?":
        factual_accuracy_score = 1.0 if any(
            token in answer_lower
            for token in ["agricultural cooperative operations", "designed for", "posez une question", "scope"]
        ) else 0.2
    else:
        factual_accuracy_score = 0.8 if len(answer_text.strip()) > 0 else 0.2

    citation_relevance_score = 0.0
    if citations:
        score_hits = 0
        for citation in citations:
            topic = str(citation.get("topic", "")).lower()
            crop = str(citation.get("crop", "")).lower()
            source_id = str(citation.get("source_id", "")).lower()
            if question.category == "RAG_ONLY":
                if any(token in topic for token in ["benchmark", "agronomic", "knowledge", "recommendation", "drying", "loss"]):
                    score_hits += 1
                if "millet" in question.question.lower() and ("mil" in crop or "millet" in crop):
                    score_hits += 1
                if any(token in source_id for token in ["aphlis", "fao"]):
                    score_hits += 1
            elif question.category == "HYBRID":
                if any(token in topic for token in ["process", "recommendation", "anomaly", "risk", "benchmark"]):
                    score_hits += 1
            else:
                if any(token in topic for token in ["stock", "batch", "lot", "process"]):
                    score_hits += 1
        citation_relevance_score = min(1.0, score_hits / max(1, len(citations)))
    elif question.category == "RAG_ONLY" and evidence_missing_response:
        citation_relevance_score = 0.55

    if question.category in {"SQL_ONLY", "HYBRID"} and route_info.get("sql_needed"):
        ui_blocks_relevant = len(ui_blocks) > 0
    else:
        ui_blocks_relevant = True

    answer_usefulness_score = 0.45
    if question.category == "UNSUPPORTED":
        answer_usefulness_score = 1.0 if route_correct else 0.2
    else:
        has_action_language = any(token in answer_lower for token in ["should", "recommend", "action", "next step", "devrait", "recommande", "action"])
        answer_usefulness_score = min(
            1.0,
            0.35
            + (0.25 if route_correct else 0.0)
            + (0.2 if factual_accuracy_score >= 0.75 else 0.0)
            + (0.1 if not contamination_detected else 0.0)
            + (0.1 if has_action_language else 0.0),
        )

    if question.category == "UNSUPPORTED":
        contamination_detected = False

    passed = (
        route_correct
        and sql_used_correctly
        and rag_used_correctly
        and factual_accuracy_score >= 0.7
        and citation_relevance_score >= (0.45 if question.category in {"RAG_ONLY", "HYBRID"} else 0.0)
        and scope_purity_score >= (0.75 if question.category in {"HYBRID", "SQL_ONLY"} else 0.5)
        and (not contamination_detected)
        and answer_usefulness_score >= 0.65
        and ui_blocks_relevant
    )

    debug_retrieval = debug_payload.get("retrieval_diagnostics", {}) if isinstance(debug_payload, dict) else {}

    return {
        "route_correct": route_correct,
        "sql_used_correctly": sql_used_correctly,
        "rag_used_correctly": rag_used_correctly,
        "factual_accuracy_score": round(float(factual_accuracy_score), 4),
        "citation_relevance_score": round(float(citation_relevance_score), 4),
        "scope_purity_score": round(float(scope_purity_score), 4),
        "contamination_detected": contamination_detected,
        "answer_usefulness_score": round(float(answer_usefulness_score), 4),
        "ui_blocks_relevant": ui_blocks_relevant,
        "passed": bool(passed),
        "retrieval_diagnostics": debug_retrieval,
        "warnings": route_info.get("warning_flags", []),
    }


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    def _avg(key: str) -> float:
        vals = [float(item.get(key, 0.0) or 0.0) for item in results]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    def _pass_rate(rows: list[dict[str, Any]]) -> float:
        if not rows:
            return 0.0
        return round(sum(1 for row in rows if row.get("passed")) / len(rows), 4)

    by_cat: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        by_cat.setdefault(str(row.get("category")), []).append(row)

    return {
        "pass_rate": _pass_rate(results),
        "avg_factual_accuracy": _avg("factual_accuracy_score"),
        "avg_citation_relevance": _avg("citation_relevance_score"),
        "avg_scope_purity": _avg("scope_purity_score"),
        "avg_answer_usefulness": _avg("answer_usefulness_score"),
        "sql_only_pass_rate": _pass_rate(by_cat.get("SQL_ONLY", [])),
        "rag_only_pass_rate": _pass_rate(by_cat.get("RAG_ONLY", [])),
        "hybrid_pass_rate": _pass_rate(by_cat.get("HYBRID", [])),
        "unsupported_pass_rate": _pass_rate(by_cat.get("UNSUPPORTED", [])),
    }


def _build_failure_patterns(results: list[dict[str, Any]]) -> list[str]:
    patterns: list[str] = []
    if any(not row.get("route_correct") for row in results):
        patterns.append("Routing mismatch detected for one or more questions.")
    if any(row.get("contamination_detected") for row in results):
        patterns.append("Scope contamination detected: unrelated product evidence leaked into answers.")
    if any(row.get("category") == "UNSUPPORTED" and not row.get("passed") for row in results):
        patterns.append("Unsupported query handling is not consistently safe.")
    if any(row.get("category") == "HYBRID" and row.get("citation_relevance_score", 0) < 0.45 for row in results):
        patterns.append("Hybrid answers show weak citation relevance in some cases.")
    if any(row.get("category") == "SQL_ONLY" and row.get("factual_accuracy_score", 0) < 0.7 for row in results):
        patterns.append("SQL-only factual accuracy below threshold for at least one question.")
    if not patterns:
        patterns.append("No major failure pattern detected under the current validation set.")
    return patterns


def _render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Chatbot Pre-Phase-6 Validation Audit",
        "",
        "## Executive Summary",
        f"- Generated at: {report['generated_at']}",
        f"- Pass rate: {report['aggregate_metrics']['pass_rate']}",
        f"- Avg factual accuracy: {report['aggregate_metrics']['avg_factual_accuracy']}",
        f"- Avg citation relevance: {report['aggregate_metrics']['avg_citation_relevance']}",
        f"- Avg scope purity: {report['aggregate_metrics']['avg_scope_purity']}",
        f"- Avg answer usefulness: {report['aggregate_metrics']['avg_answer_usefulness']}",
        "",
        "## Actual Data Snapshot",
        f"- Cooperative: {report['actual_data_snapshot'].get('cooperative_id')}",
        f"- Stocks tracked: {len(report['actual_data_snapshot'].get('stocks', []))}",
        f"- Batches tracked: {len(report['actual_data_snapshot'].get('batches', []))}",
        f"- Mango drying weekly step count: {report['actual_data_snapshot'].get('mango_drying_week', {}).get('step_count')}",
        f"- Reference metric rows: {report['actual_data_snapshot'].get('reference_metric_count')}",
        "",
        "## Per-question Validation",
    ]

    for item in report["questions"]:
        lines.extend(
            [
                "",
                f"### {item['question']}",
                f"- category: {item['category']}",
                f"- intent: expected `{item['expected_intent']}`, observed `{item['observed']['intent_type']}`",
                f"- sql_needed: {item['observed']['sql_needed']} | rag_needed: {item['observed']['rag_needed']}",
                f"- factual_accuracy_score: {item['scores']['factual_accuracy_score']}",
                f"- citation_relevance_score: {item['scores']['citation_relevance_score']}",
                f"- scope_purity_score: {item['scores']['scope_purity_score']}",
                f"- contamination_detected: {item['scores']['contamination_detected']}",
                f"- answer_usefulness_score: {item['scores']['answer_usefulness_score']}",
                f"- passed: {item['scores']['passed']}",
                f"- warning_flags: {item['observed']['warning_flags']}",
                f"- chunk_types: {item['observed']['chunk_types']}",
                f"- answer: {item['answer_text']}",
            ]
        )

    lines.extend(
        [
            "",
            "## Aggregate Metrics",
            f"- pass_rate: {report['aggregate_metrics']['pass_rate']}",
            f"- avg_factual_accuracy: {report['aggregate_metrics']['avg_factual_accuracy']}",
            f"- avg_citation_relevance: {report['aggregate_metrics']['avg_citation_relevance']}",
            f"- avg_scope_purity: {report['aggregate_metrics']['avg_scope_purity']}",
            f"- avg_answer_usefulness: {report['aggregate_metrics']['avg_answer_usefulness']}",
            f"- SQL_ONLY pass rate: {report['aggregate_metrics']['sql_only_pass_rate']}",
            f"- RAG_ONLY pass rate: {report['aggregate_metrics']['rag_only_pass_rate']}",
            f"- HYBRID pass rate: {report['aggregate_metrics']['hybrid_pass_rate']}",
            f"- unsupported pass rate: {report['aggregate_metrics']['unsupported_pass_rate']}",
            "",
            "## Failure Patterns",
        ]
    )
    for pattern in report["failure_patterns"]:
        lines.append(f"- {pattern}")

    lines.extend(
        [
            "",
            "## Recommendation",
            report["recommendation"],
        ]
    )
    return "\n".join(lines)


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        manager = db.scalar(select(User).where(User.role == UserRole.MANAGER).limit(1))
        if manager is None:
            raise RuntimeError("No manager user available for chatbot validation audit.")

        snapshot = _build_data_snapshot(db)

        # Read-only chat execution: wrap each request in transaction and rollback writes.
        bind = db.get_bind()
        if bind is None:
            raise RuntimeError("Database bind unavailable.")
        conn = bind.connect()
        outer_tx = conn.begin()
        AuditSessionLocal = sessionmaker(bind=conn, autoflush=False, autocommit=False, expire_on_commit=False)
        audit_session = AuditSessionLocal()

        app.dependency_overrides[get_current_user] = lambda: manager

        def _override_db():
            try:
                yield audit_session
            finally:
                pass

        app.dependency_overrides[get_db] = _override_db

        client = TestClient(app)

        results: list[dict[str, Any]] = []
        for item in QUESTIONS:
            started = datetime.now(UTC)
            response = client.post("/chat", json={"message": item.question})
            latency_ms = (datetime.now(UTC) - started).total_seconds() * 1000.0
            if response.status_code != 200:
                answer_text = f"HTTP {response.status_code}: {response.text}"
                payload: dict[str, Any] = {}
            else:
                payload = response.json()
                answer_text = str(payload.get("message", ""))

            context_metrics = list(payload.get("context_metrics", [])) if isinstance(payload, dict) else []
            citations = list(payload.get("citations", [])) if isinstance(payload, dict) else []
            ui_blocks = list(payload.get("ui_blocks", [])) if isinstance(payload, dict) else []

            route_info = _extract_context_signals(context_metrics)

            # Additional retrieval diagnostics through read-only debug path.
            debug_payload = debug_retrieval_context(
                audit_session,
                current_user=manager,
                message=item.question,
                top_k=6,
            )

            scores = _score_question(
                item,
                answer_text=answer_text,
                route_info=route_info,
                citations=citations,
                ui_blocks=ui_blocks,
                debug_payload=debug_payload,
                snapshot=snapshot,
            )

            results.append(
                {
                    "question": item.question,
                    "category": item.category,
                    "expected_intent": item.expected_intent,
                    "latency_ms": round(latency_ms, 3),
                    "answer_text": answer_text,
                    "observed": {
                        **route_info,
                        "citations_count": len(citations),
                        "ui_blocks_count": len(ui_blocks),
                        "citations": citations,
                    },
                    "scores": scores,
                    "debug": {
                        "filters": debug_payload.get("filters"),
                        "retrieval_diagnostics": debug_payload.get("retrieval_diagnostics"),
                        "orchestration": debug_payload.get("orchestration"),
                        "hits": debug_payload.get("hits"),
                    },
                    "passed": bool(scores.get("passed")),
                    "factual_accuracy_score": float(scores.get("factual_accuracy_score", 0.0)),
                    "citation_relevance_score": float(scores.get("citation_relevance_score", 0.0)),
                    "scope_purity_score": float(scores.get("scope_purity_score", 0.0)),
                    "answer_usefulness_score": float(scores.get("answer_usefulness_score", 0.0)),
                    "route_correct": bool(scores.get("route_correct")),
                }
            )

        aggregate = _aggregate(results)
        failures = _build_failure_patterns(results)

        recommendation = (
            "Phase 6 should start only if hybrid and RAG-only pass rates are both >= 0.70 and no contamination failures are present."
            if aggregate["hybrid_pass_rate"] >= 0.70 and aggregate["rag_only_pass_rate"] >= 0.70 and not any(
                row["scores"].get("contamination_detected") for row in results
            )
            else "Phase 6 should NOT start yet; resolve routing/grounding/citation gaps first."
        )

        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "actual_data_snapshot": snapshot,
            "questions": results,
            "aggregate_metrics": aggregate,
            "failure_patterns": failures,
            "recommendation": recommendation,
        }

        JSON_REPORT.write_text(json.dumps(_to_json_safe(report), ensure_ascii=True, indent=2), encoding="utf-8")
        MD_REPORT.write_text(_render_markdown(report), encoding="utf-8")

        print(f"Saved {JSON_REPORT}")
        print(f"Saved {MD_REPORT}")
    finally:
        try:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)
        except Exception:
            pass
        try:
            # Rollback all chatbot writes performed during audit.
            if 'outer_tx' in locals() and outer_tx.is_active:
                outer_tx.rollback()
        except Exception:
            pass
        try:
            if 'audit_session' in locals():
                audit_session.close()
        except Exception:
            pass
        try:
            if 'conn' in locals():
                conn.close()
        except Exception:
            pass
        db.close()


if __name__ == "__main__":
    main()

"""
Supabase real-app chatbot audit + chat persistence diagnosis.

Scope:
- Real Supabase PostgreSQL truth checks (no SQLite parity shortcuts)
- Authenticated /chat/agent audit against operational SQL + RAG + ML/recommendation evidence
- response_blocks verification
- PASS/PARTIAL/FAIL based on answer correctness (not only route/source)
- Chat persistence diagnosis after refresh path (/chat/sessions + /chat/sessions/{id}/messages)

Notes:
- This file intentionally does NOT implement chatbot reasoning fixes.
- It only diagnoses and reports current behavior.
"""

from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai.utils.audit_environment import EnvironmentParityAudit
from app.ai.utils.test_auth import get_or_create_test_user, get_test_auth_header
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models.chat import ChatMessage, ChatSession
from app.services import agent_assistant as agent_assistant_service
from app.ai.orchestrator.audit_logger import AuditLogger


REPORT_DIR = Path(__file__).resolve().parents[2] / "reports"
JSON_REPORT_PATH = REPORT_DIR / "chatbot_real_app_audit_supabase.json"
MD_REPORT_PATH = REPORT_DIR / "chatbot_real_app_audit_supabase.md"


EXPECTED_SQL_TABLES_BY_DOMAIN: dict[str, set[str]] = {
    "members": {"members", "inputs"},
    "stocks": {"stocks", "products"},
    "commercial": {"commercial_orders", "commercial_invoices"},
    "batches": {"batches"},
    "process_steps": {"process_steps", "batches"},
    "efficiency": {"batches", "process_steps"},
    "material_balance": {"batches", "process_steps"},
    "ml_risk": {"batches"},
    "rag_best_practices": set(),
    "recommendations": {"recommendations", "batches"},
    "multi_intent": {"stocks", "batches", "process_steps", "inputs", "members"},
}


@dataclass(frozen=True)
class AuditCase:
    case_id: str
    domain: str
    question: str
    expected_routes: set[str]
    expected_source_types: set[str]
    expected_block_types: set[str]


def _table_exists(db: Session, table_name: str) -> bool:
    return table_name in sa_inspect(db.get_bind()).get_table_names()


def _row_count(db: Session, table_name: str, cooperative_id: Any | None = None) -> int | None:
    if not _table_exists(db, table_name):
        return None
    if cooperative_id is None:
        return int(db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0)
    columns = [col["name"] for col in sa_inspect(db.get_bind()).get_columns(table_name)]
    if "cooperative_id" in columns:
        return int(
            db.execute(
                text(f"SELECT COUNT(*) FROM {table_name} WHERE cooperative_id = :coop_id"),
                {"coop_id": cooperative_id},
            ).scalar()
            or 0
        )
    return int(db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0)


def _as_float_candidates(text_blob: str) -> list[float]:
    values: list[float] = []
    for token in re.findall(r"\d+(?:[.,]\d+)?", text_blob):
        try:
            values.append(float(token.replace(",", ".")))
        except ValueError:
            continue
    return values


def _contains_number_close(answer: str, expected: float, *, tolerance_ratio: float = 0.08, tolerance_abs: float = 1.0) -> bool:
    candidates = _as_float_candidates(answer)
    threshold = max(tolerance_abs, abs(expected) * tolerance_ratio)
    return any(abs(value - expected) <= threshold for value in candidates)


def _parse_sql_tables(sources: list[dict[str, Any]]) -> set[str]:
    tables: set[str] = set()
    for src in sources:
        if str(src.get("type") or "").lower() != "sql":
            continue
        raw = str(src.get("table") or "")
        if not raw:
            continue
        for item in raw.split(","):
            token = item.strip().lower()
            if token:
                tables.add(token)
    return tables


def _route_ok(route: str, expected_routes: set[str]) -> bool:
    route_upper = route.upper()
    return any(route_upper == expected.upper() for expected in expected_routes)


def _source_types(sources: list[dict[str, Any]]) -> set[str]:
    return {str(item.get("type") or "").lower() for item in sources if item}


def _block_types(blocks: list[dict[str, Any]]) -> set[str]:
    return {str(block.get("type") or "").lower() for block in blocks if block}


def _build_truth_snapshot(db: Session, cooperative_id: Any) -> dict[str, Any]:
    members_count = _row_count(db, "members", cooperative_id) or 0
    stocks_count = _row_count(db, "stocks", cooperative_id) or 0
    batches_count = _row_count(db, "batches", cooperative_id) or 0
    process_steps_count = _row_count(db, "process_steps") or 0
    rag_chunks_count = _row_count(db, "rag_chunks", cooperative_id) or 0
    recommendations_count = _row_count(db, "recommendations") or 0
    orders_count = _row_count(db, "commercial_orders", cooperative_id) or 0
    invoices_count = _row_count(db, "commercial_invoices", cooperative_id) or 0

    top_members = [
        dict(row._mapping)
        for row in db.execute(
            text(
                """
                SELECT m.full_name, m.code AS member_code, SUM(i.quantity) AS total_kg
                FROM inputs i
                JOIN members m ON m.id = i.member_id
                WHERE i.cooperative_id = :coop_id
                GROUP BY m.id, m.full_name, m.code
                ORDER BY total_kg DESC
                LIMIT 5
                """
            ),
            {"coop_id": cooperative_id},
        ).fetchall()
    ]

    stocks_by_product = [
        dict(row._mapping)
        for row in db.execute(
            text(
                """
                SELECT p.name AS product_name, s.quantity
                FROM stocks s
                JOIN products p ON p.id = s.product_id
                WHERE s.cooperative_id = :coop_id
                ORDER BY s.quantity DESC, p.name ASC
                LIMIT 8
                """
            ),
            {"coop_id": cooperative_id},
        ).fetchall()
    ]

    batches_open_count = int(
        db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM batches
                WHERE cooperative_id = :coop_id
                  AND status NOT IN ('COMPLETED', 'CANCELLED')
                """
            ),
            {"coop_id": cooperative_id},
        ).scalar()
        or 0
    )

    low_efficiency_count = int(
        db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM batches
                WHERE cooperative_id = :coop_id
                  AND initial_qty > 0
                  AND (current_qty / initial_qty) < 0.80
                """
            ),
            {"coop_id": cooperative_id},
        ).scalar()
        or 0
    )

    material_balance = dict(
        db.execute(
            text(
                """
                SELECT
                  COALESCE(SUM(initial_qty), 0) AS total_input_kg,
                  COALESCE(SUM(current_qty), 0) AS total_output_kg
                FROM batches
                WHERE cooperative_id = :coop_id
                """
            ),
            {"coop_id": cooperative_id},
        ).one()._mapping
    )
    total_input_kg = float(material_balance.get("total_input_kg") or 0.0)
    total_output_kg = float(material_balance.get("total_output_kg") or 0.0)
    material_loss_pct = ((total_input_kg - total_output_kg) / total_input_kg * 100.0) if total_input_kg > 0 else 0.0

    process_loss_by_stage = [
        dict(row._mapping)
        for row in db.execute(
            text(
                """
                SELECT ps.type AS stage, COALESCE(SUM(ps.loss_value), 0) AS total_loss_kg
                FROM process_steps ps
                JOIN batches b ON b.id = ps.batch_id
                WHERE b.cooperative_id = :coop_id
                GROUP BY ps.type
                ORDER BY total_loss_kg DESC
                LIMIT 6
                """
            ),
            {"coop_id": cooperative_id},
        ).fetchall()
    ]

    sql_risk_count = int(
        db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM batches
                WHERE cooperative_id = :coop_id
                  AND initial_qty > 0
                  AND ((initial_qty - current_qty) / initial_qty) * 100 >= :risk_threshold
                """
            ),
            {"coop_id": cooperative_id, "risk_threshold": settings.anomaly_loss_threshold},
        ).scalar()
        or 0
    )

    rag_keyword_count = int(
        db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM rag_chunks
                WHERE cooperative_id = :coop_id
                  AND lower(content) ~ '(séchage|sechage|tri|stockage|humidit)'
                """
            ),
            {"coop_id": cooperative_id},
        ).scalar()
        or 0
    )

    return {
        "members_count": members_count,
        "stocks_count": stocks_count,
        "batches_count": batches_count,
        "batches_open_count": batches_open_count,
        "process_steps_count": process_steps_count,
        "rag_chunks_count": rag_chunks_count,
        "rag_keyword_count": rag_keyword_count,
        "recommendations_count": recommendations_count,
        "orders_count": orders_count,
        "invoices_count": invoices_count,
        "top_members": top_members,
        "stocks_by_product": stocks_by_product,
        "low_efficiency_count": low_efficiency_count,
        "material_balance": {
            "total_input_kg": total_input_kg,
            "total_output_kg": total_output_kg,
            "loss_pct": material_loss_pct,
        },
        "process_loss_by_stage": process_loss_by_stage,
        "sql_risk_count": sql_risk_count,
    }


def _build_cases() -> list[AuditCase]:
    return [
        AuditCase(
            case_id="SQL-MEMBERS-COUNT",
            domain="members",
            question="Combien de membres sont inscrits dans ma coopérative ?",
            expected_routes={"SQL_ONLY"},
            expected_source_types={"sql"},
            expected_block_types={"summary", "sources"},
        ),
        AuditCase(
            case_id="SQL-MEMBERS-TOP-KG",
            domain="members",
            question="Classe les membres par kg collectés, du plus élevé au plus faible.",
            expected_routes={"SQL_ONLY"},
            expected_source_types={"sql"},
            expected_block_types={"summary", "table", "sources"},
        ),
        AuditCase(
            case_id="SQL-STOCKS",
            domain="stocks",
            question="Quel est le stock actuel par produit en kg ?",
            expected_routes={"SQL_ONLY"},
            expected_source_types={"sql"},
            expected_block_types={"summary", "table", "sources"},
        ),
        AuditCase(
            case_id="SQL-COMMERCIAL",
            domain="commercial",
            question="Combien de commandes commerciales et combien de factures avons-nous ?",
            expected_routes={"SQL_ONLY"},
            expected_source_types={"sql"},
            expected_block_types={"summary", "sources"},
        ),
        AuditCase(
            case_id="SQL-BATCHES",
            domain="batches",
            question="Combien de lots au total et combien sont encore en cours ?",
            expected_routes={"SQL_ONLY"},
            expected_source_types={"sql"},
            expected_block_types={"summary", "sources"},
        ),
        AuditCase(
            case_id="SQL-PROCESS-STEPS",
            domain="process_steps",
            question="Quelles étapes du process génèrent les plus grandes pertes ?",
            expected_routes={"SQL_ONLY"},
            expected_source_types={"sql"},
            expected_block_types={"summary", "sources"},
        ),
        AuditCase(
            case_id="SQL-EFFICIENCY",
            domain="efficiency",
            question="Quels lots ont une faible efficacité de rendement ?",
            expected_routes={"SQL_ONLY"},
            expected_source_types={"sql"},
            expected_block_types={"summary", "sources"},
        ),
        AuditCase(
            case_id="SQL-MATERIAL-BALANCE",
            domain="material_balance",
            question="Donne le bilan matière global (entrée/sortie/perte) des lots.",
            expected_routes={"SQL_ONLY"},
            expected_source_types={"sql"},
            expected_block_types={"summary", "sources"},
        ),
        AuditCase(
            case_id="HYBRID-ML-RISK",
            domain="ml_risk",
            question="Quels lots présentent un risque élevé selon le signal ML ?",
            expected_routes={"HYBRID_SQL_ML"},
            expected_source_types={"sql", "ml"},
            expected_block_types={"summary", "sources"},
        ),
        AuditCase(
            case_id="RAG-BEST-PRACTICES",
            domain="rag_best_practices",
            question="Quelles sont les meilleures pratiques de séchage et de tri avec références ?",
            expected_routes={"RAG_ONLY", "HYBRID_SQL_RAG", "HYBRID_FULL"},
            expected_source_types={"rag"},
            expected_block_types={"summary", "sources"},
        ),
        AuditCase(
            case_id="RECOMMENDATIONS",
            domain="recommendations",
            question="Donne des recommandations prioritaires, concrètes et actionnables pour améliorer la production.",
            expected_routes={"RECOMMENDATION_ONLY", "HYBRID_FULL", "HYBRID_RAG_RECOMMENDATION"},
            expected_source_types={"recommendation"},
            expected_block_types={"summary", "sources"},
        ),
        AuditCase(
            case_id="MULTI-INTENT",
            domain="multi_intent",
            question="Donne le stock actuel en kg et les meilleures pratiques de tri/séchage dans la même réponse.",
            expected_routes={"HYBRID_SQL_RAG", "HYBRID_FULL"},
            expected_source_types={"sql", "rag"},
            expected_block_types={"summary", "sources"},
        ),
    ]


def _domain_fact_check(case: AuditCase, truth: dict[str, Any], payload: dict[str, Any]) -> tuple[bool, str]:
    answer = str(payload.get("answer") or "")
    answer_l = answer.lower()

    if case.domain == "members":
        if case.case_id.endswith("COUNT"):
            ok = _contains_number_close(answer, float(truth["members_count"])) and "membre" in answer_l
            return ok, f"expected members_count={truth['members_count']}"
        if truth["top_members"]:
            top = truth["top_members"][0]
            name_ok = str(top["full_name"]).lower() in answer_l or str(top["member_code"]).lower() in answer_l
            kg_ok = _contains_number_close(answer, float(top["total_kg"]))
            return name_ok and kg_ok, f"expected top_member={top['full_name']} ({top['total_kg']} kg)"
        return False, "no top-member truth rows found"

    if case.domain == "stocks":
        if not truth["stocks_by_product"]:
            return "aucun" in answer_l or "insuffisant" in answer_l, "stocks table empty handling"
        lead = truth["stocks_by_product"][0]
        product_ok = str(lead["product_name"]).lower() in answer_l
        qty_ok = _contains_number_close(answer, float(lead["quantity"]))
        return product_ok and qty_ok, f"expected top stock {lead['product_name']}={lead['quantity']} kg"

    if case.domain == "commercial":
        orders_ok = _contains_number_close(answer, float(truth["orders_count"]))
        invoices_ok = _contains_number_close(answer, float(truth["invoices_count"]))
        return (orders_ok or invoices_ok) and ("commande" in answer_l or "facture" in answer_l), (
            f"expected orders={truth['orders_count']} invoices={truth['invoices_count']}"
        )

    if case.domain == "batches":
        total_ok = _contains_number_close(answer, float(truth["batches_count"]))
        open_ok = _contains_number_close(answer, float(truth["batches_open_count"]))
        return (total_ok or open_ok) and ("lot" in answer_l or "batch" in answer_l), (
            f"expected total={truth['batches_count']} open={truth['batches_open_count']}"
        )

    if case.domain == "process_steps":
        if truth["process_loss_by_stage"]:
            top_stage = str(truth["process_loss_by_stage"][0]["stage"]).lower()
            stage_token = top_stage.replace("é", "e")
            answer_token = answer_l.replace("é", "e")
            ok = stage_token in answer_token and ("perte" in answer_l or "loss" in answer_l)
            return ok, f"expected top_loss_stage={truth['process_loss_by_stage'][0]['stage']}"
        return False, "no process-step truth rows found"

    if case.domain == "efficiency":
        count_ok = _contains_number_close(answer, float(truth["low_efficiency_count"]))
        semantic_ok = any(token in answer_l for token in ["effic", "rendement", "perte", "faible"])
        return count_ok and semantic_ok, f"expected low_efficiency_count={truth['low_efficiency_count']}"

    if case.domain == "material_balance":
        balance = truth["material_balance"]
        input_ok = _contains_number_close(answer, float(balance["total_input_kg"]))
        output_ok = _contains_number_close(answer, float(balance["total_output_kg"]))
        loss_ok = _contains_number_close(answer, float(balance["loss_pct"]), tolerance_ratio=0.15, tolerance_abs=1.5)
        semantic_ok = any(token in answer_l for token in ["bilan", "mati", "entrée", "sortie", "perte"])
        return (input_ok or output_ok or loss_ok) and semantic_ok, (
            "expected material balance close to "
            f"in={balance['total_input_kg']:.1f} out={balance['total_output_kg']:.1f} loss={balance['loss_pct']:.1f}%"
        )

    if case.domain == "ml_risk":
        numeric_ok = _contains_number_close(answer, float(truth["sql_risk_count"]))
        semantic_ok = any(token in answer_l for token in ["risque", "ml", "anomal", "élevé", "eleve"])
        return numeric_ok and semantic_ok, f"expected sql_risk_count={truth['sql_risk_count']} (threshold={settings.anomaly_loss_threshold})"

    if case.domain == "rag_best_practices":
        semantic_ok = any(token in answer_l for token in ["séch", "sech", "tri", "humid", "stockage", "pratique"])
        return semantic_ok, "expected domain terms for drying/sorting best practices"

    if case.domain == "recommendations":
        has_action_language = any(token in answer_l for token in ["recommand", "action", "priorit", "amélior", "amelior"])
        no_empty_disclaimer = "aucune recommandation prioritaire confirmée" not in answer_l
        return has_action_language and no_empty_disclaimer, "expected grounded actionable recommendation text"

    if case.domain == "multi_intent":
        stock_signal = any(token in answer_l for token in ["stock", "kg", "produit"])
        rag_signal = any(token in answer_l for token in ["séch", "sech", "tri", "pratique", "référence", "reference"])
        return stock_signal and rag_signal, "expected both stock evidence and RAG best-practice content"

    return False, "unknown domain"


def _evaluate_case(case: AuditCase, truth: dict[str, Any], payload: dict[str, Any], status_code: int) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    checks_total = 0
    checks_passed = 0

    if status_code != 200:
        return {
            "case_id": case.case_id,
            "domain": case.domain,
            "question": case.question,
            "http_status": status_code,
            "score": 0.0,
            "status": "FAIL",
            "issues": [f"/chat/agent returned HTTP {status_code} (expected 200)"],
            "warnings": [],
            "route": "",
            "source_types": [],
            "sql_tables_used": [],
            "response_block_types": [],
            "answer_preview": str(payload)[:240],
            "failure_tags": ["http_failure"],
        }

    route = str(payload.get("route") or "")
    sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
    blocks = payload.get("response_blocks") if isinstance(payload.get("response_blocks"), list) else []
    answer = str(payload.get("answer") or "")

    case_source_types = _source_types(sources)
    sql_tables_used = _parse_sql_tables(sources)
    block_types = _block_types(blocks)

    failure_tags: list[str] = []

    checks_total += 1
    if _route_ok(route, case.expected_routes):
        checks_passed += 1
    else:
        issues.append(f"Route mismatch: expected one of {sorted(case.expected_routes)}, got {route}")
        failure_tags.append("route_mismatch")

    checks_total += 1
    if case.expected_source_types.issubset(case_source_types):
        checks_passed += 1
    else:
        missing = sorted(case.expected_source_types - case_source_types)
        issues.append(f"Missing expected source types: {missing}; got={sorted(case_source_types)}")
        failure_tags.append("missing_source_type")
        if "rag" in missing:
            failure_tags.append("weak_rag")
        if "recommendation" in missing:
            failure_tags.append("weak_recommendation")

    checks_total += 1
    if case.expected_block_types.issubset(block_types):
        checks_passed += 1
    else:
        missing_blocks = sorted(case.expected_block_types - block_types)
        issues.append(f"Missing expected response_blocks types: {missing_blocks}; got={sorted(block_types)}")
        failure_tags.append("missing_response_block")

    checks_total += 1
    fact_ok, fact_hint = _domain_fact_check(case, truth, payload)
    if fact_ok:
        checks_passed += 1
    else:
        issues.append(f"Fact mismatch: {fact_hint}")
        failure_tags.append("fact_mismatch")

    expected_tables = EXPECTED_SQL_TABLES_BY_DOMAIN.get(case.domain, set())
    if expected_tables and "sql" in case_source_types:
        checks_total += 1
        if sql_tables_used & expected_tables:
            checks_passed += 1
        else:
            issues.append(
                f"Wrong SQL table use: expected overlap with {sorted(expected_tables)}, got {sorted(sql_tables_used)}"
            )
            failure_tags.append("wrong_table_use")

    # Domain-specific warnings
    lower_answer = answer.lower()
    if "les données disponibles ne permettent pas de confirmer ce point" in lower_answer:
        warnings.append("fallback_safe_answer_detected")
        failure_tags.append("fallback_answer")
    if case.domain == "recommendations":
        recommendation_blocks = [block for block in blocks if str(block.get("type") or "").lower() == "recommendations"]
        if not recommendation_blocks:
            warnings.append("recommendation_block_missing")
            failure_tags.append("weak_recommendation")
    if case.domain == "multi_intent":
        if "rag" not in case_source_types or "sql" not in case_source_types:
            warnings.append("multi_intent_not_fully_covered")
            failure_tags.append("multi_intent_failure")

    score = checks_passed / checks_total if checks_total else 0.0
    if score >= 0.85:
        grade = "PASS"
    elif score >= 0.55:
        grade = "PARTIAL"
    else:
        grade = "FAIL"

    return {
        "case_id": case.case_id,
        "domain": case.domain,
        "question": case.question,
        "http_status": status_code,
        "score": round(score, 4),
        "status": grade,
        "issues": issues,
        "warnings": warnings,
        "route": route,
        "source_types": sorted(case_source_types),
        "sql_tables_used": sorted(sql_tables_used),
        "response_block_types": sorted(block_types),
        "answer_preview": answer[:420],
        "failure_tags": sorted(set(failure_tags)),
    }


def _diagnose_chat_persistence(
    *,
    cooperative_truth: dict[str, Any],
    headers: dict[str, str],
    session_id: str,
) -> dict[str, Any]:
    marker = f"AUDIT-PERSIST-{uuid4()}"
    client_safe = TestClient(app, raise_server_exceptions=False)
    client_strict = TestClient(app, raise_server_exceptions=True)

    db_before = next(get_db())
    before_count = int(
        db_before.execute(
            select(text("COUNT(*)")).select_from(ChatMessage).where(ChatMessage.session_id == session_id)
        ).scalar()
        or 0
    )
    db_before.close()

    response_existing = client_safe.post(
        "/chat/agent",
        json={
            "message": f"Réponds brièvement et conserve ce marqueur: {marker}",
            "conversation_id": session_id,
            "language": "fr",
        },
        headers=headers,
    )
    existing_body: dict[str, Any] = response_existing.json() if response_existing.status_code == 200 else {}
    returned_conversation_id = str((existing_body.get("metadata") or {}).get("conversation_id") or "")

    db_after = next(get_db())
    after_count = int(
        db_after.execute(
            select(text("COUNT(*)")).select_from(ChatMessage).where(ChatMessage.session_id == session_id)
        ).scalar()
        or 0
    )
    marker_hits = int(
        db_after.execute(
            select(text("COUNT(*)"))
            .select_from(ChatMessage)
            .where(ChatMessage.session_id == session_id, ChatMessage.content.ilike(f"%{marker}%"))
        ).scalar()
        or 0
    )
    db_after.close()

    sessions_refresh = client_safe.get("/chat/sessions", headers=headers)
    messages_refresh = client_safe.get(f"/chat/sessions/{session_id}/messages", headers=headers)

    missing_conversation_exception = ""
    missing_conversation_status = None
    fk_signature_seen = False
    try:
        # This probes the path where backend must create chat_session itself.
        client_strict.post(
            "/chat/agent",
            json={"message": "Probe session auto-create path (no conversation id)", "language": "fr"},
            headers=headers,
        )
    except Exception as exc:  # noqa: BLE001 - we need exact runtime exception shape for diagnosis
        missing_conversation_exception = str(exc)
        fk_signature_seen = "fk_chat_messages_session_id_chat_sessions" in missing_conversation_exception.lower() or (
            "foreignkeyviolation" in missing_conversation_exception.lower()
        )
    else:
        fallback_response = client_safe.post(
            "/chat/agent",
            json={"message": "Probe session auto-create path (no conversation id)", "language": "fr"},
            headers=headers,
        )
        missing_conversation_status = fallback_response.status_code

    inspector = sa_inspect(next(get_db()).get_bind())
    ai_audit_log_table_exists = "ai_chat_audit_logs" in inspector.get_table_names()

    source_generate_reply = inspect.getsource(agent_assistant_service.generate_agent_chat_reply)
    source_audit_logger = inspect.getsource(AuditLogger.log)
    has_commit_in_generate_reply = "db.commit(" in source_generate_reply
    has_flush_before_orchestrator = "db.flush()" in source_generate_reply and "orchestrator.handle" in source_generate_reply
    logger_uses_nested_tx = "begin_nested" in source_audit_logger
    logger_uses_direct_commit = "self.db.commit(" in source_audit_logger
    # Static probe: the orchestrator composes AuditLogger.
    uses_orchestrator = "AgentOrchestrator" in source_generate_reply

    persistence_ok = response_existing.status_code == 200 and after_count > before_count and marker_hits > 0

    root_causes: list[str] = []
    if not ai_audit_log_table_exists:
        if logger_uses_nested_tx and not logger_uses_direct_commit and persistence_ok:
            root_causes.append(
                "Table ai_chat_audit_logs is still missing in Supabase, but logger isolation now prevents it from breaking chat persistence."
            )
        else:
            root_causes.append(
                "Missing table ai_chat_audit_logs can break logging and may affect chat transaction safety if logger is not isolated."
            )
    if fk_signature_seen:
        root_causes.append(
            "Without conversation_id, /chat/agent can fail with FK violation: assistant message insert references session_id rolled back before insert."
        )
    if not has_commit_in_generate_reply:
        root_causes.append(
            "generate_agent_chat_reply has no final db.commit(); assistant/user messages are not durable at request end."
        )
    if response_existing.status_code == 200 and after_count == before_count and marker_hits == 0:
        root_causes.append(
            "Existing-conversation call returns 200 but chat_messages count does not increase; refresh reload shows no new messages."
        )

    return {
        "probe_marker": marker,
        "existing_conversation_call": {
            "status_code": response_existing.status_code,
            "returned_conversation_id": returned_conversation_id,
        },
        "message_count_before": before_count,
        "message_count_after": after_count,
        "marker_hits_after": marker_hits,
        "refresh_sessions_status": sessions_refresh.status_code,
        "refresh_messages_status": messages_refresh.status_code,
        "missing_conversation_probe_status": missing_conversation_status,
        "missing_conversation_exception_head": missing_conversation_exception[:900],
        "fk_signature_seen": fk_signature_seen,
        "chat_audit_log_table_exists": ai_audit_log_table_exists,
        "transaction_static_signals": {
            "generate_reply_has_commit": has_commit_in_generate_reply,
            "generate_reply_has_flush_before_orchestrator": has_flush_before_orchestrator,
            "generate_reply_uses_orchestrator": uses_orchestrator,
            "audit_logger_source_loaded": bool(source_audit_logger),
            "audit_logger_uses_nested_tx": logger_uses_nested_tx,
            "audit_logger_uses_direct_commit": logger_uses_direct_commit,
        },
        "persistence_ok_after_refresh": persistence_ok,
        "root_causes": root_causes,
        "truth_context": {
            "chat_sessions_count": cooperative_truth.get("chat_sessions_count"),
            "chat_messages_count": cooperative_truth.get("chat_messages_count"),
        },
    }


def _write_report(payload: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_REPORT_PATH.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    summary = payload["summary"]
    db_meta = payload["database"]
    rag_meta = payload["rag"]
    persistence = payload["persistence"]

    lines: list[str] = [
        "# Supabase Real-App Chatbot Audit",
        "",
        f"- Timestamp UTC: {payload['timestamp_utc']}",
        f"- Audit mode: {payload['audit_mode']}",
        f"- Database dialect: {db_meta['dialect']}",
        f"- Database provider: {db_meta['provider']}",
        f"- URL masked: {db_meta['url_masked']}",
        f"- pgvector extension installed: {db_meta['pgvector_extension_installed']}",
        f"- RAG tables accessible: rag_documents={rag_meta['rag_documents_exists']}, rag_chunks={rag_meta['rag_chunks_exists']}",
        "",
        "## Overall Result",
        "",
        f"- Total cases: {summary['total_cases']}",
        f"- PASS: {summary['pass_count']}",
        f"- PARTIAL: {summary['partial_count']}",
        f"- FAIL: {summary['fail_count']}",
        f"- Overall verdict: {summary['overall_verdict']}",
        "",
        "## Case Results",
        "",
    ]

    for result in payload["cases"]:
        lines.append(f"### {result['case_id']} [{result['status']}] score={result['score']}")
        lines.append(f"- Domain: {result['domain']}")
        lines.append(f"- HTTP status: {result['http_status']}")
        lines.append(f"- Route: {result['route']}")
        lines.append(f"- Source types: {', '.join(result['source_types']) if result['source_types'] else 'none'}")
        lines.append(
            f"- response_blocks: {', '.join(result['response_block_types']) if result['response_block_types'] else 'none'}"
        )
        if result["issues"]:
            for issue in result["issues"]:
                lines.append(f"- Issue: {issue}")
        if result["warnings"]:
            for warning in result["warnings"]:
                lines.append(f"- Warning: {warning}")
        lines.append(f"- Question: {result['question']}")
        lines.append("")

    lines.extend(
        [
            "## Persistence Diagnosis",
            "",
            f"- existing /chat/agent status: {persistence['existing_conversation_call']['status_code']}",
            (
                "- conversation_id preserved in metadata: "
                f"{persistence['existing_conversation_call']['returned_conversation_id']}"
            ),
            (
                "- message count for probed session: "
                f"{persistence['message_count_before']} -> {persistence['message_count_after']}"
            ),
            f"- marker hits after call: {persistence['marker_hits_after']}",
            (
                "- refresh API status: "
                f"/chat/sessions={persistence['refresh_sessions_status']}, "
                f"/chat/sessions/{{id}}/messages={persistence['refresh_messages_status']}"
            ),
            f"- missing conversation FK signature seen: {persistence['fk_signature_seen']}",
            f"- ai_chat_audit_logs table exists: {persistence['chat_audit_log_table_exists']}",
            f"- persistence_ok_after_refresh: {persistence['persistence_ok_after_refresh']}",
            "",
            "### Root Causes",
            "",
        ]
    )
    if persistence["root_causes"]:
        for cause in persistence["root_causes"]:
            lines.append(f"- {cause}")
    else:
        lines.append("- No persistence root cause detected from this run.")

    lines.extend(
        [
            "",
            "## Recommended Fixes (Not Applied In This Audit)",
            "",
            "1. Add a final `db.commit()` in `generate_agent_chat_reply` after assistant message + updated_at update.",
            "2. Decouple `AuditLogger` transaction from chat persistence transaction (separate session or savepoint).",
            "3. Ensure `ai_chat_audit_logs` migration is applied in Supabase or make logger failure non-rolling-back for chat persistence path.",
            "4. Preserve atomic order: session create/resolve -> user message -> assistant message -> commit, with one rollback scope.",
            "5. Add integration test: existing conversation returns 200 AND message appears via `/chat/sessions/{id}/messages` after refresh.",
        ]
    )

    MD_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


class TestChatbotRealAppAudit:
    @pytest.fixture(autouse=True, scope="function")
    def _setup(self):
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        if settings.audit_mode != "supabase_readonly":
            pytest.skip(f"Expected --env=supabase_readonly, got {settings.audit_mode}")
        EnvironmentParityAudit.log_parity_header(
            "Supabase Real-App Chatbot Audit",
            "Authenticated /chat/agent + persistence diagnosis",
        )
        yield

    def test_real_supabase_chatbot_audit_and_persistence(self):
        db = next(get_db())
        user = get_or_create_test_user(db)
        headers = get_test_auth_header(user.id)

        dialect = db.get_bind().dialect.name
        assert dialect == "postgresql", f"Expected Supabase PostgreSQL dialect, got {dialect}"
        assert "sqlite" not in settings.effective_database_url.lower(), "Audit must not use SQLite."

        pgvector_installed = bool(
            db.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'")).scalar()
        )
        rag_documents_exists = _table_exists(db, "rag_documents")
        rag_chunks_exists = _table_exists(db, "rag_chunks")
        assert rag_documents_exists or rag_chunks_exists, "RAG tables not accessible from Supabase."

        cooperative_truth = _build_truth_snapshot(db, user.cooperative_id)
        cooperative_truth["chat_sessions_count"] = _row_count(db, "chat_sessions") or 0
        cooperative_truth["chat_messages_count"] = _row_count(db, "chat_messages") or 0

        # Use existing chat session to enforce authenticated /chat/agent 200 path.
        existing_session = db.scalar(
            select(ChatSession.id)
            .where(ChatSession.user_id == user.id)
            .order_by(ChatSession.updated_at.desc())
            .limit(1)
        )
        assert existing_session is not None, "No existing chat_session for authenticated user; cannot run stable 200 audit path."
        session_id = str(existing_session)

        client = TestClient(app, raise_server_exceptions=False)
        cases = _build_cases()
        results: list[dict[str, Any]] = []

        for case in cases:
            response = client.post(
                "/chat/agent",
                json={
                    "message": case.question,
                    "conversation_id": session_id,
                    "language": "fr",
                },
                headers=headers,
            )
            payload = response.json() if response.status_code == 200 else {"detail": response.text}
            results.append(_evaluate_case(case, cooperative_truth, payload, response.status_code))

        # Required by scope: authenticated /chat/agent returns 200.
        assert any(result["http_status"] == 200 for result in results), "/chat/agent never returned 200 in authenticated mode."

        # Diagnose persistence after refresh.
        persistence = _diagnose_chat_persistence(
            cooperative_truth=cooperative_truth,
            headers=headers,
            session_id=session_id,
        )

        pass_count = sum(1 for item in results if item["status"] == "PASS")
        partial_count = sum(1 for item in results if item["status"] == "PARTIAL")
        fail_count = sum(1 for item in results if item["status"] == "FAIL")
        total_cases = len(results)

        if fail_count == 0 and partial_count <= 2:
            overall_verdict = "PASS"
        elif fail_count <= max(2, total_cases // 4):
            overall_verdict = "PARTIAL"
        else:
            overall_verdict = "FAIL"

        worst_failures = sorted(
            [item for item in results if item["status"] == "FAIL"],
            key=lambda item: item["score"],
        )[:5]

        common_failure_tags: dict[str, int] = {}
        for result in results:
            for tag in result.get("failure_tags", []):
                common_failure_tags[tag] = common_failure_tags.get(tag, 0) + 1

        report_payload: dict[str, Any] = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "audit_mode": settings.audit_mode,
            "database": {
                "provider": "Supabase PostgreSQL",
                "dialect": dialect,
                "url_masked": settings.masked_database_url,
                "pgvector_extension_installed": pgvector_installed,
                "db_info": EnvironmentParityAudit.get_db_info(db),
            },
            "rag": {
                "rag_documents_exists": rag_documents_exists,
                "rag_chunks_exists": rag_chunks_exists,
                "rag_info": EnvironmentParityAudit.get_rag_info(db),
            },
            "truth_snapshot": cooperative_truth,
            "summary": {
                "total_cases": total_cases,
                "pass_count": pass_count,
                "partial_count": partial_count,
                "fail_count": fail_count,
                "overall_verdict": overall_verdict,
                "failure_tag_counts": common_failure_tags,
            },
            "cases": results,
            "worst_failures": worst_failures,
            "persistence": persistence,
            "exact_failing_questions": [
                {"case_id": item["case_id"], "question": item["question"], "status": item["status"], "issues": item["issues"]}
                for item in results
                if item["status"] != "PASS"
            ],
            "suspected_root_causes": persistence["root_causes"],
            "next_recommended_fixes": [
                "Add db.commit() at end of generate_agent_chat_reply after assistant message write.",
                "Isolate AuditLogger failures from chat transaction rollback.",
                "Apply/create ai_chat_audit_logs table migration in Supabase.",
                "Add integration test asserting message persistence across refresh APIs.",
            ],
        }

        _write_report(report_payload)

        print(f"\nJSON report: {JSON_REPORT_PATH}")
        print(f"Markdown report: {MD_REPORT_PATH}")
        print(f"Overall verdict: {overall_verdict}")

        db.close()

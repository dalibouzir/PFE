from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy import func, inspect
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.models.batch import Batch
from app.models.commercial_invoice import CommercialInvoice
from app.models.commercial_order import CommercialOrder
from app.models.enums import BatchStatus, RiskLevel
from app.models.global_charge import GlobalCharge
from app.models.input import Input
from app.models.member import Member
from app.models.parcel import Parcel
from app.models.ml import MLPredictionLog
from app.models.process_step import ProcessStep
from app.models.rag import RAGChunk, RAGDocument
from app.models.recommendation import Recommendation
from app.models.treasury_transaction import TreasuryTransaction
from app.models.user import User
from app.ai.orchestrator.audit_logger import AuditLogger
from app.core.config import Settings
from app.ai.utils.audit_environment import EnvironmentParityAudit

from tests.ai.test_chatbot_system_audit import _seed_audit_data

settings = Settings()
# Log environment parity for audit
EnvironmentParityAudit.log_parity_header("Evidence Role Truth Audit", f"Mode={settings.audit_mode}")

REPORT_DIR = Path(__file__).resolve().parents[2] / "app" / "ai" / "reports"
JSON_REPORT_PATH = REPORT_DIR / "chatbot_evidence_role_truth_audit.json"
MD_REPORT_PATH = REPORT_DIR / "chatbot_evidence_role_truth_audit.md"

STRICT_LABELS = {
    "MISSING_EXPECTED_ROWS",
    "WRONG_FINAL_FOCUS",
    "RAG_CONTENT_MISSING",
    "WRONG_EVIDENCE_ROLE",
    "HYBRID_COMBINATION_WEAK",
    "GENERIC_ANSWER_WITH_AVAILABLE_EVIDENCE",
    "MISSING_RESPONSE_BLOCKS",
}


@dataclass(frozen=True)
class EvidenceRoleCase:
    case_id: str
    module: str
    question: str
    expected_route: str
    accepted_routes: tuple[str, ...]
    expected_source_types: set[str]
    expected_evidence_role: str
    truth_builder: Callable[[Any, User], dict[str, Any]]
    validator: Callable[[dict[str, Any], dict[str, Any]], tuple[list[str], dict[str, Any]]]
    required_block_types: tuple[str, ...] = ()


def _post_agent(client: TestClient, question: str) -> dict[str, Any]:
    response = client.post(
        "/chat/agent",
        json={
            "message": question,
            "language": "fr",
            "conversation_id": str(uuid4()),
        },
    )
    assert response.status_code == 200
    return response.json()


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _source_types(payload: dict[str, Any]) -> set[str]:
    return {
        _norm(src.get("type"))
        for src in (payload.get("sources") or [])
        if isinstance(src, dict) and src.get("type")
    }


def _response_block_types(payload: dict[str, Any]) -> set[str]:
    blocks = payload.get("response_blocks") or []
    if not isinstance(blocks, list):
        return set()
    return {
        _norm(item.get("type"))
        for item in blocks
        if isinstance(item, dict) and item.get("type")
    }


def _principal_line(answer: str) -> str:
    lines = [line.strip() for line in str(answer or "").splitlines()]
    if "1. Résultat principal" in lines:
        idx = lines.index("1. Résultat principal")
        for line in lines[idx + 1 :]:
            if line:
                return line
    return lines[0] if lines else ""


def _contains_generic_uncertainty(answer: str) -> bool:
    lowered = str(answer or "").lower()
    return (
        "ne permettent pas de confirmer" in lowered
        or "données disponibles ne permettent" in lowered
        or "données insuffisantes" in lowered
    )


def _answer_refs(answer: str) -> set[str]:
    refs = set(re.findall(r"[A-Za-z]{2,}-\d{3,}", str(answer or "")))
    return {_norm(ref) for ref in refs}


def _has_any_term(answer: str, terms: list[str]) -> bool:
    lowered = str(answer or "").lower()
    return any(_norm(term) in lowered for term in terms if _norm(term))


def _term_hits(answer: str, terms: list[str]) -> list[str]:
    lowered = str(answer or "").lower()
    return [term for term in terms if _norm(term) and _norm(term) in lowered]


def _first_user(db_session) -> User:
    user = db_session.query(User).first()
    if user is None or user.cooperative_id is None:
        raise RuntimeError("No seeded user/cooperative available")
    return user


def _setup_isolated_overrides(db_session) -> None:
    bind = db_session.get_bind()
    SessionLocal = sessionmaker(bind=bind, autoflush=False, autocommit=False, expire_on_commit=False)
    seeded_user = _first_user(db_session)

    def override_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: seeded_user


def _table_exists(db_session, table_name: str) -> bool:
    try:
        return bool(inspect(db_session.get_bind()).has_table(table_name))
    except Exception:
        return False


def _truth_in_progress_lots(db_session, user: User) -> dict[str, Any]:
    refs = [
        str(row[0])
        for row in db_session.execute(
            select(Batch.code)
            .where(Batch.cooperative_id == user.cooperative_id, Batch.status == BatchStatus.IN_PROGRESS)
            .order_by(Batch.code.asc())
        ).all()
    ]
    return {
        "refs": refs,
        "truth_summary": f"in_progress_lots={len(refs)} | refs={', '.join(refs)}",
    }


def _truth_low_efficiency_lots(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(Batch.code, Batch.initial_qty, Batch.current_qty).where(Batch.cooperative_id == user.cooperative_id)
    ).all()
    refs: list[str] = []
    for code, initial, current in rows:
        ini = float(initial or 0.0)
        cur = float(current or 0.0)
        eff = (cur / ini * 100.0) if ini > 0 else 0.0
        if eff < 85.0:
            refs.append(str(code))
    refs.sort()
    return {
        "refs": refs,
        "truth_summary": f"low_efficiency_lots={len(refs)} | refs={', '.join(refs)}",
    }


def _truth_rag_drying(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(RAGDocument.title, RAGChunk.content)
        .join(RAGChunk, RAGChunk.document_id == RAGDocument.id)
        .where(RAGDocument.cooperative_id == user.cooperative_id)
    ).all()
    titles = [str(title) for title, _ in rows]
    drying_rows = [(str(title), str(content)) for title, content in rows if "séchage" in _norm(title + " " + content)]
    terms = ["humidité", "retourner", "claies", "surcharge", "bonnes pratiques", "séchage"]
    return {
        "titles": titles,
        "drying_rows": drying_rows,
        "rag_terms": terms,
        "truth_summary": f"rag_drying_chunks={len(drying_rows)} | titles={', '.join(t for t,_ in drying_rows[:3])}",
    }


def _truth_rag_sorting(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(RAGDocument.title, RAGChunk.content)
        .join(RAGChunk, RAGChunk.document_id == RAGDocument.id)
        .where(RAGDocument.cooperative_id == user.cooperative_id)
    ).all()
    sorting_rows = [(str(title), str(content)) for title, content in rows if "tri" in _norm(title + " " + content)]
    terms = ["maturité", "grades", "blessés", "tri", "bonnes pratiques"]
    return {
        "sorting_rows": sorting_rows,
        "rag_terms": terms,
        "truth_summary": f"rag_sorting_chunks={len(sorting_rows)}",
    }


def _truth_hybrid_balance(db_session, user: User) -> dict[str, Any]:
    row = db_session.execute(
        select(Batch.code, Batch.initial_qty, Batch.current_qty)
        .where(Batch.cooperative_id == user.cooperative_id, Batch.code == "MANG-004")
    ).first()
    if row is None:
        return {
            "exists": False,
            "sql_terms": [],
            "rag_terms": ["bilan matière", "quantités", "efficacité", "pertes"],
            "truth_summary": "MANG-004 absent",
        }
    code, initial, current = row
    ini = float(initial or 0.0)
    cur = float(current or 0.0)
    loss = ((ini - cur) / ini * 100.0) if ini > 0 else 0.0
    eff = (cur / ini * 100.0) if ini > 0 else 0.0
    return {
        "exists": True,
        "batch_ref": str(code),
        "loss": loss,
        "eff": eff,
        "sql_terms": [str(code), f"{loss:.1f}", f"{eff:.1f}", "bilan matière"],
        "rag_terms": ["quantités entrantes", "sortantes", "identifier les pertes", "efficacité"],
        "truth_summary": f"{code}: loss={loss:.1f}% eff={eff:.1f}% + rag_material_balance_chunk",
    }


def _truth_ml_high_risk(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(Batch.code, MLPredictionLog.risk_level)
        .join(Batch, Batch.id == MLPredictionLog.batch_id)
        .where(Batch.cooperative_id == user.cooperative_id)
    ).all()
    high_refs = [str(code) for code, level in rows if level == RiskLevel.HIGH]
    return {
        "high_refs": high_refs,
        "truth_summary": f"ml_high_risk_refs={', '.join(high_refs) if high_refs else 'none'}",
    }


def _truth_recommendations(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(Batch.code, Recommendation.suggested_action)
        .join(Batch, Batch.id == Recommendation.batch_id)
        .where(Batch.cooperative_id == user.cooperative_id)
    ).all()
    return {
        "refs": [str(code) for code, _ in rows],
        "count": len(rows),
        "truth_summary": f"recommendation_rows={len(rows)}",
    }


def _truth_stocks(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(Batch.code).where(Batch.cooperative_id == user.cooperative_id, Batch.status == BatchStatus.IN_PROGRESS)
    ).all()
    return {
        "truth_summary": f"batches_rows={len(rows)}",
    }


def _truth_members_list(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(Member.full_name, Member.code)
        .where(Member.cooperative_id == user.cooperative_id)
        .order_by(Member.full_name.asc())
    ).all()
    refs = [str(name) for name, _ in rows]
    return {
        "refs": refs,
        "truth_summary": f"members_rows={len(rows)}",
    }


def _truth_parcels_list(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(Parcel.name).where(Parcel.cooperative_id == user.cooperative_id).order_by(Parcel.name.asc())
    ).all()
    refs = [str(name) for (name,) in rows]
    return {
        "refs": refs,
        "truth_summary": f"parcels_rows={len(rows)}",
    }


def _truth_today_collections(db_session, user: User) -> dict[str, Any]:
    today = date.today()
    qty = float(
        db_session.scalar(
            select(func.coalesce(func.sum(Input.quantity), 0.0)).where(
                Input.cooperative_id == user.cooperative_id,
                Input.date == today,
            )
        )
        or 0.0
    )
    return {
        "qty": qty,
        "truth_summary": f"collections_today_kg={qty:.1f}",
    }


def _truth_stock_mango(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(func.coalesce(func.sum(Input.quantity), 0.0))
        .join(Member, Member.id == Input.member_id)
        .where(Member.cooperative_id == user.cooperative_id)
    ).all()
    return {
        "truth_summary": f"mango_stock_probe={len(rows)}",
    }


def _truth_stage_compare(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(
            ProcessStep.type,
            func.avg(func.coalesce(((ProcessStep.qty_in - ProcessStep.qty_out) * 100.0) / func.nullif(ProcessStep.qty_in, 0), 0.0)),
        )
        .join(Batch, Batch.id == ProcessStep.batch_id)
        .where(Batch.cooperative_id == user.cooperative_id)
        .group_by(ProcessStep.type)
    ).all()
    mapping = {str(stage).lower(): float(loss or 0.0) for stage, loss in rows}
    return {
        "drying": mapping.get("drying", mapping.get("séchage", mapping.get("sechage", 0.0))),
        "sorting": mapping.get("sorting", mapping.get("tri", 0.0)),
        "truth_summary": "stage_compare_drying_sorting",
    }


def _truth_member_ranking_kg(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(Member.full_name, Member.code, func.coalesce(func.sum(Input.quantity), 0.0))
        .join(Input, Input.member_id == Member.id)
        .where(Member.cooperative_id == user.cooperative_id)
        .group_by(Member.full_name, Member.code)
        .order_by(func.coalesce(func.sum(Input.quantity), 0.0).desc())
    ).all()
    return {
        "rows": [(str(name), str(code), float(qty or 0.0)) for name, code, qty in rows],
        "truth_summary": "member_ranking_kg=" + ", ".join(f"{name}:{qty:.1f}" for name, _, qty in rows[:5]),
    }


def _truth_member_ranking_value(db_session, user: User) -> dict[str, Any]:
    module_exists = _table_exists(db_session, "global_charges")
    rows = []
    if module_exists:
        rows = db_session.execute(
            select(Member.full_name, Member.code, func.coalesce(func.sum(GlobalCharge.amount_fcfa), 0.0))
            .join(GlobalCharge, GlobalCharge.member_id == Member.id)
            .where(Member.cooperative_id == user.cooperative_id)
            .group_by(Member.full_name, Member.code)
            .order_by(func.coalesce(func.sum(GlobalCharge.amount_fcfa), 0.0).desc())
        ).all()
    return {
        "module_exists": module_exists,
        "rows": [(str(name), str(code), float(total or 0.0)) for name, code, total in rows],
        "truth_summary": f"member_value_module_exists={module_exists} | rows={len(rows)}",
    }


def _truth_invoices(db_session, user: User) -> dict[str, Any]:
    module_exists = _table_exists(db_session, "commercial_invoices")
    rows = []
    if module_exists:
        rows = db_session.execute(
            select(CommercialInvoice.invoice_number, CommercialInvoice.status)
            .where(CommercialInvoice.cooperative_id == user.cooperative_id)
            .order_by(CommercialInvoice.issue_date.desc())
        ).all()
    return {
        "module_exists": module_exists,
        "rows": [(str(number), str(status.value if hasattr(status, "value") else status)) for number, status in rows],
        "truth_summary": f"invoices_module_exists={module_exists} | rows={len(rows)}",
    }


def _truth_commercial_orders(db_session, user: User) -> dict[str, Any]:
    module_exists = _table_exists(db_session, "commercial_orders")
    rows = []
    if module_exists:
        rows = db_session.execute(
            select(CommercialOrder.order_number, CommercialOrder.status, CommercialOrder.total_amount_fcfa)
            .where(CommercialOrder.cooperative_id == user.cooperative_id)
            .order_by(CommercialOrder.received_at.desc())
        ).all()
    return {
        "module_exists": module_exists,
        "rows": [
            (str(number), str(status.value if hasattr(status, "value") else status), float(total or 0.0))
            for number, status, total in rows
        ],
        "truth_summary": f"commercial_orders_module_exists={module_exists} | rows={len(rows)}",
    }


def _truth_finance(db_session, user: User) -> dict[str, Any]:
    treasury_exists = _table_exists(db_session, "treasury_transactions")
    charge_exists = _table_exists(db_session, "global_charges")
    treasury_count = 0
    charge_count = 0
    if treasury_exists:
        treasury_count = int(
            db_session.scalar(
                select(func.count(TreasuryTransaction.id)).where(TreasuryTransaction.cooperative_id == user.cooperative_id)
            )
            or 0
        )
    if charge_exists:
        charge_count = int(
            db_session.scalar(select(func.count(GlobalCharge.id)).where(GlobalCharge.cooperative_id == user.cooperative_id))
            or 0
        )
    return {
        "module_exists": treasury_exists or charge_exists,
        "rows_count": treasury_count + charge_count,
        "truth_summary": f"finance_module_exists={treasury_exists or charge_exists} | rows={treasury_count + charge_count}",
    }


def _validate_sql_list(truth: dict[str, Any], payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    mismatches: list[str] = []
    answer = str(payload.get("answer") or "")
    principal = _principal_line(answer)
    refs_expected = {_norm(ref) for ref in truth.get("refs", [])}
    refs_found = _answer_refs(answer)

    if refs_expected and not refs_expected.issubset(refs_found):
        mismatches.append("MISSING_EXPECTED_ROWS")

    if _contains_generic_uncertainty(answer) and refs_expected:
        mismatches.append("GENERIC_ANSWER_WITH_AVAILABLE_EVIDENCE")

    if principal.lower().startswith("le lot") or "étape critique" in principal.lower():
        mismatches.append("WRONG_FINAL_FOCUS")

    detail = {
        "refs_expected": sorted(refs_expected),
        "refs_found": sorted(refs_found),
        "principal_line": principal,
    }
    return sorted(set(mismatches)), detail


def _validate_low_efficiency_list(truth: dict[str, Any], payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    mismatches, detail = _validate_sql_list(truth, payload)
    principal = str(detail.get("principal_line") or "").lower()
    if "étape critique" in principal or "séchage" in principal and "lot" in principal:
        mismatches.append("WRONG_FINAL_FOCUS")
    return sorted(set(mismatches)), detail


def _validate_rag_only(truth: dict[str, Any], payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    mismatches: list[str] = []
    answer = str(payload.get("answer") or "")
    principal = _principal_line(answer)
    hits = _term_hits(answer, truth.get("rag_terms", []))

    if _contains_generic_uncertainty(answer) and truth.get("drying_rows") is not None:
        mismatches.append("GENERIC_ANSWER_WITH_AVAILABLE_EVIDENCE")

    if len(hits) < 2:
        mismatches.append("RAG_CONTENT_MISSING")

    sql_focus_markers = ("lot ", "perte cumulée", "étape critique", "mang-", "batch-")
    sql_focus = any(marker in answer.lower() for marker in sql_focus_markers)
    if sql_focus and len(hits) < 2:
        mismatches.append("WRONG_FINAL_FOCUS")
        mismatches.append("WRONG_EVIDENCE_ROLE")

    detail = {
        "rag_terms_expected": truth.get("rag_terms", []),
        "rag_terms_found": hits,
        "principal_line": principal,
    }
    return sorted(set(mismatches)), detail


def _validate_hybrid_sql_rag(truth: dict[str, Any], payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    mismatches: list[str] = []
    answer = str(payload.get("answer") or "")
    source_types = _source_types(payload)
    sql_markers = truth.get("sql_terms", [])
    rag_markers = truth.get("rag_terms", [])

    sql_hits = _term_hits(answer, sql_markers)
    rag_hits = _term_hits(answer, rag_markers)

    has_sql_role = bool(sql_hits)
    has_rag_role = bool(rag_hits)

    if not ({"sql", "rag"}.issubset(source_types)):
        mismatches.append("WRONG_EVIDENCE_ROLE")

    if not has_sql_role or not has_rag_role:
        mismatches.append("HYBRID_COMBINATION_WEAK")

    if has_sql_role and not has_rag_role:
        mismatches.append("WRONG_FINAL_FOCUS")

    if _contains_generic_uncertainty(answer) and truth.get("exists"):
        mismatches.append("GENERIC_ANSWER_WITH_AVAILABLE_EVIDENCE")

    detail = {
        "sql_terms_expected": sql_markers,
        "sql_terms_found": sql_hits,
        "rag_terms_expected": rag_markers,
        "rag_terms_found": rag_hits,
        "principal_line": _principal_line(answer),
    }
    return sorted(set(mismatches)), detail


def _validate_hybrid_sql_ml(truth: dict[str, Any], payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    mismatches: list[str] = []
    answer = str(payload.get("answer") or "")
    source_types = _source_types(payload)
    refs_found = _answer_refs(answer)
    refs_expected = {_norm(ref) for ref in truth.get("high_refs", [])}

    if not ({"sql", "ml"}.issubset(source_types)):
        mismatches.append("WRONG_EVIDENCE_ROLE")

    if refs_expected and not refs_expected.intersection(refs_found):
        mismatches.append("MISSING_EXPECTED_ROWS")

    if "signal ml" not in answer.lower() and "risque" not in answer.lower():
        mismatches.append("WRONG_EVIDENCE_ROLE")

    detail = {
        "refs_expected": sorted(refs_expected),
        "refs_found": sorted(refs_found),
        "principal_line": _principal_line(answer),
    }
    return sorted(set(mismatches)), detail


def _validate_recommendation_role(truth: dict[str, Any], payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    mismatches: list[str] = []
    metadata = payload.get("metadata") or {}
    debug = metadata.get("agent_debug") or {}
    reco_data = ((debug.get("RecommendationAgent") or {}).get("data") or {}) if isinstance(debug, dict) else {}
    recs = reco_data.get("recommendations") if isinstance(reco_data, dict) else []
    answer = str(payload.get("answer") or "")

    if "recommendation" not in _source_types(payload):
        mismatches.append("WRONG_EVIDENCE_ROLE")

    if truth.get("count", 0) == 0 and not recs:
        if "insuffis" not in answer.lower() and "aucune recommandation prioritaire" not in answer.lower():
            mismatches.append("WRONG_FINAL_FOCUS")

    detail = {
        "recommendation_rows": int(truth.get("count", 0)),
        "recommendations_returned": len(recs) if isinstance(recs, list) else 0,
        "principal_line": _principal_line(answer),
    }
    return sorted(set(mismatches)), detail


def _validate_stocks_sql_only(_: dict[str, Any], payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    mismatches: list[str] = []
    answer = str(payload.get("answer") or "")
    principal = _principal_line(answer).lower()
    if "mangue" not in answer.lower() or "arachide" not in answer.lower():
        mismatches.append("MISSING_EXPECTED_ROWS")
    if "stocks actuels" not in answer.lower() and "stock" not in principal:
        mismatches.append("WRONG_FINAL_FOCUS")
    return sorted(set(mismatches)), {"principal_line": _principal_line(answer)}


def _validate_stock_mango(_: dict[str, Any], payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    mismatches: list[str] = []
    answer = str(payload.get("answer") or "").lower()
    if "mangue" not in answer:
        mismatches.append("MISSING_EXPECTED_ROWS")
    if "arachide" in answer:
        mismatches.append("WRONG_FINAL_FOCUS")
    return sorted(set(mismatches)), {"principal_line": _principal_line(answer)}


def _validate_sql_refs(truth: dict[str, Any], payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    mismatches: list[str] = []
    answer = str(payload.get("answer") or "").lower()
    refs = [_norm(item) for item in (truth.get("refs") or [])]
    found = [item for item in refs if item in answer]
    if refs and len(found) < min(2, len(refs)):
        mismatches.append("MISSING_EXPECTED_ROWS")
    if _contains_generic_uncertainty(answer) and refs:
        mismatches.append("GENERIC_ANSWER_WITH_AVAILABLE_EVIDENCE")
    return sorted(set(mismatches)), {"refs_expected": refs, "refs_found": found}


def _validate_collections_today(truth: dict[str, Any], payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    mismatches: list[str] = []
    answer = str(payload.get("answer") or "").lower()
    qty = float(truth.get("qty", 0.0) or 0.0)
    has_number = f"{qty:.1f}" in answer or str(int(qty)) in answer
    if qty > 0 and not (has_number and "collect" in answer):
        mismatches.append("MISSING_EXPECTED_ROWS")
    return sorted(set(mismatches)), {"qty": qty}


def _validate_stage_comparison(truth: dict[str, Any], payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    mismatches: list[str] = []
    answer = str(payload.get("answer") or "").lower()
    if "séchage" not in answer and "sechage" not in answer:
        mismatches.append("MISSING_EXPECTED_ROWS")
    if "tri" not in answer and "sorting" not in answer:
        mismatches.append("MISSING_EXPECTED_ROWS")
    blocks = payload.get("response_blocks") or []
    chart_present = any(isinstance(item, dict) and _norm(item.get("type")) == "chart" for item in blocks)
    if not chart_present:
        mismatches.append("MISSING_RESPONSE_BLOCKS")
    return sorted(set(mismatches)), {"drying": truth.get("drying"), "sorting": truth.get("sorting")}


def _validate_member_ranking_kg(truth: dict[str, Any], payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    mismatches: list[str] = []
    answer = str(payload.get("answer") or "")
    rows = truth.get("rows", [])
    expected_names = [_norm(name) for name, _, _ in rows[:5]]
    found_names = [name for name in expected_names if name in answer.lower()]
    if rows and len(found_names) < min(2, len(rows)):
        mismatches.append("MISSING_EXPECTED_ROWS")
    if "lot " in answer.lower() or "étape critique" in answer.lower():
        mismatches.append("WRONG_FINAL_FOCUS")
    if _contains_generic_uncertainty(answer) and rows:
        mismatches.append("GENERIC_ANSWER_WITH_AVAILABLE_EVIDENCE")
    return sorted(set(mismatches)), {"expected_names": expected_names, "found_names": found_names}


def _validate_member_ranking_value(truth: dict[str, Any], payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    mismatches: list[str] = []
    answer = str(payload.get("answer") or "").lower()
    rows = truth.get("rows", [])
    if rows:
        if not any(_norm(name) in answer for name, _, _ in rows[:3]):
            mismatches.append("MISSING_EXPECTED_ROWS")
    else:
        if not any(token in answer for token in ("pas disponible", "aucune donnée", "aucune donnee", "ne contient pas")):
            mismatches.append("WRONG_EVIDENCE_ROLE")
        if "lot " in answer or "étape critique" in answer:
            mismatches.append("WRONG_FINAL_FOCUS")
    return sorted(set(mismatches)), {"rows_count": len(rows)}


def _validate_module_presence_or_unavailable(truth: dict[str, Any], payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    mismatches: list[str] = []
    answer = str(payload.get("answer") or "").lower()
    rows = truth.get("rows", [])
    module_exists = bool(truth.get("module_exists", False))

    if rows:
        row_markers = [_norm(row[0]) for row in rows[:5] if row]
        if row_markers and not any(marker in answer for marker in row_markers):
            mismatches.append("MISSING_EXPECTED_ROWS")
    else:
        if module_exists:
            if not any(token in answer for token in ("aucune", "pas disponible", "ne contient", "aucun")):
                mismatches.append("WRONG_EVIDENCE_ROLE")
        else:
            if not any(token in answer for token in ("module", "pas disponible", "modèle de données", "modele de donnees")):
                mismatches.append("WRONG_EVIDENCE_ROLE")

    if "lot " in answer or "étape critique" in answer:
        mismatches.append("WRONG_FINAL_FOCUS")
    return sorted(set(mismatches)), {"rows_count": len(rows), "module_exists": module_exists}


def _validate_finance_module(truth: dict[str, Any], payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    mismatches: list[str] = []
    answer = str(payload.get("answer") or "").lower()
    rows_count = int(truth.get("rows_count", 0))
    module_exists = bool(truth.get("module_exists", False))

    if rows_count > 0:
        if "fcfa" not in answer and "charge" not in answer and "dépense" not in answer and "depense" not in answer:
            mismatches.append("WRONG_EVIDENCE_ROLE")
    else:
        if module_exists:
            if not any(token in answer for token in ("aucune", "pas disponible", "ne contient", "aucun")):
                mismatches.append("WRONG_EVIDENCE_ROLE")
        else:
            if not any(token in answer for token in ("module", "pas disponible", "modèle de données", "modele de donnees")):
                mismatches.append("WRONG_EVIDENCE_ROLE")
    if "lot " in answer or "étape critique" in answer:
        mismatches.append("WRONG_FINAL_FOCUS")
    return sorted(set(mismatches)), {"rows_count": rows_count, "module_exists": module_exists}


def _build_cases() -> list[EvidenceRoleCase]:
    return [
        EvidenceRoleCase(
            case_id="sql-members-list",
            module="members",
            question="Lister les membres de notre coopérative.",
            expected_route="SQL_ONLY",
            accepted_routes=("SQL_ONLY",),
            expected_source_types={"sql"},
            expected_evidence_role="SQL_FACT_ROWS",
            truth_builder=_truth_members_list,
            validator=_validate_sql_refs,
            required_block_types=("summary", "table", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="sql-parcels-list",
            module="parcels",
            question="Liste les parcelles enregistrées.",
            expected_route="SQL_ONLY",
            accepted_routes=("SQL_ONLY",),
            expected_source_types={"sql"},
            expected_evidence_role="SQL_FACT_ROWS",
            truth_builder=_truth_parcels_list,
            validator=_validate_sql_refs,
            required_block_types=("summary", "table", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="sql-collections-today",
            module="collections",
            question="Quelle quantité a été collectée aujourd’hui ?",
            expected_route="SQL_ONLY",
            accepted_routes=("SQL_ONLY",),
            expected_source_types={"sql"},
            expected_evidence_role="SQL_FACT_ROWS",
            truth_builder=_truth_today_collections,
            validator=_validate_collections_today,
            required_block_types=("summary", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="sql-lots-in-progress",
            module="lots/batches",
            question="Quels lots sont en cours ?",
            expected_route="SQL_ONLY",
            accepted_routes=("SQL_ONLY",),
            expected_source_types={"sql"},
            expected_evidence_role="SQL_FACT_ROWS",
            truth_builder=_truth_in_progress_lots,
            validator=_validate_sql_list,
            required_block_types=("summary", "table", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="sql-low-efficiency",
            module="loss/efficiency",
            question="Quels lots ont une efficacité faible ?",
            expected_route="SQL_ONLY",
            accepted_routes=("SQL_ONLY", "HYBRID_SQL_RAG"),
            expected_source_types={"sql"},
            expected_evidence_role="SQL_FACT_ROWS",
            truth_builder=_truth_low_efficiency_lots,
            validator=_validate_low_efficiency_list,
            required_block_types=("summary", "table", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="rag-drying-best-practices",
            module="RAG knowledge",
            question="Comment réduire les pertes pendant le séchage de la mangue ?",
            expected_route="RAG_ONLY",
            accepted_routes=("RAG_ONLY", "HYBRID_SQL_RAG"),
            expected_source_types={"rag"},
            expected_evidence_role="RAG_EXPLANATION",
            truth_builder=_truth_rag_drying,
            validator=_validate_rag_only,
            required_block_types=("summary", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="rag-sorting-best-practices",
            module="RAG knowledge",
            question="Quelles sont les bonnes pratiques pour le tri des mangues ?",
            expected_route="RAG_ONLY",
            accepted_routes=("RAG_ONLY", "HYBRID_SQL_RAG"),
            expected_source_types={"rag"},
            expected_evidence_role="RAG_EXPLANATION",
            truth_builder=_truth_rag_sorting,
            validator=_validate_rag_only,
            required_block_types=("summary", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="hybrid-balance-mang004",
            module="material balance",
            question="Explique le bilan matière du lot MANG-004.",
            expected_route="HYBRID_SQL_RAG",
            accepted_routes=("HYBRID_SQL_RAG", "SQL_ONLY", "HYBRID_SQL_ML"),
            expected_source_types={"sql", "rag"},
            expected_evidence_role="HYBRID_SQL_RAG",
            truth_builder=_truth_hybrid_balance,
            validator=_validate_hybrid_sql_rag,
            required_block_types=("summary", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="hybrid-ml-risk",
            module="ML prediction logs",
            question="Quels sont les lots avec risque élevé ?",
            expected_route="HYBRID_SQL_ML",
            accepted_routes=("HYBRID_SQL_ML", "ML_ONLY"),
            expected_source_types={"ml"},
            expected_evidence_role="HYBRID_SQL_ML",
            truth_builder=_truth_ml_high_risk,
            validator=_validate_hybrid_sql_ml,
            required_block_types=("summary", "table", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="hybrid-recommendation",
            module="recommendations",
            question="Donne-moi les recommandations IA pour le lot MANG-004.",
            expected_route="HYBRID_FULL",
            accepted_routes=("HYBRID_FULL", "HYBRID_RAG_RECOMMENDATION", "RECOMMENDATION_ONLY"),
            expected_source_types={"recommendation"},
            expected_evidence_role="RECOMMENDATION_GROUNDED",
            truth_builder=_truth_recommendations,
            validator=_validate_recommendation_role,
            required_block_types=("summary", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="sql-stock-global",
            module="stocks",
            question="Quel est le stock ?",
            expected_route="SQL_ONLY",
            accepted_routes=("SQL_ONLY",),
            expected_source_types={"sql"},
            expected_evidence_role="SQL_FACT_ROWS",
            truth_builder=_truth_stocks,
            validator=_validate_stocks_sql_only,
            required_block_types=("summary", "table", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="sql-stock-mango",
            module="stocks",
            question="Quel est le stock de mangue ?",
            expected_route="SQL_ONLY",
            accepted_routes=("SQL_ONLY",),
            expected_source_types={"sql"},
            expected_evidence_role="SQL_FACT_ROWS",
            truth_builder=_truth_stock_mango,
            validator=_validate_stock_mango,
            required_block_types=("summary", "table", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="sql-stage-compare",
            module="loss/efficiency",
            question="Compare les pertes entre séchage et tri.",
            expected_route="SQL_ONLY",
            accepted_routes=("SQL_ONLY", "HYBRID_SQL_RAG"),
            expected_source_types={"sql"},
            expected_evidence_role="SQL_FACT_ROWS",
            truth_builder=_truth_stage_compare,
            validator=_validate_stage_comparison,
            required_block_types=("summary", "table", "chart", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="sql-member-top-kg",
            module="members ranking",
            question="Quel membre a livré le plus de kg ?",
            expected_route="SQL_ONLY",
            accepted_routes=("SQL_ONLY",),
            expected_source_types={"sql"},
            expected_evidence_role="SQL_MEMBER_RANKING",
            truth_builder=_truth_member_ranking_kg,
            validator=_validate_member_ranking_kg,
            required_block_types=("summary", "table", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="sql-member-ranking-kg",
            module="members ranking",
            question="Classe les membres par quantité collectée.",
            expected_route="SQL_ONLY",
            accepted_routes=("SQL_ONLY",),
            expected_source_types={"sql"},
            expected_evidence_role="SQL_MEMBER_RANKING",
            truth_builder=_truth_member_ranking_kg,
            validator=_validate_member_ranking_kg,
            required_block_types=("summary", "table", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="sql-member-top-value",
            module="members value ranking",
            question="Quel membre a généré le plus de valeur ?",
            expected_route="SQL_ONLY",
            accepted_routes=("SQL_ONLY",),
            expected_source_types={"sql"},
            expected_evidence_role="SQL_MEMBER_VALUE_OR_UNAVAILABLE",
            truth_builder=_truth_member_ranking_value,
            validator=_validate_member_ranking_value,
            required_block_types=("summary", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="sql-invoices-list",
            module="invoices",
            question="Liste les factures.",
            expected_route="SQL_ONLY",
            accepted_routes=("SQL_ONLY",),
            expected_source_types={"sql"},
            expected_evidence_role="SQL_INVOICES_OR_UNAVAILABLE",
            truth_builder=_truth_invoices,
            validator=_validate_module_presence_or_unavailable,
            required_block_types=("summary", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="sql-invoices-status",
            module="invoices",
            question="Quel est le statut des factures ?",
            expected_route="SQL_ONLY",
            accepted_routes=("SQL_ONLY",),
            expected_source_types={"sql"},
            expected_evidence_role="SQL_INVOICES_OR_UNAVAILABLE",
            truth_builder=_truth_invoices,
            validator=_validate_module_presence_or_unavailable,
            required_block_types=("summary", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="sql-commercial-orders",
            module="commercialisation",
            question="Quelles commandes commerciales sont en cours ?",
            expected_route="SQL_ONLY",
            accepted_routes=("SQL_ONLY",),
            expected_source_types={"sql"},
            expected_evidence_role="SQL_COMMERCIAL_OR_UNAVAILABLE",
            truth_builder=_truth_commercial_orders,
            validator=_validate_module_presence_or_unavailable,
            required_block_types=("summary", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="sql-commercial-total",
            module="commercialisation",
            question="Quel est le chiffre d’affaires ou total commercial ?",
            expected_route="SQL_ONLY",
            accepted_routes=("SQL_ONLY",),
            expected_source_types={"sql"},
            expected_evidence_role="SQL_COMMERCIAL_OR_UNAVAILABLE",
            truth_builder=_truth_commercial_orders,
            validator=_validate_module_presence_or_unavailable,
            required_block_types=("summary", "sources", "warnings"),
        ),
        EvidenceRoleCase(
            case_id="sql-finance",
            module="finance",
            question="Quelles charges ou dépenses avons-nous ?",
            expected_route="SQL_ONLY",
            accepted_routes=("SQL_ONLY",),
            expected_source_types={"sql"},
            expected_evidence_role="SQL_FINANCE_OR_UNAVAILABLE",
            truth_builder=_truth_finance,
            validator=_validate_finance_module,
            required_block_types=("summary", "sources", "warnings"),
        ),
    ]


def _evaluate_case(case: EvidenceRoleCase, truth: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    route = str(payload.get("route") or "")
    answer = str(payload.get("answer") or "")
    sources = _source_types(payload)

    mismatches: list[str] = []

    if route != case.expected_route and route not in case.accepted_routes:
        mismatches.append("WRONG_EVIDENCE_ROLE")

    if not case.expected_source_types.issubset(sources):
        mismatches.append("WRONG_EVIDENCE_ROLE")

    strict_mismatches, details = case.validator(truth, payload)
    mismatches.extend(strict_mismatches)

    if case.required_block_types:
        actual_blocks = _response_block_types(payload)
        expected_blocks = {_norm(item) for item in case.required_block_types}
        if not expected_blocks.issubset(actual_blocks):
            mismatches.append("MISSING_RESPONSE_BLOCKS")
            details["expected_block_types"] = sorted(expected_blocks)
            details["actual_block_types"] = sorted(actual_blocks)

    # Keep only strict labels requested for content validation.
    mismatches = sorted({m for m in mismatches if m in STRICT_LABELS})

    if not mismatches:
        verdict = "PASS"
    elif len(mismatches) == 1:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    return {
        "case_id": case.case_id,
        "module": case.module,
        "chatbot_question": case.question,
        "direct_truth_summary": truth.get("truth_summary", ""),
        "chatbot_answer_summary": " ".join(answer.split())[:320],
        "expected_route": case.expected_route,
        "actual_route": route,
        "expected_source_types": sorted(case.expected_source_types),
        "actual_source_types": sorted(sources),
        "expected_evidence_role": case.expected_evidence_role,
        "content_validation": details,
        "mismatch_labels": mismatches,
        "verdict": verdict,
        "suspected_root_cause": _root_cause(mismatches),
    }


def _root_cause(mismatches: list[str]) -> str:
    if not mismatches:
        return "Aucune anomalie détectée."
    if "MISSING_EXPECTED_ROWS" in mismatches:
        return "La réponse finale ne restitue pas toutes les lignes attendues de la vérité SQL."
    if "RAG_CONTENT_MISSING" in mismatches:
        return "Le contenu RAG attendu (bonnes pratiques/concepts) n’est pas réellement présent dans la réponse."
    if "WRONG_FINAL_FOCUS" in mismatches:
        return "Le focus final de la réponse est orienté sur un mauvais type de preuve."
    if "HYBRID_COMBINATION_WEAK" in mismatches:
        return "Le mode hybride n’équilibre pas correctement SQL et RAG dans la réponse finale."
    if "WRONG_EVIDENCE_ROLE" in mismatches:
        return "Le rôle attendu de la preuve (SQL/RAG/ML/recommandation) n’est pas respecté."
    if "GENERIC_ANSWER_WITH_AVAILABLE_EVIDENCE" in mismatches:
        return "Réponse générique alors que des preuves directes existent en base/RAG."
    if "MISSING_RESPONSE_BLOCKS" in mismatches:
        return "Les blocs structurés attendus pour le rendu UI sont absents."
    return "Incohérence de rôle de preuve détectée."


def _build_markdown(summary: dict[str, int], cases: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append("# Chatbot Evidence-Role Truth Audit")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append(
        f"- Total cases: {summary['TOTAL']} | PASS={summary['PASS']} | PARTIAL={summary['PARTIAL']} | FAIL={summary['FAIL']}"
    )
    lines.append("- Cet audit valide strictement le rôle de preuve dans le contenu final (pas seulement route/source).")
    lines.append("")
    lines.append("## Results")
    lines.append("| Module | Direct truth summary | Question | Answer summary | Expected route/source | Actual route/source | Expected evidence role | Match verdict | Exact mismatch | Suspected root cause |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for item in cases:
        mism = ", ".join(item["mismatch_labels"]) if item["mismatch_labels"] else "-"
        exp_src = ",".join(item["expected_source_types"]) or "-"
        act_src = ",".join(item["actual_source_types"]) or "-"
        lines.append(
            "| {module} | {truth} | {q} | {a} | {er}/{es} | {ar}/{asrc} | {role} | {v} | {m} | {cause} |".format(
                module=item["module"],
                truth=item["direct_truth_summary"].replace("|", "/"),
                q=item["chatbot_question"].replace("|", "/"),
                a=item["chatbot_answer_summary"].replace("|", "/"),
                er=item["expected_route"],
                es=exp_src,
                ar=item["actual_route"],
                asrc=act_src,
                role=item["expected_evidence_role"],
                v=item["verdict"],
                m=mism,
                cause=item["suspected_root_cause"],
            )
        )

    counter = Counter()
    for item in cases:
        for label in item["mismatch_labels"]:
            counter[label] += 1

    lines.append("")
    lines.append("## Worst mismatches")
    if counter:
        for label, count in counter.most_common(10):
            lines.append(f"- {label}: {count}")
    else:
        lines.append("- None")

    return "\n".join(lines)


def test_chatbot_evidence_role_truth_audit(db_session, monkeypatch):
    _seed_audit_data(db_session)
    _setup_isolated_overrides(db_session)
    monkeypatch.setattr(AuditLogger, "log", lambda self, **kwargs: None)
    user = _first_user(db_session)

    cases = _build_cases()
    results: list[dict[str, Any]] = []

    with TestClient(app) as client:
        for case in cases:
            truth = case.truth_builder(db_session, user)
            payload = _post_agent(client, case.question)
            results.append(_evaluate_case(case, truth, payload))

    counts = Counter(item["verdict"] for item in results)
    summary = {
        "PASS": int(counts.get("PASS", 0)),
        "PARTIAL": int(counts.get("PARTIAL", 0)),
        "FAIL": int(counts.get("FAIL", 0)),
        "TOTAL": len(results),
    }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audit_name": "chatbot_evidence_role_truth_audit",
        "summary": summary,
        "cases": results,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    MD_REPORT_PATH.write_text(_build_markdown(summary, results), encoding="utf-8")

    app.dependency_overrides.clear()

    assert JSON_REPORT_PATH.exists()
    assert MD_REPORT_PATH.exists()
    assert summary["TOTAL"] >= 21

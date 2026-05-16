from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.models.batch import Batch
from app.models.enums import BatchStatus, PreHarvestStepStatus, RiskLevel
from app.models.input import Input
from app.models.member import Member
from app.models.ml import MLPredictionLog
from app.models.parcel import Parcel
from app.models.pre_harvest_step import PreHarvestStep
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.rag import RAGChunk, RAGDocument
from app.models.recommendation import Recommendation
from app.models.stock import Stock
from app.models.user import User

from tests.ai.test_chatbot_system_audit import _seed_audit_data, _setup_overrides

REPORT_DIR = Path(__file__).resolve().parents[2] / "app" / "ai" / "reports"
JSON_REPORT_PATH = REPORT_DIR / "chatbot_db_truth_audit.json"
MD_REPORT_PATH = REPORT_DIR / "chatbot_db_truth_audit.md"

from app.core.config import Settings
from app.ai.utils.audit_environment import EnvironmentParityAudit

settings = Settings()
# Log environment parity for audit
EnvironmentParityAudit.log_parity_header("DB Truth Audit", f"Mode={settings.audit_mode}")

@dataclass(frozen=True)
class DBTruthCase:
    case_id: str
    module: str
    question: str
    expected_route: str
    accepted_routes: tuple[str, ...]
    expected_source_types: set[str]
    expected_sql_tables: set[str]
    operational_sql_required: bool
    truth_builder: Callable[[Any, Any], dict[str, Any]]
    semantic_checker: Callable[[dict[str, Any], dict[str, Any]], list[str]]


def _post_agent(client: TestClient, question: str) -> dict[str, Any]:
    resp = client.post("/chat/agent", json={"message": question, "language": "fr"})
    assert resp.status_code == 200
    return resp.json()


def _first_user(db_session):
    user = db_session.query(User).first()
    if user is None or user.cooperative_id is None:
        raise RuntimeError("No seeded user/cooperative available")
    return user


def _norm(text: Any) -> str:
    return str(text or "").strip().lower()


def _contains_product(answer: str, product_key: str) -> bool:
    aliases = {
        "mango": {"mango", "mangue"},
        "peanut": {"peanut", "arachide"},
        "millet": {"millet", "mil"},
    }
    toks = aliases.get(_norm(product_key), {_norm(product_key)})
    low = answer.lower()
    return any(tok in low for tok in toks if tok)


def _has_number(answer: str, value: float, tolerance: float = 0.11) -> bool:
    nums = [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[\.,]\d+)?", answer)]
    return any(abs(n - value) <= tolerance for n in nums)


def _extract_source_types(payload: dict[str, Any]) -> set[str]:
    return {
        _norm(src.get("type"))
        for src in (payload.get("sources") or [])
        if isinstance(src, dict) and src.get("type")
    }


def _extract_sql_tables(payload: dict[str, Any]) -> set[str]:
    tables: set[str] = set()
    for src in payload.get("sources", []) or []:
        if not isinstance(src, dict):
            continue
        if _norm(src.get("type")) != "sql":
            continue
        raw = _norm(src.get("table"))
        if not raw:
            continue
        for part in raw.split(","):
            clean = part.strip()
            if clean:
                tables.add(clean)
    return tables


def _summary_members(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(Member.full_name, Member.code)
        .where(Member.cooperative_id == user.cooperative_id)
        .order_by(Member.full_name.asc())
    ).all()
    return {
        "count": len(rows),
        "names": [str(r[0]) for r in rows],
        "codes": [str(r[1]) for r in rows],
        "truth_summary": f"members={len(rows)} | names={', '.join(str(r[0]) for r in rows[:5])}",
    }


def _summary_parcels(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(Parcel.name, Parcel.main_culture, Parcel.surface_ha)
        .where(Parcel.cooperative_id == user.cooperative_id)
        .order_by(Parcel.name.asc())
    ).all()
    return {
        "count": len(rows),
        "names": [str(r[0]) for r in rows],
        "truth_summary": f"parcels={len(rows)} | names={', '.join(str(r[0]) for r in rows[:5])}",
    }


def _summary_preharvest_pending(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(PreHarvestStep.label)
        .where(
            PreHarvestStep.cooperative_id == user.cooperative_id,
            PreHarvestStep.status == PreHarvestStepStatus.PENDING,
        )
    ).all()
    labels = [str(r[0]) for r in rows]
    return {
        "pending_count": len(labels),
        "labels": labels,
        "truth_summary": f"preharvest_pending={len(labels)} | labels={', '.join(labels[:5])}",
    }


def _summary_collections_today(db_session, user: User) -> dict[str, Any]:
    today = datetime.now().date()
    total = db_session.scalar(
        select(func.coalesce(func.sum(Input.quantity), 0.0)).where(
            Input.cooperative_id == user.cooperative_id,
            Input.date == today,
        )
    )
    return {
        "today_total_kg": float(total or 0.0),
        "truth_summary": f"inputs_today_total_kg={float(total or 0.0):.1f}",
    }


def _summary_stocks(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(Product.name, Stock.total_stock_kg, Stock.reserved_in_lots_kg, Stock.unit)
        .join(Product, Product.id == Stock.product_id)
        .where(Stock.cooperative_id == user.cooperative_id)
        .order_by(Product.name.asc())
    ).all()
    items = []
    for name, total, reserved, unit in rows:
        available = float(total or 0.0) - float(reserved or 0.0)
        items.append({"product": str(name), "available": available, "unit": str(unit or "kg")})
    return {
        "count": len(items),
        "items": items,
        "truth_summary": "stocks=" + ", ".join(f"{x['product']}={x['available']:.1f} {x['unit']}" for x in items),
    }


def _summary_in_progress_lots(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(Batch.code)
        .where(Batch.cooperative_id == user.cooperative_id, Batch.status == BatchStatus.IN_PROGRESS)
        .order_by(Batch.code.asc())
    ).all()
    refs = [str(r[0]) for r in rows]
    return {
        "count": len(refs),
        "refs": refs,
        "truth_summary": f"in_progress_lots={len(refs)} | refs={', '.join(refs[:6])}",
    }


def _summary_top_loss_lot(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(Batch.code, Batch.initial_qty, Batch.current_qty)
        .where(Batch.cooperative_id == user.cooperative_id)
    ).all()
    scored = []
    for code, initial, current in rows:
        ini = float(initial or 0.0)
        cur = float(current or 0.0)
        loss = ((ini - cur) / ini * 100.0) if ini > 0 else 0.0
        scored.append((str(code), loss))
    scored.sort(key=lambda x: x[1], reverse=True)
    top_code, top_loss = scored[0] if scored else ("", 0.0)
    return {
        "top_code": top_code,
        "top_loss_pct": float(top_loss),
        "truth_summary": f"top_loss_lot={top_code} ({top_loss:.1f}%)",
    }


def _summary_stage_compare(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(ProcessStep.type, ProcessStep.qty_in, ProcessStep.qty_out)
        .join(Batch, Batch.id == ProcessStep.batch_id)
        .where(Batch.cooperative_id == user.cooperative_id, ProcessStep.type.in_(["drying", "sorting"]))
    ).all()
    agg: dict[str, list[float]] = {"drying": [], "sorting": []}
    for stage, qty_in, qty_out in rows:
        q_in = float(qty_in or 0.0)
        q_out = float(qty_out or 0.0)
        loss = ((q_in - q_out) / q_in * 100.0) if q_in > 0 else 0.0
        agg[str(stage)].append(loss)
    drying_avg = sum(agg["drying"]) / len(agg["drying"]) if agg["drying"] else 0.0
    sorting_avg = sum(agg["sorting"]) / len(agg["sorting"]) if agg["sorting"] else 0.0
    return {
        "drying_avg": drying_avg,
        "sorting_avg": sorting_avg,
        "truth_summary": f"avg_loss_drying={drying_avg:.1f}% | avg_loss_sorting={sorting_avg:.1f}%",
    }


def _summary_material_balance_mang004(db_session, user: User) -> dict[str, Any]:
    row = db_session.execute(
        select(Batch.code, Batch.initial_qty, Batch.current_qty)
        .where(Batch.cooperative_id == user.cooperative_id, Batch.code == "MANG-004")
    ).first()
    if row is None:
        return {"exists": False, "truth_summary": "MANG-004 absent"}
    code, initial, current = row
    ini = float(initial or 0.0)
    cur = float(current or 0.0)
    loss = ((ini - cur) / ini * 100.0) if ini > 0 else 0.0
    eff = (cur / ini * 100.0) if ini > 0 else 0.0
    return {
        "exists": True,
        "code": str(code),
        "loss_pct": loss,
        "eff_pct": eff,
        "truth_summary": f"{code}: loss={loss:.1f}% eff={eff:.1f}%",
    }


def _summary_low_efficiency_lots(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(Batch.code, Batch.initial_qty, Batch.current_qty).where(Batch.cooperative_id == user.cooperative_id)
    ).all()
    low = []
    for code, initial, current in rows:
        ini = float(initial or 0.0)
        cur = float(current or 0.0)
        eff = (cur / ini * 100.0) if ini > 0 else 0.0
        if eff < 85.0:
            low.append((str(code), eff))
    low.sort(key=lambda x: x[1])
    return {
        "count": len(low),
        "refs": [x[0] for x in low],
        "truth_summary": f"low_efficiency_lots={len(low)} | refs={', '.join(x[0] for x in low[:6])}",
    }


def _summary_ml_logs(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(Batch.code, MLPredictionLog.risk_level, MLPredictionLog.predicted_loss_pct)
        .join(Batch, Batch.id == MLPredictionLog.batch_id)
        .where(Batch.cooperative_id == user.cooperative_id)
    ).all()
    high = [str(code) for code, level, _ in rows if level == RiskLevel.HIGH]
    return {
        "count": len(rows),
        "high_risk_refs": high,
        "truth_summary": f"ml_prediction_logs={len(rows)} | high_risk={', '.join(high) if high else 'none'}",
    }


def _summary_recommendations(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(Batch.code, Recommendation.risk_level, Recommendation.suggested_action)
        .join(Batch, Batch.id == Recommendation.batch_id)
        .where(Batch.cooperative_id == user.cooperative_id)
    ).all()
    return {
        "count": len(rows),
        "refs": [str(r[0]) for r in rows],
        "truth_summary": f"recommendations_rows={len(rows)} | refs={', '.join(str(r[0]) for r in rows[:6])}",
    }


def _summary_rag_chunks(db_session, user: User) -> dict[str, Any]:
    rows = db_session.execute(
        select(RAGDocument.title, RAGChunk.content)
        .join(RAGChunk, RAGChunk.document_id == RAGDocument.id)
        .where(RAGDocument.cooperative_id == user.cooperative_id)
    ).all()
    titles = [str(r[0]) for r in rows]
    return {
        "count": len(rows),
        "titles": titles,
        "truth_summary": f"rag_chunks={len(rows)} | titles={', '.join(titles[:4])}",
    }


def _mismatch_operational_generic(answer: str, truth_has_data: bool) -> list[str]:
    mismatches: list[str] = []
    if truth_has_data and "ne permettent pas de confirmer" in answer.lower():
        mismatches.append("MISLEADING_GENERIC_ANSWER_WITH_DATA")
    return mismatches


def _check_members(truth: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    answer = str(payload.get("answer") or "")
    mismatches = _mismatch_operational_generic(answer, truth.get("count", 0) > 0)
    for name in truth.get("names", [])[:3]:
        if _norm(name) not in answer.lower():
            mismatches.append(f"MISSING_MEMBER_NAME:{name}")
    m = re.search(r"\((\d+)\)", answer)
    if m and int(m.group(1)) != int(truth.get("count", 0)):
        mismatches.append(f"WRONG_COUNT:expected={truth.get('count')} actual={m.group(1)}")
    return mismatches


def _check_parcels(truth: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    answer = str(payload.get("answer") or "")
    mismatches = _mismatch_operational_generic(answer, truth.get("count", 0) > 0)
    if not any(_norm(name) in answer.lower() for name in truth.get("names", [])[:3]):
        mismatches.append("MISSING_PARCEL_IDENTIFIERS")
    return mismatches


def _check_preharvest_pending(truth: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    answer = str(payload.get("answer") or "")
    mismatches = _mismatch_operational_generic(answer, truth.get("pending_count", 0) > 0)
    if truth.get("pending_count", 0) > 0 and not _has_number(answer, float(truth["pending_count"]), 0.01):
        mismatches.append(f"WRONG_PENDING_COUNT:expected={truth['pending_count']}")
    return mismatches


def _check_collections_today(truth: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    answer = str(payload.get("answer") or "")
    mismatches = _mismatch_operational_generic(answer, truth.get("today_total_kg", 0) > 0)
    if truth.get("today_total_kg", 0) > 0 and not _has_number(answer, float(truth["today_total_kg"])):
        mismatches.append(f"WRONG_TODAY_COLLECTION_QTY:expected={truth['today_total_kg']:.1f}")
    return mismatches


def _check_stocks_global(truth: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    answer = str(payload.get("answer") or "")
    mismatches = _mismatch_operational_generic(answer, truth.get("count", 0) > 0)
    for item in truth.get("items", []):
        if not _contains_product(answer, item.get("product")):
            mismatches.append(f"MISSING_PRODUCT:{item.get('product')}")
    if truth.get("count", 0) > 1:
        mentions = sum(1 for item in truth.get("items", []) if _contains_product(answer, item.get("product")))
        if mentions < 2:
            mismatches.append("MISSING_ROWS:stock_list_not_complete")
    return mismatches


def _check_stock_mango(truth: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    answer = str(payload.get("answer") or "")
    mismatches: list[str] = []
    if not _contains_product(answer, "mango"):
        mismatches.append("WRONG_PRODUCT_NAME:missing_mango")
    if _contains_product(answer, "peanut"):
        mismatches.append("WRONG_PRODUCT_INCLUDED:peanut")
    mango = next((item for item in truth.get("items", []) if _norm(item.get("product")) == "mango"), None)
    if mango and not _has_number(answer, float(mango.get("available", 0.0))):
        mismatches.append(f"WRONG_QUANTITY:expected={float(mango.get('available', 0.0)):.1f}")
    return mismatches


def _check_lots_in_progress(truth: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    answer = str(payload.get("answer") or "").lower()
    mismatches = _mismatch_operational_generic(answer, truth.get("count", 0) > 0)
    if truth.get("count", 0) > 0 and not any(_norm(ref) in answer for ref in truth.get("refs", [])):
        mismatches.append("MISSING_LOT_ROWS")
    return mismatches


def _check_top_loss_lot(truth: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    answer = str(payload.get("answer") or "")
    mismatches = _mismatch_operational_generic(answer, bool(truth.get("top_code")))
    if truth.get("top_code") and _norm(truth["top_code"]) not in answer.lower():
        mismatches.append(f"WRONG_TOP_LOT:expected={truth['top_code']}")
    if truth.get("top_loss_pct") and not _has_number(answer, float(truth["top_loss_pct"])):
        mismatches.append(f"WRONG_PERCENTAGE:expected={truth['top_loss_pct']:.1f}")
    return mismatches


def _check_stage_compare(truth: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    answer = str(payload.get("answer") or "").lower()
    mismatches = _mismatch_operational_generic(answer, True)
    has_drying = "séchage" in answer or "drying" in answer
    has_sorting = "tri" in answer or "sorting" in answer
    if not (has_drying and has_sorting):
        mismatches.append("MISSING_STAGE_COMPARISON")
    return mismatches


def _check_material_balance(truth: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    answer = str(payload.get("answer") or "")
    mismatches = _mismatch_operational_generic(answer, truth.get("exists", False))
    if truth.get("exists") and "mang-004" not in answer.lower():
        mismatches.append("WRONG_LOT_NAME")
    if truth.get("exists") and not _has_number(answer, float(truth.get("loss_pct", 0.0))):
        mismatches.append(f"WRONG_LOSS_PERCENT:expected={float(truth.get('loss_pct', 0.0)):.1f}")
    if truth.get("exists") and not _has_number(answer, float(truth.get("eff_pct", 0.0))):
        mismatches.append(f"WRONG_EFFICIENCY_PERCENT:expected={float(truth.get('eff_pct', 0.0)):.1f}")
    return mismatches


def _check_low_efficiency(truth: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    answer = str(payload.get("answer") or "").lower()
    mismatches = _mismatch_operational_generic(answer, truth.get("count", 0) > 0)
    if truth.get("count", 0) > 0 and not any(_norm(ref) in answer for ref in truth.get("refs", [])[:3]):
        mismatches.append("MISSING_LOW_EFFICIENCY_LOTS")
    return mismatches


def _check_ml_risk(truth: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    answer = str(payload.get("answer") or "").lower()
    mismatches: list[str] = []
    if truth.get("high_risk_refs"):
        if not any(_norm(ref) in answer for ref in truth["high_risk_refs"]):
            mismatches.append("ML_HIGH_RISK_LOT_NOT_MENTIONED")
    warning_codes = [str(w) for w in ((payload.get("metadata") or {}).get("warning_codes") or [])]
    if "SQL_ML_CONTRADICTION" in warning_codes and "contradiction sql/ml" not in answer:
        mismatches.append("ML_SQL_CONTRADICTION_NOT_EXPLAINED")
    return mismatches


def _check_recommendations(truth: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    answer = str(payload.get("answer") or "").lower()
    mismatches: list[str] = []
    metadata = payload.get("metadata") or {}
    debug = metadata.get("agent_debug") or {}
    reco_data = ((debug.get("RecommendationAgent") or {}).get("data") or {}) if isinstance(debug, dict) else {}
    recs = reco_data.get("recommendations") if isinstance(reco_data, dict) else []
    if truth.get("count", 0) == 0 and not recs:
        if "insuffis" not in answer and "aucune recommandation prioritaire" not in answer:
            mismatches.append("MISLEADING_RECOMMENDATION_WITHOUT_DB_EVIDENCE")
    if truth.get("count", 0) > 0 and not recs:
        mismatches.append("RECOMMENDATION_ROWS_NOT_USED")
    return mismatches


def _check_rag_knowledge(truth: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    answer = str(payload.get("answer") or "").lower()
    mismatches: list[str] = []
    if truth.get("count", 0) > 0 and not any(k in answer for k in ("séchage", "humidité", "tri", "emballage")):
        mismatches.append("RAG_KNOWLEDGE_NOT_REFLECTED")
    return mismatches


def _build_cases() -> list[DBTruthCase]:
    return [
        DBTruthCase("members-01", "members/farmers", "Lister les membres de notre coopérative.", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, {"members"}, True, _summary_members, _check_members),
        DBTruthCase("parcels-01", "parcels/cultures", "Liste les parcelles enregistrées.", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, {"parcels", "pre_harvest_steps"}, True, _summary_parcels, _check_parcels),
        DBTruthCase("preharvest-01", "pre-harvest steps", "Quelles étapes pré-récolte sont en attente ?", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, {"pre_harvest_steps", "parcels"}, True, _summary_preharvest_pending, _check_preharvest_pending),
        DBTruthCase("collections-01", "collections/inputs", "Quelle quantité a été collectée aujourd’hui ?", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, {"inputs"}, True, _summary_collections_today, _check_collections_today),
        DBTruthCase("stocks-01", "stocks", "Quel est le stock ?", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, {"stocks"}, True, _summary_stocks, _check_stocks_global),
        DBTruthCase("stocks-02", "stocks", "Quel est le stock de mangue ?", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, {"stocks"}, True, _summary_stocks, _check_stock_mango),
        DBTruthCase("lots-01", "lots/batches", "Quels lots sont en cours ?", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, {"batches"}, True, _summary_in_progress_lots, _check_lots_in_progress),
        DBTruthCase("loss-01", "loss analysis", "Quel lot a le plus de pertes ?", "SQL_ONLY", ("SQL_ONLY",), {"sql"}, {"batches", "process_steps"}, True, _summary_top_loss_lot, _check_top_loss_lot),
        DBTruthCase("process-01", "post-harvest process steps", "Compare les pertes entre séchage et tri.", "SQL_ONLY", ("SQL_ONLY", "HYBRID_SQL_RAG"), {"sql"}, {"process_steps"}, True, _summary_stage_compare, _check_stage_compare),
        DBTruthCase("balance-01", "material balance", "Explique le bilan matière du lot MANG-004.", "HYBRID_SQL_RAG", ("HYBRID_SQL_RAG", "SQL_ONLY", "HYBRID_SQL_ML"), {"sql"}, {"batches", "process_steps"}, True, _summary_material_balance_mang004, _check_material_balance),
        DBTruthCase("eff-01", "loss/efficiency calculations", "Quels lots ont une efficacité faible ?", "SQL_ONLY", ("SQL_ONLY", "HYBRID_SQL_RAG"), {"sql"}, {"batches"}, True, _summary_low_efficiency_lots, _check_low_efficiency),
        DBTruthCase("ml-01", "ML prediction logs", "Quels sont les lots avec risque élevé ?", "HYBRID_SQL_ML", ("HYBRID_SQL_ML", "ML_ONLY"), {"ml"}, {"ml_prediction_logs", "batches"}, False, _summary_ml_logs, _check_ml_risk),
        DBTruthCase("reco-01", "recommendations", "Donne-moi les recommandations IA pour le lot MANG-004.", "HYBRID_FULL", ("HYBRID_FULL", "HYBRID_RAG_RECOMMENDATION", "RECOMMENDATION_ONLY"), {"recommendation"}, {"recommendations", "batches"}, False, _summary_recommendations, _check_recommendations),
        DBTruthCase("rag-01", "RAG knowledge chunks", "Comment réduire les pertes pendant le séchage de la mangue ?", "RAG_ONLY", ("RAG_ONLY", "HYBRID_SQL_RAG"), {"rag"}, set(), False, _summary_rag_chunks, _check_rag_knowledge),
    ]


def _evaluate_case(case: DBTruthCase, truth: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    route = str(payload.get("route") or "")
    answer = str(payload.get("answer") or "")
    source_types = _extract_source_types(payload)
    sql_tables = _extract_sql_tables(payload)
    warning_codes = [str(w) for w in ((payload.get("metadata") or {}).get("warning_codes") or [])]

    mismatches: list[str] = []

    if route != case.expected_route and route not in case.accepted_routes:
        mismatches.append(f"WRONG_ROUTE:selected={route} expected={case.expected_route}")

    missing_types = sorted(case.expected_source_types - source_types)
    if missing_types:
        mismatches.append("SOURCE_TYPE_MISSING:" + ",".join(missing_types))

    if case.operational_sql_required and "sql" not in source_types:
        mismatches.append("SQL_MISSING_FOR_OPERATIONAL_FACT")

    if case.operational_sql_required and "rag" in source_types and "sql" in source_types is False:
        mismatches.append("RAG_USED_WHEN_SQL_REQUIRED")

    if case.expected_sql_tables:
        if sql_tables and not (sql_tables & case.expected_sql_tables):
            mismatches.append(f"WRONG_TABLE_USED:actual={sorted(sql_tables)} expected~={sorted(case.expected_sql_tables)}")
        if case.operational_sql_required and not sql_tables:
            mismatches.append("SQL_TABLE_METADATA_MISSING")

    mismatches.extend(case.semantic_checker(truth, payload))

    if case.operational_sql_required and truth and any(
        key in truth for key in ("count", "pending_count", "today_total_kg", "items", "refs", "top_code")
    ):
        # Empty truth requires warning signal in final payload.
        has_data = True
        if "count" in truth:
            has_data = bool(truth.get("count"))
        elif "pending_count" in truth:
            has_data = bool(truth.get("pending_count"))
        elif "today_total_kg" in truth:
            has_data = float(truth.get("today_total_kg") or 0.0) > 0
        elif "items" in truth:
            has_data = bool(truth.get("items"))
        elif "refs" in truth:
            has_data = bool(truth.get("refs"))
        elif "top_code" in truth:
            has_data = bool(truth.get("top_code"))
        if not has_data and not warning_codes:
            mismatches.append("WARNING_MISSING_FOR_EMPTY_DATA")

    mismatches = sorted(set(mismatches))

    if not mismatches:
        verdict = "PASS"
    elif len(mismatches) <= 2:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"

    return {
        "case_id": case.case_id,
        "module": case.module,
        "table_module_tested": case.module,
        "direct_sql_truth_summary": truth.get("truth_summary", ""),
        "chatbot_question": case.question,
        "chatbot_answer_summary": " ".join(answer.split())[:320],
        "expected_route": case.expected_route,
        "actual_route": route,
        "expected_source_types": sorted(case.expected_source_types),
        "actual_source_types": sorted(source_types),
        "expected_sql_tables": sorted(case.expected_sql_tables),
        "actual_sql_tables": sorted(sql_tables),
        "warnings": warning_codes,
        "match_verdict": verdict,
        "exact_mismatch": mismatches,
        "suspected_root_cause": _root_cause(mismatches),
        "priority_fix_recommendation": _priority_fix(mismatches),
    }


def _root_cause(mismatches: list[str]) -> str:
    if not mismatches:
        return "Aucune anomalie détectée."
    joined = " | ".join(mismatches)
    if "WRONG_ROUTE" in joined:
        return "Sélection de mode/route incorrecte dans IntentRouter pour ce type de question."
    if "WRONG_TABLE_USED" in joined:
        return "SQLAnalyticsAgent associe la question à une table SQL non pertinente."
    if "SQL_MISSING_FOR_OPERATIONAL_FACT" in joined:
        return "Les faits opérationnels sont produits sans preuve SQL explicite."
    if "MISLEADING_GENERIC_ANSWER_WITH_DATA" in joined:
        return "Le rendu final tombe sur une formulation générique malgré des données SQL disponibles."
    if "SOURCE_TYPE_MISSING" in joined:
        return "Contrat de sources incomplet pour le mode attendu."
    if "MISSING_" in joined or "WRONG_" in joined:
        return "Alignement incomplet entre vérité base de données et réponse finale."
    return "Incohérence détectée entre données et réponse." 


def _priority_fix(mismatches: list[str]) -> str:
    if not mismatches:
        return "Aucun correctif prioritaire requis."
    joined = " | ".join(mismatches)
    if "WRONG_TABLE_USED" in joined:
        return "Priorité haute: ajuster le mapping question->table SQL dans SQLAnalyticsAgent."
    if "WRONG_ROUTE" in joined:
        return "Priorité haute: fiabiliser les règles de routage pour le module concerné."
    if "SQL_MISSING_FOR_OPERATIONAL_FACT" in joined:
        return "Priorité haute: imposer la présence de sources SQL pour les faits opérationnels."
    if "MISLEADING_GENERIC_ANSWER_WITH_DATA" in joined:
        return "Priorité moyenne: renforcer le rendu pour injecter les lignes SQL disponibles."
    return "Priorité moyenne: corriger la cohérence contenu/sources sur ce cas."


def _build_markdown(results: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Chatbot DB Truth Audit")
    lines.append("")
    lines.append("## Résumé")
    lines.append(
        f"- Total cas: {summary['TOTAL']} | PASS={summary['PASS']} | PARTIAL={summary['PARTIAL']} | FAIL={summary['FAIL']}"
    )
    lines.append("- Cet audit compare les réponses /chat/agent à la vérité SQL directe table par table.")
    lines.append("")
    lines.append("## Résultats détaillés")
    lines.append("| Module/Table testé | Vérité SQL directe | Question | Réponse chatbot (résumé) | Route attendue | Route réelle | Sources attendues/réelles | Verdict | Mismatch exact | Cause suspectée | Recommandation prioritaire |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for item in results:
        expected_sources = ",".join(item["expected_source_types"]) or "-"
        actual_sources = ",".join(item["actual_source_types"]) or "-"
        mism = "; ".join(item["exact_mismatch"]) if item["exact_mismatch"] else "-"
        lines.append(
            "| {module} | {truth} | {q} | {a} | {er} | {ar} | {es}/{asrc} | {v} | {m} | {c} | {p} |".format(
                module=item["table_module_tested"],
                truth=item["direct_sql_truth_summary"].replace("|", "/"),
                q=item["chatbot_question"].replace("|", "/"),
                a=item["chatbot_answer_summary"].replace("|", "/"),
                er=item["expected_route"],
                ar=item["actual_route"],
                es=expected_sources,
                asrc=actual_sources,
                v=item["match_verdict"],
                m=mism.replace("|", "/"),
                c=item["suspected_root_cause"].replace("|", "/"),
                p=item["priority_fix_recommendation"].replace("|", "/"),
            )
        )

    mismatch_counter = Counter()
    for item in results:
        for mismatch in item["exact_mismatch"]:
            mismatch_counter[mismatch.split(":", 1)[0]] += 1

    lines.append("")
    lines.append("## Pires mismatches")
    if mismatch_counter:
        for key, count in mismatch_counter.most_common(10):
            lines.append(f"- {key}: {count}")
    else:
        lines.append("- Aucun mismatch détecté.")

    lines.append("")
    lines.append("## Causes racines suspectées")
    root_counter = Counter(item["suspected_root_cause"] for item in results if item["exact_mismatch"])
    if root_counter:
        for cause, count in root_counter.most_common(10):
            lines.append(f"- {cause} (cas={count})")
    else:
        lines.append("- Aucune cause racine ouverte.")

    return "\n".join(lines)


def test_chatbot_db_truth_audit(db_session):
    _seed_audit_data(db_session)
    _setup_overrides(db_session)

    user = _first_user(db_session)
    cases = _build_cases()

    results: list[dict[str, Any]] = []
    with TestClient(app) as client:
        for case in cases:
            truth = case.truth_builder(db_session, user)
            payload = _post_agent(client, case.question)
            results.append(_evaluate_case(case, truth, payload))

    counts = Counter(item["match_verdict"] for item in results)
    summary = {
        "PASS": int(counts.get("PASS", 0)),
        "PARTIAL": int(counts.get("PARTIAL", 0)),
        "FAIL": int(counts.get("FAIL", 0)),
        "TOTAL": len(results),
    }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audit_name": "chatbot_db_truth_audit",
        "debug_flag": "AI_AUDIT_DEBUG=1",
        "summary": summary,
        "results": results,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    MD_REPORT_PATH.write_text(_build_markdown(results, summary), encoding="utf-8")

    app.dependency_overrides.clear()

    assert JSON_REPORT_PATH.exists()
    assert MD_REPORT_PATH.exists()
    assert summary["TOTAL"] >= 13

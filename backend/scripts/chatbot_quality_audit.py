from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import random
import re
import sys
from typing import Any, Iterable

from fastapi.testclient import TestClient
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, sessionmaker

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api.deps import get_current_user, get_db
from app.db.session import SessionLocal
from app.main import app
from app.models.batch import Batch
from app.models.enums import UserRole
from app.models.input import Input
from app.models.member import Member
from app.models.ml import MLPredictionLog, MLRecommendationLog
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.reference import KnowledgeChunk, ReferenceMetric
from app.models.stock import Stock
from app.models.user import User

ARTIFACT_DIR = ROOT_DIR / "artifacts"
JSON_REPORT = ARTIFACT_DIR / "chatbot_quality_audit.json"
MD_REPORT = ARTIFACT_DIR / "chatbot_quality_audit.md"

MISSING_EVIDENCE_MARKERS = {
    "aucune donnée",
    "aucune donnee",
    "aucune preuve",
    "introuvable",
    "pas de données",
    "pas de donnees",
    "pas disponible",
    "incomplet",
    "indisponible",
    "no data",
    "not found",
    "missing",
    "insufficient",
    "cannot provide",
}

TECHNICAL_LABEL_TOKENS = {
    "llm + rag",
    "openrouter",
    "openai/gpt-4o-mini",
    "low_grounding_confidence",
    "ml_logs_empty",
    "sql_context_missing",
    "sources rag",
    "retrieval diagnostics",
    "retrieval_plan",
    "context_metrics",
    "source_id",
    "chunk_type",
    "raw citation",
}

SMALL_TALK_FORBIDDEN_TOKENS = {
    "risques critiques",
    "pertes globales",
    "efficacité",
    "efficacite",
    "actions recommand",
    "niveau de confiance",
    "sources utilisées",
    "sources utilisees",
    "analyse opérationnelle",
    "analyse operationnelle",
}

UNSUPPORTED_FORBIDDEN_TOKENS = {
    "kpi",
    "risques critiques",
    "actions recommand",
    "niveau de confiance",
    "comparaison",
    "lots actifs",
    "stock disponible",
}

SQL_ONLY_FORBIDDEN_BLOCKS = {
    "Risques critiques",
    "Risques détectés",
    "Niveau de confiance",
    "Actions recommandées",
    "Analyse opérationnelle",
}

MODE_TO_INTENT = {
    "small_talk": "SMALL_TALK",
    "clarification_needed": "CLARIFICATION_NEEDED",
    "unsupported": "UNSUPPORTED",
    "sql_only": "SQL_ONLY",
    "sql_only_no_data": "SQL_ONLY",
    "rag_only_no_evidence": "RAG_ONLY",
}


@dataclass
class AuditCase:
    case_id: str
    category: str
    expected_intents: set[str]
    question: str
    requires_evidence: bool = False
    hallucination_trap: bool = False
    fake_tokens: tuple[str, ...] = ()
    session_key: str | None = None
    sequence_step: int = 0


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(_json_safe(v) for v in value)
    return value


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in needles)


def _flatten_strings(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            out.extend(_flatten_strings(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(_flatten_strings(item))
    return out


def _extract_metric_map(context_metrics: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("metric")): item for item in context_metrics if isinstance(item, dict)}


def _extract_warning_flags(metric_map: dict[str, dict[str, Any]]) -> list[str]:
    notes = str(metric_map.get("orchestration.warning_count", {}).get("notes", "") or "")
    return [item for item in notes.split("|") if item and item != "none"]


def _actual_intent(payload: dict[str, Any]) -> str:
    metric_map = _extract_metric_map(list(payload.get("context_metrics", [])))
    intent = str(metric_map.get("retrieval_plan.intent_type", {}).get("unit", "") or "").strip().upper()
    if intent:
        return intent
    mode = str(payload.get("mode", "") or "").strip().lower()
    return MODE_TO_INTENT.get(mode, "UNKNOWN")


def _used_sql(payload: dict[str, Any]) -> bool:
    metric_map = _extract_metric_map(list(payload.get("context_metrics", [])))
    sql_flag = float(metric_map.get("retrieval_plan.sql_needed", {}).get("value", 0.0) or 0.0) >= 0.5
    mode = str(payload.get("mode", "") or "").lower()
    if mode in {"sql_only", "sql_only_no_data"}:
        return True
    return sql_flag


def _used_rag(payload: dict[str, Any]) -> bool:
    metric_map = _extract_metric_map(list(payload.get("context_metrics", [])))
    rag_flag = float(metric_map.get("retrieval_plan.rag_needed", {}).get("value", 0.0) or 0.0) >= 0.5
    mode = str(payload.get("mode", "") or "").lower()
    has_citations = bool(payload.get("citations"))
    return rag_flag or has_citations or mode in {"llm-rag", "rag_only_no_evidence"}


def _used_ml(payload: dict[str, Any], answer_text: str) -> bool:
    metric_map = _extract_metric_map(list(payload.get("context_metrics", [])))
    if any("ml" in key.lower() for key in metric_map):
        return True
    warnings = _extract_warning_flags(metric_map)
    if any(flag.startswith("ML_") for flag in warnings):
        return True
    return " ml " in f" {answer_text.lower()} "


def _raw_json_visible(answer_text: str, ui_blocks: list[dict[str, Any]]) -> bool:
    if re.search(r"\{\s*\"[a-zA-Z0-9_]+\"\s*:\s*", answer_text):
        return True
    if re.search(r"\[[\s\{\}\[\]\"\':,._a-zA-Z0-9-]{20,}\]", answer_text):
        return True
    flat_ui = "\n".join(_flatten_strings(ui_blocks)).lower()
    return "source_id" in flat_ui or "retrieval_plan" in flat_ui


def _technical_labels_visible(answer_text: str, ui_blocks: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    corpus = "\n".join([answer_text, *[str(x) for x in _flatten_strings(ui_blocks)]]).lower()
    hits = sorted({token for token in TECHNICAL_LABEL_TOKENS if token in corpus})
    return (len(hits) > 0, hits)


def _evidence_missing_message(answer_text: str) -> bool:
    return _contains_any(answer_text, MISSING_EVIDENCE_MARKERS)


def _hallucination_risk(case: AuditCase, answer_text: str, payload: dict[str, Any], intent: str) -> tuple[str, str]:
    if not case.hallucination_trap:
        return "low", "Not a hallucination-trap scenario."

    answer_lower = answer_text.lower()
    has_missing_marker = _evidence_missing_message(answer_text)
    has_numbers = bool(re.findall(r"\b\d+(?:[\.,]\d+)?\b", answer_text))
    references_fake_token = any(token.lower() in answer_lower for token in case.fake_tokens)
    confident_tone = any(token in answer_lower for token in ["est de", "sont de", "critique", "élevé", "eleve", "recommandation", "confirmed", "confirmed"])

    if has_missing_marker and not confident_tone:
        return "low", "Missing-data disclaimer present for fake/non-existent entity."
    if (references_fake_token or has_numbers) and not has_missing_marker:
        return "high", "Answer appears to provide factual content for non-existent entity without missing-data disclaimer."
    if intent in {"SQL_ONLY", "HYBRID", "RAG_ONLY"} and not has_missing_marker:
        return "medium", "Operational intent triggered but missing-data disclaimer is unclear."
    return "medium", "Ambiguous hallucination-trap behavior."


def _irrelevant_content(case: AuditCase, answer_text: str, payload: dict[str, Any]) -> tuple[bool, str]:
    ui_blocks = list(payload.get("ui_blocks", []))
    titles = {str(item.get("title", "")) for item in ui_blocks if isinstance(item, dict)}
    answer_lower = answer_text.lower()

    if case.category == "SMALL_TALK":
        if ui_blocks or payload.get("citations") or payload.get("context_metrics"):
            return True, "Small talk returned non-empty blocks/citations/metrics."
        if any(token in answer_lower for token in SMALL_TALK_FORBIDDEN_TOKENS):
            return True, "Small talk answer includes operational analysis content."

    if case.category == "UNSUPPORTED":
        if ui_blocks or payload.get("citations") or payload.get("context_metrics"):
            return True, "Unsupported answer returned analysis blocks or evidence payload."
        if any(token in answer_lower for token in UNSUPPORTED_FORBIDDEN_TOKENS):
            return True, "Unsupported answer contains in-domain operational analysis terms."

    if case.category == "SQL_ONLY":
        if SQL_ONLY_FORBIDDEN_BLOCKS & titles:
            return True, "SQL_ONLY answer includes unrelated executive blocks (risk/confidence/actions)."

    return False, "No obvious irrelevant content leak detected."


def _intent_ok(actual_intent: str, expected_intents: set[str]) -> bool:
    return actual_intent in expected_intents


def _evaluate_case(case: AuditCase, payload: dict[str, Any]) -> dict[str, Any]:
    answer_text = str(payload.get("message", "") or "")
    actual_intent = _actual_intent(payload)
    citations = list(payload.get("citations", []))
    ui_blocks = list(payload.get("ui_blocks", []))
    context_metrics = list(payload.get("context_metrics", []))

    sql_used = _used_sql(payload)
    rag_used = _used_rag(payload)
    ml_used = _used_ml(payload, answer_text)
    evidence_missing = _evidence_missing_message(answer_text)
    raw_json_visible = _raw_json_visible(answer_text, ui_blocks)
    technical_visible, technical_hits = _technical_labels_visible(answer_text, ui_blocks)
    irrelevant, irrelevant_reason = _irrelevant_content(case, answer_text, payload)
    hallucination_risk, hallucination_note = _hallucination_risk(case, answer_text, payload, actual_intent)

    intent_ok = _intent_ok(actual_intent, case.expected_intents)
    citations_count = len(citations)

    notes: list[str] = []
    checks: list[bool] = []

    checks.append(intent_ok)
    if not intent_ok:
        notes.append(f"Intent mismatch: expected {sorted(case.expected_intents)}, got {actual_intent}.")

    if case.category == "SMALL_TALK":
        checks.extend([
            citations_count == 0,
            len(ui_blocks) == 0,
            len(context_metrics) == 0,
            not sql_used,
            not rag_used,
            not ml_used,
        ])
        if citations_count != 0 or ui_blocks or context_metrics:
            notes.append("Small talk should not return citations, cards, or metrics.")
        if sql_used or rag_used or ml_used:
            notes.append("Small talk should not trigger SQL/RAG/ML.")

    elif case.category == "UNSUPPORTED":
        checks.extend([
            citations_count == 0,
            len(ui_blocks) == 0,
            len(context_metrics) == 0,
            not sql_used,
            not rag_used,
            not ml_used,
        ])
        if citations_count != 0 or ui_blocks or context_metrics:
            notes.append("Unsupported query should not return domain analysis payload.")

    elif case.category == "SQL_ONLY":
        checks.extend([
            sql_used,
            not rag_used,
            citations_count == 0,
        ])
        if not sql_used:
            notes.append("SQL_ONLY case did not use SQL route.")
        if rag_used:
            notes.append("SQL_ONLY case should not require RAG.")
        if citations_count != 0:
            notes.append("SQL_ONLY case should not expose citations.")

    elif case.category == "RAG_ONLY":
        checks.append(rag_used)
        if case.requires_evidence:
            checks.append(citations_count > 0 or evidence_missing)
            if not (citations_count > 0 or evidence_missing):
                notes.append("RAG_ONLY case lacks citations and lacks explicit evidence-missing disclaimer.")

    elif case.category == "HYBRID":
        checks.extend([sql_used, rag_used])
        if case.requires_evidence:
            checks.append(citations_count > 0 or evidence_missing)
            if not (citations_count > 0 or evidence_missing):
                notes.append("HYBRID case lacks citations and lacks explicit evidence-missing disclaimer.")

    if case.hallucination_trap:
        checks.append(hallucination_risk != "high")
        if hallucination_risk == "high":
            notes.append("Hallucination risk high for fake/non-existent entity question.")

    checks.extend([
        not raw_json_visible,
        not technical_visible,
        not irrelevant,
    ])

    if raw_json_visible:
        notes.append("Raw JSON-like content detected in manager-facing answer payload.")
    if technical_visible:
        notes.append(f"Technical labels leaked: {technical_hits}")
    if irrelevant:
        notes.append(irrelevant_reason)

    passed = all(checks)
    if not notes and passed:
        notes.append("All checks passed.")

    return {
        "case_id": case.case_id,
        "category": case.category,
        "question": case.question,
        "expected_intent": sorted(case.expected_intents),
        "actual_intent": actual_intent,
        "answer_text": answer_text,
        "citations_count": citations_count,
        "sql_used": sql_used,
        "rag_used": rag_used,
        "ml_used": ml_used,
        "hallucination_risk": hallucination_risk,
        "hallucination_note": hallucination_note,
        "irrelevant_content_detected": irrelevant,
        "raw_json_visible": raw_json_visible,
        "technical_labels_visible": technical_visible,
        "technical_labels": technical_hits,
        "ui_blocks_count": len(ui_blocks),
        "context_metrics_count": len(context_metrics),
        "mode": str(payload.get("mode", "")),
        "grounded": bool(payload.get("grounded", False)),
        "evidence_missing_disclaimer": evidence_missing,
        "pass": passed,
        "notes": notes,
        "response_payload": payload,
    }


def _pick(values: list[str], fallback: str, index: int = 0) -> str:
    if not values:
        return fallback
    return values[index % len(values)]


def _safe_lot_compare(lots: list[str]) -> tuple[str, str]:
    if len(lots) >= 2:
        return lots[0], lots[1]
    if len(lots) == 1:
        return lots[0], lots[0]
    return "LOT-MANG-001", "LOT-MANG-002"


def _build_snapshot(db: Session) -> tuple[User, dict[str, Any]]:
    manager = db.scalar(select(User).where(User.role == UserRole.MANAGER).order_by(User.created_at.asc()).limit(1))
    if manager is None:
        manager = db.scalar(select(User).where(User.role == UserRole.OWNER).order_by(User.created_at.asc()).limit(1))
    if manager is None:
        manager = db.scalar(select(User).where(User.role == UserRole.ADMIN).order_by(User.created_at.asc()).limit(1))
    if manager is None or manager.cooperative_id is None:
        raise RuntimeError("No cooperative-scoped manager/owner/admin user found for chatbot quality audit.")

    coop_id = manager.cooperative_id

    product_rows = db.execute(
        select(Product.name).where(Product.cooperative_id == coop_id).order_by(Product.name.asc())
    ).all()
    products = [str(row[0]) for row in product_rows if row[0]]

    stock_rows = db.execute(
        select(Product.name, Stock.total_stock_kg, Stock.reserved_in_lots_kg, Stock.threshold)
        .join(Stock, Stock.product_id == Product.id)
        .where(Stock.cooperative_id == coop_id)
        .order_by(Product.name.asc())
    ).all()

    lot_rows = db.execute(
        select(Batch.code, Batch.status, Product.name)
        .join(Product, Product.id == Batch.product_id)
        .where(Batch.cooperative_id == coop_id)
        .order_by(Batch.creation_date.desc())
        .limit(30)
    ).all()

    step_rows = db.execute(
        select(ProcessStep.type, func.count(ProcessStep.id))
        .join(Batch, Batch.id == ProcessStep.batch_id)
        .where(Batch.cooperative_id == coop_id)
        .group_by(ProcessStep.type)
        .order_by(func.count(ProcessStep.id).desc())
    ).all()

    member_rows = db.execute(
        select(Member.code, Member.full_name)
        .where(Member.cooperative_id == coop_id)
        .order_by(Member.created_at.desc())
        .limit(20)
    ).all()

    reco_count = db.scalar(
        select(func.count(Recommendation.id))
        .join(Batch, Batch.id == Recommendation.batch_id)
        .where(Batch.cooperative_id == coop_id)
    ) or 0

    ml_pred_count = db.scalar(select(func.count(MLPredictionLog.id))) or 0
    ml_reco_count = db.scalar(select(func.count(MLRecommendationLog.id))) or 0

    ref_metric_count = db.scalar(select(func.count(ReferenceMetric.id))) or 0
    knowledge_rows = db.execute(
        select(KnowledgeChunk.source_id, KnowledgeChunk.crop, KnowledgeChunk.topic)
        .order_by(desc(KnowledgeChunk.created_at))
        .limit(40)
    ).all()

    input_total_qty = db.scalar(
        select(func.coalesce(func.sum(Input.quantity), 0.0)).where(Input.cooperative_id == coop_id)
    ) or 0.0

    snapshot = {
        "generated_at": datetime.now(UTC).isoformat(),
        "cooperative_id": str(coop_id),
        "manager_user_id": str(manager.id),
        "products": products,
        "stocks": [
            {
                "product": str(name),
                "total_stock_kg": float(total or 0.0),
                "reserved_stock_kg": float(reserved or 0.0),
                "available_stock_kg": float((total or 0.0) - (reserved or 0.0)),
                "threshold": float(threshold or 0.0),
            }
            for name, total, reserved, threshold in stock_rows
        ],
        "lots": [
            {
                "code": str(code),
                "status": str(status.value if hasattr(status, "value") else status),
                "product": str(product),
            }
            for code, status, product in lot_rows
        ],
        "stages": [str(item[0]) for item in step_rows if item[0]],
        "members": [{"code": str(code), "name": str(name)} for code, name in member_rows],
        "recommendations_count": int(reco_count),
        "ml_prediction_logs_count": int(ml_pred_count),
        "ml_recommendation_logs_count": int(ml_reco_count),
        "reference_metrics_count": int(ref_metric_count),
        "knowledge_chunks": [
            {"source_id": str(source_id), "crop": str(crop), "topic": str(topic)}
            for source_id, crop, topic in knowledge_rows
        ],
        "input_total_qty": float(input_total_qty),
    }
    return manager, snapshot


def _make_fake_token(prefix: str, existing_values: Iterable[str]) -> str:
    existing = {str(value).lower() for value in existing_values}
    base = f"{prefix.upper()}_{random.randint(7000, 9999)}"
    while base.lower() in existing:
        base = f"{prefix.upper()}_{random.randint(7000, 9999)}"
    return base


def _build_cases(snapshot: dict[str, Any]) -> list[AuditCase]:
    products = snapshot.get("products", [])
    lots = [item.get("code", "") for item in snapshot.get("lots", []) if item.get("code")]
    stages = [str(item) for item in snapshot.get("stages", []) if item]
    members = [item.get("code", "") for item in snapshot.get("members", []) if item.get("code")]

    p1 = _pick(products, "mangue", 0)
    p2 = _pick(products, "mil", 1)
    p3 = _pick(products, "arachide", 2)

    lot1, lot2 = _safe_lot_compare(lots)
    stage1 = _pick(stages, "séchage", 0)
    stage2 = _pick(stages, "tri", 1)
    member1 = _pick(members, "M-001", 0)

    fake_product = _make_fake_token("fake_product", products)
    fake_lot = _make_fake_token("lot_fake", lots)
    fake_member = _make_fake_token("member_fake", members)
    fake_stage = _make_fake_token("stage_fake", stages)
    fake_crop = _make_fake_token("crop_fake", products)

    cases: list[AuditCase] = []

    def add(case_id: str, category: str, expected: set[str], question: str, *, requires_evidence: bool = False, hallucination_trap: bool = False, fake_tokens: tuple[str, ...] = (), session_key: str | None = None, sequence_step: int = 0) -> None:
        cases.append(
            AuditCase(
                case_id=case_id,
                category=category,
                expected_intents=expected,
                question=question,
                requires_evidence=requires_evidence,
                hallucination_trap=hallucination_trap,
                fake_tokens=fake_tokens,
                session_key=session_key,
                sequence_step=sequence_step,
            )
        )

    # SQL_ONLY
    add("sql-01", "SQL_ONLY", {"SQL_ONLY"}, f"Quel est le stock actuel de {p1} ?")
    add("sql-02", "SQL_ONLY", {"SQL_ONLY"}, f"Quel est le stock réservé de {p1} ?")
    add("sql-03", "SQL_ONLY", {"SQL_ONLY"}, f"Quel est le stock disponible de {p1} ?")
    add("sql-04", "SQL_ONLY", {"SQL_ONLY"}, "Combien de lots actifs avons-nous ?")
    add("sql-05", "SQL_ONLY", {"SQL_ONLY"}, f"Quel est le statut du lot {lot1} ?")
    add("sql-06", "SQL_ONLY", {"SQL_ONLY"}, f"Quel est le statut du lot {lot2} ?")
    add("sql-07", "SQL_ONLY", {"SQL_ONLY"}, f"Donne la quantité disponible de {p2}.")
    add("sql-08", "SQL_ONLY", {"SQL_ONLY"}, f"Combien de stock {p3} reste-t-il ?")
    add("sql-09", "SQL_ONLY", {"SQL_ONLY"}, "Quel est le total de collecte actuellement ?")
    add("sql-10", "SQL_ONLY", {"SQL_ONLY"}, f"Stock de {p1} et seuil: donne les valeurs exactes.")

    # HYBRID
    add("hybrid-01", "HYBRID", {"HYBRID"}, f"Pourquoi les pertes sont-elles élevées sur {stage1} pour {p1} cette semaine ?", requires_evidence=True)
    add("hybrid-02", "HYBRID", {"HYBRID"}, "Quels sont les risques critiques opérationnels de la coopérative aujourd'hui ?", requires_evidence=True)
    add("hybrid-03", "HYBRID", {"HYBRID"}, f"Compare la performance des lots {lot1} et {lot2} et explique les écarts.", requires_evidence=True)
    add("hybrid-04", "HYBRID", {"HYBRID"}, f"Explique la perte de {stage1} sur {p1} et propose des actions.", requires_evidence=True)
    add("hybrid-05", "HYBRID", {"HYBRID"}, f"Quelles recommandations pour {p1} à l'étape {stage1} ?", requires_evidence=True)
    add("hybrid-06", "HYBRID", {"HYBRID"}, f"Détecte les anomalies sur le lot {lot1} et les causes probables.", requires_evidence=True)
    add("hybrid-07", "HYBRID", {"HYBRID"}, f"Pourquoi le rendement est faible au {stage2} pour {p2} ?", requires_evidence=True)
    add("hybrid-08", "HYBRID", {"HYBRID"}, f"Fais un bilan matière du lot {lot1} avec les risques associés.", requires_evidence=True)
    add("hybrid-09", "HYBRID", {"HYBRID"}, f"Analyse l'efficacité du processus {stage1} et les risques sur {p1}.", requires_evidence=True)
    add("hybrid-10", "HYBRID", {"HYBRID"}, "Compare pertes, efficacité et risques opérationnels du jour.", requires_evidence=True)

    # RAG_ONLY
    add("rag-01", "RAG_ONLY", {"RAG_ONLY"}, "Quelles sont les meilleures pratiques pour le séchage de la mangue ?", requires_evidence=True)
    add("rag-02", "RAG_ONLY", {"RAG_ONLY"}, "Quels benchmarks de pertes existent pour le mil ?", requires_evidence=True)
    add("rag-03", "RAG_ONLY", {"RAG_ONLY"}, "Quels conseils post-récolte pour le stockage afin de réduire les pertes ?", requires_evidence=True)
    add("rag-04", "RAG_ONLY", {"RAG_ONLY"}, "Quelles recommandations d'emballage améliorent la conservation ?", requires_evidence=True)
    add("rag-05", "RAG_ONLY", {"RAG_ONLY"}, f"Donne des références agronomiques utiles pour la transformation de {p1}.", requires_evidence=True)
    add("rag-06", "RAG_ONLY", {"RAG_ONLY"}, "Quels seuils d'humidité sont recommandés en séchage post-récolte ?", requires_evidence=True)
    add("rag-07", "RAG_ONLY", {"RAG_ONLY"}, "Quelles sources conseillent des pratiques de tri pour limiter les pertes ?", requires_evidence=True)
    add("rag-08", "RAG_ONLY", {"RAG_ONLY"}, "Que disent les références sur la prévention des moisissures en stockage ?", requires_evidence=True)

    # SMALL_TALK
    add("small-01", "SMALL_TALK", {"SMALL_TALK"}, "hello")
    add("small-02", "SMALL_TALK", {"SMALL_TALK"}, "bonjour")
    add("small-03", "SMALL_TALK", {"SMALL_TALK"}, "salut")
    add("small-04", "SMALL_TALK", {"SMALL_TALK"}, "merci")
    add("small-05", "SMALL_TALK", {"SMALL_TALK"}, "ok")
    add("small-06", "SMALL_TALK", {"SMALL_TALK"}, "test")

    # UNSUPPORTED
    add("unsup-01", "UNSUPPORTED", {"UNSUPPORTED"}, "Quel est le meilleur film cette semaine ?")
    add("unsup-02", "UNSUPPORTED", {"UNSUPPORTED"}, "Quel est le résultat du match de football d'hier ?")
    add("unsup-03", "UNSUPPORTED", {"UNSUPPORTED"}, "Que penses-tu de la politique internationale ?")
    add("unsup-04", "UNSUPPORTED", {"UNSUPPORTED"}, "Tu me conseilles quoi pour ma vie personnelle ?")
    add("unsup-05", "UNSUPPORTED", {"UNSUPPORTED"}, "Quelle météo demain à New York ?")
    add("unsup-06", "UNSUPPORTED", {"UNSUPPORTED"}, "Best crypto to buy today?")

    # Hallucination traps (mix SQL/HYBRID/RAG)
    add("hall-01", "SQL_ONLY", {"SQL_ONLY"}, f"Quel est le stock actuel de {fake_product} ?", hallucination_trap=True, fake_tokens=(fake_product,))
    add("hall-02", "SQL_ONLY", {"SQL_ONLY"}, f"Quel est le statut du lot {fake_lot} ?", hallucination_trap=True, fake_tokens=(fake_lot,))
    add("hall-03", "HYBRID", {"HYBRID"}, f"Pourquoi les pertes du lot {fake_lot} sont élevées aujourd'hui ?", requires_evidence=True, hallucination_trap=True, fake_tokens=(fake_lot,))
    add("hall-04", "HYBRID", {"HYBRID"}, f"Donne une recommandation opérationnelle pour {fake_product} au {stage1}.", requires_evidence=True, hallucination_trap=True, fake_tokens=(fake_product,))
    add("hall-05", "SQL_ONLY", {"SQL_ONLY"}, f"Quel est le total de collecte pour le producteur {fake_member} ?", hallucination_trap=True, fake_tokens=(fake_member,))
    add("hall-06", "HYBRID", {"HYBRID"}, f"Explique les pertes à l'étape {fake_stage} cette semaine.", requires_evidence=True, hallucination_trap=True, fake_tokens=(fake_stage,))
    add("hall-07", "RAG_ONLY", {"RAG_ONLY"}, f"Quelles références agronomiques pour la culture {fake_crop} ?", requires_evidence=True, hallucination_trap=True, fake_tokens=(fake_crop,))
    add("hall-08", "SQL_ONLY", {"SQL_ONLY"}, f"Quel est le stock réservé de {fake_product} ?", hallucination_trap=True, fake_tokens=(fake_product,))

    # Stale-response sequence (same session)
    add("stale-01", "HYBRID", {"HYBRID"}, f"Quels sont les risques critiques sur {p1} au {stage1} aujourd'hui ?", requires_evidence=True, session_key="stale-seq-1", sequence_step=1)
    add("stale-02", "SMALL_TALK", {"SMALL_TALK"}, "hello", session_key="stale-seq-1", sequence_step=2)

    return cases


def _create_chat_session(client: TestClient, title: str) -> str:
    response = client.post("/chat/sessions", json={"title": title})
    if response.status_code != 200:
        raise RuntimeError(f"Failed to create chat session: HTTP {response.status_code} {response.text}")
    payload = response.json()
    return str(payload["id"])


def _run_case(client: TestClient, case: AuditCase, session_id: str) -> tuple[dict[str, Any], float]:
    started = datetime.now(UTC)
    response = client.post(
        "/chat",
        json={"session_id": session_id, "message": case.question, "top_k": 4},
    )
    latency_ms = (datetime.now(UTC) - started).total_seconds() * 1000.0
    if response.status_code != 200:
        payload = {
            "success": False,
            "message": f"HTTP {response.status_code}: {response.text}",
            "mode": "http_error",
            "citations": [],
            "context_metrics": [],
            "ui_blocks": [],
        }
    else:
        payload = response.json()
    return payload, latency_ms


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for row in results if row["pass"])

    by_intent: dict[str, dict[str, int]] = {}
    for row in results:
        expected = row["expected_intent"][0] if row.get("expected_intent") else "UNKNOWN"
        slot = by_intent.setdefault(expected, {"total": 0, "pass": 0})
        slot["total"] += 1
        if row["pass"]:
            slot["pass"] += 1

    hall_cases = [row for row in results if row.get("hallucination_trap")]
    hall_high = [row for row in hall_cases if row.get("hallucination_risk") == "high"]

    routing_errors = [row for row in results if row.get("actual_intent") not in set(row.get("expected_intent", []))]
    citation_issues = [
        row
        for row in results
        if row["category"] in {"RAG_ONLY", "HYBRID"}
        and row.get("requires_evidence")
        and row.get("citations_count", 0) == 0
        and not row.get("evidence_missing_disclaimer")
    ]
    stale_issues = [row for row in results if row.get("stale_issue")]
    ui_debug_leaks = [row for row in results if row.get("raw_json_visible") or row.get("technical_labels_visible")]

    return {
        "total_cases": total,
        "passed_cases": passed,
        "overall_pass_rate": round((passed / total) if total else 0.0, 4),
        "pass_rate_by_intent": {
            key: {
                "pass": value["pass"],
                "total": value["total"],
                "rate": round((value["pass"] / value["total"]) if value["total"] else 0.0, 4),
            }
            for key, value in sorted(by_intent.items())
        },
        "routing_error_count": len(routing_errors),
        "hallucination_high_risk_count": len(hall_high),
        "citation_issue_count": len(citation_issues),
        "stale_issue_count": len(stale_issues),
        "ui_debug_leak_count": len(ui_debug_leaks),
    }


def _prioritized_fixes(results: list[dict[str, Any]], summary: dict[str, Any]) -> list[dict[str, str]]:
    fixes: list[dict[str, str]] = []

    if summary["routing_error_count"] > 0:
        fixes.append(
            {
                "priority": "P0",
                "issue": "Routing errors",
                "fix": "Tighten pre-router intent guards and add more intent tests for borderline prompts.",
            }
        )
    if summary["hallucination_high_risk_count"] > 0:
        fixes.append(
            {
                "priority": "P0",
                "issue": "Hallucination on missing entities",
                "fix": "Force explicit missing-data disclaimers when fake/non-existent product/lot/member/stage is detected.",
            }
        )
    if summary["stale_issue_count"] > 0:
        fixes.append(
            {
                "priority": "P0",
                "issue": "Stale response leakage",
                "fix": "Reset normalized response state and suppress previous cards/citations on non-operational intents.",
            }
        )
    if summary["citation_issue_count"] > 0:
        fixes.append(
            {
                "priority": "P1",
                "issue": "Weak/missing citations in evidence-required answers",
                "fix": "Require citation presence for RAG/HYBRID or emit explicit evidence-missing fallback text.",
            }
        )
    if summary["ui_debug_leak_count"] > 0:
        fixes.append(
            {
                "priority": "P1",
                "issue": "UI/debug leakage",
                "fix": "Keep technical labels/codes out of manager-facing text and isolate them in technical drawer only.",
            }
        )

    if not fixes:
        fixes.append(
            {
                "priority": "P2",
                "issue": "No critical failures detected",
                "fix": "Keep the audit in CI and expand multilingual edge-case coverage.",
            }
        )

    return fixes


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines: list[str] = [
        "# Chatbot Quality Audit Report",
        "",
        "## Overview",
        f"- Generated at: {report['generated_at']}",
        f"- Total test questions: {summary['total_cases']}",
        f"- Overall pass rate: {summary['overall_pass_rate']}",
        "",
        "## Pass Rate by Intent",
    ]

    for intent, values in summary["pass_rate_by_intent"].items():
        lines.append(f"- {intent}: {values['pass']}/{values['total']} ({values['rate']})")

    failed = [row for row in report["results"] if not row["pass"]]
    failed_sorted = sorted(
        failed,
        key=lambda row: (
            0 if row.get("hallucination_risk") == "high" else 1,
            0 if row.get("actual_intent") not in set(row.get("expected_intent", [])) else 1,
            row.get("citations_count", 0),
        ),
    )

    lines.extend(["", "## Worst Failed Questions"])
    if failed_sorted:
        for row in failed_sorted[:12]:
            lines.extend(
                [
                    f"- `{row['case_id']}` [{row['category']}] {row['question']}",
                    f"  - expected/actual intent: {row['expected_intent']} -> {row['actual_intent']}",
                    f"  - pass: {row['pass']} | hallucination_risk: {row['hallucination_risk']} | citations: {row['citations_count']}",
                    f"  - notes: {'; '.join(row['notes'])}",
                ]
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Hallucination Cases"])
    hall_cases = [row for row in report["results"] if row.get("hallucination_trap")]
    hall_fail = [row for row in hall_cases if row.get("hallucination_risk") == "high" or not row.get("pass")]
    if hall_fail:
        for row in hall_fail:
            lines.append(f"- `{row['case_id']}` risk={row['hallucination_risk']} :: {row['question']}")
    else:
        lines.append("- No high-risk hallucination case detected.")

    lines.extend(["", "## Routing Errors"])
    routing_errors = [row for row in report["results"] if row.get("actual_intent") not in set(row.get("expected_intent", []))]
    if routing_errors:
        for row in routing_errors:
            lines.append(f"- `{row['case_id']}` expected {row['expected_intent']} got {row['actual_intent']} :: {row['question']}")
    else:
        lines.append("- None")

    lines.extend(["", "## Citation Issues"])
    citation_issues = [
        row
        for row in report["results"]
        if row["category"] in {"RAG_ONLY", "HYBRID"}
        and row.get("requires_evidence")
        and row.get("citations_count", 0) == 0
        and not row.get("evidence_missing_disclaimer")
    ]
    if citation_issues:
        for row in citation_issues:
            lines.append(f"- `{row['case_id']}` [{row['category']}] {row['question']}")
    else:
        lines.append("- None")

    lines.extend(["", "## Stale Response Issues"])
    stale_issues = [row for row in report["results"] if row.get("stale_issue")]
    if stale_issues:
        for row in stale_issues:
            lines.append(f"- `{row['case_id']}` {row['stale_issue']}")
    else:
        lines.append("- None")

    lines.extend(["", "## UI/Debug Leakage Issues"])
    leaks = [row for row in report["results"] if row.get("raw_json_visible") or row.get("technical_labels_visible")]
    if leaks:
        for row in leaks:
            lines.append(
                f"- `{row['case_id']}` raw_json={row['raw_json_visible']} technical={row['technical_labels_visible']} labels={row['technical_labels']}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Recommended Fixes (Priority)"])
    for fix in report["recommended_fixes"]:
        lines.append(f"- {fix['priority']} — {fix['issue']}: {fix['fix']}")

    lines.extend(["", "## Minimal Acceptance Check"])
    checks = report["acceptance"]
    lines.append(f"- At least 40 questions: {checks['at_least_40_questions']}")
    lines.append(f"- All required intents covered: {checks['all_required_intents_covered']}")
    lines.append(f"- Uses real DB values: {checks['uses_real_db_values']}")
    lines.append(f"- Uses fake/non-existing values: {checks['uses_fake_values']}")
    lines.append(f"- Clear pass/fail + priority fixes: {checks['clear_report_with_priority_fixes']}")

    return "\n".join(lines)


def main() -> None:
    random.seed(42)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    manager: User | None = None
    conn = None
    outer_tx = None
    audit_session = None

    try:
        manager, snapshot = _build_snapshot(db)

        bind = db.get_bind()
        if bind is None:
            raise RuntimeError("Database bind unavailable for audit.")

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

        cases = _build_cases(snapshot)
        session_cache: dict[str, str] = {}
        results: list[dict[str, Any]] = []

        for case in cases:
            session_key = case.session_key or case.case_id
            if session_key not in session_cache:
                session_cache[session_key] = _create_chat_session(client, f"Quality Audit - {session_key}")
            session_id = session_cache[session_key]

            payload, latency_ms = _run_case(client, case, session_id)
            evaluation = _evaluate_case(case, payload)
            evaluation.update(
                {
                    "latency_ms": round(latency_ms, 3),
                    "hallucination_trap": case.hallucination_trap,
                    "requires_evidence": case.requires_evidence,
                    "session_key": case.session_key,
                    "sequence_step": case.sequence_step,
                    "stale_issue": "",
                }
            )
            results.append(evaluation)

        # Stale response check (sequence-specific validation)
        stale_rows = [row for row in results if row.get("session_key") == "stale-seq-1"]
        stale_rows = sorted(stale_rows, key=lambda row: row.get("sequence_step", 0))
        if len(stale_rows) == 2:
            first, second = stale_rows
            leak_notes: list[str] = []
            if second.get("citations_count", 0) > 0:
                leak_notes.append("Greeting response re-used citations from previous answer.")
            if second.get("ui_blocks_count", 0) > 0:
                leak_notes.append("Greeting response re-used UI cards from previous answer.")
            if second.get("context_metrics_count", 0) > 0:
                leak_notes.append("Greeting response re-used context metrics from previous answer.")
            if _contains_any(second.get("answer_text", ""), SMALL_TALK_FORBIDDEN_TOKENS):
                leak_notes.append("Greeting response includes operational analysis tokens.")
            if leak_notes:
                second["stale_issue"] = " ".join(leak_notes)
                second["pass"] = False
                second["notes"].append(second["stale_issue"])

        summary = _aggregate(results)
        recommended_fixes = _prioritized_fixes(results, summary)

        categories_present = {row["category"] for row in results}
        intents_present = {item for row in results for item in row["expected_intent"]}
        acceptance = {
            "at_least_40_questions": len(results) >= 40,
            "all_required_intents_covered": all(
                key in categories_present
                for key in {"SQL_ONLY", "HYBRID", "RAG_ONLY", "SMALL_TALK", "UNSUPPORTED"}
            ) and {"SQL_ONLY", "HYBRID", "RAG_ONLY", "SMALL_TALK", "UNSUPPORTED"}.issubset(intents_present),
            "uses_real_db_values": bool(snapshot.get("products") or snapshot.get("lots") or snapshot.get("members")),
            "uses_fake_values": any(row.get("hallucination_trap") for row in results),
            "clear_report_with_priority_fixes": True,
        }

        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "snapshot": snapshot,
            "summary": summary,
            "results": results,
            "recommended_fixes": recommended_fixes,
            "acceptance": acceptance,
        }

        JSON_REPORT.write_text(json.dumps(_json_safe(report), ensure_ascii=False, indent=2), encoding="utf-8")
        MD_REPORT.write_text(_render_markdown(report), encoding="utf-8")

        print(f"Saved {JSON_REPORT}")
        print(f"Saved {MD_REPORT}")
        print(f"Total cases: {len(results)} | Overall pass rate: {summary['overall_pass_rate']}")

    finally:
        try:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)
        except Exception:
            pass
        try:
            if outer_tx is not None and outer_tx.is_active:
                outer_tx.rollback()
        except Exception:
            pass
        try:
            if audit_session is not None:
                audit_session.close()
        except Exception:
            pass
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass
        db.close()


if __name__ == "__main__":
    main()

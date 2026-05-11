from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
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

REPORT_DIR = ROOT_DIR / "reports"
JSON_REPORT = REPORT_DIR / "chatbot_unseen_robustness_audit.json"
MD_REPORT = REPORT_DIR / "chatbot_unseen_robustness_audit.md"

FIRST_AUDIT_QUESTIONS = {
    "Quel est le stock actuel de {p1} ?",
    "Quel est le stock réservé de {p1} ?",
    "Quel est le stock disponible de {p1} ?",
    "Combien de lots actifs avons-nous ?",
    "Quel est le statut du lot {lot1} ?",
    "Quel est le statut du lot {lot2} ?",
    "Donne la quantité disponible de {p2}.",
    "Combien de stock {p3} reste-t-il ?",
    "Quel est le total de collecte actuellement ?",
    "Stock de {p1} et seuil: donne les valeurs exactes.",
    "Pourquoi les pertes sont-elles élevées sur {stage1} pour {p1} cette semaine ?",
    "Quels sont les risques critiques opérationnels de la coopérative aujourd'hui ?",
    "Compare la performance des lots {lot1} et {lot2} et explique les écarts.",
    "Explique la perte de {stage1} sur {p1} et propose des actions.",
    "Quelles recommandations pour {p1} à l'étape {stage1} ?",
    "Détecte les anomalies sur le lot {lot1} et les causes probables.",
    "Pourquoi le rendement est faible au {stage2} pour {p2} ?",
    "Fais un bilan matière du lot {lot1} avec les risques associés.",
    "Analyse l'efficacité du processus {stage1} et les risques sur {p1}.",
    "Compare pertes, efficacité et risques opérationnels du jour.",
    "Quelles sont les meilleures pratiques pour le séchage de la mangue ?",
    "Quels benchmarks de pertes existent pour le mil ?",
    "Quels conseils post-récolte pour le stockage afin de réduire les pertes ?",
    "Quelles recommandations d'emballage améliorent la conservation ?",
    "Donne des références agronomiques utiles pour la transformation de {p1}.",
    "Quels seuils d'humidité sont recommandés en séchage post-récolte ?",
    "Quelles sources conseillent des pratiques de tri pour limiter les pertes ?",
    "Que disent les références sur la prévention des moisissures en stockage ?",
    "hello",
    "bonjour",
    "salut",
    "merci",
    "ok",
    "test",
    "Quel est le meilleur film cette semaine ?",
    "Quel est le résultat du match de football d'hier ?",
    "Que penses-tu de la politique internationale ?",
    "Tu me conseilles quoi pour ma vie personnelle ?",
    "Quelle météo demain à New York ?",
    "Best crypto to buy today?",
}

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
}

UNSUPPORTED_FORBIDDEN_TOKENS = {
    "kpi",
    "risques critiques",
    "actions recommand",
    "niveau de confiance",
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

FOLLOWUP_CONTEXT_FAIL_MARKERS = {
    "pouvez-vous préciser",
    "veuillez reformuler",
    "demande trop vague",
}

MODE_TO_INTENT = {
    "small_talk": "SMALL_TALK",
    "clarification_needed": "CLARIFICATION_NEEDED",
    "unsupported": "UNSUPPORTED",
    "sql_only": "SQL_ONLY",
    "sql_only_no_data": "SQL_ONLY",
    "rag_only_no_evidence": "RAG_ONLY",
    "hybrid_no_evidence": "HYBRID",
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
    followup_expected: bool = False


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
    return sql_flag or mode in {"sql_only", "sql_only_no_data"}


def _used_rag(payload: dict[str, Any]) -> bool:
    metric_map = _extract_metric_map(list(payload.get("context_metrics", [])))
    rag_flag = float(metric_map.get("retrieval_plan.rag_needed", {}).get("value", 0.0) or 0.0) >= 0.5
    mode = str(payload.get("mode", "") or "").lower()
    return rag_flag or bool(payload.get("citations")) or mode in {"llm-rag", "rag_only_no_evidence", "hybrid_no_evidence"}


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


def _hallucination_risk(case: AuditCase, answer_text: str, intent: str) -> tuple[str, str]:
    if not case.hallucination_trap:
        return "low", "Not a hallucination-trap scenario."
    answer_lower = answer_text.lower()
    has_missing_marker = _evidence_missing_message(answer_text)
    has_numbers = bool(re.findall(r"\b\d+(?:[\.,]\d+)?\b", answer_text))
    references_fake = any(token.lower() in answer_lower for token in case.fake_tokens)
    if has_missing_marker:
        return "low", "Missing-data disclaimer present."
    if references_fake or has_numbers:
        return "high", "Potential invented facts for fake entity."
    if intent in {"SQL_ONLY", "HYBRID", "RAG_ONLY"}:
        return "medium", "Operational route without explicit missing-data disclaimer."
    return "medium", "Ambiguous fake-entity response."


def _pick(values: list[str], fallback: str, index: int = 0) -> str:
    if not values:
        return fallback
    return values[index % len(values)]


def _safe_lots(lots: list[str]) -> tuple[str, str, str]:
    if len(lots) >= 3:
        return lots[0], lots[1], lots[2]
    if len(lots) == 2:
        return lots[0], lots[1], lots[1]
    if len(lots) == 1:
        return lots[0], lots[0], lots[0]
    return "LOT-MANG-001", "LOT-BISS-001", "LOT-ARACH-001"


def _ensure_fake_value(base: str, existing: Iterable[str]) -> str:
    existing_l = {str(item).strip().lower() for item in existing if item}
    if base.lower() not in existing_l:
        return base
    suffix = 901
    while f"{base}-{suffix}".lower() in existing_l:
        suffix += 1
    return f"{base}-{suffix}"


def _build_snapshot(db: Session) -> tuple[User, dict[str, Any]]:
    manager = db.scalar(select(User).where(User.role == UserRole.MANAGER).order_by(User.created_at.asc()).limit(1))
    if manager is None:
        manager = db.scalar(select(User).where(User.role == UserRole.OWNER).order_by(User.created_at.asc()).limit(1))
    if manager is None:
        manager = db.scalar(select(User).where(User.role == UserRole.ADMIN).order_by(User.created_at.asc()).limit(1))
    if manager is None or manager.cooperative_id is None:
        raise RuntimeError("No cooperative-scoped manager/owner/admin user found.")

    coop_id = manager.cooperative_id
    products = [str(row[0]) for row in db.execute(select(Product.name).where(Product.cooperative_id == coop_id).order_by(Product.name.asc())).all() if row[0]]
    lots = db.execute(
        select(Batch.code, Batch.status, Product.name)
        .join(Product, Product.id == Batch.product_id)
        .where(Batch.cooperative_id == coop_id)
        .order_by(Batch.creation_date.desc())
        .limit(40)
    ).all()
    stages = [str(item[0]) for item in db.execute(
        select(ProcessStep.type, func.count(ProcessStep.id))
        .join(Batch, Batch.id == ProcessStep.batch_id)
        .where(Batch.cooperative_id == coop_id)
        .group_by(ProcessStep.type)
        .order_by(func.count(ProcessStep.id).desc())
    ).all() if item[0]]
    members = db.execute(
        select(Member.code, Member.full_name)
        .where(Member.cooperative_id == coop_id)
        .order_by(Member.created_at.desc())
        .limit(30)
    ).all()

    stock_rows = db.execute(
        select(Product.name, Stock.total_stock_kg, Stock.reserved_in_lots_kg, Stock.threshold)
        .join(Stock, Stock.product_id == Product.id)
        .where(Stock.cooperative_id == coop_id)
        .order_by(Product.name.asc())
    ).all()

    snapshot = {
        "generated_at": datetime.now(UTC).isoformat(),
        "cooperative_id": str(coop_id),
        "manager_user_id": str(manager.id),
        "products": products,
        "lots": [{"code": str(code), "status": str(status.value if hasattr(status, "value") else status), "product": str(product)} for code, status, product in lots],
        "stages": stages,
        "members": [{"code": str(code), "name": str(name)} for code, name in members],
        "stocks": [{"product": str(name), "total_stock_kg": float(total or 0.0), "reserved_stock_kg": float(reserved or 0.0), "threshold": float(threshold or 0.0)} for name, total, reserved, threshold in stock_rows],
        "recommendations_count": int(db.scalar(select(func.count(Recommendation.id)).join(Batch, Batch.id == Recommendation.batch_id).where(Batch.cooperative_id == coop_id)) or 0),
        "ml_prediction_logs_count": int(db.scalar(select(func.count(MLPredictionLog.id))) or 0),
        "ml_recommendation_logs_count": int(db.scalar(select(func.count(MLRecommendationLog.id))) or 0),
        "reference_metrics_count": int(db.scalar(select(func.count(ReferenceMetric.id))) or 0),
        "knowledge_chunks": [
            {"source_id": str(source_id), "crop": str(crop), "topic": str(topic)}
            for source_id, crop, topic in db.execute(
                select(KnowledgeChunk.source_id, KnowledgeChunk.crop, KnowledgeChunk.topic)
                .order_by(desc(KnowledgeChunk.created_at))
                .limit(40)
            ).all()
        ],
        "input_total_qty": float(db.scalar(select(func.coalesce(func.sum(Input.quantity), 0.0)).where(Input.cooperative_id == coop_id)) or 0.0),
    }
    return manager, snapshot


def _build_cases(snapshot: dict[str, Any]) -> list[AuditCase]:
    products = snapshot.get("products", [])
    lots = [item.get("code", "") for item in snapshot.get("lots", []) if item.get("code")]
    stages = [str(item) for item in snapshot.get("stages", []) if item]
    members_code = [item.get("code", "") for item in snapshot.get("members", []) if item.get("code")]
    members_name = [item.get("name", "") for item in snapshot.get("members", []) if item.get("name")]

    p1 = _pick(products, "Mangue", 0)
    p2 = _pick(products, "Mil", 1)
    p3 = _pick(products, "Arachide", 2)
    lot1, lot2, lot3 = _safe_lots(lots)
    stage1 = _pick(stages, "Séchage", 0)
    stage2 = _pick(stages, "Tri", 1)
    stage3 = _pick(stages, "Nettoyage", 2)
    member1 = _pick(members_code, "M-001", 0)
    member_name1 = _pick(members_name, "Ali Sow", 0)

    fake_product = _ensure_fake_value("Papaye", products)
    fake_product2 = _ensure_fake_value("Gombo Rouge", products)
    fake_lot = _ensure_fake_value("LOT-MANG-999", lots)
    fake_lot2 = _ensure_fake_value("LOT-BISS-404", lots)
    fake_member = _ensure_fake_value("Mamadou Diop", [*members_code, *members_name])
    fake_member2 = _ensure_fake_value("Awa Ndiaye", [*members_code, *members_name])
    fake_stage = _ensure_fake_value("Fermentation", stages)
    fake_stage2 = _ensure_fake_value("Fumigation", stages)
    fake_crop = _ensure_fake_value("Niébé lunaire", products)

    cases: list[AuditCase] = []

    def add(
        case_id: str,
        category: str,
        expected: set[str],
        question: str,
        *,
        requires_evidence: bool = False,
        hallucination_trap: bool = False,
        fake_tokens: tuple[str, ...] = (),
        session_key: str | None = None,
        sequence_step: int = 0,
        followup_expected: bool = False,
    ) -> None:
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
                followup_expected=followup_expected,
            )
        )

    # SQL_ONLY paraphrases (unseen)
    add("sql-u-01", "SQL_ONLY", {"SQL_ONLY"}, f"Montre-moi le volume total en stock pour {p1}.")
    add("sql-u-02", "SQL_ONLY", {"SQL_ONLY"}, f"Peux-tu sortir uniquement la quantité réservée de {p1} ?")
    add("sql-u-03", "SQL_ONLY", {"SQL_ONLY"}, f"How much available stock do we still have for {p2}?")
    add("sql-u-04", "SQL_ONLY", {"SQL_ONLY"}, "Donne juste le nombre de lots actuellement actifs.")
    add("sql-u-05", "SQL_ONLY", {"SQL_ONLY"}, f"Etat opérationnel du lot {lot1} (statut uniquement).")
    add("sql-u-06", "SQL_ONLY", {"SQL_ONLY"}, f"Lot {lot2}: current status please.")
    add("sql-u-07", "SQL_ONLY", {"SQL_ONLY"}, f"stock dispnible {p3} stp")
    add("sql-u-08", "SQL_ONLY", {"SQL_ONLY"}, f"Total collecte pour member code {member1}.")
    add("sql-u-09", "SQL_ONLY", {"SQL_ONLY"}, f"Pour {p1}, donne la quantité disponible actuelle uniquement.")

    # RAG_ONLY paraphrases (unseen)
    add("rag-u-01", "RAG_ONLY", {"RAG_ONLY"}, f"Quelles bonnes pratiques post-récolte conseiller pour conserver {p1} plus longtemps ?", requires_evidence=True)
    add("rag-u-02", "RAG_ONLY", {"RAG_ONLY"}, f"Need agronomic references about storage prevention of mold for {p2}.", requires_evidence=True)
    add("rag-u-03", "RAG_ONLY", {"RAG_ONLY"}, f"Donne des sources fiables sur les seuils recommandés d'humidité en {stage1}.", requires_evidence=True)
    add("rag-u-04", "RAG_ONLY", {"RAG_ONLY"}, "Packaging guidance: what reference practices improve conservation?", requires_evidence=True)
    add("rag-u-05", "RAG_ONLY", {"RAG_ONLY"}, "Je veux un rappel benchmark des pertes typiques en post-récolte.", requires_evidence=True)
    add("rag-u-06", "RAG_ONLY", {"RAG_ONLY"}, f"Quelles références agronomiques existent pour la transformation de {p3} ?", requires_evidence=True)
    add("rag-u-07", "RAG_ONLY", {"RAG_ONLY"}, f"Conseils pratiques de tri/nettoyage pour réduire les pertes (avec sources).", requires_evidence=True)

    # HYBRID paraphrases (unseen)
    add("hyb-u-01", "HYBRID", {"HYBRID"}, f"Pourquoi la performance du lot {lot1} semble faible cette semaine, et quelles actions prioriser ?", requires_evidence=True)
    add("hyb-u-02", "HYBRID", {"HYBRID"}, f"Compare {lot1} vs {lot2} sur pertes et efficacité, puis explique les écarts.", requires_evidence=True)
    add("hyb-u-03", "HYBRID", {"HYBRID"}, f"Fais un bilan matière du lot {lot3} et signale les risques associés.", requires_evidence=True)
    add("hyb-u-04", "HYBRID", {"HYBRID"}, f"Explain why losses are high at {stage1} for {p1}, with operational recommendations.", requires_evidence=True)
    add("hyb-u-05", "HYBRID", {"HYBRID"}, f"Détecte les anomalies récentes sur {p2} au stade {stage2} et propose des actions.", requires_evidence=True)
    add("hyb-u-06", "HYBRID", {"HYBRID"}, f"Pourquoi le rendement baisse sur {stage3} pour {p3} aujourd'hui ?", requires_evidence=True)
    add("hyb-u-07", "HYBRID", {"HYBRID"}, "Quels risques opérationnels critiques vois-tu aujourd'hui à l'échelle coopérative ?", requires_evidence=True)
    add("hyb-u-08", "HYBRID", {"HYBRID"}, f"J'ai besoin d'une explication des écarts entre lots actifs et recommandations immédiates.", requires_evidence=True)
    add("hyb-u-09", "HYBRID", {"HYBRID"}, f"Pourquoi les pertes globales varient-elles malgré un stock stable ?", requires_evidence=True)

    # SMALL_TALK unseen
    add("small-u-01", "SMALL_TALK", {"SMALL_TALK"}, "hey")
    add("small-u-02", "SMALL_TALK", {"SMALL_TALK"}, "coucou")
    add("small-u-03", "SMALL_TALK", {"SMALL_TALK"}, "hi")
    add("small-u-04", "SMALL_TALK", {"SMALL_TALK"}, "ca va")
    add("small-u-05", "SMALL_TALK", {"SMALL_TALK"}, "ok merci")

    # UNSUPPORTED unseen
    add("unsup-u-01", "UNSUPPORTED", {"UNSUPPORTED"}, "Quel film me recommandes-tu ce soir ?")
    add("unsup-u-02", "UNSUPPORTED", {"UNSUPPORTED"}, "Qui va gagner la Ligue des Champions cette année ?")
    add("unsup-u-03", "UNSUPPORTED", {"UNSUPPORTED"}, "Should I invest in crypto meme coins this month?")
    add("unsup-u-04", "UNSUPPORTED", {"UNSUPPORTED"}, "Tell me tomorrow weather in Tokyo.")
    add("unsup-u-05", "UNSUPPORTED", {"UNSUPPORTED"}, "Donne-moi une analyse de la politique monétaire US.")

    # Fake-entity traps (>=10 realistic)
    add("fake-u-01", "SQL_ONLY", {"SQL_ONLY"}, f"Quel est le stock actuel de {fake_product} ?", hallucination_trap=True, fake_tokens=(fake_product,))
    add("fake-u-02", "SQL_ONLY", {"SQL_ONLY"}, f"Statut du lot {fake_lot} ?", hallucination_trap=True, fake_tokens=(fake_lot,))
    add("fake-u-03", "SQL_ONLY", {"SQL_ONLY"}, f"Total de collecte pour le producteur {fake_member} ?", hallucination_trap=True, fake_tokens=(fake_member,))
    add("fake-u-04", "HYBRID", {"HYBRID"}, f"Pourquoi les pertes du lot {fake_lot} sont élevées aujourd'hui ?", requires_evidence=True, hallucination_trap=True, fake_tokens=(fake_lot,))
    add("fake-u-05", "SQL_ONLY", {"SQL_ONLY"}, f"Quel est le statut du lot {fake_lot} à l'étape {fake_stage} ?", hallucination_trap=True, fake_tokens=(fake_lot, fake_stage))
    add("fake-u-06", "RAG_ONLY", {"RAG_ONLY"}, f"Quelles références agronomiques pour la culture {fake_crop} ?", requires_evidence=True, hallucination_trap=True, fake_tokens=(fake_crop,))
    add("fake-u-07", "SQL_ONLY", {"SQL_ONLY"}, f"Quel est le stock réservé de {fake_product2} ?", hallucination_trap=True, fake_tokens=(fake_product2,))
    add("fake-u-08", "SQL_ONLY", {"SQL_ONLY"}, f"Quel est le statut du lot {fake_lot2} ?", hallucination_trap=True, fake_tokens=(fake_lot2,))
    add("fake-u-09", "HYBRID", {"HYBRID"}, f"Explique les pertes à l'étape {fake_stage2} cette semaine.", requires_evidence=True, hallucination_trap=True, fake_tokens=(fake_stage2,))
    add("fake-u-10", "SQL_ONLY", {"SQL_ONLY"}, f"Show total collection for farmer {fake_member2}.", hallucination_trap=True, fake_tokens=(fake_member2,))

    # Follow-up chains (>=10 follow-up turns)
    add("seq1-1", "SQL_ONLY", {"SQL_ONLY"}, f"Première vérif: stock dispo {p1}.", session_key="seq-1", sequence_step=1)
    add("seq1-2", "SQL_ONLY", {"SQL_ONLY"}, f"Deuxième vérif: stock dispo pour {p2} ?", session_key="seq-1", sequence_step=2, followup_expected=True)
    add("seq1-3", "SQL_ONLY", {"SQL_ONLY"}, f"Troisième: réservé {p2} ?", session_key="seq-1", sequence_step=3, followup_expected=True)

    add("seq2-1", "HYBRID", {"HYBRID"}, f"Pourquoi {lot1} sous-performe en {stage1} ?", requires_evidence=True, session_key="seq-2", sequence_step=1)
    add("seq2-2", "SMALL_TALK", {"SMALL_TALK"}, "hey", session_key="seq-2", sequence_step=2, followup_expected=True)
    add("seq2-3", "UNSUPPORTED", {"UNSUPPORTED"}, "best movie now?", session_key="seq-2", sequence_step=3, followup_expected=True)

    add("seq3-1", "RAG_ONLY", {"RAG_ONLY"}, f"Quels repères de conservation pour {p1} ?", requires_evidence=True, session_key="seq-3", sequence_step=1)
    add("seq3-2", "RAG_ONLY", {"RAG_ONLY"}, f"Et côté emballage, quelles sources ?", requires_evidence=True, session_key="seq-3", sequence_step=2, followup_expected=True)
    add("seq3-3", "RAG_ONLY", {"RAG_ONLY"}, f"Any benchmark references for storage moisture?", requires_evidence=True, session_key="seq-3", sequence_step=3, followup_expected=True)

    add("seq4-1", "SQL_ONLY", {"SQL_ONLY"}, f"Status lot {lot3}", session_key="seq-4", sequence_step=1)
    add("seq4-2", "HYBRID", {"HYBRID"}, f"Explique l'écart de performance de ce lot et les risques.", requires_evidence=True, session_key="seq-4", sequence_step=2, followup_expected=True)
    add("seq4-3", "SQL_ONLY", {"SQL_ONLY"}, f"ok now give only available stock for {p1}", session_key="seq-4", sequence_step=3, followup_expected=True)

    add("seq5-1", "SQL_ONLY", {"SQL_ONLY"}, f"stock actuel {p3}", session_key="seq-5", sequence_step=1)
    add("seq5-2", "SQL_ONLY", {"SQL_ONLY"}, f"et le total collecte pour {member_name1} ?", session_key="seq-5", sequence_step=2, followup_expected=True)
    add("seq5-3", "HYBRID", {"HYBRID"}, f"pk pertes hautes aujourd'hui sur {stage2} ?", requires_evidence=True, session_key="seq-5", sequence_step=3, followup_expected=True)

    # Guarantee no exact duplicate with first audit
    duplicates = [case.question for case in cases if case.question in FIRST_AUDIT_QUESTIONS]
    if duplicates:
        raise RuntimeError(f"Unseen audit contains duplicated baseline questions: {duplicates}")

    return cases


def _create_chat_session(client: TestClient, title: str) -> str:
    response = client.post("/chat/sessions", json={"title": title})
    if response.status_code != 200:
        raise RuntimeError(f"Failed to create chat session: HTTP {response.status_code} {response.text}")
    return str(response.json()["id"])


def _run_case(client: TestClient, case: AuditCase, session_id: str) -> tuple[dict[str, Any], float]:
    started = datetime.now(UTC)
    try:
        response = client.post(
            "/chat",
            json={"session_id": session_id, "message": case.question, "top_k": 4},
            timeout=15,
        )
    except Exception as exc:
        response = None
    latency_ms = (datetime.now(UTC) - started).total_seconds() * 1000.0
    if response is None:
        payload = {
            "success": False,
            "message": "HTTP timeout/error while calling /chat endpoint.",
            "mode": "http_error",
            "citations": [],
            "context_metrics": [],
            "ui_blocks": [],
        }
    elif response.status_code != 200:
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


def _evaluate_case(case: AuditCase, payload: dict[str, Any]) -> dict[str, Any]:
    answer_text = str(payload.get("message", "") or "")
    actual_intent = _actual_intent(payload)
    citations = list(payload.get("citations", []))
    ui_blocks = list(payload.get("ui_blocks", []))
    context_metrics = list(payload.get("context_metrics", []))
    evidence_missing = _evidence_missing_message(answer_text)
    raw_json_visible = _raw_json_visible(answer_text, ui_blocks)
    technical_visible, technical_hits = _technical_labels_visible(answer_text, ui_blocks)
    sql_used = _used_sql(payload)
    rag_used = _used_rag(payload)
    hallucination_risk, hallucination_note = _hallucination_risk(case, answer_text, actual_intent)

    notes: list[str] = []
    checks: list[bool] = []

    intent_ok = actual_intent in case.expected_intents
    checks.append(intent_ok)
    if not intent_ok:
        notes.append(f"Intent mismatch: expected {sorted(case.expected_intents)} got {actual_intent}.")

    if case.category == "SMALL_TALK":
        checks.extend([not sql_used, not rag_used, len(citations) == 0, len(ui_blocks) == 0, len(context_metrics) == 0])
        if _contains_any(answer_text, SMALL_TALK_FORBIDDEN_TOKENS):
            checks.append(False)
            notes.append("Small-talk leaked operational analysis.")
    elif case.category == "UNSUPPORTED":
        checks.extend([not sql_used, not rag_used, len(citations) == 0, len(ui_blocks) == 0, len(context_metrics) == 0])
        if _contains_any(answer_text, UNSUPPORTED_FORBIDDEN_TOKENS):
            checks.append(False)
            notes.append("Unsupported answer leaked cooperative analysis.")
    elif case.category == "SQL_ONLY":
        titles = {str(item.get("title", "")) for item in ui_blocks if isinstance(item, dict)}
        checks.extend([sql_used, not rag_used, len(citations) == 0, len(SQL_ONLY_FORBIDDEN_BLOCKS & titles) == 0])
        if len(SQL_ONLY_FORBIDDEN_BLOCKS & titles) > 0:
            notes.append("SQL_ONLY contains unrelated executive blocks.")
    elif case.category == "RAG_ONLY":
        checks.append(rag_used)
        if case.requires_evidence:
            checks.append(len(citations) > 0 or evidence_missing)
            if not (len(citations) > 0 or evidence_missing):
                notes.append("RAG_ONLY lacks citations and missing-data disclaimer.")
    elif case.category == "HYBRID":
        checks.extend([sql_used, rag_used])
        if case.requires_evidence:
            checks.append(len(citations) > 0 or evidence_missing)
            if not (len(citations) > 0 or evidence_missing):
                notes.append("HYBRID lacks citations and missing-data disclaimer.")

    if case.hallucination_trap and hallucination_risk == "high":
        checks.append(False)
        notes.append("High hallucination risk on fake entity.")

    if case.followup_expected and _contains_any(answer_text, FOLLOWUP_CONTEXT_FAIL_MARKERS):
        checks.append(False)
        notes.append("Follow-up appears to lose context (clarification fallback).")

    checks.extend([not raw_json_visible, not technical_visible])
    if raw_json_visible:
        notes.append("Raw JSON visible in manager-facing answer.")
    if technical_visible:
        notes.append(f"Debug labels leaked: {technical_hits}")

    passed = all(checks)
    if not notes and passed:
        notes.append("All checks passed.")

    return {
        "case_id": case.case_id,
        "category": case.category,
        "question": case.question,
        "expected_intent": sorted(case.expected_intents),
        "actual_intent": actual_intent,
        "pass": passed,
        "answer_text": answer_text,
        "answer_snippet": answer_text[:220].replace("\n", " ").strip(),
        "citations_count": len(citations),
        "hallucination_risk": hallucination_risk,
        "hallucination_note": hallucination_note,
        "raw_json_visible": raw_json_visible,
        "technical_labels_visible": technical_visible,
        "technical_labels": technical_hits,
        "requires_evidence": case.requires_evidence,
        "hallucination_trap": case.hallucination_trap,
        "session_key": case.session_key,
        "sequence_step": case.sequence_step,
        "followup_expected": case.followup_expected,
        "notes": notes,
        "mode": str(payload.get("mode", "")),
        "ui_blocks_count": len(ui_blocks),
        "context_metrics_count": len(context_metrics),
        "response_payload": payload,
    }


def _compute_stale_and_followup_risks(results: list[dict[str, Any]]) -> None:
    by_session: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        key = str(row.get("session_key") or row.get("case_id"))
        by_session.setdefault(key, []).append(row)

    for key, rows in by_session.items():
        rows.sort(key=lambda r: int(r.get("sequence_step", 0)))
        for idx, row in enumerate(rows):
            stale_risk = "low"
            if idx > 0:
                prev = rows[idx - 1]
                if row["category"] in {"SMALL_TALK", "UNSUPPORTED"}:
                    if row.get("citations_count", 0) > 0 or row.get("ui_blocks_count", 0) > 0 or row.get("context_metrics_count", 0) > 0:
                        stale_risk = "high"
                        row["pass"] = False
                        row["notes"].append("Stale response risk: previous operational payload leaked.")
            row["stale_response_risk"] = stale_risk
            row["debug_leakage_risk"] = "high" if (row.get("raw_json_visible") or row.get("technical_labels_visible")) else "low"


def _summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for row in results if row["pass"])

    by_intent: dict[str, dict[str, int]] = {}
    for row in results:
        intent = row["category"]
        slot = by_intent.setdefault(intent, {"total": 0, "pass": 0})
        slot["total"] += 1
        if row["pass"]:
            slot["pass"] += 1

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
    }


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Chatbot Unseen Robustness Audit",
        "",
        "## Overview",
        f"- Generated at: {report['generated_at']}",
        f"- Total unseen questions: {summary['total_cases']}",
        f"- Overall pass rate: {summary['overall_pass_rate']}",
        "",
        "## Pass Rate by Intent",
    ]
    for intent, values in summary["pass_rate_by_intent"].items():
        lines.append(f"- {intent}: {values['pass']}/{values['total']} ({values['rate']})")

    lines.extend(["", "## Acceptance Targets"])
    targets = report["acceptance_targets"]
    for key, value in targets.items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Test Results"])
    for row in report["results"]:
        lines.extend(
            [
                f"- `{row['case_id']}` [{row['category']}] {row['question']}",
                f"  - expected/actual: {row['expected_intent']} -> {row['actual_intent']} | pass={row['pass']}",
                f"  - snippet: {row['answer_snippet']}",
                f"  - citations={row['citations_count']} hallucination_risk={row['hallucination_risk']} stale_risk={row['stale_response_risk']} debug_risk={row['debug_leakage_risk']}",
                f"  - notes: {'; '.join(row['notes'])}",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    manager: User | None = None
    conn = None
    outer_tx = None
    audit_session = None

    try:
        manager, snapshot = _build_snapshot(db)
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

        cases = _build_cases(snapshot)
        if len(cases) < 60:
            raise RuntimeError(f"Expected at least 60 unseen cases, got {len(cases)}.")

        followup_turns = sum(1 for case in cases if case.sequence_step > 1)
        fake_traps = sum(1 for case in cases if case.hallucination_trap)
        if followup_turns < 10:
            raise RuntimeError(f"Expected at least 10 follow-up turns, got {followup_turns}.")
        if fake_traps < 10:
            raise RuntimeError(f"Expected at least 10 fake-entity traps, got {fake_traps}.")

        session_cache: dict[str, str] = {}
        results: list[dict[str, Any]] = []
        for case in cases:
            session_key = case.session_key or case.case_id
            if session_key not in session_cache:
                session_cache[session_key] = _create_chat_session(client, f"Unseen Robustness - {session_key}")
            payload, latency_ms = _run_case(client, case, session_cache[session_key])
            row = _evaluate_case(case, payload)
            row["latency_ms"] = round(latency_ms, 3)
            results.append(row)

        _compute_stale_and_followup_risks(results)
        summary = _summarize(results)
        by_intent = summary["pass_rate_by_intent"]

        acceptance_targets = {
            "overall >= 85%": summary["overall_pass_rate"] >= 0.85,
            "SQL_ONLY >= 90%": (by_intent.get("SQL_ONLY", {}).get("rate", 0.0) >= 0.9),
            "RAG_ONLY >= 80%": (by_intent.get("RAG_ONLY", {}).get("rate", 0.0) >= 0.8),
            "HYBRID >= 80%": (by_intent.get("HYBRID", {}).get("rate", 0.0) >= 0.8),
            "SMALL_TALK = 100%": (by_intent.get("SMALL_TALK", {}).get("rate", 0.0) == 1.0),
            "UNSUPPORTED = 100%": (by_intent.get("UNSUPPORTED", {}).get("rate", 0.0) == 1.0),
            "at least 60 unseen questions": len(cases) >= 60,
            "at least 10 follow-up turns": followup_turns >= 10,
            "at least 10 fake-entity traps": fake_traps >= 10,
        }

        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "snapshot": snapshot,
            "summary": summary,
            "results": results,
            "acceptance_targets": acceptance_targets,
            "metadata": {
                "case_count": len(cases),
                "follow_up_turns": followup_turns,
                "fake_trap_count": fake_traps,
            },
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

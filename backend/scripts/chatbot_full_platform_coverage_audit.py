from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import ast
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
from app.models.commercial_invoice import CommercialInvoice
from app.models.commercial_order import CommercialOrder
from app.models.enums import UserRole
from app.models.farmer_advance import FarmerAdvance
from app.models.global_charge import GlobalCharge
from app.models.input import Input
from app.models.member import Member
from app.models.ml import MLPredictionLog
from app.models.parcel import Parcel
from app.models.pre_harvest_step import PreHarvestStep
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.reference import KnowledgeChunk, ReferenceMetric
from app.models.stock import Stock
from app.models.treasury_transaction import TreasuryTransaction
from app.models.user import User

REPORT_DIR = ROOT_DIR / "reports"
JSON_REPORT = REPORT_DIR / "chatbot_full_platform_coverage_audit.json"
MD_REPORT = REPORT_DIR / "chatbot_full_platform_coverage_audit.md"

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
    "je ne trouve pas cette donnée",
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
    "lots actifs",
    "stock disponible",
    "cooperative",
}

SQL_ONLY_FORBIDDEN_BLOCKS = {
    "Risques critiques",
    "Risques détectés",
    "Niveau de confiance",
    "Actions recommandées",
    "Analyse opérationnelle",
    "Sources et justification",
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

SQL_DOMAIN_TO_MODULE = {
    "stocks": "stocks",
    "inputs": "collections",
    "batches": "lots",
    "process_steps": "process",
    "losses": "process",
    "members": "members",
    "parcels": "parcels",
    "pre_harvest": "parcels",
    "recommendations": "recommendations",
    "treasury": "finance",
    "farmer_advances": "finance",
    "commercial_orders": "orders",
    "commercial_invoices": "invoices",
    "ml_metrics": "ml",
    "dashboard": "dashboard",
}

REQUIRED_MODULES = [
    "members",
    "parcels",
    "collections",
    "stocks",
    "lots",
    "process",
    "recommendations",
    "ml",
    "orders",
    "invoices",
    "finance",
    "reference",
]


@dataclass
class AuditCase:
    case_id: str
    category: str
    module: str
    expected_intents: set[str]
    question: str
    requires_evidence: bool = False
    hallucination_trap: bool = False
    fake_tokens: tuple[str, ...] = ()
    session_key: str | None = None
    sequence_step: int = 0
    followup_expected: bool = False
    allow_missing_data: bool = False


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


def _safe_tuple(values: list[str], fallbacks: tuple[str, ...]) -> tuple[str, ...]:
    out = []
    for idx, fallback in enumerate(fallbacks):
        out.append(_pick(values, fallback, idx))
    return tuple(out)


def _ensure_fake_value(base: str, existing: Iterable[str]) -> str:
    existing_l = {str(item).strip().lower() for item in existing if item}
    if base.lower() not in existing_l:
        return base
    suffix = 901
    while f"{base}-{suffix}".lower() in existing_l:
        suffix += 1
    return f"{base}-{suffix}"


def _pick_preferred_product(values: list[str], preferred: str, fallback: str) -> str:
    preferred_l = preferred.lower()
    for value in values:
        if str(value).strip().lower() == preferred_l:
            return str(value)
    return _pick(values, fallback, 0)


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
    members = db.execute(
        select(Member.code, Member.full_name)
        .where(Member.cooperative_id == coop_id)
        .order_by(Member.created_at.desc())
        .limit(40)
    ).all()
    parcels = db.execute(
        select(Parcel.name, Parcel.main_culture, Member.code, Member.full_name)
        .join(Member, Member.id == Parcel.member_id)
        .where(Parcel.cooperative_id == coop_id)
        .order_by(Parcel.created_at.desc())
        .limit(40)
    ).all()
    lots = db.execute(
        select(Batch.code, Batch.status, Product.name)
        .join(Product, Product.id == Batch.product_id)
        .where(Batch.cooperative_id == coop_id)
        .order_by(Batch.creation_date.desc())
        .limit(40)
    ).all()
    stages = [
        str(item[0])
        for item in db.execute(
            select(ProcessStep.type, func.count(ProcessStep.id))
            .join(Batch, Batch.id == ProcessStep.batch_id)
            .where(Batch.cooperative_id == coop_id)
            .group_by(ProcessStep.type)
            .order_by(func.count(ProcessStep.id).desc())
        ).all()
        if item[0]
    ]
    orders = [
        str(row[0])
        for row in db.execute(
            select(CommercialOrder.order_number)
            .where(CommercialOrder.cooperative_id == coop_id)
            .order_by(CommercialOrder.created_at.desc())
            .limit(40)
        ).all()
        if row[0]
    ]
    invoices = [
        str(row[0])
        for row in db.execute(
            select(CommercialInvoice.invoice_number)
            .where(CommercialInvoice.cooperative_id == coop_id)
            .order_by(CommercialInvoice.created_at.desc())
            .limit(40)
        ).all()
        if row[0]
    ]

    module_data_counts = {
        "members": int(db.scalar(select(func.count(Member.id)).where(Member.cooperative_id == coop_id)) or 0),
        "parcels": int(db.scalar(select(func.count(Parcel.id)).where(Parcel.cooperative_id == coop_id)) or 0),
        "collections": int(db.scalar(select(func.count(Input.id)).where(Input.cooperative_id == coop_id)) or 0),
        "stocks": int(db.scalar(select(func.count(Stock.id)).where(Stock.cooperative_id == coop_id)) or 0),
        "lots": int(db.scalar(select(func.count(Batch.id)).where(Batch.cooperative_id == coop_id)) or 0),
        "process": int(
            db.scalar(
                select(func.count(ProcessStep.id)).join(Batch, Batch.id == ProcessStep.batch_id).where(Batch.cooperative_id == coop_id)
            )
            or 0
        ),
        "recommendations": int(
            db.scalar(
                select(func.count(Recommendation.id)).join(Batch, Batch.id == Recommendation.batch_id).where(Batch.cooperative_id == coop_id)
            )
            or 0
        ),
        "orders": int(db.scalar(select(func.count(CommercialOrder.id)).where(CommercialOrder.cooperative_id == coop_id)) or 0),
        "invoices": int(db.scalar(select(func.count(CommercialInvoice.id)).where(CommercialInvoice.cooperative_id == coop_id)) or 0),
        "finance": int(
            (db.scalar(select(func.count(GlobalCharge.id)).where(GlobalCharge.cooperative_id == coop_id)) or 0)
            + (db.scalar(select(func.count(FarmerAdvance.id)).where(FarmerAdvance.cooperative_id == coop_id)) or 0)
            + (db.scalar(select(func.count(TreasuryTransaction.id)).where(TreasuryTransaction.cooperative_id == coop_id)) or 0)
        ),
        "ml": int(db.scalar(select(func.count(MLPredictionLog.id))) or 0),
        "reference": int(db.scalar(select(func.count(KnowledgeChunk.id))) or 0) + int(db.scalar(select(func.count(ReferenceMetric.id))) or 0),
    }

    snapshot = {
        "generated_at": datetime.now(UTC).isoformat(),
        "cooperative_id": str(coop_id),
        "manager_user_id": str(manager.id),
        "products": products,
        "members": [{"code": str(code), "name": str(name)} for code, name in members],
        "parcels": [{"name": str(name), "culture": str(culture), "member_code": str(code), "member_name": str(member_name)} for name, culture, code, member_name in parcels],
        "lots": [{"code": str(code), "status": str(status.value if hasattr(status, "value") else status), "product": str(product)} for code, status, product in lots],
        "stages": stages,
        "orders": orders,
        "invoices": invoices,
        "module_data_counts": module_data_counts,
    }
    return manager, snapshot


def _build_cases(snapshot: dict[str, Any]) -> list[AuditCase]:
    products = [str(item) for item in snapshot.get("products", []) if item]
    members = snapshot.get("members", [])
    member_codes = [str(item.get("code")) for item in members if item.get("code")]
    member_names = [str(item.get("name")) for item in members if item.get("name")]
    parcels = snapshot.get("parcels", [])
    parcel_names = [str(item.get("name")) for item in parcels if item.get("name")]
    parcel_cultures = [str(item.get("culture")) for item in parcels if item.get("culture")]
    lots = [str(item.get("code")) for item in snapshot.get("lots", []) if item.get("code")]
    stages = [str(item) for item in snapshot.get("stages", []) if item]
    orders = [str(item) for item in snapshot.get("orders", []) if item]
    invoices = [str(item) for item in snapshot.get("invoices", []) if item]

    p1 = _pick_preferred_product(products, "Mangue", "Mangue")
    p2 = _pick_preferred_product(products, "Mil", "Mil")
    p3 = _pick_preferred_product(products, "Arachide", "Arachide")
    m1, m2, m3 = _safe_tuple(member_codes, ("DEMOFP-M-001", "DEMOFP-M-002", "DEMOFP-M-003"))
    mn1 = _pick(member_names, "Mamadou Diallo", 0)
    pr1, pr2 = _safe_tuple(parcel_names, ("PARCELLE-DEMO-01", "PARCELLE-DEMO-02"))
    culture1 = _pick(parcel_cultures, "Mangue", 0)
    lot1, lot2, lot3 = _safe_tuple(lots, ("DEMOFP-LOT-MANG-001", "DEMOFP-LOT-BISS-001", "DEMOFP-LOT-MIL-001"))
    st1, st2 = _safe_tuple(stages, ("Séchage", "Tri"))
    ord1, ord2 = _safe_tuple(orders, ("DEMOFP-ORD-001", "DEMOFP-ORD-002"))
    inv1, inv2 = _safe_tuple(invoices, ("DEMOFP-INV-001", "DEMOFP-INV-002"))

    fake_member = _ensure_fake_value("MEMBER_FAKE_7102", [*member_codes, *member_names])
    fake_parcel = _ensure_fake_value("PARCELLE_FAKE_8301", parcel_names)
    fake_order = _ensure_fake_value("ORD-FAKE-5501", orders)
    fake_invoice = _ensure_fake_value("INV_FAKE_4409", invoices)
    fake_lot = _ensure_fake_value("LOT_FAKE_7456", lots)
    fake_product = _ensure_fake_value("FAKE_PRODUCT_9619", products)
    fake_stage = _ensure_fake_value("STAGE_FAKE_8126", stages)

    cases: list[AuditCase] = []

    def add(
        case_id: str,
        category: str,
        module: str,
        expected: set[str],
        question: str,
        *,
        requires_evidence: bool = False,
        hallucination_trap: bool = False,
        fake_tokens: tuple[str, ...] = (),
        session_key: str | None = None,
        sequence_step: int = 0,
        followup_expected: bool = False,
        allow_missing_data: bool = False,
    ) -> None:
        cases.append(
            AuditCase(
                case_id=case_id,
                category=category,
                module=module,
                expected_intents=expected,
                question=question,
                requires_evidence=requires_evidence,
                hallucination_trap=hallucination_trap,
                fake_tokens=fake_tokens,
                session_key=session_key,
                sequence_step=sequence_step,
                followup_expected=followup_expected,
                allow_missing_data=allow_missing_data,
            )
        )

    # 1. Members/farmers
    add("mem-01", "SQL_ONLY", "members", {"SQL_ONLY"}, "Liste les membres actifs de la coopérative.")
    add("mem-02", "SQL_ONLY", "members", {"SQL_ONLY"}, f"Donne les détails du membre {m1}.")
    add("mem-03", "SQL_ONLY", "members", {"SQL_ONLY"}, f"Total de collecte du membre {m1}.")
    add("mem-04", "SQL_ONLY", "members", {"SQL_ONLY"}, f"Quelles parcelles pour le membre {m2} ?")
    add("mem-05", "SQL_ONLY", "members", {"SQL_ONLY"}, f"Montant des avances actives du membre {m2}.")
    add("mem-06", "SQL_ONLY", "members", {"SQL_ONLY"}, f"member details for {m3}")
    add("mem-07", "SQL_ONLY", "members", {"SQL_ONLY"}, f"collection totale du producteur {mn1}")
    add("mem-08", "SQL_ONLY", "members", {"SQL_ONLY"}, f"Parcelles et cultures du membre {m1}")

    # 2. Parcels/cultures
    add("par-01", "SQL_ONLY", "parcels", {"SQL_ONLY"}, f"Parcelles du membre {m1}.")
    add("par-02", "SQL_ONLY", "parcels", {"SQL_ONLY"}, f"Parcelles du membre {m1}")
    add("par-03", "SQL_ONLY", "parcels", {"SQL_ONLY"}, f"surface parcelles du membre {m1}", allow_missing_data=True)
    add("par-04", "SQL_ONLY", "parcels", {"SQL_ONLY"}, f"Parcelles et cultures du membre {m2}")
    add("par-05", "SQL_ONLY", "parcels", {"SQL_ONLY"}, f"Give parcel list for member {m2}")
    add("par-06", "SQL_ONLY", "parcels", {"SQL_ONLY"}, f"Parcelles du membre {m3}")

    # 3. Collections/inputs
    add("col-01", "SQL_ONLY", "collections", {"SQL_ONLY"}, f"Total collecté pour le produit {p1}.")
    add("col-02", "SQL_ONLY", "collections", {"SQL_ONLY"}, f"Total de collecte du membre {m2}.")
    add("col-03", "SQL_ONLY", "collections", {"SQL_ONLY"}, "Total collecté par produit")
    add("col-04", "HYBRID", "collections", {"HYBRID"}, "Distribution des grades de collecte")
    add("col-05", "SQL_ONLY", "collections", {"SQL_ONLY"}, f"total collecte pour {p2} ce mois", allow_missing_data=True)
    add("col-06", "SQL_ONLY", "collections", {"SQL_ONLY"}, f"Total collecté pour le produit {p3}.", allow_missing_data=True)

    # 4. Stocks
    add("stk-01", "SQL_ONLY", "stocks", {"SQL_ONLY"}, f"Quel est le stock actuel de {p1} ?")
    add("stk-02", "SQL_ONLY", "stocks", {"SQL_ONLY"}, f"stock réservé de {p1}")
    add("stk-03", "SQL_ONLY", "stocks", {"SQL_ONLY"}, f"stock disponible de {p2}", allow_missing_data=True)
    add("stk-04", "SQL_ONLY", "stocks", {"SQL_ONLY"}, f"low-stock alert sur {p3}")
    add("stk-05", "SQL_ONLY", "stocks", {"SQL_ONLY"}, f"stock disponible {p1}")
    add("stk-06", "SQL_ONLY", "stocks", {"SQL_ONLY"}, f"stock actuel {p2}, juste les faits", allow_missing_data=True)

    # 5. Lots/process
    add("lot-01", "SQL_ONLY", "lots", {"SQL_ONLY"}, f"Quel est le statut du lot {lot1} ?")
    add("lot-02", "SQL_ONLY", "lots", {"SQL_ONLY"}, "Combien de lots actifs ?")
    add("lot-03", "HYBRID", "lots", {"HYBRID"}, "Combien de lots complétés ?")
    add("lot-04", "HYBRID", "process", {"HYBRID"}, "Pertes moyennes par étape")
    add("lot-05", "HYBRID", "process", {"HYBRID"}, "bilan matière global des étapes")
    add("lot-06", "SQL_ONLY", "lots", {"SQL_ONLY"}, f"status lot {lot2}")
    add("lot-07", "HYBRID", "process", {"HYBRID"}, f"loss by stage for {st1}", allow_missing_data=True)
    add("lot-08", "SQL_ONLY", "lots", {"SQL_ONLY"}, f"lot status {lot3} and current quantity")

    # 6. Recommendations
    add("rec-01", "HYBRID", "recommendations", {"HYBRID"}, "Recommandations actives")
    add("rec-02", "HYBRID", "recommendations", {"HYBRID"}, f"Recommandations pour {p1}")
    add("rec-03", "HYBRID", "recommendations", {"HYBRID"}, f"recommendations by lot {lot1}")
    add("rec-04", "HYBRID", "recommendations", {"HYBRID"}, "priority recommendations")
    add("rec-05", "HYBRID", "recommendations", {"HYBRID"}, "statut feedback des recommandations")
    add("rec-06", "HYBRID", "recommendations", {"HYBRID"}, f"Pourquoi les recommandations sur {lot2} restent prioritaires et quelles actions immédiates ?", requires_evidence=True)

    # 7. Commercialisation/orders
    add("ord-01", "SQL_ONLY", "orders", {"SQL_ONLY"}, "Statut des commandes", allow_missing_data=True)
    add("ord-02", "SQL_ONLY", "orders", {"SQL_ONLY"}, f"Statut de la commande {ord1}")
    add("ord-03", "SQL_ONLY", "orders", {"SQL_ONLY"}, f"Statut de la commande {ord2}")
    add("ord-04", "SQL_ONLY", "orders", {"SQL_ONLY"}, "statut commandes ouvertes", allow_missing_data=True)
    add("ord-05", "HYBRID", "orders", {"HYBRID"}, f"Risque commercial: commande {ord1} vs stock disponible, explique les écarts.", requires_evidence=True)
    add("ord-06", "SQL_ONLY", "orders", {"SQL_ONLY"}, f"Statut de la commande {ord1}")

    # 8. Factures/invoices
    add("inv-01", "SQL_ONLY", "invoices", {"SQL_ONLY"}, "Statut des factures", allow_missing_data=True)
    add("inv-02", "SQL_ONLY", "invoices", {"SQL_ONLY"}, "invoice status summary", allow_missing_data=True)
    add("inv-03", "SQL_ONLY", "invoices", {"SQL_ONLY"}, "statut des factures payées", allow_missing_data=True)
    add("inv-04", "SQL_ONLY", "invoices", {"SQL_ONLY"}, f"Statut de la facture {inv1}")
    add("inv-05", "SQL_ONLY", "invoices", {"SQL_ONLY"}, f"invoice status {inv2}")
    add("inv-06", "SQL_ONLY", "invoices", {"SQL_ONLY"}, "statut et montants factures", allow_missing_data=True)

    # 9. Finance
    add("fin-01", "SQL_ONLY", "finance", {"SQL_ONLY"}, "Total des charges")
    add("fin-02", "SQL_ONLY", "finance", {"SQL_ONLY"}, "Charges par catégorie")
    add("fin-03", "SQL_ONLY", "finance", {"SQL_ONLY"}, f"Montant des avances actives du membre {m1}")
    add("fin-04", "SQL_ONLY", "finance", {"SQL_ONLY"}, "Solde trésorerie actuel")
    add("fin-05", "SQL_ONLY", "finance", {"SQL_ONLY"}, "revenus et dépenses de trésorerie")
    add("fin-06", "HYBRID", "finance", {"HYBRID"}, f"Impact des coûts logistiques sur l'efficacité de {st1}, avec actions.", requires_evidence=True)

    # 10. ML
    add("ml-01", "SQL_ONLY", "ml", {"SQL_ONLY"}, "Dernière prédiction ML")
    add("ml-02", "SQL_ONLY", "ml", {"SQL_ONLY"}, "latest risk predictions")
    add("ml-03", "SQL_ONLY", "ml", {"SQL_ONLY"}, "anomaly prediction récente")
    add("ml-04", "HYBRID", "ml", {"HYBRID"}, f"Croise la dernière prédiction de risque et les pertes observées sur {lot1}.", requires_evidence=True)
    add("ml-05", "HYBRID", "ml", {"HYBRID"}, "Explique les signaux ML à haut risque et leurs implications opérationnelles.", requires_evidence=True)
    add("ml-06", "SQL_ONLY", "ml", {"SQL_ONLY"}, "Dernière prédiction ML")

    # 11. RAG/reference
    add("rag-01", "RAG_ONLY", "reference", {"RAG_ONLY"}, f"Quelles bonnes pratiques de séchage pour {p1} ?", requires_evidence=True)
    add("rag-02", "RAG_ONLY", "reference", {"RAG_ONLY"}, "Quels benchmarks de pertes pour le mil ?", requires_evidence=True)
    add("rag-03", "RAG_ONLY", "reference", {"RAG_ONLY"}, "Conseils post-récolte pour la conservation avec sources", requires_evidence=True)
    add("rag-04", "RAG_ONLY", "reference", {"RAG_ONLY"}, "Bonnes pratiques d'emballage pour limiter l'humidité", requires_evidence=True)
    add("rag-05", "RAG_ONLY", "reference", {"RAG_ONLY"}, "références sur le contrôle d'humidité/moisture", requires_evidence=True)
    add("rag-06", "RAG_ONLY", "reference", {"RAG_ONLY"}, f"Best practices for {culture1} post-harvest storage", requires_evidence=True)
    add("rag-07", "RAG_ONLY", "reference", {"RAG_ONLY"}, "sources agronomiques sur prévention des pertes", requires_evidence=True)
    add("rag-08", "RAG_ONLY", "reference", {"RAG_ONLY"}, "guidance de tri et nettoyage avec sources", requires_evidence=True)

    # 12. HYBRID full-platform reasoning
    add("hyb-01", "HYBRID", "hybrid", {"HYBRID"}, f"Compare la performance des lots {lot1} et {lot2} et explique les écarts.", requires_evidence=True)
    add("hyb-02", "HYBRID", "hybrid", {"HYBRID"}, f"Fais un bilan matière du lot {lot1} avec les risques associés.", requires_evidence=True)
    add("hyb-03", "HYBRID", "hybrid", {"HYBRID"}, f"Pourquoi les pertes sont élevées au stade {st1} pour {p1} ?", requires_evidence=True)
    add("hyb-04", "HYBRID", "hybrid", {"HYBRID"}, f"Risque stock+commande: {p1} face aux commandes ouvertes, que faire ?", requires_evidence=True, allow_missing_data=True)
    add("hyb-05", "HYBRID", "hybrid", {"HYBRID"}, f"Relie approvisionnement membre {m1} et risque sur lot {lot3}.", requires_evidence=True)
    add("hyb-06", "HYBRID", "hybrid", {"HYBRID"}, f"Recommandations + tendance pertes: où prioriser pour {p3} ?", requires_evidence=True)
    add("hyb-07", "HYBRID", "hybrid", {"HYBRID"}, "Analyse risque commercial + rupture stock + actions", requires_evidence=True)
    add("hyb-08", "HYBRID", "hybrid", {"HYBRID"}, f"Explique l'impact des charges et coûts sur l'efficacité du {st1}.", requires_evidence=True, allow_missing_data=True)
    add("hyb-09", "HYBRID", "hybrid", {"HYBRID"}, "Explique les anomalies opérationnelles récentes sur les lots actifs.", requires_evidence=True, allow_missing_data=True)
    add("hyb-10", "HYBRID", "hybrid", {"HYBRID"}, "Pourquoi les risques critiques opérationnels augmentent aujourd'hui ?", requires_evidence=True, allow_missing_data=True)

    # 13. Fake entity traps
    add("fake-01", "SQL_ONLY", "members", {"SQL_ONLY"}, f"Total collecte du membre {fake_member}", hallucination_trap=True, fake_tokens=(fake_member,))
    add("fake-02", "SQL_ONLY", "parcels", {"SQL_ONLY", "CLARIFICATION_NEEDED"}, f"Surface de la parcelle {fake_parcel}", hallucination_trap=True, fake_tokens=(fake_parcel,))
    add("fake-03", "SQL_ONLY", "orders", {"SQL_ONLY"}, f"Statut commande {fake_order}", hallucination_trap=True, fake_tokens=(fake_order,))
    add("fake-04", "SQL_ONLY", "invoices", {"SQL_ONLY"}, f"Statut facture {fake_invoice}", hallucination_trap=True, fake_tokens=(fake_invoice,))
    add("fake-05", "SQL_ONLY", "lots", {"SQL_ONLY"}, f"Statut du lot {fake_lot}", hallucination_trap=True, fake_tokens=(fake_lot,))
    add("fake-06", "SQL_ONLY", "stocks", {"SQL_ONLY"}, f"Stock actuel de {fake_product}", hallucination_trap=True, fake_tokens=(fake_product,))
    add("fake-07", "HYBRID", "hybrid", {"HYBRID"}, f"Pourquoi les pertes sont hautes au stage {fake_stage} ?", requires_evidence=True, hallucination_trap=True, fake_tokens=(fake_stage,))
    add("fake-08", "HYBRID", "hybrid", {"HYBRID"}, f"Analyse le lot {fake_lot} et donne les risques", requires_evidence=True, hallucination_trap=True, fake_tokens=(fake_lot,))
    add("fake-09", "RAG_ONLY", "reference", {"RAG_ONLY"}, f"Références agronomiques pour {fake_product}", requires_evidence=True, hallucination_trap=True, fake_tokens=(fake_product,))
    add("fake-10", "SQL_ONLY", "members", {"SQL_ONLY"}, f"Avances du producteur {fake_member}", hallucination_trap=True, fake_tokens=(fake_member,))
    add("fake-11", "SQL_ONLY", "orders", {"SQL_ONLY"}, f"pending delivery for order {fake_order}", hallucination_trap=True, fake_tokens=(fake_order,))
    add("fake-12", "SQL_ONLY", "invoices", {"SQL_ONLY"}, f"overdue invoice {fake_invoice}", hallucination_trap=True, fake_tokens=(fake_invoice,))

    # 14. Follow-up chains (12 turns)
    add("seq1-1", "SQL_ONLY", "members", {"SQL_ONLY"}, f"Donne les détails du membre {m1}", session_key="seq-1", sequence_step=1)
    add("seq1-2", "SQL_ONLY", "collections", {"SQL_ONLY"}, f"et la collecte totale du membre {m1} ?", session_key="seq-1", sequence_step=2, followup_expected=True)
    add("seq1-3", "SQL_ONLY", "parcels", {"SQL_ONLY"}, f"et les parcelles du membre {m1} ?", session_key="seq-1", sequence_step=3, followup_expected=True)

    add("seq2-1", "SQL_ONLY", "orders", {"SQL_ONLY"}, f"Statut commande {ord1}", session_key="seq-2", sequence_step=1)
    add("seq2-2", "SQL_ONLY", "stocks", {"SQL_ONLY"}, f"stock disponible pour {p1} lié à cette commande ?", session_key="seq-2", sequence_step=2, followup_expected=True)
    add("seq2-3", "HYBRID", "hybrid", {"HYBRID"}, "pourquoi le risque opérationnel augmenterait si cette commande augmente de 20% ?", requires_evidence=True, session_key="seq-2", sequence_step=3, followup_expected=True, allow_missing_data=True)

    add("seq3-1", "SQL_ONLY", "lots", {"SQL_ONLY"}, f"Statut du lot {lot2}", session_key="seq-3", sequence_step=1)
    add("seq3-2", "HYBRID", "recommendations", {"HYBRID"}, f"et les recommandations associées au lot {lot2} ?", session_key="seq-3", sequence_step=2, followup_expected=True)
    add("seq3-3", "HYBRID", "finance", {"HYBRID"}, f"impact commercial et financier du lot {lot2} ?", requires_evidence=True, session_key="seq-3", sequence_step=3, followup_expected=True, allow_missing_data=True)

    add("seq4-1", "HYBRID", "hybrid", {"HYBRID"}, f"Compare {lot1} et {lot3} sur pertes/efficacité", requires_evidence=True, session_key="seq-4", sequence_step=1)
    add("seq4-2", "SMALL_TALK", "small_talk", {"SMALL_TALK"}, "hello", session_key="seq-4", sequence_step=2, followup_expected=True)
    add("seq4-3", "UNSUPPORTED", "unsupported", {"UNSUPPORTED"}, "best movie this week?", session_key="seq-4", sequence_step=3, followup_expected=True)

    # 15. Small talk and unsupported
    add("st-01", "SMALL_TALK", "small_talk", {"SMALL_TALK"}, "bonjour")
    add("st-02", "SMALL_TALK", "small_talk", {"SMALL_TALK"}, "merci")
    add("st-03", "SMALL_TALK", "small_talk", {"SMALL_TALK"}, "test")
    add("un-01", "UNSUPPORTED", "unsupported", {"UNSUPPORTED"}, "Quel est le meilleur film cette semaine ?")
    add("un-02", "UNSUPPORTED", "unsupported", {"UNSUPPORTED"}, "football result tonight")
    add("un-03", "UNSUPPORTED", "unsupported", {"UNSUPPORTED"}, "weather in Tokyo tomorrow")

    if len(cases) < 100:
        raise RuntimeError(f"Expected at least 100 audit cases, got {len(cases)}")
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
            timeout=18,
        )
    except Exception:
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


def _parse_sql_domains(context_metrics: list[dict[str, Any]]) -> list[str]:
    for metric in context_metrics:
        if metric.get("metric") == "retrieval_plan.suggested_sql_domains":
            notes = str(metric.get("notes") or "").strip()
            if not notes or notes == "none":
                return []
            return [item.strip() for item in notes.split(",") if item.strip()]
    return []


def _parse_rag_sources(citations: list[dict[str, Any]]) -> list[str]:
    sources = []
    for citation in citations:
        source_id = str(citation.get("source_id") or "").strip()
        if source_id:
            sources.append(source_id)
    return sorted(set(sources))


def _parse_tables_used(payload: dict[str, Any]) -> list[str]:
    tables: set[str] = set()

    # From citation provenance
    for citation in list(payload.get("citations", [])):
        source_id = str(citation.get("source_id") or "")
        if ":" in source_id:
            tables.add(source_id.split(":", 1)[0])

    # From retrieval diagnostics active filters
    for metric in list(payload.get("context_metrics", [])):
        if metric.get("metric") == "retrieval_diagnostics.active_filter_count":
            notes = str(metric.get("notes") or "")
            try:
                parsed = ast.literal_eval(notes)
                if isinstance(parsed, dict):
                    for key, values in parsed.items():
                        if key == "source_table" and isinstance(values, list):
                            for item in values:
                                tables.add(str(item))
            except Exception:
                pass

    # From retrieval plan SQL domains
    for domain in _parse_sql_domains(list(payload.get("context_metrics", []))):
        mapped = SQL_DOMAIN_TO_MODULE.get(domain, domain)
        tables.add(mapped)

    return sorted(tables)


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

    sql_sources = _parse_sql_domains(context_metrics)
    rag_sources = _parse_rag_sources(citations)
    tables_used = _parse_tables_used(payload)

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
                notes.append("RAG_ONLY lacks citations and missing-evidence disclaimer.")
    elif case.category == "HYBRID":
        checks.extend([sql_used, rag_used])
        if case.requires_evidence:
            checks.append(len(citations) > 0 or evidence_missing)
            if not (len(citations) > 0 or evidence_missing):
                notes.append("HYBRID lacks citations and missing-evidence disclaimer.")

    if (not case.hallucination_trap) and (not case.allow_missing_data) and evidence_missing and case.category in {"SQL_ONLY", "HYBRID"}:
        checks.append(False)
        notes.append("Unexpected missing-data response for non-fake case.")

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
        "module": case.module,
        "question": case.question,
        "expected_intent": sorted(case.expected_intents),
        "actual_intent": actual_intent,
        "pass": passed,
        "answer_text": answer_text,
        "answer_snippet": answer_text[:220].replace("\n", " ").strip(),
        "citations_count": len(citations),
        "sql_sources_used": sql_sources,
        "rag_sources_used": rag_sources,
        "tables_modules_used": tables_used,
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
        "allow_missing_data": case.allow_missing_data,
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

    for _, rows in by_session.items():
        rows.sort(key=lambda r: int(r.get("sequence_step", 0)))
        for idx, row in enumerate(rows):
            stale_risk = "low"
            if idx > 0 and row["category"] in {"SMALL_TALK", "UNSUPPORTED"}:
                if row.get("citations_count", 0) > 0 or row.get("ui_blocks_count", 0) > 0 or row.get("context_metrics_count", 0) > 0:
                    stale_risk = "high"
                    row["pass"] = False
                    row["notes"].append("Stale response risk: previous operational payload leaked.")
            row["stale_response_risk"] = stale_risk
            row["debug_leakage_risk"] = "high" if (row.get("raw_json_visible") or row.get("technical_labels_visible")) else "low"


def _summarize(results: list[dict[str, Any]], snapshot: dict[str, Any]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for row in results if row["pass"])

    by_intent: dict[str, dict[str, int]] = {}
    by_module: dict[str, dict[str, int]] = {}
    for row in results:
        intent = row["category"]
        slot = by_intent.setdefault(intent, {"total": 0, "pass": 0})
        slot["total"] += 1
        if row["pass"]:
            slot["pass"] += 1

        module = row["module"]
        mslot = by_module.setdefault(module, {"total": 0, "pass": 0})
        mslot["total"] += 1
        if row["pass"]:
            mslot["pass"] += 1

    fake_high = sum(1 for row in results if row.get("hallucination_trap") and row.get("hallucination_risk") == "high")
    stale_high = sum(1 for row in results if row.get("stale_response_risk") == "high")
    debug_high = sum(1 for row in results if row.get("debug_leakage_risk") == "high")

    seeded_modules = [module for module, count in snapshot.get("module_data_counts", {}).items() if int(count or 0) > 0]
    tested_modules = sorted({row.get("module") for row in results if row.get("module") not in {"small_talk", "unsupported", "hybrid"}})
    module_coverage_pct = round((len(set(seeded_modules) & set(tested_modules)) / len(seeded_modules)) if seeded_modules else 0.0, 4)

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
        "pass_rate_by_module": {
            key: {
                "pass": value["pass"],
                "total": value["total"],
                "rate": round((value["pass"] / value["total"]) if value["total"] else 0.0, 4),
            }
            for key, value in sorted(by_module.items())
        },
        "fake_entity_high_risk_count": fake_high,
        "stale_response_issue_count": stale_high,
        "debug_leakage_issue_count": debug_high,
        "module_coverage": {
            "seeded_modules": seeded_modules,
            "tested_modules": tested_modules,
            "coverage_rate": module_coverage_pct,
        },
    }


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Chatbot Full Platform Coverage Audit",
        "",
        "## Overview",
        f"- Generated at: {report['generated_at']}",
        f"- Total questions: {summary['total_cases']}",
        f"- Overall pass rate: {summary['overall_pass_rate']}",
        "",
        "## Pass Rate by Intent",
    ]
    for intent, values in summary["pass_rate_by_intent"].items():
        lines.append(f"- {intent}: {values['pass']}/{values['total']} ({values['rate']})")

    lines.extend(["", "## Pass Rate by Module"])
    for module, values in summary["pass_rate_by_module"].items():
        lines.append(f"- {module}: {values['pass']}/{values['total']} ({values['rate']})")

    lines.extend([
        "",
        "## Coverage & Risk",
        f"- Seeded modules: {summary['module_coverage']['seeded_modules']}",
        f"- Tested modules: {summary['module_coverage']['tested_modules']}",
        f"- Module coverage rate: {summary['module_coverage']['coverage_rate']}",
        f"- Fake-entity high-risk hallucinations: {summary['fake_entity_high_risk_count']}",
        f"- Stale response issues: {summary['stale_response_issue_count']}",
        f"- UI/debug leakage issues: {summary['debug_leakage_issue_count']}",
        "",
        "## Acceptance Targets",
    ])
    for key, value in report["acceptance_targets"].items():
        lines.append(f"- {key}: {value}")

    failures = [row for row in report["results"] if not row["pass"]]
    lines.extend(["", "## Top Failures"])
    if not failures:
        lines.append("- None.")
    else:
        for row in failures[:25]:
            lines.extend(
                [
                    f"- `{row['case_id']}` [{row['category']}/{row['module']}] {row['question']}",
                    f"  - expected/actual: {row['expected_intent']} -> {row['actual_intent']} | pass={row['pass']}",
                    f"  - snippet: {row['answer_snippet']}",
                    f"  - citations={row['citations_count']} sql={row['sql_sources_used']} tables={row['tables_modules_used']}",
                    f"  - hallucination={row['hallucination_risk']} stale={row['stale_response_risk']} debug={row['debug_leakage_risk']}",
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

        session_cache: dict[str, str] = {}
        results: list[dict[str, Any]] = []
        for case in cases:
            session_key = case.session_key or case.case_id
            if session_key not in session_cache:
                session_cache[session_key] = _create_chat_session(client, f"Full Coverage Audit - {session_key}")
            payload, latency_ms = _run_case(client, case, session_cache[session_key])
            row = _evaluate_case(case, payload)
            row["latency_ms"] = round(latency_ms, 3)
            results.append(row)

        _compute_stale_and_followup_risks(results)
        summary = _summarize(results, snapshot)
        by_intent = summary["pass_rate_by_intent"]

        acceptance_targets = {
            "overall >= 85%": summary["overall_pass_rate"] >= 0.85,
            "SQL_ONLY >= 90%": (by_intent.get("SQL_ONLY", {}).get("rate", 0.0) >= 0.9),
            "RAG_ONLY >= 85%": (by_intent.get("RAG_ONLY", {}).get("rate", 0.0) >= 0.85),
            "HYBRID >= 80%": (by_intent.get("HYBRID", {}).get("rate", 0.0) >= 0.8),
            "SMALL_TALK = 100%": (by_intent.get("SMALL_TALK", {}).get("rate", 0.0) == 1.0),
            "UNSUPPORTED = 100%": (by_intent.get("UNSUPPORTED", {}).get("rate", 0.0) == 1.0),
            "fake entity high-risk hallucination = 0": summary["fake_entity_high_risk_count"] == 0,
            "stale response issues = 0": summary["stale_response_issue_count"] == 0,
            "UI/debug leakage = 0": summary["debug_leakage_issue_count"] == 0,
            "module coverage >= 80%": summary["module_coverage"]["coverage_rate"] >= 0.8,
            "major seeded modules all tested": all(
                module in summary["module_coverage"]["tested_modules"]
                for module in summary["module_coverage"]["seeded_modules"]
            ),
            "at least 100 questions": len(cases) >= 100,
        }

        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "snapshot": snapshot,
            "summary": summary,
            "results": results,
            "acceptance_targets": acceptance_targets,
            "metadata": {
                "case_count": len(cases),
                "follow_up_turns": sum(1 for case in cases if case.sequence_step > 1),
                "fake_trap_count": sum(1 for case in cases if case.hallucination_trap),
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

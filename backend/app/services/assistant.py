from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import re
from typing import Any, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import Select, String, cast, func, or_, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.utils.stage_normalization import normalize_stage
from app.ml.llm.provider import get_llm_client
from app.models.batch import Batch
from app.models.chat import ChatMessage, ChatSession
from app.models.commercial_catalog_product import CommercialCatalogProduct
from app.models.commercial_invoice import CommercialInvoice, CommercialInvoiceLine
from app.models.commercial_order import CommercialOrder, CommercialOrderLine
from app.models.cooperative import Cooperative
from app.models.enums import UserRole
from app.models.farmer_advance import FarmerAdvance
from app.models.global_charge import GlobalCharge
from app.models.input import Input
from app.models.member import Member
from app.models.ml import MLPredictionLog
from app.models.mixins import current_utc
from app.models.parcel import Parcel
from app.models.pre_harvest_step import PreHarvestStep
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.reference import KnowledgeChunk, ReferenceMetric
from app.models.stock import Stock
from app.models.treasury_transaction import TreasuryTransaction
from app.models.user import User
from app.schemas.chat import (
    ChatCitation,
    ChatDashboardSnapshot,
    ChatMessageRead,
    ChatMetricFact,
    ChatResponse,
    ChatSessionRead,
    ChatUIBlock,
)
from app.schemas.reference import KnowledgeChunkListResponse, KnowledgeChunkRead, ReferenceMetricListResponse, ReferenceMetricRead
from app.services import analytics as analytics_service
from app.services.chat_orchestrator import orchestrate_context
from app.services.chat_retrieval_router import RetrievalIntentType, RetrievalPlan, build_retrieval_plan
from app.services.rag_freshness_policy import get_freshness_policy
from app.services.rag_retrieval_diagnostics import summarize_retrieval
from app.services.helpers import round_metric
from app.services.rag_embeddings import embed_texts
from app.utils.exceptions import NotFoundError, ValidationError

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_\-']+")
BATCH_UUID_PATTERN = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)
LOT_CODE_PATTERN = re.compile(r"\b(?:LOT|BATCH|DEMO-ML|BENCH-ML)[-_][A-Z0-9][A-Z0-9\-_]*\b", re.IGNORECASE)
MEMBER_CODE_PATTERN = re.compile(r"(?<![A-Z0-9-])(?:MEMBER|FARMER|MEM|M)[-_][A-Z0-9][A-Z0-9\-_]*\b", re.IGNORECASE)
STAGE_CODE_PATTERN = re.compile(r"\bSTAGE[_-][A-Z0-9][A-Z0-9\-_]*\b", re.IGNORECASE)
PARCEL_CODE_PATTERN = re.compile(r"\b(?:PARCELLE|PARCEL|FIELD)[-_][A-Z0-9][A-Z0-9\-_]*\b", re.IGNORECASE)
ORDER_NUMBER_PATTERN = re.compile(r"\b(?:ORD|CMD|ORDER|COMMANDE)[-_]?[A-Z0-9]{2,}\b", re.IGNORECASE)
INVOICE_NUMBER_PATTERN = re.compile(r"\b(?:INV|FACT|FACTURE)[-_]?[A-Z0-9]{2,}\b", re.IGNORECASE)
PRODUCT_CANONICAL_MAP = {
    "mango": "mango",
    "mangue": "mango",
    "mil": "millet",
    "millet": "millet",
    "arachide": "peanut",
    "peanut": "peanut",
    "bissap": "bissap",
}
STOPWORDS = {
    "about",
    "after",
    "agricultural",
    "agriculture",
    "and",
    "assistant",
    "batch",
    "better",
    "chat",
    "comment",
    "context",
    "coop",
    "cooperative",
    "data",
    "for",
    "from",
    "help",
    "how",
    "important",
    "manager",
    "more",
    "need",
    "our",
    "please",
    "process",
    "project",
    "rag",
    "request",
    "response",
    "should",
    "show",
    "system",
    "this",
    "use",
    "used",
    "using",
    "what",
    "why",
    "with",
}

QUICK_PATTERNS = (
    re.compile(r"^\s*\d+(?:\s*[\+\-\*/]\s*\d+)+\s*\??\s*$"),
    re.compile(r"^\s*(combien|what is|calculate|calcule|calculez)\b", flags=re.IGNORECASE),
)
STOCK_HINTS = {"stock", "stocks", "rupture", "seuil", "inventory", "inventaire", "available", "disponible"}
LOSS_HINTS = {"perte", "pertes", "loss", "losses", "efficacite", "efficiency", "sechage", "tri", "lot", "lots", "batch"}
MEMBER_HINTS = {
    "membre",
    "membres",
    "member",
    "members",
    "farmer",
    "farmers",
    "collecte",
    "collect",
    "collector",
    "cout",
    "cost",
    "kg",
    "rentable",
    "efficiency",
}
COMMERCIAL_HINTS = {
    "commercial",
    "commercialisation",
    "produit",
    "produits",
    "product",
    "products",
    "vente",
    "ventes",
    "sale",
    "sales",
    "invoice",
    "invoices",
    "facture",
    "factures",
    "commande",
    "commandes",
    "order",
    "orders",
}
OPERATIONAL_HINTS = {
    "batch",
    "collecte",
    "collect",
    "cooperative",
    "dashboard",
    "drying",
    "efficiency",
    "loss",
    "losses",
    "lot",
    "lots",
    "operations",
    "perte",
    "pertes",
    "process",
    "production",
    "quality",
    "facture",
    "invoice",
    "commercialisation",
    "vente",
    "commande",
    "member",
    "membre",
    "cout",
    "cost",
    "sechage",
    "stock",
    "tri",
}
FRENCH_HINTS = {
    "bonjour",
    "comment",
    "combien",
    "pourquoi",
    "perte",
    "stock",
    "facture",
    "membre",
    "cooperative",
}
ENGLISH_HINTS = {
    "hello",
    "what",
    "why",
    "how",
    "loss",
    "stock",
    "invoice",
    "member",
    "cooperative",
}

MISSING_ENTITY_SAFE_ANSWER = (
    "Je ne trouve pas cette donnée dans la base opérationnelle. "
    "Aucune donnée vérifiable n'est disponible pour cette demande. "
    "Veuillez vérifier le produit, le lot, le producteur ou l’étape demandée."
)

_LEGACY_CHUNK_TYPE_MAP = {
    "batch": "batch_summary",
    "batches": "batch_summary",
    "process_step": "process_step_summary",
    "process_steps": "process_step_summary",
    "recommendation": "recommendation_context",
    "recommendations": "recommendation_context",
    "anomaly": "anomaly_summary",
    "anomaly_context": "anomaly_summary",
    "anomaly_summary": "anomaly_summary",
    "ml_prediction_logs": "ml_prediction_context",
    "ml_prediction_context": "ml_prediction_context",
    "ml_training_runs": "ml_evaluation_context",
    "ml_evaluation_context": "ml_evaluation_context",
    "commercial_orders": "commercial_context",
    "commercial_context": "commercial_context",
    "global_charges": "cost_context",
    "parcels": "parcel_context",
    "pre_harvest_steps": "pre_harvest_context",
    "knowledge_chunks": "agronomic_knowledge",
    "knowledge_chunk": "agronomic_knowledge",
    "reference_metrics": "benchmark_reference",
    "reference_metric": "benchmark_reference",
    "product_stage_summary": "product_stage_summary",
    "lot_status_summary": "lot_status_summary",
    "lot_recommendation_summary": "lot_recommendation_summary",
    "operational_risk_summary": "operational_risk_summary",
    "scoped_loss_summary": "scoped_loss_summary",
}


@dataclass
class RetrievalHit:
    chunk_id: str
    source_table: str
    source_record_ref: str
    content: str
    metadata: dict[str, Any]
    distance: float
    keyword_score: float
    vector_rank: int = 0
    keyword_rank: int = 0
    fused_score: float = 0.0
    rerank_score: float = 0.0
    freshness_age_minutes: Optional[float] = None
    retrieval_reason: Optional[str] = None


@dataclass
class ScopeQueryProfile:
    scope_level: str
    products: set[str]
    stages: set[str]
    lot_codes: set[str]
    benchmark_intent: bool
    comparative_intent: bool


@dataclass
class ReferenceContext:
    citations: list[ChatCitation]
    metrics: list[ChatMetricFact]


def get_product_stock_fact(
    db: Session,
    *,
    current_user: User,
    product_name: str,
) -> Optional[dict[str, Any]]:
    if current_user.cooperative_id is None or not product_name:
        return None
    normalized = _normalize_product_name(product_name)
    rows = db.execute(
        select(Product.name, Stock.total_stock_kg, Stock.reserved_in_lots_kg, Stock.threshold, Stock.unit)
        .join(Stock, Stock.product_id == Product.id)
        .where(Stock.cooperative_id == current_user.cooperative_id)
    ).all()
    selected: Optional[tuple[Any, Any, Any, Any, Any]] = None
    for row in rows:
        row_product = _normalize_product_name(str(row[0] or ""))
        if row_product == normalized:
            selected = row
            break
    if selected is None:
        return None
    product_label = str(selected[0] or product_name).strip()
    total = float(selected[1] or 0.0)
    reserved = float(selected[2] or 0.0)
    threshold = float(selected[3] or 0.0)
    unit = str(selected[4] or "kg")
    available = total - reserved
    status = "low" if available < threshold else "stable"
    return {
        "fact_type": "product_stock",
        "product": product_label,
        "values": {
            "total_stock": round_metric(total),
            "reserved_in_lots": round_metric(reserved),
            "remaining_stock": round_metric(available),
            "threshold": round_metric(threshold),
            "status": status,
        },
        "units": {"stock": unit, "threshold": unit},
        "source_table": "stocks",
        "source_scope": "product",
    }


def get_product_remaining_stock(
    db: Session,
    *,
    current_user: User,
    product_name: str,
) -> Optional[dict[str, Any]]:
    fact = get_product_stock_fact(db, current_user=current_user, product_name=product_name)
    if not fact:
        return None
    remaining = float(fact.get("values", {}).get("remaining_stock", 0.0) or 0.0)
    return {
        "fact_type": "product_remaining_stock",
        "product": fact.get("product", product_name),
        "values": {"remaining_stock": remaining},
        "units": {"stock": fact.get("units", {}).get("stock", "kg")},
        "source_table": "stocks",
        "source_scope": "product",
    }


def get_batch_status_fact(
    db: Session,
    *,
    current_user: User,
    lot_code: str,
) -> Optional[dict[str, Any]]:
    if current_user.cooperative_id is None or not lot_code:
        return None
    target = lot_code.strip().upper()
    row = db.execute(
        select(Batch, Product)
        .join(Product, Product.id == Batch.product_id)
        .where(Batch.cooperative_id == current_user.cooperative_id, func.upper(Batch.code) == target)
        .limit(1)
    ).first()
    if not row:
        return None
    batch, product = row
    steps = db.scalars(
        select(ProcessStep).where(ProcessStep.batch_id == batch.id).order_by(ProcessStep.sequence_order.asc(), ProcessStep.date.asc())
    ).all()
    last_step = steps[-1] if steps else None
    pending_step = next((step for step in steps if str(step.status.value if hasattr(step.status, "value") else step.status).lower() == "pending"), None)
    initial = float(batch.initial_qty or 0.0)
    current = float(batch.current_qty or 0.0)
    cumulative_loss = ((initial - current) / initial * 100.0) if initial > 0 else 0.0
    return {
        "fact_type": "batch_status",
        "lot_code": str(batch.code or target),
        "product": str(product.name or ""),
        "values": {
            "status": str(batch.status.value if hasattr(batch.status, "value") else batch.status),
            "initial_qty": round_metric(initial),
            "current_qty": round_metric(current),
            "cumulative_loss_pct": round_metric(cumulative_loss),
            "latest_step": str(last_step.type) if last_step else "none",
            "pending_step": str(pending_step.type) if pending_step else "none",
            "risk_or_anomaly": "none",
        },
        "units": {"quantity": str(batch.unit or "kg"), "loss": "%"},
        "source_table": "batches,process_steps",
        "source_scope": "lot",
    }


def get_active_lots_fact(
    db: Session,
    *,
    current_user: User,
) -> Optional[dict[str, Any]]:
    if current_user.cooperative_id is None:
        return None
    active_count = db.scalar(
        select(func.count(Batch.id)).where(
            Batch.cooperative_id == current_user.cooperative_id,
            func.lower(cast(Batch.status, String)) == "active",
        )
    )
    return {
        "fact_type": "active_lots",
        "values": {"active_lots": int(active_count or 0)},
        "units": {"count": "count"},
        "source_table": "batches",
        "source_scope": "cooperative",
    }


def _find_member_from_message(
    db: Session,
    *,
    current_user: User,
    message: str,
) -> tuple[Optional[Member], bool]:
    if current_user.cooperative_id is None:
        return None, False
    code_candidates = {str(code).upper() for code in MEMBER_CODE_PATTERN.findall(message)}
    token_candidates = {str(token).upper().strip() for token in TOKEN_PATTERN.findall(message)}
    for token in token_candidates:
        if "-" in token and any(marker in token for marker in ("MEMBER", "FARMER", "-MEM-", "MEM-", "-M-")):
            code_candidates.add(token)
    if code_candidates:
        row = db.scalars(
            select(Member)
            .where(
                Member.cooperative_id == current_user.cooperative_id,
                func.upper(Member.code).in_(code_candidates),
            )
            .limit(1)
        ).first()
        return row, True

    lowered = message.lower()
    members = db.scalars(select(Member).where(Member.cooperative_id == current_user.cooperative_id)).all()
    for member in members:
        full_name = str(member.full_name or "").strip().lower()
        if full_name and re.search(rf"(?<![\\w-]){re.escape(full_name)}(?![\\w-])", lowered):
            return member, True

    asks_member = any(token in lowered for token in ("membre", "member", "producteur", "farmer"))
    return None, asks_member


def _find_product_from_message(
    db: Session,
    *,
    current_user: User,
    message: str,
    fallback_products: Sequence[str],
) -> tuple[Optional[Product], bool]:
    product_hint = _infer_product_from_message(
        db,
        current_user=current_user,
        message=message,
        fallback_products=fallback_products,
    )
    if current_user.cooperative_id is None:
        return None, bool(product_hint)
    if product_hint:
        product = db.scalars(
            select(Product).where(
                Product.cooperative_id == current_user.cooperative_id,
                func.lower(Product.name) == product_hint.lower(),
            )
        ).first()
        if product:
            return product, True
    return None, bool(product_hint)


def _find_order_from_message(
    db: Session,
    *,
    current_user: User,
    message: str,
) -> tuple[Optional[CommercialOrder], bool]:
    if current_user.cooperative_id is None:
        return None, False
    order_numbers = [str(code).upper() for code in ORDER_NUMBER_PATTERN.findall(message)]
    for token in TOKEN_PATTERN.findall(message):
        normalized = str(token).upper().strip()
        if "-" in normalized and (
            normalized.startswith("ORD-")
            or normalized.startswith("CMD-")
            or normalized.startswith("ORDER-")
            or "-ORD-" in normalized
            or "-CMD-" in normalized
        ):
            order_numbers.append(normalized)
    order_numbers = sorted({code for code in order_numbers if code})
    if order_numbers:
        row = db.scalars(
            select(CommercialOrder)
            .where(
                CommercialOrder.cooperative_id == current_user.cooperative_id,
                func.upper(CommercialOrder.order_number).in_(order_numbers),
            )
            .limit(1)
        ).first()
        return row, True
    lowered = message.lower()
    return None, any(token in lowered for token in ("commande", "order", "orders"))


def _find_invoice_from_message(
    db: Session,
    *,
    current_user: User,
    message: str,
) -> tuple[Optional[CommercialInvoice], bool]:
    if current_user.cooperative_id is None:
        return None, False
    invoice_numbers = [str(code).upper() for code in INVOICE_NUMBER_PATTERN.findall(message)]
    for token in TOKEN_PATTERN.findall(message):
        normalized = str(token).upper().strip()
        if "-" in normalized and (
            normalized.startswith("INV-")
            or normalized.startswith("FACT-")
            or normalized.startswith("FAC-")
            or "-INV-" in normalized
            or "-FACT-" in normalized
            or "-FAC-" in normalized
        ):
            invoice_numbers.append(normalized)
    invoice_numbers = sorted({code for code in invoice_numbers if code})
    if invoice_numbers:
        row = db.scalars(
            select(CommercialInvoice)
            .where(
                CommercialInvoice.cooperative_id == current_user.cooperative_id,
                func.upper(CommercialInvoice.invoice_number).in_(invoice_numbers),
            )
            .limit(1)
        ).first()
        return row, True
    lowered = message.lower()
    return None, any(token in lowered for token in ("facture", "invoice", "invoices"))


def _get_member_collection_total_fact(
    db: Session,
    *,
    current_user: User,
    member: Member,
) -> dict[str, Any]:
    total_qty, total_value = db.execute(
        select(func.coalesce(func.sum(Input.quantity), 0.0), func.coalesce(func.sum(Input.estimated_value), 0.0))
        .where(Input.cooperative_id == current_user.cooperative_id, Input.member_id == member.id)
    ).one()
    return {
        "fact_type": "member_collection_total",
        "member_code": str(member.code),
        "member_name": str(member.full_name),
        "values": {
            "total_collection_kg": round_metric(float(total_qty or 0.0)),
            "estimated_value_fcfa": round_metric(float(total_value or 0.0)),
        },
        "source_table": "inputs,members",
        "source_scope": "member",
    }


def _get_member_parcel_fact(
    db: Session,
    *,
    current_user: User,
    member: Member,
) -> dict[str, Any]:
    rows = db.execute(
        select(Parcel.name, Parcel.main_culture, Parcel.surface_ha)
        .where(Parcel.cooperative_id == current_user.cooperative_id, Parcel.member_id == member.id)
        .order_by(Parcel.name.asc())
    ).all()
    return {
        "fact_type": "member_parcels",
        "member_code": str(member.code),
        "member_name": str(member.full_name),
        "values": {
            "parcel_count": len(rows),
            "parcels": [
                {"name": str(name), "culture": str(culture), "surface_ha": round_metric(float(surface or 0.0))}
                for name, culture, surface in rows[:8]
            ],
        },
        "source_table": "parcels,members",
        "source_scope": "member",
    }


def _get_member_advance_fact(
    db: Session,
    *,
    current_user: User,
    member: Member,
) -> dict[str, Any]:
    total_active = db.scalar(
        select(func.coalesce(func.sum(FarmerAdvance.amount_fcfa), 0.0)).where(
            FarmerAdvance.cooperative_id == current_user.cooperative_id,
            FarmerAdvance.farmer_id == member.id,
            func.lower(cast(FarmerAdvance.status, String)) == "active",
        )
    ) or 0.0
    return {
        "fact_type": "member_advance_total",
        "member_code": str(member.code),
        "member_name": str(member.full_name),
        "values": {"active_advances_fcfa": round_metric(float(total_active))},
        "source_table": "farmer_advances,members",
        "source_scope": "member",
    }


def _get_collection_by_product_fact(
    db: Session,
    *,
    current_user: User,
    product: Product,
) -> dict[str, Any]:
    total_qty, total_value = db.execute(
        select(func.coalesce(func.sum(Input.quantity), 0.0), func.coalesce(func.sum(Input.estimated_value), 0.0))
        .where(Input.cooperative_id == current_user.cooperative_id, Input.product_id == product.id)
    ).one()
    return {
        "fact_type": "collection_by_product",
        "product": str(product.name),
        "values": {
            "total_collected_kg": round_metric(float(total_qty or 0.0)),
            "estimated_value_fcfa": round_metric(float(total_value or 0.0)),
        },
        "source_table": "inputs,products",
        "source_scope": "product",
    }


def _get_collection_totals_by_product_fact(
    db: Session,
    *,
    current_user: User,
) -> dict[str, Any]:
    rows = db.execute(
        select(Product.name, func.coalesce(func.sum(Input.quantity), 0.0))
        .join(Input, Input.product_id == Product.id)
        .where(Input.cooperative_id == current_user.cooperative_id)
        .group_by(Product.name)
        .order_by(func.coalesce(func.sum(Input.quantity), 0.0).desc())
    ).all()
    return {
        "fact_type": "collection_totals_by_product",
        "values": [
            {"product": str(product), "total_collected_kg": round_metric(float(total_qty or 0.0))}
            for product, total_qty in rows[:12]
        ],
        "source_table": "inputs,products",
        "source_scope": "cooperative",
    }


def _get_stage_loss_summary_fact(db: Session, *, current_user: User) -> dict[str, Any]:
    rows = db.execute(
        select(
            ProcessStep.type,
            func.avg(
                func.coalesce(
                    (ProcessStep.qty_in - ProcessStep.qty_out) * 100.0 / func.nullif(ProcessStep.qty_in, 0),
                    0.0,
                )
            ),
        )
        .join(Batch, Batch.id == ProcessStep.batch_id)
        .where(Batch.cooperative_id == current_user.cooperative_id)
        .group_by(ProcessStep.type)
        .order_by(func.avg(
            func.coalesce(
                (ProcessStep.qty_in - ProcessStep.qty_out) * 100.0 / func.nullif(ProcessStep.qty_in, 0),
                0.0,
            )
        ).desc())
    ).all()
    return {
        "fact_type": "stage_loss_summary",
        "values": [
            {"stage": str(stage), "avg_loss_pct": round_metric(float(avg_loss or 0.0))}
            for stage, avg_loss in rows[:8]
        ],
        "source_table": "process_steps,batches",
        "source_scope": "cooperative",
    }


def _get_order_status_summary_fact(db: Session, *, current_user: User) -> dict[str, Any]:
    rows = db.execute(
        select(cast(CommercialOrder.status, String), func.count(CommercialOrder.id))
        .where(CommercialOrder.cooperative_id == current_user.cooperative_id)
        .group_by(cast(CommercialOrder.status, String))
    ).all()
    counts = {str(status): int(count or 0) for status, count in rows}
    return {
        "fact_type": "order_status_summary",
        "values": counts,
        "source_table": "commercial_orders",
        "source_scope": "cooperative",
    }


def _get_invoice_status_summary_fact(db: Session, *, current_user: User) -> dict[str, Any]:
    rows = db.execute(
        select(cast(CommercialInvoice.status, String), func.count(CommercialInvoice.id), func.coalesce(func.sum(CommercialInvoice.total_amount_fcfa), 0.0))
        .where(CommercialInvoice.cooperative_id == current_user.cooperative_id)
        .group_by(cast(CommercialInvoice.status, String))
    ).all()
    items = [
        {"status": str(status), "count": int(count or 0), "amount_fcfa": round_metric(float(amount or 0.0))}
        for status, count, amount in rows
    ]
    return {
        "fact_type": "invoice_status_summary",
        "values": items,
        "source_table": "commercial_invoices",
        "source_scope": "cooperative",
    }


def _get_finance_summary_fact(db: Session, *, current_user: User) -> dict[str, Any]:
    total_charges = db.scalar(
        select(func.coalesce(func.sum(GlobalCharge.amount_fcfa), 0.0)).where(GlobalCharge.cooperative_id == current_user.cooperative_id)
    ) or 0.0
    total_advances = db.scalar(
        select(func.coalesce(func.sum(FarmerAdvance.amount_fcfa), 0.0)).where(
            FarmerAdvance.cooperative_id == current_user.cooperative_id,
            func.lower(cast(FarmerAdvance.status, String)) == "active",
        )
    ) or 0.0
    income = db.scalar(
        select(func.coalesce(func.sum(TreasuryTransaction.amount_fcfa), 0.0)).where(
            TreasuryTransaction.cooperative_id == current_user.cooperative_id,
            func.lower(cast(TreasuryTransaction.type, String)) == "income",
            func.lower(cast(TreasuryTransaction.status, String)) == "recorded",
        )
    ) or 0.0
    expense = db.scalar(
        select(func.coalesce(func.sum(TreasuryTransaction.amount_fcfa), 0.0)).where(
            TreasuryTransaction.cooperative_id == current_user.cooperative_id,
            func.lower(cast(TreasuryTransaction.type, String)) == "expense",
            func.lower(cast(TreasuryTransaction.status, String)) == "recorded",
        )
    ) or 0.0
    return {
        "fact_type": "finance_summary",
        "values": {
            "total_charges_fcfa": round_metric(float(total_charges)),
            "active_advances_fcfa": round_metric(float(total_advances)),
            "income_fcfa": round_metric(float(income)),
            "expense_fcfa": round_metric(float(expense)),
            "balance_fcfa": round_metric(float(income) - float(expense)),
        },
        "source_table": "global_charges,farmer_advances,treasury_transactions",
        "source_scope": "cooperative",
    }


def _get_charges_by_category_fact(db: Session, *, current_user: User) -> dict[str, Any]:
    rows = db.execute(
        select(GlobalCharge.charge_type, func.coalesce(func.sum(GlobalCharge.amount_fcfa), 0.0))
        .where(GlobalCharge.cooperative_id == current_user.cooperative_id)
        .group_by(GlobalCharge.charge_type)
        .order_by(func.coalesce(func.sum(GlobalCharge.amount_fcfa), 0.0).desc())
    ).all()
    return {
        "fact_type": "charges_by_category",
        "values": [
            {"category": str(charge_type), "amount_fcfa": round_metric(float(amount or 0.0))}
            for charge_type, amount in rows[:12]
        ],
        "source_table": "global_charges",
        "source_scope": "cooperative",
    }


def _get_ml_latest_fact(db: Session) -> Optional[dict[str, Any]]:
    row = db.scalars(select(MLPredictionLog).order_by(MLPredictionLog.created_at.desc()).limit(1)).first()
    if not row:
        return None
    return {
        "fact_type": "ml_latest_prediction",
        "values": {
            "product": str(row.product or ""),
            "critical_stage": str(row.critical_stage or ""),
            "predicted_loss_pct": round_metric(float(row.predicted_loss_pct or 0.0)),
            "risk_level": str(row.risk_level.value if hasattr(row.risk_level, "value") else row.risk_level or "unknown"),
            "anomaly_score": round_metric(float(row.anomaly_score or 0.0)),
            "model_version": str(row.model_version or ""),
            "created_at": str(row.created_at.isoformat() if row.created_at else ""),
        },
        "source_table": "ml_prediction_logs",
        "source_scope": "cooperative",
    }


def _infer_product_from_message(
    db: Session,
    *,
    current_user: User,
    message: str,
    fallback_products: Sequence[str],
) -> str:
    if fallback_products:
        return str(fallback_products[0]).strip()
    if current_user.cooperative_id is None:
        return ""
    lowered = message.lower()
    product_names = [
        str(item)
        for item in db.scalars(select(Product.name).where(Product.cooperative_id == current_user.cooperative_id))
        .all()
        if str(item or "").strip()
    ]
    for name in product_names:
        if name.lower() in lowered:
            return name
    token_candidates = [token.lower() for token in TOKEN_PATTERN.findall(lowered)]
    for token in token_candidates:
        if token.startswith("fake_product") or ("product" in token and "_" in token):
            return token
    return ""


def _validate_requested_entities_existence(
    db: Session,
    *,
    current_user: User,
    message: str,
    retrieval_plan: RetrievalPlan,
) -> dict[str, Any]:
    if current_user.cooperative_id is None:
        return {"valid": True, "missing": []}

    lowered = message.lower()
    entities = retrieval_plan.detected_entities if isinstance(retrieval_plan.detected_entities, dict) else {}
    missing: list[dict[str, str]] = []

    known_products = {
        _normalize_product_name(str(item))
        for item in db.scalars(select(Product.name).where(Product.cooperative_id == current_user.cooperative_id)).all()
        if str(item or "").strip()
    }
    known_lots = {
        str(item).upper()
        for item in db.scalars(select(Batch.code).where(Batch.cooperative_id == current_user.cooperative_id)).all()
        if str(item or "").strip()
    }
    known_member_codes = {
        str(item).upper()
        for item in db.scalars(select(Member.code).where(Member.cooperative_id == current_user.cooperative_id)).all()
        if str(item or "").strip()
    }
    known_parcel_names = {
        str(item).upper()
        for item in db.scalars(select(Parcel.name).where(Parcel.cooperative_id == current_user.cooperative_id)).all()
        if str(item or "").strip()
    }
    known_stage_tokens: set[str] = set()
    for raw in db.scalars(
        select(ProcessStep.type).join(Batch, Batch.id == ProcessStep.batch_id).where(Batch.cooperative_id == current_user.cooperative_id)
    ).all():
        token = str(normalize_stage(raw) or raw or "").lower().strip()
        if token:
            known_stage_tokens.add(token)

    product_candidates = {
        _normalize_product_name(str(item))
        for item in (entities.get("products") or [])
        if str(item or "").strip()
    }
    for match in re.finditer(r"(?:produit|product|culture|crop)\s+([a-zA-Z0-9_\-]+)", message, re.IGNORECASE):
        token = _normalize_product_name(str(match.group(1) or ""))
        if token:
            product_candidates.add(token)
    for token in TOKEN_PATTERN.findall(message):
        normalized = _normalize_product_name(str(token))
        if normalized.startswith("fake_") or normalized.startswith("crop_fake"):
            product_candidates.add(normalized)
    inferred_product = _infer_product_from_message(
        db,
        current_user=current_user,
        message=message,
        fallback_products=[str(item) for item in product_candidates if str(item).strip()],
    )
    if inferred_product:
        product_candidates.add(_normalize_product_name(inferred_product))

    lot_candidates = {str(item).upper() for item in (entities.get("batch_codes") or []) if str(item).strip()}
    lot_candidates.update({str(code).upper() for code in LOT_CODE_PATTERN.findall(message)})

    member_candidates = {str(code).upper() for code in MEMBER_CODE_PATTERN.findall(message)}
    if "producteur" in lowered or "farmer" in lowered or "member" in lowered or "membre" in lowered:
        for token in TOKEN_PATTERN.findall(message):
            normalized = str(token).upper().strip()
            if (
                normalized.startswith("MEMBER_")
                or normalized.startswith("FARMER_")
                or normalized.startswith("MEMBER-")
                or normalized.startswith("FARMER-")
                or normalized.startswith("M-")
                or normalized.startswith("MEM-")
                or "-MEM-" in normalized
                or "-M-" in normalized
            ):
                member_candidates.add(normalized)

    stage_candidates = {
        str(item).lower().strip()
        for item in (entities.get("stages") or [])
        if str(item or "").strip()
    }
    stage_candidates.update({str(item).lower() for item in STAGE_CODE_PATTERN.findall(message)})
    stage_phrase_match = re.search(r"(?:étape|etape|stage)\s+([a-zA-Z0-9_\-]+)", message, re.IGNORECASE)
    if stage_phrase_match:
        stage_candidates.add(stage_phrase_match.group(1).lower())

    if product_candidates:
        for product in sorted(product_candidates):
            if product and product not in known_products:
                missing.append({"entity_type": "product", "value": product})
    if lot_candidates:
        for lot_code in sorted(lot_candidates):
            if lot_code and lot_code not in known_lots:
                missing.append({"entity_type": "lot", "value": lot_code})
    if member_candidates:
        for code in sorted(member_candidates):
            if code and code not in known_member_codes:
                missing.append({"entity_type": "member", "value": code})
    parcel_candidates = {str(code).upper() for code in PARCEL_CODE_PATTERN.findall(message)}
    if parcel_candidates:
        for code in sorted(parcel_candidates):
            if code and code not in known_parcel_names:
                missing.append({"entity_type": "parcel", "value": code})
    if stage_candidates:
        canonical_stage_candidates = _canonical_stage_tokens(list(stage_candidates))
        for stage in sorted(canonical_stage_candidates):
            if stage and stage not in known_stage_tokens:
                missing.append({"entity_type": "stage", "value": stage})

    return {"valid": len(missing) == 0, "missing": missing}


def _build_sql_only_fact_bundle(
    db: Session,
    *,
    current_user: User,
    message: str,
    retrieval_plan: RetrievalPlan,
) -> dict[str, Any]:
    lowered = message.lower()
    entities = retrieval_plan.detected_entities if isinstance(retrieval_plan.detected_entities, dict) else {}
    products = [str(item) for item in (entities.get("products") or []) if str(item).strip()]
    lot_codes = [str(item).upper() for item in (entities.get("batch_codes") or []) if str(item).strip()]
    inferred_product = _infer_product_from_message(
        db,
        current_user=current_user,
        message=message,
        fallback_products=products,
    )
    inferred_lot_codes = sorted({*lot_codes, *[code.upper() for code in LOT_CODE_PATTERN.findall(message)]})

    fact_bundle: dict[str, Any] = {"facts": [], "missing_reason": None}

    def _ok(fact: Optional[dict[str, Any]]) -> dict[str, Any]:
        if fact:
            fact_bundle["facts"].append(fact)
            return fact_bundle
        fact_bundle["missing_reason"] = MISSING_ENTITY_SAFE_ANSWER
        return fact_bundle

    if _is_member_list_request(message):
        rows = db.execute(
            select(Member.code, Member.full_name, Member.main_product, Member.status, Member.parcel_count, Member.area_hectares)
            .where(Member.cooperative_id == current_user.cooperative_id)
            .order_by(Member.full_name.asc())
            .limit(25)
        ).all()
        fact_bundle["facts"].append(
            {
                "fact_type": "member_list",
                "values": [
                    {
                        "code": str(code),
                        "name": str(name),
                        "main_product": str(main_product or ""),
                        "status": str(status.value if hasattr(status, "value") else status),
                        "parcel_count": int(parcel_count or 0),
                        "area_hectares": round_metric(float(area_hectares or 0.0)),
                    }
                    for code, name, main_product, status, parcel_count, area_hectares in rows
                ],
                "source_table": "members",
                "source_scope": "cooperative",
            }
        )
        if not rows:
            fact_bundle["missing_reason"] = "Aucun membre trouvé pour cette coopérative."
        return fact_bundle

    if _is_lot_table_request(message):
        rows = _fetch_lot_directory_rows(
            db,
            current_user=current_user,
            message=message,
            limit=_requested_table_limit(message, default=25, maximum=100),
        )
        fact_bundle["facts"].append(
            {
                "fact_type": "lot_table",
                "values": [_lot_row_to_fact_row(row) for row in rows],
                "filters": {"active_only": _is_active_lot_filter_requested(message)},
                "source_table": "batches,products",
                "source_scope": "cooperative",
            }
        )
        if not rows:
            fact_bundle["missing_reason"] = (
                "Aucun lot actif disponible pour cette coopérative."
                if _is_active_lot_filter_requested(message)
                else "Aucun lot disponible pour cette coopérative."
            )
        return fact_bundle

    if any(token in lowered for token in ("stock", "remaining", "disponible", "réservé", "reserve", "available")):
        product_hint = inferred_product
        if product_hint:
            stock_fact = get_product_stock_fact(db, current_user=current_user, product_name=product_hint)
            return _ok(stock_fact)
        fact_bundle["missing_reason"] = MISSING_ENTITY_SAFE_ANSWER
        return fact_bundle
    if "status" in lowered or "lot-" in lowered or "batch" in lowered or inferred_lot_codes:
        lot_code = inferred_lot_codes[0] if inferred_lot_codes else ""
        if lot_code:
            batch_fact = get_batch_status_fact(db, current_user=current_user, lot_code=lot_code)
            return _ok(batch_fact)
    if "active lots" in lowered or "active lot" in lowered or "lots actifs" in lowered:
        active = get_active_lots_fact(db, current_user=current_user)
        return _ok(active)

    if any(token in lowered for token in ("completed lots", "lots completed", "lots termin", "lots compl")):
        completed_count = db.scalar(
            select(func.count(Batch.id)).where(
                Batch.cooperative_id == current_user.cooperative_id,
                func.lower(cast(Batch.status, String)) == "completed",
            )
        )
        fact_bundle["facts"].append(
            {
                "fact_type": "completed_lots",
                "values": {"completed_lots": int(completed_count or 0)},
                "source_table": "batches",
                "source_scope": "cooperative",
            }
        )
        return fact_bundle

    if any(token in lowered for token in ("perte", "loss by stage", "losses by stage", "material balance", "bilan matière", "bilan matiere")):
        fact_bundle["facts"].append(_get_stage_loss_summary_fact(db, current_user=current_user))
        return fact_bundle

    if any(token in lowered for token in ("membre", "member", "producteur", "farmer")):
        member, has_member_ref = _find_member_from_message(db, current_user=current_user, message=message)
        if has_member_ref and member is None:
            fact_bundle["missing_reason"] = MISSING_ENTITY_SAFE_ANSWER
            return fact_bundle
        if member:
            if any(token in lowered for token in ("collecte", "collection", "total")):
                fact_bundle["facts"].append(_get_member_collection_total_fact(db, current_user=current_user, member=member))
                return fact_bundle
            if any(token in lowered for token in ("parcelle", "parcel", "culture")):
                fact_bundle["facts"].append(_get_member_parcel_fact(db, current_user=current_user, member=member))
                return fact_bundle
            if any(token in lowered for token in ("avance", "advance")):
                fact_bundle["facts"].append(_get_member_advance_fact(db, current_user=current_user, member=member))
                return fact_bundle
            fact_bundle["facts"].append(
                {
                    "fact_type": "member_detail",
                    "member_code": str(member.code),
                    "member_name": str(member.full_name),
                    "values": {
                        "phone": str(member.phone or ""),
                        "village": str(member.village or ""),
                        "main_product": str(member.main_product or ""),
                        "status": str(member.status.value if hasattr(member.status, "value") else member.status),
                        "parcel_count": int(member.parcel_count or 0),
                        "area_hectares": round_metric(float(member.area_hectares or 0.0)),
                    },
                    "source_table": "members",
                    "source_scope": "member",
                }
            )
            return fact_bundle

    if any(token in lowered for token in ("parcelle", "parcel", "culture", "pre-harvest", "pre harvest", "pré-récolte", "pre recolte")):
        member, _ = _find_member_from_message(db, current_user=current_user, message=message)
        stmt = select(Parcel, Member).join(Member, Member.id == Parcel.member_id).where(Parcel.cooperative_id == current_user.cooperative_id)
        if member:
            stmt = stmt.where(Parcel.member_id == member.id)
        rows = db.execute(stmt.order_by(Parcel.name.asc()).limit(20)).all()
        if not rows:
            fact_bundle["missing_reason"] = MISSING_ENTITY_SAFE_ANSWER
            return fact_bundle
        parcels_payload = []
        for parcel, parcel_member in rows:
            pre_status = db.scalars(
                select(PreHarvestStep.status)
                .where(PreHarvestStep.parcel_id == parcel.id)
                .order_by(PreHarvestStep.step_order.desc())
                .limit(1)
            ).first()
            parcels_payload.append(
                {
                    "parcel_name": str(parcel.name),
                    "member": str(parcel_member.full_name),
                    "culture": str(parcel.main_culture),
                    "surface_ha": round_metric(float(parcel.surface_ha or 0.0)),
                    "variety": str(parcel.variety or ""),
                    "pre_harvest_status": str(pre_status.value if hasattr(pre_status, "value") else pre_status or ""),
                }
            )
        fact_bundle["facts"].append(
            {"fact_type": "parcel_summary", "values": parcels_payload[:10], "source_table": "parcels,pre_harvest_steps"}
        )
        return fact_bundle

    if any(token in lowered for token in ("collecte", "collecté", "collection", "input", "inputs", "grade", "qualité", "qualite")):
        member, has_member_ref = _find_member_from_message(db, current_user=current_user, message=message)
        product_row, has_product_ref = _find_product_from_message(
            db,
            current_user=current_user,
            message=message,
            fallback_products=products,
        )
        if has_member_ref and member is None:
            fact_bundle["missing_reason"] = MISSING_ENTITY_SAFE_ANSWER
            return fact_bundle
        if has_product_ref and product_row is None:
            fact_bundle["missing_reason"] = MISSING_ENTITY_SAFE_ANSWER
            return fact_bundle
        if member:
            fact_bundle["facts"].append(_get_member_collection_total_fact(db, current_user=current_user, member=member))
            return fact_bundle
        if product_row:
            fact_bundle["facts"].append(_get_collection_by_product_fact(db, current_user=current_user, product=product_row))
            return fact_bundle
        if any(token in lowered for token in ("par produit", "by product", "produit", "product")):
            fact_bundle["facts"].append(_get_collection_totals_by_product_fact(db, current_user=current_user))
            return fact_bundle
        grade_rows = db.execute(
            select(Input.grade, func.count(Input.id), func.coalesce(func.sum(Input.quantity), 0.0))
            .where(Input.cooperative_id == current_user.cooperative_id)
            .group_by(Input.grade)
            .order_by(func.count(Input.id).desc())
        ).all()
        fact_bundle["facts"].append(
            {
                "fact_type": "collection_grade_distribution",
                "values": [
                    {"grade": str(grade), "count": int(count or 0), "quantity_kg": round_metric(float(qty or 0.0))}
                    for grade, count, qty in grade_rows
                ],
                "source_table": "inputs",
                "source_scope": "cooperative",
            }
        )
        return fact_bundle

    if any(token in lowered for token in ("recommandation", "recommendation", "priority", "priorité", "priorite")):
        rows = db.execute(
            select(Recommendation.risk_level, Recommendation.loss_pct, Recommendation.efficiency_pct, Recommendation.suggested_action, Batch.code, Product.name)
            .join(Batch, Batch.id == Recommendation.batch_id)
            .join(Product, Product.id == Batch.product_id)
            .where(Batch.cooperative_id == current_user.cooperative_id)
            .order_by(Recommendation.created_at.desc())
            .limit(10)
        ).all()
        fact_bundle["facts"].append(
            {
                "fact_type": "recommendation_summary",
                "values": [
                    {
                        "lot_code": str(code),
                        "product": str(product),
                        "risk_level": str(risk.value if hasattr(risk, "value") else risk),
                        "loss_pct": round_metric(float(loss or 0.0)),
                        "efficiency_pct": round_metric(float(eff or 0.0)),
                        "action": str(action),
                    }
                    for risk, loss, eff, action, code, product in rows
                ],
                "source_table": "recommendations,batches",
                "source_scope": "cooperative",
            }
        )
        return fact_bundle

    if any(token in lowered for token in ("commande", "order")):
        order, has_order_ref = _find_order_from_message(db, current_user=current_user, message=message)
        if has_order_ref and order is None and ORDER_NUMBER_PATTERN.findall(message):
            fact_bundle["missing_reason"] = MISSING_ENTITY_SAFE_ANSWER
            return fact_bundle
        if order:
            lines = db.execute(
                select(CommercialOrderLine.product_name_snapshot, func.coalesce(func.sum(CommercialOrderLine.quantity_kg), 0.0))
                .where(CommercialOrderLine.order_id == order.id)
                .group_by(CommercialOrderLine.product_name_snapshot)
            ).all()
            fact_bundle["facts"].append(
                {
                    "fact_type": "order_detail",
                    "values": {
                        "order_number": str(order.order_number),
                        "status": str(order.status.value if hasattr(order.status, "value") else order.status),
                        "customer": str(order.customer_name),
                        "total_fcfa": round_metric(float(order.total_amount_fcfa or 0.0)),
                        "quantities_by_product": [
                            {"product": str(product), "qty_kg": round_metric(float(qty or 0.0))}
                            for product, qty in lines
                        ],
                    },
                    "source_table": "commercial_orders,commercial_order_lines",
                }
            )
            return fact_bundle
        fact_bundle["facts"].append(_get_order_status_summary_fact(db, current_user=current_user))
        return fact_bundle

    if any(token in lowered for token in ("facture", "invoice")):
        invoice, has_invoice_ref = _find_invoice_from_message(db, current_user=current_user, message=message)
        if has_invoice_ref and invoice is None and INVOICE_NUMBER_PATTERN.findall(message):
            fact_bundle["missing_reason"] = MISSING_ENTITY_SAFE_ANSWER
            return fact_bundle
        if invoice:
            line_total = db.scalar(
                select(func.coalesce(func.sum(CommercialInvoiceLine.line_total_fcfa), 0.0)).where(
                    CommercialInvoiceLine.invoice_id == invoice.id
                )
            ) or 0.0
            fact_bundle["facts"].append(
                {
                    "fact_type": "invoice_detail",
                    "values": {
                        "invoice_number": str(invoice.invoice_number),
                        "status": str(invoice.status.value if hasattr(invoice.status, "value") else invoice.status),
                        "issue_date": str(invoice.issue_date),
                        "due_date": str(invoice.due_date or ""),
                        "customer": str(invoice.customer_name_snapshot),
                        "total_fcfa": round_metric(float(invoice.total_amount_fcfa or 0.0)),
                        "lines_total_fcfa": round_metric(float(line_total)),
                    },
                    "source_table": "commercial_invoices,commercial_invoice_lines",
                }
            )
            return fact_bundle
        fact_bundle["facts"].append(_get_invoice_status_summary_fact(db, current_user=current_user))
        return fact_bundle

    if any(token in lowered for token in ("trésorerie", "tresorerie", "charges", "charge", "catégorie", "categorie", "avance", "advances", "balance", "coût", "cout", "cost")):
        if any(token in lowered for token in ("catégorie", "categorie", "category", "by category", "par catégorie", "par categorie")):
            fact_bundle["facts"].append(_get_charges_by_category_fact(db, current_user=current_user))
            return fact_bundle
        fact_bundle["facts"].append(_get_finance_summary_fact(db, current_user=current_user))
        return fact_bundle

    if any(token in lowered for token in ("ml", "prediction", "predictions", "prédiction", "prédictions", "risk prediction", "anomalie", "anomaly")):
        return _ok(_get_ml_latest_fact(db))

    fact_bundle["missing_reason"] = MISSING_ENTITY_SAFE_ANSWER
    return fact_bundle


def _build_sql_only_answer_from_facts(*, message: str, facts: Sequence[dict[str, Any]], language: str) -> str:
    if not facts:
        return MISSING_ENTITY_SAFE_ANSWER
    fact = facts[0]
    fact_type = str(fact.get("fact_type") or "")
    if fact_type == "product_stock":
        product = str(fact.get("product") or "product")
        values = fact.get("values", {})
        unit = str(fact.get("units", {}).get("stock", "kg"))
        return (
            f"Stock {product} : total {values.get('total_stock', 0)} {unit}, "
            f"{values.get('reserved_in_lots', 0)} {unit} réservés dans les lots, "
            f"{values.get('remaining_stock', 0)} {unit} disponibles. "
            f"Statut : {values.get('status', 'inconnu')}."
        )
    if fact_type == "batch_status":
        values = fact.get("values", {})
        unit = str(fact.get("units", {}).get("quantity", "kg"))
        return (
            f"{fact.get('lot_code', 'Lot')} ({fact.get('product', 'produit')}) : statut {values.get('status', 'inconnu')}, "
            f"quantité initiale {values.get('initial_qty', 0)} {unit}, quantité actuelle {values.get('current_qty', 0)} {unit}, "
            f"perte cumulée {values.get('cumulative_loss_pct', 0)}%, dernière étape {values.get('latest_step', 'aucune')}, "
            f"étape en attente {values.get('pending_step', 'aucune')}, anomalie/risque {values.get('risk_or_anomaly', 'aucun')}."
        )
    if fact_type == "active_lots":
        return f"Lots actifs en cours: {fact.get('values', {}).get('active_lots', 0)}."
    if fact_type == "completed_lots":
        return f"Nombre de lots complétés : {fact.get('values', {}).get('completed_lots', 0)}."
    if fact_type == "member_list":
        rows = fact.get("values", [])
        if not rows:
            return "Aucun membre trouvé pour cette coopérative."
        return f"{len(rows)} membres trouvés. Voir le tableau pour le détail."
    if fact_type == "lot_table":
        rows = fact.get("values", [])
        if not rows:
            active_only = bool((fact.get("filters") or {}).get("active_only"))
            return "Aucun lot actif disponible pour cette coopérative." if active_only else "Aucun lot disponible pour cette coopérative."
        return f"{len(rows)} lots trouvés. Voir le tableau pour le détail."
    if fact_type == "member_detail":
        values = fact.get("values", {})
        return (
            f"Membre {fact.get('member_name','')} ({fact.get('member_code','')}) : "
            f"statut {values.get('status','')}, village {values.get('village','')}, "
            f"produit principal {values.get('main_product','')}, "
            f"{values.get('parcel_count',0)} parcelles ({values.get('area_hectares',0)} ha)."
        )
    if fact_type == "member_collection_total":
        values = fact.get("values", {})
        return (
            f"Collecte cumulée — {fact.get('member_name','')} ({fact.get('member_code','')}) : "
            f"{values.get('total_collection_kg',0)} kg, valeur estimée {values.get('estimated_value_fcfa',0)} FCFA."
        )
    if fact_type == "member_parcels":
        values = fact.get("values", {})
        parcel_rows = values.get("parcels", [])
        sample = ", ".join(
            f"{item.get('name','')} ({item.get('culture','')}, {item.get('surface_ha',0)} ha)"
            for item in parcel_rows[:5]
        )
        return (
            f"Parcelles exploitées par {fact.get('member_name','')} ({fact.get('member_code','')}) : "
            f"{values.get('parcel_count',0)} parcelles. {sample}."
        )
    if fact_type == "member_advance_total":
        values = fact.get("values", {})
        return (
            f"Avances actives de {fact.get('member_name','')} ({fact.get('member_code','')}) : "
            f"{values.get('active_advances_fcfa',0)} FCFA."
        )
    if fact_type == "parcel_summary":
        rows = fact.get("values", [])[:6]
        if not rows:
            return MISSING_ENTITY_SAFE_ANSWER
        sample = ", ".join(
            f"{row.get('parcel_name','')} ({row.get('culture','')}, {row.get('surface_ha',0)} ha, statut pré-récolte {row.get('pre_harvest_status','') or 'n/a'})"
            for row in rows
        )
        return f"Parcelles (extrait) : {sample}."
    if fact_type == "collection_by_product":
        values = fact.get("values", {})
        return (
            f"Collecte totale pour {fact.get('product','')} : "
            f"{values.get('total_collected_kg',0)} kg, valeur estimée {values.get('estimated_value_fcfa',0)} FCFA."
        )
    if fact_type == "collection_grade_distribution":
        rows = fact.get("values", [])[:6]
        if not rows:
            return MISSING_ENTITY_SAFE_ANSWER
        return "Distribution des grades : " + "; ".join(
            f"{row.get('grade','')}={row.get('count',0)} entrées ({row.get('quantity_kg',0)} kg)"
            for row in rows
        ) + "."
    if fact_type == "collection_totals_by_product":
        rows = fact.get("values", [])[:8]
        if not rows:
            return MISSING_ENTITY_SAFE_ANSWER
        return "Collecte totale par produit : " + "; ".join(
            f"{row.get('product','')}={row.get('total_collected_kg',0)} kg"
            for row in rows
        ) + "."
    if fact_type == "stage_loss_summary":
        rows = fact.get("values", [])[:6]
        if not rows:
            return MISSING_ENTITY_SAFE_ANSWER
        return "Pertes moyennes par étape : " + "; ".join(
            f"{row.get('stage','')}={row.get('avg_loss_pct',0)}%" for row in rows
        ) + "."
    if fact_type == "recommendation_summary":
        rows = fact.get("values", [])[:5]
        if not rows:
            return MISSING_ENTITY_SAFE_ANSWER
        return "Recommandations actives (extrait) : " + "; ".join(
            f"{row.get('lot_code','')} {row.get('product','')} [{row.get('risk_level','')}] action: {row.get('action','')}"
            for row in rows
        ) + "."
    if fact_type == "order_status_summary":
        values = fact.get("values", {})
        if not values:
            return MISSING_ENTITY_SAFE_ANSWER
        return "Statut des commandes : " + "; ".join(f"{k}={v}" for k, v in values.items()) + "."
    if fact_type == "order_detail":
        values = fact.get("values", {})
        prod = values.get("quantities_by_product", [])
        prod_txt = ", ".join(f"{item.get('product','')}:{item.get('qty_kg',0)} kg" for item in prod[:5])
        return (
            f"Commande {values.get('order_number','')} : statut {values.get('status','')}, "
            f"client {values.get('customer','')}, total {values.get('total_fcfa',0)} FCFA. "
            f"Quantités: {prod_txt}."
        )
    if fact_type == "invoice_status_summary":
        rows = fact.get("values", [])
        if not rows:
            return MISSING_ENTITY_SAFE_ANSWER
        return "Synthèse factures : " + "; ".join(
            f"{row.get('status','')}={row.get('count',0)} ({row.get('amount_fcfa',0)} FCFA)"
            for row in rows
        ) + "."
    if fact_type == "invoice_detail":
        values = fact.get("values", {})
        return (
            f"Facture {values.get('invoice_number','')} : statut {values.get('status','')}, "
            f"émise le {values.get('issue_date','')}, échéance {values.get('due_date','') or 'n/a'}, "
            f"client {values.get('customer','')}, total {values.get('total_fcfa',0)} FCFA."
        )
    if fact_type == "finance_summary":
        values = fact.get("values", {})
        return (
            f"Finance: charges {values.get('total_charges_fcfa',0)} FCFA, avances actives {values.get('active_advances_fcfa',0)} FCFA, "
            f"revenus {values.get('income_fcfa',0)} FCFA, dépenses {values.get('expense_fcfa',0)} FCFA, "
            f"solde {values.get('balance_fcfa',0)} FCFA."
        )
    if fact_type == "charges_by_category":
        rows = fact.get("values", [])[:8]
        if not rows:
            return MISSING_ENTITY_SAFE_ANSWER
        return "Charges par catégorie : " + "; ".join(
            f"{row.get('category','')}={row.get('amount_fcfa',0)} FCFA" for row in rows
        ) + "."
    if fact_type == "ml_latest_prediction":
        values = fact.get("values", {})
        return (
            f"Dernière prédiction ML: produit {values.get('product','')}, étape {values.get('critical_stage','')}, "
            f"perte prédite {values.get('predicted_loss_pct',0)}%, risque {values.get('risk_level','')}, "
            f"score anomalie {values.get('anomaly_score',0)}, modèle {values.get('model_version','')}."
        )
    return MISSING_ENTITY_SAFE_ANSWER


def list_reference_metrics(
    db: Session,
    *,
    q: Optional[str] = None,
    country: Optional[str] = None,
    region: Optional[str] = None,
    crop: Optional[str] = None,
    metric: Optional[str] = None,
    limit: int = 50,
) -> ReferenceMetricListResponse:
    stmt = _apply_metric_filters(
        select(ReferenceMetric),
        q=q,
        country=country,
        region=region,
        crop=crop,
        metric=metric,
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(ReferenceMetric.crop.asc(), ReferenceMetric.metric.asc(), ReferenceMetric.period.desc()).limit(limit)
    ).all()
    return ReferenceMetricListResponse(total=int(total), items=[ReferenceMetricRead.model_validate(item) for item in items])


def list_knowledge_chunks(
    db: Session,
    *,
    q: Optional[str] = None,
    country: Optional[str] = None,
    region: Optional[str] = None,
    crop: Optional[str] = None,
    topic: Optional[str] = None,
    limit: int = 50,
) -> KnowledgeChunkListResponse:
    stmt = _apply_knowledge_filters(
        select(KnowledgeChunk),
        q=q,
        country=country,
        region=region,
        crop=crop,
        topic=topic,
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(KnowledgeChunk.crop.asc(), KnowledgeChunk.topic.asc(), KnowledgeChunk.region.asc()).limit(limit)
    ).all()
    return KnowledgeChunkListResponse(total=int(total), items=[KnowledgeChunkRead.model_validate(item) for item in items])


def list_chat_sessions(db: Session, current_user: User, *, limit: int = 30) -> List[ChatSessionRead]:
    sessions = db.scalars(
        select(ChatSession).where(ChatSession.user_id == current_user.id).order_by(ChatSession.updated_at.desc()).limit(limit)
    ).all()
    if not sessions:
        return []

    session_ids = [session.id for session in sessions]
    counts = {
        session_id: count
        for session_id, count in db.execute(
            select(ChatMessage.session_id, func.count(ChatMessage.id))
            .where(ChatMessage.session_id.in_(session_ids))
            .group_by(ChatMessage.session_id)
        )
    }

    last_messages = _get_last_messages_by_session(db, session_ids)
    return [
        ChatSessionRead(
            id=session.id,
            title=session.title,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=int(counts.get(session.id, 0)),
            last_message_preview=_trim_text(last_messages[session.id].content, 120) if session.id in last_messages else None,
            last_message_at=last_messages[session.id].created_at if session.id in last_messages else None,
        )
        for session in sessions
    ]


def create_chat_session(db: Session, current_user: User, *, title: Optional[str] = None) -> ChatSessionRead:
    session = ChatSession(
        user_id=current_user.id,
        cooperative_id=current_user.cooperative_id,
        title=_normalize_title(title) or "New conversation",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return ChatSessionRead(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=0,
        last_message_preview=None,
        last_message_at=None,
    )


def delete_chat_session(db: Session, current_user: User, session_id: UUID) -> None:
    session = _require_owned_session(db, current_user, session_id)
    db.delete(session)
    db.commit()


def list_chat_messages(db: Session, current_user: User, session_id: UUID, *, limit: int = 200) -> List[ChatMessageRead]:
    session = _require_owned_session(db, current_user, session_id)
    messages = db.scalars(
        select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at.asc()).limit(limit)
    ).all()
    return [_to_message_read(message) for message in messages]


def debug_retrieval_context(
    db: Session,
    *,
    current_user: User,
    message: str,
    top_k: int = 6,
) -> dict[str, Any]:
    retrieval_plan = build_retrieval_plan(message, mode=_classify_response_mode(message))
    retrieval_filters = _build_retrieval_filters(message=message, retrieval_plan=retrieval_plan)
    retrieval_diagnostics: dict[str, Any] = summarize_retrieval(filters=retrieval_filters, hits=[])
    hits: list[RetrievalHit] = []
    if retrieval_plan.rag_needed:
        hits = _retrieve_rag_hits(
            db,
            current_user=current_user,
            message=message,
            limit=min(max(top_k, 1), 8),
            retrieval_filters=retrieval_filters,
        )
        retrieval_diagnostics = summarize_retrieval(filters=retrieval_filters, hits=hits)

    sql_metrics = _build_operational_context_metrics(
        db,
        current_user=current_user,
        message=message,
        retrieval_plan=retrieval_plan,
        retrieval_filters=retrieval_filters,
        query_tokens=set(_tokenize(message)),
        region_hint=None,
    )
    orchestrated = orchestrate_context(
        db,
        current_user=current_user,
        retrieval_plan=retrieval_plan,
        message=message,
        retrieval_hits=hits,
        context_metrics=sql_metrics,
        retrieval_filters=retrieval_filters,
    )
    return {
        "retrieval_plan": {
            "intent_type": retrieval_plan.intent_type,
            "confidence": retrieval_plan.confidence,
            "sql_needed": retrieval_plan.sql_needed,
            "rag_needed": retrieval_plan.rag_needed,
            "reason": retrieval_plan.reason,
            "suggested_sql_domains": retrieval_plan.suggested_sql_domains,
            "suggested_rag_chunk_types": retrieval_plan.suggested_rag_chunk_types,
            "detected_entities": retrieval_plan.detected_entities,
            "safety_notes": retrieval_plan.safety_notes,
        },
        "filters": retrieval_filters,
        "retrieval_diagnostics": retrieval_diagnostics,
        "orchestration": {
            "warning_flags": orchestrated.warning_flags,
            "confidence_estimate": orchestrated.confidence_estimate,
            "contradictory_signals": orchestrated.contradictory_signals,
            "grounding_notes": orchestrated.grounding_notes,
            "scope_analysis": getattr(orchestrated, "scope_analysis", {}),
            "contamination_diagnostics": getattr(orchestrated, "contamination_diagnostics", {}),
        },
        "hits": [
            {
                "chunk_id": hit.chunk_id,
                "source_table": hit.source_table,
                "source_record_ref": hit.source_record_ref,
                "chunk_type": _infer_chunk_type(
                    chunk_type=hit.metadata.get("chunk_type"),
                    entity=hit.metadata.get("entity"),
                    source_table=hit.source_table,
                ),
                "freshness_timestamp": hit.metadata.get("freshness_timestamp"),
                "freshness_age_minutes": round_metric(hit.freshness_age_minutes or 0.0),
                "retrieval_score": round_metric(hit.rerank_score),
                "retrieval_reason": hit.retrieval_reason,
            }
            for hit in hits
        ],
    }


def _hybrid_query_requires_external_evidence(message: str) -> bool:
    normalized = " ".join(str(message or "").lower().split()).replace("-", " ")
    strong_analysis_hints = (
        "pourquoi",
        "why",
        "explique",
        "expliquer",
        "explain",
        "compare",
        "comparer",
        "risque",
        "risk",
        "anomalie",
        "anomaly",
    )
    if any(hint in normalized for hint in strong_analysis_hints):
        return True

    evidence_hints = (
        "source",
        "sources",
        "reference",
        "references",
        "référence",
        "références",
        "benchmark",
        "bonnes pratiques",
        "meilleures pratiques",
        "conseils",
        "post recolte",
        "post récolte",
        "conservation",
    )
    return any(hint in normalized for hint in evidence_hints)


def generate_chat_reply(
    db: Session,
    *,
    current_user: User,
    message: str,
    session_id: Optional[UUID] = None,
    top_k: int = 4,
) -> ChatResponse:
    session = _resolve_session(db, current_user, session_id=session_id, seed_text=message)
    history = _get_recent_messages(db, session.id, limit=12)
    response_mode = _classify_response_mode(message)
    response_language = _detect_response_language(message)
    retrieval_plan = build_retrieval_plan(message, mode=response_mode)
    # Hard-route deterministic directory/table asks to SQL_ONLY to prevent hybrid drift.
    if _is_member_list_request(message) or _is_lot_table_request(message):
        retrieval_plan = RetrievalPlan(
            intent_type=RetrievalIntentType.SQL_ONLY.value,
            confidence=max(0.9, retrieval_plan.confidence),
            sql_needed=True,
            rag_needed=False,
            reason="Deterministic SQL table/list request detected.",
            suggested_sql_domains=["members"] if _is_member_list_request(message) else ["batches", "losses"],
            suggested_rag_chunk_types=[],
            detected_entities=retrieval_plan.detected_entities,
            safety_notes=retrieval_plan.safety_notes,
        )
    if (
        response_mode == "quick"
        and retrieval_plan.intent_type == RetrievalIntentType.SQL_ONLY.value
        and any(token in message.lower() for token in ("stock", "status", "lot", "batch", "invoice", "member", "active"))
    ):
        response_mode = "operational"
        retrieval_plan = build_retrieval_plan(message, mode=response_mode)
    query_tokens = set(_tokenize(message))
    retrieval_filters = _build_retrieval_filters(message=message, retrieval_plan=retrieval_plan)

    user_message = ChatMessage(session_id=session.id, role="user", content=message)
    db.add(user_message)
    db.flush()

    follow_up_with_operational_context = (
        retrieval_plan.intent_type == RetrievalIntentType.CLARIFICATION_NEEDED.value
        and _history_has_operational_context(history)
    )
    if retrieval_plan.intent_type in {
        RetrievalIntentType.SMALL_TALK.value,
        RetrievalIntentType.UNSUPPORTED.value,
    } or (
        retrieval_plan.intent_type == RetrievalIntentType.CLARIFICATION_NEEDED.value and not follow_up_with_operational_context
    ):
        safe_mode_map = {
            RetrievalIntentType.SMALL_TALK.value: "small_talk",
            RetrievalIntentType.CLARIFICATION_NEEDED.value: "clarification_needed",
            RetrievalIntentType.UNSUPPORTED.value: "unsupported",
        }
        safe_answer = _build_non_operational_answer(message=message, retrieval_plan=retrieval_plan, language=response_language)
        assistant_message = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=safe_answer,
            mode=safe_mode_map.get(retrieval_plan.intent_type, "fallback"),
            llm_provider=None,
            llm_model=None,
            citations_json=[],
            context_metrics_json=[],
            dashboard_json=None,
            ui_blocks_json=[],
        )
        db.add(assistant_message)
        session.updated_at = current_utc()
        db.commit()
        db.refresh(user_message)
        db.refresh(assistant_message)
        return ChatResponse(
            success=True,
            session_id=session.id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            message=safe_answer,
            grounded=False,
            mode=safe_mode_map.get(retrieval_plan.intent_type, "fallback"),
            llm_provider=None,
            llm_model=None,
            citations=[],
            context_metrics=[],
            dashboard=None,
            ui_blocks=[],
        )

    if retrieval_plan.intent_type in {
        RetrievalIntentType.SQL_ONLY.value,
        RetrievalIntentType.HYBRID.value,
        RetrievalIntentType.RAG_ONLY.value,
    }:
        existence = _validate_requested_entities_existence(
            db,
            current_user=current_user,
            message=message,
            retrieval_plan=retrieval_plan,
        )
        if not existence.get("valid", True):
            cooperative = _get_cooperative(db, current_user)
            region = str(cooperative.region) if cooperative and cooperative.region else "cooperative"
            context_metrics = _build_retrieval_plan_metrics(retrieval_plan, region=region)
            if retrieval_plan.intent_type == RetrievalIntentType.RAG_ONLY.value:
                missing_answer = (
                    "Aucune preuve benchmark/agronomique n'a été récupérée pour cette question. "
                    "Je ne peux pas fournir une réponse de référence fiable pour le moment."
                )
                mode = "rag_only_no_evidence"
            else:
                missing_answer = MISSING_ENTITY_SAFE_ANSWER
                mode = "sql_only_no_data" if retrieval_plan.intent_type == RetrievalIntentType.SQL_ONLY.value else "hybrid_no_data"
            assistant_message = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=missing_answer,
                mode=mode,
                llm_provider=None,
                llm_model=None,
                citations_json=[],
                context_metrics_json=[metric.model_dump() for metric in context_metrics],
                dashboard_json=None,
                ui_blocks_json=[],
            )
            db.add(assistant_message)
            session.updated_at = current_utc()
            db.commit()
            db.refresh(user_message)
            db.refresh(assistant_message)
            return ChatResponse(
                success=True,
                session_id=session.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                message=missing_answer,
                grounded=False,
                mode=mode,
                llm_provider=None,
                llm_model=None,
                citations=[],
                context_metrics=context_metrics,
                dashboard=None,
                ui_blocks=[],
            )

    manager_snapshot = _build_dashboard_snapshot(db, current_user)
    cooperative = _get_cooperative(db, current_user)
    region_hint = cooperative.region if cooperative else manager_snapshot.region if manager_snapshot else None
    retrieval_hits: list[RetrievalHit] = []
    reference_context = ReferenceContext(citations=[], metrics=[])
    sql_only_fact_bundle: dict[str, Any] = {"facts": [], "missing_reason": None}
    if response_mode != "quick" and retrieval_plan.rag_needed:
        retrieval_hits = _retrieve_rag_hits(
            db,
            current_user=current_user,
            message=message,
            limit=min(max(top_k, 1), 8),
            retrieval_filters=retrieval_filters,
        )
        reference_context = _retrieve_reference_context(
            db,
            message=message,
            cooperative=cooperative,
            limit=min(max(top_k, 1), 8),
        )
    if response_mode != "quick" and retrieval_plan.intent_type == RetrievalIntentType.SQL_ONLY.value:
        sql_only_fact_bundle = _build_sql_only_fact_bundle(
            db,
            current_user=current_user,
            message=message,
            retrieval_plan=retrieval_plan,
        )

    rag_citations = _citations_from_hits(retrieval_hits, cooperative=cooperative)
    citations = _dedupe_citations([*rag_citations, *reference_context.citations], limit=10)
    operational_metrics: list[ChatMetricFact] = []
    if retrieval_plan.sql_needed or response_mode == "quick":
        operational_metrics = _build_operational_context_metrics(
            db,
            current_user=current_user,
            message=message,
            retrieval_plan=retrieval_plan,
            retrieval_filters=retrieval_filters,
            query_tokens=query_tokens,
            region_hint=region_hint,
        )
    if (
        response_mode != "quick"
        and retrieval_plan.intent_type == RetrievalIntentType.SQL_ONLY.value
        and not retrieval_plan.rag_needed
        and not operational_metrics
    ):
        reference_context = _retrieve_reference_context(
            db,
            message=message,
            cooperative=cooperative,
            limit=min(max(top_k, 1), 4),
        )
        citations = _dedupe_citations([*rag_citations, *reference_context.citations], limit=10)
    if retrieval_plan.intent_type == RetrievalIntentType.HYBRID.value and not citations and operational_metrics:
        citations = _dedupe_citations(
            [
                *citations,
                *_build_sql_evidence_citations(
                    operational_metrics=operational_metrics,
                    cooperative=cooperative,
                    limit=4,
                ),
            ],
            limit=10,
        )

    retrieval_diagnostics = summarize_retrieval(filters=retrieval_filters, hits=retrieval_hits)
    retrieval_diagnostics["top_hit_provenance"] = _summarize_retrieval_provenance(retrieval_hits, limit=5)
    orchestrated_context = orchestrate_context(
        db,
        current_user=current_user,
        retrieval_plan=retrieval_plan,
        message=message,
        retrieval_hits=retrieval_hits,
        context_metrics=[*reference_context.metrics, *operational_metrics],
        retrieval_filters=retrieval_filters,
    )
    context_metrics = _build_context_metrics(
        manager_snapshot,
        region_hint=region_hint,
        rag_hit_count=len(retrieval_hits),
        reference_metrics=reference_context.metrics,
        operational_metrics=operational_metrics,
        retrieval_plan=retrieval_plan,
        retrieval_diagnostics=retrieval_diagnostics,
        orchestrated_context=orchestrated_context,
    )
    ui_blocks: list[ChatUIBlock] = []
    if retrieval_plan.sql_needed or response_mode == "quick":
        ui_blocks = _build_ui_blocks(db, current_user=current_user, message=message, dashboard=manager_snapshot)
    ui_blocks = _build_executive_ui_blocks(
        message=message,
        retrieval_plan=retrieval_plan,
        dashboard=manager_snapshot,
        context_metrics=context_metrics,
        citations=citations,
        orchestrated_context=orchestrated_context,
        fallback_blocks=ui_blocks,
    )

    mode = "unsupported" if retrieval_plan.intent_type == RetrievalIntentType.UNSUPPORTED.value else "fallback"
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    answer = (
        _build_unsupported_scope_answer(response_language)
        if retrieval_plan.intent_type == RetrievalIntentType.UNSUPPORTED.value
        else _build_fallback_answer(
            message,
            manager_snapshot,
            citations,
            response_mode=response_mode,
            language=response_language,
        )
    )
    if (
        retrieval_plan.intent_type == RetrievalIntentType.SQL_ONLY.value
        and response_mode != "quick"
        and sql_only_fact_bundle.get("facts")
    ):
        answer = _build_sql_only_answer_from_facts(
            message=message,
            facts=sql_only_fact_bundle.get("facts", []),
            language=response_language,
        )
        citations = []
        mode = "sql_only"
    elif (
        retrieval_plan.intent_type == RetrievalIntentType.SQL_ONLY.value
        and response_mode != "quick"
        and not sql_only_fact_bundle.get("facts")
    ):
        answer = str(sql_only_fact_bundle.get("missing_reason") or "Aucune donnée SQL trouvée pour cette demande.")
        citations = []
        mode = "sql_only_no_data"
    if (
        retrieval_plan.intent_type == RetrievalIntentType.RAG_ONLY.value
        and not citations
    ):
        answer = (
            "Aucune preuve benchmark/agronomique n'a été récupérée pour cette question. "
            "Je ne peux pas fournir une réponse de référence fiable pour le moment."
        )
        mode = "rag_only_no_evidence"
    if (
        response_mode != "quick"
        and (
        retrieval_plan.intent_type == RetrievalIntentType.HYBRID.value
        and not citations
        )
    ):
        hybrid_requires_evidence = _hybrid_query_requires_external_evidence(message)
        has_sql_grounding = bool(
            sql_only_fact_bundle.get("facts")
            or operational_metrics
            or retrieval_plan.sql_needed
            or int(orchestrated_context.sql_context.get("metric_count", 0) or 0) > 0
        )
        if hybrid_requires_evidence or not has_sql_grounding:
            answer = (
                "Aucune preuve de référence n'a été récupérée pour étayer cette analyse opérationnelle. "
                "Je ne peux pas fournir une synthèse HYBRID fiable pour le moment."
            )
            mode = "hybrid_no_evidence"
        else:
            mode = "hybrid_sql_grounded"

    if (
        retrieval_plan.intent_type != RetrievalIntentType.UNSUPPORTED.value
        and mode not in {"sql_only", "sql_only_no_data", "rag_only_no_evidence", "hybrid_no_evidence"}
    ):
        try:
            llm_answer = _build_llm_answer(
                message=message,
                history=history,
                dashboard=manager_snapshot,
                citations=citations,
                context_metrics=context_metrics,
                cooperative=cooperative,
                response_mode=response_mode,
                language=response_language,
                orchestrated_context=orchestrated_context,
            )
            if llm_answer:
                answer = llm_answer
                mode = "llm-rag" if citations else "llm"
                llm_provider = settings.llm_provider
                llm_model = settings.llm_model
        except ValidationError:
            answer = _build_llm_unavailable_answer(
                message=message,
                retrieval_plan=retrieval_plan,
                citations=citations,
                context_metrics=context_metrics,
                language=response_language,
            )
            mode = "fallback_rag" if citations else "fallback"

    assistant_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer,
        mode=mode,
        llm_provider=llm_provider,
        llm_model=llm_model,
        citations_json=[citation.model_dump() for citation in citations],
        context_metrics_json=[metric.model_dump() for metric in context_metrics],
        dashboard_json=manager_snapshot.model_dump() if manager_snapshot else None,
        ui_blocks_json=[block.model_dump() for block in ui_blocks],
    )
    db.add(assistant_message)
    session.updated_at = current_utc()
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)

    return ChatResponse(
        success=True,
        session_id=session.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        message=answer,
        grounded=bool(citations),
        mode=mode,
        llm_provider=llm_provider,
        llm_model=llm_model,
        citations=citations,
        context_metrics=context_metrics,
        dashboard=manager_snapshot,
        ui_blocks=ui_blocks,
    )


def _apply_metric_filters(
    stmt: Select,
    *,
    q: Optional[str],
    country: Optional[str],
    region: Optional[str],
    crop: Optional[str],
    metric: Optional[str],
) -> Select:
    if country:
        stmt = stmt.where(ReferenceMetric.country == country)
    if region:
        stmt = stmt.where(ReferenceMetric.region.ilike(region))
    if crop:
        stmt = stmt.where(ReferenceMetric.crop.ilike(crop))
    if metric:
        stmt = stmt.where(ReferenceMetric.metric.ilike(metric))
    if q:
        like_term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                ReferenceMetric.source_id.ilike(like_term),
                ReferenceMetric.region.ilike(like_term),
                ReferenceMetric.crop.ilike(like_term),
                ReferenceMetric.metric.ilike(like_term),
                ReferenceMetric.notes.ilike(like_term),
            )
        )
    return stmt


def _apply_knowledge_filters(
    stmt: Select,
    *,
    q: Optional[str],
    country: Optional[str],
    region: Optional[str],
    crop: Optional[str],
    topic: Optional[str],
) -> Select:
    if country:
        stmt = stmt.where(KnowledgeChunk.country == country)
    if region:
        stmt = stmt.where(KnowledgeChunk.region.ilike(region))
    if crop:
        stmt = stmt.where(KnowledgeChunk.crop.ilike(crop))
    if topic:
        stmt = stmt.where(KnowledgeChunk.topic.ilike(topic))
    if q:
        like_term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                KnowledgeChunk.source_id.ilike(like_term),
                KnowledgeChunk.region.ilike(like_term),
                KnowledgeChunk.crop.ilike(like_term),
                KnowledgeChunk.topic.ilike(like_term),
                KnowledgeChunk.content.ilike(like_term),
            )
        )
    return stmt


def _build_dashboard_snapshot(db: Session, current_user: User) -> Optional[ChatDashboardSnapshot]:
    if current_user.role != UserRole.MANAGER:
        return None

    dashboard = analytics_service.get_dashboard(db, current_user)
    cooperative = _get_cooperative(db, current_user)
    return ChatDashboardSnapshot(
        cooperative_name=cooperative.name if cooperative else None,
        region=cooperative.region if cooperative else None,
        total_production=dashboard.total_production,
        loss_rate=dashboard.loss_rate,
        efficiency_rate=dashboard.efficiency_rate,
        number_of_active_batches=dashboard.number_of_active_batches,
        stock_alerts=len(dashboard.stock_alerts),
    )


def _get_cooperative(db: Session, current_user: User) -> Optional[Cooperative]:
    if current_user.cooperative_id is None:
        return None
    stmt = select(Cooperative).where(Cooperative.id == current_user.cooperative_id)
    return db.scalar(stmt)


def _resolve_session(
    db: Session,
    current_user: User,
    *,
    session_id: Optional[UUID],
    seed_text: str,
) -> ChatSession:
    if session_id:
        return _require_owned_session(db, current_user, session_id)

    new_session = ChatSession(
        user_id=current_user.id,
        cooperative_id=current_user.cooperative_id,
        title=_derive_title(seed_text),
    )
    db.add(new_session)
    db.flush()
    return new_session


def _require_owned_session(db: Session, current_user: User, session_id: UUID) -> ChatSession:
    session = db.scalar(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == current_user.id))
    if session is None:
        raise NotFoundError("Chat session not found.")
    return session


def _get_recent_messages(db: Session, session_id: UUID, *, limit: int) -> List[ChatMessage]:
    rows = db.scalars(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.desc()).limit(limit)
    ).all()
    rows.reverse()
    return rows


def _build_llm_answer(
    *,
    message: str,
    history: Sequence[ChatMessage],
    dashboard: Optional[ChatDashboardSnapshot],
    citations: Sequence[ChatCitation],
    context_metrics: Sequence[ChatMetricFact],
    cooperative: Optional[Cooperative],
    response_mode: str,
    language: str,
    orchestrated_context: Any,
) -> Optional[str]:
    client = get_llm_client()
    style_guidance = _build_response_style_guidance(response_mode)
    language_instruction = "Réponds uniquement en français."

    prompt_messages = [
        {
            "role": "system",
            "content": (
                f"You are WeeFarm manager assistant. {language_instruction} "
                "Use only chat memory from this session and the provided context. "
                "Reference snippets are retrieved from the cooperative database. "
                "Do not invent numbers not present in the context. "
                "Follow the response style guidance exactly. "
                "Reasoning order is mandatory: operational evidence first, recommendations second, "
                "benchmark comparison third, ML interpretation fourth. "
                "When multiple scopes exist, separate them explicitly as: "
                "'For the specific lot...', 'At product-stage level...', "
                "'At cooperative level...', and 'Compared with benchmark...'. "
                "Do not mix unrelated products in causal reasoning."
                "If uncertain, state uncertainty and provide a practical next step."
            ),
        }
    ]

    for previous in history:
        if previous.role not in {"user", "assistant"}:
            continue
        prompt_messages.append({"role": previous.role, "content": previous.content})

    prompt_messages.append(
        {
            "role": "user",
            "content": (
                f"Question manager: {message}\n\n"
                f"Contexte cooperative: { {'name': cooperative.name if cooperative else None, 'region': cooperative.region if cooperative else None} }\n"
                f"Snapshot dashboard: {dashboard.model_dump() if dashboard else None}\n"
                f"References recuperees: {[citation.model_dump() for citation in citations]}\n"
                f"Metriques contexte: {[metric.model_dump() for metric in context_metrics]}\n"
                f"Orchestrated context: {orchestrated_context}\n"
                f"Response mode: {response_mode}\n"
                f"Language: {language}\n"
                f"Style guidance: {style_guidance}\n"
                "Grounding policy: prioritize SQL facts over semantic summaries when they conflict. "
                "Scope policy: prioritize lot/product/stage evidence before cooperative-wide and benchmark evidence. "
                "Do not let unrelated products contaminate product-specific reasoning. "
                "When reporting metrics, explicitly mark whether each metric applies to lot, product-stage, product, "
                "cooperative, or benchmark scope. "
                "If cooperative-level metrics include unrelated products, state that directly. "
                "Acknowledge uncertainty when evidence is stale, limited, or contradictory. "
                "When contradiction exists, explain whether cooperative-wide metrics may include unrelated products. "
                "Do not invent numeric values."
            ),
        }
    )

    response = client.chat(prompt_messages)
    return response.content.strip() if response.content else None


def _build_fallback_answer(
    message: str,
    dashboard: Optional[ChatDashboardSnapshot],
    citations: Sequence[ChatCitation],
    *,
    response_mode: str,
    language: str,
) -> str:
    if response_mode == "quick":
        return "LLM indisponible. Réponse rapide : " + _solve_basic_math_or_echo(message)

    if _is_member_list_request(message):
        return "Le fournisseur LLM est indisponible. Les données membres sont fournies en tableau SQL."
    if _is_lot_table_request(message):
        return "Le fournisseur LLM est indisponible. Les données lots sont fournies en tableau SQL."

    if language == "fr":
        if dashboard:
            base = (
                "Je n'ai pas pu joindre le fournisseur LLM. "
                f"Contexte actuel: pertes {dashboard.loss_rate:.1f}%, "
                f"efficacite {dashboard.efficiency_rate:.1f}%, production {dashboard.total_production:.1f} kg."
            )
        else:
            base = "Je n'ai pas pu joindre le fournisseur LLM pour le moment."

        if citations:
            reference = f"Reference disponible: {citations[0].source_id} ({citations[0].topic})."
        else:
            reference = "Aucun extrait RAG disponible."

        return (
            f"{base} Requete: {_trim_text(message, 180)}. "
            f"{reference} Prochaine action: confirmer les donnees terrain du lot concerne."
        )

    if dashboard:
        base = (
            "Je n'ai pas pu joindre le fournisseur LLM. "
            f"Contexte actuel : pertes {dashboard.loss_rate:.1f}%, "
            f"efficacité {dashboard.efficiency_rate:.1f}%, production {dashboard.total_production:.1f} kg."
        )
    else:
        base = "Je n'ai pas pu joindre le fournisseur LLM pour le moment."

    if citations:
        reference = f"Référence disponible : {citations[0].source_id} ({citations[0].topic})."
    else:
        reference = "Aucun extrait RAG disponible."
    return f"{base} Requête : {_trim_text(message, 180)}. {reference} Prochaine action : valider les données du lot concerné."


def _build_llm_unavailable_answer(
    *,
    message: str,
    retrieval_plan: RetrievalPlan,
    citations: Sequence[ChatCitation],
    context_metrics: Sequence[ChatMetricFact],
    language: str,
) -> str:
    def _short_excerpt(value: str, limit: int = 120) -> str:
        cleaned = " ".join(str(value or "").split())
        return cleaned if len(cleaned) <= limit else f"{cleaned[:limit - 1]}…"

    if retrieval_plan.intent_type == RetrievalIntentType.RAG_ONLY.value:
        if citations:
            top = citations[:3]
            refs = "; ".join(f"{c.source_id} ({c.topic})" for c in top)
            grounded_points = " ".join(
                f"[{c.source_id}] {_short_excerpt(c.excerpt)}"
                for c in top
                if str(c.excerpt or "").strip()
            )
            return (
                "Le fournisseur LLM est indisponible. "
                f"Références récupérées: {refs}. "
                f"Synthèse déterministe: {grounded_points or 'Les extraits confirment des pratiques de réduction des pertes.'}"
            )
        return "Le fournisseur LLM est indisponible et aucune référence exploitable n'a été récupérée."

    if retrieval_plan.intent_type == RetrievalIntentType.HYBRID.value and citations:
        top = citations[:2]
        refs = "; ".join(f"{c.source_id} ({c.topic})" for c in top)
        salient_metrics = [
            metric
            for metric in context_metrics
            if not metric.metric.startswith("retrieval_plan.") and not metric.metric.startswith("orchestration.")
        ]
        metric_line = ""
        if salient_metrics:
            picked = salient_metrics[:2]
            metric_line = " Données SQL clés: " + "; ".join(
                f"{item.metric}={round_metric(float(item.value))} {item.unit}".strip()
                for item in picked
            ) + "."
        return (
            "Le fournisseur LLM est indisponible. "
            "Analyse limitée aux données structurées et aux références disponibles. "
            f"Sources clés: {refs}.{metric_line}"
        )

    return _build_fallback_answer(
        message=message,
        dashboard=None,
        citations=citations,
        response_mode="operational",
        language=language,
    )


def _build_unsupported_scope_answer(language: str) -> str:
    return (
        "Cette question sort du périmètre actuel. Je peux répondre aux questions liées aux stocks, lots, pertes, "
        "transformation post-récolte, recommandations et indicateurs de la coopérative."
    )


def _build_non_operational_answer(*, message: str, retrieval_plan: RetrievalPlan, language: str) -> str:
    if retrieval_plan.intent_type == RetrievalIntentType.SMALL_TALK.value:
        return _build_small_talk_answer(message)
    if retrieval_plan.intent_type == RetrievalIntentType.CLARIFICATION_NEEDED.value:
        return (
            "Pouvez-vous préciser votre demande ? Je peux vous aider sur les stocks, lots, pertes, risques, "
            "recommandations ou références agronomiques."
        )
    if retrieval_plan.intent_type == RetrievalIntentType.UNSUPPORTED.value:
        return _build_unsupported_scope_answer(language)
    return "Je n'ai pas pu classifier cette demande. Veuillez reformuler votre question."


def _build_small_talk_answer(message: str) -> str:
    normalized = re.sub(r"[^\w\s]", " ", " ".join(message.strip().split()).lower(), flags=re.UNICODE)
    compact = " ".join(normalized.split())
    if compact == "merci":
        return "Avec plaisir. Posez-moi une question sur les stocks, lots, pertes ou recommandations de la coopérative."
    return (
        "Bonjour. Je peux vous aider à analyser les stocks, les lots, les pertes, les risques opérationnels et les "
        "recommandations de la coopérative."
    )


def _build_retrieval_filters(*, message: str, retrieval_plan: RetrievalPlan) -> dict[str, Any]:
    lowered = message.lower()
    explicit_batch_ids = {value.lower() for value in BATCH_UUID_PATTERN.findall(lowered)}
    entities = retrieval_plan.detected_entities or {}
    stages = set(str(item).lower() for item in entities.get("stages", []))
    stage_canonical = set()
    for stage in stages:
        if stage in {"sechage", "séchage", "drying"}:
            stage_canonical.add("drying")
        if stage in {"tri", "sorting"}:
            stage_canonical.add("sorting")
        if stage in {"nettoyage", "cleaning"}:
            stage_canonical.add("cleaning")
        if stage in {"emballage", "packaging"}:
            stage_canonical.add("packaging")

    chunk_type_map = {
        "batch_summary": "batch_summary",
        "lot_status_summary": "lot_status_summary",
        "lot_recommendation_summary": "lot_recommendation_summary",
        "operational_risk_summary": "operational_risk_summary",
        "scoped_loss_summary": "scoped_loss_summary",
        "product_stage_summary": "product_stage_summary",
        "process_step_summary": "process_step_summary",
        "recommendation_context": "recommendation_context",
        "anomaly_context": "anomaly_summary",
        "agronomic_knowledge": "agronomic_knowledge",
        "benchmark_reference": "benchmark_reference",
        "parcel_context": "parcel_context",
        "pre_harvest_context": "pre_harvest_context",
        "commercial_context": "commercial_context",
        "ml_evaluation_context": "ml_evaluation_context",
    }
    preferred_chunk_types = [
        chunk_type_map[item]
        for item in retrieval_plan.suggested_rag_chunk_types
        if item in chunk_type_map
    ]
    preferred_source_tables = _infer_source_table_filters(retrieval_plan)
    preferred_source_tables.update(_infer_source_tables_from_rag_chunk_types(preferred_chunk_types))

    max_age_minutes: Optional[int] = None
    time_hints = set(str(item).lower() for item in entities.get("time_hints", []))
    if "today" in time_hints or "aujourd'hui" in time_hints or "current" in time_hints or "latest" in time_hints:
        max_age_minutes = 24 * 60
    elif "this week" in time_hints or "cette semaine" in time_hints:
        max_age_minutes = 7 * 24 * 60
    elif "this month" in time_hints or "ce mois" in time_hints:
        max_age_minutes = 31 * 24 * 60

    risk_level = None
    if "high risk" in lowered or "risque eleve" in lowered or "risque élevé" in lowered:
        risk_level = "HIGH"
    elif "medium risk" in lowered or "risque moyen" in lowered:
        risk_level = "MEDIUM"
    elif "low risk" in lowered or "faible risque" in lowered:
        risk_level = "LOW"

    return {
        "product_name": {value for value in (_normalize_product_name(str(item)) for item in entities.get("products", [])) if value},
        "stage": stages,
        "stage_canonical": stage_canonical,
        "chunk_type": set(preferred_chunk_types),
        "source_table": preferred_source_tables,
        "risk_level": risk_level,
        "batch_id": explicit_batch_ids,
        "batch_codes": set(str(item).upper() for item in entities.get("batch_codes", [])),
        "max_age_minutes": max_age_minutes,
    }


def _infer_source_table_filters(retrieval_plan: RetrievalPlan) -> set[str]:
    map_sql_to_table = {
        "batches": "batches",
        "process_steps": "process_steps",
        "recommendations": "recommendations",
        "parcels": "parcels",
        "pre_harvest": "pre_harvest_steps",
        "commercial_orders": "commercial_orders",
        "commercial_invoices": "commercial_invoices",
        "ml_metrics": "ml_prediction_logs",
    }
    values = set()
    for domain in retrieval_plan.suggested_sql_domains:
        source_table = map_sql_to_table.get(domain)
        if source_table:
            values.add(source_table)
    return values


def _infer_source_tables_from_rag_chunk_types(chunk_types: Sequence[str]) -> set[str]:
    mapping = {
        "agronomic_knowledge": {"knowledge_chunks"},
        "benchmark_reference": {"reference_metrics"},
        "batch_summary": {"batches"},
        "lot_status_summary": {"batches"},
        "operational_risk_summary": {"batches", "ml_prediction_logs", "recommendations"},
        "lot_recommendation_summary": {"recommendations", "batches"},
        "process_step_summary": {"process_steps"},
        "product_stage_summary": {"process_steps"},
        "scoped_loss_summary": {"process_steps", "batches"},
        "recommendation_context": {"recommendations", "ml_recommendation_logs"},
        "anomaly_summary": {"recommendation_feedback_logs", "ml_prediction_logs"},
        "parcel_context": {"parcels"},
        "pre_harvest_context": {"pre_harvest_steps"},
        "commercial_context": {"commercial_orders", "commercial_invoices", "commercial_catalog_products"},
        "ml_evaluation_context": {"ml_training_runs", "ml_model_registry"},
    }
    values: set[str] = set()
    for chunk_type in chunk_types:
        values.update(mapping.get(chunk_type, set()))
    return values


def _apply_retrieval_filters(hits: list[RetrievalHit], *, retrieval_filters: dict[str, Any]) -> list[RetrievalHit]:
    filtered: list[RetrievalHit] = []
    for hit in hits:
        if _hit_matches_filters(hit, retrieval_filters=retrieval_filters):
            filtered.append(hit)
    return filtered


def _hit_matches_filters(hit: RetrievalHit, *, retrieval_filters: dict[str, Any]) -> bool:
    metadata = hit.metadata or {}
    product_filters = retrieval_filters.get("product_name") or set()
    if product_filters:
        product_name = _normalize_product_name(str(metadata.get("product_name") or metadata.get("crop") or ""))
        if product_name and product_name not in product_filters:
            return False

    stage_filters = retrieval_filters.get("stage") or set()
    if stage_filters:
        stage = str(metadata.get("stage") or "").lower()
        if stage and stage not in stage_filters:
            return False

    stage_canonical_filters = retrieval_filters.get("stage_canonical") or set()
    if stage_canonical_filters:
        canonical = str(metadata.get("stage_canonical") or "").lower()
        if canonical and canonical not in stage_canonical_filters:
            return False

    chunk_type_filters = retrieval_filters.get("chunk_type") or set()
    if chunk_type_filters:
        chunk_type = str(metadata.get("chunk_type") or "").lower()
        if chunk_type and chunk_type not in chunk_type_filters:
            return False

    source_table_filters = retrieval_filters.get("source_table") or set()
    if source_table_filters and hit.source_table not in source_table_filters:
        return False

    risk_level_filter = retrieval_filters.get("risk_level")
    if risk_level_filter:
        risk_level = str(metadata.get("risk_level") or "").upper()
        if risk_level and risk_level != str(risk_level_filter).upper():
            return False

    batch_codes = retrieval_filters.get("batch_codes") or set()
    if batch_codes:
        batch_code = str(metadata.get("batch_code") or "").upper()
        content = hit.content.upper()
        if batch_code:
            if not any(code in batch_code for code in batch_codes):
                return False
        elif not any(code in content or code in hit.source_record_ref.upper() for code in batch_codes):
            return False

    batch_ids = retrieval_filters.get("batch_id") or set()
    if batch_ids:
        batch_id = str(metadata.get("batch_id") or "").lower()
        if batch_id and batch_id not in batch_ids:
            return False

    max_age_minutes = retrieval_filters.get("max_age_minutes")
    if max_age_minutes is not None:
        freshness = _freshness_age_minutes(metadata.get("freshness_timestamp"))
        if freshness is not None and freshness > float(max_age_minutes):
            return False
    return True


def _retrieve_rag_hits(
    db: Session,
    *,
    current_user: User,
    message: str,
    limit: int,
    retrieval_filters: dict[str, Any],
) -> List[RetrievalHit]:
    if not settings.rag_enabled:
        return []
    if current_user.cooperative_id is None:
        return []
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return []

    candidate_k = max(limit * 6, 24)
    vector_rows: list[dict[str, Any]] = []
    try:
        query_embedding = embed_texts([message])[0]
        vector_stmt = text(
            """
            SELECT
                c.id AS chunk_id,
                c.content AS content,
                c.metadata_json AS chunk_metadata_json,
                c.created_at AS chunk_created_at,
                d.source_table AS source_table,
                d.source_record_ref AS source_record_ref,
                d.metadata_json AS metadata_json,
                d.last_synced_at AS document_last_synced_at,
                (c.embedding <=> CAST(:embedding AS vector)) AS distance
            FROM rag_chunks c
            JOIN rag_documents d ON d.id = c.document_id
            WHERE c.cooperative_id = :cooperative_id
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :k
            """
        )
        vector_rows = db.execute(
            vector_stmt,
            {
                "cooperative_id": current_user.cooperative_id,
                "embedding": _vector_literal(query_embedding),
                "k": candidate_k,
            },
        ).mappings().all()
    except Exception:
        vector_rows = []

    keyword_stmt = text(
        """
        SELECT
            c.id AS chunk_id,
            c.content AS content,
            c.metadata_json AS chunk_metadata_json,
            c.created_at AS chunk_created_at,
            d.source_table AS source_table,
            d.source_record_ref AS source_record_ref,
            d.metadata_json AS metadata_json,
            d.last_synced_at AS document_last_synced_at,
            ts_rank_cd(to_tsvector('simple', c.content), websearch_to_tsquery('simple', :query)) AS keyword_score
        FROM rag_chunks c
        JOIN rag_documents d ON d.id = c.document_id
        WHERE c.cooperative_id = :cooperative_id
          AND to_tsvector('simple', c.content) @@ websearch_to_tsquery('simple', :query)
        ORDER BY keyword_score DESC
        LIMIT :k
        """
    )
    try:
        keyword_rows = db.execute(
            keyword_stmt,
            {
                "cooperative_id": current_user.cooperative_id,
                "query": message,
                "k": candidate_k,
            },
        ).mappings().all()
    except Exception:
        keyword_rows = []

    merged: dict[str, RetrievalHit] = {}
    for idx, row in enumerate(vector_rows, start=1):
        chunk_id = str(row.get("chunk_id"))
        source_table = str(row.get("source_table") or "source")
        source_record_ref = str(row.get("source_record_ref") or "unknown")
        metadata_map = _normalize_hit_metadata(
            source_table=source_table,
            source_record_ref=source_record_ref,
            metadata_raw=row.get("metadata_json"),
            chunk_metadata_raw=row.get("chunk_metadata_json"),
            chunk_created_at=row.get("chunk_created_at"),
            document_last_synced_at=row.get("document_last_synced_at"),
        )
        merged[chunk_id] = RetrievalHit(
            chunk_id=chunk_id,
            source_table=source_table,
            source_record_ref=source_record_ref,
            content=str(row.get("content") or ""),
            metadata=metadata_map,
            distance=float(row.get("distance") or 1.0),
            keyword_score=0.0,
            vector_rank=idx,
        )

    for idx, row in enumerate(keyword_rows, start=1):
        chunk_id = str(row.get("chunk_id"))
        keyword_score = float(row.get("keyword_score") or 0.0)
        if chunk_id in merged:
            merged[chunk_id].keyword_score = keyword_score
            merged[chunk_id].keyword_rank = idx
            continue
        source_table = str(row.get("source_table") or "source")
        source_record_ref = str(row.get("source_record_ref") or "unknown")
        metadata_map = _normalize_hit_metadata(
            source_table=source_table,
            source_record_ref=source_record_ref,
            metadata_raw=row.get("metadata_json"),
            chunk_metadata_raw=row.get("chunk_metadata_json"),
            chunk_created_at=row.get("chunk_created_at"),
            document_last_synced_at=row.get("document_last_synced_at"),
        )
        merged[chunk_id] = RetrievalHit(
            chunk_id=chunk_id,
            source_table=source_table,
            source_record_ref=source_record_ref,
            content=str(row.get("content") or ""),
            metadata=metadata_map,
            distance=1.0,
            keyword_score=keyword_score,
            keyword_rank=idx,
        )

    filtered_hits = _apply_retrieval_filters(list(merged.values()), retrieval_filters=retrieval_filters)
    if filtered_hits:
        return _rerank_hits(message=message, hits=filtered_hits, limit=limit)

    for relaxed_filters in _build_scope_relaxed_filter_sequence(retrieval_filters):
        relaxed_hits = _apply_retrieval_filters(list(merged.values()), retrieval_filters=relaxed_filters)
        if relaxed_hits:
            return _rerank_hits(message=message, hits=relaxed_hits, limit=limit)

    if _should_disable_unfiltered_fallback(retrieval_filters):
        return []
    # Backward compatibility fallback: only after scoped relaxations are exhausted.
    return _rerank_hits(message=message, hits=list(merged.values()), limit=limit)


def _rerank_hits(*, message: str, hits: list[RetrievalHit], limit: int) -> list[RetrievalHit]:
    if not hits:
        return []

    # Reciprocal Rank Fusion over vector and keyword ranks.
    rrf_k = 60.0
    query_tokens = set(_tokenize(message))
    scope_profile = _build_scope_query_profile(message)
    table_boosts = _infer_table_boosts(query_tokens, scope_profile=scope_profile)
    scope_details: list[tuple[RetrievalHit, float, float, bool, bool]] = []

    for hit in hits:
        fused = 0.0
        if hit.vector_rank > 0:
            fused += 1.0 / (rrf_k + hit.vector_rank)
        if hit.keyword_rank > 0:
            fused += 1.0 / (rrf_k + hit.keyword_rank)
        hit.fused_score = fused

        chunk_tokens = set(_tokenize(hit.content))
        lexical_overlap = (len(query_tokens & chunk_tokens) / max(1, len(query_tokens))) if query_tokens else 0.0
        distance_bonus = max(0.0, 1.0 - min(hit.distance, 2.0))
        table_boost = table_boosts.get(hit.source_table, 0.0)
        chunk_type_boost = _infer_chunk_type_boost(query_tokens=query_tokens, metadata=hit.metadata)
        freshness_adjustment = _freshness_score_adjustment(hit)
        scope_boost, scope_penalty, unrelated_product, operational_chunk = _scope_alignment_adjustment(
            scope_profile=scope_profile,
            hit=hit,
        )
        hit.rerank_score = (
            fused
            + (0.32 * lexical_overlap)
            + (0.24 * distance_bonus)
            + table_boost
            + chunk_type_boost
            + scope_boost
            - scope_penalty
            + freshness_adjustment
        )
        hit.retrieval_reason = _build_retrieval_reason(
            chunk_type_boost=chunk_type_boost,
            table_boost=table_boost,
            scope_boost=scope_boost,
            scope_penalty=scope_penalty,
            freshness_adjustment=freshness_adjustment,
            unrelated_product=unrelated_product,
            benchmark_intent=scope_profile.benchmark_intent,
            operational_chunk=operational_chunk,
        )
        scope_details.append((hit, scope_boost, scope_penalty, unrelated_product, operational_chunk))

    hits.sort(key=lambda item: item.rerank_score, reverse=True)
    hits = _prune_scope_contamination(hits=hits, scope_profile=scope_profile, limit=limit)
    return hits[:limit]


def _infer_table_boosts(query_tokens: set[str], *, scope_profile: ScopeQueryProfile) -> dict[str, float]:
    boosts: dict[str, float] = {}
    if {"rentable", "marge", "profit", "gagner", "revenu"} & query_tokens or _has_prefix(query_tokens, ("rentab", "profit")):
        boosts["inputs"] = 0.15
        boosts["farmer_advances"] = 0.12
        boosts["treasury_transactions"] = 0.1
    if {"stock", "rupture", "seuil"} & query_tokens:
        boosts["stocks"] = 0.16
        boosts["commercial_catalog_products"] = 0.08
    if {"perte", "loss", "efficacite", "sechage", "tri"} & query_tokens:
        boosts["process_steps"] = 0.16
        boosts["batches"] = 0.1
    if {
        "benchmark",
        "reference",
        "literature",
        "aphlis",
        "fao",
        "agronomic",
        "agronomique",
        "typical",
        "best",
        "practices",
    } & query_tokens:
        boosts["reference_metrics"] = 0.24
        boosts["knowledge_chunks"] = 0.22
        boosts["recommendations"] = max(boosts.get("recommendations", 0.0), 0.05)
        boosts["stocks"] = min(boosts.get("stocks", 0.0), 0.02)
        boosts["inputs"] = min(boosts.get("inputs", 0.0), 0.02)
    if scope_profile.products and not scope_profile.benchmark_intent:
        boosts["batches"] = max(boosts.get("batches", 0.0), 0.12)
        boosts["process_steps"] = max(boosts.get("process_steps", 0.0), 0.14)
        boosts["recommendations"] = max(boosts.get("recommendations", 0.0), 0.12)
        boosts["stocks"] = max(boosts.get("stocks", 0.0), 0.02)
        boosts["inputs"] = max(boosts.get("inputs", 0.0), 0.02)
    if scope_profile.lot_codes:
        boosts["batches"] = max(boosts.get("batches", 0.0), 0.18)
        boosts["process_steps"] = max(boosts.get("process_steps", 0.0), 0.16)
        boosts["recommendations"] = max(boosts.get("recommendations", 0.0), 0.15)
    if scope_profile.products and scope_profile.stages and not scope_profile.benchmark_intent:
        boosts["process_steps"] = max(boosts.get("process_steps", 0.0), 0.2)
        boosts["batches"] = max(boosts.get("batches", 0.0), 0.16)
        boosts["recommendations"] = max(boosts.get("recommendations", 0.0), 0.16)
        boosts["stocks"] = min(boosts.get("stocks", 0.0), 0.02)
        boosts["inputs"] = min(boosts.get("inputs", 0.0), 0.02)
    return boosts


def _infer_chunk_type_boost(*, query_tokens: set[str], metadata: dict[str, Any]) -> float:
    chunk_type = str(metadata.get("chunk_type") or "").strip().lower()
    if not chunk_type:
        return 0.0

    explanatory_tokens = {
        "why",
        "pourquoi",
        "explain",
        "cause",
        "causes",
        "risk",
        "risky",
        "anomaly",
        "anomalie",
        "recommendation",
        "recommendations",
        "benchmark",
    }
    operational_tokens = {"risk", "anomaly", "loss", "losses", "drying", "recommendation", "efficiency", "perte", "sechage"}
    if not (query_tokens & explanatory_tokens or query_tokens & operational_tokens):
        if not (
            {
                "benchmark",
                "reference",
                "literature",
                "aphlis",
                "fao",
                "agronomic",
                "agronomique",
                "typical",
                "best",
                "practices",
            }
            & query_tokens
        ):
            return 0.0

    boosts = {
        "recommendation_context": 0.08,
        "anomaly_summary": 0.1,
        "batch_summary": 0.06,
        "lot_status_summary": 0.11,
        "lot_recommendation_summary": 0.1,
        "operational_risk_summary": 0.11,
        "scoped_loss_summary": 0.11,
        "product_stage_summary": 0.12,
        "ml_prediction_context": 0.08,
        "process_step_summary": 0.05,
        "benchmark_reference": 0.14,
        "agronomic_knowledge": 0.14,
    }
    return boosts.get(chunk_type, 0.0)


def _freshness_score_adjustment(hit: RetrievalHit) -> float:
    chunk_type = str(hit.metadata.get("chunk_type") or "")
    policy = get_freshness_policy(chunk_type)
    age_minutes = _freshness_age_minutes(hit.metadata.get("freshness_timestamp"))
    hit.freshness_age_minutes = age_minutes
    if age_minutes is None:
        return 0.0

    max_age = policy.max_age_minutes
    if max_age is None or max_age <= 0:
        return 0.01 if age_minutes <= 24 * 60 else 0.0

    ratio = age_minutes / float(max_age)
    if ratio <= 1.0:
        return max(0.0, 0.06 * (1.0 - (ratio * 0.7)))

    penalty = min(0.08, (ratio - 1.0) * 0.03)
    if policy.refresh_mode.value in {"MANUAL_ONLY", "SCHEDULED_WEEKLY"}:
        penalty *= 0.35
    return -penalty


def _freshness_age_minutes(raw_timestamp: Any) -> Optional[float]:
    if not raw_timestamp:
        return None
    try:
        if isinstance(raw_timestamp, datetime):
            ts = raw_timestamp
        else:
            ts = datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        return max(0.0, (now - ts.astimezone(UTC)).total_seconds() / 60.0)
    except Exception:
        return None


def _normalize_hit_metadata(
    *,
    source_table: str,
    source_record_ref: str,
    metadata_raw: Any,
    chunk_metadata_raw: Any,
    chunk_created_at: Any,
    document_last_synced_at: Any,
) -> dict[str, Any]:
    doc_metadata = _coerce_metadata_map(metadata_raw)
    chunk_metadata = _coerce_metadata_map(chunk_metadata_raw)
    merged: dict[str, Any] = {**doc_metadata, **chunk_metadata}
    merged["source_table"] = str(merged.get("source_table") or source_table)
    merged["source_row_id"] = str(merged.get("source_row_id") or source_record_ref)

    inferred_chunk_type = _infer_chunk_type(
        chunk_type=merged.get("chunk_type"),
        entity=merged.get("entity"),
        source_table=source_table,
    )
    if inferred_chunk_type:
        merged["chunk_type"] = inferred_chunk_type

    freshness_value = merged.get("freshness_timestamp")
    if freshness_value is None:
        freshness_value = chunk_created_at or document_last_synced_at
    freshness_iso = _to_iso_timestamp(freshness_value)
    if freshness_iso:
        merged["freshness_timestamp"] = freshness_iso
    return merged


def _coerce_metadata_map(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        text_value = raw.strip()
        if not text_value:
            return {}
        try:
            parsed = json.loads(text_value)
        except Exception:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _infer_chunk_type(*, chunk_type: Any, entity: Any, source_table: str) -> str:
    for candidate in (chunk_type, entity, source_table):
        if candidate is None:
            continue
        key = str(candidate).strip().lower()
        if not key:
            continue
        return _LEGACY_CHUNK_TYPE_MAP.get(key, key)
    return "unknown"


def _to_iso_timestamp(raw_value: Any) -> Optional[str]:
    if raw_value is None:
        return None
    if isinstance(raw_value, datetime):
        ts = raw_value
    else:
        try:
            ts = datetime.fromisoformat(str(raw_value).replace("Z", "+00:00"))
        except Exception:
            return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC).isoformat()


def _should_disable_unfiltered_fallback(retrieval_filters: dict[str, Any]) -> bool:
    chunk_types = {str(item).lower() for item in (retrieval_filters.get("chunk_type") or set())}
    source_tables = {str(item).lower() for item in (retrieval_filters.get("source_table") or set())}
    benchmark_only_chunk_types = {"benchmark_reference", "agronomic_knowledge"}
    if chunk_types and chunk_types.issubset(benchmark_only_chunk_types):
        return True
    if source_tables and source_tables.issubset({"reference_metrics", "knowledge_chunks"}):
        return True
    return False


def _build_scope_relaxed_filter_sequence(retrieval_filters: dict[str, Any]) -> list[dict[str, Any]]:
    base_product = set(str(item).lower() for item in (retrieval_filters.get("product_name") or set()))
    base_stage = set(str(item).lower() for item in (retrieval_filters.get("stage") or set()))
    base_stage_canonical = set(str(item).lower() for item in (retrieval_filters.get("stage_canonical") or set()))
    base_chunk_types = set(str(item).lower() for item in (retrieval_filters.get("chunk_type") or set()))
    benchmark_types = {"benchmark_reference", "agronomic_knowledge"}

    if not (base_product or base_stage or base_stage_canonical):
        return []

    sequence: list[dict[str, Any]] = []

    # 1) Same product + any stage.
    if base_product:
        variant = _clone_retrieval_filters(retrieval_filters)
        variant["stage"] = set()
        variant["stage_canonical"] = set()
        sequence.append(variant)

    # 2) Same stage + any product.
    if base_stage or base_stage_canonical:
        variant = _clone_retrieval_filters(retrieval_filters)
        variant["product_name"] = set()
        sequence.append(variant)

    # 3) Cooperative operational summaries only (exclude benchmark-heavy chunks).
    operational_variant = _clone_retrieval_filters(retrieval_filters)
    operational_variant["product_name"] = set()
    operational_variant["stage"] = set()
    operational_variant["stage_canonical"] = set()
    if base_chunk_types:
        operational_variant["chunk_type"] = {item for item in base_chunk_types if item not in benchmark_types}
    if not operational_variant.get("chunk_type"):
        operational_variant["chunk_type"] = {
            "lot_status_summary",
            "product_stage_summary",
            "scoped_loss_summary",
            "operational_risk_summary",
            "batch_summary",
            "process_step_summary",
            "recommendation_context",
            "anomaly_summary",
            "lot_recommendation_summary",
        }
    sequence.append(operational_variant)

    # 4) Benchmark/reference support context.
    benchmark_variant = _clone_retrieval_filters(retrieval_filters)
    benchmark_variant["product_name"] = base_product
    benchmark_variant["stage"] = set()
    benchmark_variant["stage_canonical"] = set()
    benchmark_variant["chunk_type"] = {"benchmark_reference", "agronomic_knowledge"}
    benchmark_variant["source_table"] = {"reference_metrics", "knowledge_chunks"}
    sequence.append(benchmark_variant)

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in sequence:
        marker = repr({k: sorted(v) if isinstance(v, set) else v for k, v in item.items()})
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(item)
    return unique


def _clone_retrieval_filters(retrieval_filters: dict[str, Any]) -> dict[str, Any]:
    cloned: dict[str, Any] = {}
    for key, value in retrieval_filters.items():
        if isinstance(value, set):
            cloned[key] = set(value)
        elif isinstance(value, list):
            cloned[key] = list(value)
        elif isinstance(value, dict):
            cloned[key] = dict(value)
        else:
            cloned[key] = value
    return cloned


def _build_scope_query_profile(message: str) -> ScopeQueryProfile:
    lowered = message.lower()
    tokens = set(_tokenize(lowered))
    products = {
        _normalize_product_name(value)
        for key, value in {
            "mango": "mango",
            "mangue": "mangue",
            "millet": "millet",
            "mil": "mil",
            "peanut": "peanut",
            "arachide": "arachide",
            "bissap": "bissap",
        }.items()
        if key in lowered
    } - {""}
    stages = {
        value
        for key, value in {
            "drying": "drying",
            "sechage": "drying",
            "séchage": "drying",
            "sorting": "sorting",
            "tri": "sorting",
            "cleaning": "cleaning",
            "nettoyage": "cleaning",
            "packaging": "packaging",
            "emballage": "packaging",
            "storage": "storage",
            "stockage": "storage",
        }.items()
        if key in lowered
    }
    lot_codes = {code.upper() for code in LOT_CODE_PATTERN.findall(message)}
    benchmark_intent = any(token in lowered for token in ("benchmark", "reference", "literature", "aphlis", "fao", "best practices", "agronomic"))
    comparative_intent = bool({"compare", "comparison", "versus", "vs"} & tokens) or "compared" in lowered

    if lot_codes:
        level = "LOT"
    elif products and stages:
        level = "PRODUCT_STAGE"
    elif products:
        level = "PRODUCT"
    elif benchmark_intent:
        level = "BENCHMARK"
    elif comparative_intent:
        level = "COMPARATIVE"
    else:
        level = "COOPERATIVE"

    return ScopeQueryProfile(
        scope_level=level,
        products=products,
        stages=stages,
        lot_codes=lot_codes,
        benchmark_intent=benchmark_intent,
        comparative_intent=comparative_intent,
    )


def _scope_alignment_adjustment(*, scope_profile: ScopeQueryProfile, hit: RetrievalHit) -> tuple[float, float, bool, bool]:
    metadata = hit.metadata or {}
    chunk_type = str(metadata.get("chunk_type") or "").lower().strip()
    source_table = str(hit.source_table or "").lower().strip()
    hit_product = _normalize_product_name(str(metadata.get("product_name") or metadata.get("crop") or ""))
    hit_stage = str(metadata.get("stage_canonical") or metadata.get("stage") or "").lower().strip()
    hit_batch_code = str(metadata.get("batch_code") or "").upper().strip()
    text_upper = f"{hit.content} {hit.source_record_ref}".upper()
    operational_chunk = chunk_type not in {"benchmark_reference", "agronomic_knowledge"} and source_table not in {"reference_metrics", "knowledge_chunks"}

    boost = 0.0
    penalty = 0.0
    unrelated_product = False

    if scope_profile.lot_codes:
        if any(code in hit_batch_code or code in text_upper for code in scope_profile.lot_codes):
            boost += 0.22
        elif hit_batch_code:
            penalty += 0.16

    if scope_profile.products:
        if hit_product:
            if hit_product in scope_profile.products:
                boost += 0.14
            else:
                penalty += 0.18
                unrelated_product = True
        elif operational_chunk:
            penalty += 0.04

    if scope_profile.stages:
        if hit_stage:
            if hit_stage in scope_profile.stages:
                boost += 0.1
            else:
                penalty += 0.08

    if scope_profile.benchmark_intent:
        if chunk_type in {"benchmark_reference", "agronomic_knowledge"} or source_table in {"reference_metrics", "knowledge_chunks"}:
            boost += 0.18
        elif operational_chunk and not scope_profile.comparative_intent:
            penalty += 0.08
    else:
        if chunk_type in {"benchmark_reference", "agronomic_knowledge"}:
            penalty += 0.08 if (scope_profile.products or scope_profile.stages or scope_profile.lot_codes) else 0.06
        if operational_chunk:
            boost += 0.05

    if chunk_type in {
        "recommendation_context",
        "anomaly_summary",
        "process_step_summary",
        "product_stage_summary",
        "lot_status_summary",
        "lot_recommendation_summary",
        "operational_risk_summary",
        "scoped_loss_summary",
    } and not scope_profile.benchmark_intent:
        boost += 0.04
    if scope_profile.products and scope_profile.stages and chunk_type in {"product_stage_summary", "scoped_loss_summary"}:
        boost += 0.07
    if scope_profile.lot_codes and chunk_type in {"lot_status_summary", "lot_recommendation_summary"}:
        boost += 0.08
    if (
        scope_profile.products
        and scope_profile.stages
        and chunk_type in {"benchmark_reference", "agronomic_knowledge"}
        and not scope_profile.benchmark_intent
    ):
        penalty += 0.1

    return boost, penalty, unrelated_product, operational_chunk


def _prune_scope_contamination(*, hits: list[RetrievalHit], scope_profile: ScopeQueryProfile, limit: int) -> list[RetrievalHit]:
    if not hits:
        return hits
    if not scope_profile.products and not scope_profile.stages:
        return hits

    unrelated: list[RetrievalHit] = []
    related: list[RetrievalHit] = []
    operational_related: list[RetrievalHit] = []
    for hit in hits:
        metadata = hit.metadata or {}
        hit_product = _normalize_product_name(str(metadata.get("product_name") or metadata.get("crop") or ""))
        chunk_type = str(metadata.get("chunk_type") or "").lower().strip()
        source_table = str(hit.source_table or "").lower().strip()
        is_benchmark = chunk_type in {"benchmark_reference", "agronomic_knowledge"} or source_table in {"reference_metrics", "knowledge_chunks"}
        is_operational = not is_benchmark

        if hit_product and hit_product not in scope_profile.products:
            unrelated.append(hit)
        else:
            related.append(hit)
            if is_operational:
                operational_related.append(hit)

    if scope_profile.products and related and len(related) >= min(limit, 3):
        return related
    if scope_profile.products and scope_profile.stages and operational_related and len(operational_related) >= min(limit, 2):
        return operational_related + [item for item in related if item not in operational_related]
    if related:
        return [*related, *unrelated]
    return hits


def _build_retrieval_reason(
    *,
    chunk_type_boost: float,
    table_boost: float,
    scope_boost: float,
    scope_penalty: float,
    freshness_adjustment: float,
    unrelated_product: bool,
    benchmark_intent: bool,
    operational_chunk: bool,
) -> str:
    parts: list[str] = []
    if chunk_type_boost > 0:
        parts.append("chunk_type_boost")
    if table_boost > 0:
        parts.append("table_boost")
    if scope_boost > 0:
        parts.append("scope_match_boost")
    if scope_penalty > 0:
        parts.append("scope_mismatch_penalty")
    if unrelated_product:
        parts.append("unrelated_product_penalty")
    if benchmark_intent and not operational_chunk:
        parts.append("benchmark_scope_priority")
    if freshness_adjustment > 0:
        parts.append("freshness_boost")
    elif freshness_adjustment < 0:
        parts.append("staleness_penalty")
    return ",".join(parts) if parts else "base_rank"


def _citations_from_hits(hits: Sequence[RetrievalHit], *, cooperative: Optional[Cooperative]) -> List[ChatCitation]:
    region = cooperative.region if cooperative else "cooperative"
    citations: list[ChatCitation] = []
    for hit in hits:
        metadata_map = hit.metadata
        topic = str(metadata_map.get("chunk_type") or metadata_map.get("entity") or hit.source_table)
        crop = str(metadata_map.get("product_name") or metadata_map.get("crop") or "multi")
        citations.append(
            ChatCitation(
                source_id=f"{hit.source_table}:{hit.source_record_ref}",
                source_url=f"app://{hit.source_table}/{hit.source_record_ref}",
                region=region,
                crop=crop,
                topic=topic,
                excerpt=_trim_text(hit.content, 220),
            )
        )
    return citations


def _dedupe_citations(citations: Sequence[ChatCitation], *, limit: int) -> list[ChatCitation]:
    seen: set[str] = set()
    ordered: list[ChatCitation] = []
    for citation in citations:
        key = f"{citation.source_id}|{citation.topic}|{citation.excerpt}"
        if key in seen:
            continue
        seen.add(key)
        ordered.append(citation)
        if len(ordered) >= limit:
            break
    return ordered


def _build_sql_evidence_citations(
    *,
    operational_metrics: Sequence[ChatMetricFact],
    cooperative: Optional[Cooperative],
    limit: int = 4,
) -> list[ChatCitation]:
    if not operational_metrics:
        return []
    region = cooperative.region if cooperative else "cooperative"
    rows: list[ChatCitation] = []
    for metric in operational_metrics:
        if metric.metric.startswith("retrieval_plan.") or metric.metric.startswith("retrieval_diagnostics."):
            continue
        rows.append(
            ChatCitation(
                source_id=f"sql:{metric.source_id}:{metric.metric}",
                source_url=f"app://sql-metric/{metric.source_id}/{metric.metric}",
                region=region,
                crop=metric.crop or "multi",
                topic=metric.metric,
                excerpt=_trim_text(
                    f"{metric.metric}={round_metric(metric.value)} {metric.unit} ({metric.period}) {metric.notes or ''}".strip(),
                    220,
                ),
            )
        )
        if len(rows) >= limit:
            break
    return rows


def _retrieve_reference_context(
    db: Session,
    *,
    message: str,
    cooperative: Optional[Cooperative],
    limit: int,
) -> ReferenceContext:
    if not settings.rag_enabled:
        return ReferenceContext(citations=[], metrics=[])

    region_hint = cooperative.region if cooperative else None
    knowledge_stmt = _apply_knowledge_filters(
        select(KnowledgeChunk),
        q=message,
        country=None,
        region=region_hint,
        crop=None,
        topic=None,
    )
    knowledge_rows = db.scalars(knowledge_stmt.limit(limit)).all()
    if not knowledge_rows:
        knowledge_stmt = _apply_knowledge_filters(
            select(KnowledgeChunk),
            q=message,
            country=None,
            region=None,
            crop=None,
            topic=None,
        )
        knowledge_rows = db.scalars(knowledge_stmt.limit(limit)).all()
    if not knowledge_rows:
        token_terms = [f"%{token}%" for token in _tokenize(message) if len(token) >= 4][:6]
        if token_terms:
            token_conditions = []
            for term in token_terms:
                token_conditions.extend(
                    [
                        KnowledgeChunk.topic.ilike(term),
                        KnowledgeChunk.content.ilike(term),
                        KnowledgeChunk.crop.ilike(term),
                    ]
                )
            knowledge_stmt = select(KnowledgeChunk).where(or_(*token_conditions))
            if region_hint:
                knowledge_stmt = knowledge_stmt.where(KnowledgeChunk.region.ilike(region_hint))
            knowledge_rows = db.scalars(knowledge_stmt.limit(limit)).all()

    metric_stmt = _apply_metric_filters(
        select(ReferenceMetric),
        q=message,
        country=None,
        region=region_hint,
        crop=None,
        metric=None,
    )
    metric_rows = db.scalars(metric_stmt.order_by(ReferenceMetric.period.desc()).limit(limit)).all()
    if not metric_rows:
        metric_stmt = _apply_metric_filters(
            select(ReferenceMetric),
            q=message,
            country=None,
            region=None,
            crop=None,
            metric=None,
        )
        metric_rows = db.scalars(metric_stmt.order_by(ReferenceMetric.period.desc()).limit(limit)).all()

    citations: list[ChatCitation] = []
    for chunk in knowledge_rows:
        citations.append(
            ChatCitation(
                source_id=chunk.source_id,
                source_url=chunk.source_url,
                region=chunk.region,
                crop=chunk.crop,
                topic=chunk.topic,
                excerpt=_trim_text(chunk.content, 220),
            )
        )
    for metric in metric_rows:
        citations.append(
            ChatCitation(
                source_id=metric.source_id,
                source_url=f"app://reference/metrics/{metric.id}",
                region=metric.region,
                crop=metric.crop,
                topic=metric.metric,
                excerpt=_trim_text(
                    f"{metric.metric} {metric.value} {metric.unit} ({metric.period}) {metric.notes or ''}".strip(),
                    220,
                ),
            )
        )

    metric_facts = [
        ChatMetricFact(
            source_id=metric.source_id,
            region=metric.region,
            crop=metric.crop,
            metric=metric.metric,
            period=metric.period,
            value=round_metric(metric.value),
            unit=metric.unit,
            notes=metric.notes,
        )
        for metric in metric_rows
    ]
    return ReferenceContext(citations=citations, metrics=metric_facts)


def _build_context_metrics(
    dashboard: Optional[ChatDashboardSnapshot],
    *,
    region_hint: Optional[str],
    rag_hit_count: int,
    reference_metrics: Sequence[ChatMetricFact],
    operational_metrics: Sequence[ChatMetricFact],
    retrieval_plan: RetrievalPlan,
    retrieval_diagnostics: dict[str, Any],
    orchestrated_context: Any,
) -> List[ChatMetricFact]:
    region = (region_hint or (dashboard.region if dashboard else None) or "Senegal")
    combined: list[ChatMetricFact] = [
        ChatMetricFact(
            source_id="rag-retrieval",
            region=region,
            crop="multi",
            metric="rag_hit_count",
            period="current",
            value=float(rag_hit_count),
            unit="count",
            notes="Number of retrieved pgvector chunks used for context.",
        )
    ]
    combined.extend(_build_retrieval_plan_metrics(retrieval_plan, region=region))

    if dashboard:
        combined.extend(
            [
                ChatMetricFact(
                    source_id="dashboard-loss-rate",
                    region=region,
                    crop="multi",
                    metric="loss_rate",
                    period="current",
                    value=round_metric(dashboard.loss_rate),
                    unit="%",
                    notes="From current manager dashboard snapshot",
                ),
                ChatMetricFact(
                    source_id="dashboard-efficiency-rate",
                    region=region,
                    crop="multi",
                    metric="efficiency_rate",
                    period="current",
                    value=round_metric(dashboard.efficiency_rate),
                    unit="%",
                    notes="From current manager dashboard snapshot",
                ),
            ]
        )
    else:
        combined.append(
            ChatMetricFact(
                source_id="dashboard-missing",
                region=region,
                crop="multi",
                metric="dashboard_available",
                period="current",
                value=0.0,
                unit="binary",
                notes="No dashboard snapshot available for current user.",
            )
        )

    combined.extend(reference_metrics)
    combined.extend(operational_metrics)
    combined.extend(_build_retrieval_diagnostic_metrics(retrieval_diagnostics, region=region))
    combined.extend(_build_orchestration_metrics(orchestrated_context, region=region))
    return combined[:24]


def _build_retrieval_plan_metrics(plan: RetrievalPlan, *, region: str) -> list[ChatMetricFact]:
    sql_domains = ",".join(plan.suggested_sql_domains) if plan.suggested_sql_domains else "none"
    rag_chunk_types = ",".join(plan.suggested_rag_chunk_types) if plan.suggested_rag_chunk_types else "none"
    detected_entities = ",".join(
        sorted(key for key, values in plan.detected_entities.items() if isinstance(values, list) and values)
    ) or "none"
    notes = (
        f"reason={plan.reason}; "
        f"sql_domains={sql_domains}; "
        f"rag_chunk_types={rag_chunk_types}; "
        f"detected_entities={detected_entities}; "
        f"safety_notes={';'.join(plan.safety_notes) if plan.safety_notes else 'none'}"
    )
    return [
        ChatMetricFact(
            source_id="retrieval_plan",
            region=region,
            crop="multi",
            metric="retrieval_plan.intent_type",
            period="current",
            value=float(_intent_to_metric_value(plan.intent_type)),
            unit=plan.intent_type,
            notes=notes,
        ),
        ChatMetricFact(
            source_id="retrieval_plan",
            region=region,
            crop="multi",
            metric="retrieval_plan.confidence",
            period="current",
            value=round_metric(plan.confidence),
            unit="score_0_1",
            notes=plan.reason,
        ),
        ChatMetricFact(
            source_id="retrieval_plan",
            region=region,
            crop="multi",
            metric="retrieval_plan.sql_needed",
            period="current",
            value=1.0 if plan.sql_needed else 0.0,
            unit="binary",
            notes="1 means SQL retrieval should be used.",
        ),
        ChatMetricFact(
            source_id="retrieval_plan",
            region=region,
            crop="multi",
            metric="retrieval_plan.rag_needed",
            period="current",
            value=1.0 if plan.rag_needed else 0.0,
            unit="binary",
            notes="1 means semantic retrieval should be used.",
        ),
        ChatMetricFact(
            source_id="retrieval_plan",
            region=region,
            crop="multi",
            metric="retrieval_plan.suggested_sql_domains",
            period="current",
            value=float(len(plan.suggested_sql_domains)),
            unit="count",
            notes=sql_domains,
        ),
        ChatMetricFact(
            source_id="retrieval_plan",
            region=region,
            crop="multi",
            metric="retrieval_plan.suggested_rag_chunk_types",
            period="current",
            value=float(len(plan.suggested_rag_chunk_types)),
            unit="count",
            notes=rag_chunk_types,
        ),
        ChatMetricFact(
            source_id="retrieval_plan",
            region=region,
            crop="multi",
            metric="retrieval_plan.detected_entities",
            period="current",
            value=float(sum(len(values) for values in plan.detected_entities.values() if isinstance(values, list))),
            unit="count",
            notes=detected_entities,
        ),
    ]


def _build_retrieval_diagnostic_metrics(payload: dict[str, Any], *, region: str) -> list[ChatMetricFact]:
    filters = payload.get("filters", {}) if isinstance(payload, dict) else {}
    chunk_types = payload.get("chunk_types", {}) if isinstance(payload, dict) else {}
    freshness = payload.get("freshness", {}) if isinstance(payload, dict) else {}
    provenance = payload.get("top_hit_provenance", []) if isinstance(payload, dict) else []
    return [
        ChatMetricFact(
            source_id="retrieval_diagnostics",
            region=region,
            crop="multi",
            metric="retrieval_diagnostics.active_filter_count",
            period="current",
            value=float(filters.get("active_filter_count", 0) or 0),
            unit="count",
            notes=str(filters.get("active_filters", {})),
        ),
        ChatMetricFact(
            source_id="retrieval_diagnostics",
            region=region,
            crop="multi",
            metric="retrieval_diagnostics.chunk_type_count",
            period="current",
            value=float(len(chunk_types)),
            unit="count",
            notes=str(chunk_types),
        ),
        ChatMetricFact(
            source_id="retrieval_diagnostics",
            region=region,
            crop="multi",
            metric="retrieval_diagnostics.freshness_avg_minutes",
            period="current",
            value=float(freshness.get("freshness_avg_minutes", 0.0) or 0.0),
            unit="minutes",
            notes=str(freshness),
        ),
        ChatMetricFact(
            source_id="retrieval_diagnostics",
            region=region,
            crop="multi",
            metric="retrieval_diagnostics.provenance_count",
            period="current",
            value=float(len(provenance)),
            unit="count",
            notes=str(provenance),
        ),
    ]


def _summarize_retrieval_provenance(hits: Sequence[RetrievalHit], *, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for hit in hits[:limit]:
        metadata = hit.metadata or {}
        rows.append(
            {
                "chunk_type": _infer_chunk_type(
                    chunk_type=metadata.get("chunk_type"),
                    entity=metadata.get("entity"),
                    source_table=hit.source_table,
                ),
                "source_table": hit.source_table,
                "source_row_id": metadata.get("source_row_id") or hit.source_record_ref,
                "freshness_timestamp": metadata.get("freshness_timestamp"),
                "retrieval_score": round_metric(hit.rerank_score),
                "retrieval_reason": hit.retrieval_reason,
            }
        )
    return rows


def _build_orchestration_metrics(orchestrated_context: Any, *, region: str) -> list[ChatMetricFact]:
    if not orchestrated_context:
        return []
    warnings = list(getattr(orchestrated_context, "warning_flags", []) or [])
    confidence = getattr(orchestrated_context, "confidence_estimate", {}) or {}
    citations = list(getattr(orchestrated_context, "citations", []) or [])
    contradictions = list(getattr(orchestrated_context, "contradictory_signals", []) or [])
    scope = getattr(orchestrated_context, "scope_analysis", {}) or {}
    contamination = getattr(orchestrated_context, "contamination_diagnostics", {}) or {}
    return [
        ChatMetricFact(
            source_id="orchestration",
            region=region,
            crop="multi",
            metric="orchestration.warning_count",
            period="current",
            value=float(len(warnings)),
            unit="count",
            notes="|".join(warnings) if warnings else "none",
        ),
        ChatMetricFact(
            source_id="orchestration",
            region=region,
            crop="multi",
            metric="orchestration.confidence_score",
            period="current",
            value=float(confidence.get("score", 0.0) or 0.0),
            unit=str(confidence.get("label", "UNKNOWN")),
            notes="Hybrid orchestration confidence estimate.",
        ),
        ChatMetricFact(
            source_id="orchestration",
            region=region,
            crop="multi",
            metric="orchestration.grounded_citation_count",
            period="current",
            value=float(len(citations)),
            unit="count",
            notes="Grounded citation objects produced by orchestrator.",
        ),
        ChatMetricFact(
            source_id="orchestration",
            region=region,
            crop="multi",
            metric="orchestration.contradiction_count",
            period="current",
            value=float(len(contradictions)),
            unit="count",
            notes="|".join(contradictions) if contradictions else "none",
        ),
        ChatMetricFact(
            source_id="orchestration",
            region=region,
            crop="multi",
            metric="orchestration.scope_level",
            period="current",
            value=float(
                {
                    "LOT": 1,
                    "PRODUCT_STAGE": 2,
                    "PRODUCT": 3,
                    "COOPERATIVE": 4,
                    "BENCHMARK": 5,
                    "COMPARATIVE": 6,
                }.get(str(scope.get("scope_level") or "COOPERATIVE"), 0)
            ),
            unit=str(scope.get("scope_level", "UNKNOWN")),
            notes=str(scope),
        ),
        ChatMetricFact(
            source_id="orchestration",
            region=region,
            crop="multi",
            metric="orchestration.contamination_risk_score",
            period="current",
            value=float(contamination.get("contamination_risk_score", 0.0) or 0.0),
            unit="score_0_1",
            notes=str(contamination),
        ),
    ]


def _intent_to_metric_value(intent_type: str) -> int:
    if intent_type == RetrievalIntentType.SMALL_TALK.value:
        return 5
    if intent_type == RetrievalIntentType.CLARIFICATION_NEEDED.value:
        return 6
    if intent_type == RetrievalIntentType.SQL_ONLY.value:
        return 1
    if intent_type == RetrievalIntentType.RAG_ONLY.value:
        return 2
    if intent_type == RetrievalIntentType.HYBRID.value:
        return 3
    if intent_type == RetrievalIntentType.UNSUPPORTED.value:
        return 4
    return 0


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in vector) + "]"


def _uuid_sql_param(db: Session, value: UUID) -> str:
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "sqlite":
        return value.hex
    return str(value)


def _build_operational_context_metrics(
    db: Session,
    *,
    current_user: User,
    message: str,
    retrieval_plan: RetrievalPlan,
    retrieval_filters: dict[str, Any],
    query_tokens: set[str],
    region_hint: Optional[str],
) -> list[ChatMetricFact]:
    if current_user.cooperative_id is None:
        return []
    region = region_hint or "cooperative"
    cooperative_id_param = _uuid_sql_param(db, current_user.cooperative_id)
    metrics: list[ChatMetricFact] = []

    if STOCK_HINTS & query_tokens:
        row = db.execute(
            text(
                """
                SELECT
                    COALESCE(SUM(s.total_stock_kg), 0) AS total_stock_kg,
                    COALESCE(SUM(s.reserved_in_lots_kg), 0) AS reserved_lots_kg,
                    COALESCE(SUM(s.total_stock_kg - s.reserved_in_lots_kg), 0) AS available_stock_kg,
                    COALESCE(SUM(CASE WHEN (s.total_stock_kg - s.reserved_in_lots_kg) < s.threshold THEN 1 ELSE 0 END), 0) AS low_stock_products
                FROM stocks s
                WHERE s.cooperative_id = :cooperative_id
                """
            ),
            {"cooperative_id": cooperative_id_param},
        ).mappings().first()
        if row:
            metrics.extend(
                [
                    ChatMetricFact(
                        source_id="ops-stocks-summary",
                        region=region,
                        crop="multi",
                        metric="total_stock_kg",
                        period="current",
                        value=round_metric(float(row["total_stock_kg"] or 0)),
                        unit="kg",
                        notes="Live stock total from stocks table.",
                    ),
                    ChatMetricFact(
                        source_id="ops-stocks-summary",
                        region=region,
                        crop="multi",
                        metric="available_stock_kg",
                        period="current",
                        value=round_metric(float(row["available_stock_kg"] or 0)),
                        unit="kg",
                        notes="Live available stock (total - reserved in lots).",
                    ),
                    ChatMetricFact(
                        source_id="ops-stocks-summary",
                        region=region,
                        crop="multi",
                        metric="low_stock_products",
                        period="current",
                        value=float(row["low_stock_products"] or 0),
                        unit="count",
                        notes="Products where available stock is below threshold.",
                    ),
                ]
            )

    if LOSS_HINTS & query_tokens:
        row = db.execute(
            text(
                """
                SELECT
                    COALESCE(AVG(CASE WHEN b.initial_qty > 0 THEN ((b.initial_qty - b.current_qty) / b.initial_qty) * 100 ELSE 0 END), 0) AS avg_loss_pct,
                    COALESCE(MAX(CASE WHEN b.initial_qty > 0 THEN ((b.initial_qty - b.current_qty) / b.initial_qty) * 100 ELSE 0 END), 0) AS worst_loss_pct
                FROM batches b
                WHERE b.cooperative_id = :cooperative_id
                """
            ),
            {"cooperative_id": cooperative_id_param},
        ).mappings().first()
        if row:
            metrics.extend(
                [
                    ChatMetricFact(
                        source_id="ops-batch-loss-summary",
                        region=region,
                        crop="multi",
                        metric="avg_batch_loss_pct",
                        period="current",
                        value=round_metric(float(row["avg_loss_pct"] or 0)),
                        unit="%",
                        notes="Average loss percentage across lots.",
                    ),
                    ChatMetricFact(
                        source_id="ops-batch-loss-summary",
                        region=region,
                        crop="multi",
                        metric="worst_batch_loss_pct",
                        period="current",
                        value=round_metric(float(row["worst_loss_pct"] or 0)),
                        unit="%",
                        notes="Highest loss percentage among lots.",
                    ),
                ]
            )

    if MEMBER_HINTS & query_tokens:
        member_row = db.execute(
            text(
                """
                WITH input_agg AS (
                    SELECT
                        member_id,
                        COALESCE(SUM(quantity), 0) AS collected_kg,
                        COALESCE(SUM(estimated_value), 0) AS gross_value_fcfa
                    FROM inputs
                    WHERE cooperative_id = :cooperative_id
                    GROUP BY member_id
                ),
                advance_agg AS (
                    SELECT
                        farmer_id,
                        COALESCE(SUM(amount_fcfa), 0) AS advances_fcfa
                    FROM farmer_advances
                    WHERE cooperative_id = :cooperative_id
                      AND status = 'active'
                    GROUP BY farmer_id
                ),
                ranking AS (
                    SELECT
                        m.full_name,
                        COALESCE(i.collected_kg, 0) AS collected_kg,
                        CASE
                            WHEN COALESCE(i.collected_kg, 0) > 0
                            THEN (COALESCE(i.gross_value_fcfa, 0) - COALESCE(a.advances_fcfa, 0)) / COALESCE(i.collected_kg, 1)
                            ELSE NULL
                        END AS net_cost_per_kg
                    FROM members m
                    LEFT JOIN input_agg i ON i.member_id = m.id
                    LEFT JOIN advance_agg a ON a.farmer_id = m.id
                    WHERE m.cooperative_id = :cooperative_id
                )
                SELECT
                    COALESCE(MAX(collected_kg), 0) AS top_collected_kg,
                    COALESCE(MIN(net_cost_per_kg), 0) AS best_net_cost_per_kg
                FROM ranking
                """
            ),
            {"cooperative_id": cooperative_id_param},
        ).mappings().first()
        if member_row:
            metrics.extend(
                [
                    ChatMetricFact(
                        source_id="ops-member-efficiency",
                        region=region,
                        crop="multi",
                        metric="top_collected_kg",
                        period="current",
                        value=round_metric(float(member_row["top_collected_kg"] or 0)),
                        unit="kg",
                        notes="Highest collected quantity by one member.",
                    ),
                    ChatMetricFact(
                        source_id="ops-member-efficiency",
                        region=region,
                        crop="multi",
                        metric="best_net_cost_per_kg_fcfa",
                        period="current",
                        value=round_metric(float(member_row["best_net_cost_per_kg"] or 0)),
                        unit="FCFA/kg",
                        notes="Best (lowest) net cost per kg among members.",
                    ),
                ]
            )

    if COMMERCIAL_HINTS & query_tokens:
        commercial_row = db.execute(
            text(
                """
                WITH product_agg AS (
                    SELECT
                        COUNT(*) AS products_for_sale_count,
                        COALESCE(SUM(total_stock_kg - reserved_stock_kg), 0) AS catalog_available_stock_kg
                    FROM commercial_catalog_products
                    WHERE cooperative_id = :cooperative_id
                ),
                invoice_agg AS (
                    SELECT
                        COALESCE(SUM(total_amount_fcfa), 0) AS pending_invoice_total_fcfa
                    FROM commercial_invoices
                    WHERE cooperative_id = :cooperative_id
                      AND status = 'pending'
                )
                SELECT
                    p.products_for_sale_count,
                    p.catalog_available_stock_kg,
                    i.pending_invoice_total_fcfa
                FROM product_agg p
                CROSS JOIN invoice_agg i
                """
            ),
            {"cooperative_id": cooperative_id_param},
        ).mappings().first()
        if commercial_row:
            metrics.extend(
                [
                    ChatMetricFact(
                        source_id="ops-commercial-summary",
                        region=region,
                        crop="multi",
                        metric="products_for_sale_count",
                        period="current",
                        value=float(commercial_row["products_for_sale_count"] or 0),
                        unit="count",
                        notes="Active commercial catalog entries.",
                    ),
                    ChatMetricFact(
                        source_id="ops-commercial-summary",
                        region=region,
                        crop="multi",
                        metric="catalog_available_stock_kg",
                        period="current",
                        value=round_metric(float(commercial_row["catalog_available_stock_kg"] or 0)),
                        unit="kg",
                        notes="Available stock in commercial catalog.",
                    ),
                    ChatMetricFact(
                        source_id="ops-commercial-summary",
                        region=region,
                        crop="multi",
                        metric="pending_invoice_total_fcfa",
                        period="current",
                        value=round_metric(float(commercial_row["pending_invoice_total_fcfa"] or 0)),
                        unit="FCFA",
                        notes="Pending invoice amount to collect.",
                    ),
                ]
            )

    metrics.extend(
        _build_scoped_sql_evidence_metrics(
            db,
            current_user=current_user,
            retrieval_plan=retrieval_plan,
            retrieval_filters=retrieval_filters,
            region=region,
            message=message,
        )
    )
    return metrics[:12]


def _build_scoped_sql_evidence_metrics(
    db: Session,
    *,
    current_user: User,
    retrieval_plan: RetrievalPlan,
    retrieval_filters: dict[str, Any],
    region: str,
    message: str,
) -> list[ChatMetricFact]:
    if current_user.cooperative_id is None:
        return []

    entities = retrieval_plan.detected_entities if isinstance(retrieval_plan.detected_entities, dict) else {}
    products = [str(item).strip().lower() for item in (entities.get("products") or []) if str(item).strip()]
    stages = _canonical_stage_tokens(
        [str(item).strip().lower() for item in (entities.get("stages") or []) if str(item).strip()]
        + [str(item).strip().lower() for item in (retrieval_filters.get("stage_canonical") or set()) if str(item).strip()]
    )
    lot_codes = [str(item).strip().upper() for item in (entities.get("batch_codes") or []) if str(item).strip()]
    benchmark_intent = any(
        token in message.lower()
        for token in ("benchmark", "reference", "literature", "aphlis", "fao", "best practices", "agronomic")
    )

    if not (products or stages or lot_codes):
        return []

    scoped_metrics: list[ChatMetricFact] = []
    rows = db.execute(
        select(ProcessStep, Batch, Product)
        .join(Batch, Batch.id == ProcessStep.batch_id)
        .join(Product, Product.id == Batch.product_id)
        .where(Batch.cooperative_id == current_user.cooperative_id)
    ).all()

    losses: list[dict[str, Any]] = []
    for step, batch, product in rows:
        product_name = _normalize_product_name(str(product.name or ""))
        stage = str(normalize_stage(step.type) or "").lower().strip()
        lot_code = str(batch.code or "").upper().strip()
        loss_kg = max(float(step.qty_in) - float(step.qty_out), 0.0)
        loss_pct = (loss_kg / float(step.qty_in) * 100.0) if step.qty_in else 0.0
        losses.append(
            {
                "product": product_name,
                "stage": stage,
                "lot": lot_code,
                "loss_pct": loss_pct,
                "batch_id": str(batch.id),
                "step_id": str(step.id),
            }
        )

    batch_rows = db.execute(
        select(Batch, Product)
        .join(Product, Product.id == Batch.product_id)
        .where(Batch.cooperative_id == current_user.cooperative_id)
    ).all()
    batch_by_code = {str(batch.code or "").upper().strip(): (batch, product) for batch, product in batch_rows}

    # 1) Lot-level facts.
    for lot_code in lot_codes[:2]:
        row = batch_by_code.get(lot_code)
        if row is None:
            continue
        batch, product = row
        lot_loss_pct = ((float(batch.initial_qty) - float(batch.current_qty)) / float(batch.initial_qty) * 100.0) if batch.initial_qty else 0.0
        scoped_metrics.append(
            ChatMetricFact(
                source_id=f"scoped-sql-lot:{batch.id}",
                region=region,
                crop=str(product.name or "multi"),
                metric="scoped.lot_loss_pct",
                period="current",
                value=round_metric(lot_loss_pct),
                unit="%",
                notes=_scope_fact_notes(
                    scope_level="LOT",
                    product=str(product.name or ""),
                    stage=",".join(stages) if stages else "",
                    lot=lot_code,
                    applies_to_query=True,
                    source="live_sql",
                ),
            )
        )
        scoped_metrics.append(
            ChatMetricFact(
                source_id=f"scoped-sql-lot:{batch.id}",
                region=region,
                crop=str(product.name or "multi"),
                metric="scoped.lot_current_qty",
                period="current",
                value=round_metric(float(batch.current_qty or 0.0)),
                unit=str(batch.unit or "kg"),
                notes=_scope_fact_notes(
                    scope_level="LOT",
                    product=str(product.name or ""),
                    stage=",".join(stages) if stages else "",
                    lot=lot_code,
                    applies_to_query=True,
                    source="live_sql",
                ),
            )
        )

    def _avg(values: list[float]) -> Optional[float]:
        if not values:
            return None
        return float(sum(values) / len(values))

    # 2) Product-stage facts.
    if products and stages:
        for product_name in products[:1]:
            for stage_name in stages[:1]:
                selected = [item["loss_pct"] for item in losses if item["product"] == product_name and item["stage"] == stage_name]
                value = _avg(selected)
                if value is None:
                    continue
                scoped_metrics.append(
                    ChatMetricFact(
                        source_id=f"scoped-sql-product-stage:{product_name}:{stage_name}",
                        region=region,
                        crop=product_name,
                        metric="scoped.product_stage_loss_pct",
                        period="current",
                        value=round_metric(value),
                        unit="%",
                        notes=_scope_fact_notes(
                            scope_level="PRODUCT_STAGE",
                            product=product_name,
                            stage=stage_name,
                            lot="",
                            applies_to_query=True,
                            source="live_sql",
                        ),
                    )
                )

    # 3) Product-level facts.
    if products:
        for product_name in products[:1]:
            selected = [item["loss_pct"] for item in losses if item["product"] == product_name]
            value = _avg(selected)
            if value is None:
                continue
            scoped_metrics.append(
                ChatMetricFact(
                    source_id=f"scoped-sql-product:{product_name}",
                    region=region,
                    crop=product_name,
                    metric="scoped.product_loss_pct",
                    period="current",
                    value=round_metric(value),
                    unit="%",
                    notes=_scope_fact_notes(
                        scope_level="PRODUCT",
                        product=product_name,
                        stage=",".join(stages) if stages else "",
                        lot="",
                        applies_to_query=True,
                        source="live_sql",
                    ),
                )
            )

    # 4) Cooperative-level facts.
    coop_loss = _avg([item["loss_pct"] for item in losses])
    if coop_loss is not None:
        scoped_metrics.append(
            ChatMetricFact(
                source_id="scoped-sql-cooperative",
                region=region,
                crop="multi",
                metric="scoped.cooperative_loss_pct",
                period="current",
                value=round_metric(coop_loss),
                unit="%",
                notes=_scope_fact_notes(
                    scope_level="COOPERATIVE",
                    product=",".join(products) if products else "",
                    stage=",".join(stages) if stages else "",
                    lot=",".join(lot_codes) if lot_codes else "",
                    applies_to_query=not (products or stages or lot_codes),
                    source="live_sql",
                ),
            )
        )

    # 5) Benchmark-support facts.
    if benchmark_intent or products:
        metric_rows = db.scalars(select(ReferenceMetric).order_by(ReferenceMetric.period.desc()).limit(20)).all()
        selected_metric: Optional[ReferenceMetric] = None
        for row in metric_rows:
            crop_name = _normalize_product_name(str(row.crop or ""))
            metric_name = str(row.metric or "").lower()
            if products and crop_name and crop_name not in products:
                continue
            if "loss" not in metric_name and "perte" not in metric_name:
                continue
            selected_metric = row
            break
        if selected_metric is not None:
            scoped_metrics.append(
                ChatMetricFact(
                    source_id=f"scoped-sql-benchmark:{selected_metric.id}",
                    region=str(selected_metric.region or region),
                    crop=str(selected_metric.crop or "multi"),
                    metric="scoped.benchmark_loss_pct",
                    period=str(selected_metric.period or "reference"),
                    value=round_metric(float(selected_metric.value or 0.0)),
                    unit=str(selected_metric.unit or "%"),
                    notes=_scope_fact_notes(
                        scope_level="BENCHMARK",
                        product=str(selected_metric.crop or ""),
                        stage=",".join(stages) if stages else "",
                        lot="",
                        applies_to_query=False,
                        source="reference_sql",
                    ),
                )
            )

    return scoped_metrics[:8]


def _canonical_stage_tokens(values: Sequence[str]) -> list[str]:
    canonical: list[str] = []
    for stage in values:
        if stage in {"sechage", "séchage", "drying"}:
            key = "drying"
        elif stage in {"tri", "sorting"}:
            key = "sorting"
        elif stage in {"nettoyage", "cleaning"}:
            key = "cleaning"
        elif stage in {"emballage", "packaging"}:
            key = "packaging"
        elif stage in {"stockage", "storage"}:
            key = "storage"
        else:
            key = stage
        if key and key not in canonical:
            canonical.append(key)
    return canonical


def _normalize_product_name(raw: str) -> str:
    token = str(raw or "").lower().strip()
    if not token:
        return ""
    for key, canonical in PRODUCT_CANONICAL_MAP.items():
        if key in token:
            return canonical
    return token


def _scope_fact_notes(
    *,
    scope_level: str,
    product: str,
    stage: str,
    lot: str,
    applies_to_query: bool,
    source: str,
) -> str:
    return (
        f"scope_level={scope_level};product={product or 'none'};stage={stage or 'none'};lot={lot or 'none'};"
        f"applies_to_query={'true' if applies_to_query else 'false'};source={source}"
    )


def _build_executive_ui_blocks(
    *,
    message: str,
    retrieval_plan: RetrievalPlan,
    dashboard: Optional[ChatDashboardSnapshot],
    context_metrics: Sequence[ChatMetricFact],
    citations: Sequence[ChatCitation],
    orchestrated_context: Any,
    fallback_blocks: Sequence[ChatUIBlock],
) -> list[ChatUIBlock]:
    metric_map = {item.metric: item for item in context_metrics}
    confidence_metric = metric_map.get("orchestration.confidence_score")
    confidence_score = float(confidence_metric.value) if confidence_metric else 0.0
    confidence_label = _confidence_label_fr(str(confidence_metric.unit if confidence_metric else "MOYEN"))
    warning_metric = metric_map.get("orchestration.warning_count")
    warnings = []
    if warning_metric and warning_metric.notes:
        warnings = [item for item in str(warning_metric.notes).split("|") if item and item != "none"]

    intent = retrieval_plan.intent_type
    if intent in {
        RetrievalIntentType.SMALL_TALK.value,
        RetrievalIntentType.CLARIFICATION_NEEDED.value,
        RetrievalIntentType.UNSUPPORTED.value,
    }:
        return []
    if intent == RetrievalIntentType.SQL_ONLY.value:
        # Keep SQL-only deterministic. For explicit table/list asks, expose a compact summary + table.
        if _is_member_list_request(message):
            member_table = next((block for block in fallback_blocks if block.type == "table"), None)
            if member_table:
                rows = []
                if isinstance(member_table.payload, dict):
                    candidate_rows = member_table.payload.get("rows")
                    if isinstance(candidate_rows, list):
                        rows = candidate_rows
                return [
                    ChatUIBlock(
                        type="executive_summary",
                        title="Résumé exécutif",
                        payload={
                            "text": f"{len(rows)} membres trouvés dans la coopérative.",
                            "intent_type": intent,
                        },
                    ),
                    member_table,
                ]
        if _is_lot_table_request(message) or any(token in message.lower() for token in ("tableau", "table")):
            generic_table = next((block for block in fallback_blocks if block.type == "table"), None)
            if generic_table:
                return [generic_table]
        return []
    base_summary = _build_executive_summary_text(
        message=message,
        intent=intent,
        dashboard=dashboard,
        metric_map=metric_map,
        warnings=warnings,
    )
    kpi_items = _build_kpi_items(metric_map=metric_map, dashboard=dashboard)
    risk_items = _build_risk_items(metric_map=metric_map, warnings=warnings)
    action_items = _build_action_items(message=message, warnings=warnings, metric_map=metric_map)
    evidence_items = [
        {
            "source": item.source_id,
            "region": item.region,
            "culture": item.crop,
            "thème": item.topic,
            "extrait": item.excerpt,
        }
        for item in citations[:8]
    ]

    blocks: list[ChatUIBlock] = [
        ChatUIBlock(
            type="executive_summary",
            title="Résumé exécutif",
            payload={"text": base_summary, "intent_type": intent},
        ),
        ChatUIBlock(
            type="kpi_grid",
            title="Indicateurs opérationnels",
            payload={"items": kpi_items[:4]},
        ),
    ]

    if risk_items:
        blocks.append(
            ChatUIBlock(
                type="risk_cards",
                title="Risques critiques",
                payload={"items": risk_items},
            )
        )
    analysis_points = _build_analysis_points(message=message, intent=intent, warnings=warnings)
    if analysis_points:
        blocks.append(
            ChatUIBlock(
                type="analysis_section",
                title="Analyse opérationnelle",
                payload={"points": analysis_points[:2]},
            )
        )

    if _is_benchmark_question(message):
        blocks.append(
            ChatUIBlock(
                type="benchmark_card",
                title="Comparaison de référence",
                payload={
                    "note": "Les références externes servent de repère et ne remplacent pas les mesures terrain de la coopérative.",
                    "citations_count": len(citations),
                },
            )
        )

    blocks.append(
        ChatUIBlock(
            type="recommendation_cards",
            title="Actions recommandées",
            payload={"items": action_items},
        )
    )
    if intent == RetrievalIntentType.HYBRID.value:
        blocks.append(
            ChatUIBlock(
                type="confidence_block",
                title="Niveau de confiance",
                payload={
                    "label": confidence_label,
                    "score": round_metric(confidence_score * 100.0),
                    "warnings": [_warning_label_fr(item) for item in warnings],
                },
            )
        )
    blocks.append(
        ChatUIBlock(
            type="evidence_drawer",
            title="Sources et justification",
            payload={
                "items": evidence_items,
                "retrieval": getattr(orchestrated_context, "retrieval_summary", {}) if orchestrated_context else {},
            },
        )
    )

    supplemental_blocks = [block for block in fallback_blocks if block.type in {"table"}]
    return [*blocks, *supplemental_blocks[:1]]


def _build_executive_summary_text(
    *,
    message: str,
    intent: str,
    dashboard: Optional[ChatDashboardSnapshot],
    metric_map: dict[str, ChatMetricFact],
    warnings: Sequence[str],
) -> str:
    if intent == RetrievalIntentType.SQL_ONLY.value:
        available = metric_map.get("available_stock_kg")
        active = metric_map.get("scoped.lot_current_qty")
        if available:
            return (
                f"Réponse opérationnelle directe basée sur les données SQL en temps réel. "
                f"Stock disponible observé : {round_metric(available.value)} kg."
            )
        if active:
            return (
                f"État du lot établi à partir des écritures opérationnelles. "
                f"Quantité actuelle observée : {round_metric(active.value)} {active.unit}."
            )
        return "Réponse SQL concise fournie à partir des données opérationnelles disponibles."

    if intent == RetrievalIntentType.RAG_ONLY.value:
        if warnings:
            return "Analyse sémantique fournie avec prudence. Les sources récupérées sont limitées et nécessitent validation terrain."
        return "Analyse de connaissance fournie à partir des références agronomiques et des contenus historiques disponibles."

    if dashboard:
        return (
            f"Pertes {dashboard.loss_rate:.1f}% et efficacité {dashboard.efficiency_rate:.1f}% sur la période. "
            "Priorité aux actions opérationnelles à impact immédiat."
        )
    return "Synthèse hybride établie à partir des données opérationnelles et des sources contextuelles disponibles."


def _build_kpi_items(*, metric_map: dict[str, ChatMetricFact], dashboard: Optional[ChatDashboardSnapshot]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    mapping = [
        ("loss_rate", "Pertes globales", "%"),
        ("efficiency_rate", "Efficacité", "%"),
        ("available_stock_kg", "Stock disponible", "kg"),
        ("low_stock_products", "Alertes stock", "produits"),
        ("avg_batch_loss_pct", "Perte moyenne lots", "%"),
        ("worst_batch_loss_pct", "Perte la plus élevée", "%"),
    ]
    for key, label, unit_default in mapping:
        metric = metric_map.get(key) or metric_map.get(f"ops-{key}") or metric_map.get(f"scoped.{key}")
        if metric:
            rows.append(
                {
                    "label": label,
                    "value": round_metric(metric.value),
                    "unit": metric.unit if metric.unit and metric.unit != "binary" else unit_default,
                    "severity": _severity_from_metric(key, float(metric.value)),
                }
            )
    if dashboard and not rows:
        rows.extend(
            [
                {"label": "Pertes globales", "value": round_metric(dashboard.loss_rate), "unit": "%", "severity": _severity_from_metric("loss_rate", dashboard.loss_rate)},
                {"label": "Efficacité", "value": round_metric(dashboard.efficiency_rate), "unit": "%", "severity": _severity_from_metric("efficiency_rate", dashboard.efficiency_rate)},
            ]
        )
    return rows[:8]


def _build_risk_items(*, metric_map: dict[str, ChatMetricFact], warnings: Sequence[str]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    worst = metric_map.get("worst_batch_loss_pct")
    if worst and worst.value >= 12:
        risks.append(
            {
                "niveau": "Élevé" if worst.value >= 18 else "Moyen",
                "titre": "Pertes élevées sur les lots",
                "impact": f"La perte maximale observée atteint {round_metric(worst.value)}%.",
            }
        )
    if "CONTRADICTORY_EVIDENCE" in warnings:
        risks.append(
            {
                "niveau": "Moyen",
                "titre": "Signal contradictoire",
                "impact": "Des divergences existent entre certaines sources; prioriser les faits SQL terrain.",
            }
        )
    if "STALE_CONTEXT" in warnings:
        risks.append(
            {
                "niveau": "Moyen",
                "titre": "Contexte potentiellement ancien",
                "impact": "Certaines informations sémantiques peuvent nécessiter une actualisation.",
            }
        )
    return risks


def _build_action_items(*, message: str, warnings: Sequence[str], metric_map: dict[str, ChatMetricFact]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    lowered = message.lower()
    if "sechage" in lowered or "séchage" in lowered or "drying" in lowered:
        actions.extend(
            [
                {"priorité": "Priorité élevée", "action": "Vérifier l'uniformité du séchage sur les lots en cours.", "impact_attendu": "Réduction des pertes matière sur l'étape critique."},
                {"priorité": "Priorité élevée", "action": "Contrôler le niveau d'humidité avant et après séchage.", "impact_attendu": "Stabilisation du rendement de sortie."},
            ]
        )
    if metric_map.get("available_stock_kg"):
        actions.append(
            {
                "priorité": "Priorité moyenne",
                "action": "Suivre le stock disponible et les réservations en lots chaque jour.",
                "impact_attendu": "Prévention des ruptures et meilleure planification.",
            }
        )
    if "ML_LOGS_EMPTY" in warnings:
        actions.append(
            {
                "priorité": "Priorité faible",
                "action": "Compléter l'historique des lots, pertes et étapes de transformation pour améliorer la précision des recommandations.",
                "impact_attendu": "Niveau de confiance plus robuste sur les recommandations.",
            }
        )
    if not actions:
        actions.append(
            {
                "priorité": "Priorité moyenne",
                "action": "Valider les données du lot concerné puis appliquer les contrôles opérationnels standards.",
                "impact_attendu": "Décision plus rapide et réduction du risque d'écart.",
            }
        )
    return actions[:5]


def _build_analysis_points(*, message: str, intent: str, warnings: Sequence[str]) -> list[str]:
    points = []
    if intent == RetrievalIntentType.SQL_ONLY.value:
        points.append("Les constats sont issus de données opérationnelles exactes et à jour.")
    elif intent == RetrievalIntentType.RAG_ONLY.value:
        points.append("Les constats proviennent des contenus de référence et des connaissances agronomiques disponibles.")
    else:
        points.append("Les constats combinent données SQL exactes et contexte sémantique de référence.")
    if _is_benchmark_question(message):
        points.append("La comparaison benchmark est utilisée comme repère, sans remplacer les mesures réelles de la coopérative.")
    if warnings:
        points.append("Certains signaux demandent une validation terrain avant décision finale.")
    return points


def _is_benchmark_question(message: str) -> bool:
    lowered = message.lower()
    return any(token in lowered for token in ("benchmark", "reference", "référence", "literature", "aphlis", "fao"))


def _is_member_list_request(message: str) -> bool:
    lowered = " ".join(message.lower().split())
    has_member_hint = any(token in lowered for token in ("membre", "membres", "member", "members", "producteur", "producteurs", "farmer", "farmers"))
    has_list_hint = any(token in lowered for token in ("liste", "lister", "list", "listing", "affiche", "afficher", "montre", "montrer", "tableau", "table"))
    return has_member_hint and has_list_hint


def _is_lot_table_request(message: str) -> bool:
    lowered = " ".join(message.lower().split())
    has_lot_hint = any(token in lowered for token in ("lot", "lots", "batch", "batches"))
    has_table_hint = any(token in lowered for token in ("tableau", "table", "liste", "lister", "list", "affiche", "afficher", "montre", "montrer"))
    return has_lot_hint and has_table_hint


def _is_active_lot_filter_requested(message: str) -> bool:
    lowered = " ".join(message.lower().split())
    return any(token in lowered for token in ("actif", "actifs", "active", "actives", "en cours"))


def _requested_table_limit(message: str, *, default: int = 25, maximum: int = 100) -> int:
    match = re.search(r"\b(\d{1,3})\b", str(message or ""))
    if not match:
        return default
    value = int(match.group(1))
    if value <= 0:
        return default
    return max(1, min(value, maximum))


def _lot_loss_pct(initial_qty: float, current_qty: float) -> float:
    if initial_qty <= 0:
        return 0.0
    return ((initial_qty - current_qty) / initial_qty) * 100.0


def _fetch_lot_directory_rows(
    db: Session,
    *,
    current_user: User,
    message: str,
    limit: int = 25,
) -> list[tuple[Any, Any, Any, Any, Any, Any]]:
    if current_user.cooperative_id is None:
        return []
    stmt = (
        select(Batch.code, Product.name, Batch.initial_qty, Batch.current_qty, Batch.status, Batch.updated_at)
        .join(Product, Product.id == Batch.product_id)
        .where(Batch.cooperative_id == current_user.cooperative_id)
    )
    if _is_active_lot_filter_requested(message):
        stmt = stmt.where(func.lower(cast(Batch.status, String)) == "active")
    stmt = stmt.order_by(Batch.updated_at.desc(), Batch.code.asc()).limit(max(1, min(limit, 100)))
    return db.execute(stmt).all()


def _lot_row_to_fact_row(row: tuple[Any, Any, Any, Any, Any, Any]) -> dict[str, Any]:
    code, product, initial_qty, current_qty, status, updated_at = row
    qty_in = float(initial_qty or 0.0)
    qty_out = float(current_qty or 0.0)
    return {
        "lot_code": str(code),
        "product": str(product),
        "qty_in": round_metric(qty_in),
        "qty_out": round_metric(qty_out),
        "loss_pct": round_metric(_lot_loss_pct(qty_in, qty_out)),
        "status": str(status.value if hasattr(status, "value") else status),
        "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at or ""),
    }


def _severity_from_metric(metric_key: str, value: float) -> str:
    key = metric_key.lower()
    if "loss" in key or "perte" in key:
        if value >= 18:
            return "Élevé"
        if value >= 10:
            return "Moyen"
        return "Faible"
    if "efficiency" in key or "efficac" in key:
        if value < 70:
            return "Élevé"
        if value < 82:
            return "Moyen"
        return "Faible"
    if "stock" in key and "low" in key:
        if value >= 4:
            return "Élevé"
        if value >= 2:
            return "Moyen"
        return "Faible"
    return "Moyen"


def _warning_label_fr(code: str) -> str:
    labels = {
        "STALE_CONTEXT": "Contexte possiblement ancien",
        "LOW_GROUNDING_CONFIDENCE": "Confiance de grounding limitée",
        "CONTRADICTORY_EVIDENCE": "Éléments contradictoires",
        "LIMITED_EVIDENCE": "Sources limitées",
        "SQL_CONTEXT_MISSING": "Contexte SQL incomplet",
        "ML_CONTEXT_MISSING": "Contexte ML incomplet",
        "ML_LOGS_EMPTY": "Journaux ML indisponibles",
        "SCOPE_CONTAMINATION_RISK": "Risque de contamination de périmètre",
    }
    return labels.get(code, code)


def _confidence_label_fr(label: str) -> str:
    key = str(label).upper().strip()
    if key == "HIGH":
        return "Élevé"
    if key == "LOW":
        return "Faible"
    return "Moyen"


def _build_ui_blocks(
    db: Session,
    *,
    current_user: User,
    message: str,
    dashboard: Optional[ChatDashboardSnapshot],
) -> List[ChatUIBlock]:
    blocks: list[ChatUIBlock] = []
    member_list_request = _is_member_list_request(message)
    lot_table_request = _is_lot_table_request(message)
    if dashboard and not member_list_request and not lot_table_request:
        blocks.append(
            ChatUIBlock(
                type="kpi",
                title="Vue d'ensemble coopérative",
                payload={
                    "loss_rate": round_metric(dashboard.loss_rate),
                    "efficiency_rate": round_metric(dashboard.efficiency_rate),
                    "total_production": round_metric(dashboard.total_production),
                    "active_batches": dashboard.number_of_active_batches,
                    "stock_alerts": dashboard.stock_alerts,
                },
            )
        )

    tokens = set(_tokenize(message))
    if member_list_request:
        blocks.extend(_build_member_directory_blocks(db, current_user=current_user))
        return blocks[:8]
    if lot_table_request:
        blocks.extend(_build_lot_directory_blocks(db, current_user=current_user, message=message))
        return blocks[:8]
    if {"rentable", "profit", "marge", "revenu", "gagner"} & tokens or _has_prefix(tokens, ("rentab", "profit")):
        blocks.extend(_build_member_profitability_blocks(db, current_user=current_user))
    if MEMBER_HINTS & tokens:
        blocks.extend(_build_member_efficiency_blocks(db, current_user=current_user))
    if STOCK_HINTS & tokens:
        blocks.extend(_build_stock_blocks(db, current_user=current_user))
    if LOSS_HINTS & tokens:
        blocks.extend(_build_process_loss_blocks(db, current_user=current_user))
        blocks.extend(_build_batch_loss_blocks(db, current_user=current_user))
    if COMMERCIAL_HINTS & tokens:
        blocks.extend(_build_commercialisation_blocks(db, current_user=current_user))

    return blocks[:8]


def _has_prefix(tokens: set[str], prefixes: tuple[str, ...]) -> bool:
    for token in tokens:
        if any(token.startswith(prefix) for prefix in prefixes):
            return True
    return False


def _build_member_profitability_blocks(db: Session, *, current_user: User) -> list[ChatUIBlock]:
    if current_user.cooperative_id is None:
        return []
    cooperative_id_param = _uuid_sql_param(db, current_user.cooperative_id)
    stmt = text(
        """
        WITH input_agg AS (
            SELECT
                member_id,
                cooperative_id,
                COALESCE(SUM(estimated_value), 0) AS gross_value_fcfa,
                COALESCE(SUM(quantity), 0) AS collected_qty
            FROM inputs
            WHERE cooperative_id = :cooperative_id
            GROUP BY member_id, cooperative_id
        ),
        advance_agg AS (
            SELECT
                farmer_id,
                cooperative_id,
                COALESCE(SUM(amount_fcfa), 0) AS advances_fcfa
            FROM farmer_advances
            WHERE cooperative_id = :cooperative_id
              AND status = 'active'
            GROUP BY farmer_id, cooperative_id
        )
        SELECT
            m.full_name AS member_name,
            COALESCE(i.gross_value_fcfa, 0) AS gross_value_fcfa,
            COALESCE(a.advances_fcfa, 0) AS advances_fcfa,
            COALESCE(i.gross_value_fcfa, 0) - COALESCE(a.advances_fcfa, 0) AS net_value_fcfa,
            COALESCE(i.collected_qty, 0) AS collected_qty
        FROM members m
        LEFT JOIN input_agg i
            ON i.member_id = m.id
           AND i.cooperative_id = m.cooperative_id
        LEFT JOIN advance_agg a
            ON a.farmer_id = m.id
           AND a.cooperative_id = m.cooperative_id
        WHERE m.cooperative_id = :cooperative_id
        ORDER BY net_value_fcfa DESC
        LIMIT 5
        """
    )
    rows = db.execute(stmt, {"cooperative_id": cooperative_id_param}).mappings().all()
    if not rows:
        return []

    table_rows = [
        [
            str(row["member_name"]),
            round_metric(float(row["gross_value_fcfa"] or 0)),
            round_metric(float(row["advances_fcfa"] or 0)),
            round_metric(float(row["net_value_fcfa"] or 0)),
            round_metric(float(row["collected_qty"] or 0)),
        ]
        for row in rows
    ]
    chart_labels = [str(row["member_name"]) for row in rows]
    chart_values = [round_metric(float(row["net_value_fcfa"] or 0)) for row in rows]
    return [
        ChatUIBlock(
            type="table",
            title="Top membres rentabilité",
            payload={
                "columns": ["Membre", "Valeur brute FCFA", "Avances FCFA", "Valeur nette FCFA", "Collecte kg"],
                "rows": table_rows,
            },
        ),
        ChatUIBlock(
            type="bar_chart",
            title="Valeur nette par membre",
            payload={"labels": chart_labels, "series": [{"name": "Valeur nette FCFA", "data": chart_values}]},
        ),
    ]


def _build_stock_blocks(db: Session, *, current_user: User) -> list[ChatUIBlock]:
    if current_user.cooperative_id is None:
        return []
    cooperative_id_param = _uuid_sql_param(db, current_user.cooperative_id)
    stmt = text(
        """
        SELECT
            p.name AS product_name,
            s.total_stock_kg AS total_stock_kg,
            s.threshold AS threshold_kg,
            (s.total_stock_kg - s.threshold) AS delta_kg
        FROM stocks s
        JOIN products p ON p.id = s.product_id
        WHERE s.cooperative_id = :cooperative_id
        ORDER BY delta_kg ASC
        LIMIT 8
        """
    )
    rows = db.execute(stmt, {"cooperative_id": cooperative_id_param}).mappings().all()
    if not rows:
        return []

    table_rows = []
    labels: list[str] = []
    values: list[float] = []
    for row in rows:
        delta = round_metric(float(row["delta_kg"] or 0))
        table_rows.append(
            [
                str(row["product_name"]),
                round_metric(float(row["total_stock_kg"] or 0)),
                round_metric(float(row["threshold_kg"] or 0)),
                delta,
                "alerte" if delta < 0 else "ok",
            ]
        )
        labels.append(str(row["product_name"]))
        values.append(delta)

    return [
        ChatUIBlock(
            type="table",
            title="Anomalies de stock",
            payload={
                "columns": ["Produit", "Stock kg", "Seuil kg", "Delta kg", "Statut"],
                "rows": table_rows,
            },
        ),
        ChatUIBlock(
            type="bar_chart",
            title="Delta stock vs seuil",
            payload={"labels": labels, "series": [{"name": "Delta kg", "data": values}]},
        ),
    ]


def _build_process_loss_blocks(db: Session, *, current_user: User) -> list[ChatUIBlock]:
    if current_user.cooperative_id is None:
        return []
    cooperative_id_param = _uuid_sql_param(db, current_user.cooperative_id)
    stmt = text(
        """
        SELECT
            ps.type AS step_type,
            AVG(
                CASE
                    WHEN ps.qty_in > 0 THEN ((ps.qty_in - ps.qty_out) / ps.qty_in) * 100
                    ELSE 0
                END
            ) AS avg_loss_pct,
            COUNT(*) AS step_count
        FROM process_steps ps
        JOIN batches b ON b.id = ps.batch_id
        WHERE b.cooperative_id = :cooperative_id
        GROUP BY ps.type
        ORDER BY avg_loss_pct DESC
        LIMIT 8
        """
    )
    rows = db.execute(stmt, {"cooperative_id": cooperative_id_param}).mappings().all()
    if not rows:
        return []

    table_rows = [
        [str(row["step_type"]), round_metric(float(row["avg_loss_pct"] or 0)), int(row["step_count"] or 0)]
        for row in rows
    ]
    return [
        ChatUIBlock(
            type="table",
            title="Pertes moyennes par étape",
            payload={"columns": ["Étape", "Perte moyenne %", "Nombre d'étapes"], "rows": table_rows},
        ),
        ChatUIBlock(
            type="line_chart",
            title="Tendance pertes par étape",
            payload={
                "labels": [str(row["step_type"]) for row in rows],
                "series": [{"name": "Perte moyenne %", "data": [round_metric(float(row["avg_loss_pct"] or 0)) for row in rows]}],
            },
        ),
    ]


def _build_batch_loss_blocks(db: Session, *, current_user: User) -> list[ChatUIBlock]:
    if current_user.cooperative_id is None:
        return []
    cooperative_id_param = _uuid_sql_param(db, current_user.cooperative_id)
    stmt = text(
        """
        SELECT
            b.code AS batch_code,
            p.name AS product_name,
            b.initial_qty AS initial_qty_kg,
            b.current_qty AS current_qty_kg,
            CASE
                WHEN (b.initial_qty - b.current_qty) > 0 THEN (b.initial_qty - b.current_qty)
                ELSE 0
            END AS loss_kg,
            CASE
                WHEN b.initial_qty > 0 THEN ((b.initial_qty - b.current_qty) / b.initial_qty) * 100
                ELSE 0
            END AS loss_pct
        FROM batches b
        JOIN products p ON p.id = b.product_id
        WHERE b.cooperative_id = :cooperative_id
        ORDER BY loss_pct DESC, loss_kg DESC
        LIMIT 8
        """
    )
    rows = db.execute(stmt, {"cooperative_id": cooperative_id_param}).mappings().all()
    if not rows:
        return []

    table_rows = [
        [
            str(row["batch_code"]),
            str(row["product_name"]),
            round_metric(float(row["initial_qty_kg"] or 0)),
            round_metric(float(row["current_qty_kg"] or 0)),
            round_metric(float(row["loss_kg"] or 0)),
            round_metric(float(row["loss_pct"] or 0)),
        ]
        for row in rows
    ]
    return [
        ChatUIBlock(
            type="table",
            title="Pertes par lot",
            payload={
                "columns": ["Lot", "Produit", "Initial kg", "Actuel kg", "Perte kg", "Perte %"],
                "rows": table_rows,
            },
        )
    ]


def _build_member_efficiency_blocks(db: Session, *, current_user: User) -> list[ChatUIBlock]:
    if current_user.cooperative_id is None:
        return []
    cooperative_id_param = _uuid_sql_param(db, current_user.cooperative_id)
    stmt = text(
        """
        WITH input_agg AS (
            SELECT
                member_id,
                COALESCE(SUM(quantity), 0) AS collected_kg,
                COALESCE(SUM(estimated_value), 0) AS gross_value_fcfa
            FROM inputs
            WHERE cooperative_id = :cooperative_id
            GROUP BY member_id
        ),
        advance_agg AS (
            SELECT
                farmer_id,
                COALESCE(SUM(amount_fcfa), 0) AS advances_fcfa
            FROM farmer_advances
            WHERE cooperative_id = :cooperative_id
              AND status = 'active'
            GROUP BY farmer_id
        )
        SELECT
            m.full_name AS member_name,
            COALESCE(i.collected_kg, 0) AS collected_kg,
            COALESCE(i.gross_value_fcfa, 0) AS gross_value_fcfa,
            COALESCE(a.advances_fcfa, 0) AS advances_fcfa,
            CASE
                WHEN COALESCE(i.collected_kg, 0) > 0
                THEN (COALESCE(i.gross_value_fcfa, 0) - COALESCE(a.advances_fcfa, 0)) / COALESCE(i.collected_kg, 1)
                ELSE NULL
            END AS net_cost_per_kg
        FROM members m
        LEFT JOIN input_agg i ON i.member_id = m.id
        LEFT JOIN advance_agg a ON a.farmer_id = m.id
        WHERE m.cooperative_id = :cooperative_id
        ORDER BY collected_kg DESC
        LIMIT 8
        """
    )
    rows = db.execute(stmt, {"cooperative_id": cooperative_id_param}).mappings().all()
    if not rows:
        return []

    table_rows = [
        [
            str(row["member_name"]),
            round_metric(float(row["collected_kg"] or 0)),
            round_metric(float(row["gross_value_fcfa"] or 0)),
            round_metric(float(row["advances_fcfa"] or 0)),
            round_metric(float(row["net_cost_per_kg"] or 0)),
        ]
        for row in rows
    ]
    return [
        ChatUIBlock(
            type="table",
            title="Collecte et coût/kg par membre",
            payload={
                "columns": ["Membre", "Collecte kg", "Valeur brute FCFA", "Avances FCFA", "Coût net/kg FCFA"],
                "rows": table_rows,
            },
        )
    ]


def _build_member_directory_blocks(db: Session, *, current_user: User) -> list[ChatUIBlock]:
    columns = ["code", "nom", "produit principal", "statut", "parcelles", "surface_ha"]
    if current_user.cooperative_id is None:
        return [
            ChatUIBlock(
                type="table",
                title="Liste des membres",
                payload={"columns": columns, "rows": []},
            )
        ]
    rows = db.execute(
        select(
            Member.code,
            Member.full_name,
            Member.main_product,
            Member.status,
            Member.parcel_count,
            Member.area_hectares,
        )
        .where(Member.cooperative_id == current_user.cooperative_id)
        .order_by(Member.full_name.asc())
        .limit(25)
    ).all()
    if not rows:
        return [
            ChatUIBlock(
                type="table",
                title="Liste des membres",
                payload={"columns": columns, "rows": []},
            )
        ]

    table_rows = [
        [
            str(code),
            str(full_name),
            str(main_product or "-"),
            str(status.value if hasattr(status, "value") else status),
            int(parcel_count or 0),
            round_metric(float(area_hectares or 0.0)),
        ]
        for code, full_name, main_product, status, parcel_count, area_hectares in rows
    ]
    return [
        ChatUIBlock(
            type="table",
            title="Liste des membres",
            payload={
                "columns": columns,
                "rows": table_rows,
            },
        )
    ]


def _build_lot_directory_blocks(db: Session, *, current_user: User, message: str) -> list[ChatUIBlock]:
    columns = ["lot_code", "produit", "qty_in", "qty_out", "loss_pct", "statut", "updated_at"]
    if current_user.cooperative_id is None:
        return [ChatUIBlock(type="table", title="Liste des lots", payload={"columns": columns, "rows": []})]

    rows = _fetch_lot_directory_rows(
        db,
        current_user=current_user,
        message=message,
        limit=_requested_table_limit(message, default=25, maximum=100),
    )
    table_rows = []
    for row in rows:
        fact_row = _lot_row_to_fact_row(row)
        table_rows.append(
            [
                fact_row["lot_code"],
                fact_row["product"],
                fact_row["qty_in"],
                fact_row["qty_out"],
                fact_row["loss_pct"],
                fact_row["status"],
                fact_row["updated_at"],
            ]
        )
    return [ChatUIBlock(type="table", title="Liste des lots", payload={"columns": columns, "rows": table_rows})]


def _build_commercialisation_blocks(db: Session, *, current_user: User) -> list[ChatUIBlock]:
    if current_user.cooperative_id is None:
        return []
    cooperative_id_param = _uuid_sql_param(db, current_user.cooperative_id)
    product_stmt = text(
        """
        SELECT
            name,
            sale_price_fcfa,
            total_stock_kg,
            reserved_stock_kg,
            (total_stock_kg - reserved_stock_kg) AS available_stock_kg,
            status
        FROM commercial_catalog_products
        WHERE cooperative_id = :cooperative_id
        ORDER BY available_stock_kg ASC
        LIMIT 8
        """
    )
    invoice_stmt = text(
        """
        SELECT
            invoice_number,
            status,
            issue_date,
            due_date,
            total_amount_fcfa
        FROM commercial_invoices
        WHERE cooperative_id = :cooperative_id
        ORDER BY issue_date DESC
        LIMIT 8
        """
    )
    product_rows = db.execute(product_stmt, {"cooperative_id": cooperative_id_param}).mappings().all()
    invoice_rows = db.execute(invoice_stmt, {"cooperative_id": cooperative_id_param}).mappings().all()

    blocks: list[ChatUIBlock] = []
    if product_rows:
        blocks.append(
            ChatUIBlock(
                type="table",
                title="Produits commercialisation (stock)",
                payload={
                    "columns": ["Produit", "Prix FCFA", "Stock total kg", "Réservé kg", "Disponible kg", "Statut"],
                    "rows": [
                        [
                            str(row["name"]),
                            round_metric(float(row["sale_price_fcfa"] or 0)),
                            round_metric(float(row["total_stock_kg"] or 0)),
                            round_metric(float(row["reserved_stock_kg"] or 0)),
                            round_metric(float(row["available_stock_kg"] or 0)),
                            str(row["status"]),
                        ]
                        for row in product_rows
                    ],
                },
            )
        )
    if invoice_rows:
        blocks.append(
            ChatUIBlock(
                type="table",
                title="Factures commercialisation",
                payload={
                    "columns": ["Facture", "Statut", "Date émission", "Échéance", "Total FCFA"],
                    "rows": [
                        [
                            str(row["invoice_number"]),
                            str(row["status"]),
                            str(row["issue_date"]),
                            str(row["due_date"] or ""),
                            round_metric(float(row["total_amount_fcfa"] or 0)),
                        ]
                        for row in invoice_rows
                    ],
                },
            )
        )
    return blocks


def _to_message_read(message: ChatMessage) -> ChatMessageRead:
    citations = _safe_parse_citations(message.citations_json)
    context_metrics = _safe_parse_metrics(message.context_metrics_json)
    ui_blocks = _safe_parse_ui_blocks(message.ui_blocks_json)
    dashboard = None
    if isinstance(message.dashboard_json, dict):
        try:
            dashboard = ChatDashboardSnapshot.model_validate(message.dashboard_json)
        except Exception:
            dashboard = None

    role = message.role if message.role in {"user", "assistant", "system"} else "assistant"
    return ChatMessageRead(
        id=message.id,
        session_id=message.session_id,
        role=role,
        content=message.content,
        created_at=message.created_at,
        mode=message.mode,
        llm_provider=message.llm_provider,
        llm_model=message.llm_model,
        citations=citations,
        context_metrics=context_metrics,
        dashboard=dashboard,
        ui_blocks=ui_blocks,
    )


def _safe_parse_citations(raw: Optional[list[dict]]) -> List[ChatCitation]:
    if not raw:
        return []
    parsed: List[ChatCitation] = []
    for item in raw:
        try:
            parsed.append(ChatCitation.model_validate(item))
        except Exception:
            continue
    return parsed


def _safe_parse_metrics(raw: Optional[list[dict]]) -> List[ChatMetricFact]:
    if not raw:
        return []
    parsed: List[ChatMetricFact] = []
    for item in raw:
        try:
            parsed.append(ChatMetricFact.model_validate(item))
        except Exception:
            continue
    return parsed


def _safe_parse_ui_blocks(raw: Optional[list[dict]]) -> List[ChatUIBlock]:
    if not raw:
        return []
    parsed: List[ChatUIBlock] = []
    for item in raw:
        try:
            parsed.append(ChatUIBlock.model_validate(item))
        except Exception:
            continue
    return parsed


def _get_last_messages_by_session(db: Session, session_ids: Sequence[UUID]) -> dict[UUID, ChatMessage]:
    if not session_ids:
        return {}

    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id.in_(session_ids))
        .order_by(ChatMessage.session_id.asc(), ChatMessage.created_at.desc())
    ).all()
    last_by_session: dict[UUID, ChatMessage] = {}
    for row in rows:
        if row.session_id not in last_by_session:
            last_by_session[row.session_id] = row
    return last_by_session


def _derive_title(message: str) -> str:
    normalized = " ".join(message.split()).strip()
    if not normalized:
        return "New conversation"
    return _trim_text(normalized, 72)


def _normalize_title(title: Optional[str]) -> Optional[str]:
    if title is None:
        return None
    normalized = " ".join(title.split()).strip()
    return normalized if normalized else None


def _trim_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _tokenize(text: str) -> List[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text.lower()) if len(token) >= 3 and token.lower() not in STOPWORDS]


def _detect_response_language(message: str) -> str:
    return "fr"


def _history_has_operational_context(history: Sequence[ChatMessage]) -> bool:
    for item in reversed(history[-6:]):
        if item.role not in {"user", "assistant"}:
            continue
        content = str(item.content or "").strip().lower()
        if not content:
            continue
        tokens = set(_tokenize(content))
        if tokens & OPERATIONAL_HINTS:
            return True
        if LOT_CODE_PATTERN.search(content):
            return True
    return False


def _classify_response_mode(message: str) -> str:
    text = message.strip()
    lowered = text.lower()
    tokens = _tokenize(lowered)

    if any(pattern.match(text) for pattern in QUICK_PATTERNS):
        return "quick"

    if tokens and all(token.isdigit() for token in tokens):
        return "quick"

    if any(token in OPERATIONAL_HINTS for token in tokens):
        return "operational"

    if len(tokens) <= 5 and "?" in text:
        return "quick"

    return "analysis"


def _build_response_style_guidance(response_mode: str) -> str:
    if response_mode == "quick":
        return (
            "Give only the direct answer in one short sentence. "
            "No numbered list, no operational recommendation, no extra framing."
        )

    if response_mode == "operational":
        return (
            "Give a concise operational response. "
            "Use short plain paragraphs. Add one concrete next step only if it helps."
        )

    return (
        "Give a concise analytical response in 2-4 sentences. "
        "No fixed template. Mention assumptions briefly when needed."
    )


def _solve_basic_math_or_echo(message: str) -> str:
    expression = re.sub(r"[^0-9+\-*/(). ]", "", message).strip()
    if not expression:
        return _trim_text(message, 80)

    # Restricted eval for simple arithmetic fallback only.
    try:
        value = eval(expression, {"__builtins__": {}}, {})  # noqa: S307
    except Exception:
        return _trim_text(message, 80)

    if isinstance(value, (int, float)):
        return str(int(value) if isinstance(value, float) and value.is_integer() else value)
    return _trim_text(message, 80)

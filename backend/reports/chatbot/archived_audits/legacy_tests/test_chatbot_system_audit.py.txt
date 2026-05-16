from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select, func

from app.api.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.batch import Batch
from app.models.enums import BatchStatus, InputStatus, PreHarvestStepStatus, ProcessStepStatus, RiskLevel
from app.models.input import Input
from app.models.member import Member
from app.models.ml import MLPredictionLog
from app.models.parcel import Parcel
from app.models.pre_harvest_step import PreHarvestStep
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.rag import RAGChunk, RAGDocument
from app.models.stock import Stock
from app.models.user import User
from app.core.config import Settings
from app.ai.utils.audit_environment import EnvironmentParityAudit

settings = Settings()
# Log environment parity for audit
EnvironmentParityAudit.log_parity_header("System Audit", f"Mode={settings.audit_mode}")

REPORT_DIR = Path(__file__).resolve().parents[2] / "app" / "ai" / "reports"
JSON_REPORT_PATH = REPORT_DIR / "chatbot_system_audit.json"
MD_REPORT_PATH = REPORT_DIR / "chatbot_system_audit.md"

FAILURE_CATEGORIES = {
    "ROUTER_WRONG_MODE",
    "ENTITY_EXTRACTION_ERROR",
    "WRONG_TOOL_SELECTED",
    "TOOL_NOT_WIRED",
    "SQL_EVIDENCE_MISSING",
    "RAG_EVIDENCE_MISSING",
    "ML_EVIDENCE_MISSING",
    "SOURCE_TYPE_WRONG",
    "SOURCE_MISSING",
    "CONTEXT_LEAKAGE",
    "LLM_CONTEXT_BAD",
    "RECOMMENDATION_UNGROUNDED",
    "ML_SQL_CONTRADICTION",
    "NOT_FRENCH",
    "FRONTEND_DISPLAY_RISK",
    "CONTENT_SEMANTIC_ERROR",
}


@dataclass(frozen=True)
class AuditCase:
    case_id: str
    module: str
    question: str
    expected_intent: str
    expected_route: str
    accepted_routes: tuple[str, ...]
    expected_scope: str
    expected_source_types: set[str]
    expected_agents: set[str]
    sequence_key: str | None = None
    sequence_step: int = 0
    expected_entities: dict[str, Any] = field(default_factory=dict)
    leakage_forbidden_terms: tuple[str, ...] = ()


def _setup_overrides(db_session):
    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: db_session.query(User).first()


def _seed_rag_tables_if_missing(db_session) -> None:
    bind = db_session.get_bind()
    Base.metadata.create_all(bind=bind, tables=[RAGDocument.__table__, RAGChunk.__table__])


def _seed_audit_data(db_session) -> None:
    _seed_rag_tables_if_missing(db_session)

    user = db_session.query(User).first()
    if user is None or user.cooperative_id is None:
        raise RuntimeError("No test user/cooperative found in fixture")

    coop_id = user.cooperative_id

    product_mango = db_session.scalar(select(Product).where(Product.cooperative_id == coop_id, Product.name == "mango"))
    if product_mango is None:
        product_mango = Product(
            cooperative_id=coop_id,
            name="mango",
            category="fruit",
            unit="kg",
            quality_grade="A",
        )
        db_session.add(product_mango)
        db_session.flush()

    product_peanut = db_session.scalar(select(Product).where(Product.cooperative_id == coop_id, Product.name == "peanut"))
    if product_peanut is None:
        product_peanut = Product(
            cooperative_id=coop_id,
            name="peanut",
            category="legume",
            unit="kg",
            quality_grade="B",
        )
        db_session.add(product_peanut)
        db_session.flush()

    member_specs = [
        ("MBR-001", "Mamadou Ba", "+221770000111", "mango"),
        ("MBR-002", "Awa Ndiaye", "+221770000112", "mango"),
        ("MBR-003", "Ibrahima Diallo", "+221770000113", "peanut"),
    ]
    members_by_name: dict[str, Member] = {}
    for code, full_name, phone, main_product in member_specs:
        existing = db_session.scalar(
            select(Member).where(Member.cooperative_id == coop_id, Member.code == code)
        )
        if existing is None:
            existing = Member(
                cooperative_id=coop_id,
                code=code,
                full_name=full_name,
                phone=phone,
                village="Thiès",
                main_product=main_product,
                parcel_count=1,
                area_hectares=2.0,
                join_date=date.today() - timedelta(days=400),
            )
            db_session.add(existing)
            db_session.flush()
        members_by_name[full_name] = existing

    parcels_spec = [
        ("PARCELLE-MB-01", "Mamadou Ba", "mango", 1.4, "Kent", 120),
        ("PARCELLE-AN-01", "Awa Ndiaye", "mango", 1.1, "Keitt", 95),
        ("PARCELLE-ID-01", "Ibrahima Diallo", "peanut", 0.9, None, None),
    ]
    parcels_by_name: dict[str, Parcel] = {}
    for parcel_name, member_name, culture, surface_ha, variety, tree_count in parcels_spec:
        member = members_by_name[member_name]
        parcel = db_session.scalar(
            select(Parcel).where(Parcel.cooperative_id == coop_id, Parcel.name == parcel_name)
        )
        if parcel is None:
            parcel = Parcel(
                cooperative_id=coop_id,
                member_id=member.id,
                name=parcel_name,
                surface_ha=surface_ha,
                main_culture=culture,
                variety=variety,
                tree_count=tree_count,
            )
            db_session.add(parcel)
            db_session.flush()
        parcels_by_name[parcel_name] = parcel

    preharvest_steps = [
        ("PARCELLE-MB-01", 1, "inspection", "Inspection sanitaire", PreHarvestStepStatus.COMPLETED, 4000.0),
        ("PARCELLE-MB-01", 2, "elagage", "Elagage", PreHarvestStepStatus.PENDING, 3000.0),
        ("PARCELLE-AN-01", 1, "fertilisation", "Fertilisation", PreHarvestStepStatus.COMPLETED, 5000.0),
        ("PARCELLE-AN-01", 2, "traitement", "Traitement phytosanitaire", PreHarvestStepStatus.PENDING, 4500.0),
        ("PARCELLE-ID-01", 1, "semis", "Semis", PreHarvestStepStatus.PENDING, 2500.0),
    ]

    for parcel_name, order, step_key, label, status, cost in preharvest_steps:
        parcel = parcels_by_name[parcel_name]
        step_exists = db_session.scalar(
            select(PreHarvestStep).where(
                PreHarvestStep.cooperative_id == coop_id,
                PreHarvestStep.parcel_id == parcel.id,
                PreHarvestStep.step_order == order,
                PreHarvestStep.step_key == step_key,
            )
        )
        if step_exists is None:
            db_session.add(
                PreHarvestStep(
                    cooperative_id=coop_id,
                    parcel_id=parcel.id,
                    member_id=parcel.member_id,
                    step_order=order,
                    step_key=step_key,
                    category="pre_harvest",
                    label=label,
                    icon="leaf",
                    status=status,
                    operation_cost_fcfa=cost,
                    realization_date=(date.today() - timedelta(days=2)) if status == PreHarvestStepStatus.COMPLETED else None,
                    created_by_user_id=user.id,
                )
            )

    today = date.today()
    input_rows = [
        ("Mamadou Ba", product_mango.id, today, 650.0, "A", InputStatus.VALIDATED),
        ("Mamadou Ba", product_mango.id, today - timedelta(days=1), 420.0, "B", InputStatus.VALIDATED),
        ("Awa Ndiaye", product_mango.id, today - timedelta(days=2), 500.0, "A", InputStatus.VALIDATED),
        ("Ibrahima Diallo", product_peanut.id, today - timedelta(days=3), 280.0, "B", InputStatus.VALIDATED),
        ("Awa Ndiaye", product_mango.id, today - timedelta(days=5), 350.0, "C", InputStatus.QUALITY_CONTROL),
    ]
    for member_name, product_id, input_date, quantity, grade, status in input_rows:
        member = members_by_name[member_name]
        exists = db_session.scalar(
            select(Input).where(
                Input.cooperative_id == coop_id,
                Input.member_id == member.id,
                Input.product_id == product_id,
                Input.date == input_date,
                Input.quantity == quantity,
                Input.grade == grade,
            )
        )
        if exists is None:
            db_session.add(
                Input(
                    cooperative_id=coop_id,
                    member_id=member.id,
                    product_id=product_id,
                    date=input_date,
                    quantity=quantity,
                    grade=grade,
                    status=status,
                )
            )

    peanut_stock = db_session.scalar(
        select(Stock).where(Stock.cooperative_id == coop_id, Stock.product_id == product_peanut.id)
    )
    if peanut_stock is None:
        db_session.add(
            Stock(
                cooperative_id=coop_id,
                product_id=product_peanut.id,
                quantity=90.0,
                total_stock_kg=90.0,
                reserved_in_lots_kg=10.0,
                processed_output_kg=0.0,
                threshold=120.0,
                unit="kg",
            )
        )

    batch_mang_004 = db_session.scalar(
        select(Batch).where(Batch.cooperative_id == coop_id, Batch.code == "MANG-004")
    )
    if batch_mang_004 is None:
        batch_mang_004 = Batch(
            cooperative_id=coop_id,
            product_id=product_mango.id,
            code="MANG-004",
            creation_date=today - timedelta(days=4),
            unit="kg",
            ordered_process_steps=["cleaning", "drying", "sorting", "packaging"],
            initial_qty=1000.0,
            current_qty=720.0,
            status=BatchStatus.IN_PROGRESS,
            created_by_user_id=user.id,
        )
        db_session.add(batch_mang_004)
        db_session.flush()

    batch_mang_005 = db_session.scalar(
        select(Batch).where(Batch.cooperative_id == coop_id, Batch.code == "MANG-005")
    )
    if batch_mang_005 is None:
        batch_mang_005 = Batch(
            cooperative_id=coop_id,
            product_id=product_mango.id,
            code="MANG-005",
            creation_date=today - timedelta(days=2),
            unit="kg",
            ordered_process_steps=["cleaning", "drying", "sorting", "packaging"],
            initial_qty=900.0,
            current_qty=780.0,
            status=BatchStatus.IN_PROGRESS,
            created_by_user_id=user.id,
        )
        db_session.add(batch_mang_005)
        db_session.flush()

    def ensure_steps(batch: Batch, losses: list[tuple[str, float]]) -> None:
        qty_in = float(batch.initial_qty)
        for idx, (stage, loss_pct) in enumerate(losses, start=1):
            qty_out = round(qty_in * (1 - loss_pct / 100.0), 2)
            exists = db_session.scalar(
                select(ProcessStep).where(
                    ProcessStep.batch_id == batch.id,
                    ProcessStep.sequence_order == idx,
                    ProcessStep.type == stage,
                )
            )
            if exists is None:
                db_session.add(
                    ProcessStep(
                        batch_id=batch.id,
                        sequence_order=idx,
                        type=stage,
                        date=batch.creation_date + timedelta(days=idx - 1),
                        qty_in=qty_in,
                        qty_out=qty_out,
                        waste_qty=max(qty_in - qty_out, 0.0),
                        loss_value=max(qty_in - qty_out, 0.0),
                        loss_unit="kg",
                        normalized_loss_value=max(qty_in - qty_out, 0.0),
                        status=ProcessStepStatus.COMPLETED,
                        duration_minutes=85 + idx * 10,
                    )
                )
            qty_in = qty_out

    ensure_steps(batch_mang_004, [("cleaning", 5.0), ("drying", 14.0), ("sorting", 8.0), ("packaging", 3.0)])
    ensure_steps(batch_mang_005, [("cleaning", 4.0), ("drying", 9.0), ("sorting", 6.0), ("packaging", 2.0)])

    existing_ml = db_session.scalar(select(MLPredictionLog).where(MLPredictionLog.batch_id == batch_mang_004.id))
    if existing_ml is None:
        db_session.add(
            MLPredictionLog(
                batch_id=batch_mang_004.id,
                model_version="audit-v1",
                product="mango",
                critical_stage="drying",
                predicted_loss_pct=16.2,
                expected_efficiency_pct=78.0,
                risk_level=RiskLevel.HIGH,
                anomaly_score=0.92,
                is_anomalous=True,
                input_snapshot={"batch_ref": "MANG-004"},
                output_snapshot={"signal": "high_drying_loss"},
            )
        )

    existing_ml_2 = db_session.scalar(select(MLPredictionLog).where(MLPredictionLog.batch_id == batch_mang_005.id))
    if existing_ml_2 is None:
        db_session.add(
            MLPredictionLog(
                batch_id=batch_mang_005.id,
                model_version="audit-v1",
                product="mango",
                critical_stage="sorting",
                predicted_loss_pct=8.5,
                expected_efficiency_pct=88.0,
                risk_level=RiskLevel.MEDIUM,
                anomaly_score=0.41,
                is_anomalous=False,
                input_snapshot={"batch_ref": "MANG-005"},
                output_snapshot={"signal": "moderate"},
            )
        )

    rag_docs = [
        (
            "knowledge_drying",
            "Bonnes pratiques de séchage de la mangue",
            "Pour réduire les pertes pendant le séchage de la mangue, maintenir une humidité contrôlée, retourner les plateaux régulièrement et éviter la surcharge des claies.",
            {"product": "mango", "stage": "drying", "topic": "best_practices", "language": "fr"},
        ),
        (
            "knowledge_sorting",
            "Bonnes pratiques de tri des mangues",
            "Le tri des mangues doit éliminer les fruits blessés, séparer par maturité et standardiser les grades pour réduire les pertes post-récolte.",
            {"product": "mango", "stage": "sorting", "topic": "best_practices", "language": "fr"},
        ),
        (
            "knowledge_packaging",
            "Amélioration de l'emballage",
            "Améliorer l'emballage avec ventilation, protection mécanique et contrôle de l'humidité limite les dégradations pendant le transport.",
            {"product": "mango", "stage": "packaging", "topic": "post_harvest", "language": "fr"},
        ),
        (
            "knowledge_material_balance",
            "Bilan matière en post-récolte",
            "Le bilan matière compare les quantités entrantes et sortantes par lot et par étape pour identifier les pertes et l'efficacité.",
            {"product": "mango", "stage": "drying", "topic": "material_balance", "language": "fr"},
        ),
    ]

    for source_ref, title, content, metadata in rag_docs:
        doc = db_session.scalar(
            select(RAGDocument).where(
                RAGDocument.cooperative_id == coop_id,
                RAGDocument.source_type == "knowledge_chunks",
                RAGDocument.source_table == "knowledge_chunks",
                RAGDocument.source_record_ref == source_ref,
            )
        )
        if doc is None:
            doc = RAGDocument(
                cooperative_id=coop_id,
                source_type="knowledge_chunks",
                source_table="knowledge_chunks",
                source_record_ref=source_ref,
                title=title,
                content_hash=f"hash-{source_ref}",
                metadata_json=metadata,
            )
            db_session.add(doc)
            db_session.flush()

        chunk = db_session.scalar(
            select(RAGChunk).where(RAGChunk.document_id == doc.id, RAGChunk.chunk_index == 0)
        )
        if chunk is None:
            db_session.add(
                RAGChunk(
                    document_id=doc.id,
                    cooperative_id=coop_id,
                    chunk_index=0,
                    content=content,
                    embedding="[0.0]",
                    metadata_json=metadata,
                )
            )

    db_session.commit()


def _build_cases() -> list[AuditCase]:
    return [
        AuditCase("members-01", "members", "Liste les membres de notre coopérative.", "SQL", "SQL_ONLY", ("SQL_ONLY",), "global", {"sql"}, {"SQLAnalyticsAgent"}),
        AuditCase("members-02", "members", "Combien de membres sont enregistrés ?", "SQL", "SQL_ONLY", ("SQL_ONLY",), "global", {"sql"}, {"SQLAnalyticsAgent"}),
        AuditCase(
            "members-03",
            "members",
            "Donne-moi les informations du membre Mamadou Ba.",
            "SQL",
            "SQL_ONLY",
            ("SQL_ONLY",),
            "global",
            {"sql"},
            {"SQLAnalyticsAgent"},
            expected_entities={"member_name_contains": "Mamadou"},
        ),
        AuditCase("parcels-01", "parcels", "Liste les parcelles enregistrées.", "SQL", "SQL_ONLY", ("SQL_ONLY",), "pre_harvest", {"sql"}, {"SQLAnalyticsAgent"}),
        AuditCase("preharvest-01", "pre-harvest", "Quelles parcelles nécessitent une action en pré-récolte ?", "SQL", "SQL_ONLY", ("SQL_ONLY",), "pre_harvest", {"sql"}, {"SQLAnalyticsAgent"}),
        AuditCase("preharvest-02", "pre-harvest", "Quels sont les risques en pré-récolte ?", "HYBRID", "HYBRID_SQL_ML", ("HYBRID_SQL_ML", "SQL_ONLY"), "pre_harvest", {"sql", "ml"}, {"SQLAnalyticsAgent", "MLLossAgent"}),
        AuditCase("preharvest-03", "pre-harvest", "Quelles étapes pré-récolte sont en attente ?", "SQL", "SQL_ONLY", ("SQL_ONLY",), "pre_harvest", {"sql"}, {"SQLAnalyticsAgent"}),
        AuditCase("collections-01", "collections/inputs", "Quelle quantité a été collectée aujourd’hui ?", "SQL", "SQL_ONLY", ("SQL_ONLY",), "global", {"sql"}, {"SQLAnalyticsAgent"}),
        AuditCase("collections-02", "collections/inputs", "Quels producteurs ont livré le plus cette semaine ?", "SQL", "SQL_ONLY", ("SQL_ONLY",), "global", {"sql"}, {"SQLAnalyticsAgent"}),
        AuditCase("collections-03", "collections/inputs", "Quelle est la répartition par grade des collectes ?", "SQL", "SQL_ONLY", ("SQL_ONLY",), "global", {"sql"}, {"SQLAnalyticsAgent"}),
        AuditCase("stocks-01", "stocks", "Quel est le stock actuel ?", "SQL", "SQL_ONLY", ("SQL_ONLY",), "global", {"sql"}, {"SQLAnalyticsAgent"}),
        AuditCase("stocks-02", "stocks", "Quel est le stock actuel de mangue ?", "SQL", "SQL_ONLY", ("SQL_ONLY",), "global", {"sql"}, {"SQLAnalyticsAgent"}),
        AuditCase("stocks-03", "stocks", "Quels produits sont sous le seuil critique ?", "SQL", "SQL_ONLY", ("SQL_ONLY",), "global", {"sql"}, {"SQLAnalyticsAgent"}),
        AuditCase("lots-01", "lots/batches", "Quels lots sont en cours ?", "SQL", "SQL_ONLY", ("SQL_ONLY",), "post_harvest", {"sql"}, {"SQLAnalyticsAgent"}),
        AuditCase(
            "lots-02",
            "lots/batches",
            "Analyse le lot MANG-004.",
            "SQL",
            "SQL_ONLY",
            ("SQL_ONLY", "HYBRID_SQL_ML"),
            "batch",
            {"sql"},
            {"SQLAnalyticsAgent"},
            expected_entities={"batch_ref": "MANG-004"},
        ),
        AuditCase("lots-03", "lots/batches", "Quel lot a le plus de pertes ?", "SQL", "SQL_ONLY", ("SQL_ONLY",), "post_harvest", {"sql"}, {"SQLAnalyticsAgent"}),
        AuditCase("process-01", "process steps / flux matière", "Quelle étape post-récolte pose le plus de problème ?", "SQL", "SQL_ONLY", ("SQL_ONLY", "HYBRID_SQL_RAG"), "post_harvest", {"sql"}, {"SQLAnalyticsAgent"}),
        AuditCase("process-02", "process steps / flux matière", "Compare les pertes entre séchage et tri.", "SQL", "SQL_ONLY", ("SQL_ONLY", "HYBRID_SQL_RAG"), "post_harvest", {"sql"}, {"SQLAnalyticsAgent"}),
        AuditCase("balance-01", "material balance", "Explique le bilan matière.", "HYBRID", "HYBRID_SQL_RAG", ("HYBRID_SQL_RAG", "SQL_ONLY", "RAG_ONLY"), "global", {"sql", "rag"}, {"SQLAnalyticsAgent", "RAGKnowledgeAgent"}),
        AuditCase(
            "balance-02",
            "material balance",
            "Explique le bilan matière du lot MANG-004.",
            "HYBRID",
            "HYBRID_SQL_RAG",
            ("HYBRID_SQL_RAG", "SQL_ONLY", "HYBRID_SQL_ML"),
            "batch",
            {"sql", "rag"},
            {"SQLAnalyticsAgent", "RAGKnowledgeAgent"},
            expected_entities={"batch_ref": "MANG-004"},
        ),
        AuditCase("balance-03", "material balance", "Quels lots ont une efficacité faible ?", "SQL", "SQL_ONLY", ("SQL_ONLY", "HYBRID_SQL_RAG"), "post_harvest", {"sql"}, {"SQLAnalyticsAgent"}),
        AuditCase("rag-01", "RAG knowledge", "Comment réduire les pertes pendant le séchage de la mangue ?", "RAG", "RAG_ONLY", ("RAG_ONLY", "HYBRID_SQL_RAG"), "post_harvest", {"rag"}, {"RAGKnowledgeAgent"}),
        AuditCase("rag-02", "RAG knowledge", "Quelles sont les bonnes pratiques pour le tri des mangues ?", "RAG", "RAG_ONLY", ("RAG_ONLY", "HYBRID_SQL_RAG"), "post_harvest", {"rag"}, {"RAGKnowledgeAgent"}),
        AuditCase("rag-03", "RAG knowledge", "Comment améliorer l’emballage ?", "RAG", "RAG_ONLY", ("RAG_ONLY", "HYBRID_SQL_RAG"), "post_harvest", {"rag"}, {"RAGKnowledgeAgent"}),
        AuditCase("ml-01", "ML risk/anomaly", "Avons-nous des lots à risque aujourd’hui ?", "ML", "HYBRID_SQL_ML", ("HYBRID_SQL_ML", "ML_ONLY"), "global", {"ml"}, {"MLLossAgent"}),
        AuditCase("ml-02", "ML risk/anomaly", "Y a-t-il des anomalies dans les pertes ?", "ML", "HYBRID_SQL_ML", ("HYBRID_SQL_ML", "ML_ONLY"), "post_harvest", {"ml"}, {"MLLossAgent"}),
        AuditCase("ml-03", "ML risk/anomaly", "Quels sont les lots avec risque élevé ?", "ML", "HYBRID_SQL_ML", ("HYBRID_SQL_ML", "ML_ONLY"), "post_harvest", {"ml"}, {"MLLossAgent"}),
        AuditCase(
            "reco-01",
            "recommendations",
            "Donne-moi les recommandations IA pour le lot MANG-004.",
            "RECOMMENDATION",
            "HYBRID_FULL",
            ("HYBRID_FULL", "HYBRID_RAG_RECOMMENDATION", "RECOMMENDATION_ONLY"),
            "batch",
            {"sql", "ml"},
            {"RecommendationAgent"},
            expected_entities={"batch_ref": "MANG-004"},
        ),
        AuditCase("reco-02", "recommendations", "Que faire pour réduire les pertes au séchage ?", "RECOMMENDATION", "HYBRID_RAG_RECOMMENDATION", ("HYBRID_RAG_RECOMMENDATION", "HYBRID_FULL", "RECOMMENDATION_ONLY"), "post_harvest", {"rag"}, {"RecommendationAgent"}),
        AuditCase("reco-03", "recommendations", "Quelles actions prioritaires devons-nous faire aujourd’hui ?", "RECOMMENDATION", "RECOMMENDATION_ONLY", ("RECOMMENDATION_ONLY", "HYBRID_FULL", "HYBRID_RAG_RECOMMENDATION"), "global", set(), {"RecommendationAgent"}),
        AuditCase(
            "memory-a1",
            "memory/context",
            "Liste les membres de notre coopérative.",
            "SQL",
            "SQL_ONLY",
            ("SQL_ONLY",),
            "global",
            {"sql"},
            {"SQLAnalyticsAgent"},
            sequence_key="A",
            sequence_step=1,
        ),
        AuditCase(
            "memory-a2",
            "memory/context",
            "Quels lots sont à risque ?",
            "ML",
            "HYBRID_SQL_ML",
            ("HYBRID_SQL_ML", "ML_ONLY", "SQL_ONLY"),
            "post_harvest",
            {"ml"},
            {"MLLossAgent"},
            sequence_key="A",
            sequence_step=2,
            leakage_forbidden_terms=("membre", "producteur", "mamadou", "awa", "ibrahima"),
        ),
        AuditCase(
            "memory-b1",
            "memory/context",
            "Quels lots sont à risque ?",
            "ML",
            "HYBRID_SQL_ML",
            ("HYBRID_SQL_ML", "ML_ONLY", "SQL_ONLY"),
            "post_harvest",
            {"ml"},
            {"MLLossAgent"},
            sequence_key="B",
            sequence_step=1,
        ),
        AuditCase(
            "memory-b2",
            "memory/context",
            "Liste les membres.",
            "SQL",
            "SQL_ONLY",
            ("SQL_ONLY",),
            "global",
            {"sql"},
            {"SQLAnalyticsAgent"},
            sequence_key="B",
            sequence_step=2,
            leakage_forbidden_terms=("risque", "anomal", "lot", "séchage", "tri"),
        ),
    ]


def _post_agent(client: TestClient, *, question: str, conversation_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"message": question, "language": "fr"}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    response = client.post("/chat/agent", json=payload)
    assert response.status_code == 200
    return response.json()


def _actual_intent_from_route(route: str) -> str:
    if route == "SQL_ONLY":
        return "SQL"
    if route == "RAG_ONLY":
        return "RAG"
    if route == "ML_ONLY":
        return "ML"
    if route == "RECOMMENDATION_ONLY":
        return "RECOMMENDATION"
    if route.startswith("HYBRID"):
        return "HYBRID"
    return route


def _is_french(text: str) -> bool:
    lowered = str(text or "").lower()
    english_hits = sum(1 for token in (" the ", " what ", " which ", "risk level", "batch ", "today") if token in f" {lowered} ")
    french_hits = sum(
        1
        for token in (
            " le ",
            " la ",
            " les ",
            " des ",
            " une ",
            " et ",
            " est ",
            " avec ",
            " données",
            " pertes",
            " membres",
            " parcelles",
            " stocks",
            " lots",
            " pré-récolte",
            " recommandations",
        )
        if token in f" {lowered} "
    )
    return french_hits >= max(1, english_hits)


def _product_aliases(label: str) -> set[str]:
    raw = str(label or "").strip().lower()
    aliases = {raw}
    mapping = {
        "mango": {"mango", "mangue"},
        "mangue": {"mango", "mangue"},
        "peanut": {"peanut", "arachide"},
        "arachide": {"peanut", "arachide"},
        "millet": {"millet", "mil"},
        "mil": {"millet", "mil"},
    }
    aliases.update(mapping.get(raw, set()))
    return {item for item in aliases if item}


def _infer_tools_called(metadata: dict[str, Any], agents_used: list[str], sources: list[dict[str, Any]]) -> list[str]:
    tools: list[str] = []
    debug = metadata.get("agent_debug") or {}

    sql_data = ((debug.get("SQLAnalyticsAgent") or {}).get("data") or {}) if isinstance(debug, dict) else {}
    key_to_tool = {
        "current_stock": "SQLTools.get_current_stock",
        "collections_summary": "SQLTools.get_collections_summary",
        "batch_summary": "SQLTools.get_batch_summary",
        "top_loss_batches": "SQLTools.get_batch_summary",
        "process_step_losses": "SQLTools.get_process_step_losses",
        "stage_efficiency_summary": "SQLTools.get_stage_efficiency_summary",
        "material_balance": "SQLTools.get_material_balance",
        "top_farmers": "SQLTools.get_top_farmers",
        "low_stock_alerts": "SQLTools.get_low_stock_alerts",
        "parcel_status": "PreharvestTools.get_parcel_preharvest_status",
        "preharvest_status": "PreharvestTools.get_parcel_preharvest_status",
        "parcels_missing_data": "PreharvestTools.get_parcels_missing_data",
    }
    if isinstance(sql_data, dict):
        for key, tool_name in key_to_tool.items():
            if key in sql_data:
                tools.append(tool_name)

    if "RAGKnowledgeAgent" in agents_used:
        tools.append("RAGTools.search")
    if "MLLossAgent" in agents_used:
        tools.append("MLTools.analyze_loss_risk")
    if "RecommendationAgent" in agents_used:
        tools.append("RecommendationTools.build_recommendations")

    for source in sources:
        source_type = str(source.get("type") or "").lower()
        table = str(source.get("table") or "").lower()
        if source_type == "sql" and table and table not in {"", "none"}:
            tools.append(f"SQLSource[{table}]")

    return sorted(set(tools))


def _extract_recommendation_evidence(metadata: dict[str, Any]) -> list[str]:
    debug = metadata.get("agent_debug") or {}
    reco_data = ((debug.get("RecommendationAgent") or {}).get("data") or {}) if isinstance(debug, dict) else {}
    recommendations = reco_data.get("recommendations") if isinstance(reco_data, dict) else None
    evidence: list[str] = []
    if isinstance(recommendations, list):
        for rec in recommendations:
            if not isinstance(rec, dict):
                continue
            for item in rec.get("evidence") or []:
                evidence.append(str(item))
    return evidence


def _extract_recommendation_payload(metadata: dict[str, Any]) -> dict[str, Any]:
    debug = metadata.get("agent_debug") or {}
    reco_data = ((debug.get("RecommendationAgent") or {}).get("data") or {}) if isinstance(debug, dict) else {}
    return reco_data if isinstance(reco_data, dict) else {}


def _extract_sql_payload(metadata: dict[str, Any]) -> dict[str, Any]:
    debug = metadata.get("agent_debug") or {}
    sql_data = ((debug.get("SQLAnalyticsAgent") or {}).get("data") or {}) if isinstance(debug, dict) else {}
    return sql_data if isinstance(sql_data, dict) else {}


def _is_cautious_recommendation_mode(answer: str, reco_payload: dict[str, Any]) -> bool:
    insufficient = bool(reco_payload.get("insufficient_evidence"))
    if insufficient:
        return True
    lowered = str(answer or "").lower()
    markers = (
        "preuves actuelles sont insuffisantes",
        "pas assez de preuves",
        "insuffisantes pour recommander une action prioritaire",
    )
    return any(marker in lowered for marker in markers)


def _contradiction_is_explained(answer: str) -> bool:
    lowered = str(answer or "").lower()
    return (
        "contradiction sql/ml" in lowered
        and "priorité aux mesures sql" in lowered
        and "signal ml" in lowered
    )


def _principal_answer_line(answer: str) -> str:
    lines = [line.strip() for line in str(answer or "").splitlines()]
    try:
        idx = lines.index("1. Résultat principal")
    except ValueError:
        return lines[0] if lines else ""
    for candidate in lines[idx + 1 :]:
        if candidate:
            return candidate
    return ""


def _sql_overrides_answer(answer: str) -> bool:
    principal = _principal_answer_line(answer).lower()
    if not principal:
        return False
    sql_markers = (
        "stock",
        "lot ",
        "étape critique observée",
        "bilan matière du lot",
        "perte cumulée",
        "état pré-récolte",
        "parcelle",
        "kg disponibles",
    )
    return any(marker in principal for marker in sql_markers)


def _route_compatibility_status(
    *,
    case: AuditCase,
    route: str,
    rag_sources: list[dict[str, Any]],
    sql_sources: list[dict[str, Any]],
    answer: str,
) -> tuple[str, str]:
    if route == case.expected_route:
        return "exact_match", "Route exacte."
    if route not in case.accepted_routes:
        return "route_failure", "Route hors liste acceptée."

    # Special compatibility rule for expected RAG_ONLY.
    if case.expected_route == "RAG_ONLY" and route == "HYBRID_SQL_RAG":
        rag_present = bool(rag_sources)
        sql_dominant = _sql_overrides_answer(answer)
        if rag_present and not sql_dominant:
            return "compatible_route_accepted", "HYBRID_SQL_RAG accepté: RAG présent et réponse non dominée par SQL."
        if rag_present and sql_dominant:
            return "compatible_route_accepted", "HYBRID_SQL_RAG accepté avec risque: RAG présent mais réponse dominée par SQL."
        return "compatible_route_accepted", "HYBRID_SQL_RAG accepté avec risque: RAG absent dans la réponse finale."

    return "compatible_route_accepted", "Route compatible acceptée."


def _evaluate_case(case: AuditCase, payload: dict[str, Any], previous_case: AuditCase | None) -> dict[str, Any]:
    metadata = payload.get("metadata") or {}
    detected_entities = metadata.get("detected_entities") or {}
    route = str(payload.get("route") or "")
    agents_used = [str(a) for a in (payload.get("agents_used") or [])]
    sources = [s for s in (payload.get("sources") or []) if isinstance(s, dict)]
    source_types = {str(source.get("type") or "").lower() for source in sources if source.get("type")}
    sql_sources = [source for source in sources if str(source.get("type") or "").lower() == "sql"]
    rag_sources = [source for source in sources if str(source.get("type") or "").lower() == "rag"]
    ml_sources = [source for source in sources if str(source.get("type") or "").lower() == "ml"]

    answer = str(payload.get("answer") or "")
    answer_preview = " ".join(answer.split())[:320]
    warnings = [str(w) for w in (payload.get("warnings") or [])]
    warning_codes = [str(w) for w in (metadata.get("warning_codes") or [])]
    confidence = float(payload.get("confidence") or 0.0)

    tools_called = _infer_tools_called(metadata, agents_used, sources)
    recommendation_evidence = _extract_recommendation_evidence(metadata)
    recommendation_payload = _extract_recommendation_payload(metadata)
    sql_payload = _extract_sql_payload(metadata)
    actual_scope = str(detected_entities.get("scope") or "")
    contradiction_warning_present = any(code == "SQL_ML_CONTRADICTION" for code in warning_codes)
    contradiction_explained = _contradiction_is_explained(answer) if contradiction_warning_present else False

    french_ok = _is_french(answer)

    leakage = False
    lower_answer = answer.lower()
    if case.leakage_forbidden_terms and any(term.lower() in lower_answer for term in case.leakage_forbidden_terms):
        leakage = True

    if case.sequence_step == 2 and previous_case is not None:
        if case.sequence_key == "A" and (detected_entities.get("member_name") or "").strip():
            leakage = True
        if case.sequence_key == "B" and detected_entities.get("batch_ref"):
            leakage = True

    source_correct = case.expected_source_types.issubset(source_types) if case.expected_source_types else bool(sources)
    route_match_status, route_compatibility_note = _route_compatibility_status(
        case=case,
        route=route,
        rag_sources=rag_sources,
        sql_sources=sql_sources,
        answer=answer,
    )

    failures: list[str] = []
    if route_match_status == "route_failure":
        failures.append("ROUTER_WRONG_MODE")

    if case.expected_scope and actual_scope and case.expected_scope != actual_scope:
        failures.append("ENTITY_EXTRACTION_ERROR")

    expected_batch_ref = case.expected_entities.get("batch_ref")
    if expected_batch_ref and str(detected_entities.get("batch_ref") or "").upper() != expected_batch_ref:
        failures.append("ENTITY_EXTRACTION_ERROR")

    expected_member_contains = case.expected_entities.get("member_name_contains")
    if expected_member_contains and expected_member_contains.lower() not in str(detected_entities.get("member_name") or "").lower():
        failures.append("ENTITY_EXTRACTION_ERROR")

    if "sql" in case.expected_source_types and not sql_sources:
        failures.append("SQL_EVIDENCE_MISSING")
    if "rag" in case.expected_source_types and not rag_sources:
        failures.append("RAG_EVIDENCE_MISSING")
    if "ml" in case.expected_source_types and not ml_sources:
        failures.append("ML_EVIDENCE_MISSING")

    if case.expected_source_types and not case.expected_source_types.issubset(source_types):
        if source_types:
            failures.append("SOURCE_TYPE_WRONG")

    if not sources:
        failures.append("SOURCE_MISSING")

    if not french_ok:
        failures.append("NOT_FRENCH")

    if leakage:
        failures.append("CONTEXT_LEAKAGE")

    if case.module in {"members", "parcels", "pre-harvest"} and "SQLAnalyticsAgent" in agents_used:
        sql_tables = {str(src.get("table") or "") for src in sql_sources}
        member_specific = any("members" in tbl for tbl in sql_tables)
        parcel_specific = any("parcels" in tbl or "pre_harvest" in tbl for tbl in sql_tables)
        if case.module == "members" and not member_specific:
            failures.append("TOOL_NOT_WIRED")
        if case.module in {"parcels", "pre-harvest"} and not parcel_specific:
            failures.append("TOOL_NOT_WIRED")

    if case.expected_source_types and source_types and not case.expected_source_types.intersection(source_types):
        failures.append("WRONG_TOOL_SELECTED")

    # Semantic content checks beyond route/source correctness.
    if case.case_id == "members-01":
        members = sql_payload.get("members_list") if isinstance(sql_payload, dict) else None
        has_explicit_empty = "aucun membre" in answer.lower()
        if isinstance(members, list):
            if members and not any(str(member.get("member_name", "")).lower() in answer.lower() for member in members[:3]):
                failures.append("CONTENT_SEMANTIC_ERROR")
            if not members and not has_explicit_empty:
                failures.append("CONTENT_SEMANTIC_ERROR")
        elif not has_explicit_empty:
            failures.append("CONTENT_SEMANTIC_ERROR")

    if case.case_id == "stocks-01":
        stocks = sql_payload.get("current_stock") if isinstance(sql_payload, dict) else None
        if isinstance(stocks, list) and len(stocks) > 1:
            mentioned = 0
            lowered = answer.lower()
            for stock in stocks:
                variants = _product_aliases(stock.get("product", ""))
                if any(token in lowered for token in variants):
                    mentioned += 1
            if mentioned < 2:
                failures.append("CONTENT_SEMANTIC_ERROR")

    if case.case_id == "stocks-02":
        stocks = sql_payload.get("current_stock") if isinstance(sql_payload, dict) else None
        if isinstance(stocks, list) and stocks:
            if any(str(item.get("product", "")).lower() not in {"mango", "mangue"} for item in stocks):
                failures.append("CONTENT_SEMANTIC_ERROR")

    if case.case_id == "ml-03":
        high_risk = sql_payload.get("high_risk_lots") if isinstance(sql_payload, dict) else None
        if isinstance(high_risk, list) and len(high_risk) > 1:
            lowered = answer.lower()
            mentioned = 0
            for item in high_risk[:6]:
                if str(item.get("batch_ref", "")).lower() in lowered:
                    mentioned += 1
            if mentioned < 2:
                failures.append("CONTENT_SEMANTIC_ERROR")

    if case.module == "recommendations":
        recommendations = recommendation_payload.get("recommendations") if isinstance(recommendation_payload, dict) else []
        cautious_mode = _is_cautious_recommendation_mode(answer, recommendation_payload)
        has_unsupported_priority = False
        if isinstance(recommendations, list):
            for item in recommendations:
                if not isinstance(item, dict):
                    continue
                priority = str(item.get("priority") or "").upper()
                if priority in {"HIGH", "MEDIUM"} and not (item.get("evidence") or []):
                    has_unsupported_priority = True
                    break
        if has_unsupported_priority:
            failures.append("RECOMMENDATION_UNGROUNDED")
        elif (not recommendation_evidence or any(code in warning_codes for code in ("RECOMMENDATION_WITHOUT_EVIDENCE", "RECOMMENDATION_EVIDENCE_WEAK"))) and not cautious_mode:
            failures.append("RECOMMENDATION_UNGROUNDED")

    if contradiction_warning_present or any("align" in w.lower() and "ml" in w.lower() for w in warnings):
        if not contradiction_explained:
            failures.append("ML_SQL_CONTRADICTION")

    if route.startswith("HYBRID") and confidence >= 0.75 and any(code in warning_codes for code in ("MISSING_RAG_SOURCE", "INCOMPLETE_SQL_DATA")):
        failures.append("LLM_CONTEXT_BAD")

    frontend_display_risk = False
    for source in sources:
        if not (source.get("label") or source.get("title") or source.get("model")):
            frontend_display_risk = True
            break
    if re.search(r"\b[A-Z_]{4,}\b", answer):
        frontend_display_risk = True
    if frontend_display_risk:
        failures.append("FRONTEND_DISPLAY_RISK")

    failures = sorted({item for item in failures if item in FAILURE_CATEGORIES})

    if not failures:
        status = "PASS"
    elif len(failures) <= 2 or (source_types and route in case.accepted_routes):
        status = "PARTIAL"
    else:
        status = "FAIL"

    root_cause_map = {
        "ROUTER_WRONG_MODE": "IntentRouter heuristiques (mots-clés) orientent vers un mode différent de l’intention métier attendue.",
        "ENTITY_EXTRACTION_ERROR": "EntityExtractor ne capture pas correctement les entités (scope, lot, membre) pour cette formulation.",
        "WRONG_TOOL_SELECTED": "La sélection d’agent/outil ne correspond pas au type de question attendu.",
        "TOOL_NOT_WIRED": "Le module métier est partiellement implémenté mais non branché explicitement dans SQLAnalyticsAgent pour ce cas.",
        "SQL_EVIDENCE_MISSING": "La réponse nécessite des faits opérationnels mais aucune source SQL n’est fournie.",
        "RAG_EVIDENCE_MISSING": "La réponse explicative attendue n’expose pas de sources RAG.",
        "ML_EVIDENCE_MISSING": "La question risque/anomalie n’expose pas de source ML exploitable.",
        "SOURCE_TYPE_WRONG": "Les types de sources renvoyés ne correspondent pas au besoin de la question.",
        "SOURCE_MISSING": "Aucune source n’est renvoyée dans la réponse finale.",
        "CONTEXT_LEAKAGE": "Le contexte conversationnel précédent influence une question non liée.",
        "LLM_CONTEXT_BAD": "Synthèse finale trop confiante malgré des signaux d’incomplétude/absence de sources.",
        "RECOMMENDATION_UNGROUNDED": "Recommandation générée sans preuve suffisante SQL/RAG/ML.",
        "ML_SQL_CONTRADICTION": "Les signaux ML et les données SQL semblent incohérents pour ce cas.",
        "NOT_FRENCH": "La réponse finale n’est pas pleinement conforme au français attendu.",
        "FRONTEND_DISPLAY_RISK": "Les métadonnées sources/réponse risquent un affichage ambigu côté frontend.",
        "CONTENT_SEMANTIC_ERROR": "La réponse ne reflète pas correctement le contenu opérationnel attendu (liste/détail/pluriel).",
    }

    suspected_root_cause = root_cause_map[failures[0]] if failures else "Aucune anomalie détectée pour ce cas."

    return {
        "case_id": case.case_id,
        "module": case.module,
        "question": case.question,
        "expected_intent": case.expected_intent,
        "actual_intent": _actual_intent_from_route(route),
        "expected_route": case.expected_route,
        "actual_route": route,
        "expected_scope": case.expected_scope,
        "actual_scope": actual_scope,
        "route_match_status": route_match_status,
        "route_compatibility_note": route_compatibility_note,
        "detected_entities": detected_entities,
        "agents_used": agents_used,
        "tools_called": tools_called,
        "sql_sources": sql_sources,
        "rag_sources": rag_sources,
        "ml_sources": ml_sources,
        "recommendation_evidence": recommendation_evidence,
        "final_response_sources": sources,
        "warnings": warnings,
        "warning_codes": warning_codes,
        "contradiction_warning_present": contradiction_warning_present,
        "contradiction_explained": contradiction_explained,
        "confidence": confidence,
        "answer_preview": answer_preview,
        "french_compliance": "yes" if french_ok else "no",
        "context_leakage": "yes" if leakage else "no",
        "source_correctness": "yes" if source_correct else "no",
        "status": status,
        "failure_categories": failures,
        "suspected_root_cause": suspected_root_cause,
        "conversation_id": metadata.get("conversation_id"),
        "route_explanation": metadata.get("route_explanation"),
    }


def _build_architecture_map() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    repo_root = root.parent
    backend_chat = root / "app" / "api" / "routes" / "chat.py"
    frontend_page = repo_root / "app" / "(platform)" / "manager" / "assistant-ia" / "page.tsx"
    endpoints_ts = repo_root / "lib" / "api" / "endpoints.ts"
    orchestrator_py = root / "app" / "ai" / "orchestrator" / "agent_orchestrator.py"

    def read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    backend_chat_text = read(backend_chat)
    frontend_text = read(frontend_page)
    endpoints_text = read(endpoints_ts)
    orchestrator_text = read(orchestrator_py)

    return {
        "backend_endpoints": {
            "/chat": "@router.post('')" if "@router.post(\"\"" in backend_chat_text else "not_found",
            "/chat/agent": "@router.post('/agent')" if "/agent" in backend_chat_text else "not_found",
        },
        "frontend_usage": {
            "endpoint_constant": "agentAsk: '/chat/agent'" if "agentAsk: \"/chat/agent\"" in endpoints_text else "not_found",
            "request_call": "apiFetch(endpoints.chat.agentAsk)" if "endpoints.chat.agentAsk" in frontend_text else "not_found",
            "conversation_id_forwarded": "yes" if "conversation_id" in frontend_text else "no",
        },
        "orchestrator_components": {
            "AgentOrchestrator": "found" if "class AgentOrchestrator" in orchestrator_text else "missing",
            "IntentRouter": "found" if "IntentRouter" in orchestrator_text else "missing",
            "EntityExtractor": "found" if "EntityExtractor" in read(root / "app" / "ai" / "orchestrator" / "intent_router.py") else "missing",
            "AgentRegistry": "found" if "AgentRegistry" in orchestrator_text else "missing",
            "SQLAnalyticsAgent": "found" if "SQLAnalyticsAgent" in orchestrator_text else "missing",
            "RAGKnowledgeAgent": "found" if "RAGKnowledgeAgent" in orchestrator_text else "missing",
            "MLLossAgent": "found" if "MLLossAgent" in orchestrator_text else "missing",
            "RecommendationAgent": "found" if "RecommendationAgent" in orchestrator_text else "missing",
            "ResponseVerifier": "found" if "ResponseVerifier" in orchestrator_text else "missing",
            "SourceFormatter": "found" if "merge_and_dedupe_sources" in orchestrator_text else "missing",
            "MemoryContext": "found" if "memory_agent" in orchestrator_text else "missing",
        },
    }


def _compute_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(case["status"] for case in cases)
    total = len(cases)

    module_counts: dict[str, Counter] = defaultdict(Counter)
    for case in cases:
        module_counts[str(case["module"])][case["status"]] += 1

    route_correct = sum(1 for case in cases if "ROUTER_WRONG_MODE" not in case["failure_categories"])
    route_exact = sum(1 for case in cases if case.get("route_match_status") == "exact_match")
    route_compatible = sum(1 for case in cases if case.get("route_match_status") == "compatible_route_accepted")
    route_failed = sum(1 for case in cases if case.get("route_match_status") == "route_failure")
    tool_correct = sum(
        1
        for case in cases
        if "WRONG_TOOL_SELECTED" not in case["failure_categories"] and "TOOL_NOT_WIRED" not in case["failure_categories"]
    )
    source_correct = sum(1 for case in cases if case["source_correctness"] == "yes")
    french_ok = sum(1 for case in cases if case["french_compliance"] == "yes")
    leakage_count = sum(1 for case in cases if case["context_leakage"] == "yes")

    reco_cases = [case for case in cases if case["module"] == "recommendations"]
    reco_grounded = sum(1 for case in reco_cases if "RECOMMENDATION_UNGROUNDED" not in case["failure_categories"])

    contradiction_failure_cases = [
        {
            "case_id": case["case_id"],
            "question": case["question"],
            "warnings": case["warning_codes"],
            "answer_preview": case["answer_preview"],
        }
        for case in cases
        if "ML_SQL_CONTRADICTION" in case["failure_categories"]
    ]
    contradiction_warning_cases = [
        {
            "case_id": case["case_id"],
            "question": case["question"],
            "warnings": case["warning_codes"],
            "explained": bool(case.get("contradiction_explained")),
            "status": case["status"],
        }
        for case in cases
        if case.get("contradiction_warning_present")
    ]
    explained_warning_cases = [case for case in contradiction_warning_cases if case["explained"]]
    unresolved_warning_cases = [case for case in contradiction_warning_cases if not case["explained"]]

    failure_counter = Counter()
    root_counter = Counter()
    for case in cases:
        failure_counter.update(case["failure_categories"])
        if case["failure_categories"]:
            root_counter.update([case["suspected_root_cause"]])

    top_failures = failure_counter.most_common(10)
    top_roots = root_counter.most_common(10)

    return {
        "counts": {
            "PASS": counts.get("PASS", 0),
            "PARTIAL": counts.get("PARTIAL", 0),
            "FAIL": counts.get("FAIL", 0),
            "TOTAL": total,
        },
        "module_results": {
            module: {
                "PASS": counter.get("PASS", 0),
                "PARTIAL": counter.get("PARTIAL", 0),
                "FAIL": counter.get("FAIL", 0),
            }
            for module, counter in sorted(module_counts.items(), key=lambda item: item[0])
        },
        "rates": {
            "route_correctness_rate": round((route_correct / total) * 100.0, 2) if total else 0.0,
            "route_exact_match_rate": round((route_exact / total) * 100.0, 2) if total else 0.0,
            "route_compatible_accepted_rate": round((route_compatible / total) * 100.0, 2) if total else 0.0,
            "route_failure_rate": round((route_failed / total) * 100.0, 2) if total else 0.0,
            "tool_correctness_rate": round((tool_correct / total) * 100.0, 2) if total else 0.0,
            "source_correctness_rate": round((source_correct / total) * 100.0, 2) if total else 0.0,
            "french_compliance_rate": round((french_ok / total) * 100.0, 2) if total else 0.0,
            "recommendation_grounding_rate": round((reco_grounded / len(reco_cases)) * 100.0, 2) if reco_cases else 0.0,
        },
        "context_leakage_count": leakage_count,
        "ml_contradiction_cases": contradiction_failure_cases,
        "ml_contradiction_warning_cases": contradiction_warning_cases,
        "ml_contradiction_explained_warnings": explained_warning_cases,
        "ml_contradiction_unresolved_warnings": unresolved_warning_cases,
        "top_10_failures": [{"category": category, "count": count} for category, count in top_failures],
        "top_10_root_causes": [{"root_cause": cause, "count": count} for cause, count in top_roots],
    }


def _format_markdown(
    *,
    architecture_map: dict[str, Any],
    endpoint_usage: dict[str, Any],
    tested_modules: list[str],
    cases: list[dict[str, Any]],
    summary: dict[str, Any],
) -> str:
    counts = summary["counts"]
    rates = summary["rates"]

    worst_modules = sorted(
        summary["module_results"].items(),
        key=lambda item: (item[1]["FAIL"], item[1]["PARTIAL"]),
        reverse=True,
    )[:5]

    lines: list[str] = []
    lines.append("# Chatbot System Audit")
    lines.append("")
    lines.append("## Executive summary")
    lines.append(
        f"- Total cas: {counts['TOTAL']} | PASS={counts['PASS']} | PARTIAL={counts['PARTIAL']} | FAIL={counts['FAIL']}"
    )
    lines.append(
        f"- Taux route correcte: {rates['route_correctness_rate']}% | outils corrects: {rates['tool_correctness_rate']}% | sources correctes: {rates['source_correctness_rate']}%"
    )
    lines.append(
        f"- Routes: exactes={rates['route_exact_match_rate']}% | compatibles acceptées={rates['route_compatible_accepted_rate']}% | échecs route={rates['route_failure_rate']}%"
    )
    lines.append(
        f"- Français conforme: {rates['french_compliance_rate']}% | fuites contexte: {summary['context_leakage_count']} | grounding reco: {rates['recommendation_grounding_rate']}%"
    )
    lines.append("- Audit only: aucun correctif produit dans cette exécution.")
    lines.append("")

    lines.append("## Architecture map found in code")
    lines.append("- Backend endpoints:")
    lines.append(f"  - /chat: {architecture_map['backend_endpoints']['/chat']}")
    lines.append(f"  - /chat/agent: {architecture_map['backend_endpoints']['/chat/agent']}")
    lines.append("- Frontend usage:")
    lines.append(f"  - Endpoint constant: {architecture_map['frontend_usage']['endpoint_constant']}")
    lines.append(f"  - Request call: {architecture_map['frontend_usage']['request_call']}")
    lines.append(f"  - conversation_id forwarded: {architecture_map['frontend_usage']['conversation_id_forwarded']}")
    lines.append("- Orchestrator components:")
    for component, status in architecture_map["orchestrator_components"].items():
        lines.append(f"  - {component}: {status}")
    lines.append("")

    lines.append("## Endpoint usage")
    lines.append(f"- Test target: {endpoint_usage['audit_endpoint']}")
    lines.append(f"- Chat endpoint present: {endpoint_usage['chat_endpoint_present']}")
    lines.append(f"- Frontend route used: {endpoint_usage['frontend_agent_route']}")
    lines.append(f"- Debug mode: {endpoint_usage['debug_mode']}")
    lines.append("")

    lines.append("## Tested modules")
    for module in tested_modules:
        lines.append(f"- {module}")
    lines.append("")

    lines.append("## Pass / partial / fail counts")
    lines.append(f"- PASS: {counts['PASS']}")
    lines.append(f"- PARTIAL: {counts['PARTIAL']}")
    lines.append(f"- FAIL: {counts['FAIL']}")
    lines.append("")

    lines.append("## Module-by-module results")
    lines.append("| Module | PASS | PARTIAL | FAIL |")
    lines.append("| --- | ---: | ---: | ---: |")
    for module, stats in summary["module_results"].items():
        lines.append(f"| {module} | {stats['PASS']} | {stats['PARTIAL']} | {stats['FAIL']} |")
    lines.append("")

    lines.append("## Quality rates")
    lines.append(f"- Route correctness rate: {rates['route_correctness_rate']}%")
    lines.append(f"- Route exact match rate: {rates['route_exact_match_rate']}%")
    lines.append(f"- Route compatible accepted rate: {rates['route_compatible_accepted_rate']}%")
    lines.append(f"- Route failure rate: {rates['route_failure_rate']}%")
    lines.append(f"- Tool correctness rate: {rates['tool_correctness_rate']}%")
    lines.append(f"- Source correctness rate: {rates['source_correctness_rate']}%")
    lines.append(f"- French compliance rate: {rates['french_compliance_rate']}%")
    lines.append(f"- Context leakage count: {summary['context_leakage_count']}")
    lines.append(f"- Recommendation grounding rate: {rates['recommendation_grounding_rate']}%")
    lines.append("")

    lines.append("## SQL/ML contradiction warnings")
    warning_cases = summary.get("ml_contradiction_warning_cases", [])
    explained_cases = summary.get("ml_contradiction_explained_warnings", [])
    unresolved_cases = summary.get("ml_contradiction_unresolved_warnings", [])
    if warning_cases:
        lines.append(f"- Total warnings détectés: {len(warning_cases)}")
        lines.append(f"- Explained warnings: {len(explained_cases)}")
        for case in explained_cases:
            lines.append(f"  - {case['case_id']}: explained=yes | status={case['status']}")
        lines.append(f"- Unresolved warnings: {len(unresolved_cases)}")
        for case in unresolved_cases:
            lines.append(f"  - {case['case_id']}: explained=no | status={case['status']}")
    else:
        lines.append("- Aucun warning de contradiction SQL/ML détecté dans ce run.")
    lines.append("")

    lines.append("## Top 10 failures")
    if summary["top_10_failures"]:
        for item in summary["top_10_failures"]:
            lines.append(f"- {item['category']}: {item['count']}")
    else:
        lines.append("- Aucun échec détecté.")
    lines.append("")

    lines.append("## Exact suspected root causes")
    if summary["top_10_root_causes"]:
        for item in summary["top_10_root_causes"]:
            lines.append(f"- {item['root_cause']} (cas={item['count']})")
    else:
        lines.append("- Aucune cause racine, tous les cas sont PASS.")
    lines.append("")

    lines.append("## Worst failing modules")
    for module, stats in worst_modules:
        lines.append(f"- {module}: FAIL={stats['FAIL']} PARTIAL={stats['PARTIAL']}")
    lines.append("")

    lines.append("## Priority fix list")
    lines.append("1. Corriger les erreurs de routage (IntentRouter) pour les cas où le mode attendu n’est pas sélectionné.")
    lines.append("2. Fiabiliser extraction d’entités (scope, membre, lot) pour éviter erreurs de contexte et de tool selection.")
    lines.append("3. Forcer le grounding de recommandations avec preuves SQL/RAG/ML explicites.")
    lines.append("4. Renforcer émission de sources attendues par mode (SQL/RAG/ML) et signaler manque de preuve en metadata.")
    lines.append("5. Limiter fuite de contexte via règles de reset/filtrage d’entités mémoire pour questions non liées.")
    lines.append("")

    lines.append("## Recommended next implementation step")
    lines.append("- Démarrer par une instrumentation ciblée d’IntentRouter + EntityExtractor (debug only) puis corriger les règles de routing membres/parcelles/risque avant toute refonte plus large.")
    lines.append("")

    lines.append("## Detailed case results")
    lines.append("| Case | Module | Expected route | Actual route | Route status | Scope exp/act | Source ok | French | Leakage | Status | Root cause |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for case in cases:
        scope_repr = f"{case['expected_scope']}/{case['actual_scope'] or '-'}"
        lines.append(
            "| {case_id} | {module} | {expected_route} | {actual_route} | {route_status} | {scope_repr} | {source_ok} | {fr} | {leak} | {status} | {root} |".format(
                case_id=case["case_id"],
                module=case["module"],
                expected_route=case["expected_route"],
                actual_route=case["actual_route"],
                route_status=case.get("route_match_status", ""),
                scope_repr=scope_repr,
                source_ok=case["source_correctness"],
                fr=case["french_compliance"],
                leak=case["context_leakage"],
                status=case["status"],
                root=case["suspected_root_cause"].replace("|", "/"),
            )
        )

    return "\n".join(lines)


def _write_reports(payload: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_REPORT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    MD_REPORT_PATH.write_text(payload["markdown_report"], encoding="utf-8")


def test_chatbot_system_audit_report(db_session, monkeypatch):
    monkeypatch.setenv("AI_AUDIT_DEBUG", "1")
    _setup_overrides(db_session)
    _seed_audit_data(db_session)

    architecture_map = _build_architecture_map()
    endpoint_usage = {
        "audit_endpoint": "/chat/agent",
        "chat_endpoint_present": architecture_map["backend_endpoints"]["/chat"],
        "frontend_agent_route": architecture_map["frontend_usage"]["endpoint_constant"],
        "debug_mode": "AI_AUDIT_DEBUG=1",
    }

    client = TestClient(app)
    cases = _build_cases()

    sequence_conversation_ids: dict[str, str] = {}
    case_results: list[dict[str, Any]] = []
    previous_by_sequence: dict[str, AuditCase] = {}

    try:
        for case in cases:
            conversation_id = None
            if case.sequence_key and case.sequence_step > 1:
                conversation_id = sequence_conversation_ids.get(case.sequence_key)

            payload = _post_agent(client, question=case.question, conversation_id=conversation_id)

            metadata = payload.get("metadata") or {}
            returned_conversation_id = str(metadata.get("conversation_id") or "")
            if case.sequence_key and case.sequence_step == 1 and returned_conversation_id:
                sequence_conversation_ids[case.sequence_key] = returned_conversation_id

            previous_case = previous_by_sequence.get(case.sequence_key) if case.sequence_key else None
            evaluated = _evaluate_case(case, payload, previous_case)
            case_results.append(evaluated)

            if case.sequence_key:
                previous_by_sequence[case.sequence_key] = case
    finally:
        app.dependency_overrides.clear()
        os.environ.pop("AI_AUDIT_DEBUG", None)

    tested_modules = sorted({case["module"] for case in case_results})
    summary = _compute_summary(case_results)

    audit_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audit_mode": "system_audit",
        "debug_flag": "AI_AUDIT_DEBUG=1",
        "architecture_map": architecture_map,
        "endpoint_usage": endpoint_usage,
        "tested_modules": tested_modules,
        "summary": summary,
        "cases": case_results,
    }
    audit_payload["markdown_report"] = _format_markdown(
        architecture_map=architecture_map,
        endpoint_usage=endpoint_usage,
        tested_modules=tested_modules,
        cases=case_results,
        summary=summary,
    )

    _write_reports(audit_payload)

    assert len(case_results) >= 34
    assert summary["counts"]["TOTAL"] == len(case_results)
    assert JSON_REPORT_PATH.exists()
    assert MD_REPORT_PATH.exists()

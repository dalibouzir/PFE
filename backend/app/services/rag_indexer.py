from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.ml.utils.stage_normalization import normalize_stage
from app.models.batch import Batch
from app.models.commercial_catalog_product import CommercialCatalogProduct
from app.models.commercial_invoice import CommercialInvoice
from app.models.commercial_order import CommercialOrder
from app.models.global_charge import GlobalCharge
from app.models.parcel import Parcel
from app.models.pre_harvest_step import PreHarvestStep
from app.models.recommendation import Recommendation
from app.models.enums import UserRole
from app.models.farmer_advance import FarmerAdvance
from app.models.field import Field
from app.models.input import Input
from app.models.member import Member
from app.models.ml import (
    MLModelRegistry,
    MLPredictionLog,
    MLRecommendationLog,
    MLTrainingRun,
    RecommendationFeedbackLog,
)
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.rag import RAGChunk, RAGDocument
from app.models.reference import KnowledgeChunk, ReferenceMetric
from app.models.stock import Stock
from app.models.treasury_transaction import TreasuryTransaction
from app.models.user import User
from app.models.mixins import current_utc
from app.schemas.rag import RAGReindexResponse
from app.services.rag_chunk_registry import get_chunk_builder
from app.services.rag_context_builders import (
    build_anomaly_summary_chunk,
    build_lot_recommendation_summary_chunk,
    build_lot_status_summary_chunk,
    build_operational_risk_summary_chunk,
    build_product_stage_summary_chunk,
    build_scoped_loss_summary_chunk,
    validate_chunk_metadata,
)
from app.services.rag_embeddings import embed_texts
from app.services.helpers import get_manager_cooperative_id
from app.utils.exceptions import ForbiddenError, ValidationError


APP_SOURCE_TYPE = "app_data"
INDEXED_SOURCE_TABLES = (
    "members",
    "fields",
    "inputs",
    "stocks",
    "batches",
    "process_steps",
    "farmer_advances",
    "treasury_transactions",
    "commercial_catalog_products",
    "commercial_orders",
    "commercial_invoices",
    "parcels",
    "pre_harvest_steps",
    "recommendations",
    "ml_prediction_logs",
    "ml_recommendation_logs",
    "recommendation_feedback_logs",
    "global_charges",
    "ml_training_runs",
    "ml_model_registry",
    "knowledge_chunks",
    "reference_metrics",
)


@dataclass
class SourceDocument:
    source_table: str
    source_record_id: Optional[UUID]
    source_record_ref: str
    title: str
    content: str
    metadata: dict[str, Any]


@dataclass
class ReindexCounters:
    documents_seen: int = 0
    documents_created: int = 0
    documents_updated: int = 0
    documents_unchanged: int = 0
    documents_deleted: int = 0
    chunks_created: int = 0
    chunks_deleted: int = 0


def reindex_cooperative(
    db: Session,
    *,
    current_user: User,
    cooperative_id: Optional[UUID] = None,
    force: bool = False,
) -> RAGReindexResponse:
    if not settings.rag_enabled:
        raise ValidationError("RAG indexing is disabled.")
    if settings.rag_embedding_dimensions != 1536:
        raise ValidationError("Current schema expects 1536-dim embeddings.")

    scoped_cooperative_id = _resolve_target_cooperative_id(current_user, cooperative_id)
    started_at = current_utc()
    source_documents = _collect_source_documents(db, scoped_cooperative_id)
    counters = _reindex_documents(
        db,
        cooperative_id=scoped_cooperative_id,
        source_documents=source_documents,
        force=force,
        now=current_utc(),
        prune_stale=True,
    )
    db.commit()
    finished_at = current_utc()
    return RAGReindexResponse(
        cooperative_id=scoped_cooperative_id,
        started_at=started_at,
        finished_at=finished_at,
        documents_seen=counters.documents_seen,
        documents_created=counters.documents_created,
        documents_updated=counters.documents_updated,
        documents_unchanged=counters.documents_unchanged,
        documents_deleted=counters.documents_deleted,
        chunks_created=counters.chunks_created,
        chunks_deleted=counters.chunks_deleted,
    )


def reindex_targeted_sources(
    db: Session,
    *,
    current_user: User,
    targets: list[tuple[str, str | None]],
    cooperative_id: Optional[UUID] = None,
    force: bool = False,
) -> ReindexCounters:
    if not settings.rag_enabled or settings.rag_embedding_dimensions != 1536 or not targets:
        return ReindexCounters()

    scoped_cooperative_id = _resolve_target_cooperative_id(current_user, cooperative_id)
    table_filters: dict[str, set[str]] = {}
    for source_table, source_ref in targets:
        refs = table_filters.setdefault(source_table, set())
        if source_ref:
            refs.add(source_ref)

    source_documents = _collect_source_documents_for_tables(db, scoped_cooperative_id, set(table_filters.keys()))
    filtered_documents: list[SourceDocument] = []
    found_keys: set[str] = set()
    for doc in source_documents:
        refs = table_filters.get(doc.source_table, set())
        if refs and doc.source_record_ref not in refs:
            continue
        filtered_documents.append(doc)
        found_keys.add(_doc_key(APP_SOURCE_TYPE, doc.source_table, doc.source_record_ref))

    counters = _reindex_documents(
        db,
        cooperative_id=scoped_cooperative_id,
        source_documents=filtered_documents,
        force=force,
        now=current_utc(),
        prune_stale=False,
    )

    # Remove explicitly targeted documents that no longer exist in source tables (delete workflows).
    explicit_target_keys = {
        _doc_key(APP_SOURCE_TYPE, source_table, source_ref)
        for source_table, refs in table_filters.items()
        for source_ref in refs
    }
    missing_target_keys = explicit_target_keys - found_keys
    if missing_target_keys:
        stale_docs = db.scalars(
            select(RAGDocument).where(
                RAGDocument.cooperative_id == scoped_cooperative_id,
                RAGDocument.source_type == APP_SOURCE_TYPE,
            )
        ).all()
        stale_ids = [
            row.id
            for row in stale_docs
            if _doc_key(row.source_type, row.source_table, row.source_record_ref) in missing_target_keys
        ]
        if stale_ids:
            deleted_chunks = db.query(RAGChunk).filter(RAGChunk.document_id.in_(stale_ids)).delete(synchronize_session=False)
            deleted_docs = db.query(RAGDocument).filter(RAGDocument.id.in_(stale_ids)).delete(synchronize_session=False)
            counters.documents_deleted += int(deleted_docs)
            counters.chunks_deleted += int(deleted_chunks)

    db.commit()
    return counters


def _reindex_documents(
    db: Session,
    *,
    cooperative_id: UUID,
    source_documents: list[SourceDocument],
    force: bool,
    now: datetime,
    prune_stale: bool,
) -> ReindexCounters:
    counters = ReindexCounters(documents_seen=len(source_documents))
    existing_documents = db.scalars(
        select(RAGDocument).where(
            RAGDocument.cooperative_id == cooperative_id,
            RAGDocument.source_type == APP_SOURCE_TYPE,
        )
    ).all()
    existing_by_key = {
        _doc_key(record.source_type, record.source_table, record.source_record_ref): record
        for record in existing_documents
    }
    seen_keys: set[str] = set()

    for source in source_documents:
        key = _doc_key(APP_SOURCE_TYPE, source.source_table, source.source_record_ref)
        seen_keys.add(key)
        payload_hash = _content_hash(source.title, source.content, source.metadata)
        existing = existing_by_key.get(key)

        if existing is None:
            record = RAGDocument(
                cooperative_id=cooperative_id,
                source_type=APP_SOURCE_TYPE,
                source_table=source.source_table,
                source_record_id=source.source_record_id,
                source_record_ref=source.source_record_ref,
                title=source.title,
                content_hash=payload_hash,
                metadata_json=source.metadata,
                last_synced_at=now,
            )
            db.add(record)
            db.flush()
            chunks = _chunk_text(source.content)
            embeddings = embed_texts(chunks)
            _insert_chunks(
                db,
                record_id=record.id,
                cooperative_id=cooperative_id,
                source_table=source.source_table,
                source_record_ref=source.source_record_ref,
                source_metadata=source.metadata,
                chunks=chunks,
                embeddings=embeddings,
            )
            counters.documents_created += 1
            counters.chunks_created += len(chunks)
            continue

        existing.source_record_id = source.source_record_id
        existing.title = source.title
        existing.metadata_json = source.metadata
        existing.last_synced_at = now

        if not force and existing.content_hash == payload_hash:
            counters.documents_unchanged += 1
            continue

        chunks_deleted = db.query(RAGChunk).filter(RAGChunk.document_id == existing.id).delete(synchronize_session=False)
        chunks = _chunk_text(source.content)
        embeddings = embed_texts(chunks)
        _insert_chunks(
            db,
            record_id=existing.id,
            cooperative_id=cooperative_id,
            source_table=source.source_table,
            source_record_ref=source.source_record_ref,
            source_metadata=source.metadata,
            chunks=chunks,
            embeddings=embeddings,
        )
        existing.content_hash = payload_hash
        counters.documents_updated += 1
        counters.chunks_deleted += int(chunks_deleted)
        counters.chunks_created += len(chunks)

    if prune_stale:
        stale_document_ids = [
            record.id
            for key, record in existing_by_key.items()
            if key not in seen_keys
        ]
        if stale_document_ids:
            stale_chunks_deleted = db.query(RAGChunk).filter(RAGChunk.document_id.in_(stale_document_ids)).delete(
                synchronize_session=False
            )
            stale_documents_deleted = db.query(RAGDocument).filter(RAGDocument.id.in_(stale_document_ids)).delete(
                synchronize_session=False
            )
            counters.documents_deleted += int(stale_documents_deleted)
            counters.chunks_deleted += int(stale_chunks_deleted)
    return counters


def _resolve_target_cooperative_id(current_user: User, cooperative_id: Optional[UUID]) -> UUID:
    if current_user.role == UserRole.ADMIN:
        if cooperative_id is None:
            raise ValidationError("`cooperative_id` is required for admin reindex.")
        return cooperative_id
    if cooperative_id is not None and cooperative_id != current_user.cooperative_id:
        raise ForbiddenError("Managers can only reindex their own cooperative.")
    return get_manager_cooperative_id(current_user)


def _doc_key(source_type: str, source_table: str, source_record_ref: Optional[str]) -> str:
    return f"{source_type}::{source_table}::{source_record_ref or ''}"


def _content_hash(title: str, content: str, metadata: dict[str, Any]) -> str:
    payload = {
        "title": title,
        "content": content,
        "metadata": _stable_metadata_for_hash(metadata),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _stable_metadata_for_hash(metadata: dict[str, Any]) -> dict[str, Any]:
    stable: dict[str, Any] = {}
    for key, value in metadata.items():
        if key == "freshness_timestamp":
            continue
        stable[key] = value
    return stable


def _collect_source_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    return _collect_source_documents_for_tables(db, cooperative_id, set(INDEXED_SOURCE_TABLES))


def _collect_source_documents_for_tables(
    db: Session,
    cooperative_id: UUID,
    source_tables: set[str],
) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    for source_table in INDEXED_SOURCE_TABLES:
        if source_table not in source_tables:
            continue
        collector = _SOURCE_COLLECTORS.get(source_table)
        if collector is None:
            continue
        documents.extend(collector(db, cooperative_id))
    return documents


def get_indexed_source_tables() -> list[str]:
    return list(INDEXED_SOURCE_TABLES)


def _member_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.scalars(select(Member).where(Member.cooperative_id == cooperative_id)).all()
    documents: list[SourceDocument] = []
    for member in rows:
        content = _build_content_block(
            "Membre cooperative",
            [
                ("Nom", member.full_name),
                ("Code", member.code),
                ("Village", member.village),
                ("Produit principal", member.main_product),
                ("Produits secondaires", member.secondary_products),
                ("Specialite", member.specialty),
                ("Parcelles", member.parcel_count),
                ("Surface (ha)", member.area_hectares),
                ("Date adhesion", _fmt_date(member.join_date)),
                ("Statut", _fmt_enum(member.status)),
            ],
        )
        documents.append(
            SourceDocument(
                source_table="members",
                source_record_id=member.id,
                source_record_ref=f"member:{member.id}",
                title=f"Membre {member.full_name}",
                content=content,
                metadata={"entity": "member", "member_id": str(member.id), "member_name": member.full_name},
            )
        )
    return documents


def _field_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.execute(
        select(Field, Member)
        .join(Member, Member.id == Field.member_id)
        .where(Field.cooperative_id == cooperative_id)
    ).all()
    documents: list[SourceDocument] = []
    for field, member in rows:
        content = _build_content_block(
            "Parcelle cooperative",
            [
                ("Membre", member.full_name),
                ("Localisation", field.location),
                ("Surface (ha)", field.area),
                ("Type de sol", field.soil_type),
                ("Irrigation", field.irrigation_type),
            ],
        )
        documents.append(
            SourceDocument(
                source_table="fields",
                source_record_id=field.id,
                source_record_ref=f"field:{field.id}",
                title=f"Parcelle {member.full_name}",
                content=content,
                metadata={"entity": "field", "field_id": str(field.id), "member_id": str(member.id)},
            )
        )
    return documents


def _input_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.execute(
        select(Input, Member, Product)
        .join(Member, Member.id == Input.member_id)
        .join(Product, Product.id == Input.product_id)
        .where(Input.cooperative_id == cooperative_id)
    ).all()
    documents: list[SourceDocument] = []
    for input_row, member, product in rows:
        content = _build_content_block(
            "Collecte input cooperative",
            [
                ("Membre", member.full_name),
                ("Produit", product.name),
                ("Date", _fmt_date(input_row.date)),
                ("Quantite", input_row.quantity),
                ("Grade", input_row.grade),
                ("Valeur estimee FCFA", input_row.estimated_value),
                ("Statut", _fmt_enum(input_row.status)),
            ],
        )
        documents.append(
            SourceDocument(
                source_table="inputs",
                source_record_id=input_row.id,
                source_record_ref=f"input:{input_row.id}",
                title=f"Input {member.full_name} - {product.name}",
                content=content,
                metadata={"entity": "input", "input_id": str(input_row.id), "member_id": str(member.id), "product_id": str(product.id)},
            )
        )
    return documents


def _stock_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.execute(
        select(Stock, Product)
        .join(Product, Product.id == Stock.product_id)
        .where(Stock.cooperative_id == cooperative_id)
    ).all()
    documents: list[SourceDocument] = []
    for stock, product in rows:
        content = _build_content_block(
            "Stock cooperative",
            [
                ("Produit", product.name),
                ("Stock total kg", stock.total_stock_kg),
                ("Reserve lot kg", stock.reserved_in_lots_kg),
                ("Sortie process kg", stock.processed_output_kg),
                ("Seuil", stock.threshold),
                ("Unite", stock.unit),
                ("Derniere mise a jour", _fmt_dt(stock.last_updated)),
            ],
        )
        documents.append(
            SourceDocument(
                source_table="stocks",
                source_record_id=stock.id,
                source_record_ref=f"stock:{stock.id}",
                title=f"Stock {product.name}",
                content=content,
                metadata={"entity": "stock", "stock_id": str(stock.id), "product_id": str(product.id)},
            )
        )
    return documents


def _batch_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.execute(
        select(Batch, Product)
        .join(Product, Product.id == Batch.product_id)
        .where(Batch.cooperative_id == cooperative_id)
    ).all()
    batch_ids = [batch.id for batch, _ in rows]
    steps_by_batch: dict[UUID, list[ProcessStep]] = {}
    recommendations_by_batch: dict[UUID, Recommendation] = {}
    predictions_by_batch: dict[UUID, MLPredictionLog] = {}
    if batch_ids:
        step_rows = db.scalars(
            select(ProcessStep)
            .where(ProcessStep.batch_id.in_(batch_ids))
            .order_by(ProcessStep.sequence_order.asc())
        ).all()
        for step in step_rows:
            steps_by_batch.setdefault(step.batch_id, []).append(step)

        rec_rows = db.scalars(select(Recommendation).where(Recommendation.batch_id.in_(batch_ids))).all()
        recommendations_by_batch = {rec.batch_id: rec for rec in rec_rows}
        pred_rows = db.scalars(
            select(MLPredictionLog)
            .where(MLPredictionLog.batch_id.in_(batch_ids))
            .order_by(MLPredictionLog.created_at.desc())
        ).all()
        for prediction in pred_rows:
            if prediction.batch_id and prediction.batch_id not in predictions_by_batch:
                predictions_by_batch[prediction.batch_id] = prediction

    documents: list[SourceDocument] = []
    for batch, product in rows:
        steps = steps_by_batch.get(batch.id, [])
        recommendation = recommendations_by_batch.get(batch.id)
        prediction = predictions_by_batch.get(batch.id)
        fallback_content = _build_content_block(
            "Lot de transformation",
            [
                ("Code lot", batch.code),
                ("Produit", product.name),
                ("Date creation", _fmt_date(batch.creation_date)),
                ("Quantite initiale kg", batch.initial_qty),
                ("Quantite actuelle kg", batch.current_qty),
                ("Statut", _fmt_enum(batch.status)),
                ("Etapes", ", ".join(batch.ordered_process_steps or [])),
            ],
        )
        fallback_metadata = {
            "entity": "batch",
            "batch_id": str(batch.id),
            "product_id": str(product.id),
            "product_name": product.name,
            "batch_code": batch.code,
        }
        content, metadata = _semantic_chunk_or_fallback(
            source_table="batches",
            fallback_content=fallback_content,
            fallback_metadata=fallback_metadata,
            builder_kwargs={
                "batch": batch,
                "product": product,
                "process_steps": steps,
                "recommendation": recommendation,
                "cooperative_id": cooperative_id,
            },
        )
        documents.append(
            SourceDocument(
                source_table="batches",
                source_record_id=batch.id,
                source_record_ref=f"batch:{batch.id}",
                title=f"Lot {batch.code}",
                content=content,
                metadata=metadata,
            )
        )

        lot_status_chunk = build_lot_status_summary_chunk(
            batch=batch,
            product=product,
            process_steps=steps,
            recommendation=recommendation,
            cooperative_id=cooperative_id,
        )
        lot_status_metadata = lot_status_chunk.get("metadata", {})
        if isinstance(lot_status_metadata, dict) and validate_chunk_metadata(lot_status_metadata):
            documents.append(
                SourceDocument(
                    source_table="batches",
                    source_record_id=batch.id,
                    source_record_ref=f"batch_status:{batch.id}",
                    title=f"Lot status {batch.code}",
                    content=str(lot_status_chunk.get("content") or "").strip() or fallback_content,
                    metadata=lot_status_metadata,
                )
            )

        risk_chunk = build_operational_risk_summary_chunk(
            batch=batch,
            product=product,
            process_steps=steps,
            recommendation=recommendation,
            prediction=prediction,
            cooperative_id=cooperative_id,
        )
        risk_metadata = risk_chunk.get("metadata", {})
        if isinstance(risk_metadata, dict) and validate_chunk_metadata(risk_metadata):
            documents.append(
                SourceDocument(
                    source_table="batches",
                    source_record_id=batch.id,
                    source_record_ref=f"batch_risk:{batch.id}",
                    title=f"Risk summary {batch.code}",
                    content=str(risk_chunk.get("content") or "").strip() or fallback_content,
                    metadata=risk_metadata,
                )
            )
    return documents


def _process_step_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.execute(
        select(ProcessStep, Batch, Product)
        .join(Batch, Batch.id == ProcessStep.batch_id)
        .join(Product, Product.id == Batch.product_id)
        .where(Batch.cooperative_id == cooperative_id)
    ).all()
    product_stage_losses: dict[tuple[str, str], list[float]] = {}
    stage_losses: dict[str, list[float]] = {}
    stage_product_losses: dict[tuple[str, str], list[float]] = {}
    for step, _batch, product in rows:
        stage_canonical = normalize_stage(step.type)
        loss_kg = max(float(step.qty_in) - float(step.qty_out), 0.0)
        loss_pct = (loss_kg / float(step.qty_in) * 100.0) if step.qty_in else 0.0
        product_key = str(product.name or "").strip().lower()
        product_stage_losses.setdefault((product_key, stage_canonical), []).append(loss_pct)
        stage_losses.setdefault(stage_canonical, []).append(loss_pct)
        stage_product_losses.setdefault((stage_canonical, product_key), []).append(loss_pct)

    documents: list[SourceDocument] = []
    for step, batch, product in rows:
        loss_kg = max(float(step.qty_in) - float(step.qty_out), 0.0)
        loss_pct = (loss_kg / float(step.qty_in) * 100.0) if step.qty_in else 0.0
        product_key = str(product.name or "").strip().lower()
        stage_canonical = normalize_stage(step.type)
        stage_product_avg = _avg(product_stage_losses.get((product_key, stage_canonical), []))
        stage_coop_avg = _avg(stage_losses.get(stage_canonical, []))
        unrelated_product_name: str | None = None
        unrelated_product_loss_pct: float | None = None
        unrelated_candidates = [
            (name, _avg(values))
            for (stage_name, name), values in stage_product_losses.items()
            if stage_name == stage_canonical and name != product_key and values
        ]
        if unrelated_candidates:
            unrelated_product_name, unrelated_product_loss_pct = max(unrelated_candidates, key=lambda item: item[1])

        fallback_content = _build_content_block(
            "Etape de process",
            [
                ("Lot", batch.code),
                ("Produit", product.name),
                ("Type", step.type),
                ("Ordre", step.sequence_order),
                ("Date", _fmt_date(step.date)),
                ("Quantite entree kg", step.qty_in),
                ("Quantite sortie kg", step.qty_out),
                ("Perte kg", round(loss_kg, 2)),
                ("Perte pct", round(loss_pct, 2)),
                ("Statut", _fmt_enum(step.status)),
                ("Duree minutes", step.duration_minutes),
            ],
        )
        fallback_metadata = {
            "entity": "process_step",
            "process_step_id": str(step.id),
            "batch_id": str(batch.id),
            "product_id": str(product.id),
            "product_name": product.name,
            "batch_code": batch.code,
            "loss_pct": round(loss_pct, 2),
        }
        content, metadata = _semantic_chunk_or_fallback(
            source_table="process_steps",
            fallback_content=fallback_content,
            fallback_metadata=fallback_metadata,
            builder_kwargs={
                "step": step,
                "batch": batch,
                "product": product,
                "cooperative_id": cooperative_id,
            },
        )
        documents.append(
            SourceDocument(
                source_table="process_steps",
                source_record_id=step.id,
                source_record_ref=f"process_step:{step.id}",
                title=f"Etape {step.type} - {batch.code}",
                content=content,
                metadata=metadata,
            )
        )

        product_stage_chunk = build_product_stage_summary_chunk(
            step=step,
            batch=batch,
            product=product,
            cooperative_id=cooperative_id,
            product_stage_avg_loss_pct=stage_product_avg,
            cooperative_stage_avg_loss_pct=stage_coop_avg,
        )
        product_stage_metadata = product_stage_chunk.get("metadata", {})
        if isinstance(product_stage_metadata, dict) and validate_chunk_metadata(product_stage_metadata):
            documents.append(
                SourceDocument(
                    source_table="process_steps",
                    source_record_id=step.id,
                    source_record_ref=f"process_step_scope:{step.id}",
                    title=f"Product-stage {product.name} {step.type} - {batch.code}",
                    content=str(product_stage_chunk.get("content") or "").strip() or fallback_content,
                    metadata=product_stage_metadata,
                )
            )

        scoped_loss_chunk = build_scoped_loss_summary_chunk(
            source_row_id=f"{step.id}:scoped_loss",
            cooperative_id=cooperative_id,
            product_name=product.name,
            stage=step.type,
            stage_canonical=stage_canonical,
            product_stage_loss_pct=stage_product_avg if stage_product_avg is not None else loss_pct,
            cooperative_loss_pct=stage_coop_avg if stage_coop_avg is not None else loss_pct,
            unrelated_product_name=unrelated_product_name,
            unrelated_product_loss_pct=unrelated_product_loss_pct,
        )
        scoped_loss_metadata = scoped_loss_chunk.get("metadata", {})
        if isinstance(scoped_loss_metadata, dict) and validate_chunk_metadata(scoped_loss_metadata):
            documents.append(
                SourceDocument(
                    source_table="process_steps",
                    source_record_id=step.id,
                    source_record_ref=f"process_step_scoped_loss:{step.id}",
                    title=f"Scoped loss {product.name} {step.type}",
                    content=str(scoped_loss_chunk.get("content") or "").strip() or fallback_content,
                    metadata=scoped_loss_metadata,
                )
            )
    return documents


def _farmer_advance_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.execute(
        select(FarmerAdvance, Member)
        .join(Member, Member.id == FarmerAdvance.farmer_id)
        .where(FarmerAdvance.cooperative_id == cooperative_id)
    ).all()
    documents: list[SourceDocument] = []
    for advance, member in rows:
        content = _build_content_block(
            "Avance producteur",
            [
                ("Membre", member.full_name),
                ("Montant FCFA", advance.amount_fcfa),
                ("Date avance", _fmt_date(advance.advance_date)),
                ("Raison", advance.reason),
                ("Statut", _fmt_enum(advance.status)),
            ],
        )
        documents.append(
            SourceDocument(
                source_table="farmer_advances",
                source_record_id=advance.id,
                source_record_ref=f"farmer_advance:{advance.id}",
                title=f"Avance {member.full_name}",
                content=content,
                metadata={"entity": "farmer_advance", "advance_id": str(advance.id), "member_id": str(member.id)},
            )
        )
    return documents


def _treasury_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.execute(
        select(TreasuryTransaction, Member)
        .outerjoin(Member, Member.id == TreasuryTransaction.farmer_id)
        .where(TreasuryTransaction.cooperative_id == cooperative_id)
    ).all()
    documents: list[SourceDocument] = []
    for tx, member in rows:
        content = _build_content_block(
            "Transaction tresorerie",
            [
                ("Reference", tx.reference),
                ("Type", _fmt_enum(tx.type)),
                ("Categorie", tx.category),
                ("Libelle", tx.label),
                ("Montant FCFA", tx.amount_fcfa),
                ("Date", _fmt_date(tx.transaction_date)),
                ("Statut", _fmt_enum(tx.status)),
                ("Source", tx.source_type),
                ("Membre", member.full_name if member else None),
            ],
        )
        documents.append(
            SourceDocument(
                source_table="treasury_transactions",
                source_record_id=tx.id,
                source_record_ref=f"treasury:{tx.id}",
                title=f"Tresorerie {tx.reference}",
                content=content,
                metadata={"entity": "treasury_transaction", "transaction_id": str(tx.id), "member_id": str(member.id) if member else None},
            )
        )
    return documents


def _commercial_catalog_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.scalars(
        select(CommercialCatalogProduct).where(CommercialCatalogProduct.cooperative_id == cooperative_id)
    ).all()
    documents: list[SourceDocument] = []
    for product in rows:
        content = _build_content_block(
            "Catalogue commercial",
            [
                ("Nom", product.name),
                ("Categorie", product.category),
                ("Description", product.description),
                ("Unite vente", product.sale_unit),
                ("Prix vente FCFA", product.sale_price_fcfa),
                ("Cout FCFA", product.cost_price_fcfa),
                ("Stock kg", product.total_stock_kg),
                ("Stock reserve kg", product.reserved_stock_kg),
                ("Statut", _fmt_enum(product.status)),
            ],
        )
        documents.append(
            SourceDocument(
                source_table="commercial_catalog_products",
                source_record_id=product.id,
                source_record_ref=f"catalog_product:{product.id}",
                title=f"Catalogue {product.name}",
                content=content,
                metadata={"entity": "catalog_product", "catalog_product_id": str(product.id)},
            )
        )
    return documents


def _commercial_order_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    orders = db.scalars(
        select(CommercialOrder)
        .options(selectinload(CommercialOrder.lines))
        .where(CommercialOrder.cooperative_id == cooperative_id)
    ).all()
    documents: list[SourceDocument] = []
    for order in orders:
        line_descriptions = [
            f"{line.product_name_snapshot} {line.quantity} {line.unit_snapshot} total {line.line_total_fcfa} FCFA"
            for line in order.lines
        ]
        fallback_content = _build_content_block(
            "Commande commercialisation",
            [
                ("Numero", order.order_number),
                ("Statut", _fmt_enum(order.status)),
                ("Source", order.source),
                ("Sous total FCFA", order.subtotal_fcfa),
                ("Taxe FCFA", order.tax_amount_fcfa),
                ("Total FCFA", order.total_amount_fcfa),
                ("Date reception", _fmt_dt(order.received_at)),
                ("Lignes", " | ".join(line_descriptions)),
            ],
        )
        fallback_metadata = {"entity": "commercial_order", "order_id": str(order.id), "order_number": order.order_number}
        content, metadata = _semantic_chunk_or_fallback(
            source_table="commercial_orders",
            fallback_content=fallback_content,
            fallback_metadata=fallback_metadata,
            builder_kwargs={
                "order": order,
                "cooperative_id": cooperative_id,
            },
        )
        documents.append(
            SourceDocument(
                source_table="commercial_orders",
                source_record_id=order.id,
                source_record_ref=f"commercial_order:{order.id}",
                title=f"Commande {order.order_number}",
                content=content,
                metadata=metadata,
            )
        )
    return documents


def _commercial_invoice_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    invoices = db.scalars(
        select(CommercialInvoice)
        .options(selectinload(CommercialInvoice.lines))
        .where(CommercialInvoice.cooperative_id == cooperative_id)
    ).all()
    documents: list[SourceDocument] = []
    for invoice in invoices:
        line_descriptions = [
            f"{line.description} {line.quantity} {line.unit} total {line.line_total_fcfa} FCFA"
            for line in invoice.lines
        ]
        content = _build_content_block(
            "Facture commercialisation",
            [
                ("Numero", invoice.invoice_number),
                ("Statut", _fmt_enum(invoice.status)),
                ("Date emission", _fmt_date(invoice.issue_date)),
                ("Date echeance", _fmt_date(invoice.due_date)),
                ("Total FCFA", invoice.total_amount_fcfa),
                ("Taxe FCFA", invoice.tax_amount_fcfa),
                ("Payee le", _fmt_dt(invoice.paid_at)),
                ("Lignes", " | ".join(line_descriptions)),
            ],
        )
        documents.append(
            SourceDocument(
                source_table="commercial_invoices",
                source_record_id=invoice.id,
                source_record_ref=f"commercial_invoice:{invoice.id}",
                title=f"Facture {invoice.invoice_number}",
                content=content,
                metadata={"entity": "commercial_invoice", "invoice_id": str(invoice.id), "invoice_number": invoice.invoice_number},
            )
        )
    return documents


def _parcel_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.execute(
        select(Parcel, Member)
        .join(Member, Member.id == Parcel.member_id)
        .where(Parcel.cooperative_id == cooperative_id)
    ).all()
    parcel_ids = [parcel.id for parcel, _ in rows]
    preharvest_by_parcel: dict[UUID, list[PreHarvestStep]] = {}
    if parcel_ids:
        pre_rows = db.scalars(
            select(PreHarvestStep)
            .where(PreHarvestStep.parcel_id.in_(parcel_ids))
            .order_by(PreHarvestStep.created_at.desc())
        ).all()
        for step in pre_rows:
            preharvest_by_parcel.setdefault(step.parcel_id, []).append(step)

    documents: list[SourceDocument] = []
    for parcel, member in rows:
        fallback_content = _build_content_block(
            "Parcelle culturale",
            [
                ("Nom", parcel.name),
                ("Membre", member.full_name),
                ("Surface (ha)", parcel.surface_ha),
                ("Culture principale", parcel.main_culture),
                ("Variete", parcel.variety),
                ("Nombre d'arbres", parcel.tree_count),
            ],
        )
        fallback_metadata = {
            "entity": "parcel",
            "parcel_id": str(parcel.id),
            "member_id": str(member.id),
            "product_name": parcel.main_culture,
        }
        content, metadata = _semantic_chunk_or_fallback(
            source_table="parcels",
            fallback_content=fallback_content,
            fallback_metadata=fallback_metadata,
            builder_kwargs={
                "parcel": parcel,
                "member": member,
                "recent_preharvest_steps": preharvest_by_parcel.get(parcel.id, [])[:3],
                "cooperative_id": cooperative_id,
            },
        )
        documents.append(
            SourceDocument(
                source_table="parcels",
                source_record_id=parcel.id,
                source_record_ref=f"parcel:{parcel.id}",
                title=f"Parcelle {parcel.name}",
                content=content,
                metadata=metadata,
            )
        )
    return documents


def _pre_harvest_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.execute(
        select(PreHarvestStep, Parcel, Member)
        .join(Parcel, Parcel.id == PreHarvestStep.parcel_id)
        .join(Member, Member.id == PreHarvestStep.member_id)
        .where(PreHarvestStep.cooperative_id == cooperative_id)
    ).all()
    documents: list[SourceDocument] = []
    for step, parcel, member in rows:
        fallback_content = _build_content_block(
            "Etape pre-recolte",
            [
                ("Parcelle", parcel.name),
                ("Membre", member.full_name),
                ("Categorie", step.category),
                ("Etape", step.label),
                ("Statut", _fmt_enum(step.status)),
                ("Quantite", step.quantity_value),
                ("Unite", step.quantity_unit),
                ("Date realisation", _fmt_date(step.realization_date)),
                ("Cout operation FCFA", step.operation_cost_fcfa),
                ("Observation", step.observations),
            ],
        )
        fallback_metadata = {
            "entity": "pre_harvest_step",
            "pre_harvest_step_id": str(step.id),
            "member_id": str(member.id),
            "parcel_id": str(parcel.id),
            "product_name": parcel.main_culture,
        }
        content, metadata = _semantic_chunk_or_fallback(
            source_table="pre_harvest_steps",
            fallback_content=fallback_content,
            fallback_metadata=fallback_metadata,
            builder_kwargs={
                "step": step,
                "parcel": parcel,
                "member": member,
                "cooperative_id": cooperative_id,
            },
        )
        documents.append(
            SourceDocument(
                source_table="pre_harvest_steps",
                source_record_id=step.id,
                source_record_ref=f"pre_harvest_step:{step.id}",
                title=f"Pre-harvest {step.label} - {parcel.name}",
                content=content,
                metadata=metadata,
            )
        )
    return documents


def _recommendation_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.execute(
        select(Recommendation, Batch, Product)
        .join(Batch, Batch.id == Recommendation.batch_id)
        .join(Product, Product.id == Batch.product_id)
        .where(Batch.cooperative_id == cooperative_id)
    ).all()
    documents: list[SourceDocument] = []
    for recommendation, batch, product in rows:
        fallback_content = _build_content_block(
            "Recommandation lot",
            [
                ("Lot", batch.code),
                ("Produit", product.name),
                ("Loss pct", recommendation.loss_pct),
                ("Efficiency pct", recommendation.efficiency_pct),
                ("Risk level", _fmt_enum(recommendation.risk_level)),
                ("Action", recommendation.suggested_action),
                ("Rationale", recommendation.rationale),
            ],
        )
        fallback_metadata = {
            "entity": "recommendation",
            "recommendation_id": str(recommendation.id),
            "batch_id": str(batch.id),
            "product_id": str(product.id),
            "product_name": product.name,
            "risk_level": _fmt_enum(recommendation.risk_level).upper(),
        }
        content, metadata = _semantic_chunk_or_fallback(
            source_table="recommendations",
            fallback_content=fallback_content,
            fallback_metadata=fallback_metadata,
            builder_kwargs={
                "recommendation": recommendation,
                "batch": batch,
                "product": product,
                "cooperative_id": cooperative_id,
            },
        )
        documents.append(
            SourceDocument(
                source_table="recommendations",
                source_record_id=recommendation.id,
                source_record_ref=f"recommendation:{recommendation.id}",
                title=f"Recommendation {batch.code}",
                content=content,
                metadata=metadata,
            )
        )
        lot_chunk = build_lot_recommendation_summary_chunk(
            recommendation=recommendation,
            batch=batch,
            product=product,
            cooperative_id=cooperative_id,
        )
        lot_metadata = lot_chunk.get("metadata", {})
        if isinstance(lot_metadata, dict) and validate_chunk_metadata(lot_metadata):
            documents.append(
                SourceDocument(
                    source_table="recommendations",
                    source_record_id=recommendation.id,
                    source_record_ref=f"recommendation_lot:{recommendation.id}",
                    title=f"Lot recommendation {batch.code}",
                    content=str(lot_chunk.get("content") or "").strip() or fallback_content,
                    metadata=lot_metadata,
                )
            )
    return documents


def _ml_prediction_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.scalars(select(MLPredictionLog).order_by(MLPredictionLog.created_at.desc())).all()
    batch_ids = [row.batch_id for row in rows if row.batch_id is not None]
    batch_map: dict[UUID, Batch] = {}
    if batch_ids:
        batches = db.scalars(
            select(Batch).where(Batch.id.in_(batch_ids), Batch.cooperative_id == cooperative_id)
        ).all()
        batch_map = {batch.id: batch for batch in batches}

    documents: list[SourceDocument] = []
    for prediction in rows:
        if prediction.batch_id and prediction.batch_id not in batch_map:
            continue
        batch = batch_map.get(prediction.batch_id) if prediction.batch_id else None
        fallback_content = _build_content_block(
            "Prediction ML",
            [
                ("Batch", str(prediction.batch_id or "")),
                ("Model version", prediction.model_version),
                ("Product", prediction.product),
                ("Critical stage", prediction.critical_stage),
                ("Predicted loss pct", prediction.predicted_loss_pct),
                ("Expected efficiency pct", prediction.expected_efficiency_pct),
                ("Risk level", _fmt_enum(prediction.risk_level) if prediction.risk_level else None),
                ("Anomaly score", prediction.anomaly_score),
                ("Anomalous", prediction.is_anomalous),
            ],
        )
        fallback_metadata = {
            "entity": "ml_prediction_log",
            "prediction_log_id": str(prediction.id),
            "batch_id": str(prediction.batch_id) if prediction.batch_id else None,
            "product_name": prediction.product,
            "ml_model_version": prediction.model_version,
            "anomaly_flag": bool(prediction.is_anomalous),
        }
        content, metadata = _semantic_chunk_or_fallback(
            source_table="ml_prediction_logs",
            fallback_content=fallback_content,
            fallback_metadata=fallback_metadata,
            builder_kwargs={
                "prediction": prediction,
                "batch": batch,
                "cooperative_id": cooperative_id,
            },
        )
        documents.append(
            SourceDocument(
                source_table="ml_prediction_logs",
                source_record_id=prediction.id,
                source_record_ref=f"ml_prediction:{prediction.id}",
                title=f"ML prediction {prediction.id}",
                content=content,
                metadata=metadata,
            )
        )
        if prediction.is_anomalous:
            anomaly_chunk = build_anomaly_summary_chunk(
                feedback=None,
                prediction=prediction,
                recommendation_log=None,
                cooperative_id=cooperative_id,
            )
            anomaly_metadata = anomaly_chunk.get("metadata", {})
            if isinstance(anomaly_metadata, dict) and validate_chunk_metadata(anomaly_metadata):
                documents.append(
                    SourceDocument(
                        source_table="ml_prediction_logs",
                        source_record_id=prediction.id,
                        source_record_ref=f"ml_prediction_anomaly:{prediction.id}",
                        title=f"ML anomaly {prediction.id}",
                        content=str(anomaly_chunk.get("content") or "").strip() or fallback_content,
                        metadata=anomaly_metadata,
                    )
                )
    return documents


def _ml_recommendation_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.scalars(select(MLRecommendationLog).order_by(MLRecommendationLog.created_at.desc())).all()
    batch_ids = [row.batch_id for row in rows if row.batch_id is not None]
    batch_map: dict[UUID, Batch] = {}
    if batch_ids:
        batches = db.scalars(select(Batch).where(Batch.id.in_(batch_ids), Batch.cooperative_id == cooperative_id)).all()
        batch_map = {batch.id: batch for batch in batches}

    documents: list[SourceDocument] = []
    for row in rows:
        if row.batch_id and row.batch_id not in batch_map:
            continue
        structured = row.structured_recommendation if isinstance(row.structured_recommendation, dict) else {}
        action = structured.get("action") or structured.get("recommended_action") or "No structured action"
        risk = structured.get("risk_level") or "unknown"
        fallback_content = _build_content_block(
            "Recommendation log ML",
            [
                ("Batch", str(row.batch_id or "")),
                ("Action", action),
                ("Risk", risk),
                ("Explanation", row.llm_explanation),
            ],
        )
        content = (
            f"ML recommendation log for batch {row.batch_id or 'unknown'} suggests action: {action}. "
            f"Risk hint is {risk}. Explanation: {row.llm_explanation or 'not available'}."
        )
        metadata = {
            "entity": "ml_recommendation_log",
            "chunk_type": "recommendation_context",
            "source_table": "ml_recommendation_logs",
            "source_row_id": str(row.id),
            "cooperative_id": str(cooperative_id),
            "freshness_timestamp": current_utc().isoformat(),
            "batch_id": str(row.batch_id) if row.batch_id else None,
            "recommendation_type": "ml_recommendation",
            "risk_level": str(risk).upper(),
            "access_level": "cooperative_internal",
        }
        metadata = {k: v for k, v in metadata.items() if v is not None}
        if not validate_chunk_metadata(metadata):
            content = fallback_content
            metadata = {"entity": "ml_recommendation_log", "recommendation_log_id": str(row.id)}
        documents.append(
            SourceDocument(
                source_table="ml_recommendation_logs",
                source_record_id=row.id,
                source_record_ref=f"ml_recommendation:{row.id}",
                title=f"ML recommendation {row.id}",
                content=content,
                metadata=metadata,
            )
        )
    return documents


def _recommendation_feedback_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    feedback_rows = db.scalars(select(RecommendationFeedbackLog).order_by(RecommendationFeedbackLog.created_at.desc())).all()
    recommendation_ids = [row.recommendation_log_id for row in feedback_rows if row.recommendation_log_id is not None]
    prediction_rows = db.scalars(select(MLPredictionLog).order_by(MLPredictionLog.created_at.desc())).all()
    prediction_by_batch = {row.batch_id: row for row in prediction_rows if row.batch_id is not None}
    recommendation_map: dict[UUID, MLRecommendationLog] = {}
    if recommendation_ids:
        recommendation_rows = db.scalars(select(MLRecommendationLog).where(MLRecommendationLog.id.in_(recommendation_ids))).all()
        recommendation_map = {row.id: row for row in recommendation_rows}

    batch_ids = [row.batch_id for row in feedback_rows if row.batch_id is not None]
    batch_map: dict[UUID, Batch] = {}
    if batch_ids:
        batches = db.scalars(select(Batch).where(Batch.id.in_(batch_ids), Batch.cooperative_id == cooperative_id)).all()
        batch_map = {batch.id: batch for batch in batches}

    documents: list[SourceDocument] = []
    for feedback in feedback_rows:
        if feedback.batch_id and feedback.batch_id not in batch_map:
            continue
        recommendation_log = recommendation_map.get(feedback.recommendation_log_id) if feedback.recommendation_log_id else None
        prediction = prediction_by_batch.get(feedback.batch_id) if feedback.batch_id else None
        fallback_content = _build_content_block(
            "Feedback recommandation",
            [
                ("Batch", str(feedback.batch_id or "")),
                ("Stage", feedback.stage),
                ("Accepted", feedback.accepted),
                ("Executed", feedback.executed),
                ("Delta loss", feedback.delta_loss),
                ("Outcome", feedback.outcome_label),
                ("Comment", feedback.comment),
            ],
        )
        content, metadata = _semantic_chunk_or_fallback(
            source_table="recommendation_feedback_logs",
            fallback_content=fallback_content,
            fallback_metadata={
                "entity": "recommendation_feedback_log",
                "feedback_id": str(feedback.id),
                "batch_id": str(feedback.batch_id) if feedback.batch_id else None,
            },
            builder_kwargs={
                "feedback": feedback,
                "prediction": prediction,
                "recommendation_log": recommendation_log,
                "cooperative_id": cooperative_id,
            },
        )
        documents.append(
            SourceDocument(
                source_table="recommendation_feedback_logs",
                source_record_id=feedback.id,
                source_record_ref=f"recommendation_feedback:{feedback.id}",
                title=f"Recommendation feedback {feedback.id}",
                content=content,
                metadata=metadata,
            )
        )
    return documents


def _global_charge_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.execute(
        select(GlobalCharge, Member, Parcel, PreHarvestStep)
        .join(Member, Member.id == GlobalCharge.member_id)
        .outerjoin(Parcel, Parcel.id == GlobalCharge.parcel_id)
        .outerjoin(PreHarvestStep, PreHarvestStep.id == GlobalCharge.pre_harvest_step_id)
        .where(GlobalCharge.cooperative_id == cooperative_id)
    ).all()
    documents: list[SourceDocument] = []
    for charge, member, parcel, step in rows:
        fallback_content = _build_content_block(
            "Charge globale",
            [
                ("Type", charge.charge_type),
                ("Label", charge.label),
                ("Amount FCFA", charge.amount_fcfa),
                ("Date", _fmt_date(charge.date)),
                ("Membre", member.full_name if member else None),
                ("Parcelle", parcel.name if parcel else None),
                ("Step", step.label if step else None),
                ("Notes", charge.notes),
            ],
        )
        fallback_metadata = {
            "entity": "global_charge",
            "charge_id": str(charge.id),
            "member_id": str(charge.member_id),
            "parcel_id": str(charge.parcel_id) if charge.parcel_id else None,
        }
        content, metadata = _semantic_chunk_or_fallback(
            source_table="global_charges",
            fallback_content=fallback_content,
            fallback_metadata=fallback_metadata,
            builder_kwargs={
                "charge": charge,
                "member": member,
                "parcel": parcel,
                "step": step,
                "cooperative_id": cooperative_id,
            },
        )
        documents.append(
            SourceDocument(
                source_table="global_charges",
                source_record_id=charge.id,
                source_record_ref=f"global_charge:{charge.id}",
                title=f"Global charge {charge.label}",
                content=content,
                metadata=metadata,
            )
        )
    return documents


def _ml_training_run_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.scalars(select(MLTrainingRun).order_by(MLTrainingRun.started_at.desc())).all()
    documents: list[SourceDocument] = []
    for run in rows:
        fallback_content = _build_content_block(
            "ML training run",
            [
                ("Run name", run.run_name),
                ("Status", run.status),
                ("Started at", _fmt_dt(run.started_at)),
                ("Completed at", _fmt_dt(run.completed_at)),
                ("Dataset rows", run.dataset_rows),
                ("Metrics", json.dumps(run.metrics, ensure_ascii=True)),
            ],
        )
        content, metadata = _semantic_chunk_or_fallback(
            source_table="ml_training_runs",
            fallback_content=fallback_content,
            fallback_metadata={"entity": "ml_training_run", "training_run_id": str(run.id)},
            builder_kwargs={"run": run, "cooperative_id": cooperative_id},
        )
        documents.append(
            SourceDocument(
                source_table="ml_training_runs",
                source_record_id=run.id,
                source_record_ref=f"ml_training_run:{run.id}",
                title=f"Training run {run.run_name}",
                content=content,
                metadata=metadata,
            )
        )
    return documents


def _ml_model_registry_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.scalars(select(MLModelRegistry).order_by(MLModelRegistry.created_at.desc())).all()
    documents: list[SourceDocument] = []
    for model in rows:
        metrics = model.metrics if isinstance(model.metrics, dict) else {}
        metric_summary = ", ".join(f"{key}={value}" for key, value in list(metrics.items())[:4]) or "none"
        content = (
            f"Model registry entry {model.model_name} version {model.version} is "
            f"{'active' if model.is_active else 'inactive'}. "
            f"Artifact path: {model.artifact_path}. Key metrics: {metric_summary}."
        )
        metadata = {
            "chunk_type": "ml_evaluation_context",
            "source_table": "ml_model_registry",
            "source_row_id": str(model.id),
            "cooperative_id": str(cooperative_id),
            "freshness_timestamp": current_utc().isoformat(),
            "ml_model_version": model.version,
            "access_level": "cooperative_internal",
        }
        if not validate_chunk_metadata(metadata):
            content = _build_content_block(
                "ML model registry",
                [
                    ("Model", model.model_name),
                    ("Version", model.version),
                    ("Active", model.is_active),
                    ("Artifact", model.artifact_path),
                ],
            )
            metadata = {"entity": "ml_model_registry", "model_registry_id": str(model.id)}
        documents.append(
            SourceDocument(
                source_table="ml_model_registry",
                source_record_id=model.id,
                source_record_ref=f"ml_model_registry:{model.id}",
                title=f"Model {model.model_name} v{model.version}",
                content=content,
                metadata=metadata,
            )
        )
    return documents


def _knowledge_chunk_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.scalars(select(KnowledgeChunk).order_by(KnowledgeChunk.created_at.desc())).all()
    documents: list[SourceDocument] = []
    for row in rows:
        fallback_content = _build_content_block(
            "Agronomic knowledge",
            [
                ("Source", row.source_id),
                ("Country", row.country),
                ("Region", row.region),
                ("Crop", row.crop),
                ("Topic", row.topic),
                ("Content", row.content),
            ],
        )
        fallback_metadata = {
            "entity": "knowledge_chunk",
            "chunk_type": "agronomic_knowledge",
            "source_id": row.source_id,
            "source_url": row.source_url,
            "country": row.country,
            "region": row.region,
            "product_name": row.crop,
            "topic": row.topic,
            "access_level": "reference_public",
        }
        content, metadata = _semantic_chunk_or_fallback(
            source_table="knowledge_chunks",
            fallback_content=fallback_content,
            fallback_metadata=fallback_metadata,
            builder_kwargs={"chunk": row, "cooperative_id": cooperative_id},
        )
        documents.append(
            SourceDocument(
                source_table="knowledge_chunks",
                source_record_id=row.id,
                source_record_ref=f"knowledge_chunk:{row.id}",
                title=f"Knowledge {row.crop} - {row.topic}",
                content=content,
                metadata=metadata,
            )
        )
    return documents


def _reference_metric_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    rows = db.scalars(select(ReferenceMetric).order_by(ReferenceMetric.created_at.desc())).all()
    documents: list[SourceDocument] = []
    for row in rows:
        fallback_content = _build_content_block(
            "Benchmark reference metric",
            [
                ("Source", row.source_id),
                ("Country", row.country),
                ("Region", row.region),
                ("Crop", row.crop),
                ("Metric", row.metric),
                ("Period", row.period),
                ("Value", f"{row.value} {row.unit}"),
                ("Notes", row.notes),
            ],
        )
        fallback_metadata = {
            "entity": "reference_metric",
            "chunk_type": "benchmark_reference",
            "source_id": row.source_id,
            "country": row.country,
            "region": row.region,
            "product_name": row.crop,
            "topic": row.metric,
            "metric_name": row.metric,
            "metric_value": round(float(row.value), 4),
            "period": row.period,
            "access_level": "reference_public",
        }
        content, metadata = _semantic_chunk_or_fallback(
            source_table="reference_metrics",
            fallback_content=fallback_content,
            fallback_metadata=fallback_metadata,
            builder_kwargs={"metric": row, "cooperative_id": cooperative_id},
        )
        documents.append(
            SourceDocument(
                source_table="reference_metrics",
                source_record_id=row.id,
                source_record_ref=f"reference_metric:{row.id}",
                title=f"Benchmark {row.crop} - {row.metric}",
                content=content,
                metadata=metadata,
            )
        )
    return documents


_SOURCE_COLLECTORS = {
    "members": _member_documents,
    "fields": _field_documents,
    "inputs": _input_documents,
    "stocks": _stock_documents,
    "batches": _batch_documents,
    "process_steps": _process_step_documents,
    "farmer_advances": _farmer_advance_documents,
    "treasury_transactions": _treasury_documents,
    "commercial_catalog_products": _commercial_catalog_documents,
    "commercial_orders": _commercial_order_documents,
    "commercial_invoices": _commercial_invoice_documents,
    "parcels": _parcel_documents,
    "pre_harvest_steps": _pre_harvest_documents,
    "recommendations": _recommendation_documents,
    "ml_prediction_logs": _ml_prediction_documents,
    "ml_recommendation_logs": _ml_recommendation_documents,
    "recommendation_feedback_logs": _recommendation_feedback_documents,
    "global_charges": _global_charge_documents,
    "ml_training_runs": _ml_training_run_documents,
    "ml_model_registry": _ml_model_registry_documents,
    "knowledge_chunks": _knowledge_chunk_documents,
    "reference_metrics": _reference_metric_documents,
}


def _build_content_block(title: str, fields: list[tuple[str, Any]]) -> str:
    lines = [title]
    for label, value in fields:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        lines.append(f"- {label}: {text}")
    return "\n".join(lines)


def _semantic_chunk_or_fallback(
    *,
    source_table: str,
    fallback_content: str,
    fallback_metadata: dict[str, Any],
    builder_kwargs: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    builder = get_chunk_builder(source_table)
    if builder is None:
        return fallback_content, fallback_metadata
    try:
        chunk = builder(**builder_kwargs)
        content = str(chunk.get("content") or "").strip()
        metadata = chunk.get("metadata")
        if not content or not isinstance(metadata, dict) or not validate_chunk_metadata(metadata):
            return fallback_content, fallback_metadata
        merged = dict(fallback_metadata)
        merged.update(metadata)
        return content, merged
    except Exception:
        return fallback_content, fallback_metadata


def _chunk_text(text: str) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return ["(empty)"]

    chunk_size = max(200, int(settings.rag_chunk_size))
    overlap = max(0, int(settings.rag_chunk_overlap))
    if overlap >= chunk_size:
        overlap = chunk_size // 5

    chunks: list[str] = []
    start = 0
    text_len = len(normalized)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            backtrack_limit = max(start + int(chunk_size * 0.6), start + 1)
            split = normalized.rfind(" ", backtrack_limit, end)
            if split > start:
                end = split
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_len:
            break
        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start
    return chunks or [normalized]


def _insert_chunks(
    db: Session,
    *,
    record_id: UUID,
    cooperative_id: UUID,
    source_table: str,
    source_record_ref: str,
    source_metadata: dict[str, Any],
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    if len(chunks) != len(embeddings):
        raise ValidationError("Chunk/embedding count mismatch.")

    for idx, (content, vector) in enumerate(zip(chunks, embeddings)):
        chunk_metadata = _build_chunk_metadata(
            chunk_index=idx,
            cooperative_id=cooperative_id,
            source_table=source_table,
            source_record_ref=source_record_ref,
            source_metadata=source_metadata,
            content=content,
        )
        db.add(
            RAGChunk(
                document_id=record_id,
                cooperative_id=cooperative_id,
                chunk_index=idx,
                content=content,
                embedding=_vector_literal(vector),
                metadata_json=chunk_metadata,
            )
        )


def _build_chunk_metadata(
    *,
    chunk_index: int,
    cooperative_id: UUID,
    source_table: str,
    source_record_ref: str,
    source_metadata: dict[str, Any],
    content: str,
) -> dict[str, Any]:
    metadata = dict(source_metadata) if isinstance(source_metadata, dict) else {}
    metadata["source_table"] = source_table
    metadata["source_row_id"] = source_metadata.get("source_row_id", source_record_ref)
    metadata["cooperative_id"] = str(cooperative_id)
    metadata["freshness_timestamp"] = current_utc().isoformat()
    metadata["chunk_index"] = chunk_index
    metadata["chunk_tokens_est"] = _estimate_token_count(content)
    if "chunk_type" not in metadata:
        metadata["chunk_type"] = metadata.get("entity", source_table)
    return metadata


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in vector) + "]"


def _estimate_token_count(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _fmt_date(value: Optional[date]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()


def _fmt_dt(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()


def _fmt_enum(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)

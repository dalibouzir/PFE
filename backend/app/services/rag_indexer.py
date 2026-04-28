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
from app.models.batch import Batch
from app.models.commercial_catalog_product import CommercialCatalogProduct
from app.models.commercial_invoice import CommercialInvoice
from app.models.commercial_order import CommercialOrder
from app.models.enums import UserRole
from app.models.farmer_advance import FarmerAdvance
from app.models.field import Field
from app.models.input import Input
from app.models.member import Member
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.rag import RAGChunk, RAGDocument
from app.models.stock import Stock
from app.models.treasury_transaction import TreasuryTransaction
from app.models.user import User
from app.models.mixins import current_utc
from app.schemas.rag import RAGReindexResponse
from app.services.rag_embeddings import embed_texts
from app.services.helpers import get_manager_cooperative_id
from app.utils.exceptions import ForbiddenError, ValidationError


APP_SOURCE_TYPE = "app_data"


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
    counters = ReindexCounters(documents_seen=len(source_documents))
    now = current_utc()

    existing_documents = db.scalars(
        select(RAGDocument).where(
            RAGDocument.cooperative_id == scoped_cooperative_id,
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
                cooperative_id=scoped_cooperative_id,
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
            _insert_chunks(db, record_id=record.id, cooperative_id=scoped_cooperative_id, chunks=chunks, embeddings=embeddings)
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
        _insert_chunks(db, record_id=existing.id, cooperative_id=scoped_cooperative_id, chunks=chunks, embeddings=embeddings)
        existing.content_hash = payload_hash

        counters.documents_updated += 1
        counters.chunks_deleted += int(chunks_deleted)
        counters.chunks_created += len(chunks)

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
        "metadata": metadata,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _collect_source_documents(db: Session, cooperative_id: UUID) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    documents.extend(_member_documents(db, cooperative_id))
    documents.extend(_field_documents(db, cooperative_id))
    documents.extend(_input_documents(db, cooperative_id))
    documents.extend(_stock_documents(db, cooperative_id))
    documents.extend(_batch_documents(db, cooperative_id))
    documents.extend(_process_step_documents(db, cooperative_id))
    documents.extend(_farmer_advance_documents(db, cooperative_id))
    documents.extend(_treasury_documents(db, cooperative_id))
    documents.extend(_commercial_catalog_documents(db, cooperative_id))
    documents.extend(_commercial_order_documents(db, cooperative_id))
    documents.extend(_commercial_invoice_documents(db, cooperative_id))
    return documents


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
    documents: list[SourceDocument] = []
    for batch, product in rows:
        content = _build_content_block(
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
        documents.append(
            SourceDocument(
                source_table="batches",
                source_record_id=batch.id,
                source_record_ref=f"batch:{batch.id}",
                title=f"Lot {batch.code}",
                content=content,
                metadata={"entity": "batch", "batch_id": str(batch.id), "product_id": str(product.id), "batch_code": batch.code},
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
    documents: list[SourceDocument] = []
    for step, batch, product in rows:
        loss_kg = max(float(step.qty_in) - float(step.qty_out), 0.0)
        loss_pct = (loss_kg / float(step.qty_in) * 100.0) if step.qty_in else 0.0
        content = _build_content_block(
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
        documents.append(
            SourceDocument(
                source_table="process_steps",
                source_record_id=step.id,
                source_record_ref=f"process_step:{step.id}",
                title=f"Etape {step.type} - {batch.code}",
                content=content,
                metadata={
                    "entity": "process_step",
                    "process_step_id": str(step.id),
                    "batch_id": str(batch.id),
                    "product_id": str(product.id),
                    "batch_code": batch.code,
                },
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
        content = _build_content_block(
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
        documents.append(
            SourceDocument(
                source_table="commercial_orders",
                source_record_id=order.id,
                source_record_ref=f"commercial_order:{order.id}",
                title=f"Commande {order.order_number}",
                content=content,
                metadata={"entity": "commercial_order", "order_id": str(order.id), "order_number": order.order_number},
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
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    if len(chunks) != len(embeddings):
        raise ValidationError("Chunk/embedding count mismatch.")

    for idx, (content, vector) in enumerate(zip(chunks, embeddings)):
        db.add(
            RAGChunk(
                document_id=record_id,
                cooperative_id=cooperative_id,
                chunk_index=idx,
                content=content,
                embedding=_vector_literal(vector),
                metadata_json={"chunk_tokens_est": _estimate_token_count(content)},
            )
        )


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in vector) + "]"


def _estimate_token_count(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


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

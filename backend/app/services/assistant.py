from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.llm.provider import get_llm_client
from app.models.chat import ChatMessage, ChatSession
from app.models.cooperative import Cooperative
from app.models.enums import UserRole
from app.models.mixins import current_utc
from app.models.reference import KnowledgeChunk, ReferenceMetric
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
from app.services.helpers import round_metric
from app.services.rag_embeddings import embed_texts
from app.utils.exceptions import NotFoundError, ValidationError

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_\-']+")
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


@dataclass
class ReferenceContext:
    citations: list[ChatCitation]
    metrics: list[ChatMetricFact]


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


def list_chat_messages(db: Session, current_user: User, session_id: UUID, *, limit: int = 200) -> List[ChatMessageRead]:
    session = _require_owned_session(db, current_user, session_id)
    messages = db.scalars(
        select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at.asc()).limit(limit)
    ).all()
    return [_to_message_read(message) for message in messages]


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
    query_tokens = set(_tokenize(message))

    user_message = ChatMessage(session_id=session.id, role="user", content=message)
    db.add(user_message)
    db.flush()

    manager_snapshot = _build_dashboard_snapshot(db, current_user)
    cooperative = _get_cooperative(db, current_user)
    region_hint = cooperative.region if cooperative else manager_snapshot.region if manager_snapshot else None
    retrieval_hits: list[RetrievalHit] = []
    reference_context = ReferenceContext(citations=[], metrics=[])
    if response_mode != "quick":
        retrieval_hits = _retrieve_rag_hits(
            db,
            current_user=current_user,
            message=message,
            limit=min(max(top_k, 1), 8),
        )
        reference_context = _retrieve_reference_context(
            db,
            message=message,
            cooperative=cooperative,
            limit=min(max(top_k, 1), 8),
        )

    rag_citations = _citations_from_hits(retrieval_hits, cooperative=cooperative)
    citations = _dedupe_citations([*rag_citations, *reference_context.citations], limit=10)
    operational_metrics = _build_operational_context_metrics(
        db,
        current_user=current_user,
        query_tokens=query_tokens,
        region_hint=region_hint,
    )
    context_metrics = _build_context_metrics(
        manager_snapshot,
        region_hint=region_hint,
        rag_hit_count=len(retrieval_hits),
        reference_metrics=reference_context.metrics,
        operational_metrics=operational_metrics,
    )
    ui_blocks = _build_ui_blocks(db, current_user=current_user, message=message, dashboard=manager_snapshot)

    mode = "fallback"
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    answer = _build_fallback_answer(
        message,
        manager_snapshot,
        citations,
        response_mode=response_mode,
        language=response_language,
    )

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
        )
        if llm_answer:
            answer = llm_answer
            mode = "llm-rag" if citations else "llm"
            llm_provider = settings.llm_provider
            llm_model = settings.llm_model
    except ValidationError:
        pass

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
) -> Optional[str]:
    client = get_llm_client()
    style_guidance = _build_response_style_guidance(response_mode)
    language_instruction = "Reply in French." if language == "fr" else "Reply in English."

    prompt_messages = [
        {
            "role": "system",
            "content": (
                f"You are WeeFarm manager assistant. {language_instruction} "
                "Use only chat memory from this session and the provided context. "
                "Reference snippets are retrieved from the cooperative database. "
                "Do not invent numbers not present in the context. "
                "Follow the response style guidance exactly. "
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
                f"Response mode: {response_mode}\n"
                f"Language: {language}\n"
                f"Style guidance: {style_guidance}"
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
        if language == "fr":
            return "LLM indisponible. Reponse rapide: " + _solve_basic_math_or_echo(message)
        return "LLM unavailable. Quick answer: " + _solve_basic_math_or_echo(message)

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
            "I could not reach the LLM provider. "
            f"Current context: losses {dashboard.loss_rate:.1f}%, "
            f"efficiency {dashboard.efficiency_rate:.1f}%, production {dashboard.total_production:.1f} kg."
        )
    else:
        base = "I could not reach the LLM provider right now."

    if citations:
        reference = f"Available reference: {citations[0].source_id} ({citations[0].topic})."
    else:
        reference = "No RAG snippet is available."
    return f"{base} Request: {_trim_text(message, 180)}. {reference} Next step: validate the related lot data on the ground."


def _retrieve_rag_hits(
    db: Session,
    *,
    current_user: User,
    message: str,
    limit: int,
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
                d.source_table AS source_table,
                d.source_record_ref AS source_record_ref,
                d.metadata_json AS metadata_json,
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
            d.source_table AS source_table,
            d.source_record_ref AS source_record_ref,
            d.metadata_json AS metadata_json,
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
        metadata = row.get("metadata_json")
        metadata_map: dict[str, Any] = metadata if isinstance(metadata, dict) else {}
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
        metadata = row.get("metadata_json")
        metadata_map: dict[str, Any] = metadata if isinstance(metadata, dict) else {}
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

    return _rerank_hits(message=message, hits=list(merged.values()), limit=limit)


def _rerank_hits(*, message: str, hits: list[RetrievalHit], limit: int) -> list[RetrievalHit]:
    if not hits:
        return []

    # Reciprocal Rank Fusion over vector and keyword ranks.
    rrf_k = 60.0
    query_tokens = set(_tokenize(message))
    table_boosts = _infer_table_boosts(query_tokens)

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
        hit.rerank_score = fused + (0.32 * lexical_overlap) + (0.24 * distance_bonus) + table_boost

    hits.sort(key=lambda item: item.rerank_score, reverse=True)
    return hits[:limit]


def _infer_table_boosts(query_tokens: set[str]) -> dict[str, float]:
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
    return boosts


def _citations_from_hits(hits: Sequence[RetrievalHit], *, cooperative: Optional[Cooperative]) -> List[ChatCitation]:
    region = cooperative.region if cooperative else "cooperative"
    citations: list[ChatCitation] = []
    for hit in hits:
        metadata_map = hit.metadata
        topic = str(metadata_map.get("entity") or hit.source_table)
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
    return combined[:24]


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

    return metrics[:12]


def _build_ui_blocks(
    db: Session,
    *,
    current_user: User,
    message: str,
    dashboard: Optional[ChatDashboardSnapshot],
) -> List[ChatUIBlock]:
    blocks: list[ChatUIBlock] = []
    if dashboard:
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
    lowered = message.lower()
    words = set(token.lower() for token in TOKEN_PATTERN.findall(lowered))
    french_score = len(words & FRENCH_HINTS)
    english_score = len(words & ENGLISH_HINTS)
    has_french_accent = any(char in lowered for char in "àâçéèêëîïôùûüÿœ")

    if has_french_accent:
        return "fr"
    if english_score > french_score:
        return "en"
    if french_score > english_score:
        return "fr"
    return "fr"


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

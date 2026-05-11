from datetime import UTC, datetime, timedelta

from app.services.assistant import (
    RetrievalHit,
    _apply_retrieval_filters,
    _build_retrieval_filters,
    _build_scope_relaxed_filter_sequence,
    _normalize_hit_metadata,
    _rerank_hits,
    _should_disable_unfiltered_fallback,
    _summarize_retrieval_provenance,
)
from app.services.chat_retrieval_router import build_retrieval_plan


def _hit(
    *,
    chunk_id: str,
    source_table: str,
    content: str,
    metadata: dict,
    vector_rank: int = 1,
    keyword_rank: int = 1,
) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=chunk_id,
        source_table=source_table,
        source_record_ref=f"{source_table}:{chunk_id}",
        content=content,
        metadata=metadata,
        distance=0.25,
        keyword_score=0.5,
        vector_rank=vector_rank,
        keyword_rank=keyword_rank,
    )


def test_retrieval_filters_apply_stage_product_batch_and_chunk_type():
    message = "why are drying losses high this week for mango in LOT-MANG-004"
    plan = build_retrieval_plan(message)
    filters = _build_retrieval_filters(message=message, retrieval_plan=plan)

    fresh_ts = datetime.now(UTC).isoformat()
    matching = _hit(
        chunk_id="1",
        source_table="process_steps",
        content="Lot LOT-MANG-004 drying losses increased for mango.",
        metadata={
            "product_name": "mango",
            "stage": "drying",
            "stage_canonical": "drying",
            "chunk_type": "process_step_summary",
            "batch_code": "LOT-MANG-004",
            "freshness_timestamp": fresh_ts,
        },
    )
    non_matching = _hit(
        chunk_id="2",
        source_table="parcels",
        content="Parcel update for peanut",
        metadata={
            "product_name": "peanut",
            "chunk_type": "parcel_context",
            "freshness_timestamp": fresh_ts,
        },
    )
    filtered = _apply_retrieval_filters([matching, non_matching], retrieval_filters=filters)
    assert len(filtered) == 1
    assert filtered[0].chunk_id == "1"


def test_recent_chunks_score_higher_than_stale_for_operational_context():
    now = datetime.now(UTC)
    recent = _hit(
        chunk_id="recent",
        source_table="recommendations",
        content="Recommendation for drying anomaly and loss reduction.",
        metadata={
            "chunk_type": "recommendation_context",
            "freshness_timestamp": (now - timedelta(minutes=5)).isoformat(),
        },
        vector_rank=1,
        keyword_rank=1,
    )
    stale = _hit(
        chunk_id="stale",
        source_table="recommendations",
        content="Recommendation for drying anomaly and loss reduction.",
        metadata={
            "chunk_type": "recommendation_context",
            "freshness_timestamp": (now - timedelta(hours=8)).isoformat(),
        },
        vector_rank=1,
        keyword_rank=1,
    )
    ranked = _rerank_hits(message="why anomaly risk loss drying recommendation", hits=[stale, recent], limit=2)
    assert ranked[0].chunk_id == "recent"
    assert ranked[0].rerank_score > ranked[1].rerank_score


def test_batch_code_filtering_works():
    plan = build_retrieval_plan("what happened to LOT-MANG-004")
    filters = _build_retrieval_filters(message="what happened to LOT-MANG-004", retrieval_plan=plan)
    hits = [
        _hit(
            chunk_id="ok",
            source_table="batches",
            content="Lot LOT-MANG-004 had higher drying losses.",
            metadata={"chunk_type": "batch_summary", "batch_code": "LOT-MANG-004"},
        ),
        _hit(
            chunk_id="other",
            source_table="batches",
            content="Lot LOT-MANG-009 normal trend.",
            metadata={"chunk_type": "batch_summary", "batch_code": "LOT-MANG-009"},
        ),
    ]
    filtered = _apply_retrieval_filters(hits, retrieval_filters=filters)
    assert [item.chunk_id for item in filtered] == ["ok"]


def test_provenance_metadata_exists_for_ranked_hits():
    now = datetime.now(UTC).isoformat()
    hits = [
        _hit(
            chunk_id="1",
            source_table="ml_prediction_logs",
            content="Prediction indicates anomaly risk.",
            metadata={
                "chunk_type": "ml_prediction_context",
                "source_row_id": "row-1",
                "freshness_timestamp": now,
            },
        )
    ]
    ranked = _rerank_hits(message="anomaly risk", hits=hits, limit=1)
    provenance = _summarize_retrieval_provenance(ranked, limit=1)
    assert provenance
    row = provenance[0]
    assert "chunk_type" in row
    assert "source_table" in row
    assert "source_row_id" in row
    assert "freshness_timestamp" in row
    assert "retrieval_score" in row
    assert "retrieval_reason" in row


def test_retrieval_still_works_when_metadata_missing():
    bare = _hit(
        chunk_id="bare",
        source_table="batches",
        content="Generic batch summary text",
        metadata={},
    )
    ranked = _rerank_hits(message="batch summary", hits=[bare], limit=1)
    assert len(ranked) == 1


def test_normalize_hit_metadata_populates_chunk_type_and_freshness_from_fallbacks():
    now_iso = datetime.now(UTC).isoformat()
    normalized = _normalize_hit_metadata(
        source_table="process_steps",
        source_record_ref="process_step:legacy-1",
        metadata_raw='{"entity":"process_step"}',
        chunk_metadata_raw={},
        chunk_created_at=now_iso,
        document_last_synced_at=None,
    )
    assert normalized["chunk_type"] == "process_step_summary"
    assert normalized["freshness_timestamp"]
    assert normalized["source_row_id"] == "process_step:legacy-1"


def test_benchmark_query_prefers_reference_chunk_types_over_operational_chunks():
    now = datetime.now(UTC).isoformat()
    benchmark = _hit(
        chunk_id="bench",
        source_table="reference_metrics",
        content="Benchmark reference metric for millet drying losses.",
        metadata={"chunk_type": "benchmark_reference", "freshness_timestamp": now},
        vector_rank=2,
        keyword_rank=2,
    )
    operational = _hit(
        chunk_id="stock",
        source_table="stocks",
        content="Current stock details for millet.",
        metadata={"chunk_type": "stock", "freshness_timestamp": now},
        vector_rank=1,
        keyword_rank=1,
    )
    ranked = _rerank_hits(
        message="what does benchmark literature say about millet losses",
        hits=[operational, benchmark],
        limit=2,
    )
    assert ranked[0].chunk_id == "bench"


def test_disable_unfiltered_fallback_for_benchmark_filters():
    assert _should_disable_unfiltered_fallback({"chunk_type": {"benchmark_reference"}})
    assert _should_disable_unfiltered_fallback({"chunk_type": {"agronomic_knowledge"}})
    assert _should_disable_unfiltered_fallback({"source_table": {"reference_metrics"}})
    assert not _should_disable_unfiltered_fallback({"chunk_type": {"batch_summary"}})


def test_scope_reranking_penalizes_unrelated_product_chunks():
    now = datetime.now(UTC).isoformat()
    mango = _hit(
        chunk_id="mango",
        source_table="process_steps",
        content="Mango drying losses slightly increased.",
        metadata={"chunk_type": "process_step_summary", "product_name": "mango", "stage_canonical": "drying", "freshness_timestamp": now},
        vector_rank=2,
        keyword_rank=2,
    )
    bissap = _hit(
        chunk_id="bissap",
        source_table="process_steps",
        content="Bissap catastrophic losses in drying stage.",
        metadata={"chunk_type": "process_step_summary", "product_name": "bissap", "stage_canonical": "drying", "freshness_timestamp": now},
        vector_rank=1,
        keyword_rank=1,
    )
    ranked = _rerank_hits(message="why are mango drying losses high", hits=[bissap, mango], limit=2)
    assert ranked[0].chunk_id == "mango"


def test_scope_reranking_prioritizes_lot_specific_hits():
    now = datetime.now(UTC).isoformat()
    lot_target = _hit(
        chunk_id="lot-target",
        source_table="batches",
        content="Lot LOT-MANG-004 drying loss observed.",
        metadata={"chunk_type": "batch_summary", "batch_code": "LOT-MANG-004", "product_name": "mango", "freshness_timestamp": now},
        vector_rank=2,
        keyword_rank=2,
    )
    other_lot = _hit(
        chunk_id="lot-other",
        source_table="batches",
        content="Lot LOT-MANG-009 drying loss observed.",
        metadata={"chunk_type": "batch_summary", "batch_code": "LOT-MANG-009", "product_name": "mango", "freshness_timestamp": now},
        vector_rank=1,
        keyword_rank=1,
    )
    ranked = _rerank_hits(message="what happened to LOT-MANG-004", hits=[other_lot, lot_target], limit=2)
    assert ranked[0].chunk_id == "lot-target"


def test_product_stage_reranking_prioritizes_operational_chunk_over_benchmark():
    now = datetime.now(UTC).isoformat()
    operational = _hit(
        chunk_id="ops",
        source_table="process_steps",
        content="Mango drying stage loss increased this week.",
        metadata={
            "chunk_type": "product_stage_summary",
            "product_name": "mango",
            "stage_canonical": "drying",
            "freshness_timestamp": now,
        },
        vector_rank=2,
        keyword_rank=2,
    )
    benchmark = _hit(
        chunk_id="bench",
        source_table="reference_metrics",
        content="Benchmark reference for post-harvest losses.",
        metadata={"chunk_type": "benchmark_reference", "product_name": "mango", "freshness_timestamp": now},
        vector_rank=1,
        keyword_rank=1,
    )
    ranked = _rerank_hits(message="why are drying losses high this week for mango", hits=[benchmark, operational], limit=2)
    assert ranked[0].chunk_id == "ops"


def test_scope_relaxed_fallback_sequence_preserves_hierarchy():
    plan = build_retrieval_plan("why are drying losses high this week for mango")
    filters = _build_retrieval_filters(
        message="why are drying losses high this week for mango",
        retrieval_plan=plan,
    )
    variants = _build_scope_relaxed_filter_sequence(filters)
    assert len(variants) >= 3
    # First relax step keeps product and drops strict stage.
    assert variants[0]["product_name"] == {"mango"}
    assert variants[0]["stage"] == set()
    # Last step is benchmark/reference support.
    assert variants[-1]["chunk_type"] == {"benchmark_reference", "agronomic_knowledge"}
    assert variants[-1]["source_table"] == {"reference_metrics", "knowledge_chunks"}

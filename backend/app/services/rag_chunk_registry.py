from __future__ import annotations

from typing import Callable

from app.services.rag_context_builders import (
    build_anomaly_summary_chunk,
    build_batch_summary_chunk,
    build_benchmark_reference_chunk,
    build_commercial_order_chunk,
    build_global_charge_chunk,
    build_agronomic_knowledge_chunk,
    build_ml_prediction_chunk,
    build_ml_training_run_chunk,
    build_parcel_chunk,
    build_pre_harvest_chunk,
    build_process_step_chunk,
    build_recommendation_chunk,
)


SemanticChunkBuilder = Callable[..., dict]


_REGISTRY: dict[str, SemanticChunkBuilder] = {
    "batches": build_batch_summary_chunk,
    "process_steps": build_process_step_chunk,
    "recommendations": build_recommendation_chunk,
    "parcels": build_parcel_chunk,
    "pre_harvest_steps": build_pre_harvest_chunk,
    "ml_prediction_logs": build_ml_prediction_chunk,
    "ml_training_runs": build_ml_training_run_chunk,
    "commercial_orders": build_commercial_order_chunk,
    "global_charges": build_global_charge_chunk,
    "recommendation_feedback_logs": build_anomaly_summary_chunk,
    "knowledge_chunks": build_agronomic_knowledge_chunk,
    "reference_metrics": build_benchmark_reference_chunk,
}


def get_chunk_builder(source_table: str) -> SemanticChunkBuilder | None:
    return _REGISTRY.get(source_table)


def get_registered_source_tables() -> list[str]:
    return sorted(_REGISTRY.keys())

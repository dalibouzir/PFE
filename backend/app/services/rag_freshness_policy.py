from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RefreshMode(str, Enum):
    ON_CREATE_UPDATE = "ON_CREATE_UPDATE"
    SCHEDULED_DAILY = "SCHEDULED_DAILY"
    SCHEDULED_WEEKLY = "SCHEDULED_WEEKLY"
    MANUAL_ONLY = "MANUAL_ONLY"
    NEVER = "NEVER"


@dataclass(frozen=True)
class FreshnessPolicy:
    chunk_type: str
    refresh_mode: RefreshMode
    max_age_minutes: int | None
    reindex_priority: int
    requires_realtime: bool
    source_tables: tuple[str, ...]


_POLICIES: dict[str, FreshnessPolicy] = {
    "batch_summary": FreshnessPolicy(
        chunk_type="batch_summary",
        refresh_mode=RefreshMode.ON_CREATE_UPDATE,
        max_age_minutes=60,
        reindex_priority=1,
        requires_realtime=True,
        source_tables=("batches",),
    ),
    "process_step_summary": FreshnessPolicy(
        chunk_type="process_step_summary",
        refresh_mode=RefreshMode.ON_CREATE_UPDATE,
        max_age_minutes=30,
        reindex_priority=1,
        requires_realtime=True,
        source_tables=("process_steps",),
    ),
    "recommendation_context": FreshnessPolicy(
        chunk_type="recommendation_context",
        refresh_mode=RefreshMode.ON_CREATE_UPDATE,
        max_age_minutes=30,
        reindex_priority=1,
        requires_realtime=True,
        source_tables=("recommendations", "ml_recommendation_logs"),
    ),
    "anomaly_summary": FreshnessPolicy(
        chunk_type="anomaly_summary",
        refresh_mode=RefreshMode.ON_CREATE_UPDATE,
        max_age_minutes=15,
        reindex_priority=1,
        requires_realtime=True,
        source_tables=("recommendation_feedback_logs", "ml_prediction_logs"),
    ),
    "parcel_context": FreshnessPolicy(
        chunk_type="parcel_context",
        refresh_mode=RefreshMode.SCHEDULED_DAILY,
        max_age_minutes=24 * 60,
        reindex_priority=2,
        requires_realtime=False,
        source_tables=("parcels",),
    ),
    "pre_harvest_context": FreshnessPolicy(
        chunk_type="pre_harvest_context",
        refresh_mode=RefreshMode.ON_CREATE_UPDATE,
        max_age_minutes=120,
        reindex_priority=1,
        requires_realtime=True,
        source_tables=("pre_harvest_steps",),
    ),
    "commercial_context": FreshnessPolicy(
        chunk_type="commercial_context",
        refresh_mode=RefreshMode.ON_CREATE_UPDATE,
        max_age_minutes=60,
        reindex_priority=1,
        requires_realtime=True,
        source_tables=("commercial_orders", "commercial_invoices"),
    ),
    "ml_prediction_context": FreshnessPolicy(
        chunk_type="ml_prediction_context",
        refresh_mode=RefreshMode.ON_CREATE_UPDATE,
        max_age_minutes=30,
        reindex_priority=1,
        requires_realtime=True,
        source_tables=("ml_prediction_logs",),
    ),
    "ml_training_context": FreshnessPolicy(
        chunk_type="ml_training_context",
        refresh_mode=RefreshMode.MANUAL_ONLY,
        max_age_minutes=7 * 24 * 60,
        reindex_priority=4,
        requires_realtime=False,
        source_tables=("ml_training_runs", "ml_model_registry"),
    ),
    "ml_evaluation_context": FreshnessPolicy(
        chunk_type="ml_evaluation_context",
        refresh_mode=RefreshMode.MANUAL_ONLY,
        max_age_minutes=7 * 24 * 60,
        reindex_priority=4,
        requires_realtime=False,
        source_tables=("ml_training_runs", "ml_model_registry"),
    ),
    "benchmark_reference": FreshnessPolicy(
        chunk_type="benchmark_reference",
        refresh_mode=RefreshMode.SCHEDULED_WEEKLY,
        max_age_minutes=7 * 24 * 60,
        reindex_priority=3,
        requires_realtime=False,
        source_tables=("reference_metrics",),
    ),
    "agronomic_knowledge": FreshnessPolicy(
        chunk_type="agronomic_knowledge",
        refresh_mode=RefreshMode.MANUAL_ONLY,
        max_age_minutes=14 * 24 * 60,
        reindex_priority=4,
        requires_realtime=False,
        source_tables=("knowledge_chunks",),
    ),
}


_DEFAULT_POLICY = FreshnessPolicy(
    chunk_type="default",
    refresh_mode=RefreshMode.MANUAL_ONLY,
    max_age_minutes=None,
    reindex_priority=5,
    requires_realtime=False,
    source_tables=(),
)


def get_freshness_policy(chunk_type: str) -> FreshnessPolicy:
    return _POLICIES.get(chunk_type, _DEFAULT_POLICY)


def get_all_freshness_policies() -> dict[str, FreshnessPolicy]:
    return dict(_POLICIES)

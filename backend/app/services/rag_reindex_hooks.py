from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.rag_indexer import ReindexCounters, reindex_targeted_sources


def _safe_targeted_reindex(
    db: Session,
    *,
    current_user: User,
    targets: list[tuple[str, str | None]],
    cooperative_id: Optional[UUID] = None,
) -> ReindexCounters:
    try:
        return reindex_targeted_sources(
            db,
            current_user=current_user,
            cooperative_id=cooperative_id,
            targets=targets,
            force=False,
        )
    except Exception:
        # Keep operational flows resilient; indexing failures must not break core transactions.
        return ReindexCounters()


def reindex_batch_if_needed(
    db: Session,
    *,
    current_user: User,
    batch_id: UUID,
    cooperative_id: UUID,
) -> ReindexCounters:
    targets = [
        ("batches", f"batch:{batch_id}"),
        ("recommendations", None),
        ("process_steps", None),
    ]
    return _safe_targeted_reindex(db, current_user=current_user, cooperative_id=cooperative_id, targets=targets)


def reindex_process_step_if_needed(
    db: Session,
    *,
    current_user: User,
    process_step_id: UUID,
    batch_id: UUID,
    cooperative_id: UUID,
) -> ReindexCounters:
    targets = [
        ("process_steps", f"process_step:{process_step_id}"),
        ("batches", f"batch:{batch_id}"),
        ("recommendations", None),
    ]
    return _safe_targeted_reindex(db, current_user=current_user, cooperative_id=cooperative_id, targets=targets)


def reindex_recommendation_if_needed(
    db: Session,
    *,
    current_user: User,
    batch_id: UUID,
    cooperative_id: UUID,
) -> ReindexCounters:
    targets = [
        ("recommendations", None),
        ("batches", f"batch:{batch_id}"),
    ]
    return _safe_targeted_reindex(db, current_user=current_user, cooperative_id=cooperative_id, targets=targets)


def reindex_parcel_if_needed(
    db: Session,
    *,
    current_user: User,
    parcel_id: UUID,
    cooperative_id: UUID,
    pre_harvest_step_id: UUID | None = None,
) -> ReindexCounters:
    targets: list[tuple[str, str | None]] = [("parcels", f"parcel:{parcel_id}"), ("pre_harvest_steps", None)]
    if pre_harvest_step_id:
        targets.append(("pre_harvest_steps", f"pre_harvest_step:{pre_harvest_step_id}"))
    return _safe_targeted_reindex(db, current_user=current_user, cooperative_id=cooperative_id, targets=targets)


def reindex_ml_prediction_if_needed(
    db: Session,
    *,
    current_user: User,
    prediction_log_id: UUID | None,
    batch_id: UUID | None,
    cooperative_id: UUID | None,
) -> ReindexCounters:
    targets: list[tuple[str, str | None]] = [("ml_prediction_logs", None), ("recommendation_feedback_logs", None)]
    if prediction_log_id:
        targets.append(("ml_prediction_logs", f"ml_prediction:{prediction_log_id}"))
    if batch_id:
        targets.append(("batches", f"batch:{batch_id}"))
    return _safe_targeted_reindex(db, current_user=current_user, cooperative_id=cooperative_id, targets=targets)


def reindex_commercial_if_needed(
    db: Session,
    *,
    current_user: User,
    cooperative_id: UUID,
    order_id: UUID | None = None,
    invoice_id: UUID | None = None,
) -> ReindexCounters:
    targets: list[tuple[str, str | None]] = [("commercial_orders", None), ("commercial_invoices", None)]
    if order_id:
        targets.append(("commercial_orders", f"commercial_order:{order_id}"))
    if invoice_id:
        targets.append(("commercial_invoices", f"commercial_invoice:{invoice_id}"))
    return _safe_targeted_reindex(db, current_user=current_user, cooperative_id=cooperative_id, targets=targets)

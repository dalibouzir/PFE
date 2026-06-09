from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.batch import Batch


@dataclass(frozen=True)
class ResolvedLot:
    batch: Batch
    requested_ref: str

    @property
    def batch_id(self):
        return self.batch.id

    @property
    def canonical_ref(self) -> str:
        return str(self.batch.code)


def resolve_lot_reference(db: Session, cooperative_id, lot_ref: str | None) -> ResolvedLot | None:
    requested = str(lot_ref or "").strip()
    if not requested:
        return None
    needle = requested.upper()
    batch = db.scalar(
        select(Batch).where(
            Batch.cooperative_id == cooperative_id,
            or_(
                func.upper(Batch.code) == needle,
                func.upper(func.coalesce(Batch.postharvest_reference, "")) == needle,
            ),
        )
    )
    if batch is None:
        return None
    return ResolvedLot(batch=batch, requested_ref=requested)

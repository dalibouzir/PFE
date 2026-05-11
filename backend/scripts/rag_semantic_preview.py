from __future__ import annotations

from pathlib import Path
import sys

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.models.batch import Batch
from app.models.commercial_order import CommercialOrder
from app.models.global_charge import GlobalCharge
from app.models.ml import MLPredictionLog, MLTrainingRun
from app.models.parcel import Parcel
from app.models.pre_harvest_step import PreHarvestStep
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.services.rag_context_builders import (
    build_batch_summary_chunk,
    build_commercial_order_chunk,
    build_global_charge_chunk,
    build_ml_prediction_chunk,
    build_ml_training_run_chunk,
    build_parcel_chunk,
    build_pre_harvest_chunk,
    build_process_step_chunk,
    build_recommendation_chunk,
)


def _print_preview(name: str, payload: dict) -> None:
    print(f"\n=== {name} ===")
    print("chunk_type:", payload.get("metadata", {}).get("chunk_type"))
    print("content:", str(payload.get("content", ""))[:320])
    print("metadata:", payload.get("metadata", {}))


def main() -> None:
    db = SessionLocal()
    try:
        batch_row = db.execute(select(Batch, Product).join(Product, Product.id == Batch.product_id).limit(1)).first()
        if batch_row:
            batch, product = batch_row
            steps = db.scalars(
                select(ProcessStep).where(ProcessStep.batch_id == batch.id).order_by(ProcessStep.sequence_order.asc())
            ).all()
            recommendation = db.scalar(select(Recommendation).where(Recommendation.batch_id == batch.id))
            _print_preview(
                "batch_summary",
                build_batch_summary_chunk(
                    batch=batch,
                    product=product,
                    process_steps=steps,
                    recommendation=recommendation,
                    cooperative_id=batch.cooperative_id,
                ),
            )
            if steps:
                _print_preview(
                    "process_step_summary",
                    build_process_step_chunk(step=steps[0], batch=batch, product=product, cooperative_id=batch.cooperative_id),
                )
            if recommendation:
                _print_preview(
                    "recommendation_context",
                    build_recommendation_chunk(
                        recommendation=recommendation,
                        batch=batch,
                        product=product,
                        cooperative_id=batch.cooperative_id,
                    ),
                )

        parcel_row = db.scalar(select(Parcel).limit(1))
        if parcel_row:
            recent_steps = db.scalars(
                select(PreHarvestStep)
                .where(PreHarvestStep.parcel_id == parcel_row.id)
                .order_by(PreHarvestStep.created_at.desc())
                .limit(3)
            ).all()
            _print_preview(
                "parcel_context",
                build_parcel_chunk(
                    parcel=parcel_row,
                    member=parcel_row.member,
                    recent_preharvest_steps=recent_steps,
                    cooperative_id=parcel_row.cooperative_id,
                ),
            )
            if recent_steps:
                _print_preview(
                    "pre_harvest_context",
                    build_pre_harvest_chunk(
                        step=recent_steps[0],
                        parcel=parcel_row,
                        member=parcel_row.member,
                        cooperative_id=parcel_row.cooperative_id,
                    ),
                )

        prediction = db.scalar(select(MLPredictionLog).limit(1))
        if prediction:
            batch = db.scalar(select(Batch).where(Batch.id == prediction.batch_id)) if prediction.batch_id else None
            coop_id = batch.cooperative_id if batch else db.scalar(select(Batch.cooperative_id).limit(1))
            if coop_id:
                _print_preview(
                    "ml_prediction_context",
                    build_ml_prediction_chunk(prediction=prediction, batch=batch, cooperative_id=coop_id),
                )

        run = db.scalar(select(MLTrainingRun).limit(1))
        if run:
            coop_id = db.scalar(select(Batch.cooperative_id).limit(1))
            if coop_id:
                _print_preview("ml_evaluation_context", build_ml_training_run_chunk(run=run, cooperative_id=coop_id))

        order = db.scalar(select(CommercialOrder).limit(1))
        if order:
            _print_preview("commercial_context", build_commercial_order_chunk(order=order, cooperative_id=order.cooperative_id))

        charge = db.scalar(select(GlobalCharge).limit(1))
        if charge:
            _print_preview(
                "cost_context",
                build_global_charge_chunk(
                    charge=charge,
                    member=charge.member,
                    parcel=charge.parcel,
                    step=charge.pre_harvest_step,
                    cooperative_id=charge.cooperative_id,
                ),
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()

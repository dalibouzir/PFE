from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.batch import Batch
from app.models.enums import ProcessStepStatus, RiskLevel, UserRole
from app.models.input import Input
from app.models.process_step import ProcessStep
from app.models.recommendation import Recommendation
from app.models.stock import Stock
from app.models.user import User
from app.schemas.analytics import AnomalyResponse, DashboardResponse, RecommendationResponse
from app.schemas.batch import BatchMetricsSummary
from app.schemas.input import InputRead
from app.schemas.process_step import ProcessStepRead
from app.services.helpers import get_manager_cooperative_id, round_metric
from app.services.stocks import list_low_stock_alerts
from app.utils.exceptions import NotFoundError


COMPLETED_STEP_STATUSES = (ProcessStepStatus.COMPLETED, ProcessStepStatus.FLAGGED)
LONG_DURATION_THRESHOLD_MINUTES = 8 * 60


def get_batch_for_user(db: Session, user: User, batch_id) -> Batch:
    stmt = (
        select(Batch)
        .options(
            selectinload(Batch.process_steps),
            selectinload(Batch.product),
            selectinload(Batch.recommendation),
        )
        .where(Batch.id == batch_id)
    )
    if user.role != UserRole.ADMIN:
        stmt = stmt.where(Batch.cooperative_id == get_manager_cooperative_id(user))
    batch = db.scalar(stmt)
    if batch is None:
        raise NotFoundError("Batch not found.")
    return batch


def compute_process_metrics(process_step: ProcessStep):
    waste_qty = process_step.waste_qty
    if waste_qty is None:
        waste_qty = max(process_step.qty_in - process_step.qty_out, 0.0)
    loss_pct = ((process_step.qty_in - process_step.qty_out) / process_step.qty_in) * 100.0
    efficiency_pct = (process_step.qty_out / process_step.qty_in) * 100.0
    warning = process_step.qty_out > process_step.qty_in
    return {
        "waste_qty": round_metric(waste_qty),
        "loss_pct": round_metric(loss_pct),
        "efficiency_pct": round_metric(efficiency_pct),
        "warning": warning,
    }


def serialize_process_step(process_step: ProcessStep) -> ProcessStepRead:
    metrics = compute_process_metrics(process_step)
    return ProcessStepRead(
        id=process_step.id,
        batch_id=process_step.batch_id,
        type=process_step.type,
        date=process_step.date,
        qty_in=round_metric(process_step.qty_in),
        qty_out=round_metric(process_step.qty_out),
        waste_qty=metrics["waste_qty"],
        notes=process_step.notes,
        status=process_step.status.value,
        duration_minutes=process_step.duration_minutes,
        created_at=process_step.created_at,
        updated_at=process_step.updated_at,
        loss_pct=metrics["loss_pct"],
        efficiency_pct=metrics["efficiency_pct"],
        warning=metrics["warning"],
    )


def compute_batch_metrics(db: Session, batch_id) -> BatchMetricsSummary:
    batch = db.scalar(
        select(Batch)
        .options(selectinload(Batch.process_steps))
        .where(Batch.id == batch_id)
    )
    if batch is None:
        raise NotFoundError("Batch not found.")

    completed_steps = [
        step for step in sorted(batch.process_steps, key=lambda item: (item.date, item.created_at, item.id))
        if step.status in COMPLETED_STEP_STATUSES
    ]
    latest_completed = completed_steps[-1] if completed_steps else None
    total_input = completed_steps[0].qty_in if completed_steps else batch.initial_qty
    final_output = latest_completed.qty_out if latest_completed else batch.current_qty
    total_loss_pct = ((batch.initial_qty - batch.current_qty) / batch.initial_qty) * 100.0
    total_efficiency_pct = (batch.current_qty / batch.initial_qty) * 100.0

    return BatchMetricsSummary(
        batch_id=batch.id,
        total_input=round_metric(total_input),
        final_output=round_metric(final_output),
        total_loss_pct=round_metric(total_loss_pct),
        total_efficiency_pct=round_metric(total_efficiency_pct),
        completed_steps=len(completed_steps),
        latest_step_id=latest_completed.id if latest_completed else None,
    )


def detect_anomaly(db: Session, batch_id) -> AnomalyResponse:
    batch = db.scalar(
        select(Batch)
        .options(selectinload(Batch.process_steps))
        .where(Batch.id == batch_id)
    )
    if batch is None:
        raise NotFoundError("Batch not found.")

    metrics = compute_batch_metrics(db, batch_id)
    reasons = []
    score = 0.0

    if metrics.total_loss_pct > settings.anomaly_loss_threshold:
        reasons.append(
            f"Batch loss {metrics.total_loss_pct}% exceeds threshold {settings.anomaly_loss_threshold}%."
        )
        score += min(45.0, metrics.total_loss_pct - settings.anomaly_loss_threshold + 20.0)

    max_step_loss = 0.0
    for step in batch.process_steps:
        step_metrics = compute_process_metrics(step)
        max_step_loss = max(max_step_loss, step_metrics["loss_pct"])
        if step_metrics["loss_pct"] > settings.step_loss_threshold:
            reasons.append(
                f"Step '{step.type}' loss {step_metrics['loss_pct']}% exceeds threshold {settings.step_loss_threshold}%."
            )
            score += min(35.0, step_metrics["loss_pct"] - settings.step_loss_threshold + 10.0)
        if step.duration_minutes and step.duration_minutes > LONG_DURATION_THRESHOLD_MINUTES:
            reasons.append(
                f"Step '{step.type}' duration {step.duration_minutes} minutes exceeds {LONG_DURATION_THRESHOLD_MINUTES} minutes."
            )
            score += min(20.0, (step.duration_minutes - LONG_DURATION_THRESHOLD_MINUTES) / 20.0)

    unique_reasons = list(dict.fromkeys(reasons))
    anomaly_score = round_metric(min(score, 100.0))
    return AnomalyResponse(
        batch_id=batch.id,
        anomaly_detected=anomaly_score > 0,
        anomaly_score=anomaly_score,
        reasons=unique_reasons,
    )


def _recommendation_payload_for_batch(db: Session, batch: Batch):
    metrics = compute_batch_metrics(db, batch.id)
    anomaly = detect_anomaly(db, batch.id)
    actions = []
    rationale_bits = []

    for step in batch.process_steps:
        step_metrics = compute_process_metrics(step)
        step_type = step.type.lower()
        if "dry" in step_type and step_metrics["loss_pct"] > settings.step_loss_threshold:
            actions.append("Review drying duration, tray exposure, and humidity control.")
            rationale_bits.append("Drying losses are above the configured step threshold.")
        if "clean" in step_type and step_metrics["loss_pct"] > settings.step_loss_threshold:
            actions.append("Inspect cleaning calibration and reduce aggressive sorting.")
            rationale_bits.append("Cleaning waste indicates potential calibration drift.")
        if "sort" in step_type and step_metrics["efficiency_pct"] < 85:
            actions.append("Revisit sorting criteria and raw material grading before processing.")
            rationale_bits.append("Sorting efficiency is lower than expected.")
        if "pack" in step_type and step.duration_minutes and step.duration_minutes > LONG_DURATION_THRESHOLD_MINUTES:
            actions.append("Check packaging workflow pacing and operator handoff times.")
            rationale_bits.append("Packaging duration is slower than baseline.")

    if metrics.total_efficiency_pct < 85:
        actions.append("Audit the full stage sequence and review raw material quality grade.")
        rationale_bits.append("Overall batch efficiency is below 85%.")

    low_stock = db.scalars(
        select(Stock).where(Stock.cooperative_id == batch.cooperative_id, Stock.quantity < Stock.threshold)
    ).all()
    if low_stock:
        actions.append("Reorder or collect more inputs for products below stock threshold.")
        rationale_bits.append("Current stock alerts indicate replenishment risk.")

    if not actions:
        actions.append("Process indicators are stable. Keep weekly monitoring active.")
        rationale_bits.append("Loss and efficiency remain within configured thresholds.")

    risk_level = RiskLevel.LOW
    if anomaly.anomaly_score >= 70:
        risk_level = RiskLevel.HIGH
    elif anomaly.anomaly_score >= 30:
        risk_level = RiskLevel.MEDIUM

    return {
        "batch_id": batch.id,
        "loss_pct": metrics.total_loss_pct,
        "efficiency_pct": metrics.total_efficiency_pct,
        "anomaly_detected": anomaly.anomaly_detected,
        "anomaly_score": anomaly.anomaly_score,
        "risk_level": risk_level,
        "suggested_action": " ".join(dict.fromkeys(actions)),
        "rationale": " ".join(dict.fromkeys(rationale_bits + anomaly.reasons)),
        "reasons": anomaly.reasons,
    }


def generate_recommendation(db: Session, batch_id) -> RecommendationResponse:
    batch = db.scalar(
        select(Batch)
        .options(selectinload(Batch.process_steps), selectinload(Batch.recommendation))
        .where(Batch.id == batch_id)
    )
    if batch is None:
        raise NotFoundError("Batch not found.")

    payload = _recommendation_payload_for_batch(db, batch)
    recommendation = batch.recommendation
    if recommendation is None:
        recommendation = db.scalar(select(Recommendation).where(Recommendation.batch_id == batch.id))
    if recommendation is None:
        recommendation = Recommendation(
            batch_id=batch.id,
            loss_pct=payload["loss_pct"],
            efficiency_pct=payload["efficiency_pct"],
            anomaly_score=payload["anomaly_score"],
            risk_level=payload["risk_level"],
            suggested_action=payload["suggested_action"],
            rationale=payload["rationale"],
        )
        db.add(recommendation)
        batch.recommendation = recommendation
    else:
        recommendation.loss_pct = payload["loss_pct"]
        recommendation.efficiency_pct = payload["efficiency_pct"]
        recommendation.anomaly_score = payload["anomaly_score"]
        recommendation.risk_level = payload["risk_level"]
        recommendation.suggested_action = payload["suggested_action"]
        recommendation.rationale = payload["rationale"]
    db.flush()

    return RecommendationResponse(
        batch_id=batch.id,
        loss_pct=payload["loss_pct"],
        efficiency_pct=payload["efficiency_pct"],
        anomaly_detected=payload["anomaly_detected"],
        anomaly_score=payload["anomaly_score"],
        risk_level=payload["risk_level"].value,
        suggested_action=payload["suggested_action"],
        rationale=payload["rationale"],
        reasons=payload["reasons"],
    )


def get_dashboard(db: Session, manager: User) -> DashboardResponse:
    cooperative_id = get_manager_cooperative_id(manager)
    batches = db.scalars(
        select(Batch)
        .options(selectinload(Batch.process_steps))
        .where(Batch.cooperative_id == cooperative_id)
        .order_by(Batch.creation_date.desc())
    ).all()

    total_initial = sum(batch.initial_qty for batch in batches) or 0.0
    total_current = sum(batch.current_qty for batch in batches) or 0.0
    total_production = round_metric(total_current)
    loss_rate = round_metric(((total_initial - total_current) / total_initial) * 100.0) if total_initial else 0.0
    efficiency_rate = round_metric((total_current / total_initial) * 100.0) if total_initial else 0.0
    active_batches = len([batch for batch in batches if batch.status.value in ("created", "in_progress")])

    recent_inputs = db.scalars(
        select(Input)
        .where(Input.cooperative_id == cooperative_id)
        .order_by(Input.date.desc(), Input.created_at.desc())
        .limit(5)
    ).all()

    recent_steps = db.scalars(
        select(ProcessStep)
        .join(Batch, Batch.id == ProcessStep.batch_id)
        .where(Batch.cooperative_id == cooperative_id)
        .order_by(ProcessStep.date.desc(), ProcessStep.created_at.desc())
        .limit(5)
    ).all()

    recent_recommendation_rows = db.scalars(
        select(Recommendation)
        .join(Batch, Batch.id == Recommendation.batch_id)
        .where(Batch.cooperative_id == cooperative_id)
        .order_by(Recommendation.created_at.desc())
        .limit(5)
    ).all()

    recent_recommendations = [generate_recommendation(db, row.batch_id) for row in recent_recommendation_rows]

    return DashboardResponse(
        total_production=total_production,
        loss_rate=loss_rate,
        efficiency_rate=efficiency_rate,
        number_of_active_batches=active_batches,
        stock_alerts=list_low_stock_alerts(db, cooperative_id),
        recent_inputs=[InputRead.model_validate(item) for item in recent_inputs],
        recent_process_steps=[serialize_process_step(step) for step in recent_steps],
        recent_recommendations=recent_recommendations,
    )

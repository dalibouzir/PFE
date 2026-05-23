from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Optional
from uuid import UUID

from app.ml.utils.stage_normalization import normalize_stage
from app.models.batch import Batch
from app.models.commercial_order import CommercialOrder
from app.models.global_charge import GlobalCharge
from app.models.member import Member
from app.models.ml import MLPredictionLog, MLRecommendationLog, MLTrainingRun, RecommendationFeedbackLog
from app.models.parcel import Parcel
from app.models.pre_harvest_step import PreHarvestStep
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.reference import KnowledgeChunk, ReferenceMetric
from app.models.recommendation import Recommendation


REQUIRED_METADATA_KEYS = {"chunk_type", "source_table", "source_row_id", "cooperative_id", "freshness_timestamp"}
OPTIONAL_METADATA_KEYS = {
    "product_name",
    "product_id",
    "batch_id",
    "process_step_id",
    "stage",
    "stage_canonical",
    "member_id",
    "parcel_id",
    "season",
    "risk_level",
    "loss_pct",
    "efficiency_pct",
    "anomaly_flag",
    "commercial_order_id",
    "ml_model_version",
    "recommendation_type",
    "access_level",
    "country",
    "region",
    "topic",
    "metric_name",
    "metric_value",
    "period",
    "source_id",
    "source_url",
    "batch_code",
    "scope_level",
    "applies_to_query",
    "scope_product",
    "scope_stage",
    "scope_lot",
}


def validate_chunk_metadata(metadata: dict[str, Any]) -> bool:
    if not isinstance(metadata, dict):
        return False
    for key in REQUIRED_METADATA_KEYS:
        value = metadata.get(key)
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
    for key in ("chunk_type", "source_table", "source_row_id", "cooperative_id"):
        if not isinstance(metadata.get(key), str):
            return False
    allowed_keys = REQUIRED_METADATA_KEYS | OPTIONAL_METADATA_KEYS
    if any(key not in allowed_keys for key in metadata):
        return False
    return True


def build_batch_summary_chunk(
    *,
    batch: Batch,
    product: Optional[Product],
    process_steps: Iterable[ProcessStep],
    recommendation: Optional[Recommendation],
    cooperative_id: UUID,
) -> dict[str, Any]:
    steps = list(process_steps)
    total_loss_kg = max(float(batch.initial_qty) - float(batch.current_qty), 0.0)
    total_loss_pct = (total_loss_kg / float(batch.initial_qty) * 100.0) if batch.initial_qty else 0.0
    stage_names = ", ".join(step.type for step in steps) if steps else "no recorded steps"
    worst_step = _find_worst_step(steps)
    risk_level = _risk_label(
        recommendation.risk_level.value if recommendation and recommendation.risk_level else None,
        total_loss_pct=total_loss_pct,
        anomaly_score=recommendation.anomaly_score if recommendation else None,
    )

    product_name = product.name if product else "unknown product"
    summary_parts = [
        (
            f"Lot {batch.code} processed {round(batch.initial_qty, 2)} {batch.unit} of {product_name} "
            f"through {stage_names}."
        ),
        (
            f"Current quantity is {round(batch.current_qty, 2)} {batch.unit}, representing a total loss of "
            f"{round(total_loss_pct, 2)}% ({round(total_loss_kg, 2)} {batch.unit})."
        ),
    ]
    if worst_step:
        summary_parts.append(
            f"The largest stage loss occurred during {worst_step['stage']} at {round(worst_step['loss_pct'], 2)}%."
        )
    if recommendation:
        summary_parts.append(
            f"Operational risk was assessed as {risk_level} with suggested action: {recommendation.suggested_action}."
        )
    else:
        summary_parts.append(f"Operational risk is currently estimated as {risk_level} based on available losses.")

    metadata = _base_metadata(
        chunk_type="batch_summary",
        source_table="batches",
        source_row_id=batch.id,
        cooperative_id=cooperative_id,
        product_name=product_name,
        product_id=product.id if product else None,
        batch_id=batch.id,
        risk_level=risk_level,
        loss_pct=round(total_loss_pct, 2),
        efficiency_pct=round(max(0.0, 100.0 - total_loss_pct), 2),
        access_level="cooperative_internal",
    )
    return _chunk(summary_parts, metadata)


def build_process_step_chunk(
    *,
    step: ProcessStep,
    batch: Optional[Batch],
    product: Optional[Product],
    cooperative_id: UUID,
) -> dict[str, Any]:
    loss_kg = max(float(step.qty_in) - float(step.qty_out), 0.0)
    loss_pct = (loss_kg / float(step.qty_in) * 100.0) if step.qty_in else 0.0
    stage_canonical = normalize_stage(step.type)
    product_name = product.name if product else "unknown product"
    batch_code = batch.code if batch else "unknown lot"
    content = (
        f"Process step {step.type} for lot {batch_code} ({product_name}) transformed "
        f"{round(step.qty_in, 2)} kg into {round(step.qty_out, 2)} kg, with a loss of "
        f"{round(loss_kg, 2)} kg ({round(loss_pct, 2)}%). "
        f"The step status is {_enum_value(step.status)} and duration is {step.duration_minutes or 'not recorded'} minutes."
    )
    metadata = _base_metadata(
        chunk_type="process_step_summary",
        source_table="process_steps",
        source_row_id=step.id,
        cooperative_id=cooperative_id,
        product_name=product_name,
        product_id=product.id if product else None,
        batch_id=batch.id if batch else None,
        process_step_id=step.id,
        stage=step.type,
        stage_canonical=stage_canonical,
        loss_pct=round(loss_pct, 2),
        efficiency_pct=round(max(0.0, 100.0 - loss_pct), 2),
        access_level="cooperative_internal",
    )
    return _chunk([content], metadata)


def build_product_stage_summary_chunk(
    *,
    step: ProcessStep,
    batch: Optional[Batch],
    product: Optional[Product],
    cooperative_id: UUID,
    product_stage_avg_loss_pct: Optional[float] = None,
    cooperative_stage_avg_loss_pct: Optional[float] = None,
) -> dict[str, Any]:
    loss_kg = max(float(step.qty_in) - float(step.qty_out), 0.0)
    loss_pct = (loss_kg / float(step.qty_in) * 100.0) if step.qty_in else 0.0
    stage_canonical = normalize_stage(step.type)
    product_name = product.name if product else "unknown product"
    batch_code = batch.code if batch else "unknown lot"

    parts = [
        (
            f"For product {product_name} at stage {step.type}, lot {batch_code} processed "
            f"{round(step.qty_in, 2)} kg into {round(step.qty_out, 2)} kg with {round(loss_pct, 2)}% loss "
            f"and {round(max(0.0, 100.0 - loss_pct), 2)}% efficiency."
        )
    ]
    if product_stage_avg_loss_pct is not None:
        parts.append(
            f"Recent product-stage average loss is {round(product_stage_avg_loss_pct, 2)}%."
        )
    if cooperative_stage_avg_loss_pct is not None:
        parts.append(
            f"Cooperative-wide stage average is {round(cooperative_stage_avg_loss_pct, 2)}%, "
            "which can include unrelated products."
        )

    metadata = _base_metadata(
        chunk_type="product_stage_summary",
        source_table="process_steps",
        source_row_id=step.id,
        cooperative_id=cooperative_id,
        product_name=product_name,
        product_id=product.id if product else None,
        batch_id=batch.id if batch else None,
        batch_code=batch_code,
        process_step_id=step.id,
        stage=step.type,
        stage_canonical=stage_canonical,
        loss_pct=round(loss_pct, 2),
        efficiency_pct=round(max(0.0, 100.0 - loss_pct), 2),
        scope_level="PRODUCT_STAGE",
        applies_to_query=True,
        access_level="cooperative_internal",
    )
    return _chunk(parts, metadata)


def build_lot_status_summary_chunk(
    *,
    batch: Batch,
    product: Optional[Product],
    process_steps: Iterable[ProcessStep],
    recommendation: Optional[Recommendation],
    cooperative_id: UUID,
) -> dict[str, Any]:
    steps = list(process_steps)
    product_name = product.name if product else "unknown product"
    total_loss_kg = max(float(batch.initial_qty) - float(batch.current_qty), 0.0)
    total_loss_pct = (total_loss_kg / float(batch.initial_qty) * 100.0) if batch.initial_qty else 0.0
    risk = _risk_label(
        recommendation.risk_level.value if recommendation and recommendation.risk_level else None,
        total_loss_pct=total_loss_pct,
        anomaly_score=recommendation.anomaly_score if recommendation else None,
    )

    step_fragments: list[str] = []
    for step in sorted(steps, key=lambda value: value.sequence_order):
        step_loss = _step_loss_pct(step)
        step_fragments.append(f"{step.type} {round(step_loss, 2)}% loss")
    step_text = ", ".join(step_fragments) if step_fragments else "No completed process steps yet"

    content = (
        f"Lot {batch.code} is {str(batch.status.value if hasattr(batch.status, 'value') else batch.status).lower()} for {product_name}. "
        f"Initial quantity is {round(batch.initial_qty, 2)} {batch.unit}, current quantity is {round(batch.current_qty, 2)} {batch.unit}. "
        f"Completed steps: {step_text}. Cumulative loss is {round(total_loss_pct, 2)}% "
        f"({round(total_loss_kg, 2)} {batch.unit}) and operational risk is {risk}."
    )
    metadata = _base_metadata(
        chunk_type="lot_status_summary",
        source_table="batches",
        source_row_id=batch.id,
        cooperative_id=cooperative_id,
        product_name=product_name,
        product_id=product.id if product else None,
        batch_id=batch.id,
        batch_code=batch.code,
        risk_level=risk,
        loss_pct=round(total_loss_pct, 2),
        efficiency_pct=round(max(0.0, 100.0 - total_loss_pct), 2),
        scope_level="LOT",
        applies_to_query=True,
        access_level="cooperative_internal",
    )
    return _chunk([content], metadata)


def build_lot_recommendation_summary_chunk(
    *,
    recommendation: Recommendation,
    batch: Optional[Batch],
    product: Optional[Product],
    cooperative_id: UUID,
) -> dict[str, Any]:
    product_name = product.name if product else "unknown product"
    batch_code = batch.code if batch else "unknown lot"
    content = (
        f"Lot-specific recommendation for {batch_code} ({product_name}) was created because loss reached "
        f"{round(recommendation.loss_pct, 2)}% and efficiency dropped to {round(recommendation.efficiency_pct, 2)}%. "
        f"Risk is {_enum_value(recommendation.risk_level).upper()} and anomaly score is {round(recommendation.anomaly_score, 3)}. "
        f"Suggested action: {recommendation.suggested_action}. Rationale: {recommendation.rationale}"
    )
    metadata = _base_metadata(
        chunk_type="lot_recommendation_summary",
        source_table="recommendations",
        source_row_id=recommendation.id,
        cooperative_id=cooperative_id,
        product_name=product_name,
        product_id=product.id if product else None,
        batch_id=batch.id if batch else None,
        batch_code=batch_code,
        risk_level=_enum_value(recommendation.risk_level).upper(),
        loss_pct=round(recommendation.loss_pct, 2),
        efficiency_pct=round(recommendation.efficiency_pct, 2),
        anomaly_flag=recommendation.anomaly_score >= 0.5,
        recommendation_type="lot_specific_mitigation",
        scope_level="LOT",
        applies_to_query=True,
        access_level="cooperative_internal",
    )
    return _chunk([content], metadata)


def build_operational_risk_summary_chunk(
    *,
    batch: Batch,
    product: Optional[Product],
    process_steps: Iterable[ProcessStep],
    recommendation: Optional[Recommendation],
    prediction: Optional[MLPredictionLog],
    cooperative_id: UUID,
) -> dict[str, Any]:
    steps = list(process_steps)
    product_name = product.name if product else "unknown product"
    total_loss_kg = max(float(batch.initial_qty) - float(batch.current_qty), 0.0)
    total_loss_pct = (total_loss_kg / float(batch.initial_qty) * 100.0) if batch.initial_qty else 0.0
    worst_step = _find_worst_step(steps)

    risk = _risk_label(
        recommendation.risk_level.value if recommendation and recommendation.risk_level else None,
        total_loss_pct=total_loss_pct,
        anomaly_score=(prediction.anomaly_score if prediction else None) or (recommendation.anomaly_score if recommendation else None),
    )
    parts = [
        (
            f"Operational risk summary for lot {batch.code} ({product_name}): cumulative loss is "
            f"{round(total_loss_pct, 2)}% with risk classified as {risk}."
        )
    ]
    if worst_step:
        parts.append(
            f"Most sensitive stage is {worst_step['stage']} at {round(worst_step['loss_pct'], 2)}% loss."
        )
    if prediction is not None:
        parts.append(
            f"ML predicted {round(prediction.predicted_loss_pct or 0.0, 2)}% loss and anomaly score "
            f"{round(prediction.anomaly_score or 0.0, 3)}."
        )
    if recommendation is not None:
        parts.append(f"Recommended mitigation: {recommendation.suggested_action}.")

    metadata = _base_metadata(
        chunk_type="operational_risk_summary",
        source_table="batches",
        source_row_id=batch.id,
        cooperative_id=cooperative_id,
        product_name=product_name,
        product_id=product.id if product else None,
        batch_id=batch.id,
        batch_code=batch.code,
        stage=worst_step["stage"] if worst_step else None,
        stage_canonical=normalize_stage(worst_step["stage"]) if worst_step else None,
        risk_level=risk,
        loss_pct=round(total_loss_pct, 2),
        efficiency_pct=round(max(0.0, 100.0 - total_loss_pct), 2),
        anomaly_flag=bool((prediction and prediction.is_anomalous) or (recommendation and recommendation.anomaly_score >= 0.5)),
        scope_level="PRODUCT_STAGE" if worst_step else "PRODUCT",
        applies_to_query=True,
        access_level="cooperative_internal",
    )
    return _chunk(parts, metadata)


def build_scoped_loss_summary_chunk(
    *,
    source_row_id: Any,
    cooperative_id: UUID,
    product_name: str,
    stage: str,
    stage_canonical: Optional[str],
    product_stage_loss_pct: float,
    cooperative_loss_pct: float,
    unrelated_product_name: Optional[str] = None,
    unrelated_product_loss_pct: Optional[float] = None,
) -> dict[str, Any]:
    parts = [
        (
            f"{product_name} at stage {stage} shows {round(product_stage_loss_pct, 2)}% loss, while "
            f"cooperative-wide average is {round(cooperative_loss_pct, 2)}%."
        )
    ]
    if unrelated_product_name and unrelated_product_loss_pct is not None:
        parts.append(
            f"The cooperative average is affected by unrelated product signals such as {unrelated_product_name} "
            f"({round(unrelated_product_loss_pct, 2)}% loss). Do not treat this as direct {product_name} evidence."
        )
    else:
        parts.append("Cooperative-wide averages can include unrelated products and should be interpreted as supporting context.")

    metadata = _base_metadata(
        chunk_type="scoped_loss_summary",
        source_table="process_steps",
        source_row_id=source_row_id,
        cooperative_id=cooperative_id,
        product_name=product_name,
        stage=stage,
        stage_canonical=stage_canonical or normalize_stage(stage),
        loss_pct=round(product_stage_loss_pct, 2),
        scope_level="PRODUCT_STAGE",
        applies_to_query=True,
        access_level="cooperative_internal",
    )
    return _chunk(parts, metadata)


def build_recommendation_chunk(
    *,
    recommendation: Recommendation,
    batch: Optional[Batch],
    product: Optional[Product],
    cooperative_id: UUID,
) -> dict[str, Any]:
    batch_code = batch.code if batch else "unknown lot"
    product_name = product.name if product else "unknown product"
    content = (
        f"A recommendation was generated for lot {batch_code} ({product_name}) after losses reached "
        f"{round(recommendation.loss_pct, 2)}% and efficiency dropped to {round(recommendation.efficiency_pct, 2)}%. "
        f"Risk level is {_enum_value(recommendation.risk_level).upper()}. "
        f"Suggested action: {recommendation.suggested_action}. "
        f"Rationale: {recommendation.rationale}"
    )
    metadata = _base_metadata(
        chunk_type="recommendation_context",
        source_table="recommendations",
        source_row_id=recommendation.id,
        cooperative_id=cooperative_id,
        product_name=product_name,
        product_id=product.id if product else None,
        batch_id=batch.id if batch else None,
        risk_level=_enum_value(recommendation.risk_level).upper(),
        loss_pct=round(recommendation.loss_pct, 2),
        efficiency_pct=round(recommendation.efficiency_pct, 2),
        anomaly_flag=recommendation.anomaly_score >= 0.5,
        recommendation_type="batch_loss_mitigation",
        access_level="cooperative_internal",
    )
    return _chunk([content], metadata)


def build_parcel_chunk(
    *,
    parcel: Parcel,
    member: Optional[Member],
    recent_preharvest_steps: Iterable[PreHarvestStep],
    cooperative_id: UUID,
) -> dict[str, Any]:
    recent = list(recent_preharvest_steps)
    member_name = member.full_name if member else "unknown member"
    latest_step = recent[0] if recent else None
    parts = [
        (
            f"Parcel {parcel.name} managed by {member_name} covers {round(parcel.surface_ha, 2)} hectares and is "
            f"primarily dedicated to {parcel.main_culture}{f' ({parcel.variety})' if parcel.variety else ''}."
        )
    ]
    if parcel.tree_count:
        parts.append(f"The parcel has approximately {parcel.tree_count} productive trees.")
    if latest_step:
        parts.append(
            f"Latest pre-harvest monitoring step is {latest_step.label} with status {_enum_value(latest_step.status)}."
        )
    metadata = _base_metadata(
        chunk_type="parcel_context",
        source_table="parcels",
        source_row_id=parcel.id,
        cooperative_id=cooperative_id,
        product_name=parcel.main_culture,
        member_id=parcel.member_id,
        parcel_id=parcel.id,
        access_level="cooperative_internal",
    )
    return _chunk(parts, metadata)


def build_pre_harvest_chunk(
    *,
    step: PreHarvestStep,
    parcel: Optional[Parcel],
    member: Optional[Member],
    cooperative_id: UUID,
) -> dict[str, Any]:
    parcel_name = parcel.name if parcel else "unknown parcel"
    member_name = member.full_name if member else "unknown member"
    operation_cost = f"{round(step.operation_cost_fcfa, 2)} FCFA" if step.operation_cost_fcfa is not None else "not recorded"
    content = (
        f"Pre-harvest step {step.label} ({step.category}) for parcel {parcel_name} under member {member_name} "
        f"is currently {_enum_value(step.status)}. Quantity is {step.quantity_value or 'not recorded'} "
        f"{step.quantity_unit or ''}. Operation cost is {operation_cost}. "
        f"Observation: {step.observations or 'none'}."
    )
    metadata = _base_metadata(
        chunk_type="pre_harvest_context",
        source_table="pre_harvest_steps",
        source_row_id=step.id,
        cooperative_id=cooperative_id,
        member_id=step.member_id,
        parcel_id=step.parcel_id,
        season=_derive_season(step.realization_date),
        access_level="cooperative_internal",
    )
    return _chunk([content], metadata)


def build_ml_prediction_chunk(
    *,
    prediction: MLPredictionLog,
    batch: Optional[Batch],
    cooperative_id: UUID,
) -> dict[str, Any]:
    batch_code = batch.code if batch else "unknown lot"
    risk_level = _enum_value(prediction.risk_level).upper() if prediction.risk_level else _risk_label(
        None,
        total_loss_pct=prediction.predicted_loss_pct or 0.0,
        anomaly_score=prediction.anomaly_score,
    )
    content = (
        f"The ML system predicted outcomes for lot {batch_code} (model {prediction.model_version}): "
        f"expected loss {round(prediction.predicted_loss_pct or 0.0, 2)}%, expected efficiency "
        f"{round(prediction.expected_efficiency_pct or 0.0, 2)}%, and risk {risk_level}. "
        f"Critical stage identified: {prediction.critical_stage or 'not specified'}. "
        f"Anomaly flag is {'true' if prediction.is_anomalous else 'false'}."
    )
    metadata = _base_metadata(
        chunk_type="ml_prediction_context",
        source_table="ml_prediction_logs",
        source_row_id=prediction.id,
        cooperative_id=cooperative_id,
        product_name=prediction.product,
        batch_id=prediction.batch_id,
        stage=prediction.critical_stage,
        stage_canonical=normalize_stage(prediction.critical_stage),
        risk_level=risk_level,
        loss_pct=round(prediction.predicted_loss_pct or 0.0, 2),
        efficiency_pct=round(prediction.expected_efficiency_pct or 0.0, 2),
        anomaly_flag=bool(prediction.is_anomalous),
        ml_model_version=prediction.model_version,
        access_level="cooperative_internal",
    )
    return _chunk([content], metadata)


def build_ml_training_run_chunk(*, run: MLTrainingRun, cooperative_id: UUID) -> dict[str, Any]:
    metrics = run.metrics if isinstance(run.metrics, dict) else {}
    metric_summary = ", ".join(f"{k}={v}" for k, v in list(metrics.items())[:4]) or "no metrics recorded"
    content = (
        f"ML training run {run.run_name} completed with status {run.status}. "
        f"Dataset size was {run.dataset_rows} rows. "
        f"Key metrics: {metric_summary}."
    )
    metadata = _base_metadata(
        chunk_type="ml_evaluation_context",
        source_table="ml_training_runs",
        source_row_id=run.id,
        cooperative_id=cooperative_id,
        ml_model_version=str(metrics.get("model_version") or "unknown"),
        access_level="cooperative_internal",
    )
    return _chunk([content], metadata)


def build_commercial_order_chunk(*, order: CommercialOrder, cooperative_id: UUID) -> dict[str, Any]:
    lines = [
        f"{line.product_name_snapshot} ({line.quantity} {line.unit_snapshot})"
        for line in order.lines
    ]
    content = (
        f"Commercial order {order.order_number} from source {order.source} is currently {_enum_value(order.status)}. "
        f"Subtotal is {round(order.subtotal_fcfa, 2)} FCFA and total is {round(order.total_amount_fcfa, 2)} FCFA. "
        f"Main lines: {', '.join(lines) if lines else 'none'}."
    )
    metadata = _base_metadata(
        chunk_type="commercial_context",
        source_table="commercial_orders",
        source_row_id=order.id,
        cooperative_id=cooperative_id,
        commercial_order_id=order.id,
        access_level="cooperative_internal",
    )
    return _chunk([content], metadata)


def build_global_charge_chunk(
    *,
    charge: GlobalCharge,
    member: Optional[Member],
    parcel: Optional[Parcel],
    step: Optional[PreHarvestStep],
    cooperative_id: UUID,
) -> dict[str, Any]:
    member_name = member.full_name if member else "unknown member"
    parcel_name = parcel.name if parcel else "not linked"
    step_label = step.label if step else "not linked"
    content = (
        f"Global charge {charge.label} ({charge.charge_type}) recorded {round(charge.amount_fcfa, 2)} FCFA "
        f"on {charge.date.isoformat()} for member {member_name}. "
        f"Parcel link: {parcel_name}. Pre-harvest step link: {step_label}. "
        f"Source type is {charge.source_type}. Notes: {charge.notes or 'none'}."
    )
    metadata = _base_metadata(
        chunk_type="cost_context",
        source_table="global_charges",
        source_row_id=charge.id,
        cooperative_id=cooperative_id,
        member_id=charge.member_id,
        parcel_id=charge.parcel_id,
        batch_id=charge.batch_id,
        process_step_id=charge.process_step_id,
        season=_derive_season(charge.date),
        access_level="cooperative_internal",
    )
    return _chunk([content], metadata)


def build_anomaly_summary_chunk(
    *,
    feedback: Optional[RecommendationFeedbackLog],
    prediction: Optional[MLPredictionLog],
    recommendation_log: Optional[MLRecommendationLog],
    cooperative_id: UUID,
) -> dict[str, Any]:
    batch_id = feedback.batch_id if feedback else (prediction.batch_id if prediction else None)
    stage = feedback.stage if feedback else (prediction.critical_stage if prediction else None)
    anomaly_flag = bool(prediction.is_anomalous) if prediction is not None else False
    risk_hint = _enum_value(prediction.risk_level).upper() if prediction and prediction.risk_level else "MEDIUM"
    parts = []
    if prediction is not None:
        parts.append(
            f"ML anomaly context detected for batch {prediction.batch_id or 'unknown'} with anomaly score "
            f"{round(prediction.anomaly_score or 0.0, 3)} and predicted loss {round(prediction.predicted_loss_pct or 0.0, 2)}%."
        )
    if feedback is not None:
        parts.append(
            f"Operational feedback indicates recommendation {'accepted' if feedback.accepted else 'not accepted'} and "
            f"{'executed' if feedback.executed else 'not executed'}, with delta loss "
            f"{round(feedback.delta_loss or 0.0, 2)}."
        )
        if feedback.comment:
            parts.append(f"Operator comment: {feedback.comment}")
    if recommendation_log is not None and recommendation_log.llm_explanation:
        parts.append(f"Associated recommendation explanation: {recommendation_log.llm_explanation}")
    if not parts:
        parts.append("Anomaly summary created from limited data with no detailed feedback available.")

    metadata = _base_metadata(
        chunk_type="anomaly_summary",
        source_table="recommendation_feedback_logs" if feedback is not None else "ml_prediction_logs",
        source_row_id=feedback.id if feedback is not None else (prediction.id if prediction is not None else "unknown"),
        cooperative_id=cooperative_id,
        batch_id=batch_id,
        stage=stage,
        stage_canonical=normalize_stage(stage),
        risk_level=risk_hint,
        anomaly_flag=anomaly_flag or (feedback.manual_review_required if feedback else False),
        ml_model_version=(feedback.model_version if feedback else None) or (prediction.model_version if prediction else None),
        access_level="cooperative_internal",
    )
    return _chunk(parts, metadata)


def build_agronomic_knowledge_chunk(
    *,
    chunk: KnowledgeChunk,
    cooperative_id: UUID,
) -> dict[str, Any]:
    content = (
        f"Référence post-récolte pour {chunk.crop} ({chunk.region}, {chunk.country}). "
        f"Thème: {chunk.topic}. {chunk.content}"
    )
    metadata = _base_metadata(
        chunk_type="agronomic_knowledge",
        source_table="knowledge_chunks",
        source_row_id=chunk.id,
        cooperative_id=cooperative_id,
        product_name=chunk.crop,
        country=chunk.country,
        region=chunk.region,
        topic=chunk.topic,
        source_id=chunk.source_id,
        source_url=chunk.source_url,
        access_level="reference_public",
    )
    return _chunk([content], metadata)


def build_benchmark_reference_chunk(
    *,
    metric: ReferenceMetric,
    cooperative_id: UUID,
) -> dict[str, Any]:
    content = (
        f"Benchmark reference metric for {metric.crop} in {metric.region}, {metric.country}: "
        f"{metric.metric} is {round(metric.value, 3)} {metric.unit} for period {metric.period}. "
        f"Source: {metric.source_id}. {metric.notes or ''}".strip()
    )
    metadata = _base_metadata(
        chunk_type="benchmark_reference",
        source_table="reference_metrics",
        source_row_id=metric.id,
        cooperative_id=cooperative_id,
        product_name=metric.crop,
        country=metric.country,
        region=metric.region,
        topic=metric.metric,
        metric_name=metric.metric,
        metric_value=round(metric.value, 4),
        period=metric.period,
        source_id=metric.source_id,
        access_level="reference_public",
    )
    return _chunk([content], metadata)


def _chunk(parts: list[str], metadata: dict[str, Any]) -> dict[str, Any]:
    content = " ".join(part.strip() for part in parts if part and part.strip()).strip()
    if not content:
        content = "No operational context available."
    cleaned = _clean_metadata(metadata)
    if not validate_chunk_metadata(cleaned):
        raise ValueError("Invalid chunk metadata generated.")
    return {"content": content, "metadata": cleaned}


def _base_metadata(
    *,
    chunk_type: str,
    source_table: str,
    source_row_id: Any,
    cooperative_id: UUID,
    **optional: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "chunk_type": chunk_type,
        "source_table": source_table,
        "source_row_id": str(source_row_id),
        "cooperative_id": str(cooperative_id),
        "freshness_timestamp": datetime.now(UTC).isoformat(),
    }
    for key, value in optional.items():
        if value is None:
            continue
        if key in {"product_id", "batch_id", "process_step_id", "member_id", "parcel_id", "commercial_order_id"}:
            payload[key] = str(value)
            continue
        payload[key] = value
    return payload


def _find_worst_step(steps: Iterable[ProcessStep]) -> Optional[dict[str, Any]]:
    worst_stage: Optional[dict[str, Any]] = None
    for step in steps:
        loss_kg = max(float(step.qty_in) - float(step.qty_out), 0.0)
        loss_pct = (loss_kg / float(step.qty_in) * 100.0) if step.qty_in else 0.0
        if worst_stage is None or loss_pct > worst_stage["loss_pct"]:
            worst_stage = {"stage": step.type, "loss_pct": loss_pct}
    return worst_stage


def _step_loss_pct(step: ProcessStep) -> float:
    loss_kg = max(float(step.qty_in) - float(step.qty_out), 0.0)
    return (loss_kg / float(step.qty_in) * 100.0) if step.qty_in else 0.0


def _risk_label(level: Optional[str], *, total_loss_pct: float, anomaly_score: Optional[float]) -> str:
    if level:
        return level.upper()
    if anomaly_score is not None and anomaly_score >= 0.7:
        return "HIGH"
    if total_loss_pct >= 15.0:
        return "HIGH"
    if total_loss_pct >= 8.0:
        return "MEDIUM"
    return "LOW"


def _enum_value(value: Any) -> str:
    if value is None:
        return "unknown"
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _derive_season(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "month"):
        month = int(value.month)
        if month in {12, 1, 2}:
            return "dry_season"
        if month in {6, 7, 8, 9}:
            return "rainy_season"
        return "transition_season"
    return None


def _clean_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, float):
            cleaned[key] = round(value, 4)
            continue
        cleaned[key] = value
    return cleaned
UTC = timezone.utc

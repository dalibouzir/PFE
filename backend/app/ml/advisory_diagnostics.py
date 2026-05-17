from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

from app.ml.utils.stage_normalization import normalize_stage


ML_STRATEGY = "enhanced_advisory_v1"
BENCHMARK_SOURCE = "synthetic_offline_selected_strategy"
ADVISORY_CAVEAT = (
    "Ce signal est une aide à la décision basée sur une stratégie ML/analytique validée sur benchmark synthétique. "
    "Les décisions opérationnelles doivent rester confirmées par les données réelles de la coopérative."
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        out = float(value)
    except (TypeError, ValueError):
        return default
    if out != out:  # NaN
        return default
    return out


def _stage_from_row(row: Mapping[str, Any]) -> str:
    stage = row.get("critical_stage") or row.get("process_type") or row.get("stage") or row.get("stage_canonical")
    return normalize_stage(str(stage or "unknown"))


def _product_from_row(row: Mapping[str, Any]) -> str:
    return str(row.get("product") or "unknown").strip().lower()


def estimate_loss_with_stage_baseline(feature_row: Mapping[str, Any]) -> Dict[str, Any]:
    candidate_sources = [
        ("product_stage_season_avg_loss", "product_stage_season_mean_loss"),
        ("stage_season_avg_loss", "stage_season_mean_loss"),
        ("product_stage_historical_avg_loss", "product_stage_mean_loss"),
        ("historical_avg_loss_same_stage", "stage_mean_loss"),
        ("historical_avg_loss_same_product", "product_mean_loss"),
        ("rolling_loss_last_n_batches", "rolling_product_loss"),
        ("previous_batch_loss", "previous_batch_loss"),
    ]
    evidences: list[tuple[str, float]] = []
    for key, baseline_type in candidate_sources:
        value = feature_row.get(key)
        if value is None:
            continue
        numeric = _safe_float(value, default=-1.0)
        if numeric < 0:
            continue
        evidences.append((baseline_type, numeric))

    if evidences:
        baseline_type, estimate = evidences[0]
    else:
        baseline_type, estimate = "global_safe_default", 8.0

    evidence_count = len(evidences)
    if evidence_count >= 3:
        confidence = "high"
    elif evidence_count >= 1:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "estimate_loss_pct": round(float(estimate), 4),
        "baseline_type": baseline_type,
        "evidence_count": int(evidence_count),
        "confidence_label": confidence,
    }


def compute_critical_risk_advisory(
    feature_row: Mapping[str, Any],
    *,
    baseline_estimate: Optional[Mapping[str, Any]] = None,
    predicted_loss_pct: Optional[float] = None,
    observed_loss_pct: Optional[float] = None,
) -> Dict[str, Any]:
    baseline_payload = baseline_estimate or estimate_loss_with_stage_baseline(feature_row)
    base_loss = _safe_float(
        observed_loss_pct if observed_loss_pct is not None else predicted_loss_pct,
        default=_safe_float(baseline_payload.get("estimate_loss_pct"), default=8.0),
    )

    stage = _stage_from_row(feature_row)
    product = _product_from_row(feature_row)
    grade = str(feature_row.get("grade") or "B").strip().upper()
    humidity = _safe_float(feature_row.get("humidity"), 0.0)
    rainfall = _safe_float(feature_row.get("rainfall"), 0.0)
    dew_point = _safe_float(feature_row.get("dew_point"), 0.0)
    duration = _safe_float(feature_row.get("step_duration_minutes"), 0.0)
    delay = _safe_float(feature_row.get("delay_since_previous_step_minutes"), 0.0)

    stage_weight = {"drying": 2.2, "packaging": 1.3, "sorting": 1.0, "cleaning": 1.0}.get(stage, 1.0)
    product_weight = {"mangue": 1.4, "arachide": 1.4, "mil": 1.1, "mango": 1.4, "peanut": 1.4}.get(product, 1.0)
    grade_weight = {"C": 1.3, "B": 1.0, "A": 0.9}.get(grade, 1.0)

    humidity_risk = max((humidity - 70.0) / 20.0, 0.0)
    rainfall_risk = max((rainfall - 3.0) / 8.0, 0.0)
    dew_risk = max((dew_point - 20.0) / 8.0, 0.0)
    duration_risk = max((duration - 180.0) / 180.0, 0.0)
    delay_risk = max((delay - 120.0) / 180.0, 0.0)

    risk_score = (
        0.16 * base_loss
        + stage_weight
        + 0.8 * product_weight
        + 0.5 * grade_weight
        + 1.2 * humidity_risk
        + 1.0 * rainfall_risk
        + 0.8 * dew_risk
        + 1.0 * duration_risk
        + 0.8 * delay_risk
    )

    advisory_flags: list[str] = []
    if base_loss >= 18.0:
        risk_level = "high"
    elif base_loss >= 8.0:
        risk_level = "medium"
    else:
        risk_level = "low"

    drying_weather_extreme = stage == "drying" and (humidity >= 80.0 or rainfall >= 8.0 or dew_point >= 24.0)
    if drying_weather_extreme:
        advisory_flags.append("drying_weather_extreme")
    if duration >= 210:
        advisory_flags.append("step_duration_extreme")
    if delay >= 180:
        advisory_flags.append("step_delay_extreme")
    if grade == "C":
        advisory_flags.append("low_grade_risk")

    if risk_level != "high" and (risk_score >= 5.3 or drying_weather_extreme):
        risk_level = "high"
        advisory_flags.append("severity_override_high")
    elif risk_level == "low" and risk_score >= 3.4:
        risk_level = "medium"
        advisory_flags.append("severity_override_medium")

    return {
        "risk_level": risk_level,
        "risk_score": round(float(risk_score), 4),
        "advisory_flags": advisory_flags,
        "caveat": ADVISORY_CAVEAT,
    }


def detect_assessment_anomalies(
    feature_row: Mapping[str, Any],
    *,
    historical_context: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    ctx = dict(historical_context or {})
    stage = _stage_from_row(feature_row)
    product = _product_from_row(feature_row)
    qty_in = _safe_float(feature_row.get("qty_in"), 0.0)
    qty_out = _safe_float(feature_row.get("qty_out"), 0.0)
    loss_qty = _safe_float(feature_row.get("loss_qty"), max(qty_in - qty_out, 0.0))
    loss_pct = _safe_float(feature_row.get("loss_pct"), 0.0)
    efficiency_pct = _safe_float(feature_row.get("efficiency_pct"), 0.0)
    duration = _safe_float(feature_row.get("step_duration_minutes"), 0.0)
    delay = _safe_float(feature_row.get("delay_since_previous_step_minutes"), 0.0)
    humidity = _safe_float(feature_row.get("humidity"), 0.0)
    rainfall = _safe_float(feature_row.get("rainfall"), 0.0)
    dew_point = _safe_float(feature_row.get("dew_point"), 0.0)

    stage_thresholds = ctx.get(
        "stage_loss_thresholds",
        {"drying": 18.0, "sorting": 14.0, "cleaning": 12.0, "packaging": 10.0, "unknown": 15.0},
    )
    ps_bounds = ctx.get("product_stage_bounds", {})
    ps_key = f"{product}|{stage}"
    ps_bound = ps_bounds.get(ps_key) or {}
    ps_upper = _safe_float(ps_bound.get("upper"), stage_thresholds.get(stage, 15.0) + 3.0)
    duration_threshold = _safe_float(ctx.get("duration_threshold"), 210.0)
    delay_threshold = _safe_float(ctx.get("delay_threshold"), 180.0)

    flags: Dict[str, bool] = {
        "invalid_quantity_balance": qty_out > qty_in or qty_in <= 0 or qty_out < 0,
        "extreme_loss_by_stage": loss_pct >= _safe_float(stage_thresholds.get(stage, 15.0), 15.0),
        "product_stage_outlier": loss_pct >= ps_upper,
        "duration_delay_extreme": duration >= duration_threshold or delay >= delay_threshold,
        "weather_stage_high_loss": stage == "drying"
        and loss_pct >= _safe_float(stage_thresholds.get("drying", 18.0), 18.0)
        and (humidity >= 80.0 or rainfall >= 8.0 or dew_point >= 24.0),
        "unexpected_packaging_loss": stage == "packaging" and loss_pct >= 10.0,
        "efficiency_drop": efficiency_pct <= 0.72,
    }

    severity = (
        2.0 * int(flags["invalid_quantity_balance"])
        + 1.5 * int(flags["extreme_loss_by_stage"])
        + 1.2 * int(flags["product_stage_outlier"])
        + 1.0 * int(flags["duration_delay_extreme"])
        + 1.0 * int(flags["weather_stage_high_loss"])
        + 1.0 * int(flags["unexpected_packaging_loss"])
        + 0.8 * int(flags["efficiency_drop"])
    )
    severity_label = "high" if severity >= 3.0 else "medium" if severity >= 1.5 else "low"

    active = [name for name, enabled in flags.items() if enabled]
    is_anomalous = bool(active)
    explanation = (
        "No anomaly rule triggered."
        if not active
        else " | ".join(active)
    )

    return {
        "is_anomalous": is_anomalous,
        "anomaly_flags": active,
        "severity": round(float(severity), 4),
        "severity_label": severity_label,
        "evidence": {
            "stage": stage,
            "product": product,
            "qty_in": qty_in,
            "qty_out": qty_out,
            "loss_qty": loss_qty,
            "loss_pct": loss_pct,
            "efficiency_pct": efficiency_pct,
            "step_duration_minutes": duration,
            "delay_since_previous_step_minutes": delay,
            "humidity": humidity,
            "rainfall": rainfall,
            "dew_point": dew_point,
        },
        "explanation": explanation,
    }


def rank_rule_recommendations(
    recommendations: Sequence[str],
    *,
    feature_row: Mapping[str, Any],
    critical_risk_advisory: Optional[Mapping[str, Any]] = None,
    anomaly_diagnostics: Optional[Mapping[str, Any]] = None,
    mode: str = "predictive",
) -> list[Dict[str, Any]]:
    recs = [str(item) for item in recommendations if str(item).strip()]
    if not recs:
        return []

    stage = _stage_from_row(feature_row)
    loss_pct = _safe_float(feature_row.get("loss_pct"), _safe_float(feature_row.get("predicted_loss_pct"), 0.0))
    humidity = _safe_float(feature_row.get("humidity"), 0.0)
    rainfall = _safe_float(feature_row.get("rainfall"), 0.0)
    dew_point = _safe_float(feature_row.get("dew_point"), 0.0)
    duration = _safe_float(feature_row.get("step_duration_minutes"), 0.0)
    delay = _safe_float(feature_row.get("delay_since_previous_step_minutes"), 0.0)
    evidence_quality = 1.0 - (0.35 if int(_safe_float(feature_row.get("missing_duration_flag"), 0.0)) == 1 else 0.0)
    stage_priority = {"drying": 1.0, "sorting": 0.8, "cleaning": 0.7, "packaging": 0.75}.get(stage, 0.6)

    risk_payload = dict(critical_risk_advisory or {})
    risk_score = _safe_float(risk_payload.get("risk_score"), 0.0)
    risk_level = str(risk_payload.get("risk_level") or "low").strip().lower()
    anomaly_payload = dict(anomaly_diagnostics or {})
    anomaly_score = _safe_float(anomaly_payload.get("severity"), 0.0)
    weather_duration_risk = (
        max((humidity - 70.0) / 20.0, 0.0)
        + max((rainfall - 3.0) / 8.0, 0.0)
        + max((dew_point - 20.0) / 8.0, 0.0)
        + max((duration - 180.0) / 180.0, 0.0)
        + max((delay - 120.0) / 180.0, 0.0)
    )
    loss_severity = max((loss_pct - 8.0) / 10.0, 0.0)
    confidence_penalty = 0.25 if mode == "predictive" else 0.10

    def _score_for_action(action: str) -> tuple[float, str]:
        lower = action.lower()
        score = 0.0
        reasons: list[str] = []

        # Core shared components.
        score += 0.9 * loss_severity
        score += 0.6 * anomaly_score
        score += 0.4 * weather_duration_risk
        score += 0.3 * stage_priority
        score += 0.25 * risk_score
        if risk_level == "high":
            score += 0.6
            reasons.append("high_risk_level")
        if anomaly_score > 0:
            reasons.append("anomaly_signal")
        if weather_duration_risk > 0.8:
            reasons.append("weather_duration_risk")

        if "monitor" in lower:
            score = max(0.0, 1.1 - (loss_severity + anomaly_score))
            reasons = ["low_severity_monitoring"]
        elif "dry" in lower or "humidity" in lower or "ventilation" in lower:
            score += 0.9 * weather_duration_risk + (0.5 if stage == "drying" else 0.0)
            reasons.append("drying_weather_action")
        elif "packaging" in lower or "emballage" in lower:
            score += (0.8 if stage == "packaging" else 0.2) + 0.6 * loss_severity
            reasons.append("packaging_loss_control")
        elif "delay" in lower or "wait" in lower or "waiting" in lower:
            score += 0.8 * max((delay - 60.0) / 120.0, 0.0)
            reasons.append("delay_reduction")
        elif "inspect" in lower or "verify" in lower:
            score += 1.2 * anomaly_score + 0.4 * loss_severity
            reasons.append("inspection_priority")
        elif "review" in lower or "procedure" in lower:
            score += 0.5 * loss_severity + 0.4 * risk_score
            reasons.append("process_review")

        score = score * evidence_quality - confidence_penalty
        return round(float(score), 4), ",".join(dict.fromkeys(reasons)) or "general_priority"

    ranked = []
    for action in recs:
        score, reason = _score_for_action(action)
        ranked.append({"action": action, "priority_score": score, "priority_reason": reason})
    ranked.sort(key=lambda item: item["priority_score"], reverse=True)
    return ranked


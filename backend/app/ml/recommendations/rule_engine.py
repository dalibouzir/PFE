from __future__ import annotations

from typing import Dict, List, Mapping

from app.core.config import settings
from app.ml.utils.stage_normalization import normalize_stage


NORMAL_PERFORMANCE_SIGNAL = "Batch performance within expected range"
LIMITED_CONFIDENCE_SIGNAL = "Limited data confidence: verify before action"

RULES = {
    "drying": [
        "Check drying duration settings",
        "Check humidity and moisture conditions",
        "Verify ventilation and airflow performance",
        "Compare with similar recent drying batches",
    ],
    "sorting": [
        "Verify grading criteria application",
        "Check rejection reasons by quality bucket",
        "Inspect damage and defect patterns",
        "Review sorting consistency across operators",
    ],
    "cleaning": [
        "Check cleaning calibration settings",
        "Inspect foreign matter removal effectiveness",
        "Verify handling losses during cleaning",
        "Review operator cleaning checklist adherence",
    ],
    "packaging": [
        "Check packaging workflow sequence",
        "Verify weighing accuracy before packaging",
        "Inspect handling losses during packaging",
        "Verify packaging material suitability",
    ],
}


def derive_prediction_signals(predicted_loss_pct: float, feature_row: Mapping[str, object]) -> List[str]:
    historical_stage_loss = float(feature_row.get("historical_avg_loss_same_stage", 0.0) or 0.0)
    deviation_from_stage_avg = float(feature_row.get("deviation_from_stage_avg", 0.0) or 0.0)
    stock_level = float(feature_row.get("stock_level", 0.0) or 0.0)
    batch_size = float(feature_row.get("batch_size", 0.0) or 0.0)

    top_signals: List[str] = []
    if predicted_loss_pct > historical_stage_loss + 2.0:
        top_signals.append("Stage loss above historical average")
    if deviation_from_stage_avg > 2.0:
        top_signals.append("Batch deviates from normal stage efficiency")
    if batch_size > 0 and stock_level < batch_size * 0.25:
        top_signals.append("Stock pressure is increasing")
    if not top_signals:
        top_signals.append(NORMAL_PERFORMANCE_SIGNAL)
    return top_signals


def build_recommendation(prediction: Dict) -> Dict:
    stage_label = str(prediction.get("critical_stage", ""))
    stage = normalize_stage(stage_label)
    stage_known = stage != "unknown"
    risk_level = prediction["risk_level"]
    loss_pct = float(prediction.get("observed_loss_pct", prediction.get("predicted_loss_pct", 0.0)))
    reasoning = list(dict.fromkeys(prediction.get("top_signals", [])))
    severity = "high" if risk_level == "high" else "medium" if risk_level == "medium" else "low"

    if (
        risk_level == "low"
        and not prediction.get("is_anomalous")
        and reasoning == [NORMAL_PERFORMANCE_SIGNAL]
    ):
        return {
            "issue_type": "monitor",
            "critical_stage": prediction["critical_stage"],
            "severity": severity,
            "recommended_actions": [
                "Continue current process",
                "Monitor upcoming batches",
                "Verify basic stage checklist compliance",
            ],
            "reasoning_signals": reasoning,
            "used_fallback": False,
            "stage_canonical": stage,
        }

    actions = list(RULES.get(stage, [
        "Review stage workflow",
        "Check operator checklist compliance",
        "Compare with recent similar batches",
    ]))
    used_fallback = stage not in RULES

    if severity == "low":
        actions.extend([
            "Monitor next batches for the same stage",
            "Verify basic stage checklist compliance",
        ])
    elif severity == "medium":
        actions.extend([
            "Review stage process parameters",
            "Compare current performance to historical stage average",
            "Inspect likely loss source before next run",
        ])
    else:
        actions.extend([
            "Stop and review before the next batch if operationally possible",
            "Inspect root cause with senior operator",
            "Escalate findings to cooperative manager",
            "Document corrective action and owner",
        ])
    if prediction.get("is_anomalous"):
        actions.append("Investigate anomaly drivers and log findings")

    issue_type = "high_loss" if loss_pct >= settings.step_loss_threshold else "efficiency_dip"
    if loss_pct >= settings.anomaly_loss_threshold:
        reasoning.append("Loss exceeds critical threshold")
    if issue_type == "efficiency_dip":
        reasoning.append("Observed efficiency dip requires verification")

    confidence_score = prediction.get("confidence_score")
    confidence_low = False
    if confidence_score is not None:
        try:
            confidence_low = float(confidence_score) < settings.ml_confidence_medium_threshold
        except (TypeError, ValueError):
            confidence_low = False
    if prediction.get("manual_review_required") or prediction.get("low_data_confidence") or confidence_low or not stage_known:
        reasoning.append(LIMITED_CONFIDENCE_SIGNAL)

    return {
        "issue_type": issue_type,
        "critical_stage": prediction["critical_stage"],
        "severity": severity,
        "recommended_actions": list(dict.fromkeys(actions)),
        "reasoning_signals": list(dict.fromkeys(reasoning)),
        "used_fallback": used_fallback,
        "stage_canonical": stage,
    }

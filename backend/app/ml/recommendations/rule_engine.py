from __future__ import annotations

from typing import Dict, List, Mapping

from app.core.config import settings


NORMAL_PERFORMANCE_SIGNAL = "Batch performance within expected range"

RULES = {
    "drying": [
        "Review drying duration",
        "Inspect environmental moisture conditions",
        "Compare current batch with similar recent batches",
    ],
    "sorting": [
        "Verify pre-sorting quality",
        "Inspect grading consistency",
        "Recalibrate sorting standards",
    ],
    "cleaning": [
        "Inspect cleaning calibration",
        "Review equipment maintenance logs",
        "Check staff adherence to cleaning checklist",
    ],
    "packaging": [
        "Inspect handling and packaging workflow",
        "Check packaging material quality",
        "Audit handoff timing between sorting and packaging",
    ],
}


def derive_prediction_signals(predicted_loss_pct: float, feature_row: Mapping[str, object]) -> List[str]:
    top_signals: List[str] = []
    if predicted_loss_pct > float(feature_row["historical_avg_loss_same_stage"]) + 2.0:
        top_signals.append("Stage loss above historical average")
    if float(feature_row["deviation_from_stage_avg"]) > 2.0:
        top_signals.append("Batch deviates from normal stage efficiency")
    if float(feature_row["stock_level"]) < float(feature_row["batch_size"]) * 0.25:
        top_signals.append("Stock pressure is increasing")
    if not top_signals:
        top_signals.append(NORMAL_PERFORMANCE_SIGNAL)
    return top_signals


def build_recommendation(prediction: Dict) -> Dict:
    stage = prediction["critical_stage"].lower()
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
            ],
            "reasoning_signals": reasoning,
        }

    stage_key = "packaging" if "pack" in stage else stage
    actions = list(RULES.get(stage_key, [
        "Review stage workflow",
        "Check operator checklist compliance",
        "Compare with recent similar batches",
    ]))

    if risk_level == "high":
        actions.append("Schedule an immediate onsite review")
    if prediction.get("is_anomalous"):
        actions.append("Investigate anomaly drivers and log findings")

    issue_type = "high_loss" if loss_pct >= settings.step_loss_threshold else "efficiency_dip"
    if loss_pct >= settings.anomaly_loss_threshold:
        reasoning.append("Loss exceeds critical threshold")

    return {
        "issue_type": issue_type,
        "critical_stage": prediction["critical_stage"],
        "severity": severity,
        "recommended_actions": list(dict.fromkeys(actions)),
        "reasoning_signals": reasoning,
    }

from __future__ import annotations

from typing import Dict

import math

from app.core.config import settings
from app.ml.utils.feature_prep import FEATURE_SCHEMA_VERSION


def _is_finite(value: float | None) -> bool:
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return not (math.isnan(float(value)) or math.isinf(float(value)))
    return False


def evaluate_validation_gates(
    *,
    metadata: Dict,
    artifact_compatibility: Dict,
    trained_rows: int,
) -> Dict:
    metrics = metadata.get("metrics", {})
    forbidden_violations = metadata.get("forbidden_predictive_violations", {}) or {}
    flat_forbidden = []
    for value in forbidden_violations.values():
        if isinstance(value, list):
            flat_forbidden.extend(value)

    schema_version = metadata.get("feature_schema_version")
    expected_schema = getattr(settings, "ml_expected_feature_schema_version", FEATURE_SCHEMA_VERSION)

    model_mae = metrics.get("regression_mae")
    stage_mean_mae = metrics.get("regression_stage_mean_mae")
    product_stage_mean_mae = metrics.get("regression_product_stage_mean_mae")

    underperforms_stage = _is_finite(model_mae) and _is_finite(stage_mean_mae) and float(model_mae) > float(stage_mean_mae)
    underperforms_product_stage = _is_finite(model_mae) and _is_finite(product_stage_mean_mae) and float(model_mae) > float(product_stage_mean_mae)

    false_low_high_risk_rate = metrics.get("false_low_high_risk_rate")
    gates = {
        "artifact_compatibility": bool(artifact_compatibility.get("compatible", False)),
        "predictive_leakage_clean": len(flat_forbidden) == 0,
        "trained_rows_minimum": int(trained_rows) >= int(settings.ml_min_rows),
        "feature_schema_match": str(schema_version) == str(expected_schema),
        "regression_mae_finite": _is_finite(model_mae),
        "false_low_high_risk_rate_ok": _is_finite(false_low_high_risk_rate)
        and float(false_low_high_risk_rate) <= float(getattr(settings, "ml_max_false_low_high_risk_rate", 0.35)),
        "anomaly_validation_required": False,
        "production_readiness_claimed": False,
    }

    all_required_passed = all(
        [
            gates["artifact_compatibility"],
            gates["predictive_leakage_clean"],
            gates["trained_rows_minimum"],
            gates["feature_schema_match"],
            gates["regression_mae_finite"],
            gates["false_low_high_risk_rate_ok"],
        ]
    )

    beats_strong_baselines = (
        _is_finite(model_mae)
        and _is_finite(stage_mean_mae)
        and _is_finite(product_stage_mean_mae)
        and float(model_mae) <= float(stage_mean_mae)
        and float(model_mae) <= float(product_stage_mean_mae)
    )

    mvp_demo_allowed = bool(all_required_passed)
    production_ready = bool(
        all_required_passed
        and beats_strong_baselines
        and int(trained_rows) >= int(getattr(settings, "ml_production_min_rows", 3000))
    )

    return {
        "expected_feature_schema_version": expected_schema,
        "feature_schema_version": schema_version,
        "trained_rows": int(trained_rows),
        "model_mae": float(model_mae) if _is_finite(model_mae) else None,
        "stage_mean_mae": float(stage_mean_mae) if _is_finite(stage_mean_mae) else None,
        "product_stage_mean_mae": float(product_stage_mean_mae) if _is_finite(product_stage_mean_mae) else None,
        "false_low_high_risk_rate": float(false_low_high_risk_rate) if _is_finite(false_low_high_risk_rate) else None,
        "underperforms_stage_baseline": underperforms_stage,
        "underperforms_product_stage_baseline": underperforms_product_stage,
        "beats_strong_baselines": beats_strong_baselines,
        "all_required_passed": all_required_passed,
        "can_activate": all_required_passed,
        "mvp_demo_allowed": mvp_demo_allowed,
        "production_ready": production_ready,
        "gates": gates,
    }

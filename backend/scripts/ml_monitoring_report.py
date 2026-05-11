#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.db.session import SessionLocal
from app.ml.features.engineer import build_features
from app.ml.utils.feature_prep import assign_risk_level, prepare_feature_frame
from app.ml.utils.model_registry import get_active_model_version, get_registry_versions
from app.ml.utils.model_store import artifact_compatibility_status
from app.ml.utils.prediction_logging import read_prediction_logs
from app.ml.utils.stage_normalization import normalize_stage
from app.models.ml import RecommendationFeedbackLog


def _distribution(series: pd.Series) -> Dict[str, int]:
    return {str(k): int(v) for k, v in series.value_counts(dropna=False).to_dict().items()}


def _prob_dist(counts: Dict[str, int]) -> Dict[str, float]:
    total = float(sum(counts.values()))
    if total <= 0:
        return {}
    return {key: float(value / total) for key, value in counts.items()}


def _total_variation_distance(reference: Dict[str, int], current: Dict[str, int]) -> float:
    ref = _prob_dist(reference)
    cur = _prob_dist(current)
    keys = sorted(set(ref.keys()) | set(cur.keys()))
    if not keys:
        return 0.0
    return float(0.5 * sum(abs(ref.get(key, 0.0) - cur.get(key, 0.0)) for key in keys))


def _latest_model_version() -> str | None:
    versions = get_registry_versions()
    if not versions:
        return None
    ordered = sorted(versions, key=lambda item: str(item.get("trained_at", "")), reverse=True)
    return str(ordered[0].get("model_version")) if ordered else None


def _prediction_summary() -> Dict:
    logs = read_prediction_logs()
    if not logs:
        return {
            "prediction_count": 0,
            "average_predicted_loss": None,
            "risk_distribution": {},
            "warning_flag_counts": {},
        }

    losses = [float(item.get("predicted_loss_pct", 0.0)) for item in logs if item.get("predicted_loss_pct") is not None]
    risk_series = pd.Series([str(item.get("risk_level", "unknown")) for item in logs])

    warning_counts: Dict[str, int] = {}
    for item in logs:
        for warning in item.get("warning_flags", []) or []:
            warning_counts[str(warning)] = warning_counts.get(str(warning), 0) + 1

    return {
        "prediction_count": int(len(logs)),
        "average_predicted_loss": float(np.mean(losses)) if losses else None,
        "risk_distribution": _distribution(risk_series),
        "warning_flag_counts": warning_counts,
    }


def _feedback_summary(db: Session) -> Dict:
    total = db.scalar(select(func.count(RecommendationFeedbackLog.id))) or 0
    real_feedback = db.scalar(
        select(func.count(RecommendationFeedbackLog.id)).where(
            RecommendationFeedbackLog.loss_before.isnot(None),
            RecommendationFeedbackLog.loss_after.isnot(None),
        )
    ) or 0
    labels = db.execute(
        select(RecommendationFeedbackLog.outcome_label, func.count(RecommendationFeedbackLog.id))
        .group_by(RecommendationFeedbackLog.outcome_label)
    ).all()
    return {
        "feedback_rows": int(total),
        "real_feedback_rows": int(real_feedback),
        "outcome_distribution": {str(label or "unknown"): int(count) for label, count in labels},
    }


def run_monitoring_report(db: Session, output_json: Path, output_md: Path) -> Dict:
    feature_set = build_features(db)
    df = feature_set.features.copy()
    if df.empty:
        raise RuntimeError("No feature rows available for monitoring report.")

    prepared, _ = prepare_feature_frame(df)
    prepared["risk_level"] = prepared["loss_pct"].apply(assign_risk_level)
    canonical = df["process_type"].apply(normalize_stage)

    active_model = get_active_model_version()
    latest_model_version = _latest_model_version()
    compatibility = artifact_compatibility_status()

    current_product_dist = _distribution(prepared["product"])
    current_stage_dist = _distribution(prepared["stage_canonical"])
    current_risk_dist = _distribution(prepared["risk_level"])

    reference_profile = (active_model or {}).get("dataset_profile", {})
    reference_product_dist = reference_profile.get("product_distribution", {})
    reference_stage_dist = reference_profile.get("stage_distribution", {})
    reference_risk_dist = reference_profile.get("risk_distribution", {})

    shift = {
        "product_distribution_tvd": _total_variation_distance(reference_product_dist, current_product_dist),
        "stage_distribution_tvd": _total_variation_distance(reference_stage_dist, current_stage_dist),
        "risk_distribution_tvd": _total_variation_distance(reference_risk_dist, current_risk_dist),
    }

    predictive_features = compatibility.get("predictive_regression_features", [])
    missing_feature_rate = {
        feature: float(prepared[feature].isna().mean())
        for feature in predictive_features
        if feature in prepared.columns
    }

    unknown_stage_rate = float((canonical == "unknown").mean())
    prediction_summary = _prediction_summary()
    feedback = _feedback_summary(db)

    warnings: List[str] = []
    threshold = float(settings.ml_distribution_shift_threshold)
    if reference_profile:
        if shift["product_distribution_tvd"] > threshold:
            warnings.append("product_distribution_shift_high")
        if shift["stage_distribution_tvd"] > threshold:
            warnings.append("stage_distribution_shift_high")
        if shift["risk_distribution_tvd"] > threshold:
            warnings.append("risk_distribution_shift_high")
    else:
        warnings.append("no_training_reference_profile_for_drift")
    if unknown_stage_rate > 0.05:
        warnings.append("unknown_stage_rate_high")
    if feedback["real_feedback_rows"] == 0:
        warnings.append("no_real_feedback_available")
    if bool((active_model or {}).get("contains_demo_seed_data", False)):
        warnings.append("synthetic_demo_data_used")

    report = {
        "dataset": {
            "row_count": int(len(prepared)),
            "product_distribution": current_product_dist,
            "stage_distribution": current_stage_dist,
            "risk_distribution": current_risk_dist,
            "unknown_stage_rate": unknown_stage_rate,
            "missing_feature_rate": missing_feature_rate,
        },
        "model": {
            "latest_model_version": latest_model_version,
            "active_model_version": (active_model or {}).get("model_version"),
            "feature_schema_version": compatibility.get("feature_schema_version"),
            "artifact_compatibility": compatibility,
            "active_model_status": (active_model or {}).get("status"),
            "mvp_demo_allowed": bool((active_model or {}).get("mvp_demo_allowed", False)),
            "production_ready": bool((active_model or {}).get("production_ready", False)),
        },
        "prediction_logs": prediction_summary,
        "feedback": feedback,
        "drift": {
            "reference_profile_available": bool(reference_profile),
            "reference_product_distribution": reference_product_dist,
            "reference_stage_distribution": reference_stage_dist,
            "reference_risk_distribution": reference_risk_dist,
            **shift,
        },
        "warnings": warnings,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2))

    lines = [
        "# ML Monitoring Report",
        "",
        "## Overview",
        f"- Dataset rows: {report['dataset']['row_count']}",
        f"- Latest model version: {report['model']['latest_model_version']}",
        f"- Active model version: {report['model']['active_model_version']}",
        f"- Feature schema version: {report['model']['feature_schema_version']}",
        "",
        "## Data Distribution",
        f"- Product distribution: {report['dataset']['product_distribution']}",
        f"- Stage distribution: {report['dataset']['stage_distribution']}",
        f"- Risk distribution: {report['dataset']['risk_distribution']}",
        f"- Unknown stage rate: {report['dataset']['unknown_stage_rate']:.4f}",
        "",
        "## Prediction Logs",
        f"- Prediction count: {report['prediction_logs']['prediction_count']}",
        f"- Average predicted loss: {report['prediction_logs']['average_predicted_loss']}",
        f"- Prediction risk distribution: {report['prediction_logs']['risk_distribution']}",
        "",
        "## Drift Checks",
        f"- Product TVD shift: {report['drift']['product_distribution_tvd']:.4f}",
        f"- Stage TVD shift: {report['drift']['stage_distribution_tvd']:.4f}",
        f"- Risk TVD shift: {report['drift']['risk_distribution_tvd']:.4f}",
        "",
        "## Warnings",
        f"- Warnings: {report['warnings']}",
    ]
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines) + "\n")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ML monitoring and drift report.")
    parser.add_argument("--output-json", default="artifacts/ml_monitoring_report.json")
    parser.add_argument("--output-md", default="artifacts/ml_monitoring_report.md")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = run_monitoring_report(db, output_json=Path(args.output_json), output_md=Path(args.output_md))
    finally:
        db.close()

    print(f"Saved JSON report: {args.output_json}")
    print(f"Saved Markdown report: {args.output_md}")
    print(f"Rows: {report['dataset']['row_count']}")
    print(f"Active model: {report['model']['active_model_version']}")
    print(f"Warnings: {report['warnings']}")


if __name__ == "__main__":
    main()

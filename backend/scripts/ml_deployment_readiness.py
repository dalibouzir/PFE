#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.ml.features.engineer import build_features
from app.ml.utils.model_registry import get_active_model_version
from app.ml.utils.model_store import artifact_compatibility_status


def _load_json_if_exists(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _baseline_summary(evaluation: Dict) -> Dict:
    time_eval = (evaluation.get("evaluation") or {}).get("time_based") or {}
    reg = time_eval.get("regression") or {}
    model = reg.get("model") or {}
    baselines = reg.get("baselines") or {}

    def mae(name: str) -> float | None:
        item = baselines.get(name) or {}
        value = item.get("mae")
        return float(value) if isinstance(value, (int, float)) else None

    model_mae = float(model.get("mae")) if isinstance(model.get("mae"), (int, float)) else None
    stage_mae = mae("stage_mean_loss")
    product_stage_mae = mae("product_stage_mean_loss")

    return {
        "model_mae": model_mae,
        "stage_mean_mae": stage_mae,
        "product_stage_mean_mae": product_stage_mae,
        "model_beats_stage_mean": bool(model_mae is not None and stage_mae is not None and model_mae <= stage_mae),
        "model_beats_product_stage_mean": bool(model_mae is not None and product_stage_mae is not None and model_mae <= product_stage_mae),
    }


def _deployment_recommendation(
    artifact_compatibility: Dict,
    active_model: Dict | None,
    warnings: List[str],
    baseline: Dict,
) -> str:
    if not bool(artifact_compatibility.get("compatible", False)):
        return "do_not_deploy"

    if not active_model:
        return "do_not_deploy"

    if bool(active_model.get("production_ready", False)):
        return "production_ready"

    if not bool(active_model.get("mvp_demo_allowed", False)):
        return "deploy_demo_only"

    return "deploy_mvp_with_warnings" if warnings or not baseline.get("model_beats_stage_mean", False) else "deploy_mvp_with_warnings"


def run_deployment_readiness(
    db,
    output_json: Path,
    output_md: Path,
    diagnostics_path: Path = Path("artifacts/ml_diagnostics_phase5.json"),
    evaluation_path: Path = Path("artifacts/ml_evaluation_phase5.json"),
    monitoring_path: Path = Path("artifacts/ml_monitoring_report.json"),
) -> Dict:
    compatibility = artifact_compatibility_status()
    active_model = get_active_model_version()
    features = build_features(db).features

    diagnostics = _load_json_if_exists(diagnostics_path)
    evaluation = _load_json_if_exists(evaluation_path)
    monitoring = _load_json_if_exists(monitoring_path)

    leakage_flags = ((diagnostics.get("leakage_checks") or {}).get("predictive_feature_leakage_flags")) or []
    baseline = _baseline_summary(evaluation)
    classification = (((evaluation.get("evaluation") or {}).get("time_based") or {}).get("classification") or {}).get("model", {})
    warnings = list(monitoring.get("warnings") or [])

    if leakage_flags:
        warnings.append("predictive_leakage_detected")
    if not baseline.get("model_beats_stage_mean", False):
        warnings.append("model_underperforms_stage_baseline")
    if float(classification.get("high_recall", 0.0) or 0.0) == 0.0:
        warnings.append("high_risk_recall_zero")

    recommendation = _deployment_recommendation(compatibility, active_model, warnings, baseline)

    report = {
        "artifact_compatibility": compatibility,
        "active_model": {
            "model_version": (active_model or {}).get("model_version"),
            "status": (active_model or {}).get("status"),
            "mvp_demo_allowed": bool((active_model or {}).get("mvp_demo_allowed", False)),
            "production_ready": bool((active_model or {}).get("production_ready", False)),
            "validation": (active_model or {}).get("validation", {}),
        },
        "checks": {
            "tests_status": "manual: run pytest suite before deployment",
            "leakage_flags": leakage_flags,
            "dataset_rows": int(len(features)),
            "risk_method": "thresholded_predicted_loss",
            "baseline_summary": baseline,
            "classification_summary": {
                "macro_f1": classification.get("macro_f1"),
                "medium_recall": classification.get("medium_recall"),
                "high_recall": classification.get("high_recall"),
                "false_low_high_risk_rate": classification.get("false_low_high_risk_rate"),
            },
        },
        "known_limitations": sorted(set(warnings)),
        "deployment_recommendation": recommendation,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2))

    lines = [
        "# ML Deployment Readiness",
        "",
        "## Core Checks",
        f"- Artifact compatibility: {compatibility.get('compatible')} ({compatibility.get('reason')})",
        f"- Active model version: {(active_model or {}).get('model_version')}",
        f"- Dataset rows: {len(features)}",
        f"- Leakage flags: {leakage_flags}",
        f"- Risk method: thresholded_predicted_loss",
        "",
        "## Baseline Comparison",
        f"- Model MAE: {baseline.get('model_mae')}",
        f"- Stage mean MAE: {baseline.get('stage_mean_mae')}",
        f"- Product-stage mean MAE: {baseline.get('product_stage_mean_mae')}",
        f"- Beats stage baseline: {baseline.get('model_beats_stage_mean')}",
        f"- Beats product-stage baseline: {baseline.get('model_beats_product_stage_mean')}",
        "",
        "## Known Limitations",
        f"- {sorted(set(warnings))}",
        "",
        "## Recommendation",
        f"- Deployment recommendation: {recommendation}",
    ]
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines) + "\n")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate ML deployment readiness report.")
    parser.add_argument("--output-json", default="artifacts/ml_deployment_readiness.json")
    parser.add_argument("--output-md", default="artifacts/ml_deployment_readiness.md")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = run_deployment_readiness(db, output_json=Path(args.output_json), output_md=Path(args.output_md))
    finally:
        db.close()

    print(f"Saved JSON report: {args.output_json}")
    print(f"Saved Markdown report: {args.output_md}")
    print(f"Deployment recommendation: {report['deployment_recommendation']}")


if __name__ == "__main__":
    main()

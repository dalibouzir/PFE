#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict

from sqlalchemy import select
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.models.ml import RecommendationFeedbackLog
from scripts.evaluate_ml_models import run_evaluation

REGRESSION_IMPROVEMENT_GATE = 0.10
CLASSIFICATION_IMPROVEMENT_GATE = 0.10


def _best_regression_baseline(time_eval: Dict) -> tuple[str, Dict]:
    baselines = time_eval["regression"]["baselines"]
    return min(baselines.items(), key=lambda item: float(item[1]["mae"]))


def _best_threshold_classification_baseline(time_eval: Dict) -> tuple[str, Dict]:
    candidates = {
        "thresholded_predicted_loss_baseline": time_eval["classification"]["thresholded_predicted_loss_baseline"],
        "thresholded_product_stage_average_baseline": time_eval["classification"]["thresholded_product_stage_average_baseline"],
    }
    return max(candidates.items(), key=lambda item: float(item[1]["macro_f1"]))


def _safe_relative_improvement(baseline_value: float, model_value: float) -> float:
    if baseline_value <= 0:
        return 0.0
    return float((baseline_value - model_value) / baseline_value)


def _has_recommendation_outcome_feedback(db: Session) -> bool:
    row = db.scalar(
        select(RecommendationFeedbackLog.id).where(
            RecommendationFeedbackLog.loss_before.isnot(None),
            RecommendationFeedbackLog.loss_after.isnot(None),
            RecommendationFeedbackLog.outcome_recorded_at.isnot(None),
        ).limit(1)
    )
    return row is not None


def _build_gate_results(time_eval: Dict, *, has_reco_feedback: bool) -> Dict:
    model_reg_mae = float(time_eval["regression"]["model"]["mae"])
    best_reg_name, best_reg = _best_regression_baseline(time_eval)
    best_reg_mae = float(best_reg["mae"])
    reg_improvement = _safe_relative_improvement(best_reg_mae, model_reg_mae)
    regression_pass = reg_improvement >= REGRESSION_IMPROVEMENT_GATE

    model_cls_f1 = float(time_eval["classification"]["model"]["macro_f1"])
    best_cls_name, best_cls = _best_threshold_classification_baseline(time_eval)
    best_cls_f1 = float(best_cls["macro_f1"])
    cls_improvement = _safe_relative_improvement(model_cls_f1, best_cls_f1)
    classification_pass = cls_improvement >= CLASSIFICATION_IMPROVEMENT_GATE

    return {
        "regression": {
            "status": "PASS" if regression_pass else "FAIL",
            "rule": "Model MAE must beat best baseline MAE by at least 10%",
            "model_mae": model_reg_mae,
            "best_baseline_name": best_reg_name,
            "best_baseline_mae": best_reg_mae,
            "relative_improvement_vs_best_baseline": reg_improvement,
            "required_min_improvement": REGRESSION_IMPROVEMENT_GATE,
        },
        "classification": {
            "status": "PASS" if classification_pass else "FAIL",
            "rule": "Model macro-F1 must beat best threshold baseline macro-F1 by at least 10%",
            "model_macro_f1": model_cls_f1,
            "best_threshold_baseline_name": best_cls_name,
            "best_threshold_baseline_macro_f1": best_cls_f1,
            "relative_improvement_vs_best_threshold_baseline": cls_improvement,
            "required_min_improvement": CLASSIFICATION_IMPROVEMENT_GATE,
        },
        "anomaly_detection": {
            "status": "EXPLORATORY",
            "rule": "Remains exploratory unless labeled anomaly ground truth exists",
            "ground_truth_labels_available": False,
        },
        "recommendation_policy": {
            "status": "RULE_BASED",
            "rule": "Remains rule-based unless action/outcome feedback exists",
            "action_outcome_feedback_exists": has_reco_feedback,
        },
    }


def _build_selection(gates: Dict) -> Dict:
    regression_selected = (
        "ml_model"
        if gates["regression"]["status"] == "PASS"
        else f"baseline:{gates['regression']['best_baseline_name']}"
    )
    classification_selected = (
        "ml_model"
        if gates["classification"]["status"] == "PASS"
        else f"threshold_baseline:{gates['classification']['best_threshold_baseline_name']}"
    )
    return {
        "regression": regression_selected,
        "classification": classification_selected,
        "anomaly_detection": "exploratory_only",
        "recommendation_policy": "rule_engine_templates",
    }


def _baseline_table(time_eval: Dict) -> list[Dict]:
    rows = []
    model_mae = float(time_eval["regression"]["model"]["mae"])
    for name, item in sorted(time_eval["regression"]["baselines"].items(), key=lambda kv: float(kv[1]["mae"])):
        baseline_mae = float(item["mae"])
        rows.append(
            {
                "baseline": name,
                "mae": baseline_mae,
                "delta_vs_model_mae": float(baseline_mae - model_mae),
                "model_beats_baseline": bool(model_mae < baseline_mae),
            }
        )
    return rows


def _write_markdown(report: Dict, output_md: Path) -> None:
    time_eval = report["evaluation"]["time_based"]
    random_eval = report["evaluation"]["random_split"]
    gates = report["gates"]
    lines: list[str] = []
    lines.append("# WeeFarm ML Reliability Audit")
    lines.append("")
    lines.append("## Dataset")
    lines.append(f"- Rows: {report['dataset']['row_count']}")
    lines.append("")
    lines.append("## Time Split (Primary)")
    lines.append(f"- Regression model MAE: {time_eval['regression']['model']['mae']:.4f}")
    lines.append(f"- Classification model macro-F1: {time_eval['classification']['model']['macro_f1']:.4f}")
    lines.append("")
    lines.append("## Random Split (Secondary)")
    lines.append(f"- Regression model MAE: {random_eval['regression']['model']['mae']:.4f}")
    lines.append(f"- Classification model macro-F1: {random_eval['classification']['model']['macro_f1']:.4f}")
    lines.append("")
    lines.append("## Baseline Comparison (Time Split)")
    lines.append("| Baseline | MAE | Delta vs model MAE | Model beats baseline |")
    lines.append("| --- | ---: | ---: | :---: |")
    for row in report["baseline_comparison_table_time_split"]:
        lines.append(
            f"| {row['baseline']} | {row['mae']:.4f} | {row['delta_vs_model_mae']:.4f} | {'YES' if row['model_beats_baseline'] else 'NO'} |"
        )
    lines.append("")
    lines.append("## Classification Baseline Comparison (Time Split)")
    lines.append("| Candidate | Macro-F1 |")
    lines.append("| --- | ---: |")
    lines.append(f"| model | {time_eval['classification']['model']['macro_f1']:.4f} |")
    lines.append(
        f"| thresholded_predicted_loss_baseline | {time_eval['classification']['thresholded_predicted_loss_baseline']['macro_f1']:.4f} |"
    )
    lines.append(
        f"| thresholded_product_stage_average_baseline | {time_eval['classification']['thresholded_product_stage_average_baseline']['macro_f1']:.4f} |"
    )
    lines.append("")
    lines.append("## Gate Results")
    lines.append(f"- Regression gate: {gates['regression']['status']}")
    lines.append(f"- Classification gate: {gates['classification']['status']}")
    lines.append(f"- Anomaly gate: {gates['anomaly_detection']['status']}")
    lines.append(f"- Recommendation policy gate: {gates['recommendation_policy']['status']}")
    lines.append("")
    lines.append("## Selection Decision")
    lines.append(f"- Regression decision: {report['selected_model_or_fallback']['regression']}")
    lines.append(f"- Classification decision: {report['selected_model_or_fallback']['classification']}")
    lines.append(f"- Anomaly decision: {report['selected_model_or_fallback']['anomaly_detection']}")
    lines.append(f"- Recommendation decision: {report['selected_model_or_fallback']['recommendation_policy']}")
    lines.append("")
    lines.append("## PFE Report Claims")
    lines.append("Can claim:")
    lines.append(f"- Classification ML outperforms threshold baselines by {gates['classification']['relative_improvement_vs_best_threshold_baseline'] * 100:.2f}% on macro-F1 (time split).")
    lines.append("- Anomaly outputs are operational signals only (not supervised-validated accuracy).")
    lines.append("- Recommendation generation is currently rule-based template logic.")
    lines.append("Cannot claim:")
    lines.append("- Reliable regression superiority over strong statistical baselines for loss prediction.")
    lines.append("- Validated anomaly detection accuracy without labeled anomaly ground truth.")
    lines.append("- ML-ranked recommendation policy effectiveness without action/outcome feedback evidence.")
    lines.append("")
    lines.append("## Honest Verdict")
    lines.append(
        "Current stack is mixed-readiness: classification signal is promising, regression reliability gate fails, anomaly is exploratory, and recommendation remains rule-based."
    )
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines))


def run_reliability_audit(db: Session, output_json: Path, output_md: Path) -> Dict:
    eval_report = run_evaluation(
        db,
        output_json=Path("artifacts/ml_evaluation_report.json"),
        output_md=Path("artifacts/ml_evaluation_report.md"),
    )
    time_eval = eval_report["evaluation"]["time_based"]
    has_reco_feedback = _has_recommendation_outcome_feedback(db)
    gates = _build_gate_results(time_eval, has_reco_feedback=has_reco_feedback)

    report = {
        "dataset": eval_report["dataset"],
        "split_details": eval_report["split_details"],
        "evaluation": eval_report["evaluation"],
        "baseline_comparison_table_time_split": _baseline_table(time_eval),
        "gates": gates,
        "selected_model_or_fallback": _build_selection(gates),
        "pfe_claims": {
            "can_claim": [
                "Classification model improvement over threshold baselines is measurable on macro-F1.",
                "Anomaly output is exploratory and must not be reported as validated accuracy.",
                "Recommendation engine behavior is currently rule-based.",
            ],
            "cannot_claim": [
                "Regression model is superior to strong baselines.",
                "Anomaly detection is validated without labels.",
                "Recommendation policy is ML-ranked and outcome-proven.",
            ],
        },
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2))
    _write_markdown(report, output_md)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run strict ML reliability gates and claim audit.")
    parser.add_argument(
        "--output-json",
        default="reports/ml_reliability_audit.json",
        help="JSON report path.",
    )
    parser.add_argument(
        "--output-md",
        default="reports/ml_reliability_audit.md",
        help="Markdown report path.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = run_reliability_audit(db, output_json=Path(args.output_json), output_md=Path(args.output_md))
    finally:
        db.close()

    print(f"Saved JSON report: {args.output_json}")
    print(f"Saved Markdown report: {args.output_md}")
    print(f"Rows: {report['dataset']['row_count']}")
    print(f"Regression gate: {report['gates']['regression']['status']}")
    print(f"Classification gate: {report['gates']['classification']['status']}")


if __name__ == "__main__":
    main()

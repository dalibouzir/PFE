from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import desc, func, select

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.models.ml import MLPredictionLog, MLTrainingRun
from app.services.helpers import round_metric
from scripts.evaluate_ml_models import run_evaluation

JSON_REPORT_PATH = ROOT_DIR / "reports" / "ml_model_validation_report.json"
MD_REPORT_PATH = ROOT_DIR / "reports" / "ml_model_validation_report.md"


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _build_partial_report(reason: str) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "partial",
        "limitation": reason,
        "dataset": {
            "row_count": 0,
            "product_distribution": {},
            "stage_distribution": {},
            "risk_class_distribution": {},
        },
        "model_or_service": {
            "regression": "RandomForestRegressor via evaluate_ml_models",
            "classification": "RandomForestClassifier via evaluate_ml_models",
            "anomaly": "IsolationForest via evaluate_ml_models",
        },
        "metrics": {
            "classification": None,
            "regression": None,
            "anomaly_detection": {
                "true_positives": None,
                "false_positives": None,
                "false_negatives": None,
                "note": "No labeled anomaly ground truth available.",
            },
        },
        "strongest_cases": [],
        "weakest_cases": [],
        "limitations": [
            reason,
            "No supervised anomaly labels are currently available to compute TP/FP/FN precisely.",
        ],
        "synthetic_data_disclaimer": "Metrics are computed on synthetic/demo operational data and are not production validation.",
        "pfe_usage_guidance": [
            "Use these metrics to document relative model behavior on the demo dataset.",
            "Avoid claiming external/generalized performance without real-field validation data.",
            "Highlight anomaly-evaluation limitation as an explicit research gap in the PFE report.",
        ],
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = [
        "# ML Full Demo Validation Report",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Status: {report.get('status')}",
        "",
    ]

    if report.get("status") != "ok":
        lines.extend(
            [
                "## Limitation",
                f"- {report.get('limitation')}",
                "",
                "## Synthetic Data Disclaimer",
                f"- {report.get('synthetic_data_disclaimer')}",
            ]
        )
        return "\n".join(lines)

    dataset = report["dataset"]
    lines.extend(
        [
            "## Dataset",
            f"- Rows: {dataset.get('row_count')}",
            f"- Products: {dataset.get('product_distribution')}",
            f"- Stages (raw): {dataset.get('stage_distribution_raw')}",
            f"- Stages (canonical): {dataset.get('stage_distribution_canonical')}",
            f"- Risk classes: {dataset.get('risk_class_distribution')}",
            "",
            "## Model/Service",
            f"- Regression: {report['model_or_service']['regression']}",
            f"- Classification: {report['model_or_service']['classification']}",
            f"- Anomaly: {report['model_or_service']['anomaly']}",
            "",
            "## Classification Metrics",
            f"- Accuracy: {report['metrics']['classification']['accuracy']}",
            f"- Precision (macro): {report['metrics']['classification']['precision_macro']}",
            f"- Recall (macro): {report['metrics']['classification']['recall_macro']}",
            f"- F1 (macro): {report['metrics']['classification']['f1_macro']}",
            f"- F1 (weighted): {report['metrics']['classification']['f1_weighted']}",
            f"- Confusion matrix labels: {report['metrics']['classification']['labels']}",
            f"- Confusion matrix: {report['metrics']['classification']['confusion_matrix']}",
            "",
            "## Regression Metrics",
            f"- MAE: {report['metrics']['regression']['mae']}",
            f"- RMSE: {report['metrics']['regression']['rmse']}",
            f"- R²: {report['metrics']['regression']['r2']}",
            "",
            "## Anomaly Metrics",
            f"- True positives: {report['metrics']['anomaly_detection']['true_positives']}",
            f"- False positives: {report['metrics']['anomaly_detection']['false_positives']}",
            f"- False negatives: {report['metrics']['anomaly_detection']['false_negatives']}",
            f"- Note: {report['metrics']['anomaly_detection']['note']}",
            "",
            "## Strongest Cases",
        ]
    )
    for item in report.get("strongest_cases", [])[:8]:
        lines.append(f"- {item}")

    lines.extend(["", "## Weakest Cases"])
    for item in report.get("weakest_cases", [])[:8]:
        lines.append(f"- {item}")

    lines.extend(["", "## Limitations"])
    for item in report.get("limitations", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Synthetic Data Disclaimer", f"- {report.get('synthetic_data_disclaimer')}"])

    lines.extend(["", "## PFE Usage Guidance"])
    for item in report.get("pfe_usage_guidance", []):
        lines.append(f"- {item}")

    return "\n".join(lines)


def main() -> None:
    JSON_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()

    try:
        tmp_json = ROOT_DIR / "artifacts" / "ml_model_validation_tmp.json"
        tmp_md = ROOT_DIR / "artifacts" / "ml_model_validation_tmp.md"

        try:
            eval_report = run_evaluation(db, output_json=tmp_json, output_md=tmp_md)
        except Exception as exc:
            report = _build_partial_report(str(exc))
            JSON_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            MD_REPORT_PATH.write_text(_render_markdown(report), encoding="utf-8")
            print(f"Saved {JSON_REPORT_PATH}")
            print(f"Saved {MD_REPORT_PATH}")
            return

        dataset = eval_report.get("dataset", {})
        time_eval = eval_report.get("evaluation", {}).get("time_based", {})
        cls_model = time_eval.get("classification", {}).get("model", {})
        cls_per_class = cls_model.get("per_class", {})
        precision_macro = _safe_float(
            sum(float(item.get("precision", 0.0)) for item in cls_per_class.values()) / max(len(cls_per_class), 1)
        )
        recall_macro = _safe_float(
            sum(float(item.get("recall", 0.0)) for item in cls_per_class.values()) / max(len(cls_per_class), 1)
        )

        reg_model = time_eval.get("regression", {}).get("model", {})
        anomaly_review = time_eval.get("anomaly_review", {})

        top_errors = time_eval.get("top_prediction_errors", [])
        strongest_segments = time_eval.get("segment_analysis", {}).get("by_product_stage", [])
        strongest_sorted = sorted(
            strongest_segments,
            key=lambda row: (float(row.get("mae", 999.0)), -int(row.get("row_count", 0))),
        )

        strongest_cases = [
            {
                "product": item.get("product"),
                "stage_canonical": item.get("stage_canonical"),
                "row_count": item.get("row_count"),
                "mae": round_metric(float(item.get("mae", 0.0))),
                "mean_actual_loss_pct": round_metric(float(item.get("mean_actual_loss_pct", 0.0))),
                "mean_predicted_loss_pct": round_metric(float(item.get("mean_predicted_loss_pct", 0.0))),
            }
            for item in strongest_sorted[:8]
        ]

        weakest_cases = [
            {
                "product": item.get("product"),
                "process_type": item.get("process_type"),
                "stage_canonical": item.get("stage_canonical"),
                "actual_loss_pct": round_metric(float(item.get("actual_loss_pct", 0.0))),
                "predicted_loss_pct": round_metric(float(item.get("predicted_loss_pct", 0.0))),
                "abs_error": round_metric(float(item.get("abs_error", 0.0))),
            }
            for item in top_errors[:10]
        ]

        latest_train = db.scalars(select(MLTrainingRun).order_by(desc(MLTrainingRun.started_at)).limit(1)).first()
        prediction_count = int(db.scalar(select(func.count(MLPredictionLog.id))) or 0)

        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "ok",
            "dataset": {
                "row_count": int(dataset.get("row_count", 0)),
                "product_distribution": dataset.get("product_distribution", {}),
                "stage_distribution_raw": dataset.get("stage_distribution_raw", {}),
                "stage_distribution_canonical": dataset.get("stage_distribution_canonical", {}),
                "risk_class_distribution": dataset.get("risk_class_distribution", {}),
                "prediction_log_count": prediction_count,
            },
            "model_or_service": {
                "regression": "RandomForestRegressor (time-based evaluation split)",
                "classification": "RandomForestClassifier (time-based evaluation split)",
                "anomaly": "IsolationForest (exploratory review)",
                "latest_training_run": {
                    "run_name": str(latest_train.run_name) if latest_train else None,
                    "status": str(latest_train.status) if latest_train else None,
                    "started_at": str(latest_train.started_at.isoformat()) if latest_train and latest_train.started_at else None,
                    "completed_at": str(latest_train.completed_at.isoformat()) if latest_train and latest_train.completed_at else None,
                    "dataset_rows": int(latest_train.dataset_rows) if latest_train else None,
                },
                "labels_or_targets": {
                    "classification_target": "risk_level derived from loss_pct thresholds",
                    "regression_target": "loss_pct",
                    "anomaly_target": "none (unsupervised, no labeled anomaly ground truth)",
                },
            },
            "metrics": {
                "classification": {
                    "accuracy": _safe_float(cls_model.get("accuracy")),
                    "precision_macro": precision_macro,
                    "recall_macro": recall_macro,
                    "f1_macro": _safe_float(cls_model.get("macro_f1")),
                    "f1_weighted": _safe_float(cls_model.get("weighted_f1")),
                    "labels": cls_model.get("labels", []),
                    "confusion_matrix": cls_model.get("confusion_matrix", []),
                    "per_class": cls_per_class,
                },
                "regression": {
                    "mae": _safe_float(reg_model.get("mae")),
                    "rmse": _safe_float(reg_model.get("rmse")),
                    "r2": _safe_float(reg_model.get("r2")),
                },
                "anomaly_detection": {
                    "true_positives": None,
                    "false_positives": None,
                    "false_negatives": None,
                    "note": "No labeled anomaly ground truth in current schema; only exploratory anomaly flag-rate metrics are available.",
                    "exploratory": {
                        "flag_rate": _safe_float(anomaly_review.get("flag_rate")),
                        "score_negative_rate": _safe_float(anomaly_review.get("score_negative_rate")),
                        "flagged_count": int(anomaly_review.get("flagged_count", 0) or 0),
                        "flagged_high_loss_rate": _safe_float(anomaly_review.get("flagged_high_loss_rate")),
                    },
                },
            },
            "strongest_cases": strongest_cases,
            "weakest_cases": weakest_cases,
            "limitations": [
                "Evaluation uses synthetic/demo operational data and may not reflect production field variability.",
                "Risk labels are derived from thresholded loss_pct, which may embed heuristic bias.",
                "No supervised anomaly labels are available; TP/FP/FN cannot be computed reliably.",
            ],
            "synthetic_data_disclaimer": "These metrics are computed from synthetic demo data seeded for platform validation and should be treated as internal validation only.",
            "pfe_usage_guidance": [
                "Report these metrics as reproducible internal benchmarks for the demo dataset.",
                "Use confusion matrix and per-class recall to discuss risk-class detection strengths/weaknesses.",
                "Use MAE/RMSE/R² to explain predictive error characteristics and model fit limits.",
                "Explicitly mention that anomaly TP/FP/FN are unavailable due to missing labeled anomaly targets.",
            ],
            "raw_eval_source": {
                "time_split_train_rows": int(time_eval.get("train_rows", 0) or 0),
                "time_split_test_rows": int(time_eval.get("test_rows", 0) or 0),
                "split_details": eval_report.get("split_details", {}),
            },
        }

        JSON_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        MD_REPORT_PATH.write_text(_render_markdown(report), encoding="utf-8")
        print(f"Saved {JSON_REPORT_PATH}")
        print(f"Saved {MD_REPORT_PATH}")

    finally:
        db.close()


if __name__ == "__main__":
    main()

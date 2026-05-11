#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_fscore_support,
    r2_score,
)
from sklearn.model_selection import train_test_split
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.ml.features.engineer import build_features
from app.ml.training.trainer import _build_pipeline, _split_train_test_indices
from app.ml.utils.feature_prep import (
    assign_risk_level,
    assign_thresholded_risk_level,
    get_risk_thresholds,
    prepare_feature_frame,
)
from app.ml.utils.stage_normalization import normalize_stage


RISK_LABELS = ["low", "medium", "high"]


def _safe_rmse(y_true: pd.Series, y_pred: np.ndarray) -> float:
    try:
        return float(mean_squared_error(y_true, y_pred, squared=False))
    except TypeError:
        return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def _safe_r2(y_true: pd.Series, y_pred: np.ndarray) -> float | None:
    if len(y_true) < 2:
        return None
    value = float(r2_score(y_true, y_pred))
    if math.isnan(value) or math.isinf(value):
        return None
    return value


def _distribution(series: pd.Series) -> Dict[str, int]:
    return {str(key): int(val) for key, val in series.value_counts(dropna=False).to_dict().items()}


def _classification_metrics(y_true: pd.Series, y_pred: np.ndarray) -> Dict:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=RISK_LABELS,
        zero_division=0,
    )
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted")),
        "per_class": {
            label: {
                "precision": float(precision[idx]),
                "recall": float(recall[idx]),
                "f1": float(f1[idx]),
                "support": int(support[idx]),
            }
            for idx, label in enumerate(RISK_LABELS)
        },
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=RISK_LABELS).tolist(),
        "labels": list(RISK_LABELS),
    }
    total_high = int(np.sum(y_true == "high"))
    false_low = int(np.sum((y_true == "high") & (y_pred == "low")))
    metrics["false_low_high_risk_rate"] = float(false_low / total_high) if total_high else 0.0
    metrics["medium_recall"] = float(metrics["per_class"]["medium"]["recall"])
    metrics["high_recall"] = float(metrics["per_class"]["high"]["recall"])
    return metrics


def _regression_metrics(y_true: pd.Series, y_pred: np.ndarray) -> Dict:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": _safe_rmse(y_true, y_pred),
        "r2": _safe_r2(y_true, y_pred),
    }


def _baseline_predictions(
    prepared: pd.DataFrame,
    train_indices: pd.Index,
    test_indices: pd.Index,
) -> Dict[str, np.ndarray]:
    train = prepared.loc[train_indices]
    test = prepared.loc[test_indices]

    global_mean = float(train["loss_pct"].mean())
    pred_global = np.full(shape=len(test), fill_value=global_mean)

    prod_map = train.groupby("product")["loss_pct"].mean().to_dict()
    stage_map = train.groupby("stage_canonical")["loss_pct"].mean().to_dict()
    prod_stage_map = train.groupby(["product", "stage_canonical"])["loss_pct"].mean().to_dict()
    stage_season_map = train.groupby(["stage_canonical", "season"])["loss_pct"].mean().to_dict()
    prod_stage_season_map = train.groupby(["product", "stage_canonical", "season"])["loss_pct"].mean().to_dict()
    rolling_prod_stage_map = (
        train.sort_values(["date_ordinal"])
        .groupby(["product", "stage_canonical"])["loss_pct"]
        .apply(lambda series: float(series.tail(5).mean()))
        .to_dict()
    )

    pred_product = np.array([prod_map.get(row["product"], global_mean) for _, row in test.iterrows()], dtype=float)
    pred_stage = np.array([stage_map.get(row["stage_canonical"], global_mean) for _, row in test.iterrows()], dtype=float)
    pred_prod_stage = np.array(
        [prod_stage_map.get((row["product"], row["stage_canonical"]), prod_map.get(row["product"], stage_map.get(row["stage_canonical"], global_mean))) for _, row in test.iterrows()],
        dtype=float,
    )
    pred_stage_season = np.array(
        [
            stage_season_map.get(
                (row["stage_canonical"], row["season"]),
                stage_map.get(row["stage_canonical"], global_mean),
            )
            for _, row in test.iterrows()
        ],
        dtype=float,
    )
    pred_prod_stage_season = np.array(
        [
            prod_stage_season_map.get(
                (row["product"], row["stage_canonical"], row["season"]),
                prod_stage_map.get((row["product"], row["stage_canonical"]), stage_map.get(row["stage_canonical"], global_mean)),
            )
            for _, row in test.iterrows()
        ],
        dtype=float,
    )
    pred_prod_stage_rolling = np.array(
        [
            rolling_prod_stage_map.get(
                (row["product"], row["stage_canonical"]),
                prod_stage_map.get((row["product"], row["stage_canonical"]), global_mean),
            )
            for _, row in test.iterrows()
        ],
        dtype=float,
    )
    pred_previous_batch = test["previous_batch_loss"].to_numpy(dtype=float)

    return {
        "global_mean_loss": pred_global,
        "product_mean_loss": pred_product,
        "stage_mean_loss": pred_stage,
        "product_stage_mean_loss": pred_prod_stage,
        "stage_season_mean_loss": pred_stage_season,
        "product_stage_season_mean_loss": pred_prod_stage_season,
        "product_stage_rolling_mean_loss": pred_prod_stage_rolling,
        "previous_batch_loss_baseline": pred_previous_batch,
    }


def _segment_metrics(eval_df: pd.DataFrame, keys: List[str]) -> List[Dict]:
    rows: List[Dict] = []
    grouped = eval_df.groupby(keys, dropna=False)
    for key, group in grouped:
        if not isinstance(key, tuple):
            key = (key,)
        item = {keys[idx]: str(val) for idx, val in enumerate(key)}
        item.update(
            {
                "row_count": int(len(group)),
                "mae": float(mean_absolute_error(group["actual_loss_pct"], group["predicted_loss_pct"])),
                "mean_actual_loss_pct": float(group["actual_loss_pct"].mean()),
                "mean_predicted_loss_pct": float(group["predicted_loss_pct"].mean()),
                "error_bias": float((group["predicted_loss_pct"] - group["actual_loss_pct"]).mean()),
            }
        )
        rows.append(item)
    rows.sort(key=lambda row: row["row_count"], reverse=True)
    return rows


def _evaluate_split(prepared: pd.DataFrame, feature_groups: Dict[str, List[str]], train_indices: pd.Index, test_indices: pd.Index, split_name: str) -> Dict:
    regression_features = feature_groups["predictive_regression_features"]
    classification_features = feature_groups["predictive_classification_features"]
    anomaly_features = feature_groups["assessment_anomaly_features"]

    y_loss = prepared["loss_pct"]
    y_risk = prepared["loss_pct"].apply(assign_risk_level)

    X_loss_train = prepared.loc[train_indices, regression_features]
    X_loss_test = prepared.loc[test_indices, regression_features]
    X_risk_train = prepared.loc[train_indices, classification_features]
    X_risk_test = prepared.loc[test_indices, classification_features]
    X_anomaly_train = prepared.loc[train_indices, anomaly_features]
    X_anomaly_test = prepared.loc[test_indices, anomaly_features]
    y_loss_train = y_loss.loc[train_indices]
    y_loss_test = y_loss.loc[test_indices]
    y_risk_train = y_risk.loc[train_indices]
    y_risk_test = y_risk.loc[test_indices]

    loss_model = _build_pipeline(
        regression_features,
        RandomForestRegressor(n_estimators=250, random_state=42),
    )
    risk_model = _build_pipeline(
        classification_features,
        RandomForestClassifier(n_estimators=250, random_state=42),
    )
    anomaly_model = _build_pipeline(
        anomaly_features,
        IsolationForest(n_estimators=200, random_state=42, contamination=0.08),
    )

    loss_model.fit(X_loss_train, y_loss_train)
    risk_model.fit(X_risk_train, y_risk_train)
    anomaly_model.fit(X_anomaly_train)

    loss_pred = loss_model.predict(X_loss_test)
    risk_pred = risk_model.predict(X_risk_test)
    anomaly_scores = anomaly_model.decision_function(X_anomaly_test)
    anomaly_flags = anomaly_model.predict(X_anomaly_test)

    baseline_pred = _baseline_predictions(prepared, train_indices, test_indices)
    baseline_metrics = {}
    model_metrics = _regression_metrics(y_loss_test, loss_pred)
    for name, pred in baseline_pred.items():
        metrics = _regression_metrics(y_loss_test, pred)
        baseline_metrics[name] = {
            **metrics,
            "mae_improvement_vs_model": float(metrics["mae"] - model_metrics["mae"]),
            "rmse_improvement_vs_model": float(metrics["rmse"] - model_metrics["rmse"]),
        }

    majority_label = str(y_risk_train.mode().iloc[0])
    majority_pred = np.full(shape=len(y_risk_test), fill_value=majority_label)
    predicted_loss_threshold_risk = np.array([assign_thresholded_risk_level(float(value)) for value in loss_pred])
    test_rows = prepared.loc[test_indices].copy()
    train_rows = prepared.loc[train_indices].copy()
    ps_risk_map = train_rows.groupby(["product", "stage_canonical"])["loss_pct"].mean().apply(assign_thresholded_risk_level).to_dict()
    fallback_risk = assign_thresholded_risk_level(float(train_rows["loss_pct"].mean()))
    product_stage_threshold_risk = np.array(
        [
            ps_risk_map.get((row["product"], row["stage_canonical"]), fallback_risk)
            for _, row in test_rows.iterrows()
        ]
    )

    classification = {
        "model": _classification_metrics(y_risk_test, risk_pred),
        "majority_class_baseline": _classification_metrics(y_risk_test, majority_pred),
        "thresholded_predicted_loss_baseline": _classification_metrics(y_risk_test, predicted_loss_threshold_risk),
        "thresholded_product_stage_average_baseline": _classification_metrics(y_risk_test, product_stage_threshold_risk),
        "risk_thresholds_used": get_risk_thresholds(),
    }

    eval_df = test_rows.copy()
    eval_df["actual_loss_pct"] = y_loss_test.to_numpy()
    eval_df["predicted_loss_pct"] = loss_pred
    eval_df["abs_error"] = (eval_df["predicted_loss_pct"] - eval_df["actual_loss_pct"]).abs()
    eval_df["actual_risk_level"] = y_risk_test.to_numpy()
    eval_df["predicted_risk_level"] = risk_pred
    eval_df["anomaly_score_raw"] = anomaly_scores
    eval_df["is_anomalous"] = anomaly_flags == -1

    top_errors = (
        eval_df.sort_values("abs_error", ascending=False)
        .head(10)[
            [
                "product",
                "process_type",
                "stage_canonical",
                "qty_in",
                "qty_out",
                "actual_loss_pct",
                "predicted_loss_pct",
                "abs_error",
                "actual_risk_level",
                "predicted_risk_level",
            ]
        ]
        .to_dict("records")
    )

    flagged = eval_df[eval_df["is_anomalous"]].copy()
    top_anomaly = eval_df.sort_values("anomaly_score_raw", ascending=True).head(10)
    anomaly_review = {
        "anomaly_accuracy_reported": False,
        "note": "Exploratory only: no labeled anomaly ground truth available.",
        "flag_rate": float(np.mean(eval_df["is_anomalous"])),
        "score_negative_rate": float(np.mean(eval_df["anomaly_score_raw"] < 0)),
        "flagged_count": int(len(flagged)),
        "flagged_high_loss_rate": float(np.mean(flagged["actual_loss_pct"] >= 18.0)) if len(flagged) else 0.0,
        "top_anomaly_examples": top_anomaly[
            [
                "product",
                "process_type",
                "stage_canonical",
                "actual_loss_pct",
                "predicted_loss_pct",
                "anomaly_score_raw",
                "is_anomalous",
            ]
        ].to_dict("records"),
    }

    return {
        "split_name": split_name,
        "train_rows": int(len(train_indices)),
        "test_rows": int(len(test_indices)),
        "regression": {
            "model": model_metrics,
            "baselines": baseline_metrics,
        },
        "classification": classification,
        "segment_analysis": {
            "by_product": _segment_metrics(eval_df, ["product"]),
            "by_canonical_stage": _segment_metrics(eval_df, ["stage_canonical"]),
            "by_product_stage": _segment_metrics(eval_df, ["product", "stage_canonical"]),
            "by_risk_class": _segment_metrics(eval_df, ["actual_risk_level"]),
        },
        "top_prediction_errors": top_errors,
        "anomaly_review": anomaly_review,
    }


def _write_markdown(report: Dict, output_md: Path) -> None:
    time_split = report["evaluation"]["time_based"]
    random_split = report["evaluation"]["random_split"]
    model_cls = time_split["classification"]["model"]
    model_reg = time_split["regression"]["model"]
    baseline_reg = time_split["regression"]["baselines"]

    lines: List[str] = []
    lines.append("# ML Evaluation Report")
    lines.append("")
    lines.append("## Dataset Summary")
    lines.append(f"- Rows: {report['dataset']['row_count']}")
    lines.append(f"- Products: {report['dataset']['product_distribution']}")
    lines.append(f"- Raw stages: {report['dataset']['stage_distribution_raw']}")
    lines.append(f"- Canonical stages: {report['dataset']['stage_distribution_canonical']}")
    lines.append(f"- Risk classes: {report['dataset']['risk_class_distribution']}")
    lines.append("")
    lines.append("## Split Strategy")
    lines.append(f"- Time-based split: train={time_split['train_rows']}, test={time_split['test_rows']}")
    lines.append(f"- Random split: train={random_split['train_rows']}, test={random_split['test_rows']}")
    lines.append("")
    lines.append("## Regression Evaluation")
    lines.append(f"- Time split model MAE: {model_reg['mae']:.4f}")
    lines.append(f"- Time split model RMSE: {model_reg['rmse']:.4f}")
    lines.append(f"- Time split model R2: {model_reg['r2']}")
    lines.append("")
    lines.append("## Baseline Comparison")
    for name, metrics in baseline_reg.items():
        lines.append(
            f"- {name}: MAE={metrics['mae']:.4f}, RMSE={metrics['rmse']:.4f}, "
            f"MAE delta vs model={metrics['mae_improvement_vs_model']:.4f}"
        )
    lines.append("")
    lines.append("## Classification Evaluation")
    lines.append(
        f"- Model accuracy={model_cls['accuracy']:.4f}, macro-F1={model_cls['macro_f1']:.4f}, "
        f"weighted-F1={model_cls['weighted_f1']:.4f}"
    )
    lines.append(f"- Per-class: {model_cls['per_class']}")
    lines.append(f"- Confusion matrix: {model_cls['confusion_matrix']}")
    lines.append(
        f"- Medium recall: {model_cls['medium_recall']:.4f}, High recall: {model_cls['high_recall']:.4f}, "
        f"False-low high-risk rate: {model_cls['false_low_high_risk_rate']:.4f}"
    )
    lines.append(f"- Thresholded risk method: {time_split['classification']['risk_thresholds_used']}")
    lines.append("")
    lines.append("## Segment Analysis")
    lines.append(f"- Product segments: {time_split['segment_analysis']['by_product']}")
    lines.append(f"- Canonical stage segments: {time_split['segment_analysis']['by_canonical_stage']}")
    lines.append("")
    lines.append("## Top Prediction Errors")
    lines.append(f"- Top 10 errors: {time_split['top_prediction_errors']}")
    lines.append("")
    lines.append("## Anomaly Review")
    lines.append("- No anomaly accuracy is reported (no ground-truth anomaly labels).")
    lines.append(f"- Anomaly review: {time_split['anomaly_review']}")
    lines.append("")
    lines.append("## Honest Interpretation")
    lines.append("- Regression is mixed versus strong baselines across splits.")
    lines.append("- Classification remains weak for medium/high risk recall.")
    lines.append("- Current anomaly signals are exploratory only, not validated accuracy.")
    lines.append("")
    lines.append("## Recommended Next Actions")
    lines.append("- Improve class balance for medium/high risk.")
    lines.append("- Add walk-forward validation and calibration tracking.")
    lines.append("- Add labeled anomaly feedback to evaluate precision@k.")
    lines.append("")

    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines))


def run_evaluation(db: Session, output_json: Path, output_md: Path) -> Dict:
    feature_set = build_features(db)
    df = feature_set.features.copy()
    if df.empty:
        raise RuntimeError("No ML rows found. Add process-step data first.")

    df["stage_canonical"] = df["process_type"].apply(normalize_stage)
    prepared, feature_groups = prepare_feature_frame(df)
    train_idx_time, test_idx_time, split_details = _split_train_test_indices(prepared, test_size=0.2)
    train_idx_random, test_idx_random = train_test_split(prepared.index, test_size=0.2, random_state=42)

    report = {
        "dataset": {
            "row_count": int(len(df)),
            "product_distribution": _distribution(df["product"]),
            "stage_distribution_raw": _distribution(df["process_type"]),
            "stage_distribution_canonical": _distribution(df["stage_canonical"]),
            "risk_class_distribution": _distribution(prepared["loss_pct"].apply(assign_risk_level)),
        },
        "split_details": {
            "time_based": split_details,
            "random": {
                "train_rows": int(len(train_idx_random)),
                "test_rows": int(len(test_idx_random)),
            },
        },
        "evaluation": {
            "time_based": _evaluate_split(prepared, feature_groups, train_idx_time, test_idx_time, "time_based"),
            "random_split": _evaluate_split(prepared, feature_groups, train_idx_random, test_idx_random, "random"),
        },
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2))
    _write_markdown(report, output_md)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ML models with baselines and segment diagnostics.")
    parser.add_argument(
        "--output-json",
        default="artifacts/ml_evaluation_report.json",
        help="JSON report path.",
    )
    parser.add_argument(
        "--output-md",
        default="artifacts/ml_evaluation_report.md",
        help="Markdown report path.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = run_evaluation(db, output_json=Path(args.output_json), output_md=Path(args.output_md))
    finally:
        db.close()

    print(f"Saved JSON report: {args.output_json}")
    print(f"Saved Markdown report: {args.output_md}")
    print(f"Rows: {report['dataset']['row_count']}")
    print(f"Time split regression MAE: {report['evaluation']['time_based']['regression']['model']['mae']:.4f}")
    print(f"Time split classification macro-F1: {report['evaluation']['time_based']['classification']['model']['macro_f1']:.4f}")


if __name__ == "__main__":
    main()

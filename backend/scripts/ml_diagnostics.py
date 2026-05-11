#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier, RandomForestRegressor
from sklearn.inspection import permutation_importance
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

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionLocal
from app.core.config import settings
from app.ml.features.engineer import build_features
from app.ml.recommendations.rule_engine import NORMAL_PERFORMANCE_SIGNAL, build_recommendation
from app.ml.training.trainer import _build_pipeline, _split_train_test_indices
from app.ml.utils.feature_prep import (
    FORBIDDEN_PREDICTIVE_FEATURES,
    assign_risk_level,
    assign_thresholded_risk_level,
    get_risk_thresholds,
    prepare_feature_frame,
)
from app.ml.utils.model_store import artifact_compatibility_status, load_model_bundle
from app.ml.utils.model_registry import get_active_model_version, get_registry_versions
from app.ml.utils.stage_normalization import normalize_stage


RISK_LABELS = ["low", "medium", "high"]
LEAKAGE_FEATURES = set(FORBIDDEN_PREDICTIVE_FEATURES)


def _safe_rmse(y_true: pd.Series, y_pred: np.ndarray) -> float:
    try:
        return float(mean_squared_error(y_true, y_pred, squared=False))
    except TypeError:
        return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def _finite_or_none(value: float) -> float | None:
    if value is None:
        return None
    if np.isnan(value) or np.isinf(value):
        return None
    return float(value)


def _series_distribution(values: pd.Series) -> Dict[str, int]:
    return {str(key): int(val) for key, val in values.value_counts(dropna=False).to_dict().items()}


def _class_report(y_true: pd.Series, y_pred: np.ndarray) -> Dict[str, Dict[str, float]]:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=RISK_LABELS,
        zero_division=0,
    )
    return {
        label: {
            "precision": float(precision[idx]),
            "recall": float(recall[idx]),
            "f1": float(f1[idx]),
            "support": int(support[idx]),
        }
        for idx, label in enumerate(RISK_LABELS)
    }


def _evaluate_split(
    prepared: pd.DataFrame,
    feature_groups: Dict[str, List[str]],
    train_indices: pd.Index,
    test_indices: pd.Index,
    split_name: str,
) -> Dict:
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

    loss_baseline = np.full(shape=len(y_loss_test), fill_value=float(y_loss_train.mean()))
    prod_stage_mean = (
        prepared.loc[train_indices].groupby(["product", "stage_canonical"])["loss_pct"].mean().to_dict()
    )
    global_mean = float(y_loss_train.mean())
    prod_stage_baseline = np.array(
        [
            prod_stage_mean.get(
                (row["product"], row["stage_canonical"]),
                global_mean,
            )
            for _, row in prepared.loc[test_indices].iterrows()
        ],
        dtype=float,
    )
    majority_label = str(y_risk_train.mode().iloc[0])
    majority_pred = np.full(shape=len(y_risk_test), fill_value=majority_label)

    split_rows = prepared.loc[test_indices].copy()
    split_rows["predicted_loss_pct"] = loss_pred
    split_rows["actual_loss_pct"] = y_loss_test
    split_rows["abs_error"] = (split_rows["predicted_loss_pct"] - split_rows["actual_loss_pct"]).abs()
    split_rows["predicted_risk_level"] = risk_pred
    split_rows["actual_risk_level"] = y_risk_test
    split_rows["anomaly_score_raw"] = anomaly_scores
    split_rows["is_anomalous"] = anomaly_flags == -1

    preprocessor = loss_model.named_steps["preprocessor"]
    regressor = loss_model.named_steps["model"]
    feature_names = preprocessor.get_feature_names_out()
    importances = regressor.feature_importances_
    feature_importance = sorted(
        (
            {"feature": str(name), "importance": float(importance)}
            for name, importance in zip(feature_names, importances)
        ),
        key=lambda item: item["importance"],
        reverse=True,
    )

    try:
        perm = permutation_importance(
            loss_model,
            X_loss_test,
            y_loss_test,
            n_repeats=8,
            random_state=42,
            scoring="neg_mean_absolute_error",
        )
        permutation = sorted(
            (
                {"feature": str(name), "importance_mean": float(mean), "importance_std": float(std)}
                for name, mean, std in zip(regression_features, perm.importances_mean, perm.importances_std)
            ),
            key=lambda item: item["importance_mean"],
            reverse=True,
        )
    except Exception as exc:
        permutation = [{"error": f"Permutation importance unavailable: {exc}"}]

    anomaly_examples = split_rows.sort_values("anomaly_score_raw", ascending=True).head(10)
    anomaly_columns = [
        "product",
        "process_type",
        "qty_in",
        "qty_out",
        "loss_pct",
        "efficiency_pct",
        "stock_level",
        "date_ordinal",
        "anomaly_score_raw",
        "is_anomalous",
    ]
    anomaly_rows = anomaly_examples[[col for col in anomaly_columns if col in anomaly_examples.columns]].to_dict("records")

    top_errors = split_rows.sort_values("abs_error", ascending=False).head(10)
    error_columns = [
        "product",
        "process_type",
        "qty_in",
        "qty_out",
        "actual_loss_pct",
        "predicted_loss_pct",
        "abs_error",
        "actual_risk_level",
        "predicted_risk_level",
    ]
    top_error_rows = top_errors[[col for col in error_columns if col in top_errors.columns]].to_dict("records")

    threshold_risk_pred = np.array([assign_thresholded_risk_level(float(value)) for value in loss_pred])
    high_mask = y_risk_test == "high"
    false_low_high_risk_rate = (
        float(np.mean(threshold_risk_pred[high_mask] == "low")) if int(np.sum(high_mask)) > 0 else 0.0
    )

    return {
        "split_name": split_name,
        "train_rows": int(len(train_indices)),
        "test_rows": int(len(test_indices)),
        "metrics": {
            "regression_mae": float(mean_absolute_error(y_loss_test, loss_pred)),
            "regression_rmse": _safe_rmse(y_loss_test, loss_pred),
            "regression_r2": _finite_or_none(float(r2_score(y_loss_test, loss_pred))) if len(y_loss_test) > 1 else None,
            "regression_baseline_mae": float(mean_absolute_error(y_loss_test, loss_baseline)),
            "regression_baseline_rmse": _safe_rmse(y_loss_test, loss_baseline),
            "classification_accuracy": float(accuracy_score(y_risk_test, risk_pred)),
            "classification_macro_f1": float(f1_score(y_risk_test, risk_pred, average="macro")),
            "classification_weighted_f1": float(f1_score(y_risk_test, risk_pred, average="weighted")),
            "classification_majority_baseline_accuracy": float(accuracy_score(y_risk_test, majority_pred)),
            "classification_thresholded_predicted_loss_accuracy": float(accuracy_score(y_risk_test, threshold_risk_pred)),
            "classification_thresholded_predicted_loss_macro_f1": float(f1_score(y_risk_test, threshold_risk_pred, average="macro")),
            "classification_per_class": _class_report(y_risk_test, risk_pred),
            "classification_confusion_matrix": confusion_matrix(y_risk_test, risk_pred, labels=RISK_LABELS).tolist(),
            "classification_labels": list(RISK_LABELS),
            "false_low_high_risk_rate": false_low_high_risk_rate,
            "risk_thresholds_used": get_risk_thresholds(),
            "anomaly_ratio_test": float(np.mean(anomaly_scores < 0)),
            "anomaly_flag_rate_test": float(np.mean(anomaly_flags == -1)),
            "anomaly_contamination_configured": 0.08,
            "baseline_comparison_summary": {
                "model_mae": float(mean_absolute_error(y_loss_test, loss_pred)),
                "global_mean_mae": float(mean_absolute_error(y_loss_test, loss_baseline)),
                "product_stage_mean_mae": float(mean_absolute_error(y_loss_test, prod_stage_baseline)),
            },
        },
        "feature_importance_top20": feature_importance[:20],
        "permutation_importance_top20": permutation[:20],
        "top_prediction_errors": top_error_rows,
        "anomaly_examples": anomaly_rows,
    }


def _artifact_feature_consistency(prepared: pd.DataFrame) -> Dict:
    try:
        bundle = load_model_bundle()
    except Exception as exc:
        return {"bundle_loaded": False, "error": str(exc)}

    present_features = set(prepared.columns)
    required = {
        "predictive_regression_features": bundle.predictive_regression_features,
        "predictive_classification_features": bundle.predictive_classification_features,
        "assessment_anomaly_features": bundle.assessment_anomaly_features,
    }
    output = {"bundle_loaded": True, "model_version": bundle.metadata.get("model_version"), "missing_features": {}, "leakage_flags": {}}
    for key, features in required.items():
        missing = sorted(set(features) - present_features)
        output["missing_features"][key] = missing
        output["leakage_flags"][key] = sorted(set(features) & LEAKAGE_FEATURES)
    return output


def run_diagnostics(output_path: Path) -> Dict:
    db = SessionLocal()
    try:
        feature_set = build_features(db)
    finally:
        db.close()

    df = feature_set.features.copy()
    if df.empty:
        raise RuntimeError("No ML rows found. Add process step data first.")

    prepared, feature_groups = prepare_feature_frame(df)
    y_risk = prepared["loss_pct"].apply(assign_risk_level)

    train_idx_time, test_idx_time, split_details = _split_train_test_indices(prepared, test_size=0.2)
    train_idx_random, test_idx_random = train_test_split(prepared.index, test_size=0.2, random_state=42)

    predictive_leakage_flags = sorted(set(feature_groups["predictive_regression_features"]) & LEAKAGE_FEATURES)
    duplicate_rows = int(prepared.duplicated().sum())
    canonical_stage = df["process_type"].apply(normalize_stage)
    unknown_stage_count = int((canonical_stage == "unknown").sum())

    recommendation_rows = []
    for _, row in prepared.iterrows():
        loss_pct = float(row["loss_pct"])
        recommendation = build_recommendation(
            {
                "critical_stage": row["process_type"],
                "risk_level": assign_risk_level(loss_pct),
                "predicted_loss_pct": loss_pct,
                "is_anomalous": False,
                "top_signals": [NORMAL_PERFORMANCE_SIGNAL],
            }
        )
        recommendation_rows.append(
            {
                "stage_canonical": recommendation.get("stage_canonical", normalize_stage(row["process_type"])),
                "used_fallback": bool(recommendation.get("used_fallback", False)),
                "has_actions": bool(recommendation.get("recommended_actions")),
            }
        )
    rec_df = pd.DataFrame(recommendation_rows)
    fallback_rate = float(rec_df["used_fallback"].mean()) if not rec_df.empty else 0.0
    recommendation_coverage = float(rec_df["has_actions"].mean()) if not rec_df.empty else 0.0
    stage_specific_coverage = {}
    for stage in sorted(rec_df["stage_canonical"].unique()) if not rec_df.empty else []:
        subset = rec_df[rec_df["stage_canonical"] == stage]
        stage_specific_coverage[str(stage)] = {
            "rows": int(len(subset)),
            "coverage": float(subset["has_actions"].mean()) if len(subset) else 0.0,
            "fallback_rate": float(subset["used_fallback"].mean()) if len(subset) else 0.0,
        }

    signature_cols = [col for col in feature_groups["predictive_regression_features"] if col in prepared.columns]
    train_signatures = set(prepared.loc[train_idx_time, signature_cols].astype(str).agg("|".join, axis=1).tolist())
    test_signatures = set(prepared.loc[test_idx_time, signature_cols].astype(str).agg("|".join, axis=1).tolist())
    cross_split_duplicates = int(len(train_signatures.intersection(test_signatures)))
    registry_versions = get_registry_versions()
    active_model = get_active_model_version()

    report = {
        "dataset": {
            "row_count": int(len(df)),
            "column_count": int(df.shape[1]),
            "date_min": str(pd.to_datetime(df["date"]).min().date()) if "date" in df else None,
            "date_max": str(pd.to_datetime(df["date"]).max().date()) if "date" in df else None,
            "product_distribution": _series_distribution(df["product"]),
            "stage_distribution": _series_distribution(df["process_type"]),
            "stage_distribution_canonical": _series_distribution(canonical_stage),
            "unknown_stage_count": unknown_stage_count,
            "risk_class_distribution": _series_distribution(y_risk),
            "loss_distribution_pct": {
                "min": float(df["loss_pct"].min()),
                "p25": float(df["loss_pct"].quantile(0.25)),
                "median": float(df["loss_pct"].median()),
                "p75": float(df["loss_pct"].quantile(0.75)),
                "max": float(df["loss_pct"].max()),
                "mean": float(df["loss_pct"].mean()),
                "std": float(df["loss_pct"].std(ddof=0)),
            },
            "missing_values": {str(col): int(val) for col, val in df.isna().sum().to_dict().items()},
            "duplicate_rows": duplicate_rows,
            "batch_distribution": _series_distribution(df["batch_id"].astype(str)) if "batch_id" in df.columns else {},
            "below_min_training_rows": bool(len(df) < settings.ml_min_rows),
            "ml_min_rows_required": int(settings.ml_min_rows),
        },
        "split": {
            **split_details,
            "random_train_rows": int(len(train_idx_random)),
            "random_test_rows": int(len(test_idx_random)),
            "cross_split_duplicate_signatures_time_based": cross_split_duplicates,
        },
        "leakage_checks": {
            "predictive_feature_leakage_flags": predictive_leakage_flags,
            "target_in_predictive_features": sorted(set(feature_groups["predictive_regression_features"]) & {"loss_pct"}),
            "assessment_contains_target_related_features": sorted(set(feature_groups["assessment_anomaly_features"]) & LEAKAGE_FEATURES),
        },
        "model_eval_time_split": _evaluate_split(prepared, feature_groups, train_idx_time, test_idx_time, "time_based"),
        "model_eval_random_split": _evaluate_split(prepared, feature_groups, train_idx_random, test_idx_random, "random"),
        "artifact_consistency": _artifact_feature_consistency(prepared),
        "artifact_compatibility": artifact_compatibility_status(),
        "model_registry": {
            "active_model_version": (active_model or {}).get("model_version"),
            "registered_versions": [item.get("model_version") for item in registry_versions],
            "registered_count": int(len(registry_versions)),
        },
        "recommendation_diagnostics": {
            "fallback_rate": fallback_rate,
            "recommendation_coverage": recommendation_coverage,
            "stage_specific_coverage": stage_specific_coverage,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ML diagnostics for the backend pipeline.")
    parser.add_argument(
        "--output",
        default="artifacts/ml_diagnostics.json",
        help="Output JSON path (relative to backend/ when run there).",
    )
    args = parser.parse_args()

    report = run_diagnostics(Path(args.output))
    print(f"Saved diagnostics: {args.output}")
    print(f"Rows: {report['dataset']['row_count']}")
    if report["dataset"]["below_min_training_rows"]:
        print(
            "WARNING: dataset rows below training minimum "
            f"({report['dataset']['row_count']} < {report['dataset']['ml_min_rows_required']})."
        )
    print(f"Products: {report['dataset']['product_distribution']}")
    print(f"Stages: {report['dataset']['stage_distribution']}")
    print(f"Canonical stages: {report['dataset']['stage_distribution_canonical']}")
    print(f"Unknown stage count: {report['dataset']['unknown_stage_count']}")
    print(f"Risk classes: {report['dataset']['risk_class_distribution']}")
    print(f"Time split rows: train={report['split']['train_rows']} test={report['split']['test_rows']}")
    print(
        "Time split MAE / Accuracy / Macro-F1: "
        f"{report['model_eval_time_split']['metrics']['regression_mae']:.4f} / "
        f"{report['model_eval_time_split']['metrics']['classification_accuracy']:.4f} / "
        f"{report['model_eval_time_split']['metrics']['classification_macro_f1']:.4f}"
    )
    print(
        "Random split MAE / Accuracy / Macro-F1: "
        f"{report['model_eval_random_split']['metrics']['regression_mae']:.4f} / "
        f"{report['model_eval_random_split']['metrics']['classification_accuracy']:.4f} / "
        f"{report['model_eval_random_split']['metrics']['classification_macro_f1']:.4f}"
    )
    print(f"Predictive leakage flags: {report['leakage_checks']['predictive_feature_leakage_flags']}")
    artifact_compatibility = report["artifact_compatibility"]
    print(f"Artifact compatibility: {artifact_compatibility.get('compatible')}")
    print(f"Artifact compatibility reason: {artifact_compatibility.get('reason')}")
    print(f"Artifact predictive features: {artifact_compatibility.get('predictive_regression_features')}")
    print(f"Artifact forbidden violations: {artifact_compatibility.get('forbidden_predictive_violations')}")
    rec_diag = report["recommendation_diagnostics"]
    print(f"Recommendation fallback rate: {rec_diag.get('fallback_rate'):.4f}")
    print(f"Recommendation coverage: {rec_diag.get('recommendation_coverage'):.4f}")


if __name__ == "__main__":
    main()

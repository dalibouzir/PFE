#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest, RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

SYNTHETIC_WARNING = (
    "SYNTHETIC BENCHMARK — NOT REAL APP PERFORMANCE. These metrics evaluate pipeline behavior "
    "under controlled simulated data and must not be reported as production model accuracy."
)
RISK_LABELS = ["low", "medium", "high"]


def _assign_risk(loss_pct: float) -> str:
    if loss_pct >= 18.0:
        return "high"
    if loss_pct >= 8.0:
        return "medium"
    return "low"


def _build_preprocessor(categorical_cols: List[str], numeric_cols: List[str]) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_cols),
            ("num", "passthrough", numeric_cols),
        ]
    )


def _build_pipeline(categorical_cols: List[str], numeric_cols: List[str], estimator: object) -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocessor", _build_preprocessor(categorical_cols, numeric_cols)),
            ("model", estimator),
        ]
    )


def _time_split_indices(df: pd.DataFrame, test_size: float = 0.2) -> Tuple[pd.Index, pd.Index, Dict]:
    unique_times = np.sort(df["event_time_ordinal"].dropna().unique())
    if len(unique_times) >= 2:
        split_pos = max(1, int(round(len(unique_times) * (1.0 - test_size))))
        split_pos = min(split_pos, len(unique_times) - 1)
        split_cutoff = unique_times[split_pos - 1]

        train_idx = df.index[df["event_time_ordinal"] <= split_cutoff]
        test_idx = df.index[df["event_time_ordinal"] > split_cutoff]
        if len(train_idx) > 0 and len(test_idx) > 0:
            return train_idx, test_idx, {
                "strategy": "time_based",
                "split_cutoff_event_ordinal": int(split_cutoff),
                "train_rows": int(len(train_idx)),
                "test_rows": int(len(test_idx)),
            }

    train_idx, test_idx = train_test_split(df.index, test_size=test_size, random_state=42)
    return train_idx, test_idx, {
        "strategy": "random_fallback",
        "train_rows": int(len(train_idx)),
        "test_rows": int(len(test_idx)),
    }


def _regression_baselines(frame: pd.DataFrame, train_idx: pd.Index, test_idx: pd.Index) -> Dict[str, np.ndarray]:
    train = frame.loc[train_idx]
    test = frame.loc[test_idx]

    global_mean = float(train["loss_pct"].mean())
    stage_mean_map = train.groupby("stage")["loss_pct"].mean().to_dict()
    product_stage_map = train.groupby(["product", "stage"])["loss_pct"].mean().to_dict()

    pred_global = np.full(len(test), global_mean, dtype=float)
    pred_stage = np.array([stage_mean_map.get(row["stage"], global_mean) for _, row in test.iterrows()], dtype=float)
    pred_product_stage = np.array(
        [
            product_stage_map.get(
                (row["product"], row["stage"]),
                stage_mean_map.get(row["stage"], global_mean),
            )
            for _, row in test.iterrows()
        ],
        dtype=float,
    )

    return {
        "global_mean_loss": pred_global,
        "stage_mean_loss": pred_stage,
        "product_stage_mean_loss": pred_product_stage,
    }


def _classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=RISK_LABELS,
        zero_division=0,
    )
    return {
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
    }


def _evaluate_anomaly_against_synthetic_labels(y_true: np.ndarray, y_pred_flags: np.ndarray) -> Dict:
    pred = (y_pred_flags == -1).astype(int)
    return {
        "label_type": "synthetic_anomaly_labels_only",
        "precision": float(precision_recall_fscore_support(y_true, pred, average="binary", zero_division=0)[0]),
        "recall": float(precision_recall_fscore_support(y_true, pred, average="binary", zero_division=0)[1]),
        "f1": float(precision_recall_fscore_support(y_true, pred, average="binary", zero_division=0)[2]),
        "support_positive": int(np.sum(y_true == 1)),
    }


def _evaluate_split(df: pd.DataFrame, train_idx: pd.Index, test_idx: pd.Index, split_name: str) -> Dict:
    categorical = ["product", "stage", "season", "region", "grade", "synthetic_cooperative_id"]
    numeric = [
        "stage_order",
        "qty_in",
        "humidity",
        "temperature",
        "rainfall",
        "wind_speed",
        "dew_point",
        "step_duration_minutes",
        "delay_since_previous_step_minutes",
        "cumulative_duration_before_stage",
        "missing_duration_flag",
        "event_time_ordinal",
    ]

    X_train = df.loc[train_idx, categorical + numeric]
    X_test = df.loc[test_idx, categorical + numeric]
    y_loss_train = df.loc[train_idx, "loss_pct"]
    y_loss_test = df.loc[test_idx, "loss_pct"]
    y_risk_train = df.loc[train_idx, "risk_label"]
    y_risk_test = df.loc[test_idx, "risk_label"]
    y_anom_test = df.loc[test_idx, "anomaly_label_synthetic"].to_numpy(dtype=int)

    reg_model = _build_pipeline(categorical, numeric, RandomForestRegressor(n_estimators=260, random_state=42))
    cls_model = _build_pipeline(categorical, numeric, RandomForestClassifier(n_estimators=260, random_state=42))
    anom_model = _build_pipeline(categorical, numeric, IsolationForest(n_estimators=220, random_state=42, contamination=0.08))

    reg_model.fit(X_train, y_loss_train)
    cls_model.fit(X_train, y_risk_train)
    anom_model.fit(X_train)

    pred_loss = reg_model.predict(X_test)
    pred_risk = cls_model.predict(X_test)
    pred_anom_flags = anom_model.predict(X_test)

    baselines = _regression_baselines(df, train_idx, test_idx)
    model_mae = float(mean_absolute_error(y_loss_test, pred_loss))
    baseline_metrics = {
        name: {
            "mae": float(mean_absolute_error(y_loss_test, pred_values)),
            "mae_delta_vs_model": float(mean_absolute_error(y_loss_test, pred_values) - model_mae),
        }
        for name, pred_values in baselines.items()
    }

    best_baseline_name, best_baseline_payload = min(
        baseline_metrics.items(), key=lambda item: float(item[1]["mae"])
    )

    majority_label = str(pd.Series(y_risk_train).mode().iloc[0])
    majority_pred = np.full(len(y_risk_test), majority_label)

    return {
        "split": split_name,
        "regression": {
            "model": {"mae": model_mae},
            "baselines": baseline_metrics,
            "best_baseline": {
                "name": best_baseline_name,
                "mae": float(best_baseline_payload["mae"]),
                "model_beats_baseline": bool(model_mae < float(best_baseline_payload["mae"])),
            },
        },
        "classification": {
            "model": _classification_metrics(y_risk_test.to_numpy(), pred_risk),
            "majority_baseline": _classification_metrics(y_risk_test.to_numpy(), majority_pred),
        },
        "anomaly_synthetic": _evaluate_anomaly_against_synthetic_labels(y_anom_test, pred_anom_flags),
    }


def run_synthetic_benchmark(
    *,
    dataset_csv: Path,
    output_json: Path,
    output_md: Path,
) -> Dict:
    df = pd.read_csv(dataset_csv)
    if df.empty:
        raise ValueError("Synthetic benchmark dataset is empty.")
    if "data_origin" not in df.columns or not (df["data_origin"] == "SYNTHETIC_BENCHMARK").all():
        raise ValueError("Dataset must be synthetic and include data_origin=SYNTHETIC_BENCHMARK.")

    working = df.copy()
    working["event_time"] = pd.to_datetime(working["event_time"], utc=True, errors="coerce")
    working["event_time_ordinal"] = working["event_time"].dt.date.apply(lambda d: d.toordinal() if pd.notna(d) else np.nan)
    working["step_duration_minutes"] = pd.to_numeric(working["step_duration_minutes"], errors="coerce").fillna(0.0)
    for col in [
        "stage_order",
        "qty_in",
        "loss_pct",
        "humidity",
        "temperature",
        "rainfall",
        "wind_speed",
        "dew_point",
        "delay_since_previous_step_minutes",
        "cumulative_duration_before_stage",
        "missing_duration_flag",
        "anomaly_label_synthetic",
    ]:
        working[col] = pd.to_numeric(working[col], errors="coerce").fillna(0.0)

    working["risk_label"] = working["loss_pct"].apply(_assign_risk)

    train_time_idx, test_time_idx, time_info = _time_split_indices(working, test_size=0.2)
    time_eval = _evaluate_split(working, train_time_idx, test_time_idx, split_name="time_based")

    train_rand_idx, test_rand_idx = train_test_split(working.index, test_size=0.2, random_state=42)
    rand_eval = _evaluate_split(working, train_rand_idx, test_rand_idx, split_name="random_split")

    report = {
        "warning": SYNTHETIC_WARNING,
        "source": "synthetic",
        "dataset": {
            "row_count": int(len(working)),
            "crops": sorted(str(x) for x in working["product"].dropna().unique().tolist()),
            "stages": sorted(str(x) for x in working["stage"].dropna().unique().tolist()),
            "seasons": sorted(str(x) for x in working["season"].dropna().unique().tolist()),
            "regions": sorted(str(x) for x in working["region"].dropna().unique().tolist()),
            "data_origin": "SYNTHETIC_BENCHMARK",
        },
        "generation_and_noise_assumptions": {
            "drying_rule": "sensitive to humidity/rainfall/duration/delay",
            "sorting_rule": "depends on grade and product quality",
            "cleaning_rule": "moderate loss profile",
            "packaging_rule": "mostly low loss profile",
            "mango_rule": "higher sensitivity to humidity and delay",
            "noise": "gaussian and random shocks",
            "anomalies": "explicitly injected and labeled as synthetic",
        },
        "split_info": {
            "time_split": time_info,
            "random_split": {
                "strategy": "random_80_20",
                "train_rows": int(len(train_rand_idx)),
                "test_rows": int(len(test_rand_idx)),
            },
        },
        "evaluation": {
            "time_based": time_eval,
            "random_split": rand_eval,
        },
        "promotion_policy": "synthetic benchmark is not used for production promotion",
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2))

    lines = [
        f"# {SYNTHETIC_WARNING}",
        "",
        "## Dataset",
        f"- Source: synthetic",
        f"- Row count: {report['dataset']['row_count']}",
        f"- Crops: {', '.join(report['dataset']['crops'])}",
        f"- Stages: {', '.join(report['dataset']['stages'])}",
        f"- Data origin: {report['dataset']['data_origin']}",
        "",
        "## Generation Assumptions",
        f"- Drying sensitivity: {report['generation_and_noise_assumptions']['drying_rule']}",
        f"- Sorting sensitivity: {report['generation_and_noise_assumptions']['sorting_rule']}",
        f"- Noise: {report['generation_and_noise_assumptions']['noise']}",
        f"- Anomalies: {report['generation_and_noise_assumptions']['anomalies']}",
        "",
        "## Time Split (Primary)",
        f"- Regression MAE (model): {report['evaluation']['time_based']['regression']['model']['mae']:.4f}",
        f"- Best baseline: {report['evaluation']['time_based']['regression']['best_baseline']['name']} "
        f"(MAE {report['evaluation']['time_based']['regression']['best_baseline']['mae']:.4f})",
        f"- Model beats best baseline: {report['evaluation']['time_based']['regression']['best_baseline']['model_beats_baseline']}",
        f"- Classification macro-F1 (model): {report['evaluation']['time_based']['classification']['model']['macro_f1']:.4f}",
        f"- Classification macro-F1 (majority baseline): {report['evaluation']['time_based']['classification']['majority_baseline']['macro_f1']:.4f}",
        "",
        "## Random Split (Secondary)",
        f"- Regression MAE (model): {report['evaluation']['random_split']['regression']['model']['mae']:.4f}",
        f"- Classification macro-F1 (model): {report['evaluation']['random_split']['classification']['model']['macro_f1']:.4f}",
        "",
        "## Anomaly Metrics (Synthetic Labels Only)",
        f"- Label type: {report['evaluation']['time_based']['anomaly_synthetic']['label_type']}",
        f"- Precision: {report['evaluation']['time_based']['anomaly_synthetic']['precision']:.4f}",
        f"- Recall: {report['evaluation']['time_based']['anomaly_synthetic']['recall']:.4f}",
        f"- F1: {report['evaluation']['time_based']['anomaly_synthetic']['f1']:.4f}",
        "",
        "## Scope Boundary",
        "- Not mixed with Supabase app data.",
        "- Not used for production promotion.",
        "- Not a substitute for real app deployment evidence.",
    ]
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines) + "\n")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ML on synthetic post-harvest benchmark only.")
    parser.add_argument(
        "--dataset-csv",
        default="backend/artifacts/synthetic_postharvest_benchmark.csv",
        help="Synthetic dataset CSV path.",
    )
    parser.add_argument(
        "--output-json",
        default="backend/reports/ml_synthetic_benchmark_report.json",
        help="Output JSON report path.",
    )
    parser.add_argument(
        "--output-md",
        default="backend/reports/ml_synthetic_benchmark_report.md",
        help="Output Markdown report path.",
    )
    args = parser.parse_args()

    report = run_synthetic_benchmark(
        dataset_csv=Path(args.dataset_csv),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
    )
    print(f"Saved synthetic benchmark JSON report: {args.output_json}")
    print(f"Saved synthetic benchmark Markdown report: {args.output_md}")
    print(f"Synthetic dataset rows: {report['dataset']['row_count']}")


if __name__ == "__main__":
    main()

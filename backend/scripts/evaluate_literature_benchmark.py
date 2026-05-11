#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.ml.utils.feature_prep import (
    FORBIDDEN_PREDICTIVE_FEATURES,
    assign_risk_level,
    forbidden_predictive_violations,
    prepare_feature_frame,
)
from app.ml.utils.stage_normalization import normalize_stage
from app.ml.training.trainer import _split_train_test_indices
from scripts.build_literature_benchmark_dataset import BENCHMARK_MARKER, build_dataset
from scripts.evaluate_ml_models import _distribution, _evaluate_split


def _season_for_month(month: int) -> str:
    if month in {11, 12, 1, 2}:
        return "dry"
    if month in {3, 4, 5}:
        return "hot"
    return "rainy"


def _engineer_from_benchmark(df: pd.DataFrame) -> pd.DataFrame:
    working = df.copy()
    working["date"] = pd.to_datetime(working["date"])  # type: ignore[assignment]
    working = working.sort_values(["date", "batch_id"], ascending=True).reset_index(drop=True)

    qty_in = pd.to_numeric(working["qty_in"], errors="coerce").fillna(0.0)
    qty_out = pd.to_numeric(working["qty_out"], errors="coerce").fillna(0.0)
    valid_input = qty_in > 0

    working["loss_pct"] = np.where(valid_input, ((qty_in - qty_out) / qty_in) * 100.0, 0.0)
    working["loss_pct"] = pd.Series(working["loss_pct"]).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0.0)
    working["efficiency_pct"] = np.where(valid_input, qty_out / qty_in, 0.0)
    working["efficiency_pct"] = pd.Series(working["efficiency_pct"]).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0.0)

    working["month"] = working["date"].dt.month
    working["week_of_year"] = working["date"].dt.isocalendar().week.astype(int)
    working["season"] = working["month"].apply(_season_for_month)
    working["stage_canonical"] = working["process_type"].apply(normalize_stage)
    working["stage_order"] = working["stage_canonical"].map(
        {"cleaning": 1, "drying": 2, "sorting": 3, "packaging": 4}
    ).fillna(0).astype(int)
    working["is_drying_stage"] = (working["stage_canonical"] == "drying").astype(int)
    working["is_sorting_stage"] = (working["stage_canonical"] == "sorting").astype(int)
    working["is_packaging_stage"] = (working["stage_canonical"] == "packaging").astype(int)

    batch_size = pd.to_numeric(working["batch_size"], errors="coerce").fillna(0.0)
    stock_level = pd.to_numeric(working["stock_level"], errors="coerce").fillna(0.0)
    working["stock_pressure_ratio"] = np.where(batch_size > 0, stock_level / batch_size, 0.0)
    working["stock_pressure_ratio"] = pd.to_numeric(working["stock_pressure_ratio"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    working["qty_in_log"] = np.log1p(qty_in.clip(lower=0.0))
    working["batch_size_log"] = np.log1p(batch_size.clip(lower=0.0))

    working["product_stage_key"] = (
        working["product"].astype(str).str.lower().str.strip()
        + "|"
        + working["stage_canonical"].astype(str).str.lower().str.strip()
    )

    working["historical_avg_loss_same_product"] = (
        working.groupby("product")["loss_pct"].expanding().mean().shift(1).reset_index(level=0, drop=True)
    )
    working["historical_avg_loss_same_stage"] = (
        working.groupby("process_type")["loss_pct"].expanding().mean().shift(1).reset_index(level=0, drop=True)
    )
    working["historical_avg_efficiency_same_stage"] = (
        working.groupby("process_type")["efficiency_pct"].expanding().mean().shift(1).reset_index(level=0, drop=True)
    )
    working["product_stage_historical_avg_loss"] = (
        working.groupby("product_stage_key")["loss_pct"].expanding().mean().shift(1).reset_index(level=0, drop=True)
    )
    working["product_stage_historical_median_loss"] = (
        working.groupby("product_stage_key")["loss_pct"].expanding().median().shift(1).reset_index(level=0, drop=True)
    )
    working["product_stage_rolling_loss_last_5"] = (
        working.groupby("product_stage_key")["loss_pct"]
        .rolling(5, min_periods=1)
        .mean()
        .shift(1)
        .reset_index(level=0, drop=True)
    )
    working["product_stage_rolling_loss_last_10"] = (
        working.groupby("product_stage_key")["loss_pct"]
        .rolling(10, min_periods=1)
        .mean()
        .shift(1)
        .reset_index(level=0, drop=True)
    )
    working["stage_season_avg_loss"] = (
        working.groupby(["stage_canonical", "season"])["loss_pct"]
        .expanding()
        .mean()
        .shift(1)
        .reset_index(level=[0, 1], drop=True)
    )
    working["product_stage_season_avg_loss"] = (
        working.groupby(["product_stage_key", "season"])["loss_pct"]
        .expanding()
        .mean()
        .shift(1)
        .reset_index(level=[0, 1], drop=True)
    )
    working["loss_volatility_product_stage"] = (
        working.groupby("product_stage_key")["loss_pct"]
        .rolling(5, min_periods=3)
        .std()
        .shift(1)
        .reset_index(level=0, drop=True)
    )

    working["deviation_from_stage_avg"] = working["loss_pct"] - working["historical_avg_loss_same_stage"]

    batch_summary = (
        working.groupby(["batch_id", "product"])
        .agg(
            batch_loss=("loss_pct", "mean"),
            batch_efficiency=("efficiency_pct", "mean"),
            batch_date=("date", "max"),
        )
        .reset_index()
        .sort_values(["product", "batch_date"], ascending=True)
    )
    batch_summary["previous_batch_loss"] = batch_summary.groupby("product")["batch_loss"].shift(1)
    batch_summary["days_since_previous_batch"] = batch_summary.groupby("product")["batch_date"].diff().dt.days
    batch_summary["rolling_loss_last_n_batches"] = (
        batch_summary.groupby("product")["batch_loss"]
        .rolling(settings.ml_rolling_window, min_periods=1)
        .mean()
        .shift(1)
        .reset_index(level=0, drop=True)
    )
    batch_summary["rolling_efficiency_last_n_batches"] = (
        batch_summary.groupby("product")["batch_efficiency"]
        .rolling(settings.ml_rolling_window, min_periods=1)
        .mean()
        .shift(1)
        .reset_index(level=0, drop=True)
    )

    working = working.merge(
        batch_summary[
            [
                "batch_id",
                "previous_batch_loss",
                "days_since_previous_batch",
                "rolling_loss_last_n_batches",
                "rolling_efficiency_last_n_batches",
            ]
        ],
        on="batch_id",
        how="left",
    )

    default_loss_pct = float(settings.step_loss_threshold)
    default_eff = max(0.0, 1.0 - default_loss_pct / 100.0)
    working = working.fillna(
        {
            "historical_avg_loss_same_product": default_loss_pct,
            "historical_avg_loss_same_stage": default_loss_pct,
            "historical_avg_efficiency_same_stage": default_eff,
            "product_stage_historical_avg_loss": default_loss_pct,
            "product_stage_historical_median_loss": default_loss_pct,
            "product_stage_rolling_loss_last_5": default_loss_pct,
            "product_stage_rolling_loss_last_10": default_loss_pct,
            "stage_season_avg_loss": default_loss_pct,
            "product_stage_season_avg_loss": default_loss_pct,
            "loss_volatility_product_stage": 0.0,
            "deviation_from_stage_avg": 0.0,
            "previous_batch_loss": default_loss_pct,
            "days_since_previous_batch": 0.0,
            "rolling_loss_last_n_batches": default_loss_pct,
            "rolling_efficiency_last_n_batches": default_eff,
        }
    )

    return working


def _load_current_report(path: Path) -> Dict:
    if not path.exists():
        return {"available": False, "note": f"Current demo/app report not found at {path}"}
    payload = json.loads(path.read_text())
    time_eval = payload["evaluation"]["time_based"]
    return {
        "available": True,
        "path": str(path),
        "row_count": payload["dataset"]["row_count"],
        "regression_mae": time_eval["regression"]["model"]["mae"],
        "regression_rmse": time_eval["regression"]["model"]["rmse"],
        "regression_r2": time_eval["regression"]["model"]["r2"],
        "classification_macro_f1": time_eval["classification"]["model"]["macro_f1"],
        "classification_medium_recall": time_eval["classification"]["model"]["medium_recall"],
        "classification_high_recall": time_eval["classification"]["model"]["high_recall"],
        "classification_false_low_high_risk_rate": time_eval["classification"]["model"]["false_low_high_risk_rate"],
        "baseline_stage_mean_mae": time_eval["regression"]["baselines"]["stage_mean_loss"]["mae"],
        "baseline_product_stage_mean_mae": time_eval["regression"]["baselines"]["product_stage_mean_loss"]["mae"],
    }


def _summarize_baseline_wins(time_eval: Dict) -> Dict:
    model_mae = float(time_eval["regression"]["model"]["mae"])
    wins: List[str] = []
    losses: List[str] = []
    for name, baseline in time_eval["regression"]["baselines"].items():
        baseline_mae = float(baseline["mae"])
        if model_mae < baseline_mae:
            wins.append(name)
        else:
            losses.append(name)
    return {"model_mae": model_mae, "beats": wins, "loses_to": losses}


def run_literature_benchmark(
    dataset_csv: Path,
    output_json: Path,
    output_md: Path,
    comparison_md: Path,
    current_demo_report: Path,
    target_rows: int,
    seed: int,
) -> Dict:
    if not dataset_csv.exists():
        build_dataset(
            output_csv=dataset_csv,
            output_metadata=dataset_csv.parent / "literature_benchmark_metadata.json",
            output_methodology=dataset_csv.parent / "literature_benchmark_methodology.md",
            target_rows=max(3000, target_rows),
            seed=seed,
        )

    raw = pd.read_csv(dataset_csv)
    engineered = _engineer_from_benchmark(raw)
    prepared, feature_groups = prepare_feature_frame(engineered)

    regression_violations = forbidden_predictive_violations(feature_groups["predictive_regression_features"])
    classification_violations = forbidden_predictive_violations(feature_groups["predictive_classification_features"])

    train_idx_time, test_idx_time, split_details = _split_train_test_indices(prepared, test_size=0.2)
    train_idx_rand, test_idx_rand = train_test_split(prepared.index, test_size=0.2, random_state=42)

    report = {
        "purpose": "Literature-informed benchmark evaluation (not production accuracy).",
        "dataset": {
            "dataset_marker": BENCHMARK_MARKER,
            "row_count": int(len(prepared)),
            "product_distribution": _distribution(prepared["product"]),
            "stage_distribution_raw": _distribution(prepared["process_type"]),
            "stage_distribution_canonical": _distribution(prepared["stage_canonical"]),
            "risk_class_distribution": _distribution(prepared["loss_pct"].apply(assign_risk_level)),
            "loss_distribution": {
                "mean": float(prepared["loss_pct"].mean()),
                "median": float(prepared["loss_pct"].median()),
                "p90": float(prepared["loss_pct"].quantile(0.90)),
                "p95": float(prepared["loss_pct"].quantile(0.95)),
                "max": float(prepared["loss_pct"].max()),
            },
        },
        "predictive_contract": {
            "forbidden_predictive_features": sorted(FORBIDDEN_PREDICTIVE_FEATURES),
            "regression_violations": regression_violations,
            "classification_violations": classification_violations,
            "predictive_features_clean": len(regression_violations) == 0 and len(classification_violations) == 0,
        },
        "split_details": {
            "time_based": split_details,
            "random": {"train_rows": int(len(train_idx_rand)), "test_rows": int(len(test_idx_rand))},
        },
        "evaluation": {
            "time_based": _evaluate_split(prepared, feature_groups, train_idx_time, test_idx_time, "time_based"),
            "random_split": _evaluate_split(prepared, feature_groups, train_idx_rand, test_idx_rand, "random"),
        },
    }

    report["baseline_summary"] = _summarize_baseline_wins(report["evaluation"]["time_based"])
    report["current_demo_app_reference"] = _load_current_report(current_demo_report)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    _write_markdown_report(report, output_md)
    _write_comparison_report(report, comparison_md)
    return report


def _write_markdown_report(report: Dict, output_md: Path) -> None:
    time_eval = report["evaluation"]["time_based"]
    lines: List[str] = []
    lines.append("# Literature-Informed Benchmark Evaluation")
    lines.append("")
    lines.append("## Purpose")
    lines.append("This benchmark tests model potential under source-informed post-harvest distributions.")
    lines.append("It does NOT represent real cooperative operational accuracy.")
    lines.append("")
    lines.append("## Benchmark Dataset Summary")
    lines.append(f"- Rows: {report['dataset']['row_count']}")
    lines.append(f"- Product distribution: {report['dataset']['product_distribution']}")
    lines.append(f"- Raw stage distribution: {report['dataset']['stage_distribution_raw']}")
    lines.append(f"- Canonical stage distribution: {report['dataset']['stage_distribution_canonical']}")
    lines.append(f"- Risk class distribution: {report['dataset']['risk_class_distribution']}")
    lines.append("")
    lines.append("## Baseline Comparison")
    lines.append(f"- Model MAE (time split): {time_eval['regression']['model']['mae']:.4f}")
    lines.append(f"- Beats baselines: {report['baseline_summary']['beats']}")
    lines.append(f"- Loses to baselines: {report['baseline_summary']['loses_to']}")
    lines.append("")
    lines.append("## Risk Detection Evaluation")
    cls_model = time_eval["classification"]["model"]
    cls_thr = time_eval["classification"]["thresholded_predicted_loss_baseline"]
    lines.append(
        f"- RF classifier macro-F1: {cls_model['macro_f1']:.4f}, medium recall: {cls_model['medium_recall']:.4f}, "
        f"high recall: {cls_model['high_recall']:.4f}"
    )
    lines.append(
        f"- Thresholded predicted-loss macro-F1: {cls_thr['macro_f1']:.4f}, false-low high-risk rate: {cls_thr['false_low_high_risk_rate']:.4f}"
    )
    lines.append("")
    lines.append("## Anomaly Review")
    lines.append("- Exploratory only: no anomaly accuracy claim (no ground-truth anomaly labels).")
    lines.append(f"- Summary: {time_eval['anomaly_review']}")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("- Results indicate architecture behavior under literature-informed benchmark conditions only.")
    lines.append("- This benchmark cannot be used as proof of production readiness or real-world accuracy.")
    lines.append("")
    lines.append("## PFE Report Wording")
    lines.append(
        "We trained and evaluated the ML pipeline on a literature-informed benchmark dataset calibrated from APHLIS, "
        "Senegal mango/groundnut references, and contextual sources. The benchmark is useful to test architecture potential "
        "under plausible distributions, but it does not replace real cooperative operational data and cannot be used to claim production accuracy."
    )
    lines.append("")

    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines))


def _write_comparison_report(report: Dict, comparison_md: Path) -> None:
    current = report.get("current_demo_app_reference", {})
    bench_time = report["evaluation"]["time_based"]
    bench_cls_model = bench_time["classification"]["model"]
    bench_cls_thr = bench_time["classification"]["thresholded_predicted_loss_baseline"]

    lines: List[str] = []
    lines.append("# Literature-Informed Benchmark Evaluation")
    lines.append("")
    lines.append("## Purpose")
    lines.append("Compare current demo/app results with benchmark-data results to isolate architecture-vs-data effects.")
    lines.append("")
    lines.append("## Sources Used")
    lines.append("See artifacts/benchmark_sources.md and artifacts/benchmark_sources.json for source mapping and reliability notes.")
    lines.append("")
    lines.append("## Dataset Methodology")
    lines.append("See artifacts/literature_benchmark_methodology.md.")
    lines.append("")
    lines.append("## Benchmark Dataset Summary")
    lines.append(f"- Rows: {report['dataset']['row_count']}")
    lines.append(f"- Risk distribution: {report['dataset']['risk_class_distribution']}")
    lines.append("")

    lines.append("## Current Demo/App Model Results")
    if current.get("available"):
        lines.append(f"- Report path: {current['path']}")
        lines.append(
            f"- Regression MAE={current['regression_mae']:.4f}, RMSE={current['regression_rmse']:.4f}, R2={current['regression_r2']}"
        )
        lines.append(
            f"- Classifier macro-F1={current['classification_macro_f1']:.4f}, medium recall={current['classification_medium_recall']:.4f}, high recall={current['classification_high_recall']:.4f}"
        )
    else:
        lines.append(f"- {current.get('note', 'Current demo/app report unavailable')}")
    lines.append("")

    lines.append("## Benchmark Model Results")
    lines.append(
        f"- Regression MAE={bench_time['regression']['model']['mae']:.4f}, RMSE={bench_time['regression']['model']['rmse']:.4f}, R2={bench_time['regression']['model']['r2']}"
    )
    lines.append(
        f"- RF classifier macro-F1={bench_cls_model['macro_f1']:.4f}, medium recall={bench_cls_model['medium_recall']:.4f}, high recall={bench_cls_model['high_recall']:.4f}"
    )
    lines.append(
        f"- Thresholded-risk macro-F1={bench_cls_thr['macro_f1']:.4f}, false-low high-risk rate={bench_cls_thr['false_low_high_risk_rate']:.4f}"
    )
    lines.append("")

    lines.append("## Baseline Comparison")
    lines.append(f"- Beats baselines: {report['baseline_summary']['beats']}")
    lines.append(f"- Loses to baselines: {report['baseline_summary']['loses_to']}")
    lines.append("")

    lines.append("## Risk Detection Evaluation")
    lines.append("- Focus metric for safety: false_low_high_risk_rate.")
    lines.append("- Served risk should remain thresholded_predicted_loss unless classifier materially improves medium/high recall.")
    lines.append("")

    lines.append("## Anomaly Review")
    lines.append("- Exploratory only; no anomaly accuracy claim without labels.")
    lines.append("")

    lines.append("## Interpretation")
    lines.append("- Architecture potential can improve under richer distributions, but this does not prove operational generalization.")
    lines.append("- Production validation still requires real cooperative data and feedback labels.")
    lines.append("- Can this benchmark be used as proof of production accuracy? NO.")
    lines.append("")

    lines.append("## PFE Report Wording")
    lines.append(
        "In addition to the app dataset, we built a literature-informed benchmark dataset from APHLIS and crop-specific references "
        "to test ML architecture behavior under realistic post-harvest distributions. Benchmark gains are informative for model potential, "
        "but they are not evidence of production accuracy because the benchmark is synthetic and not real cooperative operational history."
    )
    lines.append("")

    comparison_md.parent.mkdir(parents=True, exist_ok=True)
    comparison_md.write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ML architecture on literature-informed benchmark dataset.")
    parser.add_argument("--dataset-csv", default="artifacts/literature_benchmark_dataset.csv")
    parser.add_argument("--output-json", default="artifacts/literature_benchmark_evaluation.json")
    parser.add_argument("--output-md", default="artifacts/literature_benchmark_evaluation.md")
    parser.add_argument("--comparison-md", default="artifacts/literature_benchmark_comparison.md")
    parser.add_argument("--current-demo-report", default="artifacts/ml_evaluation_final.json")
    parser.add_argument("--target-rows", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    report = run_literature_benchmark(
        dataset_csv=Path(args.dataset_csv),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
        comparison_md=Path(args.comparison_md),
        current_demo_report=Path(args.current_demo_report),
        target_rows=args.target_rows,
        seed=args.seed,
    )

    print(f"Saved benchmark evaluation JSON: {args.output_json}")
    print(f"Saved benchmark evaluation MD: {args.output_md}")
    print(f"Saved benchmark comparison MD: {args.comparison_md}")
    print(f"Rows: {report['dataset']['row_count']}")
    print(f"Time split MAE: {report['evaluation']['time_based']['regression']['model']['mae']:.4f}")


if __name__ == "__main__":
    main()

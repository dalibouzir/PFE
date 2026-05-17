#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    GradientBoostingRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    IsolationForest,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


SYNTHETIC_OFFLINE_WARNING = (
    "SYNTHETIC OFFLINE BENCHMARK — NOT REAL APP PERFORMANCE. "
    "These results are for controlled model development only and must not be used as production accuracy claims."
)
RISK_LABELS = ["low", "medium", "high"]
SOURCE_LABEL = "SYNTHETIC_OFFLINE_BENCHMARK"
PHASE1_REFERENCE = {
    "candidate": "LogisticRegression_class_weight_balanced",
    "macro_f1": 0.5173,
    "high_risk_recall": 0.3913,
    "high_risk_precision": 0.0744,
    "false_low_high_risk_rate": 0.4783,
}
PHASE1B_REFERENCE = {
    "candidate": "Phase1B_LogRegBalanced_plus_HighOverride",
    "macro_f1": 0.4691,
    "high_risk_recall": 0.4348,
    "high_risk_precision": 0.0654,
    "false_low_high_risk_rate": 0.4783,
    "false_alarms": 143,
}


def _assign_risk(loss_pct: float) -> str:
    if loss_pct >= 18.0:
        return "high"
    if loss_pct >= 8.0:
        return "medium"
    return "low"


def _build_one_hot_encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def _build_preprocessor(categorical_cols: List[str], numeric_cols: List[str]) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("cat", _build_one_hot_encoder(), categorical_cols),
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


def _prepare_frame(dataset_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(dataset_csv)
    if df.empty:
        raise ValueError("Synthetic benchmark dataset is empty.")
    if "data_origin" not in df.columns:
        raise ValueError("Dataset must include data_origin column.")
    if not (df["data_origin"] == "SYNTHETIC_BENCHMARK").all():
        raise ValueError("Dataset must contain only SYNTHETIC_BENCHMARK rows.")

    working = df.copy()
    working["event_time"] = pd.to_datetime(working["event_time"], utc=True, errors="coerce")
    working["event_time_ordinal"] = working["event_time"].dt.date.apply(
        lambda d: d.toordinal() if pd.notna(d) else np.nan
    )

    for col in [
        "stage_order",
        "qty_in",
        "qty_out",
        "loss_qty",
        "loss_pct",
        "efficiency_pct",
        "humidity",
        "temperature",
        "rainfall",
        "wind_speed",
        "dew_point",
        "step_duration_minutes",
        "delay_since_previous_step_minutes",
        "cumulative_duration_before_stage",
        "missing_duration_flag",
        "anomaly_label_synthetic",
    ]:
        working[col] = pd.to_numeric(working[col], errors="coerce")

    working["step_duration_minutes"] = working["step_duration_minutes"].fillna(0.0)
    working["missing_duration_flag"] = working["missing_duration_flag"].fillna(1.0)
    working["delay_since_previous_step_minutes"] = working["delay_since_previous_step_minutes"].fillna(0.0)
    working["cumulative_duration_before_stage"] = working["cumulative_duration_before_stage"].fillna(0.0)
    working["event_time_ordinal"] = working["event_time_ordinal"].fillna(0.0)
    working["risk_label"] = working["loss_pct"].apply(_assign_risk)

    working["product_stage"] = (
        working["product"].astype(str).str.lower().str.strip()
        + "|"
        + working["stage"].astype(str).str.lower().str.strip()
    )
    working["grade_stage"] = (
        working["grade"].astype(str).str.upper().str.strip()
        + "|"
        + working["stage"].astype(str).str.lower().str.strip()
    )
    working["season_stage"] = (
        working["season"].astype(str).str.lower().str.strip()
        + "|"
        + working["stage"].astype(str).str.lower().str.strip()
    )
    working["humidity_stage"] = working["humidity"].fillna(0.0) * working["stage_order"].fillna(0.0)
    working["rainfall_stage"] = working["rainfall"].fillna(0.0) * working["stage_order"].fillna(0.0)
    working["duration_stage"] = working["step_duration_minutes"].fillna(0.0) * working["stage_order"].fillna(0.0)
    product_factor = working["product"].astype(str).str.lower().map({"mangue": 1.3, "arachide": 1.0, "mil": 0.9}).fillna(1.0)
    working["delay_product"] = working["delay_since_previous_step_minutes"].fillna(0.0) * product_factor
    return working


def _time_split_indices(df: pd.DataFrame, test_size: float = 0.2) -> Tuple[pd.Index, pd.Index, Dict[str, Any]]:
    unique_times = np.sort(df["event_time_ordinal"].dropna().unique())
    if len(unique_times) >= 2:
        split_pos = max(1, int(round(len(unique_times) * (1.0 - test_size))))
        split_pos = min(split_pos, len(unique_times) - 1)
        split_cutoff = unique_times[split_pos - 1]

        train_idx = df.index[df["event_time_ordinal"] <= split_cutoff]
        test_idx = df.index[df["event_time_ordinal"] > split_cutoff]
        if len(train_idx) > 0 and len(test_idx) > 0:
            train_lots = set(df.loc[train_idx, "synthetic_lot_id"].astype(str).tolist())
            test_lots = set(df.loc[test_idx, "synthetic_lot_id"].astype(str).tolist())
            return train_idx, test_idx, {
                "strategy": "time_based",
                "split_cutoff_event_ordinal": int(split_cutoff),
                "train_rows": int(len(train_idx)),
                "test_rows": int(len(test_idx)),
                "lot_overlap_count": int(len(train_lots.intersection(test_lots))),
            }

    train_idx, test_idx = train_test_split(df.index, test_size=test_size, random_state=42)
    return train_idx, test_idx, {
        "strategy": "random_fallback",
        "train_rows": int(len(train_idx)),
        "test_rows": int(len(test_idx)),
        "lot_overlap_count": 0,
    }


def _random_split_indices(df: pd.DataFrame, test_size: float = 0.2) -> Tuple[pd.Index, pd.Index, Dict[str, Any]]:
    train_idx, test_idx = train_test_split(df.index, test_size=test_size, random_state=42)
    return train_idx, test_idx, {
        "strategy": "random_80_20",
        "train_rows": int(len(train_idx)),
        "test_rows": int(len(test_idx)),
    }


def _grouped_lot_time_split_indices(df: pd.DataFrame, test_size: float = 0.2) -> Optional[Tuple[pd.Index, pd.Index, Dict[str, Any]]]:
    if "synthetic_lot_id" not in df.columns:
        return None
    lot_summary = (
        df.groupby("synthetic_lot_id", dropna=False)["event_time_ordinal"]
        .max()
        .reset_index()
        .sort_values("event_time_ordinal", ascending=True)
    )
    if len(lot_summary) < 2:
        return None
    split_pos = max(1, int(round(len(lot_summary) * (1.0 - test_size))))
    split_pos = min(split_pos, len(lot_summary) - 1)
    train_lots = set(lot_summary.iloc[:split_pos]["synthetic_lot_id"].astype(str).tolist())
    test_lots = set(lot_summary.iloc[split_pos:]["synthetic_lot_id"].astype(str).tolist())
    train_idx = df.index[df["synthetic_lot_id"].astype(str).isin(train_lots)]
    test_idx = df.index[df["synthetic_lot_id"].astype(str).isin(test_lots)]
    if len(train_idx) == 0 or len(test_idx) == 0:
        return None
    return train_idx, test_idx, {
        "strategy": "grouped_lot_time",
        "train_rows": int(len(train_idx)),
        "test_rows": int(len(test_idx)),
        "train_lots": int(len(train_lots)),
        "test_lots": int(len(test_lots)),
        "lot_overlap_count": 0,
    }


def _regression_baselines(
    frame: pd.DataFrame, train_idx: pd.Index, test_idx: pd.Index
) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]:
    train = frame.loc[train_idx]
    test = frame.loc[test_idx]

    global_mean = float(train["loss_pct"].mean())
    stage_map = train.groupby("stage")["loss_pct"].mean().to_dict()
    product_stage_map = train.groupby(["product", "stage"])["loss_pct"].mean().to_dict()
    stage_season_map = train.groupby(["stage", "season"])["loss_pct"].mean().to_dict()
    product_stage_season_map = train.groupby(["product", "stage", "season"])["loss_pct"].mean().to_dict()

    def _pred(rows: pd.DataFrame) -> Dict[str, np.ndarray]:
        pred_global = np.full(len(rows), global_mean, dtype=float)
        pred_stage = np.array([stage_map.get(row["stage"], global_mean) for _, row in rows.iterrows()], dtype=float)
        pred_product_stage = np.array(
            [
                product_stage_map.get(
                    (row["product"], row["stage"]),
                    stage_map.get(row["stage"], global_mean),
                )
                for _, row in rows.iterrows()
            ],
            dtype=float,
        )
        pred_stage_season = np.array(
            [
                stage_season_map.get(
                    (row["stage"], row["season"]),
                    stage_map.get(row["stage"], global_mean),
                )
                for _, row in rows.iterrows()
            ],
            dtype=float,
        )
        pred_product_stage_season = np.array(
            [
                product_stage_season_map.get(
                    (row["product"], row["stage"], row["season"]),
                    stage_season_map.get(
                        (row["stage"], row["season"]),
                        stage_map.get(row["stage"], global_mean),
                    ),
                )
                for _, row in rows.iterrows()
            ],
            dtype=float,
        )
        return {
            "global_mean_loss": pred_global,
            "stage_mean_loss": pred_stage,
            "product_stage_mean_loss": pred_product_stage,
            "stage_season_mean_loss": pred_stage_season,
            "product_stage_season_mean_loss": pred_product_stage_season,
        }

    return _pred(train), _pred(test)


def _regression_candidate_predictions(
    frame: pd.DataFrame,
    train_idx: pd.Index,
    test_idx: pd.Index,
    categorical_cols: List[str],
    numeric_cols: List[str],
    baseline_train_pred: Dict[str, np.ndarray],
    baseline_test_pred: Dict[str, np.ndarray],
) -> Dict[str, np.ndarray]:
    train = frame.loc[train_idx]
    test = frame.loc[test_idx]
    X_train = train[categorical_cols + numeric_cols]
    X_test = test[categorical_cols + numeric_cols]
    y_train = train["loss_pct"].to_numpy(dtype=float)

    rf = _build_pipeline(
        categorical_cols,
        numeric_cols,
        RandomForestRegressor(n_estimators=260, random_state=42),
    )
    gbr = _build_pipeline(
        categorical_cols,
        numeric_cols,
        GradientBoostingRegressor(random_state=42),
    )
    hgb = _build_pipeline(
        categorical_cols,
        numeric_cols,
        HistGradientBoostingRegressor(random_state=42),
    )

    rf.fit(X_train, y_train)
    gbr.fit(X_train, y_train)
    hgb.fit(X_train, y_train)

    preds: Dict[str, np.ndarray] = {
        "RandomForestRegressor": rf.predict(X_test),
        "GradientBoostingRegressor": gbr.predict(X_test),
        "HistGradientBoostingRegressor": hgb.predict(X_test),
    }

    # Stage-specific regressors
    stage_pred = np.full(len(test), float(y_train.mean()), dtype=float)
    for stage_name in sorted(train["stage"].dropna().astype(str).unique().tolist()):
        stage_train = train[train["stage"].astype(str) == stage_name]
        stage_test_idx = test.index[test["stage"].astype(str) == stage_name]
        if len(stage_test_idx) == 0:
            continue
        if len(stage_train) < 20:
            fallback = float(stage_train["loss_pct"].mean()) if len(stage_train) else float(y_train.mean())
            stage_pred[test.index.get_indexer(stage_test_idx)] = fallback
            continue
        stage_model = _build_pipeline(
            categorical_cols,
            numeric_cols,
            HistGradientBoostingRegressor(random_state=42),
        )
        stage_model.fit(
            stage_train[categorical_cols + numeric_cols],
            stage_train["loss_pct"].to_numpy(dtype=float),
        )
        stage_pred[test.index.get_indexer(stage_test_idx)] = stage_model.predict(
            test.loc[stage_test_idx, categorical_cols + numeric_cols]
        )
    preds["StageSpecificHistGradientBoostingRegressor"] = stage_pred

    # Product-stage-specific regressors.
    product_stage_pred = np.full(len(test), float(y_train.mean()), dtype=float)
    for ps_name in sorted(train["product_stage"].dropna().astype(str).unique().tolist()):
        ps_train = train[train["product_stage"].astype(str) == ps_name]
        ps_test_idx = test.index[test["product_stage"].astype(str) == ps_name]
        if len(ps_test_idx) == 0:
            continue
        if len(ps_train) < 30:
            fallback = float(ps_train["loss_pct"].mean()) if len(ps_train) else float(y_train.mean())
            product_stage_pred[test.index.get_indexer(ps_test_idx)] = fallback
            continue
        ps_model = _build_pipeline(
            categorical_cols,
            numeric_cols,
            HistGradientBoostingRegressor(random_state=42),
        )
        ps_model.fit(
            ps_train[categorical_cols + numeric_cols],
            ps_train["loss_pct"].to_numpy(dtype=float),
        )
        product_stage_pred[test.index.get_indexer(ps_test_idx)] = ps_model.predict(
            test.loc[ps_test_idx, categorical_cols + numeric_cols]
        )
    preds["ProductStageSpecificHistGradientBoostingRegressor"] = product_stage_pred

    # Residual-on-best-baseline
    baseline_test_mae = {
        name: float(mean_absolute_error(test["loss_pct"].to_numpy(dtype=float), values))
        for name, values in baseline_test_pred.items()
    }
    selected_baseline = min(baseline_test_mae.items(), key=lambda item: item[1])[0]
    residual_target = y_train - baseline_train_pred[selected_baseline]
    residual_model = _build_pipeline(
        categorical_cols,
        numeric_cols,
        HistGradientBoostingRegressor(random_state=42),
    )
    residual_model.fit(X_train, residual_target)
    residual_test_pred = residual_model.predict(X_test)
    preds["ResidualOnBestBaselineRegressor"] = baseline_test_pred[selected_baseline] + residual_test_pred

    # Residual on stage-season baseline (fixed reference).
    if "stage_season_mean_loss" in baseline_train_pred and "stage_season_mean_loss" in baseline_test_pred:
        residual_stage_season = y_train - baseline_train_pred["stage_season_mean_loss"]
        residual_stage_season_model = _build_pipeline(
            categorical_cols,
            numeric_cols,
            HistGradientBoostingRegressor(random_state=42),
        )
        residual_stage_season_model.fit(X_train, residual_stage_season)
        preds["ResidualOnStageSeasonBaselineRegressor"] = (
            baseline_test_pred["stage_season_mean_loss"] + residual_stage_season_model.predict(X_test)
        )

    # Weather/duration-focused residual model.
    focused_numeric_cols = [
        "humidity",
        "temperature",
        "rainfall",
        "wind_speed",
        "dew_point",
        "step_duration_minutes",
        "delay_since_previous_step_minutes",
        "cumulative_duration_before_stage",
        "missing_duration_flag",
        "humidity_stage",
        "rainfall_stage",
        "duration_stage",
        "delay_product",
        "stage_order",
    ]
    focused_categorical_cols = ["stage", "product", "season", "grade", "product_stage", "season_stage"]
    focused_X_train = train[focused_categorical_cols + focused_numeric_cols]
    focused_X_test = test[focused_categorical_cols + focused_numeric_cols]
    if "stage_season_mean_loss" in baseline_train_pred and "stage_season_mean_loss" in baseline_test_pred:
        focused_residual = y_train - baseline_train_pred["stage_season_mean_loss"]
        focused_model = _build_pipeline(
            focused_categorical_cols,
            focused_numeric_cols,
            GradientBoostingRegressor(random_state=42),
        )
        focused_model.fit(focused_X_train, focused_residual)
        preds["WeatherDurationResidualOnStageSeason"] = (
            baseline_test_pred["stage_season_mean_loss"] + focused_model.predict(focused_X_test)
        )
    return preds


def _per_group_mae(y_true: np.ndarray, y_pred: np.ndarray, keys: pd.Series) -> Dict[str, float]:
    out: Dict[str, float] = {}
    tmp = pd.DataFrame({"key": keys.astype(str), "y": y_true, "pred": y_pred})
    for key, group in tmp.groupby("key"):
        out[str(key)] = float(mean_absolute_error(group["y"], group["pred"]))
    return out


def _evaluate_regression_split(
    frame: pd.DataFrame,
    train_idx: pd.Index,
    test_idx: pd.Index,
    split_name: str,
    categorical_cols: List[str],
    numeric_cols: List[str],
) -> Dict[str, Any]:
    train = frame.loc[train_idx]
    test = frame.loc[test_idx]
    y_test = test["loss_pct"].to_numpy(dtype=float)

    baseline_train_pred, baseline_test_pred = _regression_baselines(frame, train_idx, test_idx)
    candidate_preds = _regression_candidate_predictions(
        frame,
        train_idx,
        test_idx,
        categorical_cols=categorical_cols,
        numeric_cols=numeric_cols,
        baseline_train_pred=baseline_train_pred,
        baseline_test_pred=baseline_test_pred,
    )

    # Baselines included in ranking table.
    for base_name, base_pred in baseline_test_pred.items():
        candidate_preds[base_name] = base_pred

    baseline_mae = {
        name: float(mean_absolute_error(y_test, pred))
        for name, pred in baseline_test_pred.items()
    }
    best_baseline_name, best_baseline_mae = min(baseline_mae.items(), key=lambda item: item[1])

    rows: List[Dict[str, Any]] = []
    stage_baseline_map = train.groupby("stage")["loss_pct"].mean().to_dict()
    sechage_baseline_mae = None
    sechage_mask = test["stage"].astype(str) == "sechage"
    if int(sechage_mask.sum()) > 0:
        sechage_truth = test.loc[sechage_mask, "loss_pct"].to_numpy(dtype=float)
        sechage_baseline_pred = np.array(
            [stage_baseline_map.get("sechage", float(train["loss_pct"].mean()))] * len(sechage_truth),
            dtype=float,
        )
        sechage_baseline_mae = float(mean_absolute_error(sechage_truth, sechage_baseline_pred))

    for candidate_name, pred in candidate_preds.items():
        mae = float(mean_absolute_error(y_test, pred))
        improvement_pct = float(((best_baseline_mae - mae) / best_baseline_mae) * 100.0) if best_baseline_mae > 0 else 0.0
        per_stage = _per_group_mae(y_test, pred, test["stage"])
        per_product = _per_group_mae(y_test, pred, test["product"])
        sechage_mae = per_stage.get("sechage")
        sechage_beats_baseline = (
            bool(sechage_mae < sechage_baseline_mae)
            if (sechage_mae is not None and sechage_baseline_mae is not None)
            else None
        )
        gate_pass = bool(improvement_pct >= 10.0 and sechage_beats_baseline is True)

        rows.append(
            {
                "candidate": candidate_name,
                "split": split_name,
                "mae": mae,
                "best_baseline_name": best_baseline_name,
                "best_baseline_mae": float(best_baseline_mae),
                "beats_best_baseline": bool(mae < best_baseline_mae),
                "relative_improvement_pct_vs_best_baseline": improvement_pct,
                "gate_pass": gate_pass,
                "sechage_mae": sechage_mae,
                "sechage_baseline_mae": sechage_baseline_mae,
                "sechage_beats_stage_baseline": sechage_beats_baseline,
                "per_stage_mae": per_stage,
                "per_product_mae": per_product,
            }
        )

    ranked = sorted(rows, key=lambda row: row["mae"])
    return {
        "split": split_name,
        "best_baseline": {"name": best_baseline_name, "mae": float(best_baseline_mae)},
        "candidates_ranked": ranked,
        "any_gate_passed": bool(any(row["gate_pass"] for row in ranked)),
    }


def _classification_metrics(y_true: np.ndarray, y_pred: np.ndarray, *, groups: Optional[pd.Series] = None) -> Dict[str, Any]:
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=RISK_LABELS,
        zero_division=0,
    )
    per_class = {
        label: {
            "precision": float(precision[idx]),
            "recall": float(recall[idx]),
            "f1": float(f1[idx]),
            "support": int(support[idx]),
        }
        for idx, label in enumerate(RISK_LABELS)
    }
    high_support = int(np.sum(y_true == "high"))
    false_low_count = int(np.sum((y_true == "high") & (y_pred == "low")))
    false_low_rate = float(false_low_count / high_support) if high_support > 0 else 0.0

    payload: Dict[str, Any] = {
        "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted")),
        "per_class": per_class,
        "high_risk_recall": float(per_class["high"]["recall"]),
        "high_risk_precision": float(per_class["high"]["precision"]),
        "false_low_high_risk_rate": false_low_rate,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=RISK_LABELS).tolist(),
        "labels": list(RISK_LABELS),
    }

    if groups is not None:
        per_group_macro_f1: Dict[str, float] = {}
        temp = pd.DataFrame({"group": groups.astype(str), "y_true": y_true, "y_pred": y_pred})
        for group_key, subset in temp.groupby("group"):
            per_group_macro_f1[str(group_key)] = float(
                f1_score(subset["y_true"], subset["y_pred"], labels=RISK_LABELS, average="macro", zero_division=0)
            )
        payload["per_group_macro_f1"] = per_group_macro_f1
    return payload


def _high_risk_recall_by_group(y_true: np.ndarray, y_pred: np.ndarray, groups: pd.Series) -> Dict[str, float]:
    out: Dict[str, float] = {}
    frame = pd.DataFrame({"group": groups.astype(str), "y_true": y_true, "y_pred": y_pred})
    for group_key, subset in frame.groupby("group"):
        support = int(np.sum(subset["y_true"] == "high"))
        if support == 0:
            out[str(group_key)] = 0.0
            continue
        recall = float(np.mean(subset.loc[subset["y_true"] == "high", "y_pred"] == "high"))
        out[str(group_key)] = recall
    return out


def _pareto_frontier(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def dominates(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        ge_all = (
            float(a["macro_f1"]) >= float(b["macro_f1"])
            and float(a["high_risk_recall"]) >= float(b["high_risk_recall"])
            and float(a["high_risk_precision"]) >= float(b["high_risk_precision"])
            and int(a["false_alarms_count"]) <= int(b["false_alarms_count"])
        )
        strict_any = (
            float(a["macro_f1"]) > float(b["macro_f1"])
            or float(a["high_risk_recall"]) > float(b["high_risk_recall"])
            or float(a["high_risk_precision"]) > float(b["high_risk_precision"])
            or int(a["false_alarms_count"]) < int(b["false_alarms_count"])
        )
        return ge_all and strict_any

    frontier: List[Dict[str, Any]] = []
    for i, row in enumerate(rows):
        dominated = False
        for j, other in enumerate(rows):
            if i == j:
                continue
            if dominates(other, row):
                dominated = True
                break
        if not dominated:
            frontier.append(row)
    return sorted(
        frontier,
        key=lambda row: (
            row["high_risk_recall"],
            row["macro_f1"],
            row["high_risk_precision"],
            -row["false_alarms_count"],
        ),
        reverse=True,
    )


def _phase1c_final_decision(
    *,
    best_prediction: Optional[Dict[str, Any]],
    current_reference_false_low: float,
) -> Dict[str, Any]:
    if not best_prediction:
        return {"decision": "FAIL", "reason": "no_prediction_mode_candidate"}

    pass_condition = bool(
        float(best_prediction["high_risk_recall"]) >= 0.40
        and float(best_prediction["macro_f1"]) >= 0.50
        and float(best_prediction["false_low_high_risk_rate"]) < float(current_reference_false_low)
        and int(best_prediction["false_alarms_count"]) <= int(PHASE1B_REFERENCE["false_alarms"] * 1.10)
    )
    if pass_condition:
        return {
            "decision": "PASS",
            "reason": "prediction_mode_candidate_meets_offline_phase1c_gate",
        }

    partial_condition = bool(
        float(best_prediction["high_risk_recall"]) > float(PHASE1_REFERENCE["high_risk_recall"])
        or float(best_prediction["high_risk_recall"]) > float(PHASE1B_REFERENCE["high_risk_recall"])
    )
    if partial_condition:
        return {
            "decision": "PARTIAL",
            "reason": "recall_improved_materially_but_full_gate_not_met",
        }
    return {"decision": "FAIL", "reason": "no_material_prediction_mode_tradeoff_improvement"}


def _risk_severity_score(frame: pd.DataFrame, *, include_loss_pct: bool = False) -> np.ndarray:
    stage_weight = frame["stage"].astype(str).map(
        {"sechage": 2.2, "emballage": 1.3, "tri": 1.0, "nettoyage": 1.0}
    ).fillna(1.0)
    product_weight = frame["product"].astype(str).map({"mangue": 1.4, "arachide": 1.4, "mil": 1.1}).fillna(1.0)
    grade_weight = frame["grade"].astype(str).map({"C": 1.3, "B": 1.0, "A": 0.9}).fillna(1.0)

    humidity = pd.to_numeric(frame["humidity"], errors="coerce").fillna(0.0)
    rainfall = pd.to_numeric(frame["rainfall"], errors="coerce").fillna(0.0)
    dew_point = pd.to_numeric(frame["dew_point"], errors="coerce").fillna(0.0)
    duration = pd.to_numeric(frame["step_duration_minutes"], errors="coerce").fillna(0.0)
    delay = pd.to_numeric(frame["delay_since_previous_step_minutes"], errors="coerce").fillna(0.0)

    humidity_risk = np.clip((humidity - 70.0) / 20.0, 0.0, 2.0)
    rainfall_risk = np.clip((rainfall - 3.0) / 8.0, 0.0, 2.0)
    dew_risk = np.clip((dew_point - 20.0) / 8.0, 0.0, 2.0)
    duration_risk = np.clip((duration - 180.0) / 180.0, 0.0, 2.0)
    delay_risk = np.clip((delay - 120.0) / 180.0, 0.0, 2.0)

    score = (
        stage_weight.values
        + 0.8 * product_weight.values
        + 0.5 * grade_weight.values
        + 1.2 * humidity_risk.values
        + 1.0 * rainfall_risk.values
        + 0.8 * dew_risk.values
        + 1.0 * duration_risk.values
        + 0.8 * delay_risk.values
    )
    if include_loss_pct:
        loss_pct = pd.to_numeric(frame["loss_pct"], errors="coerce").fillna(0.0)
        score = score + 1.6 * np.clip((loss_pct - 12.0) / 8.0, 0.0, 3.0).values
    return np.asarray(score, dtype=float)


def _apply_high_risk_override(
    base_pred: np.ndarray,
    override_mask: np.ndarray,
    *,
    only_low_medium: bool = True,
) -> np.ndarray:
    out = np.array(base_pred, dtype=object).copy()
    if only_low_medium:
        mask = override_mask & np.isin(out, ["low", "medium"])
    else:
        mask = override_mask
    out[mask] = "high"
    return out


def _build_calibrated_rf(categorical_cols: List[str], numeric_cols: List[str]) -> Pipeline:
    base_pipeline = _build_pipeline(
        categorical_cols,
        numeric_cols,
        RandomForestClassifier(n_estimators=260, random_state=42, class_weight="balanced"),
    )
    try:
        model = CalibratedClassifierCV(estimator=base_pipeline, method="sigmoid", cv=3)
    except TypeError:
        model = CalibratedClassifierCV(base_estimator=base_pipeline, method="sigmoid", cv=3)
    return model


def _build_logistic_balanced(categorical_cols: List[str], numeric_cols: List[str]) -> Pipeline:
    return Pipeline(
        steps=[
            (
                "preprocessor",
                ColumnTransformer(
                    transformers=[
                        ("cat", _build_one_hot_encoder(), categorical_cols),
                        ("num", Pipeline([("scaler", StandardScaler())]), numeric_cols),
                    ]
                ),
            ),
            (
                "model",
                LogisticRegression(
                    max_iter=5000,
                    class_weight="balanced",
                    solver="lbfgs",
                ),
            ),
        ]
    )


def _safe_predict_proba(model: object, X: pd.DataFrame) -> Optional[np.ndarray]:
    if not hasattr(model, "predict_proba"):
        return None
    try:
        return model.predict_proba(X)
    except Exception:
        return None


def _class_index_map(classes: np.ndarray) -> Dict[str, int]:
    return {str(label): idx for idx, label in enumerate(classes)}


def _predict_with_high_threshold(
    *,
    proba: np.ndarray,
    classes: np.ndarray,
    high_threshold: float,
    medium_threshold: float = 0.35,
) -> np.ndarray:
    idx = _class_index_map(classes)
    high_idx = idx.get("high")
    med_idx = idx.get("medium")
    low_idx = idx.get("low")
    if high_idx is None or med_idx is None or low_idx is None:
        return classes[np.argmax(proba, axis=1)]

    out: List[str] = []
    for row in proba:
        p_low = float(row[low_idx])
        p_med = float(row[med_idx])
        p_high = float(row[high_idx])
        if p_high >= float(high_threshold):
            out.append("high")
            continue
        if p_med >= float(medium_threshold):
            out.append("medium")
            continue
        out.append("medium" if p_med >= p_low else "low")
    return np.array(out, dtype=object)


def _predict_with_stage_thresholds(
    *,
    proba: np.ndarray,
    classes: np.ndarray,
    stages: pd.Series,
    stage_thresholds: Dict[str, float],
    default_high_threshold: float,
    medium_threshold: float = 0.35,
) -> np.ndarray:
    idx = _class_index_map(classes)
    high_idx = idx.get("high")
    med_idx = idx.get("medium")
    low_idx = idx.get("low")
    if high_idx is None or med_idx is None or low_idx is None:
        return classes[np.argmax(proba, axis=1)]

    out: List[str] = []
    for i, row in enumerate(proba):
        stage_name = str(stages.iloc[i])
        threshold = float(stage_thresholds.get(stage_name, default_high_threshold))
        p_low = float(row[low_idx])
        p_med = float(row[med_idx])
        p_high = float(row[high_idx])
        if p_high >= threshold:
            out.append("high")
            continue
        if p_med >= float(medium_threshold):
            out.append("medium")
            continue
        out.append("medium" if p_med >= p_low else "low")
    return np.array(out, dtype=object)


def _predict_with_cost_matrix(
    *,
    proba: np.ndarray,
    classes: np.ndarray,
    cost_matrix: Dict[str, Dict[str, float]],
) -> np.ndarray:
    labels = [str(item) for item in classes.tolist()]
    out: List[str] = []
    for row in proba:
        class_prob = {labels[idx]: float(row[idx]) for idx in range(len(labels))}
        best_label = labels[0]
        best_cost = float("inf")
        for pred_label in labels:
            expected_cost = 0.0
            for true_label in labels:
                expected_cost += class_prob[true_label] * float(cost_matrix.get(true_label, {}).get(pred_label, 0.0))
            if expected_cost < best_cost:
                best_cost = expected_cost
                best_label = pred_label
        out.append(best_label)
    return np.array(out, dtype=object)


def _threshold_sweep(
    *,
    candidate_prefix: str,
    proba: np.ndarray,
    classes: np.ndarray,
    y_true: np.ndarray,
    thresholds: List[float],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for threshold in thresholds:
        pred = _predict_with_high_threshold(
            proba=proba,
            classes=classes,
            high_threshold=threshold,
            medium_threshold=0.35,
        )
        metrics = _classification_metrics(y_true, pred)
        rows.append(
            {
                "candidate": f"{candidate_prefix}_high_threshold_{threshold:.2f}",
                "threshold": float(threshold),
                "macro_f1": float(metrics["macro_f1"]),
                "high_risk_recall": float(metrics["high_risk_recall"]),
                "high_risk_precision": float(metrics["high_risk_precision"]),
                "false_low_high_risk_rate": float(metrics["false_low_high_risk_rate"]),
                "pred": pred,
            }
        )
    return rows


def _select_stage_thresholds_from_train(
    *,
    proba_train: np.ndarray,
    y_train: np.ndarray,
    train_stages: pd.Series,
    classes: np.ndarray,
    thresholds: List[float],
    default_threshold: float,
) -> Dict[str, float]:
    idx = _class_index_map(classes)
    high_idx = idx.get("high")
    if high_idx is None:
        return {}

    out: Dict[str, float] = {}
    data = pd.DataFrame(
        {
            "stage": train_stages.astype(str).values,
            "p_high": proba_train[:, high_idx],
            "is_high": (y_train == "high").astype(int),
        }
    )
    for stage_name, subset in data.groupby("stage"):
        if len(subset) < 25:
            out[str(stage_name)] = float(default_threshold)
            continue
        best_threshold = float(default_threshold)
        best_score = float("-inf")
        y_binary = subset["is_high"].to_numpy(dtype=int)
        for threshold in thresholds:
            pred_binary = (subset["p_high"].to_numpy(dtype=float) >= float(threshold)).astype(int)
            tp = int(np.sum((pred_binary == 1) & (y_binary == 1)))
            fp = int(np.sum((pred_binary == 1) & (y_binary == 0)))
            fn = int(np.sum((pred_binary == 0) & (y_binary == 1)))
            recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
            precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
            # Recall-prioritized score with mild precision regularization.
            score = (2.0 * recall) + (0.25 * precision)
            if score > best_score:
                best_score = score
                best_threshold = float(threshold)
        out[str(stage_name)] = best_threshold
    return out


def _proba_summary(
    *,
    proba: Optional[np.ndarray],
    classes: Optional[np.ndarray],
) -> Dict[str, Any]:
    if proba is None or classes is None:
        return {"available": False}
    idx = _class_index_map(classes)
    high_idx = idx.get("high")
    if high_idx is None:
        return {"available": False}
    high_prob = proba[:, high_idx]
    return {
        "available": True,
        "high_probability_mean": float(np.mean(high_prob)),
        "high_probability_quantiles": {
            "q50": float(np.quantile(high_prob, 0.50)),
            "q75": float(np.quantile(high_prob, 0.75)),
            "q90": float(np.quantile(high_prob, 0.90)),
            "q95": float(np.quantile(high_prob, 0.95)),
            "q99": float(np.quantile(high_prob, 0.99)),
        },
    }


def _critical_risk_failure_diagnostics(
    *,
    train: pd.DataFrame,
    test: pd.DataFrame,
    y_test: np.ndarray,
    current_pred: np.ndarray,
    current_proba: Optional[np.ndarray],
    current_classes: Optional[np.ndarray],
) -> Dict[str, Any]:
    labels = RISK_LABELS
    high_support = int(np.sum(y_test == "high"))
    confusion = confusion_matrix(y_test, current_pred, labels=labels).tolist()
    high_pred_as_low = int(np.sum((y_test == "high") & (current_pred == "low")))
    high_pred_as_medium = int(np.sum((y_test == "high") & (current_pred == "medium")))
    high_pred_as_high = int(np.sum((y_test == "high") & (current_pred == "high")))

    test_diag = test.copy().reset_index(drop=True)
    test_diag["y_true"] = y_test
    test_diag["y_pred"] = current_pred
    if current_proba is not None and current_classes is not None:
        class_idx = _class_index_map(current_classes)
        for label in labels:
            if label in class_idx:
                test_diag[f"proba_{label}"] = current_proba[:, class_idx[label]]
            else:
                test_diag[f"proba_{label}"] = 0.0
    else:
        for label in labels:
            test_diag[f"proba_{label}"] = 0.0

    high_rows = test_diag[test_diag["y_true"] == "high"].copy()
    high_cluster = {
        "by_stage": {str(k): int(v) for k, v in high_rows["stage"].value_counts(dropna=False).to_dict().items()},
        "by_product": {str(k): int(v) for k, v in high_rows["product"].value_counts(dropna=False).to_dict().items()},
        "by_season": {str(k): int(v) for k, v in high_rows["season"].value_counts(dropna=False).to_dict().items()},
        "by_anomaly_label": {
            str(k): int(v)
            for k, v in high_rows["anomaly_label_synthetic"].fillna(-1).astype(int).value_counts(dropna=False).to_dict().items()
        },
    }

    high_examples = high_rows[
        [
            "product",
            "stage",
            "season",
            "loss_pct",
            "humidity",
            "rainfall",
            "step_duration_minutes",
            "delay_since_previous_step_minutes",
            "anomaly_label_synthetic",
            "y_pred",
            "proba_low",
            "proba_medium",
            "proba_high",
        ]
    ].head(12)

    return {
        "train_class_distribution": {str(k): int(v) for k, v in train["risk_label"].value_counts(dropna=False).to_dict().items()},
        "test_class_distribution": {str(k): int(v) for k, v in test_diag["y_true"].value_counts(dropna=False).to_dict().items()},
        "high_risk_support_count": high_support,
        "confusion_matrix_current_model": confusion,
        "labels": labels,
        "high_risk_predictions_breakdown": {
            "predicted_low": high_pred_as_low,
            "predicted_medium": high_pred_as_medium,
            "predicted_high": high_pred_as_high,
        },
        "probability_summary_current_model": _proba_summary(
            proba=current_proba,
            classes=current_classes,
        ),
        "high_risk_cluster": high_cluster,
        "high_risk_examples": high_examples.to_dict(orient="records"),
    }


def _evaluate_classification_split(
    frame: pd.DataFrame,
    train_idx: pd.Index,
    test_idx: pd.Index,
    split_name: str,
    categorical_cols: List[str],
    numeric_cols: List[str],
) -> Dict[str, Any]:
    train = frame.loc[train_idx]
    test = frame.loc[test_idx]
    X_train = train[categorical_cols + numeric_cols]
    X_test = test[categorical_cols + numeric_cols]
    y_train = train["risk_label"].to_numpy(dtype=str)
    y_test = test["risk_label"].to_numpy(dtype=str)

    # Baselines
    majority_label = str(pd.Series(y_train).mode().iloc[0])
    majority_pred = np.full(len(y_test), majority_label, dtype=object)
    stage_mean = train.groupby("stage")["loss_pct"].mean().to_dict()
    threshold_pred = np.array(
        [_assign_risk(stage_mean.get(stage_name, float(train["loss_pct"].mean()))) for stage_name in test["stage"]],
        dtype=object,
    )

    predictions: Dict[str, np.ndarray] = {
        "majority_baseline": majority_pred,
        "threshold_stage_mean_baseline": threshold_pred,
    }
    probabilities: Dict[str, Optional[np.ndarray]] = {
        "majority_baseline": None,
        "threshold_stage_mean_baseline": None,
    }
    classes_map: Dict[str, Optional[np.ndarray]] = {
        "majority_baseline": None,
        "threshold_stage_mean_baseline": None,
    }

    rf = _build_pipeline(
        categorical_cols,
        numeric_cols,
        RandomForestClassifier(n_estimators=260, random_state=42),
    )
    rf_balanced = _build_pipeline(
        categorical_cols,
        numeric_cols,
        RandomForestClassifier(n_estimators=260, random_state=42, class_weight="balanced"),
    )
    logreg_balanced = _build_logistic_balanced(categorical_cols, numeric_cols)
    hgbc = _build_pipeline(
        categorical_cols,
        numeric_cols,
        HistGradientBoostingClassifier(random_state=42),
    )
    calibrated_rf = _build_calibrated_rf(categorical_cols, numeric_cols)

    rf.fit(X_train, y_train)
    rf_balanced.fit(X_train, y_train)
    logreg_balanced.fit(X_train, y_train)
    hgbc.fit(X_train, y_train)
    calibrated_rf.fit(X_train, y_train)

    model_objects: Dict[str, object] = {
        "RandomForestClassifier": rf,
        "RandomForestClassifier_class_weight_balanced": rf_balanced,
        "LogisticRegression_class_weight_balanced": logreg_balanced,
        "HistGradientBoostingClassifier": hgbc,
        "CalibratedRandomForestClassifier": calibrated_rf,
    }
    for name, model in model_objects.items():
        predictions[name] = model.predict(X_test)
        probabilities[name] = _safe_predict_proba(model, X_test)
        classes_map[name] = np.array(getattr(model, "classes_", []), dtype=object)

    # Threshold-tuned and cost-sensitive variants on RF balanced and calibrated RF.
    thresholds = [round(float(x), 2) for x in np.arange(0.10, 0.56, 0.05)]
    threshold_tradeoff_rows: List[Dict[str, Any]] = []
    for source_name in [
        "RandomForestClassifier_class_weight_balanced",
        "CalibratedRandomForestClassifier",
        "LogisticRegression_class_weight_balanced",
    ]:
        source_proba = probabilities.get(source_name)
        source_classes = classes_map.get(source_name)
        if source_proba is None or source_classes is None or len(source_classes) == 0:
            continue
        sweep = _threshold_sweep(
            candidate_prefix=source_name,
            proba=source_proba,
            classes=source_classes,
            y_true=y_test,
            thresholds=thresholds,
        )
        threshold_tradeoff_rows.extend(
            [
                {
                    "source_model": source_name,
                    "threshold": row["threshold"],
                    "macro_f1": row["macro_f1"],
                    "high_risk_recall": row["high_risk_recall"],
                    "high_risk_precision": row["high_risk_precision"],
                    "false_low_high_risk_rate": row["false_low_high_risk_rate"],
                }
                for row in sweep
            ]
        )
        valid = [row for row in sweep if row["macro_f1"] >= 0.50]
        best = sorted(
            valid if valid else sweep,
            key=lambda item: (item["high_risk_recall"], item["macro_f1"], item["high_risk_precision"]),
            reverse=True,
        )[0]
        predictions[best["candidate"]] = best["pred"]
        probabilities[best["candidate"]] = source_proba
        classes_map[best["candidate"]] = source_classes

    # Stage-aware thresholds from train probabilities.
    rf_balanced_train_proba = _safe_predict_proba(rf_balanced, X_train)
    rf_balanced_test_proba = probabilities.get("RandomForestClassifier_class_weight_balanced")
    rf_balanced_classes = classes_map.get("RandomForestClassifier_class_weight_balanced")
    if rf_balanced_train_proba is not None and rf_balanced_test_proba is not None and rf_balanced_classes is not None:
        default_threshold = 0.25
        stage_thresholds = _select_stage_thresholds_from_train(
            proba_train=rf_balanced_train_proba,
            y_train=y_train,
            train_stages=train["stage"],
            classes=rf_balanced_classes,
            thresholds=thresholds,
            default_threshold=default_threshold,
        )
        stage_aware_pred = _predict_with_stage_thresholds(
            proba=rf_balanced_test_proba,
            classes=rf_balanced_classes,
            stages=test["stage"].reset_index(drop=True),
            stage_thresholds=stage_thresholds,
            default_high_threshold=default_threshold,
            medium_threshold=0.35,
        )
        predictions["StageAwareThresholdBalancedRF"] = stage_aware_pred
        probabilities["StageAwareThresholdBalancedRF"] = rf_balanced_test_proba
        classes_map["StageAwareThresholdBalancedRF"] = rf_balanced_classes

        # Product-stage-aware thresholding using train risk prevalence.
        idx_map = _class_index_map(rf_balanced_classes)
        high_idx = idx_map.get("high")
        if high_idx is not None:
            train_aux = train.copy().reset_index(drop=True)
            train_aux["p_high"] = rf_balanced_train_proba[:, high_idx]
            train_aux["y_high"] = (y_train == "high").astype(int)
            ps_thresholds: Dict[str, float] = {}
            for ps_key, subset in train_aux.groupby("product_stage"):
                if len(subset) < 20:
                    ps_thresholds[str(ps_key)] = 0.25
                    continue
                y_bin = subset["y_high"].to_numpy(dtype=int)
                p = subset["p_high"].to_numpy(dtype=float)
                best_t = 0.25
                best_score = float("-inf")
                for t in thresholds:
                    pred_bin = (p >= t).astype(int)
                    tp = int(np.sum((pred_bin == 1) & (y_bin == 1)))
                    fp = int(np.sum((pred_bin == 1) & (y_bin == 0)))
                    fn = int(np.sum((pred_bin == 0) & (y_bin == 1)))
                    recall = float(tp / (tp + fn)) if (tp + fn) else 0.0
                    precision = float(tp / (tp + fp)) if (tp + fp) else 0.0
                    score = (2.0 * recall) + (0.3 * precision)
                    if score > best_score:
                        best_score = score
                        best_t = float(t)
                ps_thresholds[str(ps_key)] = best_t

            test_ps = test["product_stage"].astype(str).reset_index(drop=True)
            test_pred = np.array(predictions["RandomForestClassifier_class_weight_balanced"], dtype=object).copy()
            p_high_test = rf_balanced_test_proba[:, high_idx]
            for i in range(len(test_pred)):
                threshold = ps_thresholds.get(test_ps.iloc[i], 0.25)
                if float(p_high_test[i]) >= threshold:
                    test_pred[i] = "high"
            predictions["ProductStageAwareThresholdBalancedRF"] = test_pred
            probabilities["ProductStageAwareThresholdBalancedRF"] = rf_balanced_test_proba
            classes_map["ProductStageAwareThresholdBalancedRF"] = rf_balanced_classes

    # Cost-sensitive decision rule (penalize high->low heavily).
    calibrated_proba = probabilities.get("CalibratedRandomForestClassifier")
    calibrated_classes = classes_map.get("CalibratedRandomForestClassifier")
    if calibrated_proba is not None and calibrated_classes is not None and len(calibrated_classes) == 3:
        cost_matrix = {
            "high": {"high": 0.0, "medium": 4.0, "low": 8.0},
            "medium": {"high": 1.5, "medium": 0.0, "low": 2.5},
            "low": {"high": 1.0, "medium": 0.4, "low": 0.0},
        }
        cost_pred = _predict_with_cost_matrix(
            proba=calibrated_proba,
            classes=calibrated_classes,
            cost_matrix=cost_matrix,
        )
        predictions["CostSensitiveCalibratedRF"] = cost_pred
        probabilities["CostSensitiveCalibratedRF"] = calibrated_proba
        classes_map["CostSensitiveCalibratedRF"] = calibrated_classes

    # Phase 1B rule-assisted candidates.
    severity_pred = _risk_severity_score(test, include_loss_pct=False)
    severity_assess = _risk_severity_score(test, include_loss_pct=True)
    sev_quantiles = {
        "aggressive": 0.80,
        "balanced": 0.85,
        "conservative": 0.90,
    }
    sev_masks = {
        name: (severity_pred >= float(np.quantile(severity_pred, q)))
        for name, q in sev_quantiles.items()
    }
    sev_assess_high = severity_assess >= float(np.quantile(severity_assess, 0.85))

    if "LogisticRegression_class_weight_balanced" in predictions:
        base = np.array(predictions["LogisticRegression_class_weight_balanced"], dtype=object)
        for mode_name, mask in sev_masks.items():
            predictions[f"Phase1C_LogRegBalanced_plus_HighOverride_{mode_name}"] = _apply_high_risk_override(base, mask)
        # Keep Phase1B historical name for continuity in reports.
        predictions["Phase1B_LogRegBalanced_plus_HighOverride"] = _apply_high_risk_override(
            base, sev_masks["balanced"]
        )
        logreg_proba = probabilities.get("LogisticRegression_class_weight_balanced")
        logreg_classes = classes_map.get("LogisticRegression_class_weight_balanced")
        if logreg_proba is not None and logreg_classes is not None and len(logreg_classes) == 3:
            logreg_threshold_pred = _predict_with_high_threshold(
                proba=logreg_proba,
                classes=logreg_classes,
                high_threshold=0.32,
                medium_threshold=0.38,
            )
            predictions["Phase2_LogRegThreshold_h0.32_m0.38"] = logreg_threshold_pred

            idx = _class_index_map(logreg_classes)
            high_idx = idx.get("high")
            if high_idx is not None:
                p_high = logreg_proba[:, high_idx]
                sev_cut = float(np.quantile(severity_pred, 0.90))
                promote_mask = (p_high >= 0.29) & (severity_pred >= sev_cut)
                two_stage = _apply_high_risk_override(logreg_threshold_pred, promote_mask, only_low_medium=True)

                # Filter likely false alarms while retaining strong-high evidence.
                filter_mask = (
                    (two_stage == "high")
                    & (p_high < 0.42)
                    & (severity_pred < sev_cut)
                    & (test["stage"].astype(str).to_numpy() != "sechage")
                )
                two_stage[filter_mask] = "medium"
                predictions["Phase2_TwoStage_LogReg_SeverityFilter"] = two_stage

                # Grid-search a small safe family of two-stage variants.
                candidate_specs = []
                for promote_t in [0.27, 0.29, 0.31]:
                    for filter_t in [0.40, 0.44]:
                        for q in [0.88, 0.90]:
                            candidate_specs.append((promote_t, filter_t, q))
                best_name = None
                best_tuple = None
                for promote_t, filter_t, q in candidate_specs:
                    sev_q = float(np.quantile(severity_pred, q))
                    promote = (p_high >= promote_t) & (severity_pred >= sev_q)
                    pred_tmp = _apply_high_risk_override(logreg_threshold_pred, promote, only_low_medium=True)
                    filt = (
                        (pred_tmp == "high")
                        & (p_high < filter_t)
                        & (severity_pred < sev_q)
                        & (test["stage"].astype(str).to_numpy() != "sechage")
                    )
                    pred_tmp[filt] = "medium"
                    m = _classification_metrics(y_test, pred_tmp)
                    high_detected = int(np.sum((y_test == "high") & (pred_tmp == "high")))
                    false_alarms = int(np.sum((y_test != "high") & (pred_tmp == "high")))
                    key = (
                        float(m["high_risk_recall"]) >= 0.40,
                        float(m["macro_f1"]),
                        float(m["high_risk_precision"]),
                        -false_alarms,
                        high_detected,
                    )
                    name = f"Phase2_TwoStage_LogReg_p{promote_t:.2f}_f{filter_t:.2f}_q{q:.2f}"
                    predictions[name] = pred_tmp
                    if best_tuple is None or key > best_tuple:
                        best_tuple = key
                        best_name = name
                if best_name:
                    predictions["Phase2_TwoStage_LogReg_BestGrid"] = np.array(
                        predictions[best_name], dtype=object
                    )
    if "RandomForestClassifier_class_weight_balanced" in predictions:
        base = np.array(predictions["RandomForestClassifier_class_weight_balanced"], dtype=object)
        for mode_name, mask in sev_masks.items():
            predictions[f"Phase1C_RFBalanced_plus_HighOverride_{mode_name}"] = _apply_high_risk_override(base, mask)
        predictions["Phase1B_RFBalanced_plus_HighOverride"] = _apply_high_risk_override(base, sev_masks["balanced"])
        predictions["Phase1B_WeatherDurationRiskOverride_BalancedRF"] = _apply_high_risk_override(
            base, sev_masks["aggressive"]
        )
    if "CalibratedRandomForestClassifier" in predictions:
        base = np.array(predictions["CalibratedRandomForestClassifier"], dtype=object)
        if probabilities.get("CalibratedRandomForestClassifier") is not None and classes_map.get("CalibratedRandomForestClassifier") is not None:
            p = probabilities["CalibratedRandomForestClassifier"]
            c = classes_map["CalibratedRandomForestClassifier"]
            for t in [0.18, 0.22, 0.26]:
                high_pred = _predict_with_high_threshold(
                    proba=p,
                    classes=c,
                    high_threshold=t,
                    medium_threshold=0.35,
                )
                predictions[f"Phase1C_ConservativeHybrid_t{t:.2f}"] = _apply_high_risk_override(
                    high_pred, sev_masks["conservative"]
                )
                predictions[f"Phase1C_BalancedHybrid_t{t:.2f}"] = _apply_high_risk_override(
                    high_pred, sev_masks["balanced"]
                )
            predictions["Phase1B_ConservativeHybrid"] = _apply_high_risk_override(
                _predict_with_high_threshold(proba=p, classes=c, high_threshold=0.22, medium_threshold=0.35),
                sev_masks["conservative"],
            )
            predictions["Phase1B_BalancedHybrid"] = _apply_high_risk_override(base, sev_masks["aggressive"])

    # Assessment-mode candidate may use post-event loss_pct inside severity.
    if "LogisticRegression_class_weight_balanced" in predictions:
        base = np.array(predictions["LogisticRegression_class_weight_balanced"], dtype=object)
        predictions["Phase1B_AssessmentMode_LogReg_plus_PostEventLossSeverity"] = _apply_high_risk_override(
            base, sev_assess_high
        )

    baseline_rows = {
        name: _classification_metrics(y_test, pred)
        for name, pred in predictions.items()
        if "baseline" in name
    }
    baseline_best_name, baseline_best_payload = max(
        baseline_rows.items(), key=lambda item: float(item[1]["macro_f1"])
    )
    baseline_best_macro_f1 = float(baseline_best_payload["macro_f1"])
    current_reference_name = "RandomForestClassifier"
    current_reference_false_low = float(
        _classification_metrics(y_test, predictions[current_reference_name])["false_low_high_risk_rate"]
    )

    candidate_mode: Dict[str, str] = {}
    for name in predictions.keys():
        if "AssessmentMode" in name:
            candidate_mode[name] = "assessment_mode"
        else:
            candidate_mode[name] = "prediction_mode"

    rows: List[Dict[str, Any]] = []
    for candidate_name, pred in predictions.items():
        overall = _classification_metrics(y_test, pred)
        per_stage = _classification_metrics(y_test, pred, groups=test["stage"])["per_group_macro_f1"]
        per_product = _classification_metrics(y_test, pred, groups=test["product"])["per_group_macro_f1"]
        per_stage_high_recall = _high_risk_recall_by_group(y_test, pred, test["stage"])
        per_product_high_recall = _high_risk_recall_by_group(y_test, pred, test["product"])
        high_detected_count = int(np.sum((y_test == "high") & (pred == "high")))
        false_alarms_count = int(np.sum((y_test != "high") & (pred == "high")))
        precision_or_tradeoff_ok = bool(
            (overall["high_risk_precision"] > PHASE1_REFERENCE["high_risk_precision"])
            or (
                overall["high_risk_recall"] >= PHASE1_REFERENCE["high_risk_recall"]
                and overall["false_low_high_risk_rate"] < PHASE1_REFERENCE["false_low_high_risk_rate"]
            )
        )
        gate_pass = bool(
            overall["high_risk_recall"] >= 0.40
            and overall["macro_f1"] >= 0.50
            and overall["false_low_high_risk_rate"] < current_reference_false_low
            and overall["false_low_high_risk_rate"] < PHASE1_REFERENCE["false_low_high_risk_rate"]
            and precision_or_tradeoff_ok
        )
        rows.append(
            {
                "candidate": candidate_name,
                "mode": candidate_mode.get(candidate_name, "prediction_mode"),
                "split": split_name,
                "macro_f1": float(overall["macro_f1"]),
                "weighted_f1": float(overall["weighted_f1"]),
                "high_risk_recall": float(overall["high_risk_recall"]),
                "high_risk_precision": float(overall["high_risk_precision"]),
                "false_low_high_risk_rate": float(overall["false_low_high_risk_rate"]),
                "confusion_matrix": overall["confusion_matrix"],
                "labels": overall["labels"],
                "per_class": overall["per_class"],
                "per_stage_macro_f1": per_stage,
                "per_product_macro_f1": per_product,
                "per_stage_high_risk_recall": per_stage_high_recall,
                "per_product_high_risk_recall": per_product_high_recall,
                "high_risk_detected_count": high_detected_count,
                "false_alarms_count": false_alarms_count,
                "best_baseline_name": baseline_best_name,
                "best_baseline_macro_f1": baseline_best_macro_f1,
                "beats_best_baseline": bool(overall["macro_f1"] > baseline_best_macro_f1),
                "beats_current_false_low_rate": bool(overall["false_low_high_risk_rate"] < current_reference_false_low),
                "beats_phase1_false_low_rate": bool(overall["false_low_high_risk_rate"] < PHASE1_REFERENCE["false_low_high_risk_rate"]),
                "precision_or_tradeoff_ok": precision_or_tradeoff_ok,
                "probability_summary": _proba_summary(
                    proba=probabilities.get(candidate_name),
                    classes=classes_map.get(candidate_name),
                ),
                "gate_pass": gate_pass,
            }
        )

    prediction_rows = [row for row in rows if row["mode"] == "prediction_mode"]
    assessment_rows = [row for row in rows if row["mode"] == "assessment_mode"]
    prediction_rows_for_ranking = [row for row in prediction_rows if float(row["macro_f1"]) >= 0.45]
    if not prediction_rows_for_ranking:
        prediction_rows_for_ranking = prediction_rows
    ranked_prediction = sorted(
        prediction_rows_for_ranking,
        key=lambda row: (
            row["high_risk_recall"],
            row["macro_f1"],
            row["high_risk_precision"],
            -row["false_alarms_count"],
            -row["false_low_high_risk_rate"],
        ),
        reverse=True,
    )
    ranked_assessment = sorted(
        assessment_rows,
        key=lambda row: (
            row["high_risk_recall"],
            row["macro_f1"],
            -row["false_low_high_risk_rate"],
            row["high_risk_precision"],
        ),
        reverse=True,
    )
    ranked = ranked_prediction + ranked_assessment
    pareto_prediction = _pareto_frontier(ranked_prediction)
    best_recall_prediction = (
        sorted(ranked_prediction, key=lambda row: (row["high_risk_recall"], row["macro_f1"]), reverse=True)[0]
        if ranked_prediction
        else None
    )
    best_macro_prediction = (
        sorted(ranked_prediction, key=lambda row: (row["macro_f1"], row["high_risk_recall"]), reverse=True)[0]
        if ranked_prediction
        else None
    )
    lowest_false_alarm_with_recall = None
    recall_positive = [row for row in ranked_prediction if float(row["high_risk_recall"]) > 0.0]
    if recall_positive:
        lowest_false_alarm_with_recall = sorted(
            recall_positive,
            key=lambda row: (row["false_alarms_count"], -row["high_risk_recall"], -row["macro_f1"]),
        )[0]
    best_balanced_prediction = None
    if ranked_prediction:
        best_balanced_prediction = sorted(
            ranked_prediction,
            key=lambda row: (
                abs(float(row["high_risk_recall"]) - 0.40),
                abs(float(row["macro_f1"]) - 0.50),
                row["false_alarms_count"],
                -float(row["high_risk_precision"]),
            ),
        )[0]
    final_decision = _phase1c_final_decision(
        best_prediction=ranked_prediction[0] if ranked_prediction else None,
        current_reference_false_low=current_reference_false_low,
    )
    critical_diagnostics = _critical_risk_failure_diagnostics(
        train=train,
        test=test,
        y_test=y_test,
        current_pred=predictions[current_reference_name],
        current_proba=probabilities.get(current_reference_name),
        current_classes=classes_map.get(current_reference_name),
    )
    return {
        "split": split_name,
        "best_baseline": {"name": baseline_best_name, "macro_f1": baseline_best_macro_f1},
        "current_reference": {
            "candidate": current_reference_name,
            "false_low_high_risk_rate": current_reference_false_low,
            "macro_f1": float(_classification_metrics(y_test, predictions[current_reference_name])["macro_f1"]),
            "high_risk_recall": float(_classification_metrics(y_test, predictions[current_reference_name])["high_risk_recall"]),
        },
        "phase1_reference": PHASE1_REFERENCE,
        "gates": {
            "primary": {
                "high_risk_recall_min": 0.40,
                "macro_f1_min": 0.50,
                "false_low_high_risk_rate_must_improve_vs_current": True,
                "false_low_high_risk_rate_must_improve_vs_phase1": True,
                "high_risk_precision_or_tradeoff_condition": "precision > 0.0744 OR safer recall tradeoff",
            },
            "secondary": {
                "high_risk_recall_target": 0.45,
                "high_risk_precision_target": 0.10,
                "high_risk_precision_report_only": True,
            },
        },
        "rule_definition": {
            "severity_score_components": {
                "stage_weight": {"sechage": 2.2, "emballage": 1.3, "tri": 1.0, "nettoyage": 1.0},
                "product_weight": {"mangue": 1.4, "arachide": 1.4, "mil": 1.1},
                "grade_weight": {"C": 1.3, "B": 1.0, "A": 0.9},
                "weather_duration_terms": [
                    "humidity_risk",
                    "rainfall_risk",
                    "dew_point_risk",
                    "step_duration_risk",
                    "delay_risk",
                ],
                "assessment_only_term": "loss_pct_risk",
            },
            "mode_boundary": {
                "prediction_mode": "does not use loss_pct/loss_qty/efficiency_pct as features",
                "assessment_mode": "may include post-event loss_pct in severity override",
            },
        },
        "threshold_tuning_tradeoff": threshold_tradeoff_rows,
        "critical_risk_failure_diagnostics": critical_diagnostics,
        "phase1b_reference": PHASE1B_REFERENCE,
        "prediction_mode_candidates_ranked": ranked_prediction,
        "assessment_mode_candidates_ranked": ranked_assessment,
        "phase1c_pareto_frontier_prediction_mode": pareto_prediction,
        "phase1c_best_recall_prediction_mode": best_recall_prediction,
        "phase1c_best_macro_f1_prediction_mode": best_macro_prediction,
        "phase1c_best_balanced_prediction_mode": best_balanced_prediction,
        "phase1c_lowest_false_alarm_with_recall_prediction_mode": lowest_false_alarm_with_recall,
        "best_prediction_mode_candidate": ranked_prediction[0] if ranked_prediction else None,
        "best_assessment_mode_candidate": ranked_assessment[0] if ranked_assessment else None,
        "phase1c_final_decision": final_decision,
        "candidates_ranked": ranked,
        "any_gate_passed": bool(any(row["gate_pass"] for row in ranked_prediction)),
    }


def _evaluate_anomaly_diagnostics(
    frame: pd.DataFrame,
    train_idx: pd.Index,
    test_idx: pd.Index,
    categorical_cols: List[str],
    numeric_cols: List[str],
) -> Dict[str, Any]:
    train = frame.loc[train_idx].copy().reset_index(drop=True)
    test = frame.loc[test_idx].copy().reset_index(drop=True)
    y_true = test["anomaly_label_synthetic"].to_numpy(dtype=int)

    def _safe_std(value: float) -> float:
        return float(value) if pd.notna(value) and float(value) > 1e-9 else 1.0

    def _zscore(values: pd.Series, mean: object, std: object) -> np.ndarray:
        v = pd.to_numeric(values, errors="coerce").fillna(0.0)
        if isinstance(mean, pd.Series):
            m = pd.to_numeric(mean, errors="coerce").fillna(float(v.mean()))
        else:
            m = pd.Series(float(mean), index=v.index)
        if isinstance(std, pd.Series):
            s_raw = pd.to_numeric(std, errors="coerce").fillna(float(v.std()))
        else:
            s_raw = pd.Series(float(std), index=v.index)
        s = s_raw.apply(_safe_std)
        return ((v - m) / s).to_numpy(dtype=float)

    def _binary_metrics(pred: np.ndarray, score: Optional[np.ndarray], *, mode: str, candidate_type: str, name: str) -> Dict[str, Any]:
        pred_binary = np.asarray(pred, dtype=int)
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, pred_binary, average="binary", zero_division=0
        )
        tp = int(np.sum((pred_binary == 1) & (y_true == 1)))
        fp = int(np.sum((pred_binary == 1) & (y_true == 0)))
        fn = int(np.sum((pred_binary == 0) & (y_true == 1)))
        tn = int(np.sum((pred_binary == 0) & (y_true == 0)))
        if score is None:
            score = pred_binary.astype(float)
        score_arr = np.asarray(score, dtype=float)
        top_k = max(1, int(round(len(score_arr) * 0.1)))
        top_idx = np.argsort(-score_arr)[:top_k]
        precision_at_10 = float(np.mean(y_true[top_idx])) if len(top_idx) > 0 else 0.0
        assessment_gate_pass = bool(
            mode == "assessment_mode"
            and float(f1) >= 0.75
            and float(precision) >= 0.60
            and float(recall) >= 0.80
            and float(precision_at_10) >= 0.60
        )
        prediction_gate_pass = bool(
            mode == "prediction_mode"
            and float(recall) >= 0.25
            and float(precision_at_10) >= 0.20
        )
        return {
            "candidate": name,
            "mode": mode,
            "candidate_type": candidate_type,
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "precision_at_10pct": float(precision_at_10),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "predicted_positive": int(np.sum(pred_binary == 1)),
            "true_positive_support": int(np.sum(y_true == 1)),
            "false_positive_count": fp,
            "false_negative_count": fn,
            "confusion_counts": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
            "gate_pass": bool(assessment_gate_pass or prediction_gate_pass),
            "assessment_mode_gate_pass": bool(assessment_gate_pass),
            "prediction_mode_gate_pass": bool(prediction_gate_pass),
        }

    # IsolationForest baseline on prediction-mode fields only.
    iforest = _build_pipeline(
        categorical_cols,
        numeric_cols,
        IsolationForest(n_estimators=220, random_state=42, contamination=0.08),
    )
    iforest.fit(train[categorical_cols + numeric_cols])
    iforest_flags = iforest.predict(test[categorical_cols + numeric_cols])
    iforest_pred = (iforest_flags == -1).astype(int)
    iforest_score = -iforest.decision_function(test[categorical_cols + numeric_cols])

    # Shared thresholds/stats.
    stage_duration_q95 = train.groupby("stage")["step_duration_minutes"].quantile(0.95).to_dict()
    stage_delay_q95 = train.groupby("stage")["delay_since_previous_step_minutes"].quantile(0.95).to_dict()
    stage_loss_q95 = train.groupby("stage")["loss_pct"].quantile(0.95).to_dict()
    qty_in_q20 = float(train["qty_in"].quantile(0.20))
    duration_q90 = float(train["step_duration_minutes"].quantile(0.90))
    delay_q90 = float(train["delay_since_previous_step_minutes"].quantile(0.90))
    humidity_q90_sechage = float(train.loc[train["stage"] == "sechage", "humidity"].quantile(0.90))
    rainfall_q90_sechage = float(train.loc[train["stage"] == "sechage", "rainfall"].quantile(0.90))
    dew_q90_sechage = float(train.loc[train["stage"] == "sechage", "dew_point"].quantile(0.90))
    humidity_q85 = float(train["humidity"].quantile(0.85))
    rainfall_q85 = float(train["rainfall"].quantile(0.85))
    dew_q85 = float(train["dew_point"].quantile(0.85))

    # Prediction-mode rules (no qty_out/loss fields).
    pred_rule_weather_stage = (
        (test["stage"].astype(str) == "sechage")
        & (
            (test["humidity"] >= humidity_q90_sechage)
            | (test["rainfall"] >= rainfall_q90_sechage)
            | (test["dew_point"] >= dew_q90_sechage)
        )
    ).astype(int)
    pred_rule_duration_delay = np.array(
        [
            int(
                (row["step_duration_minutes"] >= stage_duration_q95.get(row["stage"], duration_q90))
                or (row["delay_since_previous_step_minutes"] >= stage_delay_q95.get(row["stage"], delay_q90))
            )
            for _, row in test.iterrows()
        ],
        dtype=int,
    )
    pred_rule_grade_stage = (
        (test["grade"].astype(str).str.upper() == "C")
        & test["stage"].astype(str).isin(["sechage", "emballage"])
        & ((test["humidity"] >= humidity_q85) | (test["rainfall"] >= rainfall_q85) | (test["dew_point"] >= dew_q85))
    ).astype(int)
    pred_rule_qty_context = (
        (test["qty_in"] <= qty_in_q20)
        & ((test["step_duration_minutes"] >= duration_q90) | (test["delay_since_previous_step_minutes"] >= delay_q90))
    ).astype(int)
    pred_rule_score = (
        pred_rule_weather_stage.to_numpy(dtype=int)
        + pred_rule_duration_delay
        + pred_rule_grade_stage.to_numpy(dtype=int)
        + pred_rule_qty_context.to_numpy(dtype=int)
    )

    # Prediction-mode statistical signals.
    ps_train_stats = (
        train.groupby(["product", "stage"])
        .agg(
            duration_mean=("step_duration_minutes", "mean"),
            duration_std=("step_duration_minutes", "std"),
            delay_mean=("delay_since_previous_step_minutes", "mean"),
            delay_std=("delay_since_previous_step_minutes", "std"),
            humidity_mean=("humidity", "mean"),
            humidity_std=("humidity", "std"),
            rainfall_mean=("rainfall", "mean"),
            rainfall_std=("rainfall", "std"),
        )
        .reset_index()
    )
    stage_season_weather_stats = (
        train.groupby(["stage", "season"])
        .agg(
            humidity_mean=("humidity", "mean"),
            humidity_std=("humidity", "std"),
            rainfall_mean=("rainfall", "mean"),
            rainfall_std=("rainfall", "std"),
        )
        .reset_index()
    )
    test_ps = test.merge(ps_train_stats, on=["product", "stage"], how="left")
    test_ps["duration_z"] = _zscore(test_ps["step_duration_minutes"], test_ps["duration_mean"].fillna(train["step_duration_minutes"].mean()), test_ps["duration_std"].fillna(train["step_duration_minutes"].std()))
    test_ps["delay_z"] = _zscore(test_ps["delay_since_previous_step_minutes"], test_ps["delay_mean"].fillna(train["delay_since_previous_step_minutes"].mean()), test_ps["delay_std"].fillna(train["delay_since_previous_step_minutes"].std()))
    test_ss = test.merge(stage_season_weather_stats, on=["stage", "season"], how="left")
    test_ss["humidity_z"] = _zscore(test_ss["humidity"], test_ss["humidity_mean"].fillna(train["humidity"].mean()), test_ss["humidity_std"].fillna(train["humidity"].std()))
    test_ss["rainfall_z"] = _zscore(test_ss["rainfall"], test_ss["rainfall_mean"].fillna(train["rainfall"].mean()), test_ss["rainfall_std"].fillna(train["rainfall"].std()))
    pred_stat_duration = (np.abs(test_ps["duration_z"].to_numpy(dtype=float)) >= 2.5).astype(int)
    pred_stat_delay = (np.abs(test_ps["delay_z"].to_numpy(dtype=float)) >= 2.5).astype(int)
    pred_stat_weather = (
        (np.abs(test_ss["humidity_z"].to_numpy(dtype=float)) >= 2.5)
        | (np.abs(test_ss["rainfall_z"].to_numpy(dtype=float)) >= 2.5)
    ).astype(int)
    pred_stat_score = pred_stat_duration + pred_stat_delay + pred_stat_weather.astype(int)

    # Assessment-mode rules/statistics (use completed-step outcome fields).
    stage_loss_stats = train.groupby("stage")["loss_pct"].agg(["mean", "std"]).to_dict(orient="index")
    ps_loss_stats = (
        train.groupby(["product", "stage"])["loss_pct"]
        .agg(["mean", "std"])
        .reset_index()
        .rename(columns={"mean": "ps_loss_mean", "std": "ps_loss_std"})
    )
    ps_iqr = train.groupby(["product", "stage"])["loss_pct"].quantile([0.25, 0.75]).unstack().reset_index()
    ps_iqr = ps_iqr.rename(columns={0.25: "q1", 0.75: "q3"})
    stage_season_loss_stats = (
        train.groupby(["stage", "season"])["loss_pct"]
        .agg(["mean", "std"])
        .reset_index()
        .rename(columns={"mean": "ss_loss_mean", "std": "ss_loss_std"})
    )
    packaging_q95 = float(train.loc[train["stage"] == "emballage", "loss_pct"].quantile(0.95))
    loss_q90_global = float(train["loss_pct"].quantile(0.90))
    loss_q95_global = float(train["loss_pct"].quantile(0.95))

    assess_impossible_qty = ((test["qty_out"] > test["qty_in"]) | (test["qty_out"] < 0)).astype(int)
    assess_extreme_loss_stage = np.array(
        [
            int(
                row["loss_pct"] >= max(
                    stage_loss_q95.get(row["stage"], loss_q95_global),
                    stage_loss_stats.get(row["stage"], {}).get("mean", train["loss_pct"].mean())
                    + 2.0 * _safe_std(stage_loss_stats.get(row["stage"], {}).get("std", train["loss_pct"].std())),
                )
            )
            for _, row in test.iterrows()
        ],
        dtype=int,
    )
    assess_packaging_unexpected = (
        (test["stage"].astype(str) == "emballage") & (test["loss_pct"] >= packaging_q95)
    ).astype(int)
    assess_consistency_low_qty_high_loss = (
        (test["qty_in"] <= qty_in_q20) & (test["loss_pct"] >= loss_q90_global)
    ).astype(int)

    test_iqr = test.merge(ps_iqr, on=["product", "stage"], how="left")
    iqr = (test_iqr["q3"] - test_iqr["q1"]).fillna(train["loss_pct"].quantile(0.75) - train["loss_pct"].quantile(0.25))
    assess_ps_iqr = (
        test_iqr["loss_pct"]
        >= (test_iqr["q3"].fillna(train["loss_pct"].quantile(0.75)) + 1.5 * iqr)
    ).astype(int)

    assess_weather_stage_loss = (
        (test["stage"].astype(str) == "sechage")
        & (test["humidity"] >= humidity_q90_sechage)
        & (test["loss_pct"] >= loss_q90_global)
    ).astype(int)
    assess_rule_score = (
        assess_impossible_qty.to_numpy(dtype=int)
        + assess_extreme_loss_stage
        + assess_packaging_unexpected.to_numpy(dtype=int)
        + assess_consistency_low_qty_high_loss.to_numpy(dtype=int)
        + assess_ps_iqr.to_numpy(dtype=int)
        + assess_weather_stage_loss.to_numpy(dtype=int)
    )

    test_ps_loss = test.merge(ps_loss_stats, on=["product", "stage"], how="left")
    ps_loss_z = _zscore(
        test_ps_loss["loss_pct"],
        test_ps_loss["ps_loss_mean"].fillna(train["loss_pct"].mean()),
        test_ps_loss["ps_loss_std"].fillna(train["loss_pct"].std()),
    )
    test_ss_loss = test.merge(stage_season_loss_stats, on=["stage", "season"], how="left")
    ss_loss_z = _zscore(
        test_ss_loss["loss_pct"],
        test_ss_loss["ss_loss_mean"].fillna(train["loss_pct"].mean()),
        test_ss_loss["ss_loss_std"].fillna(train["loss_pct"].std()),
    )
    eff_mean = float(train["efficiency_pct"].mean())
    eff_std = _safe_std(float(train["efficiency_pct"].std()))
    eff_z = (pd.to_numeric(test["efficiency_pct"], errors="coerce").fillna(0.0).to_numpy(dtype=float) - eff_mean) / eff_std
    assess_stat_score = (
        (np.abs(ps_loss_z) >= 2.5).astype(int)
        + (np.abs(ss_loss_z) >= 2.5).astype(int)
        + (eff_z <= -2.0).astype(int)
    )

    candidate_defs: List[Tuple[str, str, str, np.ndarray, np.ndarray]] = []
    # Baseline ML
    candidate_defs.append(("IsolationForestBaseline", "prediction_mode", "ml", iforest_pred, iforest_score))

    # Prediction-mode candidates
    candidate_defs.append(("PredictionRulesOnly", "prediction_mode", "rule", (pred_rule_score >= 1).astype(int), pred_rule_score.astype(float)))
    candidate_defs.append(("PredictionRulesConservative", "prediction_mode", "rule", (pred_rule_score >= 2).astype(int), pred_rule_score.astype(float)))
    candidate_defs.append(("PredictionStatisticalOnly", "prediction_mode", "statistical", (pred_stat_score >= 1).astype(int), pred_stat_score.astype(float)))
    candidate_defs.append(("PredictionRulesPlusStatistical", "prediction_mode", "hybrid", ((pred_rule_score + pred_stat_score) >= 1).astype(int), (pred_rule_score + pred_stat_score).astype(float)))
    candidate_defs.append(("PredictionHybridBalanced", "prediction_mode", "hybrid", ((pred_rule_score + pred_stat_score) >= 2).astype(int) | ((iforest_pred == 1) & ((pred_rule_score + pred_stat_score) >= 1)), (pred_rule_score + pred_stat_score + iforest_score).astype(float)))
    candidate_defs.append(("PredictionHybridHighRecall", "prediction_mode", "hybrid", ((pred_rule_score >= 1) | (pred_stat_score >= 1) | (iforest_pred == 1)).astype(int), (pred_rule_score + pred_stat_score + iforest_score).astype(float)))

    # Assessment-mode candidates
    candidate_defs.append(("AssessmentRulesOnly", "assessment_mode", "rule", (assess_rule_score >= 1).astype(int), assess_rule_score.astype(float)))
    candidate_defs.append(("AssessmentRulesConservative", "assessment_mode", "rule", (assess_rule_score >= 2).astype(int), assess_rule_score.astype(float)))
    candidate_defs.append(("AssessmentStatisticalOnly", "assessment_mode", "statistical", (assess_stat_score >= 1).astype(int), assess_stat_score.astype(float)))
    candidate_defs.append(("AssessmentRulesPlusStatistical", "assessment_mode", "hybrid", ((assess_rule_score + assess_stat_score) >= 1).astype(int), (assess_rule_score + assess_stat_score).astype(float)))
    candidate_defs.append(("AssessmentHybridBalanced", "assessment_mode", "hybrid", (((assess_rule_score + assess_stat_score) >= 2) | ((assess_rule_score >= 1) & (iforest_pred == 1))).astype(int), (assess_rule_score + assess_stat_score + iforest_score).astype(float)))
    candidate_defs.append(("AssessmentHybridHighRecall", "assessment_mode", "hybrid", ((assess_rule_score >= 1) | (assess_stat_score >= 1) | (iforest_pred == 1)).astype(int), (assess_rule_score + assess_stat_score + iforest_score).astype(float)))

    rows: List[Dict[str, Any]] = []
    for name, mode, candidate_type, pred, score in candidate_defs:
        rows.append(_binary_metrics(pred=pred, score=score, mode=mode, candidate_type=candidate_type, name=name))

    prediction_rows = [row for row in rows if row["mode"] == "prediction_mode"]
    assessment_rows = [row for row in rows if row["mode"] == "assessment_mode"]
    prediction_ranked = sorted(
        prediction_rows,
        key=lambda row: (row["recall"], row["precision_at_10pct"], row["f1"], -row["false_positive_count"]),
        reverse=True,
    )
    assessment_ranked = sorted(
        assessment_rows,
        key=lambda row: (row["assessment_mode_gate_pass"], row["f1"], row["precision_at_10pct"], row["recall"]),
        reverse=True,
    )
    iforest_baseline = next(row for row in rows if row["candidate"] == "IsolationForestBaseline")
    best_prediction = prediction_ranked[0] if prediction_ranked else None
    best_assessment = assessment_ranked[0] if assessment_ranked else None
    assessment_gate_pass = bool(any(row["assessment_mode_gate_pass"] for row in assessment_rows))

    if assessment_gate_pass:
        decision = {"decision": "PASS", "reason": "assessment_mode_hybrid_passed_offline_gate"}
    elif best_assessment and float(best_assessment["f1"]) > float(iforest_baseline["f1"]):
        decision = {"decision": "PARTIAL", "reason": "hybrid_improves_over_iforest_but_gate_not_fully_met"}
    else:
        decision = {"decision": "FAIL", "reason": "no_material_improvement_over_iforest"}

    return {
        "explanation": (
            "IsolationForest underperforms because synthetic anomaly labels are injected using outcome shocks, while "
            "unsupervised context-only separation is weak. Rule/statistical checks align better with operational post-step anomalies."
        ),
        "classification_status_frozen": {
            "decision": "PARTIAL",
            "state": "improved_but_non_promoted",
            "best_prediction_mode_candidate": {
                "candidate": "Phase1C_LogRegBalanced_plus_HighOverride_balanced",
                "macro_f1": 0.4679,
                "high_risk_recall": 0.4783,
                "high_risk_precision": 0.0688,
                "false_low_high_risk_rate": 0.4348,
                "false_alarms": 149,
            },
        },
        "gate_definition": {
            "assessment_mode": {
                "f1_min": 0.75,
                "precision_min": 0.60,
                "recall_min": 0.80,
                "precision_at_10pct_min": 0.60,
            },
            "prediction_mode": {
                "note": "Reported separately as context risk indicators; not used for production promotion.",
            },
        },
        "rule_definitions": {
            "prediction_mode_rules": [
                "weather_stage_sechage_extreme",
                "duration_delay_extreme_by_stage",
                "grade_c_stage_weather",
                "low_qty_with_extreme_duration_or_delay",
            ],
            "assessment_mode_rules": [
                "qty_out_gt_qty_in_or_invalid",
                "extreme_loss_by_stage",
                "product_stage_iqr_loss_outlier",
                "duration_delay_extreme",
                "weather_stage_plus_high_loss",
                "unexpected_packaging_loss",
            ],
            "assessment_only_fields": ["qty_out", "loss_qty", "loss_pct", "efficiency_pct"],
        },
        "isolation_forest_baseline": iforest_baseline,
        "prediction_mode_candidates": prediction_ranked,
        "assessment_mode_candidates": assessment_ranked,
        "best_prediction_mode_candidate": best_prediction,
        "best_assessment_mode_candidate": best_assessment,
        "final_anomaly_decision": decision,
        "all_candidates": rows,
        "promotion_note": "Anomaly results are synthetic/offline only; runtime remains non-promoted.",
    }


def _evaluate_recommendation_ranking(
    frame: pd.DataFrame,
    train_idx: pd.Index,
    test_idx: pd.Index,
    anomaly_diagnostics: Dict[str, Any],
) -> Dict[str, Any]:
    train = frame.loc[train_idx].copy().reset_index(drop=True)
    test = frame.loc[test_idx].copy().reset_index(drop=True)

    actions = [
        "increase_ventilation_delay_drying",
        "inspect_process_step_material_balance",
        "reduce_waiting_time_before_next_stage",
        "verify_packaging_method_material",
        "review_stage_procedure_operator_method",
        "monitor_only_no_strong_action",
    ]
    action_templates = {
        "increase_ventilation_delay_drying": "increase ventilation / delay drying / protect from humidity",
        "inspect_process_step_material_balance": "inspect process step and verify material balance",
        "reduce_waiting_time_before_next_stage": "reduce waiting time before next stage",
        "verify_packaging_method_material": "verify packaging method and material",
        "review_stage_procedure_operator_method": "review stage procedure and operator method",
        "monitor_only_no_strong_action": "monitor only / no strong action",
    }

    stage_priority_map = {"sechage": 1.0, "tri": 0.8, "nettoyage": 0.7, "emballage": 0.75}
    product_stage_mean_loss = train.groupby(["product", "stage"])["loss_pct"].mean().to_dict()
    default_ps_loss = float(train["loss_pct"].mean())

    humidity_q90 = float(train["humidity"].quantile(0.90))
    rainfall_q90 = float(train["rainfall"].quantile(0.90))
    dew_q90 = float(train["dew_point"].quantile(0.90))
    duration_q90 = float(train["step_duration_minutes"].quantile(0.90))
    delay_q90 = float(train["delay_since_previous_step_minutes"].quantile(0.90))
    loss_q70 = float(train["loss_pct"].quantile(0.70))
    loss_q90 = float(train["loss_pct"].quantile(0.90))
    loss_q95 = float(train["loss_pct"].quantile(0.95))
    eff_q10 = float(train["efficiency_pct"].quantile(0.10))

    def _norm(value: float, threshold: float) -> float:
        if threshold <= 0:
            return 0.0
        return float(np.clip(value / threshold, 0.0, 2.0))

    def _build_row_features(row: pd.Series, *, mode: str) -> Dict[str, float]:
        stage = str(row["stage"])
        product = str(row["product"])
        ps_key = (product, stage)

        weather_duration_risk = (
            0.30 * _norm(float(row["humidity"]), humidity_q90)
            + 0.25 * _norm(float(row["rainfall"]), rainfall_q90)
            + 0.20 * _norm(float(row["dew_point"]), dew_q90)
            + 0.15 * _norm(float(row["step_duration_minutes"]), duration_q90)
            + 0.10 * _norm(float(row["delay_since_previous_step_minutes"]), delay_q90)
        )
        stage_priority_score = float(stage_priority_map.get(stage, 0.6))
        recurrence_score = float(np.clip(product_stage_mean_loss.get(ps_key, default_ps_loss) / max(default_ps_loss, 1e-6), 0.0, 2.0))
        evidence_quality_score = 1.0 - (0.35 if int(row["missing_duration_flag"]) == 1 else 0.0)

        loss_severity_score = 0.0
        anomaly_assessment_score = 0.0
        classification_risk_score = 0.0
        if mode == "assessment_mode":
            loss_pct = float(row["loss_pct"])
            loss_severity_score = float(np.clip((loss_pct - loss_q70) / max(loss_q95 - loss_q70, 1e-6), 0.0, 2.0))
            anomaly_assessment_score = 1.0 if int(row["anomaly_label_synthetic"]) == 1 else 0.0
            if loss_pct >= loss_q90:
                classification_risk_score = 1.0
            elif loss_pct >= loss_q70:
                classification_risk_score = 0.6
            else:
                classification_risk_score = 0.2
            if float(row["efficiency_pct"]) <= eff_q10:
                anomaly_assessment_score += 0.5
        else:
            # prediction-mode approximation using only context.
            classification_risk_score = float(
                np.clip(
                    0.40 * stage_priority_score
                    + 0.35 * weather_duration_risk
                    + 0.25 * recurrence_score,
                    0.0,
                    1.5,
                )
            )

        confidence_penalty = 0.25 if mode == "prediction_mode" else 0.10
        return {
            "loss_severity_score": float(loss_severity_score),
            "anomaly_score_assessment_mode": float(anomaly_assessment_score),
            "classification_risk_score": float(classification_risk_score),
            "weather_duration_risk_score": float(weather_duration_risk),
            "stage_priority_score": float(stage_priority_score),
            "recurrence_or_product_stage_baseline_score": float(recurrence_score),
            "evidence_quality_score": float(evidence_quality_score),
            "confidence_penalty": float(confidence_penalty),
        }

    def _action_scores(features: Dict[str, float], row: pd.Series, strategy: str) -> Dict[str, float]:
        is_drying = str(row["stage"]) == "sechage"
        is_packaging = str(row["stage"]) == "emballage"
        anomaly_signal = features["anomaly_score_assessment_mode"] + features["loss_severity_score"]
        context_signal = (
            0.5 * features["weather_duration_risk_score"]
            + 0.3 * features["classification_risk_score"]
            + 0.2 * features["recurrence_or_product_stage_baseline_score"]
        )
        severity = anomaly_signal + context_signal + 0.25 * features["stage_priority_score"]

        base = {
            "increase_ventilation_delay_drying": (1.2 if is_drying else 0.4) * (features["weather_duration_risk_score"] + 0.4 * features["classification_risk_score"]),
            "inspect_process_step_material_balance": 1.1 * (anomaly_signal + 0.3 * features["classification_risk_score"]),
            "reduce_waiting_time_before_next_stage": 0.9 * features["weather_duration_risk_score"] + 0.25 * features["stage_priority_score"],
            "verify_packaging_method_material": (1.2 if is_packaging else 0.3) * (severity + 0.2),
            "review_stage_procedure_operator_method": 0.7 * features["recurrence_or_product_stage_baseline_score"] + 0.5 * severity,
            "monitor_only_no_strong_action": max(0.0, 1.2 - severity),
        }

        if strategy == "SeverityFirstRanking":
            base["inspect_process_step_material_balance"] += 0.8 * anomaly_signal
            base["review_stage_procedure_operator_method"] += 0.4 * features["loss_severity_score"]
            base["monitor_only_no_strong_action"] -= 0.5 * severity
        elif strategy == "HybridEvidenceRanking":
            evidence_boost = 0.4 * features["evidence_quality_score"]
            for key in base:
                base[key] += evidence_boost
            base["increase_ventilation_delay_drying"] += 0.4 * features["weather_duration_risk_score"]
            base["reduce_waiting_time_before_next_stage"] += 0.3 * features["weather_duration_risk_score"]
            base["inspect_process_step_material_balance"] += 0.6 * anomaly_signal
        elif strategy == "ConservativeRanking":
            base["monitor_only_no_strong_action"] += 0.6
            base["inspect_process_step_material_balance"] += 0.2 * anomaly_signal
            base["review_stage_procedure_operator_method"] += 0.2 * features["recurrence_or_product_stage_baseline_score"]
            if severity > 1.2:
                base["monitor_only_no_strong_action"] -= 0.8
        elif strategy == "FinalConservativeEvidenceRanking":
            high_loss = float(row["loss_pct"]) >= loss_q90
            medium_loss = float(row["loss_pct"]) >= loss_q70
            anomaly_true = int(row["anomaly_label_synthetic"]) == 1
            drying_weather = (
                str(row["stage"]) == "sechage"
                and (
                    float(row["humidity"]) >= humidity_q90
                    or float(row["rainfall"]) >= rainfall_q90
                    or float(row["dew_point"]) >= dew_q90
                )
            )
            duration_delay_extreme = (
                float(row["step_duration_minutes"]) >= duration_q90
                or float(row["delay_since_previous_step_minutes"]) >= delay_q90
            )
            packaging_alert = str(row["stage"]) == "emballage" and float(row["loss_pct"]) >= loss_q70
            recurrence_high = features["recurrence_or_product_stage_baseline_score"] >= 1.0

            base["monitor_only_no_strong_action"] += 0.8
            if anomaly_true or high_loss:
                base["inspect_process_step_material_balance"] += 2.2
                base["monitor_only_no_strong_action"] -= 2.2
            if drying_weather:
                base["increase_ventilation_delay_drying"] += 1.6
                base["monitor_only_no_strong_action"] -= 0.6
            if duration_delay_extreme:
                base["reduce_waiting_time_before_next_stage"] += 1.2
                base["monitor_only_no_strong_action"] -= 0.5
            if packaging_alert:
                base["verify_packaging_method_material"] += 1.5
                base["monitor_only_no_strong_action"] -= 0.5
            if medium_loss or recurrence_high:
                base["review_stage_procedure_operator_method"] += 1.0
            if features["evidence_quality_score"] < 0.8:
                base["monitor_only_no_strong_action"] += 0.7
        # RuleDefaultRanking keeps base.

        # Apply confidence penalty to aggressive interventions.
        for key in [
            "increase_ventilation_delay_drying",
            "inspect_process_step_material_balance",
            "reduce_waiting_time_before_next_stage",
            "verify_packaging_method_material",
            "review_stage_procedure_operator_method",
        ]:
            penalty_scale = 0.55 if strategy in {"ConservativeRanking", "FinalConservativeEvidenceRanking"} else 1.0
            base[key] -= features["confidence_penalty"] * penalty_scale
        return base

    def _proxy_relevance(row: pd.Series, action: str, *, mode: str) -> int:
        high_loss = float(row["loss_pct"]) >= loss_q90
        medium_loss = float(row["loss_pct"]) >= loss_q70
        anomaly_true = int(row["anomaly_label_synthetic"]) == 1
        drying_weather = (
            str(row["stage"]) == "sechage"
            and (
                float(row["humidity"]) >= humidity_q90
                or float(row["rainfall"]) >= rainfall_q90
                or float(row["dew_point"]) >= dew_q90
            )
        )
        duration_delay_extreme = (
            float(row["step_duration_minutes"]) >= duration_q90
            or float(row["delay_since_previous_step_minutes"]) >= delay_q90
        )
        packaging_alert = str(row["stage"]) == "emballage" and float(row["loss_pct"]) >= loss_q70
        recurrence_high = product_stage_mean_loss.get((str(row["product"]), str(row["stage"])), default_ps_loss) >= default_ps_loss

        if action == "inspect_process_step_material_balance":
            if anomaly_true or high_loss:
                return 2
            if medium_loss:
                return 1
        if action == "increase_ventilation_delay_drying":
            if drying_weather:
                return 2
            if str(row["stage"]) == "sechage":
                return 1
        if action == "reduce_waiting_time_before_next_stage":
            if duration_delay_extreme:
                return 2
            if str(row["stage"]) in {"sechage", "tri"}:
                return 1
        if action == "verify_packaging_method_material":
            if packaging_alert:
                return 2
            if str(row["stage"]) == "emballage":
                return 1
        if action == "review_stage_procedure_operator_method":
            if high_loss and recurrence_high:
                return 2
            if medium_loss or recurrence_high:
                return 1
        if action == "monitor_only_no_strong_action":
            if not anomaly_true and not medium_loss and not duration_delay_extreme:
                return 1
        if mode == "prediction_mode" and action == "monitor_only_no_strong_action" and not drying_weather:
            return max(1, 0)
        return 0

    def _rank_and_eval(mode: str, strategy: str) -> Dict[str, Any]:
        ranked_actions: List[List[str]] = []
        rel_lists: List[List[int]] = []
        top1_relevance: List[int] = []
        top1_anomaly_or_loss_hit = 0
        top1_anomaly_or_loss_total = 0
        for _, row in test.iterrows():
            features = _build_row_features(row, mode=mode)
            action_score_map = _action_scores(features, row, strategy=strategy)
            ranking = sorted(actions, key=lambda name: action_score_map[name], reverse=True)
            relevances = [_proxy_relevance(row, action, mode=mode) for action in ranking]
            ranked_actions.append(ranking)
            rel_lists.append(relevances)
            top1_relevance.append(relevances[0])

            high_event = (int(row["anomaly_label_synthetic"]) == 1) or (float(row["loss_pct"]) >= loss_q90)
            if high_event:
                top1_anomaly_or_loss_total += 1
                if ranking[0] != "monitor_only_no_strong_action":
                    top1_anomaly_or_loss_hit += 1

        def _precision_at_k(k: int) -> float:
            vals = []
            for rel in rel_lists:
                topk = rel[:k]
                vals.append(float(np.mean([1 if x >= 1 else 0 for x in topk])))
            return float(np.mean(vals)) if vals else 0.0

        def _ndcg_at_k(k: int) -> float:
            scores = []
            for rel in rel_lists:
                topk = rel[:k]
                dcg = 0.0
                for i, r in enumerate(topk):
                    dcg += (2**r - 1) / np.log2(i + 2)
                ideal = sorted(rel, reverse=True)[:k]
                idcg = 0.0
                for i, r in enumerate(ideal):
                    idcg += (2**r - 1) / np.log2(i + 2)
                scores.append(float(dcg / idcg) if idcg > 0 else 0.0)
            return float(np.mean(scores)) if scores else 0.0

        p3 = _precision_at_k(3)
        p5 = _precision_at_k(5)
        ndcg5 = _ndcg_at_k(5)
        mean_top_rel = float(np.mean(top1_relevance)) if top1_relevance else 0.0
        coverage = float(top1_anomaly_or_loss_hit / top1_anomaly_or_loss_total) if top1_anomaly_or_loss_total > 0 else 0.0

        gate_pass = False
        if mode == "assessment_mode":
            gate_pass = bool(p3 >= 0.70 and ndcg5 >= 0.85 and coverage >= 0.90)

        return {
            "strategy": strategy,
            "mode": mode,
            "precision_at_3": float(p3),
            "precision_at_5": float(p5),
            "ndcg_at_5": float(ndcg5),
            "mean_relevance_top_1": float(mean_top_rel),
            "top_priority_anomaly_high_loss_coverage": float(coverage),
            "gate_pass": bool(gate_pass),
            "sample_top_actions": ranked_actions[:5],
        }

    strategies = [
        "RuleDefaultRanking",
        "SeverityFirstRanking",
        "HybridEvidenceRanking",
        "ConservativeRanking",
        "FinalConservativeEvidenceRanking",
    ]
    rows: List[Dict[str, Any]] = []
    for mode in ["prediction_mode", "assessment_mode"]:
        for strategy in strategies:
            rows.append(_rank_and_eval(mode=mode, strategy=strategy))

    pred_rows = [row for row in rows if row["mode"] == "prediction_mode"]
    assess_rows = [row for row in rows if row["mode"] == "assessment_mode"]
    pred_ranked = sorted(pred_rows, key=lambda row: (row["precision_at_3"], row["ndcg_at_5"], row["top_priority_anomaly_high_loss_coverage"]), reverse=True)
    assess_ranked = sorted(assess_rows, key=lambda row: (row["gate_pass"], row["precision_at_3"], row["ndcg_at_5"], row["top_priority_anomaly_high_loss_coverage"]), reverse=True)
    best_pred = pred_ranked[0] if pred_ranked else None
    best_assess = assess_ranked[0] if assess_ranked else None

    if best_assess and best_assess["gate_pass"]:
        final_decision = {"decision": "PASS", "reason": "synthetic_assessment_mode_recommendation_ranking_pass"}
    elif best_assess and best_assess["precision_at_3"] >= 0.60:
        final_decision = {"decision": "PARTIAL", "reason": "proxy_ranking_is_useful_but_gate_not_fully_met"}
    else:
        final_decision = {"decision": "FAIL", "reason": "ranking_proxy_quality_below_threshold"}

    return {
        "warning": "Synthetic proxy relevance is not real recommendation outcome evidence.",
        "status_summary_frozen": {
            "regression": "baseline_fallback_not_ml_promoted",
            "classification": "PARTIAL_improved_but_non_promoted",
            "anomaly": anomaly_diagnostics.get("final_anomaly_decision", {}),
            "runtime": "unchanged_non_promoted_rule_based",
        },
        "action_templates": action_templates,
        "ranking_score_definition": {
            "components": [
                "loss_severity_score",
                "anomaly_score_assessment_mode",
                "classification_risk_score",
                "weather_duration_risk_score",
                "stage_priority_score",
                "recurrence_or_product_stage_baseline_score",
                "evidence_quality_score",
                "confidence_penalty",
            ],
            "strategies": strategies,
        },
        "proxy_relevance_definition": {
            "high": "anomaly true OR high loss OR severe stage/weather/duration condition",
            "medium": "moderate loss or moderate contextual risk",
            "low": "otherwise",
            "boundary": "Synthetic proxy relevance is not real recommendation outcome evidence.",
        },
        "prediction_mode_candidates": pred_ranked,
        "assessment_mode_candidates": assess_ranked,
        "best_prediction_mode_candidate": best_pred,
        "best_assessment_mode_candidate": best_assess,
        "gate_definition": {
            "assessment_mode": {
                "precision_at_3_min": 0.70,
                "ndcg_at_5_min": 0.85,
                "top_priority_anomaly_high_loss_coverage_min": 0.90,
            },
            "prediction_mode": {"report_only": True},
        },
        "final_recommendation_ranking_decision": final_decision,
        "forbidden_claims": [
            "production-ready learned recommender",
            "real cooperative recommendation uplift",
            "runtime promoted recommendation model",
        ],
    }


def _evaluate_split(
    frame: pd.DataFrame,
    train_idx: pd.Index,
    test_idx: pd.Index,
    split_name: str,
) -> Dict[str, Any]:
    categorical_cols = [
        "product",
        "stage",
        "season",
        "region",
        "grade",
        "synthetic_cooperative_id",
        "product_stage",
        "grade_stage",
        "season_stage",
    ]
    numeric_cols = [
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
        "humidity_stage",
        "rainfall_stage",
        "duration_stage",
        "delay_product",
    ]

    regression = _evaluate_regression_split(
        frame,
        train_idx,
        test_idx,
        split_name=split_name,
        categorical_cols=categorical_cols,
        numeric_cols=numeric_cols,
    )
    classification = _evaluate_classification_split(
        frame,
        train_idx,
        test_idx,
        split_name=split_name,
        categorical_cols=categorical_cols,
        numeric_cols=numeric_cols,
    )
    anomaly_diagnostics = _evaluate_anomaly_diagnostics(
        frame,
        train_idx,
        test_idx,
        categorical_cols=categorical_cols,
        numeric_cols=numeric_cols,
    )
    recommendation_ranking = _evaluate_recommendation_ranking(
        frame,
        train_idx,
        test_idx,
        anomaly_diagnostics=anomaly_diagnostics,
    )

    return {
        "split": split_name,
        "train_rows": int(len(train_idx)),
        "test_rows": int(len(test_idx)),
        "regression": regression,
        "classification": classification,
        "anomaly_diagnostics": anomaly_diagnostics,
        "recommendation_ranking": recommendation_ranking,
    }


def _render_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# {SYNTHETIC_OFFLINE_WARNING}")
    lines.append("")
    lines.append("## Dataset")
    lines.append(f"- Source label: {report['source_label']}")
    lines.append(f"- Data origin expected: {report['dataset']['data_origin_expected']}")
    lines.append(f"- Row count: {report['dataset']['row_count']}")
    lines.append(f"- Products: {', '.join(report['dataset']['products'])}")
    lines.append(f"- Stages: {', '.join(report['dataset']['stages'])}")
    lines.append("")
    lines.append("## Split Summary")
    for split_key, payload in report["split_info"].items():
        lines.append(f"- {split_key}: {payload}")
    lines.append("")
    lines.append("## Regression Candidate Table (Time Split Primary)")
    lines.append("| candidate | mae | best_baseline | best_baseline_mae | rel_improvement_pct | beats_baseline | sechage_beats_baseline | gate_pass |")
    lines.append("|---|---:|---|---:|---:|---|---|---|")
    for row in report["evaluation"]["time_based"]["regression"]["candidates_ranked"]:
        lines.append(
            f"| {row['candidate']} | {row['mae']:.4f} | {row['best_baseline_name']} | {row['best_baseline_mae']:.4f} | "
            f"{row['relative_improvement_pct_vs_best_baseline']:.2f}% | {row['beats_best_baseline']} | "
            f"{row['sechage_beats_stage_baseline']} | {row['gate_pass']} |"
        )
    lines.append("")
    cls_payload = report["evaluation"]["time_based"]["classification"]
    lines.append("## Previous Phase 1 Reference")
    lines.append(f"- Candidate: {cls_payload['phase1_reference']['candidate']}")
    lines.append(f"- Macro-F1: {cls_payload['phase1_reference']['macro_f1']:.4f}")
    lines.append(f"- High-risk recall: {cls_payload['phase1_reference']['high_risk_recall']:.4f}")
    lines.append(f"- High-risk precision: {cls_payload['phase1_reference']['high_risk_precision']:.4f}")
    lines.append(f"- False-low-high-risk rate: {cls_payload['phase1_reference']['false_low_high_risk_rate']:.4f}")
    lines.append("")
    lines.append("## Previous Phase 1B Reference")
    lines.append(f"- Candidate: {cls_payload['phase1b_reference']['candidate']}")
    lines.append(f"- Macro-F1: {cls_payload['phase1b_reference']['macro_f1']:.4f}")
    lines.append(f"- High-risk recall: {cls_payload['phase1b_reference']['high_risk_recall']:.4f}")
    lines.append(f"- High-risk precision: {cls_payload['phase1b_reference']['high_risk_precision']:.4f}")
    lines.append(f"- False-low-high-risk rate: {cls_payload['phase1b_reference']['false_low_high_risk_rate']:.4f}")
    lines.append(f"- False alarms: {int(cls_payload['phase1b_reference']['false_alarms'])}")
    lines.append("")
    lines.append("## Phase 1B Prediction-Mode Candidate Table (Time Split Primary)")
    lines.append("| candidate | macro_f1 | high_recall | high_precision | false_low_high_rate | high_detected | false_alarms | gate_pass |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for row in cls_payload["prediction_mode_candidates_ranked"]:
        lines.append(
            f"| {row['candidate']} | {row['macro_f1']:.4f} | {row['high_risk_recall']:.4f} | {row['high_risk_precision']:.4f} | "
            f"{row['false_low_high_risk_rate']:.4f} | {row['high_risk_detected_count']} | {row['false_alarms_count']} | {row['gate_pass']} |"
        )
    lines.append("")
    lines.append("## Phase 1B Assessment-Mode Candidate Table (Time Split Primary)")
    lines.append("| candidate | macro_f1 | high_recall | high_precision | false_low_high_rate | high_detected | false_alarms | gate_pass |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for row in cls_payload["assessment_mode_candidates_ranked"]:
        lines.append(
            f"| {row['candidate']} | {row['macro_f1']:.4f} | {row['high_risk_recall']:.4f} | {row['high_risk_precision']:.4f} | "
            f"{row['false_low_high_risk_rate']:.4f} | {row['high_risk_detected_count']} | {row['false_alarms_count']} | {row['gate_pass']} |"
        )
    lines.append("")
    lines.append("## Best Phase 1B Candidates")
    lines.append(f"- Best prediction-mode: {cls_payload['best_prediction_mode_candidate']['candidate'] if cls_payload['best_prediction_mode_candidate'] else 'None'}")
    lines.append(f"- Best assessment-mode: {cls_payload['best_assessment_mode_candidate']['candidate'] if cls_payload['best_assessment_mode_candidate'] else 'None'}")
    lines.append("")
    lines.append("## Critical-Risk Diagnostics (Time Split Primary)")
    lines.append(f"- Current reference model: {cls_payload['current_reference']['candidate']}")
    lines.append(f"- Current reference macro-F1: {cls_payload['current_reference']['macro_f1']:.4f}")
    lines.append(f"- Current reference high-risk recall: {cls_payload['current_reference']['high_risk_recall']:.4f}")
    lines.append(
        f"- Current reference false-low-high-risk rate: {cls_payload['current_reference']['false_low_high_risk_rate']:.4f}"
    )
    diag = cls_payload["critical_risk_failure_diagnostics"]
    lines.append(f"- Train class distribution: {diag['train_class_distribution']}")
    lines.append(f"- Test class distribution: {diag['test_class_distribution']}")
    lines.append(f"- High-risk support count: {diag['high_risk_support_count']}")
    lines.append(f"- Confusion matrix (current model): {diag['confusion_matrix_current_model']}")
    lines.append(f"- High-risk predicted as low/medium/high: {diag['high_risk_predictions_breakdown']}")
    lines.append(f"- High-risk cluster by stage: {diag['high_risk_cluster']['by_stage']}")
    lines.append(f"- High-risk cluster by product: {diag['high_risk_cluster']['by_product']}")
    lines.append(f"- High-risk cluster by season: {diag['high_risk_cluster']['by_season']}")
    lines.append("")
    lines.append("## Rule Definition (Phase 1B)")
    lines.append(f"- Definition: {cls_payload['rule_definition']}")
    lines.append("")
    lines.append("## Phase 1C Pareto Frontier (Prediction-Mode)")
    lines.append("| candidate | macro_f1 | high_recall | high_precision | false_alarms |")
    lines.append("|---|---:|---:|---:|---:|")
    for row in cls_payload["phase1c_pareto_frontier_prediction_mode"]:
        lines.append(
            f"| {row['candidate']} | {row['macro_f1']:.4f} | {row['high_risk_recall']:.4f} | {row['high_risk_precision']:.4f} | {row['false_alarms_count']} |"
        )
    lines.append("")
    lines.append("## Phase 1C Selection Summary")
    lines.append(f"- Best recall candidate: {cls_payload['phase1c_best_recall_prediction_mode']['candidate'] if cls_payload['phase1c_best_recall_prediction_mode'] else 'None'}")
    lines.append(f"- Best macro-F1 candidate: {cls_payload['phase1c_best_macro_f1_prediction_mode']['candidate'] if cls_payload['phase1c_best_macro_f1_prediction_mode'] else 'None'}")
    lines.append(f"- Best balanced candidate: {cls_payload['phase1c_best_balanced_prediction_mode']['candidate'] if cls_payload['phase1c_best_balanced_prediction_mode'] else 'None'}")
    lines.append(
        f"- Lowest false-alarm candidate with recall>0: "
        f"{cls_payload['phase1c_lowest_false_alarm_with_recall_prediction_mode']['candidate'] if cls_payload['phase1c_lowest_false_alarm_with_recall_prediction_mode'] else 'None'}"
    )
    lines.append(
        f"- Final classification decision (Phase 1C): {cls_payload['phase1c_final_decision']['decision']} "
        f"({cls_payload['phase1c_final_decision']['reason']})"
    )
    lines.append("")
    lines.append("## Threshold Tuning Tradeoff (Time Split Primary)")
    lines.append("| source_model | high_threshold | macro_f1 | high_recall | high_precision | false_low_high_rate |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for row in cls_payload["threshold_tuning_tradeoff"]:
        lines.append(
            f"| {row['source_model']} | {row['threshold']:.2f} | {row['macro_f1']:.4f} | {row['high_risk_recall']:.4f} | "
            f"{row['high_risk_precision']:.4f} | {row['false_low_high_risk_rate']:.4f} |"
        )
    lines.append("")
    lines.append("## Classification Gate (Primary)")
    lines.append("- high-risk recall >= 0.40")
    lines.append("- macro-F1 >= 0.50")
    lines.append("- false-low-high-risk rate must improve vs current reference")
    lines.append(f"- Any candidate passed: {cls_payload['any_gate_passed']}")
    lines.append("")
    lines.append("## Classification Freeze (Phase 2)")
    frozen = report["evaluation"]["time_based"]["anomaly_diagnostics"]["classification_status_frozen"]
    lines.append(
        f"- Classification decision remains: {frozen['decision']} ({frozen['state']}). No further classification tuning in this phase."
    )
    lines.append(f"- Frozen best prediction-mode candidate: {frozen['best_prediction_mode_candidate']}")
    lines.append("")
    lines.append("## Anomaly Diagnostic")
    anom = report["evaluation"]["time_based"]["anomaly_diagnostics"]
    lines.append(f"- Explanation: {anom['explanation']}")
    iso = anom["isolation_forest_baseline"]
    lines.append(
        f"- IsolationForest baseline: precision={iso['precision']:.4f}, recall={iso['recall']:.4f}, "
        f"f1={iso['f1']:.4f}, precision@10%={iso['precision_at_10pct']:.4f}, tp={iso['tp']}, fp={iso['fp']}, fn={iso['fn']}"
    )
    lines.append("")
    lines.append("## Anomaly Candidate Table (Prediction-Mode)")
    lines.append("| candidate | type | precision | recall | f1 | precision@10% | fp | fn | tp | gate_pass |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in anom["prediction_mode_candidates"]:
        lines.append(
            f"| {row['candidate']} | {row['candidate_type']} | {row['precision']:.4f} | {row['recall']:.4f} | "
            f"{row['f1']:.4f} | {row['precision_at_10pct']:.4f} | {row['fp']} | {row['fn']} | {row['tp']} | {row['prediction_mode_gate_pass']} |"
        )
    lines.append("")
    lines.append("## Anomaly Candidate Table (Assessment-Mode)")
    lines.append("| candidate | type | precision | recall | f1 | precision@10% | fp | fn | tp | gate_pass |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in anom["assessment_mode_candidates"]:
        lines.append(
            f"| {row['candidate']} | {row['candidate_type']} | {row['precision']:.4f} | {row['recall']:.4f} | "
            f"{row['f1']:.4f} | {row['precision_at_10pct']:.4f} | {row['fp']} | {row['fn']} | {row['tp']} | {row['assessment_mode_gate_pass']} |"
        )
    lines.append("")
    lines.append("## Anomaly Best Candidates")
    lines.append(f"- Best prediction-mode anomaly/risk candidate: {anom['best_prediction_mode_candidate']['candidate'] if anom['best_prediction_mode_candidate'] else 'None'}")
    lines.append(f"- Best assessment-mode anomaly candidate: {anom['best_assessment_mode_candidate']['candidate'] if anom['best_assessment_mode_candidate'] else 'None'}")
    lines.append(f"- Final anomaly decision: {anom['final_anomaly_decision']['decision']} ({anom['final_anomaly_decision']['reason']})")
    lines.append("")
    lines.append("## Anomaly Rule Logic")
    lines.append(f"- Rule definitions: {anom['rule_definitions']}")
    lines.append(f"- Gate definition: {anom['gate_definition']}")
    lines.append(f"- Promotion note: {anom['promotion_note']}")
    lines.append("")
    rec = report["evaluation"]["time_based"]["recommendation_ranking"]
    lines.append("## Recommendation Ranking (Phase 3)")
    lines.append(f"- Proxy relevance warning: {rec['warning']}")
    lines.append(f"- Frozen status summary: {rec['status_summary_frozen']}")
    lines.append(f"- Action templates: {rec['action_templates']}")
    lines.append(f"- Ranking score definition: {rec['ranking_score_definition']}")
    lines.append("")
    lines.append("## Recommendation Ranking Candidates (Prediction-Mode)")
    lines.append("| strategy | Precision@3 | Precision@5 | NDCG@5 | mean top relevance | anomaly/high-loss top coverage | gate_pass |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for row in rec["prediction_mode_candidates"]:
        lines.append(
            f"| {row['strategy']} | {row['precision_at_3']:.4f} | {row['precision_at_5']:.4f} | {row['ndcg_at_5']:.4f} | "
            f"{row['mean_relevance_top_1']:.4f} | {row['top_priority_anomaly_high_loss_coverage']:.4f} | {row['gate_pass']} |"
        )
    lines.append("")
    lines.append("## Recommendation Ranking Candidates (Assessment-Mode)")
    lines.append("| strategy | Precision@3 | Precision@5 | NDCG@5 | mean top relevance | anomaly/high-loss top coverage | gate_pass |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for row in rec["assessment_mode_candidates"]:
        lines.append(
            f"| {row['strategy']} | {row['precision_at_3']:.4f} | {row['precision_at_5']:.4f} | {row['ndcg_at_5']:.4f} | "
            f"{row['mean_relevance_top_1']:.4f} | {row['top_priority_anomaly_high_loss_coverage']:.4f} | {row['gate_pass']} |"
        )
    lines.append("")
    lines.append("## Recommendation Ranking Best Candidates")
    lines.append(
        f"- Best prediction-mode ranking candidate: {rec['best_prediction_mode_candidate']['strategy'] if rec['best_prediction_mode_candidate'] else 'None'}"
    )
    lines.append(
        f"- Best assessment-mode ranking candidate: {rec['best_assessment_mode_candidate']['strategy'] if rec['best_assessment_mode_candidate'] else 'None'}"
    )
    lines.append(
        f"- Final recommendation-ranking decision: {rec['final_recommendation_ranking_decision']['decision']} "
        f"({rec['final_recommendation_ranking_decision']['reason']})"
    )
    lines.append("")
    lines.append("## Claims Guardrail")
    lines.append("### Allowed claims")
    for item in report["claims_guardrail"]["allowed_claims"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Forbidden claims")
    for item in report["claims_guardrail"]["forbidden_claims"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Scope Boundary")
    lines.append("- Offline synthetic benchmark only.")
    lines.append("- Not mixed with Supabase app data.")
    lines.append("- Not used for production promotion.")
    lines.append("- No runtime model replacement.")
    return "\n".join(lines) + "\n"


def _build_critical_risk_report(report: Dict[str, Any]) -> Dict[str, Any]:
    time_cls = report["evaluation"]["time_based"]["classification"]
    best_prediction_mode = time_cls["best_prediction_mode_candidate"] or {}
    best_assessment_mode = time_cls["best_assessment_mode_candidate"] or {}
    return {
        "warning": SYNTHETIC_OFFLINE_WARNING,
        "source_label": SOURCE_LABEL,
        "source": "synthetic_offline_critical_risk",
        "dataset": report["dataset"],
        "split_info": report["split_info"],
        "phase1_reference": time_cls["phase1_reference"],
        "phase1b_reference": time_cls["phase1b_reference"],
        "critical_risk_diagnostics": time_cls["critical_risk_failure_diagnostics"],
        "rule_definition": time_cls["rule_definition"],
        "threshold_tuning_tradeoff": time_cls["threshold_tuning_tradeoff"],
        "gates": time_cls["gates"],
        "phase1c_pareto_frontier_prediction_mode": time_cls["phase1c_pareto_frontier_prediction_mode"],
        "phase1c_best_recall_prediction_mode": time_cls["phase1c_best_recall_prediction_mode"],
        "phase1c_best_macro_f1_prediction_mode": time_cls["phase1c_best_macro_f1_prediction_mode"],
        "phase1c_best_balanced_prediction_mode": time_cls["phase1c_best_balanced_prediction_mode"],
        "phase1c_lowest_false_alarm_with_recall_prediction_mode": time_cls["phase1c_lowest_false_alarm_with_recall_prediction_mode"],
        "phase1c_final_decision": time_cls["phase1c_final_decision"],
        "best_prediction_mode_candidate": best_prediction_mode,
        "best_assessment_mode_candidate": best_assessment_mode,
        "prediction_mode_candidates": time_cls["prediction_mode_candidates_ranked"],
        "assessment_mode_candidates": time_cls["assessment_mode_candidates_ranked"],
        "all_candidates_time_split": time_cls["candidates_ranked"],
        "boundary": {
            "offline_only": True,
            "non_production_claims_only": True,
            "runtime_model_unchanged": True,
        },
    }


def _render_critical_risk_markdown(critical_report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# {SYNTHETIC_OFFLINE_WARNING}")
    lines.append("")
    lines.append("## Focus")
    lines.append("- Offline synthetic critical-risk detection analysis only.")
    lines.append("")
    lines.append("## Previous Phase 1 Reference")
    phase1 = critical_report["phase1_reference"]
    lines.append(f"- Candidate: {phase1.get('candidate')}")
    lines.append(f"- Macro-F1: {float(phase1.get('macro_f1', 0.0)):.4f}")
    lines.append(f"- High-risk recall: {float(phase1.get('high_risk_recall', 0.0)):.4f}")
    lines.append(f"- High-risk precision: {float(phase1.get('high_risk_precision', 0.0)):.4f}")
    lines.append(f"- False-low-high-risk rate: {float(phase1.get('false_low_high_risk_rate', 0.0)):.4f}")
    lines.append("")
    phase1b = critical_report["phase1b_reference"]
    lines.append("## Previous Phase 1B Reference")
    lines.append(f"- Candidate: {phase1b.get('candidate')}")
    lines.append(f"- Macro-F1: {float(phase1b.get('macro_f1', 0.0)):.4f}")
    lines.append(f"- High-risk recall: {float(phase1b.get('high_risk_recall', 0.0)):.4f}")
    lines.append(f"- High-risk precision: {float(phase1b.get('high_risk_precision', 0.0)):.4f}")
    lines.append(f"- False-low-high-risk rate: {float(phase1b.get('false_low_high_risk_rate', 0.0)):.4f}")
    lines.append(f"- False alarms: {int(phase1b.get('false_alarms', 0))}")
    lines.append("")
    lines.append("## Best Candidates (Time Split)")
    best_pred = critical_report["best_prediction_mode_candidate"]
    best_assess = critical_report["best_assessment_mode_candidate"]
    lines.append(f"- Best prediction-mode candidate: {best_pred.get('candidate')}")
    lines.append(f"- Prediction-mode macro-F1: {float(best_pred.get('macro_f1', 0.0)):.4f}")
    lines.append(f"- Prediction-mode high-risk recall: {float(best_pred.get('high_risk_recall', 0.0)):.4f}")
    lines.append(f"- Prediction-mode high-risk precision: {float(best_pred.get('high_risk_precision', 0.0)):.4f}")
    lines.append(f"- Prediction-mode false-low-high-risk rate: {float(best_pred.get('false_low_high_risk_rate', 0.0)):.4f}")
    lines.append(f"- Prediction-mode gate pass: {best_pred.get('gate_pass')}")
    lines.append(f"- Best assessment-mode candidate: {best_assess.get('candidate')}")
    lines.append(f"- Assessment-mode macro-F1: {float(best_assess.get('macro_f1', 0.0)):.4f}")
    lines.append(f"- Assessment-mode high-risk recall: {float(best_assess.get('high_risk_recall', 0.0)):.4f}")
    lines.append(f"- Assessment-mode high-risk precision: {float(best_assess.get('high_risk_precision', 0.0)):.4f}")
    lines.append(f"- Assessment-mode false-low-high-risk rate: {float(best_assess.get('false_low_high_risk_rate', 0.0)):.4f}")
    lines.append(f"- Assessment-mode gate pass: {best_assess.get('gate_pass')}")
    lines.append("")
    diag = critical_report["critical_risk_diagnostics"]
    lines.append("## Failure Diagnostics")
    lines.append(f"- Train class distribution: {diag['train_class_distribution']}")
    lines.append(f"- Test class distribution: {diag['test_class_distribution']}")
    lines.append(f"- High-risk support count: {diag['high_risk_support_count']}")
    lines.append(f"- Confusion matrix (current model): {diag['confusion_matrix_current_model']}")
    lines.append(f"- High-risk prediction breakdown: {diag['high_risk_predictions_breakdown']}")
    lines.append(f"- High-risk cluster by stage: {diag['high_risk_cluster']['by_stage']}")
    lines.append(f"- High-risk cluster by product: {diag['high_risk_cluster']['by_product']}")
    lines.append(f"- High-risk cluster by season: {diag['high_risk_cluster']['by_season']}")
    lines.append("")
    lines.append("## Rule Definition")
    lines.append(f"- {critical_report['rule_definition']}")
    lines.append("")
    lines.append("## Phase 1C Pareto Frontier (Prediction-Mode)")
    lines.append("| candidate | macro_f1 | high_recall | high_precision | false_alarms |")
    lines.append("|---|---:|---:|---:|---:|")
    for row in critical_report["phase1c_pareto_frontier_prediction_mode"]:
        lines.append(
            f"| {row['candidate']} | {row['macro_f1']:.4f} | {row['high_risk_recall']:.4f} | {row['high_risk_precision']:.4f} | {row['false_alarms_count']} |"
        )
    lines.append("")
    lines.append("## Phase 1C Selection Summary")
    lines.append(
        f"- Best recall candidate: "
        f"{critical_report['phase1c_best_recall_prediction_mode']['candidate'] if critical_report['phase1c_best_recall_prediction_mode'] else 'None'}"
    )
    lines.append(
        f"- Best macro-F1 candidate: "
        f"{critical_report['phase1c_best_macro_f1_prediction_mode']['candidate'] if critical_report['phase1c_best_macro_f1_prediction_mode'] else 'None'}"
    )
    lines.append(
        f"- Best balanced candidate: "
        f"{critical_report['phase1c_best_balanced_prediction_mode']['candidate'] if critical_report['phase1c_best_balanced_prediction_mode'] else 'None'}"
    )
    lines.append(
        f"- Lowest false-alarm candidate with recall>0: "
        f"{critical_report['phase1c_lowest_false_alarm_with_recall_prediction_mode']['candidate'] if critical_report['phase1c_lowest_false_alarm_with_recall_prediction_mode'] else 'None'}"
    )
    lines.append(
        f"- Final classification decision: {critical_report['phase1c_final_decision']['decision']} "
        f"({critical_report['phase1c_final_decision']['reason']})"
    )
    lines.append("")
    lines.append("## Prediction-Mode Candidates")
    lines.append("| candidate | macro_f1 | high_recall | high_precision | false_low_high_rate | false_alarms | gate_pass |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for row in critical_report["prediction_mode_candidates"]:
        lines.append(
            f"| {row['candidate']} | {row['macro_f1']:.4f} | {row['high_risk_recall']:.4f} | {row['high_risk_precision']:.4f} | "
            f"{row['false_low_high_risk_rate']:.4f} | {row['false_alarms_count']} | {row['gate_pass']} |"
        )
    lines.append("")
    lines.append("## Assessment-Mode Candidates")
    lines.append("| candidate | macro_f1 | high_recall | high_precision | false_low_high_rate | false_alarms | gate_pass |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for row in critical_report["assessment_mode_candidates"]:
        lines.append(
            f"| {row['candidate']} | {row['macro_f1']:.4f} | {row['high_risk_recall']:.4f} | {row['high_risk_precision']:.4f} | "
            f"{row['false_low_high_risk_rate']:.4f} | {row['false_alarms_count']} | {row['gate_pass']} |"
        )
    lines.append("")
    lines.append("## Threshold Tuning Tradeoff")
    lines.append("| source_model | high_threshold | macro_f1 | high_recall | high_precision | false_low_high_rate |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for row in critical_report["threshold_tuning_tradeoff"]:
        lines.append(
            f"| {row['source_model']} | {row['threshold']:.2f} | {row['macro_f1']:.4f} | {row['high_risk_recall']:.4f} | "
            f"{row['high_risk_precision']:.4f} | {row['false_low_high_risk_rate']:.4f} |"
        )
    lines.append("")
    lines.append("## Boundary")
    lines.append("- Synthetic offline benchmark only.")
    lines.append("- Not production accuracy.")
    lines.append("- No runtime promotion or model replacement.")
    return "\n".join(lines) + "\n"


def _build_synthetic_anomaly_report(report: Dict[str, Any]) -> Dict[str, Any]:
    anomaly = report["evaluation"]["time_based"]["anomaly_diagnostics"]
    return {
        "warning": SYNTHETIC_OFFLINE_WARNING,
        "source_label": SOURCE_LABEL,
        "source": "synthetic_offline_anomaly",
        "dataset": report["dataset"],
        "split_info": report["split_info"],
        "classification_status_frozen": anomaly["classification_status_frozen"],
        "explanation": anomaly["explanation"],
        "isolation_forest_baseline": anomaly["isolation_forest_baseline"],
        "prediction_mode_candidates": anomaly["prediction_mode_candidates"],
        "assessment_mode_candidates": anomaly["assessment_mode_candidates"],
        "best_prediction_mode_candidate": anomaly["best_prediction_mode_candidate"],
        "best_assessment_mode_candidate": anomaly["best_assessment_mode_candidate"],
        "final_anomaly_decision": anomaly["final_anomaly_decision"],
        "rule_definitions": anomaly["rule_definitions"],
        "gate_definition": anomaly["gate_definition"],
        "promotion_note": anomaly["promotion_note"],
        "boundary": {
            "offline_only": True,
            "non_production_claims_only": True,
            "runtime_model_unchanged": True,
        },
    }


def _render_synthetic_anomaly_markdown(anomaly_report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# {SYNTHETIC_OFFLINE_WARNING}")
    lines.append("")
    lines.append("## Classification Freeze")
    frozen = anomaly_report["classification_status_frozen"]
    lines.append(f"- Decision: {frozen['decision']} ({frozen['state']})")
    lines.append(f"- Frozen best prediction-mode candidate: {frozen['best_prediction_mode_candidate']}")
    lines.append("")
    lines.append("## IsolationForest Baseline")
    iso = anomaly_report["isolation_forest_baseline"]
    lines.append(
        f"- precision={iso['precision']:.4f}, recall={iso['recall']:.4f}, f1={iso['f1']:.4f}, "
        f"precision@10%={iso['precision_at_10pct']:.4f}, tp={iso['tp']}, fp={iso['fp']}, fn={iso['fn']}"
    )
    lines.append("")
    lines.append("## Prediction-Mode Anomaly Candidates")
    lines.append("| candidate | type | precision | recall | f1 | precision@10% | fp | fn | tp | gate_pass |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in anomaly_report["prediction_mode_candidates"]:
        lines.append(
            f"| {row['candidate']} | {row['candidate_type']} | {row['precision']:.4f} | {row['recall']:.4f} | "
            f"{row['f1']:.4f} | {row['precision_at_10pct']:.4f} | {row['fp']} | {row['fn']} | {row['tp']} | {row['prediction_mode_gate_pass']} |"
        )
    lines.append("")
    lines.append("## Assessment-Mode Anomaly Candidates")
    lines.append("| candidate | type | precision | recall | f1 | precision@10% | fp | fn | tp | gate_pass |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in anomaly_report["assessment_mode_candidates"]:
        lines.append(
            f"| {row['candidate']} | {row['candidate_type']} | {row['precision']:.4f} | {row['recall']:.4f} | "
            f"{row['f1']:.4f} | {row['precision_at_10pct']:.4f} | {row['fp']} | {row['fn']} | {row['tp']} | {row['assessment_mode_gate_pass']} |"
        )
    lines.append("")
    lines.append("## Best Candidates and Decision")
    lines.append(f"- Best prediction-mode anomaly/risk candidate: {anomaly_report['best_prediction_mode_candidate']['candidate'] if anomaly_report['best_prediction_mode_candidate'] else 'None'}")
    lines.append(f"- Best assessment-mode anomaly candidate: {anomaly_report['best_assessment_mode_candidate']['candidate'] if anomaly_report['best_assessment_mode_candidate'] else 'None'}")
    lines.append(
        f"- Final anomaly decision: {anomaly_report['final_anomaly_decision']['decision']} "
        f"({anomaly_report['final_anomaly_decision']['reason']})"
    )
    lines.append("")
    lines.append("## Logic and Boundaries")
    lines.append(f"- Explanation: {anomaly_report['explanation']}")
    lines.append(f"- Rule definitions: {anomaly_report['rule_definitions']}")
    lines.append(f"- Gate definition: {anomaly_report['gate_definition']}")
    lines.append(f"- Promotion note: {anomaly_report['promotion_note']}")
    lines.append("- Synthetic offline benchmark only.")
    lines.append("- Not production accuracy.")
    lines.append("- No runtime promotion or model replacement.")
    return "\n".join(lines) + "\n"


def _build_synthetic_recommendation_ranking_report(report: Dict[str, Any]) -> Dict[str, Any]:
    rec = report["evaluation"]["time_based"]["recommendation_ranking"]
    return {
        "warning": SYNTHETIC_OFFLINE_WARNING,
        "source_label": SOURCE_LABEL,
        "source": "synthetic_offline_recommendation_ranking",
        "dataset": report["dataset"],
        "split_info": report["split_info"],
        "proxy_relevance_warning": rec["warning"],
        "status_summary_frozen": rec["status_summary_frozen"],
        "action_templates": rec["action_templates"],
        "ranking_score_definition": rec["ranking_score_definition"],
        "proxy_relevance_definition": rec["proxy_relevance_definition"],
        "prediction_mode_candidates": rec["prediction_mode_candidates"],
        "assessment_mode_candidates": rec["assessment_mode_candidates"],
        "best_prediction_mode_candidate": rec["best_prediction_mode_candidate"],
        "best_assessment_mode_candidate": rec["best_assessment_mode_candidate"],
        "gate_definition": rec["gate_definition"],
        "final_recommendation_ranking_decision": rec["final_recommendation_ranking_decision"],
        "forbidden_claims": rec["forbidden_claims"],
        "boundary": {
            "offline_only": True,
            "non_production_claims_only": True,
            "runtime_model_unchanged": True,
        },
    }


def _render_synthetic_recommendation_ranking_markdown(rec_report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# {SYNTHETIC_OFFLINE_WARNING}")
    lines.append("")
    lines.append("## Frozen Model Status")
    lines.append(f"- {rec_report['status_summary_frozen']}")
    lines.append("")
    lines.append("## Action Templates")
    for key, value in rec_report["action_templates"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Ranking Score Definition")
    lines.append(f"- {rec_report['ranking_score_definition']}")
    lines.append("")
    lines.append("## Proxy Relevance Boundary")
    lines.append(f"- {rec_report['proxy_relevance_warning']}")
    lines.append(f"- {rec_report['proxy_relevance_definition']}")
    lines.append("")
    lines.append("## Prediction-Mode Ranking Candidates")
    lines.append("| strategy | Precision@3 | Precision@5 | NDCG@5 | mean top relevance | anomaly/high-loss top coverage | gate_pass |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for row in rec_report["prediction_mode_candidates"]:
        lines.append(
            f"| {row['strategy']} | {row['precision_at_3']:.4f} | {row['precision_at_5']:.4f} | {row['ndcg_at_5']:.4f} | "
            f"{row['mean_relevance_top_1']:.4f} | {row['top_priority_anomaly_high_loss_coverage']:.4f} | {row['gate_pass']} |"
        )
    lines.append("")
    lines.append("## Assessment-Mode Ranking Candidates")
    lines.append("| strategy | Precision@3 | Precision@5 | NDCG@5 | mean top relevance | anomaly/high-loss top coverage | gate_pass |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for row in rec_report["assessment_mode_candidates"]:
        lines.append(
            f"| {row['strategy']} | {row['precision_at_3']:.4f} | {row['precision_at_5']:.4f} | {row['ndcg_at_5']:.4f} | "
            f"{row['mean_relevance_top_1']:.4f} | {row['top_priority_anomaly_high_loss_coverage']:.4f} | {row['gate_pass']} |"
        )
    lines.append("")
    lines.append("## Best Candidates and Decision")
    lines.append(
        f"- Best prediction-mode ranking candidate: {rec_report['best_prediction_mode_candidate']['strategy'] if rec_report['best_prediction_mode_candidate'] else 'None'}"
    )
    lines.append(
        f"- Best assessment-mode ranking candidate: {rec_report['best_assessment_mode_candidate']['strategy'] if rec_report['best_assessment_mode_candidate'] else 'None'}"
    )
    lines.append(
        f"- Final recommendation-ranking decision: {rec_report['final_recommendation_ranking_decision']['decision']} "
        f"({rec_report['final_recommendation_ranking_decision']['reason']})"
    )
    lines.append("")
    lines.append("## Forbidden Claims")
    for item in rec_report["forbidden_claims"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Boundary")
    lines.append("- Synthetic offline benchmark only.")
    lines.append("- Not production accuracy.")
    lines.append("- No runtime promotion or model replacement.")
    return "\n".join(lines) + "\n"


def run_synthetic_model_improvement(
    *,
    dataset_csv: Path,
    output_json: Path,
    output_md: Path,
    critical_output_json: Optional[Path] = None,
    critical_output_md: Optional[Path] = None,
    anomaly_output_json: Optional[Path] = None,
    anomaly_output_md: Optional[Path] = None,
    recommendation_output_json: Optional[Path] = None,
    recommendation_output_md: Optional[Path] = None,
) -> Dict[str, Any]:
    frame = _prepare_frame(dataset_csv)

    time_train_idx, time_test_idx, time_info = _time_split_indices(frame, test_size=0.2)
    rand_train_idx, rand_test_idx, rand_info = _random_split_indices(frame, test_size=0.2)
    grouped = _grouped_lot_time_split_indices(frame, test_size=0.2)
    grouped_info = grouped[2] if grouped is not None else {"strategy": "not_available"}

    evaluation: Dict[str, Any] = {
        "time_based": _evaluate_split(frame, time_train_idx, time_test_idx, split_name="time_based"),
        "random_split": _evaluate_split(frame, rand_train_idx, rand_test_idx, split_name="random_split"),
    }
    if grouped is not None:
        evaluation["grouped_lot_time"] = _evaluate_split(
            frame, grouped[0], grouped[1], split_name="grouped_lot_time"
        )

    report = {
        "warning": SYNTHETIC_OFFLINE_WARNING,
        "source_label": SOURCE_LABEL,
        "source": "synthetic_offline",
        "dataset": {
            "row_count": int(len(frame)),
            "products": sorted(str(x) for x in frame["product"].dropna().unique().tolist()),
            "stages": sorted(str(x) for x in frame["stage"].dropna().unique().tolist()),
            "data_origin_expected": "SYNTHETIC_BENCHMARK",
        },
        "split_info": {
            "time_split": time_info,
            "random_split": rand_info,
            "grouped_lot_time_split": grouped_info,
        },
        "evaluation": evaluation,
        "claims_guardrail": {
            "allowed_claims": [
                "synthetic benchmark improved or did not improve specific model candidates",
                "classification has potential if high-risk recall improves",
                "regression remains baseline-fallback when it does not beat baseline",
                "synthetic benchmark is controlled and non-production",
            ],
            "forbidden_claims": [
                "production-ready ML",
                "real cooperative accuracy",
                "promoted runtime model",
                "validated anomaly detection in production",
                "fully learned recommendations",
            ],
        },
        "safety": {
            "no_db_connection_used": True,
            "no_production_artifact_writes": True,
            "offline_only": True,
        },
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2))
    output_md.write_text(_render_markdown(report))
    if critical_output_json is not None and critical_output_md is not None:
        critical_report = _build_critical_risk_report(report)
        critical_output_json.parent.mkdir(parents=True, exist_ok=True)
        critical_output_md.parent.mkdir(parents=True, exist_ok=True)
        critical_output_json.write_text(json.dumps(critical_report, indent=2))
        critical_output_md.write_text(_render_critical_risk_markdown(critical_report))
    if anomaly_output_json is not None and anomaly_output_md is not None:
        anomaly_report = _build_synthetic_anomaly_report(report)
        anomaly_output_json.parent.mkdir(parents=True, exist_ok=True)
        anomaly_output_md.parent.mkdir(parents=True, exist_ok=True)
        anomaly_output_json.write_text(json.dumps(anomaly_report, indent=2))
        anomaly_output_md.write_text(_render_synthetic_anomaly_markdown(anomaly_report))
    if recommendation_output_json is not None and recommendation_output_md is not None:
        rec_report = _build_synthetic_recommendation_ranking_report(report)
        recommendation_output_json.parent.mkdir(parents=True, exist_ok=True)
        recommendation_output_md.parent.mkdir(parents=True, exist_ok=True)
        recommendation_output_json.write_text(json.dumps(rec_report, indent=2))
        recommendation_output_md.write_text(_render_synthetic_recommendation_ranking_markdown(rec_report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline synthetic model-by-model ML improvement benchmark.")
    parser.add_argument(
        "--dataset-csv",
        default="backend/artifacts/synthetic_postharvest_benchmark.csv",
        help="Path to synthetic benchmark CSV dataset.",
    )
    parser.add_argument(
        "--output-json",
        default="backend/reports/ml_synthetic_model_improvement.json",
        help="Path to output JSON report.",
    )
    parser.add_argument(
        "--output-md",
        default="backend/reports/ml_synthetic_model_improvement.md",
        help="Path to output Markdown report.",
    )
    parser.add_argument(
        "--critical-output-json",
        default="backend/reports/ml_synthetic_critical_risk_detection.json",
        help="Path to output critical-risk JSON report.",
    )
    parser.add_argument(
        "--critical-output-md",
        default="backend/reports/ml_synthetic_critical_risk_detection.md",
        help="Path to output critical-risk Markdown report.",
    )
    parser.add_argument(
        "--anomaly-output-json",
        default="backend/reports/ml_synthetic_anomaly_detection.json",
        help="Path to output anomaly JSON report.",
    )
    parser.add_argument(
        "--anomaly-output-md",
        default="backend/reports/ml_synthetic_anomaly_detection.md",
        help="Path to output anomaly Markdown report.",
    )
    parser.add_argument(
        "--recommendation-output-json",
        default="backend/reports/ml_synthetic_recommendation_ranking.json",
        help="Path to output recommendation-ranking JSON report.",
    )
    parser.add_argument(
        "--recommendation-output-md",
        default="backend/reports/ml_synthetic_recommendation_ranking.md",
        help="Path to output recommendation-ranking Markdown report.",
    )
    args = parser.parse_args()

    report = run_synthetic_model_improvement(
        dataset_csv=Path(args.dataset_csv),
        output_json=Path(args.output_json),
        output_md=Path(args.output_md),
        critical_output_json=Path(args.critical_output_json),
        critical_output_md=Path(args.critical_output_md),
        anomaly_output_json=Path(args.anomaly_output_json),
        anomaly_output_md=Path(args.anomaly_output_md),
        recommendation_output_json=Path(args.recommendation_output_json),
        recommendation_output_md=Path(args.recommendation_output_md),
    )
    print(f"Saved synthetic model improvement JSON report: {args.output_json}")
    print(f"Saved synthetic model improvement Markdown report: {args.output_md}")
    print(f"Saved critical-risk JSON report: {args.critical_output_json}")
    print(f"Saved critical-risk Markdown report: {args.critical_output_md}")
    print(f"Saved anomaly JSON report: {args.anomaly_output_json}")
    print(f"Saved anomaly Markdown report: {args.anomaly_output_md}")
    print(f"Saved recommendation-ranking JSON report: {args.recommendation_output_json}")
    print(f"Saved recommendation-ranking Markdown report: {args.recommendation_output_md}")
    print(f"Rows evaluated: {report['dataset']['row_count']}")


if __name__ == "__main__":
    main()

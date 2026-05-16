from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from app.core.config import settings
from app.models.enums import RiskLevel
from app.ml.utils.stage_normalization import normalize_stage


CATEGORICAL_FEATURES = ["product", "process_type", "stage_canonical", "season", "product_stage_key"]
FEATURE_SCHEMA_VERSION = "phase4-v1"
FORBIDDEN_PREDICTIVE_FEATURES = {
    "loss_pct",
    "efficiency_pct",
    "qty_out",
    "deviation_from_stage_avg",
}

PREDICTIVE_REGRESSION_FEATURES = [
    "product",
    "process_type",
    "stage_canonical",
    "product_stage_key",
    "season",
    "qty_in",
    "qty_in_log",
    "batch_size",
    "batch_size_log",
    "stock_level",
    "stock_pressure_ratio",
    "month",
    "week_of_year",
    "stage_order",
    "is_drying_stage",
    "is_sorting_stage",
    "is_packaging_stage",
    "historical_avg_loss_same_product",
    "historical_avg_loss_same_stage",
    "historical_avg_efficiency_same_stage",
    "product_stage_historical_avg_loss",
    "product_stage_historical_median_loss",
    "product_stage_rolling_loss_last_5",
    "product_stage_rolling_loss_last_10",
    "stage_season_avg_loss",
    "product_stage_season_avg_loss",
    "loss_volatility_product_stage",
    "previous_batch_loss",
    "days_since_previous_batch",
    "rolling_loss_last_n_batches",
    "rolling_efficiency_last_n_batches",
    "weather_available",
    "weather_avg_humidity_window",
    "weather_max_humidity_window",
    "weather_avg_temperature_window",
    "weather_avg_dew_point_window",
    "weather_avg_wind_speed_window",
    "weather_avg_surface_pressure_window",
    "weather_rain_flag_window",
    "weather_precip_total_window",
    "weather_is_forecast",
    "weather_is_observed",
    "weather_product_humidity_interaction",
    "weather_stage_humidity_interaction",
    "weather_season_humidity_interaction",
    "weather_feature_timestamp_ordinal",
    "date_ordinal",
]

PREDICTIVE_CLASSIFICATION_FEATURES = list(PREDICTIVE_REGRESSION_FEATURES)

ASSESSMENT_ANOMALY_FEATURES = [
    *PREDICTIVE_REGRESSION_FEATURES[:-1],
    "deviation_from_stage_avg",
    "qty_out",
    "loss_pct",
    "efficiency_pct",
    "date_ordinal",
]
PREDICTIVE_FEATURES = list(PREDICTIVE_REGRESSION_FEATURES)
ASSESSMENT_FEATURES = list(ASSESSMENT_ANOMALY_FEATURES)


def forbidden_predictive_violations(feature_names: List[str]) -> List[str]:
    return sorted(set(feature_names) & FORBIDDEN_PREDICTIVE_FEATURES)


def assign_risk_level(loss_pct: float) -> str:
    if loss_pct >= settings.anomaly_loss_threshold:
        return RiskLevel.HIGH.value
    if loss_pct >= settings.step_loss_threshold:
        return RiskLevel.MEDIUM.value
    return RiskLevel.LOW.value


def get_risk_thresholds() -> Dict[str, float]:
    low = float(settings.ml_risk_low_threshold)
    high = float(settings.ml_risk_high_threshold)
    if high <= low:
        high = low + 1e-6
    return {
        "low_to_medium": low,
        "medium_to_high": high,
    }


def assign_thresholded_risk_level(predicted_loss_pct: float) -> str:
    thresholds = get_risk_thresholds()
    value = float(predicted_loss_pct)
    if value < thresholds["low_to_medium"]:
        return RiskLevel.LOW.value
    if value < thresholds["medium_to_high"]:
        return RiskLevel.MEDIUM.value
    return RiskLevel.HIGH.value


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        out = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(out) or np.isinf(out):
        return default
    return out


def _derive_predictive_enrichment(working: pd.DataFrame) -> pd.DataFrame:
    if "stage_canonical" not in working.columns:
        working["stage_canonical"] = working["process_type"].apply(normalize_stage)
    else:
        working["stage_canonical"] = working["stage_canonical"].apply(normalize_stage)

    if "product_stage_key" not in working.columns:
        working["product_stage_key"] = (
            working["product"].astype(str).str.lower().str.strip()
            + "|"
            + working["stage_canonical"].astype(str).str.lower().str.strip()
        )

    if "stock_pressure_ratio" not in working.columns:
        batch_size = pd.to_numeric(working.get("batch_size", 0.0), errors="coerce").fillna(0.0)
        stock_level = pd.to_numeric(working.get("stock_level", 0.0), errors="coerce").fillna(0.0)
        denom = batch_size.replace(0.0, np.nan)
        working["stock_pressure_ratio"] = (stock_level / denom).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    if "qty_in_log" not in working.columns:
        qty_in = pd.to_numeric(working.get("qty_in", 0.0), errors="coerce").fillna(0.0).clip(lower=0.0)
        working["qty_in_log"] = np.log1p(qty_in)
    if "batch_size_log" not in working.columns:
        batch_size = pd.to_numeric(working.get("batch_size", 0.0), errors="coerce").fillna(0.0).clip(lower=0.0)
        working["batch_size_log"] = np.log1p(batch_size)

    stage_order_map = {"cleaning": 1, "drying": 2, "sorting": 3, "packaging": 4}
    if "stage_order" not in working.columns:
        working["stage_order"] = working["stage_canonical"].map(stage_order_map).fillna(0).astype(int)
    if "is_drying_stage" not in working.columns:
        working["is_drying_stage"] = (working["stage_canonical"] == "drying").astype(int)
    if "is_sorting_stage" not in working.columns:
        working["is_sorting_stage"] = (working["stage_canonical"] == "sorting").astype(int)
    if "is_packaging_stage" not in working.columns:
        working["is_packaging_stage"] = (working["stage_canonical"] == "packaging").astype(int)

    default_loss = float(settings.step_loss_threshold)
    if "product_stage_historical_avg_loss" not in working.columns:
        working["product_stage_historical_avg_loss"] = pd.to_numeric(
            working.get("historical_avg_loss_same_stage", default_loss),
            errors="coerce",
        ).fillna(default_loss)
    if "product_stage_historical_median_loss" not in working.columns:
        working["product_stage_historical_median_loss"] = pd.to_numeric(
            working.get("historical_avg_loss_same_stage", default_loss),
            errors="coerce",
        ).fillna(default_loss)
    if "product_stage_rolling_loss_last_5" not in working.columns:
        working["product_stage_rolling_loss_last_5"] = pd.to_numeric(
            working.get("rolling_loss_last_n_batches", default_loss),
            errors="coerce",
        ).fillna(default_loss)
    if "product_stage_rolling_loss_last_10" not in working.columns:
        working["product_stage_rolling_loss_last_10"] = pd.to_numeric(
            working.get("rolling_loss_last_n_batches", default_loss),
            errors="coerce",
        ).fillna(default_loss)
    if "stage_season_avg_loss" not in working.columns:
        working["stage_season_avg_loss"] = pd.to_numeric(
            working.get("historical_avg_loss_same_stage", default_loss),
            errors="coerce",
        ).fillna(default_loss)
    if "product_stage_season_avg_loss" not in working.columns:
        working["product_stage_season_avg_loss"] = pd.to_numeric(
            working.get("historical_avg_loss_same_stage", default_loss),
            errors="coerce",
        ).fillna(default_loss)
    if "loss_volatility_product_stage" not in working.columns:
        working["loss_volatility_product_stage"] = 0.0
    if "days_since_previous_batch" not in working.columns:
        working["days_since_previous_batch"] = 0.0
    if "weather_available" not in working.columns:
        working["weather_available"] = 0.0
    if "weather_rain_flag_window" not in working.columns:
        working["weather_rain_flag_window"] = 0.0
    if "weather_is_forecast" not in working.columns:
        working["weather_is_forecast"] = 0.0
    if "weather_is_observed" not in working.columns:
        working["weather_is_observed"] = 0.0

    # Ensure all required predictive columns exist with safe defaults.
    for feature in PREDICTIVE_REGRESSION_FEATURES:
        if feature not in working.columns:
            if feature in CATEGORICAL_FEATURES:
                working[feature] = "unknown"
            else:
                working[feature] = 0.0

    for feature in PREDICTIVE_REGRESSION_FEATURES:
        if feature in CATEGORICAL_FEATURES:
            working[feature] = working[feature].fillna("unknown").astype(str)
        else:
            working[feature] = pd.to_numeric(working[feature], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)

    return working


def prepare_feature_frame(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, List[str]]]:
    working = df.copy()
    working = _derive_predictive_enrichment(working)
    working["date_ordinal"] = pd.to_datetime(working["date"]).dt.date.apply(lambda item: item.toordinal())
    drop_cols = [col for col in ("date", "weather_feature_timestamp") if col in working.columns]
    working = working.drop(columns=drop_cols)

    feature_sets = {
        "predictive_regression_features": list(PREDICTIVE_REGRESSION_FEATURES),
        "predictive_classification_features": list(PREDICTIVE_CLASSIFICATION_FEATURES),
        "assessment_anomaly_features": list(ASSESSMENT_ANOMALY_FEATURES),
    }

    return working, feature_sets
    if "weather_feature_timestamp_ordinal" not in working.columns:
        if "weather_feature_timestamp" in working.columns:
            weather_ts = pd.to_datetime(working["weather_feature_timestamp"], errors="coerce", utc=True)
            weather_ordinal = weather_ts.dt.date.apply(lambda item: item.toordinal() if pd.notna(item) else np.nan)
            working["weather_feature_timestamp_ordinal"] = pd.to_numeric(weather_ordinal, errors="coerce")
        else:
            working["weather_feature_timestamp_ordinal"] = np.nan

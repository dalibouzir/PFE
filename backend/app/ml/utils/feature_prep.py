from __future__ import annotations

from typing import Dict, List, Tuple

import pandas as pd

from app.core.config import settings
from app.models.enums import RiskLevel


CATEGORICAL_FEATURES = ["product", "process_type", "season"]

PREDICTIVE_REGRESSION_FEATURES = [
    "product",
    "process_type",
    "season",
    "qty_in",
    "batch_size",
    "stock_level",
    "month",
    "week_of_year",
    "historical_avg_loss_same_product",
    "historical_avg_loss_same_stage",
    "historical_avg_efficiency_same_stage",
    "deviation_from_stage_avg",
    "previous_batch_loss",
    "rolling_loss_last_n_batches",
    "rolling_efficiency_last_n_batches",
    "date_ordinal",
]

PREDICTIVE_CLASSIFICATION_FEATURES = list(PREDICTIVE_REGRESSION_FEATURES)

ASSESSMENT_ANOMALY_FEATURES = [
    *PREDICTIVE_REGRESSION_FEATURES[:-1],
    "qty_out",
    "loss_pct",
    "efficiency_pct",
    "date_ordinal",
]


def assign_risk_level(loss_pct: float) -> str:
    if loss_pct >= settings.anomaly_loss_threshold:
        return RiskLevel.HIGH.value
    if loss_pct >= settings.step_loss_threshold:
        return RiskLevel.MEDIUM.value
    return RiskLevel.LOW.value


def prepare_feature_frame(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, List[str]]]:
    working = df.copy()
    working["date_ordinal"] = pd.to_datetime(working["date"]).dt.date.apply(lambda item: item.toordinal())
    working = working.drop(columns=["date"])

    feature_sets = {
        "predictive_regression_features": list(PREDICTIVE_REGRESSION_FEATURES),
        "predictive_classification_features": list(PREDICTIVE_CLASSIFICATION_FEATURES),
        "assessment_anomaly_features": list(ASSESSMENT_ANOMALY_FEATURES),
    }

    return working, feature_sets

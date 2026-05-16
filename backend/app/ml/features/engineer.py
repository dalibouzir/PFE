from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.weather_features import build_weather_feature_frame
from app.ml.utils.stage_normalization import normalize_stage
from app.models.batch import Batch
from app.models.process_step import ProcessStep
from app.models.product import Product
from app.models.stock import Stock


SEASON_MAP = {
    "dry": {11, 12, 1, 2},
    "hot": {3, 4, 5},
    "rainy": {6, 7, 8, 9, 10},
}


@dataclass
class FeatureSet:
    features: pd.DataFrame
    raw: List[Dict]
    diagnostics: Dict[str, Any] | None = None


def _season_for_month(month: int) -> str:
    for season, months in SEASON_MAP.items():
        if month in months:
            return season
    return "dry"


def _to_date(value: date) -> pd.Timestamp:
    return pd.to_datetime(value)


def fetch_process_records(db: Session) -> List[Dict]:
    stocks = db.scalars(select(Stock)).all()
    stock_lookup = {(stock.cooperative_id, stock.product_id): stock.quantity for stock in stocks}

    rows = db.execute(
        select(
            ProcessStep,
            Batch,
            Product,
        ).join(Batch, Batch.id == ProcessStep.batch_id)
        .join(Product, Product.id == Batch.product_id)
    ).all()

    records: List[Dict] = []
    for step, batch, product in rows:
        records.append(
            {
                "batch_id": batch.id,
                "cooperative_id": batch.cooperative_id,
                "product": product.name,
                "process_type": step.type,
                "qty_in": step.qty_in,
                "qty_out": step.qty_out,
                "batch_size": batch.initial_qty,
                "batch_current_qty": batch.current_qty,
                "date": step.date,
                "stock_level": stock_lookup.get((batch.cooperative_id, batch.product_id), 0.0),
            }
        )
    return records


def build_features(db: Session, batch_id: Optional[str] = None, *, include_weather: bool = False) -> FeatureSet:
    records = fetch_process_records(db)
    if not records:
        return FeatureSet(features=pd.DataFrame(), raw=[])

    df = pd.DataFrame(records)
    df["date"] = df["date"].apply(_to_date)
    df = df.sort_values(["date", "batch_id"], ascending=True)

    qty_in = pd.to_numeric(df["qty_in"], errors="coerce").fillna(0.0)
    qty_out = pd.to_numeric(df["qty_out"], errors="coerce").fillna(0.0)
    valid_input = qty_in > 0

    df["loss_pct"] = np.where(valid_input, ((qty_in - qty_out) / qty_in) * 100.0, 0.0)
    df["loss_pct"] = pd.Series(df["loss_pct"]).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0.0)
    df["efficiency_pct"] = np.where(valid_input, qty_out / qty_in, 0.0)
    df["efficiency_pct"] = pd.Series(df["efficiency_pct"]).replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0.0)
    df["month"] = df["date"].dt.month
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
    df["season"] = df["month"].apply(_season_for_month)
    df["stage_canonical"] = df["process_type"].apply(normalize_stage)
    df["stage_order"] = df["stage_canonical"].map(
        {"cleaning": 1, "drying": 2, "sorting": 3, "packaging": 4}
    ).fillna(0).astype(int)
    df["is_drying_stage"] = (df["stage_canonical"] == "drying").astype(int)
    df["is_sorting_stage"] = (df["stage_canonical"] == "sorting").astype(int)
    df["is_packaging_stage"] = (df["stage_canonical"] == "packaging").astype(int)
    df["stock_pressure_ratio"] = np.where(
        pd.to_numeric(df["batch_size"], errors="coerce").fillna(0.0) > 0,
        pd.to_numeric(df["stock_level"], errors="coerce").fillna(0.0)
        / pd.to_numeric(df["batch_size"], errors="coerce").fillna(1.0),
        0.0,
    )
    df["stock_pressure_ratio"] = (
        pd.to_numeric(df["stock_pressure_ratio"], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )
    df["qty_in_log"] = np.log1p(pd.to_numeric(df["qty_in"], errors="coerce").fillna(0.0).clip(lower=0.0))
    df["batch_size_log"] = np.log1p(pd.to_numeric(df["batch_size"], errors="coerce").fillna(0.0).clip(lower=0.0))
    df["product_stage_key"] = (
        df["product"].astype(str).str.lower().str.strip()
        + "|"
        + df["stage_canonical"].astype(str).str.lower().str.strip()
    )

    df["historical_avg_loss_same_product"] = (
        df.groupby("product")["loss_pct"].expanding().mean().shift(1).reset_index(level=0, drop=True)
    )
    df["historical_avg_loss_same_stage"] = (
        df.groupby("process_type")["loss_pct"].expanding().mean().shift(1).reset_index(level=0, drop=True)
    )
    df["historical_avg_efficiency_same_stage"] = (
        df.groupby("process_type")["efficiency_pct"].expanding().mean().shift(1).reset_index(level=0, drop=True)
    )
    df["product_stage_historical_avg_loss"] = (
        df.groupby("product_stage_key")["loss_pct"].expanding().mean().shift(1).reset_index(level=0, drop=True)
    )
    df["product_stage_historical_median_loss"] = (
        df.groupby("product_stage_key")["loss_pct"].expanding().median().shift(1).reset_index(level=0, drop=True)
    )
    df["product_stage_rolling_loss_last_5"] = (
        df.groupby("product_stage_key")["loss_pct"]
        .rolling(5, min_periods=1)
        .mean()
        .shift(1)
        .reset_index(level=0, drop=True)
    )
    df["product_stage_rolling_loss_last_10"] = (
        df.groupby("product_stage_key")["loss_pct"]
        .rolling(10, min_periods=1)
        .mean()
        .shift(1)
        .reset_index(level=0, drop=True)
    )
    df["stage_season_avg_loss"] = (
        df.groupby(["stage_canonical", "season"])["loss_pct"]
        .expanding()
        .mean()
        .shift(1)
        .reset_index(level=[0, 1], drop=True)
    )
    df["product_stage_season_avg_loss"] = (
        df.groupby(["product_stage_key", "season"])["loss_pct"]
        .expanding()
        .mean()
        .shift(1)
        .reset_index(level=[0, 1], drop=True)
    )
    df["loss_volatility_product_stage"] = (
        df.groupby("product_stage_key")["loss_pct"]
        .rolling(5, min_periods=3)
        .std()
        .shift(1)
        .reset_index(level=0, drop=True)
    )

    df["deviation_from_stage_avg"] = df["loss_pct"] - df["historical_avg_loss_same_stage"]

    batch_summary = (
        df.groupby(["batch_id", "product"])
        .agg(
            batch_loss=("loss_pct", "mean"),
            batch_efficiency=("efficiency_pct", "mean"),
            batch_date=("date", "max"),
        )
        .reset_index()
        .sort_values(["product", "batch_date"], ascending=True)
    )
    batch_summary["previous_batch_loss"] = (
        batch_summary.groupby("product")["batch_loss"].shift(1)
    )
    batch_summary["days_since_previous_batch"] = (
        batch_summary.groupby("product")["batch_date"].diff().dt.days
    )
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

    df = df.merge(
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
    default_efficiency = max(0.0, 1.0 - default_loss_pct / 100.0)
    fill_defaults = {
        "historical_avg_loss_same_product": default_loss_pct,
        "historical_avg_loss_same_stage": default_loss_pct,
        "historical_avg_efficiency_same_stage": default_efficiency,
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
        "rolling_efficiency_last_n_batches": default_efficiency,
    }

    df = df.fillna(fill_defaults)

    if include_weather:
        weather = build_weather_feature_frame(df, event_time_col="date", cooperative_time_col="cooperative_id")
        weather_frame = weather.frame
        if len(weather_frame) == len(df):
            df = pd.concat([df.reset_index(drop=True), weather_frame.reset_index(drop=True)], axis=1)
        else:
            # Defensive fallback: preserve core pipeline even if weather alignment fails.
            df["weather_available"] = 0
        humidity_base = pd.to_numeric(df.get("weather_avg_humidity_window"), errors="coerce").fillna(0.0)
        product_factor = df["product"].astype(str).str.lower().map({"mangue": 1.15, "mango": 1.15, "bissap": 1.1, "mil": 0.95, "millet": 0.95, "arachide": 1.0, "peanut": 1.0}).fillna(1.0)
        stage_factor = df["stage_canonical"].map({"drying": 1.2, "sorting": 1.05, "cleaning": 0.9, "packaging": 0.95}).fillna(1.0)
        season_factor = df["season"].map({"rainy": 1.2, "hot": 0.95, "dry": 0.9}).fillna(1.0)
        df["weather_product_humidity_interaction"] = humidity_base * product_factor
        df["weather_stage_humidity_interaction"] = humidity_base * stage_factor
        df["weather_season_humidity_interaction"] = humidity_base * season_factor

    if batch_id:
        df = df[df["batch_id"].astype(str) == str(batch_id)]

    feature_columns = [
        "batch_id",
        "cooperative_id",
        "product",
        "process_type",
        "stage_canonical",
        "product_stage_key",
        "qty_in",
        "qty_in_log",
        "qty_out",
        "batch_size",
        "batch_size_log",
        "stock_level",
        "stock_pressure_ratio",
        "date",
        "month",
        "week_of_year",
        "season",
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
        "deviation_from_stage_avg",
        "previous_batch_loss",
        "days_since_previous_batch",
        "rolling_loss_last_n_batches",
        "rolling_efficiency_last_n_batches",
        "weather_available",
        "weather_feature_timestamp",
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
        "loss_pct",
        "efficiency_pct",
    ]

    for col in feature_columns:
        if col not in df.columns:
            df[col] = 0.0
    feature_df = df[feature_columns].copy()
    raw = feature_df.to_dict(orient="records")

    diagnostics: Dict[str, Any] = {"weather": {"enabled": bool(include_weather), "row_count": int(len(feature_df))}}
    if include_weather:
        weather_available = pd.to_numeric(feature_df["weather_available"], errors="coerce").fillna(0).astype(int)
        diagnostics["weather"].update(
            {
                "rows_with_weather": int(weather_available.sum()),
                "rows_without_weather": int(len(weather_available) - int(weather_available.sum())),
                "coverage_rate": float(weather_available.mean()) if len(weather_available) else 0.0,
                "leakage_violations": int(weather.leakage_violations),
            }
        )
    return FeatureSet(features=feature_df, raw=raw, diagnostics=diagnostics)

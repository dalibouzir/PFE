from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
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


def _season_for_month(month: int) -> str:
    for season, months in SEASON_MAP.items():
        if month in months:
            return season
    return "dry"


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


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


def build_features(db: Session, batch_id: Optional[str] = None) -> FeatureSet:
    records = fetch_process_records(db)
    if not records:
        return FeatureSet(features=pd.DataFrame(), raw=[])

    df = pd.DataFrame(records)
    df["date"] = df["date"].apply(_to_date)
    df = df.sort_values(["date", "batch_id"], ascending=True)

    df["loss_pct"] = ((df["qty_in"] - df["qty_out"]) / df["qty_in"]) * 100.0
    df["efficiency_pct"] = df.apply(lambda row: _safe_ratio(row["qty_out"], row["qty_in"]), axis=1)
    df["month"] = df["date"].dt.month
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
    df["season"] = df["month"].apply(_season_for_month)

    df["historical_avg_loss_same_product"] = (
        df.groupby("product")["loss_pct"].expanding().mean().shift(1).reset_index(level=0, drop=True)
    )
    df["historical_avg_loss_same_stage"] = (
        df.groupby("process_type")["loss_pct"].expanding().mean().shift(1).reset_index(level=0, drop=True)
    )
    df["historical_avg_efficiency_same_stage"] = (
        df.groupby("process_type")["efficiency_pct"].expanding().mean().shift(1).reset_index(level=0, drop=True)
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
        batch_summary[["batch_id", "previous_batch_loss", "rolling_loss_last_n_batches", "rolling_efficiency_last_n_batches"]],
        on="batch_id",
        how="left",
    )

    fill_defaults = {
        "historical_avg_loss_same_product": df["loss_pct"].mean(),
        "historical_avg_loss_same_stage": df["loss_pct"].mean(),
        "historical_avg_efficiency_same_stage": df["efficiency_pct"].mean(),
        "deviation_from_stage_avg": 0.0,
        "previous_batch_loss": df["loss_pct"].mean(),
        "rolling_loss_last_n_batches": df["loss_pct"].mean(),
        "rolling_efficiency_last_n_batches": df["efficiency_pct"].mean(),
    }

    df = df.fillna(fill_defaults)

    if batch_id:
        df = df[df["batch_id"].astype(str) == str(batch_id)]

    feature_columns = [
        "product",
        "process_type",
        "qty_in",
        "qty_out",
        "batch_size",
        "stock_level",
        "date",
        "month",
        "week_of_year",
        "season",
        "historical_avg_loss_same_product",
        "historical_avg_loss_same_stage",
        "historical_avg_efficiency_same_stage",
        "deviation_from_stage_avg",
        "previous_batch_loss",
        "rolling_loss_last_n_batches",
        "rolling_efficiency_last_n_batches",
        "loss_pct",
        "efficiency_pct",
    ]

    feature_df = df[feature_columns].copy()
    raw = feature_df.to_dict(orient="records")

    return FeatureSet(features=feature_df, raw=raw)

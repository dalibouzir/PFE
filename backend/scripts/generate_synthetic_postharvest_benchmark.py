#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

STAGES = ["nettoyage", "sechage", "tri", "emballage"]
STAGE_ORDER = {"nettoyage": 1, "sechage": 2, "tri": 3, "emballage": 4}
PRODUCTS = ["mangue", "arachide", "mil"]
SEASONS = ["dry", "hot", "rainy"]
REGIONS = ["thies", "dakar", "kaolack", "saint_louis"]
GRADES = ["A", "B", "C"]
SYNTHETIC_WARNING = (
    "SYNTHETIC BENCHMARK — NOT REAL APP PERFORMANCE. "
    "These metrics evaluate pipeline behavior under controlled simulated data and must not be "
    "reported as production model accuracy."
)


@dataclass(frozen=True)
class GenerationAssumptions:
    anomaly_rate: float = 0.06
    missing_duration_rate: float = 0.08
    base_event_start: str = "2025-01-01T08:00:00+00:00"


def _seasonal_weather(rng: np.random.Generator, season: str) -> Dict[str, float]:
    if season == "rainy":
        humidity = float(np.clip(rng.normal(83, 8), 45, 99))
        temperature = float(np.clip(rng.normal(30, 3), 20, 42))
        rainfall = float(np.clip(rng.gamma(shape=2.5, scale=5.0), 0, 60))
        wind_speed = float(np.clip(rng.normal(14, 4), 2, 35))
        dew_point = float(np.clip(rng.normal(24, 3), 10, 32))
    elif season == "hot":
        humidity = float(np.clip(rng.normal(52, 10), 20, 90))
        temperature = float(np.clip(rng.normal(36, 4), 24, 45))
        rainfall = float(np.clip(rng.gamma(shape=1.2, scale=1.5), 0, 18))
        wind_speed = float(np.clip(rng.normal(11, 4), 1, 32))
        dew_point = float(np.clip(rng.normal(18, 4), 6, 28))
    else:
        humidity = float(np.clip(rng.normal(40, 9), 15, 80))
        temperature = float(np.clip(rng.normal(29, 4), 18, 40))
        rainfall = float(np.clip(rng.gamma(shape=1.0, scale=0.8), 0, 12))
        wind_speed = float(np.clip(rng.normal(10, 3), 1, 25))
        dew_point = float(np.clip(rng.normal(14, 4), 2, 24))
    return {
        "humidity": humidity,
        "temperature": temperature,
        "rainfall": rainfall,
        "wind_speed": wind_speed,
        "dew_point": dew_point,
    }


def _grade_quality_penalty(grade: str) -> float:
    if grade == "A":
        return -0.8
    if grade == "B":
        return 0.0
    return 1.2


def _product_loss_adjustment(product: str, stage: str) -> float:
    if stage == "sechage":
        if product == "mangue":
            return 2.0
        if product == "arachide":
            return 0.6
        return 0.2
    if stage == "tri":
        if product == "mangue":
            return 0.7
        if product == "arachide":
            return 0.3
        return 0.5
    if stage == "nettoyage":
        return 0.4 if product == "mangue" else 0.2
    return 0.1


def _base_stage_loss(stage: str) -> float:
    if stage == "nettoyage":
        return 2.8
    if stage == "sechage":
        return 8.2
    if stage == "tri":
        return 4.6
    return 1.4


def _compute_loss_pct(
    *,
    stage: str,
    product: str,
    grade: str,
    humidity: float,
    rainfall: float,
    duration_minutes: float,
    delay_minutes: float,
    rng: np.random.Generator,
    anomalous: bool,
) -> float:
    base = _base_stage_loss(stage)
    product_adj = _product_loss_adjustment(product, stage)
    grade_adj = _grade_quality_penalty(grade) if stage == "tri" else 0.0

    if stage == "sechage":
        humidity_effect = max(0.0, (humidity - 60.0) * 0.12)
        rain_effect = rainfall * 0.06
        duration_effect = max(0.0, (duration_minutes - 170.0) * 0.015)
        delay_effect = max(0.0, (delay_minutes - 120.0) * 0.01)
        mango_extra = 1.3 if product == "mangue" and humidity > 75 else 0.0
        deterministic = base + product_adj + humidity_effect + rain_effect + duration_effect + delay_effect + mango_extra
    elif stage == "tri":
        humidity_effect = max(0.0, (humidity - 70.0) * 0.03)
        deterministic = base + product_adj + grade_adj + humidity_effect
    elif stage == "nettoyage":
        deterministic = base + product_adj + max(0.0, rainfall * 0.01)
    else:
        deterministic = base + product_adj + max(0.0, (delay_minutes - 90.0) * 0.003)

    noise = rng.normal(0.0, 1.35)
    loss_pct = deterministic + noise

    if anomalous:
        # Inject harder edge cases while keeping them bounded and labeled.
        loss_pct += rng.uniform(8.0, 22.0)

    return float(np.clip(loss_pct, 0.2, 55.0))


def generate_synthetic_benchmark(
    *,
    rows: int = 2000,
    seed: int = 42,
    assumptions: GenerationAssumptions = GenerationAssumptions(),
) -> pd.DataFrame:
    if rows <= 0:
        raise ValueError("rows must be positive")

    rng = np.random.default_rng(seed)
    lot_count = int(np.ceil(rows / len(STAGES)))
    start_dt = datetime.fromisoformat(assumptions.base_event_start)

    records: List[Dict] = []

    for lot_index in range(lot_count):
        product = str(rng.choice(PRODUCTS))
        season = str(rng.choice(SEASONS, p=[0.33, 0.31, 0.36]))
        region = str(rng.choice(REGIONS))
        grade = str(rng.choice(GRADES, p=[0.42, 0.39, 0.19]))
        synthetic_coop_id = f"syn-coop-{int(rng.integers(1, 6))}"
        lot_id = f"SYN-LOT-{lot_index+1:05d}"
        event_anchor = start_dt + timedelta(hours=12 * lot_index)

        qty_in = float(np.clip(rng.normal(1200.0, 380.0), 250.0, 3200.0))
        cumulative_before = 0.0

        for stage in STAGES:
            stage_order = STAGE_ORDER[stage]
            weather = _seasonal_weather(rng, season)
            anomalous = bool(rng.random() < assumptions.anomaly_rate)

            base_duration = {
                "nettoyage": rng.normal(95, 26),
                "sechage": rng.normal(250, 65),
                "tri": rng.normal(130, 35),
                "emballage": rng.normal(80, 20),
            }[stage]
            duration_minutes = float(np.clip(base_duration, 15, 640))

            delay_minutes = 0.0 if stage_order == 1 else float(np.clip(rng.normal(95, 70), 0, 560))
            if product == "mangue" and stage == "sechage":
                delay_minutes += float(np.clip(rng.normal(45, 30), 0, 180))

            missing_duration_flag = 1 if rng.random() < assumptions.missing_duration_rate else 0
            if missing_duration_flag:
                step_duration_minutes = np.nan
            else:
                step_duration_minutes = duration_minutes

            loss_pct = _compute_loss_pct(
                stage=stage,
                product=product,
                grade=grade,
                humidity=weather["humidity"],
                rainfall=weather["rainfall"],
                duration_minutes=duration_minutes,
                delay_minutes=delay_minutes,
                rng=rng,
                anomalous=anomalous,
            )
            loss_qty = float(qty_in * loss_pct / 100.0)
            qty_out = float(max(1.0, qty_in - loss_qty))
            efficiency_pct = float(np.clip((qty_out / qty_in) * 100.0, 0.0, 100.0))

            event_time = event_anchor + timedelta(minutes=int(cumulative_before + delay_minutes + duration_minutes))

            records.append(
                {
                    "synthetic_lot_id": lot_id,
                    "synthetic_cooperative_id": synthetic_coop_id,
                    "product": product,
                    "stage": stage,
                    "stage_order": stage_order,
                    "qty_in": round(qty_in, 3),
                    "qty_out": round(qty_out, 3),
                    "loss_qty": round(loss_qty, 3),
                    "loss_pct": round(loss_pct, 4),
                    "efficiency_pct": round(efficiency_pct, 4),
                    "event_time": event_time.isoformat(),
                    "season": season,
                    "region": region,
                    "grade": grade,
                    "humidity": round(weather["humidity"], 4),
                    "temperature": round(weather["temperature"], 4),
                    "rainfall": round(weather["rainfall"], 4),
                    "wind_speed": round(weather["wind_speed"], 4),
                    "dew_point": round(weather["dew_point"], 4),
                    "step_duration_minutes": (round(float(step_duration_minutes), 4) if not np.isnan(step_duration_minutes) else None),
                    "delay_since_previous_step_minutes": round(delay_minutes, 4),
                    "cumulative_duration_before_stage": round(cumulative_before, 4),
                    "missing_duration_flag": int(missing_duration_flag),
                    "anomaly_label_synthetic": int(anomalous),
                    "data_origin": "SYNTHETIC_BENCHMARK",
                }
            )

            # Next stage starts from current output.
            qty_in = qty_out
            cumulative_before += delay_minutes + duration_minutes

    df = pd.DataFrame(records).head(rows).copy()
    return df


def build_metadata(df: pd.DataFrame, *, rows: int, seed: int) -> Dict:
    return {
        "warning": SYNTHETIC_WARNING,
        "source": "synthetic",
        "rows_requested": int(rows),
        "rows_generated": int(len(df)),
        "seed": int(seed),
        "crops": PRODUCTS,
        "stages": STAGES,
        "data_origin_value": "SYNTHETIC_BENCHMARK",
        "generation_assumptions": {
            "drying_sensitivity": "loss increases with humidity, rainfall, and long duration/delay",
            "sorting_sensitivity": "loss depends on grade/product quality with noise",
            "cleaning_behavior": "moderate baseline loss",
            "packaging_behavior": "typically low loss",
            "mango_profile": "higher humidity and delay sensitivity",
            "noise": "gaussian noise plus random shocks",
            "anomalies": "explicitly injected and labeled via anomaly_label_synthetic",
        },
        "columns": list(df.columns),
    }


def save_outputs(df: pd.DataFrame, *, csv_path: Path, json_path: Path, metadata: Dict) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(metadata, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic post-harvest benchmark dataset.")
    parser.add_argument("--rows", type=int, default=2000, help="Number of synthetic process-step rows.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--output-csv",
        default="backend/artifacts/synthetic_postharvest_benchmark.csv",
        help="Output CSV path.",
    )
    parser.add_argument(
        "--output-json",
        default="backend/artifacts/synthetic_postharvest_benchmark.json",
        help="Output metadata JSON path.",
    )
    args = parser.parse_args()

    df = generate_synthetic_benchmark(rows=args.rows, seed=args.seed)
    metadata = build_metadata(df, rows=args.rows, seed=args.seed)
    save_outputs(df, csv_path=Path(args.output_csv), json_path=Path(args.output_json), metadata=metadata)

    print(f"Saved synthetic dataset CSV: {args.output_csv}")
    print(f"Saved synthetic dataset metadata JSON: {args.output_json}")
    print(f"Rows generated: {len(df)}")


if __name__ == "__main__":
    main()

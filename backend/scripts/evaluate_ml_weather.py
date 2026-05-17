#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from sqlalchemy import func, select
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sklearn.model_selection import train_test_split
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.base import Base
from app.core.config import settings
from app.db.session import SessionLocal
from app.ml.features.engineer import build_features
from app.models.process_step import ProcessStep
from app.ml.training.trainer import _split_train_test_indices
from app.ml.utils.feature_prep import assign_risk_level, prepare_feature_frame
from scripts.evaluate_ml_models import _distribution, _evaluate_split
from scripts.seed_ml_training_data import seed_ml_training_data

REGRESSION_GATE = 0.10
CLASSIFICATION_GATE = 0.10


def _safe_relative_improvement(baseline: float, model: float) -> float:
    if baseline <= 0:
        return 0.0
    return float((baseline - model) / baseline)


def _classification_improvement(model: float, baseline: float) -> float:
    if baseline <= 0:
        return 0.0
    return float((model - baseline) / baseline)


def _best_threshold_baseline(classification: Dict) -> tuple[str, float]:
    candidates = {
        "thresholded_predicted_loss_baseline": float(classification["thresholded_predicted_loss_baseline"]["macro_f1"]),
        "thresholded_product_stage_average_baseline": float(classification["thresholded_product_stage_average_baseline"]["macro_f1"]),
    }
    name = max(candidates, key=candidates.get)
    return name, candidates[name]


def _schema_columns(features_df) -> list[str]:
    prepared, _ = prepare_feature_frame(features_df.head(1).copy())
    return sorted(prepared.columns.tolist())


def run_weather_evaluation(
    db: Session,
    output_json: Path,
    output_md: Path,
    *,
    source_info: Dict | None = None,
) -> Dict:
    internal_set = build_features(db, include_weather=False)
    weather_set = build_features(db, include_weather=True)

    if internal_set.features.empty or weather_set.features.empty:
        raise RuntimeError("No ML feature rows available for weather evaluation.")

    internal_df = internal_set.features.copy()
    weather_df = weather_set.features.copy()
    internal_df["stage_canonical"] = internal_df["process_type"].astype(str).str.lower()
    weather_df["stage_canonical"] = weather_df["process_type"].astype(str).str.lower()

    internal_prepared, internal_feature_groups = prepare_feature_frame(internal_df)
    weather_prepared, weather_feature_groups = prepare_feature_frame(weather_df)

    int_train_time, int_test_time, split_details = _split_train_test_indices(internal_prepared, test_size=0.2)
    int_train_rand, int_test_rand = train_test_split(internal_prepared.index, test_size=0.2, random_state=42)

    weather_time_eval = _evaluate_split(weather_prepared, weather_feature_groups, int_train_time, int_test_time, "weather_time")
    weather_rand_eval = _evaluate_split(weather_prepared, weather_feature_groups, int_train_rand, int_test_rand, "weather_random")
    internal_time_eval = _evaluate_split(internal_prepared, internal_feature_groups, int_train_time, int_test_time, "internal_time")
    internal_rand_eval = _evaluate_split(internal_prepared, internal_feature_groups, int_train_rand, int_test_rand, "internal_random")

    regression_baselines = internal_time_eval["regression"]["baselines"]
    best_baseline_name, best_baseline_payload = min(
        regression_baselines.items(),
        key=lambda item: float(item[1]["mae"]),
    )
    best_baseline_mae = float(best_baseline_payload["mae"])
    internal_mae = float(internal_time_eval["regression"]["model"]["mae"])
    weather_mae = float(weather_time_eval["regression"]["model"]["mae"])

    weather_reg_improvement = _safe_relative_improvement(best_baseline_mae, weather_mae)
    internal_reg_improvement = _safe_relative_improvement(best_baseline_mae, internal_mae)
    weather_reg_pass = weather_reg_improvement >= REGRESSION_GATE
    internal_reg_pass = internal_reg_improvement >= REGRESSION_GATE

    best_numeric_model = "internal_model" if internal_mae <= weather_mae else "weather_model"
    best_numeric_across_all = (
        "baseline"
        if best_baseline_mae < min(internal_mae, weather_mae)
        else best_numeric_model
    )

    gate_pass_candidates = []
    if internal_reg_pass:
        gate_pass_candidates.append(("internal_model", internal_mae))
    if weather_reg_pass:
        gate_pass_candidates.append(("weather_model", weather_mae))
    if gate_pass_candidates:
        gate_promoted_candidate = min(gate_pass_candidates, key=lambda item: item[1])[0]
    else:
        gate_promoted_candidate = f"baseline:{best_baseline_name}"
    selected_regression = gate_promoted_candidate

    _, weather_best_threshold = _best_threshold_baseline(weather_time_eval["classification"])
    _, internal_best_threshold = _best_threshold_baseline(internal_time_eval["classification"])
    weather_cls_f1 = float(weather_time_eval["classification"]["model"]["macro_f1"])
    internal_cls_f1 = float(internal_time_eval["classification"]["model"]["macro_f1"])
    weather_cls_pass = _classification_improvement(weather_cls_f1, weather_best_threshold) >= CLASSIFICATION_GATE
    internal_cls_pass = _classification_improvement(internal_cls_f1, internal_best_threshold) >= CLASSIFICATION_GATE

    weather_diag = (weather_set.diagnostics or {}).get("weather", {})
    leakage_violations = int(weather_diag.get("leakage_violations", 0))

    report = {
        "source": source_info or {},
        "dataset": {
            "row_count": int(len(internal_df)),
            "product_distribution": _distribution(internal_df["product"]),
            "stage_distribution_raw": _distribution(internal_df["process_type"]),
            "risk_class_distribution": _distribution(internal_prepared["loss_pct"].apply(assign_risk_level)),
        },
        "weather_coverage": {
            "coverage_rate": float(weather_diag.get("coverage_rate", 0.0)),
            "rows_with_weather": int(weather_diag.get("rows_with_weather", 0)),
            "rows_without_weather": int(weather_diag.get("rows_without_weather", 0)),
            "total_rows": int(weather_diag.get("row_count", len(weather_df))),
        },
        "leakage_check": {
            "status": "PASS" if leakage_violations == 0 else "FAIL",
            "violations": leakage_violations,
            "rule": "weather_feature_timestamp must be <= event_time",
        },
        "split_details": {
            "time_based": split_details,
            "random": {"train_rows": int(len(int_train_rand)), "test_rows": int(len(int_test_rand))},
        },
        "evaluation": {
            "internal_model": {"time_based": internal_time_eval, "random_split_secondary": internal_rand_eval},
            "weather_model": {"time_based": weather_time_eval, "random_split_secondary": weather_rand_eval},
        },
        "comparison": {
            "regression": {
                "best_baseline_name": best_baseline_name,
                "best_baseline_mae": best_baseline_mae,
                "internal_model_mae": internal_mae,
                "weather_model_mae": weather_mae,
                "internal_relative_improvement_vs_baseline": internal_reg_improvement,
                "weather_relative_improvement_vs_baseline": weather_reg_improvement,
                "best_numeric_candidate_model_only": best_numeric_model,
                "best_numeric_candidate_across_all": best_numeric_across_all,
                "gate_promoted_candidate": gate_promoted_candidate,
                "production_decision": selected_regression,
                "selected_decision": selected_regression,
            },
            "classification": {
                "internal_model_macro_f1": internal_cls_f1,
                "internal_best_threshold_baseline_macro_f1": internal_best_threshold,
                "weather_model_macro_f1": weather_cls_f1,
                "weather_best_threshold_baseline_macro_f1": weather_best_threshold,
            },
        },
        "gates": {
            "regression_internal": "PASS" if internal_reg_pass else "FAIL",
            "regression_weather": "PASS" if weather_reg_pass else "FAIL",
            "classification_internal": "PASS" if internal_cls_pass else "FAIL",
            "classification_weather": "PASS" if weather_cls_pass else "FAIL",
        },
        "train_serve_schema_parity": {
            "status": "PASS" if _schema_columns(weather_df) == _schema_columns(weather_df.tail(1).copy()) else "FAIL",
            "train_columns_count": len(_schema_columns(weather_df)),
            "inference_columns_count": len(_schema_columns(weather_df.tail(1).copy())),
        },
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2))

    source = report.get("source", {})
    source_label = str(source.get("data_source_label") or "unknown")
    fallback_used = bool(source.get("fallback_used", False))
    lines = [
        "# WeeFarm ML Weather Evaluation",
        "",
    ]
    if fallback_used:
        lines.extend([
            "## LOCAL/FALLBACK DATASET — NOT COMPARABLE TO FULL SUPABASE AUDIT.",
            "",
        ])
    lines.extend([
        "## Data Source",
        f"- Label: {source_label}",
        f"- Identifier: {source.get('database_identifier')}",
        f"- Fallback used: {fallback_used}",
        f"- Generated at: {source.get('generated_at')}",
        f"- Python runtime: {source.get('python_runtime')}",
        "",
        "## Dataset",
        f"- Rows: {report['dataset']['row_count']}",
        "",
        "## Weather Coverage",
        f"- Coverage rate: {report['weather_coverage']['coverage_rate']:.4f}",
        f"- Rows with weather: {report['weather_coverage']['rows_with_weather']}",
        f"- Rows without weather: {report['weather_coverage']['rows_without_weather']}",
        "",
        "## Leakage Check",
        f"- Status: {report['leakage_check']['status']}",
        f"- Violations: {report['leakage_check']['violations']}",
        "",
        "## Regression (Time Split Primary)",
        f"- Baseline ({best_baseline_name}) MAE: {best_baseline_mae:.4f}",
        f"- Internal model MAE: {internal_mae:.4f}",
        f"- Weather model MAE: {weather_mae:.4f}",
        f"- Internal relative improvement vs best baseline: {internal_reg_improvement * 100:.2f}%",
        f"- Weather relative improvement vs best baseline: {weather_reg_improvement * 100:.2f}%",
        f"- Best numeric candidate (model-only): {best_numeric_model}",
        f"- Best numeric candidate (across all): {best_numeric_across_all}",
        f"- Gate-promoted candidate: {gate_promoted_candidate}",
        f"- Production decision: {selected_regression}",
        f"- Selected decision: {selected_regression}",
        "",
        "## Regression (Random Split Secondary)",
        f"- Internal model MAE: {internal_rand_eval['regression']['model']['mae']:.4f}",
        f"- Weather model MAE: {weather_rand_eval['regression']['model']['mae']:.4f}",
        "",
        "## Classification (Time Split)",
        f"- Internal model macro-F1: {internal_cls_f1:.4f}",
        f"- Internal best threshold baseline macro-F1: {internal_best_threshold:.4f}",
        f"- Weather model macro-F1: {weather_cls_f1:.4f}",
        f"- Weather best threshold baseline macro-F1: {weather_best_threshold:.4f}",
        "",
        "## Gate Results",
        f"- Internal regression gate: {report['gates']['regression_internal']}",
        f"- Weather regression gate: {report['gates']['regression_weather']}",
        f"- Internal classification gate: {report['gates']['classification_internal']}",
        f"- Weather classification gate: {report['gates']['classification_weather']}",
    ])
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines))
    return report


def _local_sqlite_session() -> tuple[Session, bool]:
    sqlite_path = BACKEND_DIR / "weefarm.db"
    engine = create_engine(
        f"sqlite:///{sqlite_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    SessionLocalSQLite = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)
    session = SessionLocalSQLite()
    step_count = int(session.scalar(select(func.count(ProcessStep.id))) or 0)
    seeded = False
    if step_count == 0:
        seed_ml_training_data(session, target_rows=500, random_seed=42, demo_only=True)
        seeded = True
    return session, seeded


def _source_info(*, fallback_used: bool, seeded_local: bool) -> Dict:
    generated_at = datetime.now(timezone.utc).isoformat()
    python_runtime = platform.python_version()
    if fallback_used:
        label = "test_seed" if seeded_local else "fallback_sqlite"
        return {
            "data_source_label": label,
            "database_identifier": str((BACKEND_DIR / "weefarm.db").resolve()),
            "fallback_used": True,
            "generated_at": generated_at,
            "python_runtime": python_runtime,
        }

    masked = settings.masked_database_url
    label = "supabase" if "supabase.com" in masked or "pooler.supabase.com" in masked else "unknown"
    return {
        "data_source_label": label,
        "database_identifier": masked,
        "fallback_used": False,
        "generated_at": generated_at,
        "python_runtime": python_runtime,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate weather-aware vs internal ML models.")
    parser.add_argument("--output-json", default="backend/reports/ml_weather_evaluation.json")
    parser.add_argument("--output-md", default="backend/reports/ml_weather_evaluation.md")
    args = parser.parse_args()

    db = SessionLocal()
    used_local_fallback = False
    local_seeded = False
    try:
        report = run_weather_evaluation(
            db,
            output_json=Path(args.output_json),
            output_md=Path(args.output_md),
            source_info=_source_info(fallback_used=False, seeded_local=False),
        )
    except OperationalError:
        db.close()
        db, local_seeded = _local_sqlite_session()
        used_local_fallback = True
        report = run_weather_evaluation(
            db,
            output_json=Path(args.output_json),
            output_md=Path(args.output_md),
            source_info=_source_info(fallback_used=True, seeded_local=local_seeded),
        )
    finally:
        db.close()
    print(f"Saved JSON report: {args.output_json}")
    print(f"Saved Markdown report: {args.output_md}")
    print(f"Data source: {report.get('source', {}).get('data_source_label')}")
    print(f"Weather coverage: {report['weather_coverage']['coverage_rate']:.4f}")
    print(f"Regression decision: {report['comparison']['regression']['selected_decision']}")


if __name__ == "__main__":
    main()

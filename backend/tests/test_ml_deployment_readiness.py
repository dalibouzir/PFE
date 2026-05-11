from __future__ import annotations

import json
from pathlib import Path

import joblib

from app.core import config
from app.ml.training.trainer import MODEL_FILES
from app.ml.utils.model_registry import ensure_registry_files, register_model_version, set_active_model_version, store_versioned_artifacts
from scripts.ml_deployment_readiness import run_deployment_readiness


def _create_dummy_artifacts(tmp_path: Path) -> dict:
    joblib.dump({"name": "loss"}, tmp_path / MODEL_FILES["loss_regressor"])
    joblib.dump({"name": "risk"}, tmp_path / MODEL_FILES["risk_classifier"])
    joblib.dump({"name": "anomaly"}, tmp_path / MODEL_FILES["anomaly_detector"])
    (tmp_path / MODEL_FILES["feature_metadata"]).write_text(
        json.dumps(
            {
                "model_version": "v-ready",
                "feature_schema_version": "phase4-v1",
                "predictive_regression_features": ["product", "process_type", "qty_in", "date_ordinal"],
                "predictive_classification_features": ["product", "process_type", "qty_in", "date_ordinal"],
                "assessment_anomaly_features": ["product", "process_type", "qty_in", "qty_out", "loss_pct", "efficiency_pct", "deviation_from_stage_avg", "date_ordinal"],
            }
        )
    )
    return {key: str(tmp_path / filename) for key, filename in MODEL_FILES.items()}


def test_deployment_readiness_report_generation_and_no_production_claim(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "ml_artifacts_path", str(tmp_path))
    ensure_registry_files()

    sources = _create_dummy_artifacts(tmp_path)
    stored = store_versioned_artifacts("v-ready", sources)
    register_model_version(
        model_version="v-ready",
        run_name="phase5",
        feature_schema_version="phase4-v1",
        training_rows=1485,
        metrics={
            "regression_mae": 3.78,
            "regression_stage_mean_mae": 2.66,
            "regression_product_stage_mean_mae": 2.67,
            "false_low_high_risk_rate": 0.0,
        },
        artifact_paths=stored,
        status="candidate",
        validation={"mvp_demo_allowed": True, "production_ready": False},
    )
    set_active_model_version("v-ready")

    diagnostics_path = tmp_path / "diag.json"
    diagnostics_path.write_text(json.dumps({"leakage_checks": {"predictive_feature_leakage_flags": []}}))

    eval_path = tmp_path / "eval.json"
    eval_path.write_text(
        json.dumps(
            {
                "evaluation": {
                    "time_based": {
                        "regression": {
                            "model": {"mae": 3.78},
                            "baselines": {
                                "stage_mean_loss": {"mae": 2.66},
                                "product_stage_mean_loss": {"mae": 2.67},
                            },
                        },
                        "classification": {
                            "model": {
                                "macro_f1": 0.30,
                                "medium_recall": 0.0,
                                "high_recall": 0.0,
                                "false_low_high_risk_rate": 1.0,
                            }
                        },
                    }
                }
            }
        )
    )

    monitoring_path = tmp_path / "mon.json"
    monitoring_path.write_text(json.dumps({"warnings": ["synthetic_demo_data_used"]}))

    output_json = tmp_path / "ml_deployment_readiness.json"
    output_md = tmp_path / "ml_deployment_readiness.md"

    report = run_deployment_readiness(
        db_session,
        output_json=output_json,
        output_md=output_md,
        diagnostics_path=diagnostics_path,
        evaluation_path=eval_path,
        monitoring_path=monitoring_path,
    )

    assert output_json.exists()
    assert output_md.exists()
    assert report["active_model"]["production_ready"] is False
    assert report["deployment_recommendation"] in {"deploy_mvp_with_warnings", "deploy_demo_only", "do_not_deploy"}
    assert "model_underperforms_stage_baseline" in report["known_limitations"]

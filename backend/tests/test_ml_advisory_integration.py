from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_current_manager
from app.core import config
from app.db.session import get_db
from app.main import app
from app.ml.advisory_diagnostics import (
    compute_critical_risk_advisory,
    detect_assessment_anomalies,
    estimate_loss_with_stage_baseline,
    rank_rule_recommendations,
)
from app.ml.features.engineer import build_features
from app.ml.training.trainer import train_models
from app.models.batch import Batch
from app.models.user import User


def _predictive_payload_from_feature(feature: dict) -> dict:
    return {
        "features": [
            {
                "product": feature["product"],
                "process_type": feature["process_type"],
                "qty_in": feature["qty_in"],
                "batch_size": feature["batch_size"],
                "stock_level": feature["stock_level"],
                "date": datetime.fromisoformat(str(feature["date"])).isoformat(),
                "month": feature["month"],
                "week_of_year": feature["week_of_year"],
                "season": feature["season"],
                "historical_avg_loss_same_product": feature["historical_avg_loss_same_product"],
                "historical_avg_loss_same_stage": feature["historical_avg_loss_same_stage"],
                "historical_avg_efficiency_same_stage": feature["historical_avg_efficiency_same_stage"],
                "previous_batch_loss": feature["previous_batch_loss"],
                "rolling_loss_last_n_batches": feature["rolling_loss_last_n_batches"],
                "rolling_efficiency_last_n_batches": feature["rolling_efficiency_last_n_batches"],
            }
        ],
        "include_explanation": False,
    }


def test_advisory_diagnostics_pure_functions():
    row = {
        "product": "mangue",
        "process_type": "sechage",
        "season": "rainy",
        "stage_season_avg_loss": 11.2,
        "historical_avg_loss_same_stage": 10.0,
        "qty_in": 100.0,
        "qty_out": 60.0,
        "loss_pct": 40.0,
        "efficiency_pct": 0.6,
        "humidity": 88.0,
        "rainfall": 10.0,
        "dew_point": 25.0,
        "step_duration_minutes": 260.0,
        "delay_since_previous_step_minutes": 200.0,
        "missing_duration_flag": 0,
    }

    baseline = estimate_loss_with_stage_baseline(row)
    assert "estimate_loss_pct" in baseline
    assert baseline["baseline_type"]

    risk = compute_critical_risk_advisory(
        row,
        baseline_estimate=baseline,
        observed_loss_pct=row["loss_pct"],
    )
    assert {"risk_level", "risk_score", "advisory_flags"}.issubset(risk.keys())

    anomaly = detect_assessment_anomalies(row)
    assert anomaly["is_anomalous"] is True
    assert anomaly["anomaly_flags"]

    recs = [
        "Inspect process step and verify material balance",
        "Reduce waiting time before next stage",
        "Monitor only / no strong action",
    ]
    ranked = rank_rule_recommendations(
        recs,
        feature_row=row,
        critical_risk_advisory=risk,
        anomaly_diagnostics=anomaly,
        mode="assessment",
    )
    assert len(ranked) == len(recs)
    assert all("priority_score" in item for item in ranked)


def test_ml_endpoints_include_advisory_fields_and_readiness(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "ml_min_rows", 1)
    monkeypatch.setattr(config.settings, "ml_artifacts_path", str(tmp_path))
    train_models(db_session, run_name="advisory-integration")

    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_manager] = lambda: db_session.query(User).first()
    client = TestClient(app)

    first_feature = build_features(db_session).raw[0]
    predict_response = client.post("/ml/predict", json=_predictive_payload_from_feature(first_feature))
    assert predict_response.status_code == 200
    predict_payload = predict_response.json()
    assert "prediction" in predict_payload
    assert "recommendation" in predict_payload
    assert "baseline_estimate" in predict_payload["prediction"]
    assert "critical_risk_advisory" in predict_payload["prediction"]
    assert predict_payload["prediction"]["ml_strategy"] == "enhanced_advisory_v1"
    assert predict_payload["prediction"]["benchmark_source"] == "synthetic_offline_selected_strategy"
    assert predict_payload["prediction"]["integrated_strategy"] is True
    assert predict_payload["prediction"]["advisory_only"] is True
    assert "ml_readiness_state" in predict_payload["prediction"]
    assert "recommendation_mode" in predict_payload["prediction"]
    assert predict_payload["prediction"]["promoted"] is False
    assert "ranked_recommendations" in predict_payload["recommendation"]
    assert len(predict_payload["recommendation"]["ranked_recommendations"]) == len(
        predict_payload["recommendation"]["recommended_actions"]
    )

    batch_id = str(db_session.scalar(select(Batch.id).limit(1)))
    assess_response = client.post("/ml/assess", json={"batch_id": batch_id, "include_explanation": False})
    assert assess_response.status_code == 200
    assess_payload = assess_response.json()
    assert "assessment_anomaly_diagnostics" in assess_payload["assessment"]
    assert "critical_risk_advisory" in assess_payload["assessment"]
    assert assess_payload["assessment"]["ml_strategy"] == "enhanced_advisory_v1"
    assert assess_payload["assessment"]["promoted"] is False
    assert "ranked_recommendations" in assess_payload["recommendation"]

    recommendation_response = client.get(f"/ml/recommendation/{batch_id}")
    assert recommendation_response.status_code == 200
    recommendation_payload = recommendation_response.json()
    assert "assessment" in recommendation_payload
    assert "recommendation" in recommendation_payload
    assert "ranked_recommendations" in recommendation_payload["recommendation"]
    assert "ml_readiness_state" in recommendation_payload["assessment"]

    app.dependency_overrides.clear()


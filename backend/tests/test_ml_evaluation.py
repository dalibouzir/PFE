from __future__ import annotations

import json
from pathlib import Path

from scripts.evaluate_ml_models import run_evaluation


def test_evaluation_script_generates_reports_and_required_sections(db_session, tmp_path):
    output_json = tmp_path / "ml_evaluation_report.json"
    output_md = tmp_path / "ml_evaluation_report.md"

    report = run_evaluation(db_session, output_json=output_json, output_md=output_md)

    assert output_json.exists()
    assert output_md.exists()
    assert report["dataset"]["row_count"] > 0

    time_eval = report["evaluation"]["time_based"]
    assert "baselines" in time_eval["regression"]
    assert "global_mean_loss" in time_eval["regression"]["baselines"]
    assert "product_mean_loss" in time_eval["regression"]["baselines"]
    assert "stage_mean_loss" in time_eval["regression"]["baselines"]
    assert "product_stage_mean_loss" in time_eval["regression"]["baselines"]
    assert "stage_season_mean_loss" in time_eval["regression"]["baselines"]
    assert "product_stage_season_mean_loss" in time_eval["regression"]["baselines"]
    assert "product_stage_rolling_mean_loss" in time_eval["regression"]["baselines"]
    assert "previous_batch_loss_baseline" in time_eval["regression"]["baselines"]
    assert "by_product" in time_eval["segment_analysis"]
    assert "by_canonical_stage" in time_eval["segment_analysis"]
    assert "by_product_stage" in time_eval["segment_analysis"]
    assert "by_risk_class" in time_eval["segment_analysis"]
    assert time_eval["anomaly_review"]["anomaly_accuracy_reported"] is False
    assert "thresholded_predicted_loss_baseline" in time_eval["classification"]
    assert "thresholded_product_stage_average_baseline" in time_eval["classification"]
    assert "false_low_high_risk_rate" in time_eval["classification"]["model"]

    payload = json.loads(output_json.read_text())
    assert "evaluation" in payload
    assert "time_based" in payload["evaluation"]

    md = output_md.read_text()
    assert "# ML Evaluation Report" in md
    assert "## Honest Interpretation" in md
    assert "No anomaly accuracy is reported" in md

from __future__ import annotations

import json

from scripts.evaluate_ml_reliability import _build_gate_results, run_reliability_audit


def _time_eval_fixture(*, model_mae: float, baseline_mae: float, model_f1: float, thr1_f1: float, thr2_f1: float):
    return {
        "regression": {
            "model": {"mae": model_mae},
            "baselines": {
                "global_mean_loss": {"mae": baseline_mae + 1.0},
                "stage_mean_loss": {"mae": baseline_mae},
            },
        },
        "classification": {
            "model": {"macro_f1": model_f1},
            "thresholded_predicted_loss_baseline": {"macro_f1": thr1_f1},
            "thresholded_product_stage_average_baseline": {"macro_f1": thr2_f1},
        },
    }


def test_regression_gate_fails_when_model_does_not_beat_best_baseline_by_10pct():
    time_eval = _time_eval_fixture(
        model_mae=4.0,
        baseline_mae=3.8,
        model_f1=0.45,
        thr1_f1=0.35,
        thr2_f1=0.33,
    )
    gates = _build_gate_results(time_eval, has_reco_feedback=False)
    assert gates["regression"]["status"] == "FAIL"


def test_classification_gate_passes_only_when_margin_is_at_least_10pct():
    pass_eval = _time_eval_fixture(
        model_mae=3.0,
        baseline_mae=3.5,
        model_f1=0.44,
        thr1_f1=0.39,
        thr2_f1=0.36,
    )
    fail_eval = _time_eval_fixture(
        model_mae=3.0,
        baseline_mae=3.5,
        model_f1=0.42,
        thr1_f1=0.39,
        thr2_f1=0.36,
    )
    assert _build_gate_results(pass_eval, has_reco_feedback=False)["classification"]["status"] == "PASS"
    assert _build_gate_results(fail_eval, has_reco_feedback=False)["classification"]["status"] == "FAIL"


def test_anomaly_and_recommendation_are_declared_non_claimable_without_required_evidence():
    time_eval = _time_eval_fixture(
        model_mae=3.0,
        baseline_mae=3.5,
        model_f1=0.44,
        thr1_f1=0.39,
        thr2_f1=0.36,
    )
    gates = _build_gate_results(time_eval, has_reco_feedback=False)
    assert gates["anomaly_detection"]["status"] == "EXPLORATORY"
    assert gates["anomaly_detection"]["ground_truth_labels_available"] is False
    assert gates["recommendation_policy"]["status"] == "RULE_BASED"
    assert gates["recommendation_policy"]["action_outcome_feedback_exists"] is False


def test_reliability_audit_generates_reports_with_gate_section(db_session, tmp_path):
    output_json = tmp_path / "ml_reliability_audit.json"
    output_md = tmp_path / "ml_reliability_audit.md"
    report = run_reliability_audit(db_session, output_json=output_json, output_md=output_md)

    assert output_json.exists()
    assert output_md.exists()
    assert report["dataset"]["row_count"] > 0
    assert report["gates"]["anomaly_detection"]["status"] == "EXPLORATORY"
    assert report["gates"]["recommendation_policy"]["status"] == "RULE_BASED"
    assert report["selected_model_or_fallback"]["anomaly_detection"] == "exploratory_only"
    assert report["selected_model_or_fallback"]["recommendation_policy"] == "rule_engine_templates"

    payload = json.loads(output_json.read_text())
    assert "gates" in payload
    assert "baseline_comparison_table_time_split" in payload

    md = output_md.read_text()
    assert "# WeeFarm ML Reliability Audit" in md
    assert "## Gate Results" in md
    assert "Cannot claim:" in md

from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_synthetic_postharvest_benchmark import (
    build_metadata,
    generate_synthetic_benchmark,
    save_outputs,
)
from scripts.run_ml_synthetic_model_improvement import (
    SOURCE_LABEL,
    SYNTHETIC_OFFLINE_WARNING,
    run_synthetic_model_improvement,
)


def test_runner_works_without_db_connection(tmp_path):
    script_text = Path("backend/scripts/run_ml_synthetic_model_improvement.py").read_text()
    assert "app.db" not in script_text

    df = generate_synthetic_benchmark(rows=240, seed=19)
    dataset_csv = tmp_path / "synthetic.csv"
    dataset_meta = tmp_path / "synthetic.json"
    save_outputs(df, csv_path=dataset_csv, json_path=dataset_meta, metadata=build_metadata(df, rows=240, seed=19))

    output_json = tmp_path / "reports" / "ml_synthetic_model_improvement.json"
    output_md = tmp_path / "reports" / "ml_synthetic_model_improvement.md"
    report = run_synthetic_model_improvement(
        dataset_csv=dataset_csv,
        output_json=output_json,
        output_md=output_md,
    )
    assert report["dataset"]["row_count"] == 240
    assert output_json.exists()
    assert output_md.exists()


def test_report_contains_warning_and_source_label(tmp_path):
    df = generate_synthetic_benchmark(rows=260, seed=21)
    dataset_csv = tmp_path / "synthetic.csv"
    dataset_meta = tmp_path / "synthetic.json"
    save_outputs(df, csv_path=dataset_csv, json_path=dataset_meta, metadata=build_metadata(df, rows=260, seed=21))

    output_json = tmp_path / "reports" / "ml_synthetic_model_improvement.json"
    output_md = tmp_path / "reports" / "ml_synthetic_model_improvement.md"
    run_synthetic_model_improvement(
        dataset_csv=dataset_csv,
        output_json=output_json,
        output_md=output_md,
    )

    payload = json.loads(output_json.read_text())
    md = output_md.read_text()
    assert payload["warning"] == SYNTHETIC_OFFLINE_WARNING
    assert SYNTHETIC_OFFLINE_WARNING in md
    assert payload["source_label"] == SOURCE_LABEL
    assert payload["evaluation"]["time_based"]["classification"]["critical_risk_failure_diagnostics"]["high_risk_support_count"] >= 0


def test_runner_does_not_overwrite_real_supabase_reports(tmp_path):
    df = generate_synthetic_benchmark(rows=220, seed=25)
    dataset_csv = tmp_path / "synthetic.csv"
    dataset_meta = tmp_path / "synthetic.json"
    save_outputs(df, csv_path=dataset_csv, json_path=dataset_meta, metadata=build_metadata(df, rows=220, seed=25))

    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    real_json = reports_dir / "ml_reliability_audit.json"
    real_md = reports_dir / "ml_reliability_audit.md"
    real_json.write_text("REAL_SUPABASE_REPORT")
    real_md.write_text("REAL_SUPABASE_REPORT_MD")

    output_json = reports_dir / "ml_synthetic_model_improvement.json"
    output_md = reports_dir / "ml_synthetic_model_improvement.md"
    run_synthetic_model_improvement(
        dataset_csv=dataset_csv,
        output_json=output_json,
        output_md=output_md,
    )

    assert real_json.read_text() == "REAL_SUPABASE_REPORT"
    assert real_md.read_text() == "REAL_SUPABASE_REPORT_MD"


def test_runner_does_not_overwrite_production_model_artifacts(tmp_path):
    df = generate_synthetic_benchmark(rows=210, seed=27)
    dataset_csv = tmp_path / "synthetic.csv"
    dataset_meta = tmp_path / "synthetic.json"
    save_outputs(df, csv_path=dataset_csv, json_path=dataset_meta, metadata=build_metadata(df, rows=210, seed=27))

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    sentinels = [
        artifacts_dir / "loss_regressor.joblib",
        artifacts_dir / "risk_classifier.joblib",
        artifacts_dir / "anomaly_detector.joblib",
    ]
    before = {}
    for idx, path in enumerate(sentinels):
        path.write_text(f"sentinel-{idx}")
        before[path.name] = (path.read_text(), path.stat().st_mtime_ns)

    output_json = tmp_path / "reports" / "ml_synthetic_model_improvement.json"
    output_md = tmp_path / "reports" / "ml_synthetic_model_improvement.md"
    run_synthetic_model_improvement(
        dataset_csv=dataset_csv,
        output_json=output_json,
        output_md=output_md,
    )

    for path in sentinels:
        assert path.read_text() == before[path.name][0]
        assert path.stat().st_mtime_ns == before[path.name][1]


def test_output_includes_candidate_tables_and_gates(tmp_path):
    df = generate_synthetic_benchmark(rows=280, seed=33)
    dataset_csv = tmp_path / "synthetic.csv"
    dataset_meta = tmp_path / "synthetic.json"
    save_outputs(df, csv_path=dataset_csv, json_path=dataset_meta, metadata=build_metadata(df, rows=280, seed=33))

    output_json = tmp_path / "reports" / "ml_synthetic_model_improvement.json"
    output_md = tmp_path / "reports" / "ml_synthetic_model_improvement.md"
    run_synthetic_model_improvement(
        dataset_csv=dataset_csv,
        output_json=output_json,
        output_md=output_md,
    )

    payload = json.loads(output_json.read_text())
    md = output_md.read_text()

    reg_rows = payload["evaluation"]["time_based"]["regression"]["candidates_ranked"]
    cls_rows = payload["evaluation"]["time_based"]["classification"]["candidates_ranked"]
    anom_payload = payload["evaluation"]["time_based"]["anomaly_diagnostics"]
    rec_payload = payload["evaluation"]["time_based"]["recommendation_ranking"]
    pred_rows = payload["evaluation"]["time_based"]["classification"]["prediction_mode_candidates_ranked"]
    assess_rows = payload["evaluation"]["time_based"]["classification"]["assessment_mode_candidates_ranked"]
    assert reg_rows
    assert cls_rows
    assert pred_rows

    assert all("best_baseline_name" in row for row in reg_rows)
    assert all("gate_pass" in row for row in reg_rows)
    assert all("best_baseline_name" in row for row in cls_rows)
    assert all("gate_pass" in row for row in cls_rows)
    assert all("high_risk_recall" in row for row in cls_rows)
    assert all("false_low_high_risk_rate" in row for row in cls_rows)
    assert all("confusion_matrix" in row for row in cls_rows)
    assert all("mode" in row for row in cls_rows)
    assert all(row["mode"] == "prediction_mode" for row in pred_rows)
    assert all(row["mode"] == "assessment_mode" for row in assess_rows)
    assert anom_payload["classification_status_frozen"]["decision"] == "PARTIAL"
    assert anom_payload["isolation_forest_baseline"]["candidate"] == "IsolationForestBaseline"
    assert anom_payload["prediction_mode_candidates"]
    assert anom_payload["assessment_mode_candidates"]
    assert all("precision" in row for row in anom_payload["prediction_mode_candidates"])
    assert all("recall" in row for row in anom_payload["prediction_mode_candidates"])
    assert all("f1" in row for row in anom_payload["prediction_mode_candidates"])
    assert all("precision_at_10pct" in row for row in anom_payload["prediction_mode_candidates"])
    assert all("candidate_type" in row for row in anom_payload["prediction_mode_candidates"])
    assert all("mode" in row for row in anom_payload["prediction_mode_candidates"])
    assert all(row["mode"] == "prediction_mode" for row in anom_payload["prediction_mode_candidates"])
    assert all(row["mode"] == "assessment_mode" for row in anom_payload["assessment_mode_candidates"])
    assert "final_anomaly_decision" in anom_payload
    assert rec_payload["warning"]
    assert rec_payload["prediction_mode_candidates"]
    assert rec_payload["assessment_mode_candidates"]
    assert all("precision_at_3" in row for row in rec_payload["prediction_mode_candidates"])
    assert all("precision_at_5" in row for row in rec_payload["prediction_mode_candidates"])
    assert all("ndcg_at_5" in row for row in rec_payload["prediction_mode_candidates"])
    assert all("mode" in row for row in rec_payload["prediction_mode_candidates"])
    assert all(row["mode"] == "prediction_mode" for row in rec_payload["prediction_mode_candidates"])
    assert all(row["mode"] == "assessment_mode" for row in rec_payload["assessment_mode_candidates"])
    assert "final_recommendation_ranking_decision" in rec_payload

    assert "Regression Candidate Table (Time Split Primary)" in md
    assert "Phase 1B Prediction-Mode Candidate Table (Time Split Primary)" in md
    assert "Phase 1B Assessment-Mode Candidate Table (Time Split Primary)" in md
    assert "best_baseline" in md
    assert "Critical-Risk Diagnostics (Time Split Primary)" in md
    assert "Threshold Tuning Tradeoff (Time Split Primary)" in md
    assert "Phase 1C Pareto Frontier (Prediction-Mode)" in md
    assert "Final classification decision (Phase 1C)" in md
    assert "Anomaly Candidate Table (Prediction-Mode)" in md
    assert "Anomaly Candidate Table (Assessment-Mode)" in md
    assert "Final anomaly decision" in md
    assert "Recommendation Ranking Candidates (Prediction-Mode)" in md
    assert "Recommendation Ranking Candidates (Assessment-Mode)" in md
    assert "Final recommendation-ranking decision" in md


def test_writes_optional_critical_risk_report_files(tmp_path):
    df = generate_synthetic_benchmark(rows=260, seed=41)
    dataset_csv = tmp_path / "synthetic.csv"
    dataset_meta = tmp_path / "synthetic.json"
    save_outputs(df, csv_path=dataset_csv, json_path=dataset_meta, metadata=build_metadata(df, rows=260, seed=41))

    output_json = tmp_path / "reports" / "ml_synthetic_model_improvement.json"
    output_md = tmp_path / "reports" / "ml_synthetic_model_improvement.md"
    critical_json = tmp_path / "reports" / "ml_synthetic_critical_risk_detection.json"
    critical_md = tmp_path / "reports" / "ml_synthetic_critical_risk_detection.md"

    run_synthetic_model_improvement(
        dataset_csv=dataset_csv,
        output_json=output_json,
        output_md=output_md,
        critical_output_json=critical_json,
        critical_output_md=critical_md,
    )

    assert critical_json.exists()
    assert critical_md.exists()
    payload = json.loads(critical_json.read_text())
    assert payload["warning"] == SYNTHETIC_OFFLINE_WARNING
    assert "best_prediction_mode_candidate" in payload
    assert "best_assessment_mode_candidate" in payload
    assert "prediction_mode_candidates" in payload
    assert "phase1c_pareto_frontier_prediction_mode" in payload
    assert "phase1c_final_decision" in payload


def test_writes_optional_anomaly_report_files(tmp_path):
    df = generate_synthetic_benchmark(rows=260, seed=43)
    dataset_csv = tmp_path / "synthetic.csv"
    dataset_meta = tmp_path / "synthetic.json"
    save_outputs(df, csv_path=dataset_csv, json_path=dataset_meta, metadata=build_metadata(df, rows=260, seed=43))

    output_json = tmp_path / "reports" / "ml_synthetic_model_improvement.json"
    output_md = tmp_path / "reports" / "ml_synthetic_model_improvement.md"
    anomaly_json = tmp_path / "reports" / "ml_synthetic_anomaly_detection.json"
    anomaly_md = tmp_path / "reports" / "ml_synthetic_anomaly_detection.md"

    run_synthetic_model_improvement(
        dataset_csv=dataset_csv,
        output_json=output_json,
        output_md=output_md,
        anomaly_output_json=anomaly_json,
        anomaly_output_md=anomaly_md,
    )

    assert anomaly_json.exists()
    assert anomaly_md.exists()
    payload = json.loads(anomaly_json.read_text())
    assert payload["warning"] == SYNTHETIC_OFFLINE_WARNING
    assert "prediction_mode_candidates" in payload
    assert "assessment_mode_candidates" in payload
    assert "isolation_forest_baseline" in payload
    assert "final_anomaly_decision" in payload


def test_writes_optional_recommendation_report_files(tmp_path):
    df = generate_synthetic_benchmark(rows=260, seed=47)
    dataset_csv = tmp_path / "synthetic.csv"
    dataset_meta = tmp_path / "synthetic.json"
    save_outputs(df, csv_path=dataset_csv, json_path=dataset_meta, metadata=build_metadata(df, rows=260, seed=47))

    output_json = tmp_path / "reports" / "ml_synthetic_model_improvement.json"
    output_md = tmp_path / "reports" / "ml_synthetic_model_improvement.md"
    rec_json = tmp_path / "reports" / "ml_synthetic_recommendation_ranking.json"
    rec_md = tmp_path / "reports" / "ml_synthetic_recommendation_ranking.md"

    run_synthetic_model_improvement(
        dataset_csv=dataset_csv,
        output_json=output_json,
        output_md=output_md,
        recommendation_output_json=rec_json,
        recommendation_output_md=rec_md,
    )

    assert rec_json.exists()
    assert rec_md.exists()
    payload = json.loads(rec_json.read_text())
    assert payload["warning"] == SYNTHETIC_OFFLINE_WARNING
    assert "prediction_mode_candidates" in payload
    assert "assessment_mode_candidates" in payload
    assert "proxy_relevance_warning" in payload
    assert "final_recommendation_ranking_decision" in payload

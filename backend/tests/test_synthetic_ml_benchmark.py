from __future__ import annotations

import json
from pathlib import Path

from scripts.evaluate_ml_synthetic_benchmark import SYNTHETIC_WARNING, run_synthetic_benchmark
from scripts.generate_synthetic_postharvest_benchmark import (
    build_metadata,
    generate_synthetic_benchmark,
    save_outputs,
)


def test_generator_creates_requested_number_of_rows(tmp_path):
    rows = 321
    df = generate_synthetic_benchmark(rows=rows, seed=7)
    assert len(df) == rows

    metadata = build_metadata(df, rows=rows, seed=7)
    csv_path = tmp_path / "synthetic.csv"
    json_path = tmp_path / "synthetic.json"
    save_outputs(df, csv_path=csv_path, json_path=json_path, metadata=metadata)

    assert csv_path.exists()
    assert json_path.exists()


def test_all_rows_are_marked_synthetic_origin():
    df = generate_synthetic_benchmark(rows=150, seed=3)
    assert (df["data_origin"] == "SYNTHETIC_BENCHMARK").all()


def test_generator_requires_no_db_connection():
    script_text = Path("backend/scripts/generate_synthetic_postharvest_benchmark.py").read_text()
    assert "app.db" not in script_text
    df = generate_synthetic_benchmark(rows=40, seed=11)
    assert len(df) == 40


def test_evaluator_does_not_write_production_artifacts(tmp_path):
    dataset_df = generate_synthetic_benchmark(rows=220, seed=9)
    dataset_csv = tmp_path / "synthetic.csv"
    dataset_meta = tmp_path / "synthetic.json"
    save_outputs(dataset_df, csv_path=dataset_csv, json_path=dataset_meta, metadata=build_metadata(dataset_df, rows=220, seed=9))

    # Sentinel files that must remain untouched.
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

    output_json = tmp_path / "reports" / "ml_synthetic_benchmark_report.json"
    output_md = tmp_path / "reports" / "ml_synthetic_benchmark_report.md"

    run_synthetic_benchmark(dataset_csv=dataset_csv, output_json=output_json, output_md=output_md)

    for path in sentinels:
        assert path.read_text() == before[path.name][0]
        assert path.stat().st_mtime_ns == before[path.name][1]


def test_report_contains_synthetic_warning(tmp_path):
    dataset_df = generate_synthetic_benchmark(rows=180, seed=12)
    dataset_csv = tmp_path / "synthetic.csv"
    dataset_meta = tmp_path / "synthetic.json"
    save_outputs(dataset_df, csv_path=dataset_csv, json_path=dataset_meta, metadata=build_metadata(dataset_df, rows=180, seed=12))

    output_json = tmp_path / "reports" / "ml_synthetic_benchmark_report.json"
    output_md = tmp_path / "reports" / "ml_synthetic_benchmark_report.md"

    run_synthetic_benchmark(dataset_csv=dataset_csv, output_json=output_json, output_md=output_md)

    payload = json.loads(output_json.read_text())
    assert payload["warning"] == SYNTHETIC_WARNING
    md_text = output_md.read_text()
    assert SYNTHETIC_WARNING in md_text


def test_synthetic_report_does_not_overwrite_real_supabase_reports(tmp_path):
    dataset_df = generate_synthetic_benchmark(rows=200, seed=4)
    dataset_csv = tmp_path / "synthetic.csv"
    dataset_meta = tmp_path / "synthetic.json"
    save_outputs(dataset_df, csv_path=dataset_csv, json_path=dataset_meta, metadata=build_metadata(dataset_df, rows=200, seed=4))

    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    real_json = reports_dir / "ml_reliability_audit.json"
    real_md = reports_dir / "ml_reliability_audit.md"
    real_json.write_text("REAL_SUPABASE_REPORT")
    real_md.write_text("REAL_SUPABASE_REPORT_MD")

    output_json = reports_dir / "ml_synthetic_benchmark_report.json"
    output_md = reports_dir / "ml_synthetic_benchmark_report.md"

    run_synthetic_benchmark(dataset_csv=dataset_csv, output_json=output_json, output_md=output_md)

    assert real_json.read_text() == "REAL_SUPABASE_REPORT"
    assert real_md.read_text() == "REAL_SUPABASE_REPORT_MD"
    assert output_json.exists()
    assert output_md.exists()

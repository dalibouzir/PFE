from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.build_literature_benchmark_dataset import BENCHMARK_MARKER, build_dataset
from scripts.evaluate_literature_benchmark import run_literature_benchmark


REQUIRED_COLUMNS = {
    "batch_id",
    "cooperative_id",
    "product",
    "process_type",
    "stage_canonical",
    "qty_in",
    "qty_out",
    "batch_size",
    "stock_level",
    "date",
    "source_marker",
}


def test_build_literature_benchmark_dataset_outputs_required_files(tmp_path):
    csv_path = tmp_path / "literature_benchmark_dataset.csv"
    metadata_path = tmp_path / "literature_benchmark_metadata.json"
    methodology_path = tmp_path / "literature_benchmark_methodology.md"

    metadata = build_dataset(
        output_csv=csv_path,
        output_metadata=metadata_path,
        output_methodology=methodology_path,
        target_rows=3000,
        seed=42,
    )

    assert csv_path.exists()
    assert metadata_path.exists()
    assert methodology_path.exists()
    assert (tmp_path / "benchmark_sources.json").exists()
    assert (tmp_path / "benchmark_sources.md").exists()

    df = pd.read_csv(csv_path)
    assert len(df) >= 3000
    assert REQUIRED_COLUMNS.issubset(df.columns)
    assert set(df["product"].unique()) == {"Mangue", "Arachide", "Mil"}
    assert set(df["process_type"].unique()) == {"Nettoyage", "Séchage", "Tri", "Emballage"}
    assert set(df["source_marker"].unique()) == {BENCHMARK_MARKER}

    risk = metadata["risk_distribution"]
    assert risk.get("low", 0) > 0
    assert risk.get("medium", 0) > 0
    assert risk.get("high", 0) > 0


def test_evaluate_literature_benchmark_generates_reports(tmp_path):
    csv_path = tmp_path / "literature_benchmark_dataset.csv"
    build_dataset(
        output_csv=csv_path,
        output_metadata=tmp_path / "literature_benchmark_metadata.json",
        output_methodology=tmp_path / "literature_benchmark_methodology.md",
        target_rows=3000,
        seed=42,
    )

    output_json = tmp_path / "literature_benchmark_evaluation.json"
    output_md = tmp_path / "literature_benchmark_evaluation.md"
    comparison_md = tmp_path / "literature_benchmark_comparison.md"
    current_demo = tmp_path / "missing_demo.json"

    report = run_literature_benchmark(
        dataset_csv=csv_path,
        output_json=output_json,
        output_md=output_md,
        comparison_md=comparison_md,
        current_demo_report=current_demo,
        target_rows=3000,
        seed=42,
    )

    assert output_json.exists()
    assert output_md.exists()
    assert comparison_md.exists()

    payload = json.loads(output_json.read_text())
    assert payload["predictive_contract"]["predictive_features_clean"] is True
    assert payload["predictive_contract"]["regression_violations"] == []
    assert payload["predictive_contract"]["classification_violations"] == []

    assert "evaluation" in payload
    assert "time_based" in payload["evaluation"]
    assert "baselines" in payload["evaluation"]["time_based"]["regression"]
    assert payload["evaluation"]["time_based"]["anomaly_review"]["anomaly_accuracy_reported"] is False

    md = output_md.read_text()
    assert "does not represent real cooperative operational accuracy" in md.lower()

    comparison = comparison_md.read_text()
    assert "proof of production accuracy? NO" in comparison

    assert report["dataset"]["row_count"] >= 3000

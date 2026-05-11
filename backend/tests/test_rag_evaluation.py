from pathlib import Path
import subprocess
import json

from app.services.rag_evaluation import (
    EvaluationScenario,
    chunk_diversity_score,
    evaluate_scenario_result,
    freshness_score,
    grounding_score,
    retrieval_relevance_score,
    sql_alignment_score,
)


def test_evaluation_metric_ranges():
    assert 0.0 <= retrieval_relevance_score([0.1, 0.3, 0.5]) <= 1.0
    assert 0.0 <= grounding_score(0.8, 1) <= 1.0
    assert 0.0 <= freshness_score(30) <= 1.0
    assert 0.0 <= sql_alignment_score(True, True, 0) <= 1.0
    assert 0.0 <= chunk_diversity_score(2, 3) <= 1.0


def test_evaluate_scenario_result_produces_expected_keys():
    scenario = EvaluationScenario(
        question="why are drying losses high this week for mango?",
        expected_chunk_types=["process_step_summary", "recommendation_context"],
        expected_sql_usage=True,
    )
    payload = {
        "retrieval_plan": {"sql_needed": True},
        "filters": {"stage_canonical": {"drying"}},
        "retrieval_diagnostics": {
            "hit_count": 2,
            "freshness": {"freshness_avg_minutes": 40},
            "chunk_diversity": {"chunk_type_unique_count": 2, "source_table_unique_count": 2},
        },
        "orchestration": {
            "warning_flags": [],
            "confidence_estimate": {"score": 0.82, "label": "HIGH"},
            "contradictory_signals": [],
        },
        "hits": [
            {
                "chunk_type": "process_step_summary",
                "source_table": "process_steps",
                "source_record_ref": "process_step:1",
                "retrieval_score": 0.42,
                "retrieval_reason": "chunk_type_boost",
            },
            {
                "chunk_type": "recommendation_context",
                "source_table": "recommendations",
                "source_record_ref": "recommendation:1",
                "retrieval_score": 0.36,
                "retrieval_reason": "freshness_boost",
            },
        ],
    }
    metrics = evaluate_scenario_result(scenario=scenario, debug_payload=payload)
    for key in (
        "retrieval_relevance_score",
        "grounding_score",
        "freshness_score",
        "citation_quality_score",
        "contradiction_rate",
        "SQL_alignment_score",
        "chunk_diversity_score",
        "expected_chunk_coverage",
        "scope_purity_score",
        "contamination_rate",
        "product_alignment_score",
        "stage_alignment_score",
        "operational_priority_score",
    ):
        assert key in metrics
    assert metrics["expected_chunk_coverage"] == 1.0


def test_benchmark_script_generates_reports():
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    cmd = ["../.venv/bin/python", "scripts/rag_benchmark.py"]
    completed = subprocess.run(cmd, cwd=backend_dir, check=True, capture_output=True, text=True)
    assert completed.returncode == 0
    assert (backend_dir / "artifacts" / "rag_benchmark_report.json").exists()
    assert (backend_dir / "artifacts" / "rag_benchmark_report.md").exists()


def test_healthcheck_script_runs_and_outputs_core_fields():
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    cmd = ["../.venv/bin/python", "scripts/rag_metadata_healthcheck.py"]
    completed = subprocess.run(cmd, cwd=backend_dir, check=True, capture_output=True, text=True)
    assert completed.returncode == 0
    payload = completed.stdout.strip()
    assert payload
    assert "\"total_chunks\"" in payload
    assert "\"chunks_with_chunk_type\"" in payload
    assert "\"chunks_with_freshness_timestamp\"" in payload


def test_benchmark_scenarios_define_expected_chunk_types():
    from scripts.rag_benchmark import _scenarios

    scenarios = _scenarios()
    assert scenarios
    assert any(item.expected_chunk_types for item in scenarios)
    assert all(item.expected_chunk_types or item.expected_sql_usage for item in scenarios)


def test_benchmark_scenario_expected_chunk_coverage_positive_when_reference_hits_present():
    scenario = EvaluationScenario(
        question="what does benchmark say about millet losses?",
        expected_chunk_types=["benchmark_reference", "agronomic_knowledge"],
        expected_sql_usage=False,
    )
    payload = {
        "retrieval_plan": {"sql_needed": False},
        "filters": {"chunk_type": {"benchmark_reference", "agronomic_knowledge"}},
        "retrieval_diagnostics": {
            "hit_count": 2,
            "freshness": {"freshness_avg_minutes": 10},
            "chunk_diversity": {"chunk_type_unique_count": 2, "source_table_unique_count": 2},
        },
        "orchestration": {"warning_flags": [], "confidence_estimate": {"score": 0.9}, "contradictory_signals": []},
        "hits": [
            {
                "chunk_type": "benchmark_reference",
                "source_table": "reference_metrics",
                "source_record_ref": "reference_metric:1",
                "retrieval_score": 0.6,
                "retrieval_reason": "chunk_type_boost",
            },
            {
                "chunk_type": "agronomic_knowledge",
                "source_table": "knowledge_chunks",
                "source_record_ref": "knowledge_chunk:1",
                "retrieval_score": 0.58,
                "retrieval_reason": "chunk_type_boost",
            },
        ],
    }
    metrics = evaluate_scenario_result(scenario=scenario, debug_payload=payload)
    assert metrics["expected_chunk_coverage"] > 0.0


def test_scope_metrics_capture_contamination():
    scenario = EvaluationScenario(
        question="why are mango drying losses high compared with bissap?",
        expected_chunk_types=["process_step_summary"],
        expected_sql_usage=True,
    )
    payload = {
        "retrieval_plan": {"sql_needed": True},
        "filters": {"product_name": {"mango"}, "stage_canonical": {"drying"}},
        "retrieval_diagnostics": {
            "hit_count": 2,
            "freshness": {"freshness_avg_minutes": 8},
            "chunk_diversity": {"chunk_type_unique_count": 1, "source_table_unique_count": 1},
            "scope": {
                "scope_purity_score": 0.5,
                "contamination_rate": 0.5,
                "product_alignment_score": 0.5,
                "stage_alignment_score": 1.0,
                "operational_priority_score": 1.0,
            },
        },
        "orchestration": {"warning_flags": ["SCOPE_CONTAMINATION_RISK"], "confidence_estimate": {"score": 0.4}, "contradictory_signals": []},
        "hits": [
            {"chunk_type": "process_step_summary", "source_table": "process_steps", "source_record_ref": "a", "retrieval_score": 0.4, "retrieval_reason": "scope_match_boost"},
            {"chunk_type": "process_step_summary", "source_table": "process_steps", "source_record_ref": "b", "retrieval_score": 0.3, "retrieval_reason": "unrelated_product_penalty"},
        ],
    }
    metrics = evaluate_scenario_result(scenario=scenario, debug_payload=payload)
    assert metrics["contamination_rate"] > 0.0
    assert metrics["scope_purity_score"] < 1.0


def test_seed_reference_knowledge_script_is_idempotent_and_creates_rows():
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    cmd = ["../.venv/bin/python", "scripts/seed_reference_knowledge.py"]

    first = subprocess.run(cmd, cwd=backend_dir, check=True, capture_output=True, text=True)
    first_payload = json.loads(first.stdout)
    assert first_payload["knowledge_chunks"]["total"] >= 12
    assert first_payload["reference_metrics"]["total"] >= 12

    second = subprocess.run(cmd, cwd=backend_dir, check=True, capture_output=True, text=True)
    second_payload = json.loads(second.stdout)
    assert second_payload["knowledge_chunks"]["inserted"] == 0
    assert second_payload["reference_metrics"]["inserted"] == 0
    assert second_payload["knowledge_chunks"]["total"] >= 12
    assert second_payload["reference_metrics"]["total"] >= 12


def test_seed_reference_knowledge_coverage_lists_expected_crops():
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    completed = subprocess.run(
        ["../.venv/bin/python", "scripts/seed_reference_knowledge.py"],
        cwd=backend_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    crops = set(payload["coverage"]["crops"])
    assert {"Mil", "Mangue", "Arachide"} <= crops

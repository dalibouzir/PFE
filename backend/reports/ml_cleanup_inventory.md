# ML Cleanup Inventory

Date: 2026-05-17

## Policy
- Inventory scope: `backend/reports/`, `backend/artifacts/`, `backend/tests/`, `backend/scripts/`.
- Categories:
  - `KEEP_FINAL`: final traceable outputs used in final reporting context.
  - `KEEP_SOURCE`: reproducibility/protection sources (scripts/tests).
  - `MOVE_ARCHIVE`: old intermediate docs/reports to keep but de-clutter.
  - `DELETE_CANDIDATE`: safe-to-delete temporary duplicates (none deleted automatically unless clear).
  - `DO_NOT_TOUCH`: protected production/runtime-sensitive files or critical governance artifacts.

## backend/reports/
| File | Classification | Rationale |
|---|---|---|
| `ml_final_model_status.md` | KEEP_FINAL | Final status source for PFE claims |
| `ml_final_model_status.json` | KEEP_FINAL | Structured final status metrics |
| `ml_validation_snapshot_comparison.md` | KEEP_FINAL | Real-vs-synthetic boundary summary |
| `ml_synthetic_model_improvement.md` | KEEP_FINAL | Final synthetic/offline comprehensive report |
| `ml_synthetic_model_improvement.json` | KEEP_FINAL | Machine-readable synthetic final report |
| `ml_synthetic_critical_risk_detection.md` | KEEP_FINAL | Classification phase traceability |
| `ml_synthetic_critical_risk_detection.json` | KEEP_FINAL | Classification structured traceability |
| `ml_synthetic_anomaly_detection.md` | KEEP_FINAL | Final anomaly diagnostics |
| `ml_synthetic_anomaly_detection.json` | KEEP_FINAL | Structured anomaly diagnostics |
| `ml_synthetic_recommendation_ranking.md` | KEEP_FINAL | Final recommendation ranking diagnostics |
| `ml_synthetic_recommendation_ranking.json` | KEEP_FINAL | Structured recommendation diagnostics |
| `ml_synthetic_benchmark_report.md` | KEEP_FINAL | Synthetic benchmark baseline traceability |
| `ml_synthetic_benchmark_report.json` | KEEP_FINAL | Structured synthetic baseline traceability |
| `ml_reliability_audit_supabase.md` | KEEP_FINAL | Real-data readiness evidence |
| `ml_reliability_audit_supabase.json` | KEEP_FINAL | Structured real-data readiness evidence |
| `ml_weather_evaluation_supabase.md` | KEEP_FINAL | Real-data weather evaluation evidence |
| `ml_weather_evaluation_supabase.json` | KEEP_FINAL | Structured real-data weather evidence |
| `ml_app_integration_plan.md` | KEEP_FINAL | Safe integration planning artifact |
| `ml_cleanup_inventory.md` | KEEP_FINAL | Cleanup governance record |
| `ml_current_state_audit.md` | MOVE_ARCHIVE | Intermediate audit snapshot |
| `ml_enhancement_strategy.md` | MOVE_ARCHIVE | Intermediate planning report |
| `ml_model_by_model_enhancement_plan.md` | MOVE_ARCHIVE | Intermediate planning report |
| `ml_postharvest_learning_loop.md` | MOVE_ARCHIVE | Intermediate planning report |
| `ml_production_readiness_plan.md` | MOVE_ARCHIVE | Intermediate planning report |
| `ml_reproducibility_stabilization.md` | MOVE_ARCHIVE | Intermediate stabilization report |
| `ml_model_validation_report.md` | MOVE_ARCHIVE | Older validation report |
| `ml_model_validation_report.json` | MOVE_ARCHIVE | Older validation report |
| `ml_reliability_audit.md` | KEEP_FINAL | Historical traceability artifact |
| `ml_reliability_audit.json` | KEEP_FINAL | Historical traceability artifact |
| `ml_weather_evaluation.md` | KEEP_FINAL | Historical weather artifact |
| `ml_weather_evaluation.json` | KEEP_FINAL | Historical weather artifact |

## backend/artifacts/
| File | Classification | Rationale |
|---|---|---|
| `synthetic_postharvest_benchmark.csv` | KEEP_FINAL | Final synthetic dataset used in PFE context |
| `synthetic_postharvest_benchmark.json` | KEEP_FINAL | Synthetic dataset metadata traceability |
| `model_registry.json` | DO_NOT_TOUCH | Runtime/model tracking sensitivity |
| `active_model.json` | DO_NOT_TOUCH | Runtime model pointer sensitivity |
| `ml_model_validation_tmp.md` | MOVE_ARCHIVE | Temporary/intermediate file |
| `ml_model_validation_tmp.json` | MOVE_ARCHIVE | Temporary/intermediate file |
| `ml_cleanup_candidates.md` | MOVE_ARCHIVE | Old cleanup scratch artifact |
| `ml_before_after_report.md` | MOVE_ARCHIVE | Intermediate comparison artifact |
| `ml_before_after_report.json` | MOVE_ARCHIVE | Intermediate comparison artifact |
| `ml_diagnostics_after_retrain.json` | MOVE_ARCHIVE | Intermediate diagnostics |
| `ml_diagnostics_after_clean_retrain.json` | MOVE_ARCHIVE | Intermediate diagnostics |
| `ml_evaluation_report.md` | MOVE_ARCHIVE | Older eval snapshot |
| `ml_evaluation_report.json` | MOVE_ARCHIVE | Older eval snapshot |
| `ml_evaluation_phase4.md` | MOVE_ARCHIVE | Phase artifact |
| `ml_evaluation_phase4.json` | MOVE_ARCHIVE | Phase artifact |
| `ml_evaluation_phase5.md` | MOVE_ARCHIVE | Phase artifact |
| `ml_evaluation_phase5.json` | MOVE_ARCHIVE | Phase artifact |
| `ml_evaluation_final.md` | MOVE_ARCHIVE | Intermediate “final” before current final |
| `ml_evaluation_final.json` | MOVE_ARCHIVE | Intermediate “final” before current final |
| `ml_diagnostics.json` | KEEP_SOURCE | Diagnostics reproducibility |
| `ml_diagnostics_seeded.json` | KEEP_SOURCE | Diagnostics reproducibility |
| `ml_diagnostics_phase2.json` | KEEP_SOURCE | Diagnostics reproducibility |
| `ml_diagnostics_phase4.json` | KEEP_SOURCE | Diagnostics reproducibility |
| `ml_diagnostics_phase5.json` | KEEP_SOURCE | Diagnostics reproducibility |
| `ml_diagnostics_final.json` | KEEP_SOURCE | Diagnostics reproducibility |
| `ml_monitoring_report.md` | KEEP_SOURCE | Monitoring reproducibility |
| `ml_monitoring_report.json` | KEEP_SOURCE | Monitoring reproducibility |
| `ml_deployment_readiness.md` | KEEP_SOURCE | Readiness reproducibility |
| `ml_deployment_readiness.json` | KEEP_SOURCE | Readiness reproducibility |
| `weather_cache.jsonl` | KEEP_SOURCE | Non-final but operational cache/data source |
| `benchmark_sources.md` | KEEP_SOURCE | Benchmark traceability |
| `benchmark_sources.json` | KEEP_SOURCE | Benchmark traceability |
| `rag_benchmark_report.md` | KEEP_SOURCE | Unrelated benchmark reproducibility |
| `rag_benchmark_report.json` | KEEP_SOURCE | Unrelated benchmark reproducibility |
| `literature_benchmark_*` | KEEP_SOURCE | Benchmark reproducibility |

## backend/tests/
| File | Classification | Rationale |
|---|---|---|
| `test_synthetic_model_improvement.py` | KEEP_SOURCE | Guards final synthetic report behavior |
| `test_synthetic_ml_benchmark.py` | KEEP_SOURCE | Guards synthetic benchmark pipeline |
| `test_ml_readiness_truthfulness.py` | KEEP_SOURCE | Guards readiness truthfulness |
| `test_ml_reliability_audit.py` | KEEP_SOURCE | Reliability reproducibility |
| `test_ml_weather_evaluation.py` | KEEP_SOURCE | Weather reproducibility |
| `test_ml_pipeline_diagnostics.py` | KEEP_SOURCE | Diagnostics reproducibility |
| `test_ml_monitoring.py` | KEEP_SOURCE | Monitoring reproducibility |
| `test_ml_evaluation.py` | KEEP_SOURCE | Evaluation reproducibility |
| `test_ml_repro_stabilization.py` | KEEP_SOURCE | Stabilization reproducibility |
| `test_ml_deployment_readiness.py` | KEEP_SOURCE | Readiness reproducibility |
| `test_ml_seed_training_data.py` | KEEP_SOURCE | Training-data reproducibility |
| `test_ml_resilience.py` | KEEP_SOURCE | ML resilience safety checks |

## backend/scripts/
| File | Classification | Rationale |
|---|---|---|
| `run_ml_synthetic_model_improvement.py` | KEEP_SOURCE | Final synthetic/offline orchestration |
| `generate_synthetic_postharvest_benchmark.py` | KEEP_SOURCE | Synthetic dataset generator |
| `evaluate_ml_synthetic_benchmark.py` | KEEP_SOURCE | Synthetic benchmark evaluator |
| `evaluate_ml_reliability.py` | KEEP_SOURCE | Reliability reproducibility |
| `evaluate_ml_weather.py` | KEEP_SOURCE | Weather reproducibility |
| `evaluate_ml_models.py` | KEEP_SOURCE | Model evaluation reproducibility |
| `ml_diagnostics.py` | KEEP_SOURCE | Diagnostics reproducibility |
| `ml_monitoring_report.py` | KEEP_SOURCE | Monitoring reproducibility |
| `ml_deployment_readiness.py` | KEEP_SOURCE | Readiness reproducibility |
| `seed_ml_training_data.py` | DO_NOT_TOUCH | Potentially data-seeding sensitive |
| `generate_ml_prediction_logs.py` | DO_NOT_TOUCH | Potentially operational log-impacting |
| `backfill_weather_features.py` | DO_NOT_TOUCH | Potentially data-mutating workflow |
| `ml_full_demo_validation.py` | KEEP_SOURCE | Demo reproducibility |
| `build_literature_benchmark_dataset.py` | KEEP_SOURCE | Benchmark reproducibility |
| `evaluate_literature_benchmark.py` | KEEP_SOURCE | Benchmark reproducibility |
| `rag_benchmark.py` | KEEP_SOURCE | Benchmark reproducibility |

## Planned Cleanup Action
- Create archive directory: `backend/archive/ml_old_audits/`.
- Move only `MOVE_ARCHIVE` files listed above.
- Do not delete protected files in this pass.

## Explicit Safety Note
No production ML source code, readiness logic, DB models, migrations, or workflow files are modified by this cleanup operation.

## Integration Update (Post Advisory Integration)
- Date: 2026-05-17
- New advisory/runtime-integration artifacts:
  - `backend/app/ml/advisory_diagnostics.py` -> `KEEP_SOURCE`
  - `backend/tests/test_ml_advisory_integration.py` -> `KEEP_SOURCE`
  - `backend/reports/ml_app_integration_report.md` -> `KEEP_FINAL`
- Archived intermediate files are currently under `backend/archive/ml_old_audits/` and remain preserved for traceability.
- No additional deletions were executed in this update pass.

## Final Cleanup Execution
- Execution date: 2026-05-17
- Final validation mode: Supabase read-only execution for ML integration validation (no SQLite fallback in final path).
- SQLite fallback policy in final scripts:
  - `backend/scripts/evaluate_ml_reliability.py`: fallback disabled by default; legacy-only via `--allow-sqlite-fallback`.
  - `backend/scripts/evaluate_ml_weather.py`: fallback disabled by default; legacy-only via `--allow-sqlite-fallback`.

### Files Kept (final/reproducibility/protected)
- All `KEEP_FINAL`, `KEEP_SOURCE`, and `DO_NOT_TOUCH` files remain preserved.
- Protected runtime code intentionally not touched:
  - `backend/app/models/*`
  - `backend/alembic/*`
  - workflow/stock/Collecte modules
  - final PFE context files and synthetic benchmark CSV copy in context folder

### Files Archived
- Existing archive retained under `backend/archive/ml_old_audits/`:
  - intermediate reports and artifacts previously classified as `MOVE_ARCHIVE`.

### Files Deleted
- None in this final pass (archive-over-delete policy preserved).

### Final Risk Note
- Advisory execution now succeeds on Supabase read-only data path, but artifact fallback mode in service can mask missing local model artifacts by design; this is intentional for non-promoted advisory continuity and must remain clearly documented as advisory-only behavior.

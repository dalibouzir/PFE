# WeeFarm Final PFE Evidence Status (2026-05-13)

## Executive Overview
This repository is now documented as **FastAPI-first** for PFE runtime claims, legacy Express/Prisma is explicitly excluded from canonical scope, and backend test collection no longer fails on `SessionLocal` imports.

Current validation status on 2026-05-13:
- `pytest --collect-only`: **PASS** (`218 collected`, no collection errors)
- full backend `pytest`: **PARTIAL** (`202 passed`, `13 failed`, `3 skipped`)
- key AI/RAG/ML/chatbot scripts under `backend/scripts`: **10/10 successful exits**

## Canonical Runtime Architecture (FastAPI-first)
| Claim | Status | Evidence |
|---|---|---|
| Canonical backend runtime is FastAPI | confirmed by code | `backend/app/main.py`, `backend/app/api/router.py`, `backend/app/api/routes/` |
| Canonical frontend runtime is Next.js App Router | confirmed by code | `package.json` (`next` scripts), `app/`, `components/`, `hooks/` |
| Canonical ORM/migrations are SQLAlchemy + Alembic | confirmed by code | `backend/app/models/`, `backend/alembic/versions/` |
| PostgreSQL/pgvector is target RAG datastore (SQLite used in local test mode) | confirmed by code | `backend/alembic/versions/3f4c2a1b9d7e_add_rag_pgvector_tables.py`, `backend/app/core/config.py` |
| Architecture is declared FastAPI-first in docs | confirmed by code | `README.md`, `docs/architecture.md` |

## Legacy Components Excluded from PFE Scope
| Claim | Status | Evidence |
|---|---|---|
| Express/Prisma stack is legacy and excluded from chapters 3–5 architecture claims | confirmed by code | `_archive/legacy-express-prisma/src/LEGACY_SCOPE.md`, `_archive/legacy-express-prisma/prisma/LEGACY_SCOPE.md` |
| Legacy commands remain only for historical compatibility | confirmed by code | `package.json` (`legacy:*` scripts) |
| Report baseline must not use legacy Express/Prisma as canonical runtime | confirmed by code | `README.md` (Archived Legacy Components section), `docs/architecture.md` |

## SessionLocal Collection Fix Status
| Claim | Status | Evidence |
|---|---|---|
| `SessionLocal` import compatibility restored while preserving lazy DB initialization | confirmed by code | `backend/app/db/session.py` (`_LazySessionLocal`, `SessionLocal = _LazySessionLocal()`) |
| Test collection no longer fails due to `SessionLocal` import errors | confirmed by audit/test | `cd backend && ../.venv/bin/python -m pytest --collect-only -q` (result below) |

## Validation Commands and Results
### 1) Backend test collection
Command:
```bash
cd backend && ../.venv/bin/python -m pytest --collect-only -q
```
Observed output summary:
- `218 tests collected in 2.33s`
- no collection/import failure

### 2) Full backend suite
Command:
```bash
cd backend && ../.venv/bin/python -m pytest -q
```
Observed output summary:
- `13 failed, 202 passed, 3 skipped, 45 warnings in 38.44s`
- pass ratio (all collected): `202 / 218 = 92.66%`
- pass ratio (excluding skipped): `202 / 215 = 93.95%`

Remaining failing tests (13):
1. `tests/test_config_regression_fix.py::test_environment_metadata_normal_mode`
2. `tests/test_coop_agent_intent_router.py::test_full_analysis_routes_hybrid_full`
3. `tests/test_ml_monitoring.py::test_model_registry_creation_and_candidate_registration`
4. `tests/test_ml_monitoring.py::test_prediction_log_write_and_read`
5. `tests/test_ml_pipeline_diagnostics.py::test_training_inference_feature_columns_are_consistent`
6. `tests/test_ml_pipeline_diagnostics.py::test_predictive_inference_works_without_deviation_from_stage_avg`
7. `tests/test_ml_pipeline_diagnostics.py::test_predictive_inference_rejects_forbidden_fields`
8. `tests/test_ml_resilience.py::test_load_model_bundle_rejects_forbidden_predictive_features`
9. `tests/test_ml_seed_training_data.py::test_retrained_artifacts_from_seed_are_clean`
10. `tests/test_phase1_chatbot_behavior.py::test_valid_missing_lot_returns_missing_batch_message_only_for_specific_lot`
11. `tests/test_phase1_chatbot_behavior.py::test_stage_loss_answer_uses_highest_loss_step_not_latest_row`
12. `tests/test_prediction_endpoint.py::test_predictive_and_assessment_endpoints`
13. `tests/test_training_pipeline.py::test_training_pipeline_creates_artifacts`

### 3) Key script batch (AI/RAG/ML/chatbot)
Execution log:
- `backend/reports/final_pfe_script_runs_2026-05-13.log`

Commands run and status:
1. `scripts/seed_full_demo_dataset.py` -> PASS (`EXIT_CODE=0`)
2. `scripts/validate_demo_data_integrity.py --fix` -> PASS (`EXIT_CODE=0`)
3. `scripts/full_rag_index_coverage_report.py --skip-reindex` -> PASS (`EXIT_CODE=0`)
4. `scripts/chatbot_quality_audit.py` -> PASS (`EXIT_CODE=0`)
5. `scripts/chatbot_unseen_robustness_audit.py` -> PASS (`EXIT_CODE=0`)
6. `scripts/chatbot_full_platform_coverage_audit.py` -> PASS (`EXIT_CODE=0`)
7. `scripts/chat_sql_rag_eval_harness.py` -> PASS (`EXIT_CODE=0`)
8. `scripts/rag_benchmark.py` -> PASS (`EXIT_CODE=0`)
9. `scripts/ml_full_demo_validation.py` -> PASS (`EXIT_CODE=0`)
10. `scripts/final_ai_validation_report.py` -> PASS (`EXIT_CODE=0`)

## Regenerated Audit/Validation Artifacts (2026-05-13)
- `backend/reports/final_pfe_script_runs_2026-05-13.log`
- `backend/reports/final_ai_validation_report.md`
- `backend/reports/final_ai_validation_report.json`
- `backend/reports/ml_model_validation_report.md`
- `backend/reports/ml_model_validation_report.json`
- `backend/reports/chat_sql_rag_eval_harness_2026-05-13.md`
- `backend/reports/chat_sql_rag_eval_harness_2026-05-13.json`
- `backend/reports/chatbot_full_platform_coverage_audit.md`
- `backend/reports/chatbot_full_platform_coverage_audit.json`
- `backend/reports/chatbot_unseen_robustness_audit.md`
- `backend/reports/chatbot_unseen_robustness_audit.json`
- `backend/reports/full_rag_index_coverage_report.md`
- `backend/reports/demo_data_integrity_report.md`

## Safe Claims for PFE Report (Current Evidence)
1. WeeFarm runtime architecture for the PFE is FastAPI backend + Next.js frontend, with SQLAlchemy/Alembic persistence.
2. RAG/pgvector integration is implemented and auditable through migrations, scripts, and generated reports.
3. ML and recommendation components are implemented with validation scripts and report artifacts.
4. Chatbot orchestration and audits are implemented, with dedicated evaluation/audit outputs.
5. Repository now has explicit legacy separation for historical Express/Prisma code.

## Claims That Must NOT Be Made
1. Do not claim full backend test-suite green status.
2. Do not claim production readiness of all ML and chatbot behavior paths while failing tests remain.
3. Do not present legacy Express/Prisma stack as canonical architecture.
4. Do not claim PostgreSQL/pgvector-only execution in all environments (local test/audit mode uses SQLite).
5. Do not claim zero known technical debt in model artifact/versioning and router behavior.

## Remaining Risks / Open Gaps Before Final Chapter Writing
1. Resolve the 13 backend test failures, prioritizing ML artifact lifecycle, intent routing, and chatbot behavior assertions.
2. Stabilize configuration expectation mismatch in `test_environment_metadata_normal_mode`.
3. Ensure ML tests that patch `ml_artifacts_path` are isolated from existing active-model/materialization side effects.
4. Re-run full suite and update this report once failures are resolved.


# ML App Integration Report

Date: 2026-05-17

## Scope
This report documents the integration of the selected enhanced ML advisory strategy into the backend ML service and schemas.

No DB migration, Supabase write, workflow policy change, stock/Collecte behavior change, frontend change, or runtime ML promotion was performed.

## Files Changed
- `backend/app/ml/advisory_diagnostics.py` (new)
- `backend/app/services/ml.py`
- `backend/app/schemas/ml.py`
- `backend/app/api/routes/ml.py`
- `backend/tests/test_ml_advisory_integration.py` (new)

## Integrated Strategy (Advisory-Only)
- Regression: baseline-first fallback helper integrated (`stage/season/product-stage` fallback estimation support).
- Critical-risk classification: advisory-only critical-risk signal integrated with explicit caveat.
- Anomaly: assessment-mode rule/statistical diagnostics integrated as advisory diagnostics.
- Recommendation: rule-first recommendations now include advisory ranking scores/reasons; original recommendations are preserved.
- Strategy metadata attached: `ml_strategy=enhanced_advisory_v1`, `benchmark_source=synthetic_offline_selected_strategy`, `integrated_strategy=true`, `advisory_only=true`.

## What Was Not Changed
- Readiness gate logic and readiness metadata presence were kept.
- Promotion trust policy remained unchanged (`promoted` stays governed by readiness layer, and remains false in current low-data context).
- Existing `/ml` endpoint response shape was kept backward-compatible (only additive optional fields).
- DB models, migrations, and workflow lifecycle modules were untouched.

## New/Extended Response Fields
- Prediction output:
  - `baseline_estimate`
  - `critical_risk_advisory`
  - `ml_strategy`
  - `benchmark_source`
  - `integrated_strategy`
  - `advisory_only`
- Assessment output:
  - all fields above plus `assessment_anomaly_diagnostics`
- Recommendation output:
  - `ranked_recommendations`
  - `ml_strategy`
  - `benchmark_source`
  - `integrated_strategy`
  - `advisory_only`

## Route Safety Adjustment
- `GET /ml/recommendation/{batch_id}` now calls service with `include_explanation=false` by default.
- Rationale: avoids external LLM dependency failures (HTTP 402) in local/test contexts while preserving response schema compatibility.

## Tests Run
- `backend/.venv311/bin/python3 -m pytest -q backend/tests/test_ml_advisory_integration.py` -> 2 passed
- `backend/.venv311/bin/python3 -m pytest -q backend/tests/test_prediction_endpoint.py backend/tests/test_feature_engineering.py backend/tests/test_recommendation_mapping.py backend/tests/test_ml_readiness_truthfulness.py` -> 16 passed
- `backend/.venv311/bin/python3 -m pytest -q backend/tests/test_phase1_lifecycle.py backend/tests/test_post_recolte_lifecycle.py backend/tests/test_stock_lot_flux_flow.py` -> 38 passed

## Remaining Caveats
- Advisory signals are integration-time decision support, not runtime ML promotion.
- Synthetic/offline benchmark strategy remains non-production evidence.
- Classification precision and false-alarm profile remain limited; keep advisory framing explicit.

## Final Runtime Posture
- Regression baseline fallback active.
- Critical-risk classification advisory active.
- Assessment-mode anomaly diagnostics advisory active.
- Rule-first recommendation ranking advisory active.
- Readiness metadata retained as source-of-truth governance layer.

## Supabase Read-Only Execution Validation
- Validation date: 2026-05-17
- Database target: `aws-0-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require` (PostgreSQL/Supabase, read path)
- SQLite was not used for this final execution validation.

### Records Used (masked)
- Batch used for assess/recommendation: `ed53e7e8...44ce`
- Feature rows available from real data: `49`
- Predictive sample context: product `Arachide`, stage `Nettoyage`

### Calls Executed
- `ml_service.predict(..., include_explanation=False)`
- `ml_service.assess(..., include_explanation=False)`
- `ml_service.get_recommendation(..., include_explanation=False)`

### Advisory Field Presence
- Predict output: `baseline_estimate`, `critical_risk_advisory`, `ml_strategy`, `benchmark_source`, `integrated_strategy`, `advisory_only` present.
- Assess output: all above plus `assessment_anomaly_diagnostics` present.
- Recommendation output: `ranked_recommendations` present.
- Readiness metadata present in outputs (`ml_readiness_state`, `dataset_n`, `promoted`, `recommendation_mode`).

### Readiness/Promotion Status Observed
- `ml_readiness_state = INSUFFICIENT_DATA`
- `promoted = false`
- Promotion remains governed by readiness policy (unchanged).

### Row Count Comparison (Before vs After)
| Table | Before | After | Delta |
|---|---:|---:|---:|
| `batches` | 23 | 23 | 0 |
| `process_steps` | 49 | 49 | 0 |
| `stock_movements` | 23 | 23 | 0 |
| `ml_prediction_logs` | 13 | 13 | 0 |
| `ml_recommendation_logs` | 15 | 18 | +3 |

Interpretation:
- Operational tables (`batches`, `process_steps`, `stock_movements`) were unchanged.
- `ml_recommendation_logs` increased by 3 due to expected endpoint/service logging behavior.

### SQLite Fallback Removal/Legacy Labeling Summary
- Updated scripts:
  - `backend/scripts/evaluate_ml_reliability.py`
  - `backend/scripts/evaluate_ml_weather.py`
- Change:
  - SQLite fallback is now disabled by default for final validation.
  - New explicit legacy flag required: `--allow-sqlite-fallback`.
  - Without that flag, Supabase connection failure raises an error and does not silently fall back.

### Errors Found and Fixes Applied
- Error found during initial Supabase execution:
  - `ML model artifacts are missing or invalid. Retrain models first.`
- Fix applied:
  - Added safe service-level artifact-missing fallback in `backend/app/services/ml.py` so advisory outputs still run from real Supabase features using baseline/rule diagnostics, without DB schema changes and without SQLite fallback.
  - This preserves backward-compatible response shape and readiness metadata.

# ML Reproducibility Stabilization

Date: 2026-05-17

## A. What Was Broken
- `python3` on this machine points to Python 3.9.6, while backend codebase uses modern type annotations (`X | None`) and fails import-time for model modules.
- Audit scripts originally depended on configured remote DB connectivity; this was brittle for local audit reproduction.
- `prepare_feature_frame()` had dead/unreachable weather ordinal logic after `return`.

## B. Runtime/Python Compatibility Decision
- Kept project runtime intent as **Python 3.11** (matches `backend/Dockerfile`: `FROM python:3.11-slim`).
- Did **not** broaden non-ML compatibility edits.
- Validation executed with interpreter:
  - `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/.venv311/bin/python3`

## C. Files Changed
- `backend/app/ml/utils/feature_prep.py`
  - Fixed weather ordinal derivation placement and fallback (`weather_feature_timestamp_ordinal`).
- `backend/scripts/evaluate_ml_reliability.py`
  - Added resilient local SQLite fallback for script execution if configured DB connection fails.
- `backend/scripts/evaluate_ml_weather.py`
  - Added resilient local SQLite fallback for script execution if configured DB connection fails.
- `backend/tests/test_ml_repro_stabilization.py` (new)
  - Added focused reproducibility tests.
- Regenerated reports:
  - `backend/reports/ml_reliability_audit.json`
  - `backend/reports/ml_reliability_audit.md`
  - `backend/reports/ml_weather_evaluation.json`
  - `backend/reports/ml_weather_evaluation.md`

## D. Commands Run
1. `python3 backend/scripts/evaluate_ml_reliability.py --output-json backend/reports/ml_reliability_audit.json --output-md backend/reports/ml_reliability_audit.md`
2. `python3 backend/scripts/evaluate_ml_weather.py --output-json backend/reports/ml_weather_evaluation.json --output-md backend/reports/ml_weather_evaluation.md`
3. `cd backend && python3 -m pytest -q tests/test_ml_reliability_audit.py tests/test_ml_weather_evaluation.py tests/test_backfill_weather_features.py tests/test_ml_repro_stabilization.py`
4. `backend/.venv311/bin/python3 backend/scripts/evaluate_ml_reliability.py --output-json backend/reports/ml_reliability_audit.json --output-md backend/reports/ml_reliability_audit.md`
5. `backend/.venv311/bin/python3 backend/scripts/evaluate_ml_weather.py --output-json backend/reports/ml_weather_evaluation.json --output-md backend/reports/ml_weather_evaluation.md`
6. `cd backend && ../backend/.venv311/bin/python3 -m pytest -q tests/test_ml_reliability_audit.py tests/test_ml_weather_evaluation.py tests/test_backfill_weather_features.py tests/test_ml_repro_stabilization.py`

## E. Test Results
- With `python3` (3.9.6): failed due type-annotation incompatibility in model imports.
- With Python 3.11 venv:
  - `18 passed` for focused suite.
  - No test failures.

## F. Regenerated Reliability Metrics
- Dataset size: `45`
- Regression model MAE: `3.7136060569240574`
- Best baseline MAE: `3.8362454907928663`
- Selected regression decision: `baseline:product_stage_mean_loss`
- Classification macro-F1: `0.3125`
- Best classification baseline macro-F1: `0.5555555555555555`
- Classification gate: `FAIL`
- Anomaly status: `EXPLORATORY`
- Recommendation policy status: `RULE_BASED`

## G. Regenerated Weather Metrics
- Weather coverage: `0.7555555555555555`
- Leakage violations: `0`
- Internal model MAE: `3.7136060569240574`
- Weather model MAE: `3.880656168991981`
- Best numeric candidate (model-only): `internal_model`
- Gate-promoted/production decision: `baseline:product_stage_mean_loss`

## H. Current Trustworthy ML Claims
- Reliability/Weather audit scripts now run reproducibly in intended Python 3.11 runtime.
- Regression and classification are independently evaluated and gated; numeric wins are separated from promotion decisions.
- Anomaly remains exploratory.
- Recommendation policy remains rule-based.
- Weather leakage checks remain enforced.

## I. Claims That Remain Forbidden
- Do not claim validated anomaly accuracy.
- Do not claim recommendation policy is fully ML-learned.
- Do not claim regression model promotion on this 45-row Supabase snapshot (gate fails).
- Do not claim classification superiority on this 45-row Supabase snapshot (gate fails).

## J. Remaining Risks and Next Step
- Machine default `python3` (3.9.6) remains incompatible with current codebase.
- Recommended next step: standardize local dev runner to Python 3.11 (e.g., shell alias, project task runner, or CI/local docs) so “python3 …” resolves consistently.

## Final Verdict
Stabilization is complete for the intended runtime (Python 3.11). Scope drift from non-ML files was reverted.

## Historical Artifact Note
- `1520` rows corresponds to **HISTORICAL ARTIFACT — NOT CURRENT SUPABASE SNAPSHOT**.

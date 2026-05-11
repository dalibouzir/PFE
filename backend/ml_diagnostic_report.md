# ML Diagnostic Report

Generated on: 2026-05-07

## Executive summary

- The current ML stack is **not production-ready**.
- It is **MVP/demo-usable only with strict caveats** after retraining with the updated pipeline.
- Main blockers:
  - Very small live dataset (`5` rows in current DB snapshot from diagnostics).
  - Historical artifact mismatch: existing saved models were trained with a leakage-prone predictive feature (`deviation_from_stage_avg`).
  - Weak anomaly validation (no labeled anomalies; current metric is proxy-only).
  - Risk-class metrics are unstable due severe class sparsity/imbalance.

## Pipeline audit (end-to-end)

### 1) Training data fetch
- Source: SQL join over `ProcessStep -> Batch -> Product` plus `Stock` lookup by `(cooperative_id, product_id)`.
- File: `backend/app/ml/features/engineer.py`.
- Observed behavior:
  - Uses process-level rows as training examples.
  - Adds stock snapshot from current `Stock` table (not time-versioned), so this can drift from historical reality.

### 2) Feature building
- Temporal fields: `month`, `week_of_year`, `season`.
- History fields: expanding means and rolling previous batch trends.
- Recent hardening changes:
  - Added safe zero-division handling for `loss_pct` and `efficiency_pct`.
  - Replaced leak-prone NaN default fill (global target mean) with threshold-based priors.
  - Added `batch_id` and `cooperative_id` to feature frame for diagnostics traceability.

### 3) Label creation
- Regression target: `loss_pct`.
- Classification target: `risk_level = assign_risk_level(loss_pct)` using thresholds from config:
  - `step_loss_threshold=12.0`
  - `anomaly_loss_threshold=18.0`

### 4) Split strategy
- Previous: random row split only (contamination risk).
- Updated: time-based split by `date_ordinal` with random fallback.
- File: `backend/app/ml/training/trainer.py`.

### 5) Model training
- Loss regressor: `RandomForestRegressor(n_estimators=250)`.
- Risk classifier: `RandomForestClassifier(n_estimators=250)`.
- Anomaly: `IsolationForest(n_estimators=200, contamination=0.08)`.
- Pipelines include OneHot for categorical features.

### 6) Metrics
- Previous metrics were minimal and optimistic.
- Updated training metadata now stores:
  - Regression: MAE/RMSE/R2 + mean baseline MAE/RMSE
  - Classification: accuracy, macro-F1, weighted-F1, majority baseline accuracy, per-class PR/F1/support, confusion matrix
  - Split details

### 7) Artifact save/load
- Artifacts saved to `settings.ml_artifacts_path`.
- Metadata in `feature_metadata.json`.
- Inference loads model bundle via `load_model_bundle`.
- Consistency check now included in diagnostics script output.

### 8) Inference use
- Predictive mode uses only predictive feature set from metadata.
- Assessment mode computes/patches `loss_pct` and `efficiency_pct` if missing.
- Hardening fix: UUID-safe normalization in prediction logs.

## Serious ML issues found

1. **Historical target leakage in deployed artifacts**
- Existing `backend/artifacts/feature_metadata.json` still includes `deviation_from_stage_avg` inside predictive feature lists.
- That feature depends on `loss_pct` and is not valid pre-stage.
- Fixed in code for future training; **must retrain to purge old artifacts**.

2. **Tiny dataset = unstable/meaningless metrics**
- Current diagnostics dataset size: `5` rows.
- Time split test size: `1` row; R2 not defined.
- Any 1.0 accuracy/F1 under this setup is not reliable.

3. **Train/test contamination risk (previous implementation)**
- Previous random row split across process steps could mix correlated rows across train/test.
- Mitigated by time-based split in trainer.

4. **Anomaly evaluation is weak**
- Current anomaly metric is `ratio(score < 0)`; this is not ground-truth validation.
- No labeled anomaly set; contamination=0.08 is arbitrary.

5. **Risk class imbalance/sparsity**
- Current diagnostic snapshot class distribution: `low=4`, `high=1`, `medium=0`.
- Classifier per-class metrics are not trustworthy under this sparsity.

6. **Recommendation stage mapping fragility**
- Rule engine is mostly English-key based (`drying/sorting/cleaning/packaging`).
- Current data contains French stage names (`Nettoyage`, `Sechage`, `Tri`) -> often falls back to generic actions.

7. **Metric naming/unit inconsistency**
- `efficiency_pct` is represented as ratio `0..1` in several flows (not `0..100`), while name suggests percent.

## Model-by-model judgment

## Loss Regressor
- Target correctness: conceptually correct (`loss_pct`).
- Current reliability: **weak in production context** due tiny dataset + stale artifacts.
- Baseline comparison: now implemented; in current live snapshot, improvements are unstable and test-row-dependent.
- Random Forest suitability: acceptable for tabular non-linear baseline, but data volume is currently insufficient.
- Calibration/realism: no calibrated uncertainty; point estimates only.

## Risk Classifier
- Label generation: deterministic from loss thresholds; technically correct.
- Accuracy alone is misleading here due imbalance/tiny holdout.
- Added per-class precision/recall/F1 + confusion matrix in training metadata and diagnostics.
- Recommendation: if data remains small, derive risk directly from predicted loss thresholds instead of a separate classifier.

## Anomaly Detector
- IsolationForest usage is mechanically valid.
- Contamination fixed at `0.08` without empirical calibration.
- Current validation metric is not enough; no labeled anomalies.
- Recommendation: create weak labels from incident logs/manual reviews and evaluate precision@k / alert hit-rate.

## Recommendation Engine
- Current output is primarily **rule-based**, not ML-driven.
- Impact model path exists but is often unavailable/insufficiently trained.
- Stage-specific action quality is limited by stage naming mismatch and generic fallback.
- Future LLM explanation risk: overclaiming confidence if explanation is not explicitly tied to model signals and uncertainty.

## What is reliable now
- Artifact loading safeguards and metadata checks.
- Basic feature engineering pipeline with safer null/zero handling.
- Rule-based recommendation fallback always returns actions.
- Test coverage around feature math, no-division, feature consistency, and recommendation generation.

## What is weak now
- Statistical validity of metrics on current production-like data.
- Anomaly detection trustworthiness.
- Risk classifier generalization.
- Cross-lingual/stage-normalization robustness in recommendations.

## What is misleading in current metrics
- Perfect/near-perfect classification on tiny holdouts.
- R2 with <2 test rows.
- Anomaly ratio interpreted as model quality.
- `test_model_accuracy.py` risk check is case-mismatched (`LOW/MEDIUM/HIGH` vs `low/medium/high`), producing false 0% risk accuracy.

## MVP readiness vs production readiness

- **MVP-ready:** only as a guided decision-support demo with explicit “low confidence / limited data” disclaimer.
- **Production-ready:** **No**.

## Required fixes before report/demo

1. Retrain models immediately with updated pipeline (to remove predictive leakage feature from artifacts).
2. Expand training dataset significantly (target at least hundreds of diverse process rows, with all risk classes present).
3. Normalize/standardize stage taxonomy (`cleaning/drying/sorting/packaging` equivalents).
4. Present macro-F1, weighted-F1, per-class metrics, and baseline comparison in every demo dashboard.
5. Do not claim anomaly “accuracy” without labeled anomaly evaluation.

## Optional improvements after MVP

1. Add walk-forward (time-series) evaluation windows instead of single split.
2. Add probabilistic calibration for risk outputs.
3. Add anomaly triage feedback loop and alert precision@k monitoring.
4. Replace static contamination with adaptive thresholding by product/stage.
5. Standardize `efficiency_pct` semantics (rename to ratio or convert to actual percent).

## Exact files changed

- `backend/app/ml/features/engineer.py`
- `backend/app/ml/inference/predictor.py`
- `backend/app/ml/training/trainer.py`
- `backend/app/ml/utils/feature_prep.py`
- `backend/scripts/ml_diagnostics.py`
- `backend/tests/test_training_pipeline.py`
- `backend/tests/test_ml_pipeline_diagnostics.py`
- `backend/artifacts/ml_diagnostics.json`

## Reproducible commands

```bash
cd backend
python3 -m pytest -q \
  tests/test_feature_engineering.py \
  tests/test_training_pipeline.py \
  tests/test_recommendation_mapping.py \
  tests/test_ml_resilience.py \
  tests/test_ml_pipeline_diagnostics.py
```

```bash
cd backend
python3 scripts/ml_diagnostics.py --output artifacts/ml_diagnostics.json
cat artifacts/ml_diagnostics.json
```

Optional comparison script (known limitations, currently still misleading for risk case labels):
```bash
cd backend
python3 test_model_accuracy.py
```

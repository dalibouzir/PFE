# WeeFarm ML Model-by-Model Enhancement Plan

Date: 2026-05-17
Scope: Planning and audit only (no runtime, DB, workflow, or model artifact changes)

## A. Executive Verdict
- Real-data readiness remains non-promoted and must stay the production source of truth.
- Synthetic benchmark is useful for controlled diagnostics only and must remain explicitly non-production.
- Current strongest ML signal candidate is classification (macro-F1 above majority baseline), but critical-risk detection is still weak.
- Current weakest ML components are regression (loses to simple stage baseline) and anomaly detection (near-random against synthetic labels).
- Recommendation engine should remain rule-first; ranking can be added later as assistive scoring only.

## B. Current Real-Data Readiness Status
- Real snapshot status (from `backend/reports/ml_validation_snapshot_comparison.md`):
  - Rows: 45 (user context also reports ~49 process-step rows).
  - Regression gate: FAIL.
  - Classification gate: FAIL.
  - Weather model did not beat internal numeric model.
  - Recommendation policy: RULE_BASED.
- Readiness policy (`backend/app/ml/readiness.py`) keeps non-promoted behavior until dataset and model gates pass.
- Dataset thresholds are explicit:
  - very low under 100 rows
  - reliable candidate from 500
  - production candidate from 1000

## C. Synthetic Benchmark Results (Controlled, Separate)
- Source artifacts:
  - `backend/artifacts/synthetic_postharvest_benchmark.csv`
  - `backend/reports/ml_synthetic_benchmark_report.json`
- Time split:
  - Regression MAE model: 3.6455
  - Best baseline MAE: 2.6350 (`stage_mean_loss`) -> model does not beat best baseline
  - Classification macro-F1: 0.5977 vs majority 0.2773
  - Anomaly precision/recall/F1: 0.0189 / 0.0345 / 0.0244
- Random split:
  - Regression MAE model: 2.9585
  - Best baseline MAE: 2.6862 (`stage_mean_loss`) -> model does not beat best baseline
  - Classification macro-F1: 0.6140
- Boundary remains mandatory: synthetic metrics are not production metrics and not used for promotion.

## D. Regression Diagnosis and Plan
### Diagnosis (Why regression loses to `stage_mean_loss`)
- Top likely causes (with evidence):
  1. Stage dominates target structure.
  - Synthetic generator sets stage-specific base losses (`_base_stage_loss`) and stage-conditioned rules.
  - Stage explains large variance in `loss_pct` (eta^2 ~= 0.4337 on synthetic data).
  - Top feature importance is `stage_sechage` (~0.398).
  2. Baseline is near the generator’s primary signal.
  - `stage_mean_loss` matches core signal and outperforms model on both time and random splits.
  3. Global model is not specialized enough for stage regimes.
  - Highest model MAE is on `sechage` (5.0039), where rule complexity is highest.
  4. Noise/anomaly shock level increases irreducible error.
  - Generator injects Gaussian noise plus random shock anomalies; baseline means remain robust.
  5. Time split can leak lot continuity across boundary.
  - Split is date-based and had 2 overlapping lot IDs across train/test in this snapshot.
  - This does not explain underperformance alone, but it weakens evaluation isolation.

### Baseline policy conclusion
- Do not hard-replace with `product_stage_mean_loss` now.
- Keep a baseline basket and always compare against the best of:
  - `stage_mean_loss`
  - `product_stage_mean_loss`
  - (optionally) `stage_season_mean_loss` when season signal is stable.

### Recommended regression redesign (no implementation yet)
- Candidate family:
  - keep RandomForestRegressor as reference
  - add HistGradientBoostingRegressor and GradientBoostingRegressor
  - keep stage/product-stage baselines as mandatory competitors
- Architecture:
  - Evaluate stage-specific models (especially `sechage`) vs one global model.
  - Evaluate residual modeling: baseline prediction + model on residual.
- Feature direction:
  - Add explicit interactions for stage-sensitive regimes:
  - humidity x stage, rainfall x stage, duration x stage, delay x product.
- Evaluation gate (proposed):
  - Primary: time split MAE must beat best baseline by >=10%.
  - Secondary: `sechage` segment MAE must also beat segment baseline.
  - If either fails: keep baseline in production recommendation context.

## E. Classification Diagnosis and Plan
### What works now
- Macro-F1 clearly exceeds majority baseline (0.5977 vs 0.2773 time split).
- Medium class is learned reasonably well (time split medium F1 ~0.8466).

### What is weak
- High-risk class recall is 0.0 in both time and random splits.
- Confusion on time split (`low, medium, high` rows):
  - `[[274, 8, 0], [10, 80, 1], [13, 10, 0]]`
  - all true high-risk cases are missed (predicted low/medium).
- Current risk labels are global thresholds (`>=8 medium`, `>=18 high`) and not product-stage specific.

### Recommended classification redesign (no implementation yet)
- Model candidates:
  - keep RandomForestClassifier baseline
  - add LogisticRegression baseline
  - add HistGradientBoostingClassifier
  - add calibrated variant (CalibratedClassifierCV)
- Label/threshold plan:
  - maintain global thresholds for governance continuity, but evaluate product-stage threshold overlays for analysis.
- Imbalance handling:
  - test class-weighted training (`class_weight=balanced`) and threshold tuning for high-risk recall.
- Success metrics:
  - macro-F1
  - high-risk recall (priority metric)
  - high-risk precision
  - false-low rate for true high-risk
  - calibration error (ECE/Brier) for high-risk probability
- Gate suggestion:
  - require non-zero high-risk recall before any ML-assisted escalation claims.

## F. Anomaly Diagnosis and Plan
### Why IsolationForest fails in current synthetic setup
- Synthetic anomaly labels are injected by adding shocks to `loss_pct` in generator.
- Synthetic evaluator anomaly model does not include `loss_pct`, `qty_out`, or `loss_qty` features.
- Therefore, anomaly labels are only weakly observable from model inputs; low precision/recall is expected.
- Empirical time split counts: 1 TP, 52 FP, 28 FN (support 29 positives).

### Recommended hybrid anomaly strategy
1. Rule anomalies (primary):
- impossible quantity transitions
- extreme loss bands by stage
- timestamp/duration consistency violations
2. Statistical outliers by product-stage (secondary):
- z-score/IQR/robust MAD on `loss_pct`, duration, and delay by product-stage
3. Supervised anomaly classifier (conditional):
- only for datasets with reliable anomaly labels
- synthetic-only benchmark acceptable for R&D comparison, not production claims

### Success metrics
- Precision@K for operator triage
- Top-decile capture rate of true severe events
- False alert rate per 100 steps
- For labeled experiments only: PR-AUC and recall at fixed precision

## G. Recommendation Ranking Plan
### Recommendation mode now
- Rule-first action generation remains correct and must not change.
- Any ML signal is assistive context, not autonomous action selection.

### Future ranking design (safe)
- Keep rule engine generating allowed actions.
- Add a ranking score per action using:
  - predicted risk
  - predicted loss severity
  - stage criticality
  - weather/duration sensitivity
  - historical recurrence of similar issue
  - evidence quality/confidence score

### Feedback data needed (for future learned ranking)
- recommended_action_id
- accepted/rejected flag
- execution timestamp
- observed post-action loss delta
- operator override reason
- context snapshot hash (product/stage/weather/duration bucket)

### Recommendation evaluation metrics
- action acceptance rate (with safeguards)
- precision@1 for helpful action ranking
- mean loss reduction after accepted action
- harmful recommendation rate
- calibration of confidence vs observed outcome

## H. Weather/Duration Plan
- Evaluate weather/duration by stage, especially `sechage`, not only globally.
- Planned interaction checks:
  - humidity x stage
  - rainfall x stage
  - duration x stage
  - delay x product
- Segment evaluation metrics:
  - drying-only regression MAE
  - critical-risk recall on weather-sensitive stages
  - permutation importance by segment

## I. Feature Engineering Improvements (Planned)
- Synthetic evaluator currently uses:
  - categorical: product, stage, season, region, grade, synthetic_cooperative_id
  - numeric: stage_order, qty_in, humidity, temperature, rainfall, wind_speed, dew_point, step_duration_minutes, delay_since_previous_step_minutes, cumulative_duration_before_stage, missing_duration_flag, event_time_ordinal
- Ignored in synthetic evaluator:
  - synthetic_lot_id, qty_out, loss_qty, efficiency_pct, event_time (raw string), data_origin
- Planned improvements:
  - add explicit cross features for known stage-weather-duration mechanics
  - add lot-aware split key to avoid same-lot leakage across train/test
  - preserve leakage-safe features only (available at prediction time)

## J. Evaluation Strategy and Gates
- Keep strict separation:
  - Real-data reports determine production readiness.
  - Synthetic reports are diagnostic only.
- Split strategy improvements:
  - time split remains primary
  - add grouped time split by lot ID (no lot overlap train/test)
- Gate policy (proposed, no weakening):
  - Regression: >=10% MAE improvement vs best baseline on time split and key stage segment
  - Classification: macro-F1 improvement vs baselines plus minimum high-risk recall threshold
  - Anomaly: no promotion gate from unsupervised F1 alone; use alert-quality metrics

## K. Implementation Priority (Roadmap)
Phase 1: diagnostics and report only
- finalize this plan and freeze baseline evidence tables

Phase 2: regression redesign and evaluation only
- test model candidates + stage-specific variants + interaction features
- no runtime promotion changes

Phase 3: classification calibration and segment metrics
- calibrate probabilities and optimize high-risk recall/precision tradeoff

Phase 4: hybrid anomaly redesign
- implement rule + statistical stack first, supervised anomaly only for labeled experiments

Phase 5: recommendation ranking metadata
- add feedback fields and offline ranking evaluation scaffolding

Phase 6: final PFE reporting context
- publish clear production vs synthetic boundary narrative and final claims checklist

## L. What Must Not Be Claimed in the PFE
- Do not claim production-grade ML superiority from synthetic benchmark results.
- Do not claim promoted ML readiness while real-data gates fail.
- Do not describe recommendation engine as fully learned or autonomous.
- Do not present anomaly model as reliable detector on real operations.

## M. What Can Be Claimed Safely
- ML pipeline is reproducible and source-aware under current tooling.
- Real-data governance is conservative (gated, fallback-protected, rule-first).
- Synthetic benchmark provides controlled stress testing and model comparison only.
- Classification shows early promise relative to majority baseline, but high-risk recall remains unresolved.

## N. Additional Recommendations
- Add a single reproducible command target (for example `make synthetic-benchmark`) to standardize generator + evaluator runs for PFE audits.
- Add a “claims guardrail” appendix in reports listing allowed vs disallowed statements.
- Add a fixed benchmark card template with:
  - data source label (REAL vs SYNTHETIC)
  - split type
  - baseline winner
  - gate pass/fail
  - explicit promotion eligibility status

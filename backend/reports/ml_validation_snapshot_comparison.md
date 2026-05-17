# ML Validation Snapshot Comparison

Date: 2026-05-17

## A. Current Supabase Snapshot
- Data source: `supabase` (`aws-0-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require`)
- Rows: `45`
- Reliability (time split):
  - Regression model MAE: `3.7136`
  - Best baseline MAE: `3.8362` (`product_stage_mean_loss`)
  - Numerical comparison: model is better by `3.20%`
  - Regression gate (>=10% improvement): `FAIL`
  - Promotion decision: `baseline:product_stage_mean_loss`
  - Classification model macro-F1: `0.3125`
  - Best threshold baseline macro-F1: `0.5556`
  - Classification gate: `FAIL`
  - Anomaly status: `EXPLORATORY`
  - Recommendation policy: `RULE_BASED`
- Weather (time split):
  - Coverage: `0.7556` (`34/45`)
  - Leakage violations: `0` (`PASS`)
  - Internal model MAE: `3.7136`
  - Weather model MAE: `3.8807`
  - Best numeric model candidate: `internal_model`
  - Gate-promoted production decision: `baseline:product_stage_mean_loss`

## B. Historical Larger Artifact
- Source: `backend/backend/reports/ml_reliability_audit.json`
- Label: **HISTORICAL ARTIFACT — NOT CURRENT SUPABASE SNAPSHOT**
- Rows: `1520`
- Reliability (time split):
  - Regression model MAE: `4.3500`
  - Best baseline MAE: `3.7667` (`stage_season_mean_loss`)
  - Regression decision: `baseline:stage_season_mean_loss`
  - Classification model macro-F1: `0.4356`
  - Classification gate: `FAIL`
  - Anomaly status: `EXPLORATORY`
  - Recommendation policy: `RULE_BASED`
- Weather metrics for this same historical snapshot are not present in a paired historical weather artifact in the repository.

## C. PFE-Safe Interpretation
- Current snapshot demonstrates reproducible audit execution under Python 3.11 and source-aware reporting.
- Current snapshot does not justify ML promotion claims: regression and classification both fail strict gates, and weather model is worse than internal model.
- Historical artifact provides broader experimental context only and must be labeled historical whenever cited.
- Neither snapshot should be used to claim production-grade ML superiority.
- Safe claim: ML remains advisory and gated, with fallback decisions explicitly enforced in reports.

# ML Before vs Now Report

## Executive Comparison

The ML system moved from leakage-prone and weakly evaluated to a guarded MVP/demo pipeline with explicit leakage contracts, stage normalization, stronger diagnostics, and model governance.

It is cleaner and safer, but not production-ready due to weak performance against strong baselines and poor classifier recall for medium/high classes.

## Before vs Now Table

| Area | Before | Now | Status |
|---|---|---|---|
| Predictive leakage | Old artifact metadata included `deviation_from_stage_avg` in predictive features | Predictive contract excludes `loss_pct`, `efficiency_pct`, `qty_out`, `deviation_from_stage_avg`; leakage checks clean | fixed |
| Artifact compatibility | Contaminated artifacts could be loaded | Compatibility checks reject contaminated artifacts; current compatibility true | fixed |
| Feature schema governance | No enforced schema lifecycle | `feature_schema_version` present and validated in metadata/registry | improved |
| Dataset readiness | Tiny dataset, unstable metrics | Seeded and expanded dataset (1485 rows) for demo evaluation | improved |
| Stage naming | French/English mismatch risk | Canonical stage normalization (`cleaning/drying/sorting/packaging`) implemented | fixed |
| Recommendation stage coverage | Fallback risk on known stages | Stage-specific coverage preserved; fallback rate ~0 for known stages | improved |
| Regression evaluation | Weak/optimistic metrics | Time/random split + baseline comparisons added | fixed |
| Regression strength | No strong baseline challenge | Model still underperforms stage/product-stage baselines | still weak |
| Risk serving strategy | Overtrust in weak classifier | Served risk now `thresholded_predicted_loss` with thresholds | improved |
| Classifier quality | Overtrusted low-only behavior | Medium/high recall remains poor (near 0 in RF classifier) and explicitly reported | still weak |
| Anomaly evaluation | Accuracy implication risk without labels | Explicitly marked exploratory only, no anomaly accuracy claim | intentionally limited |
| Model governance | No explicit active/candidate lifecycle | Registry + candidate/active status + rollback + validation gates | improved |
| Monitoring | No drift/health reporting | Monitoring and deployment readiness reports generated | improved |

## Current Final Snapshot

- Dataset rows: `1485`
- Risk distribution: `low=1229`, `medium=204`, `high=52`
- Predictive leakage flags: `[]`
- Artifact compatibility: `true`
- Regression (time split): `MAE=3.7800`, `RMSE=5.8916`, `R2=0.0924`
- Stage baseline MAE: `2.6695` (better than model)
- Product-stage baseline MAE: `2.6757` (better than model)
- RF classifier macro-F1: `0.3043`
- RF classifier medium recall: `0.0`
- RF classifier high recall: `0.0`
- Served risk method: `thresholded_predicted_loss`
- Anomaly detection: exploratory only

## Honest Conclusion

The system is clean enough for MVP/demo with warnings, but not production-ready.


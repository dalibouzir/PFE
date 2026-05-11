# ML Deployment Readiness

## Core Checks
- Artifact compatibility: True (ok)
- Active model version: 20260507155633
- Dataset rows: 1485
- Leakage flags: []
- Risk method: thresholded_predicted_loss

## Baseline Comparison
- Model MAE: 3.7799943919242156
- Stage mean MAE: 2.669471663009396
- Product-stage mean MAE: 2.6756710473815426
- Beats stage baseline: False
- Beats product-stage baseline: False

## Known Limitations
- ['high_risk_recall_zero', 'model_underperforms_stage_baseline', 'synthetic_demo_data_used']

## Recommendation
- Deployment recommendation: deploy_mvp_with_warnings

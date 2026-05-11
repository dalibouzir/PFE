# ML Full Demo Validation Report

Generated: 2026-05-08T21:48:58.962560+00:00
Status: ok

## Dataset
- Rows: 1517
- Products: {'Mangue': 517, 'Arachide': 500, 'Mil': 492, 'Bissap': 8}
- Stages (raw): {'Nettoyage': 384, 'Tri': 380, 'Séchage': 377, 'Emballage': 373, 'Sechage': 2, 'Conditionnement': 1}
- Stages (canonical): {'cleaning': 384, 'sorting': 380, 'drying': 379, 'packaging': 374}
- Risk classes: {'low': 1258, 'medium': 206, 'high': 53}

## Model/Service
- Regression: RandomForestRegressor (time-based evaluation split)
- Classification: RandomForestClassifier (time-based evaluation split)
- Anomaly: IsolationForest (exploratory review)

## Classification Metrics
- Accuracy: 0.8294573643410853
- Precision (macro): 0.43561076604554866
- Recall (macro): 0.45172564438619484
- F1 (macro): 0.44345238095238093
- F1 (weighted): 0.8084856035437431
- Confusion matrix labels: ['low', 'medium', 'high']
- Confusion matrix: [[101, 8, 0], [8, 6, 0], [6, 0, 0]]

## Regression Metrics
- MAE: 4.015032910777352
- RMSE: 7.280572723452175
- R²: 0.06511232771235986

## Anomaly Metrics
- True positives: None
- False positives: None
- False negatives: None
- Note: No labeled anomaly ground truth in current schema; only exploratory anomaly flag-rate metrics are available.

## Strongest Cases
- {'product': 'Mil', 'stage_canonical': 'packaging', 'row_count': 8, 'mae': 1.03, 'mean_actual_loss_pct': 2.2, 'mean_predicted_loss_pct': 2.47}
- {'product': 'Mangue', 'stage_canonical': 'packaging', 'row_count': 9, 'mae': 1.23, 'mean_actual_loss_pct': 1.8, 'mean_predicted_loss_pct': 2.57}
- {'product': 'Mangue', 'stage_canonical': 'cleaning', 'row_count': 13, 'mae': 1.24, 'mean_actual_loss_pct': 2.31, 'mean_predicted_loss_pct': 3.06}
- {'product': 'Mil', 'stage_canonical': 'cleaning', 'row_count': 9, 'mae': 1.24, 'mean_actual_loss_pct': 3.38, 'mean_predicted_loss_pct': 3.05}
- {'product': 'Arachide', 'stage_canonical': 'cleaning', 'row_count': 11, 'mae': 1.8, 'mean_actual_loss_pct': 3.6, 'mean_predicted_loss_pct': 3.0}
- {'product': 'Arachide', 'stage_canonical': 'packaging', 'row_count': 10, 'mae': 3.09, 'mean_actual_loss_pct': 3.59, 'mean_predicted_loss_pct': 3.26}
- {'product': 'Arachide', 'stage_canonical': 'drying', 'row_count': 8, 'mae': 3.41, 'mean_actual_loss_pct': 8.71, 'mean_predicted_loss_pct': 12.12}
- {'product': 'Bissap', 'stage_canonical': 'cleaning', 'row_count': 3, 'mae': 4.01, 'mean_actual_loss_pct': 1.0, 'mean_predicted_loss_pct': 5.01}

## Weakest Cases
- {'product': 'Bissap', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'actual_loss_pct': 68.0, 'predicted_loss_pct': 5.81, 'abs_error': 62.19}
- {'product': 'Arachide', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 1.5, 'predicted_loss_pct': 15.51, 'abs_error': 14.01}
- {'product': 'Arachide', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 20.79, 'predicted_loss_pct': 6.81, 'abs_error': 13.99}
- {'product': 'Arachide', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 18.78, 'predicted_loss_pct': 7.88, 'abs_error': 10.91}
- {'product': 'Mil', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'actual_loss_pct': 4.0, 'predicted_loss_pct': 14.86, 'abs_error': 10.87}
- {'product': 'Mangue', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 19.21, 'predicted_loss_pct': 8.47, 'abs_error': 10.73}
- {'product': 'Bissap', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 2.0, 'predicted_loss_pct': 12.46, 'abs_error': 10.46}
- {'product': 'Mangue', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'actual_loss_pct': 5.05, 'predicted_loss_pct': 15.46, 'abs_error': 10.41}

## Limitations
- Evaluation uses synthetic/demo operational data and may not reflect production field variability.
- Risk labels are derived from thresholded loss_pct, which may embed heuristic bias.
- No supervised anomaly labels are available; TP/FP/FN cannot be computed reliably.

## Synthetic Data Disclaimer
- These metrics are computed from synthetic demo data seeded for platform validation and should be treated as internal validation only.

## PFE Usage Guidance
- Report these metrics as reproducible internal benchmarks for the demo dataset.
- Use confusion matrix and per-class recall to discuss risk-class detection strengths/weaknesses.
- Use MAE/RMSE/R² to explain predictive error characteristics and model fit limits.
- Explicitly mention that anomaly TP/FP/FN are unavailable due to missing labeled anomaly targets.
# ML Full Demo Validation Report

Generated: 2026-05-13T10:44:32.817896+00:00
Status: ok

## Dataset
- Rows: 52
- Products: {'mango': 20, 'Mangue': 11, 'Arachide': 8, 'Mil': 8, 'Bissap': 5}
- Stages (raw): {'Nettoyage': 12, 'Tri': 9, 'Séchage': 7, 'cleaning': 5, 'drying': 5, 'sorting': 5, 'packaging': 5, 'Emballage': 3, 'Conditionnement': 1}
- Stages (canonical): {'cleaning': 17, 'sorting': 14, 'drying': 12, 'packaging': 9}
- Risk classes: {'low': 48, 'medium': 3, 'high': 1}

## Model/Service
- Regression: RandomForestRegressor (time-based evaluation split)
- Classification: RandomForestClassifier (time-based evaluation split)
- Anomaly: IsolationForest (exploratory review)

## Classification Metrics
- Accuracy: 0.9166666666666666
- Precision (macro): 0.3055555555555555
- Recall (macro): 0.3333333333333333
- F1 (macro): 0.4782608695652174
- F1 (weighted): 0.8768115942028986
- Confusion matrix labels: ['low', 'medium', 'high']
- Confusion matrix: [[11, 0, 0], [1, 0, 0], [0, 0, 0]]

## Regression Metrics
- MAE: 2.366245496533157
- RMSE: 3.640381427682027
- R²: -0.4634031610206406

## Anomaly Metrics
- True positives: None
- False positives: None
- False negatives: None
- Note: No labeled anomaly ground truth in current schema; only exploratory anomaly flag-rate metrics are available.

## Strongest Cases
- {'product': 'mango', 'stage_canonical': 'packaging', 'row_count': 4, 'mae': 1.08, 'mean_actual_loss_pct': 4.75, 'mean_predicted_loss_pct': 5.28}
- {'product': 'mango', 'stage_canonical': 'cleaning', 'row_count': 2, 'mae': 1.49, 'mean_actual_loss_pct': 4.5, 'mean_predicted_loss_pct': 3.01}
- {'product': 'mango', 'stage_canonical': 'sorting', 'row_count': 3, 'mae': 2.12, 'mean_actual_loss_pct': 6.67, 'mean_predicted_loss_pct': 4.55}
- {'product': 'mango', 'stage_canonical': 'drying', 'row_count': 3, 'mae': 4.91, 'mean_actual_loss_pct': 9.33, 'mean_predicted_loss_pct': 4.75}

## Weakest Cases
- {'product': 'mango', 'process_type': 'drying', 'stage_canonical': 'drying', 'actual_loss_pct': 14.0, 'predicted_loss_pct': 3.77, 'abs_error': 10.23}
- {'product': 'mango', 'process_type': 'sorting', 'stage_canonical': 'sorting', 'actual_loss_pct': 8.0, 'predicted_loss_pct': 3.36, 'abs_error': 4.64}
- {'product': 'mango', 'process_type': 'drying', 'stage_canonical': 'drying', 'actual_loss_pct': 9.0, 'predicted_loss_pct': 4.99, 'abs_error': 4.01}
- {'product': 'mango', 'process_type': 'packaging', 'stage_canonical': 'packaging', 'actual_loss_pct': 2.0, 'predicted_loss_pct': 4.55, 'abs_error': 2.55}
- {'product': 'mango', 'process_type': 'cleaning', 'stage_canonical': 'cleaning', 'actual_loss_pct': 5.0, 'predicted_loss_pct': 2.55, 'abs_error': 2.45}
- {'product': 'mango', 'process_type': 'sorting', 'stage_canonical': 'sorting', 'actual_loss_pct': 6.0, 'predicted_loss_pct': 4.38, 'abs_error': 1.62}
- {'product': 'mango', 'process_type': 'packaging', 'stage_canonical': 'packaging', 'actual_loss_pct': 3.0, 'predicted_loss_pct': 3.67, 'abs_error': 0.67}
- {'product': 'mango', 'process_type': 'packaging', 'stage_canonical': 'packaging', 'actual_loss_pct': 7.0, 'predicted_loss_pct': 6.43, 'abs_error': 0.57}

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
# ML Evaluation Report

## Dataset Summary
- Rows: 12
- Products: {'mango': 12}
- Raw stages: {'cleaning': 3, 'drying': 3, 'sorting': 3, 'packaging': 3}
- Canonical stages: {'cleaning': 3, 'drying': 3, 'sorting': 3, 'packaging': 3}
- Risk classes: {'low': 12}

## Split Strategy
- Time-based split: train=10, test=2
- Random split: train=9, test=3

## Regression Evaluation
- Time split model MAE: 0.2001
- Time split model RMSE: 0.2155
- Time split model R2: 0.8146355751323975

## Baseline Comparison
- global_mean_loss: MAE=1.2001, RMSE=1.3003, MAE delta vs model=1.0001
- product_mean_loss: MAE=1.2001, RMSE=1.3003, MAE delta vs model=1.0001
- stage_mean_loss: MAE=0.0000, RMSE=0.0000, MAE delta vs model=-0.2001
- product_stage_mean_loss: MAE=0.0000, RMSE=0.0000, MAE delta vs model=-0.2001
- stage_season_mean_loss: MAE=0.0000, RMSE=0.0000, MAE delta vs model=-0.2001
- product_stage_season_mean_loss: MAE=0.0000, RMSE=0.0000, MAE delta vs model=-0.2001
- product_stage_rolling_mean_loss: MAE=0.0000, RMSE=0.0000, MAE delta vs model=-0.2001
- previous_batch_loss_baseline: MAE=1.0001, RMSE=1.1184, MAE delta vs model=0.8000

## Classification Evaluation
- Model accuracy=1.0000, macro-F1=1.0000, weighted-F1=1.0000
- Per-class: {'low': {'precision': 1.0, 'recall': 1.0, 'f1': 1.0, 'support': 2}, 'medium': {'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'support': 0}, 'high': {'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'support': 0}}
- Confusion matrix: [[2, 0, 0], [0, 0, 0], [0, 0, 0]]
- Medium recall: 0.0000, High recall: 0.0000, False-low high-risk rate: 0.0000
- Thresholded risk method: {'low_to_medium': 6.0, 'medium_to_high': 12.0}

## Segment Analysis
- Product segments: [{'product': 'mango', 'row_count': 2, 'mae': 0.20005924916722861, 'mean_actual_loss_pct': 6.5002157972558745, 'mean_predicted_loss_pct': 6.300156548088646, 'error_bias': -0.20005924916722861}]
- Canonical stage segments: [{'stage_canonical': 'packaging', 'row_count': 1, 'mae': 0.28021670025113554, 'mean_actual_loss_pct': 7.000797091587765, 'mean_predicted_loss_pct': 6.72058039133663, 'error_bias': -0.28021670025113554}, {'stage_canonical': 'sorting', 'row_count': 1, 'mae': 0.11990179808332169, 'mean_actual_loss_pct': 5.999634502923984, 'mean_predicted_loss_pct': 5.879732704840662, 'error_bias': -0.11990179808332169}]

## Top Prediction Errors
- Top 10 errors: [{'product': 'mango', 'process_type': 'packaging', 'stage_canonical': 'packaging', 'qty_in': 514.37, 'qty_out': 478.36, 'actual_loss_pct': 7.000797091587765, 'predicted_loss_pct': 6.72058039133663, 'abs_error': 0.28021670025113554, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'mango', 'process_type': 'sorting', 'stage_canonical': 'sorting', 'qty_in': 547.2, 'qty_out': 514.37, 'actual_loss_pct': 5.999634502923984, 'predicted_loss_pct': 5.879732704840662, 'abs_error': 0.11990179808332169, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}]

## Anomaly Review
- No anomaly accuracy is reported (no ground-truth anomaly labels).
- Anomaly review: {'anomaly_accuracy_reported': False, 'note': 'Exploratory only: no labeled anomaly ground truth available.', 'flag_rate': 0.0, 'score_negative_rate': 0.0, 'flagged_count': 0, 'flagged_high_loss_rate': 0.0, 'top_anomaly_examples': [{'product': 'mango', 'process_type': 'packaging', 'stage_canonical': 'packaging', 'actual_loss_pct': 7.000797091587765, 'predicted_loss_pct': 6.72058039133663, 'anomaly_score_raw': 0.025986797880581558, 'is_anomalous': False}, {'product': 'mango', 'process_type': 'sorting', 'stage_canonical': 'sorting', 'actual_loss_pct': 5.999634502923984, 'predicted_loss_pct': 5.879732704840662, 'anomaly_score_raw': 0.04971838012446994, 'is_anomalous': False}]}

## Honest Interpretation
- Regression is mixed versus strong baselines across splits.
- Classification remains weak for medium/high risk recall.
- Current anomaly signals are exploratory only, not validated accuracy.

## Recommended Next Actions
- Improve class balance for medium/high risk.
- Add walk-forward validation and calibration tracking.
- Add labeled anomaly feedback to evaluate precision@k.

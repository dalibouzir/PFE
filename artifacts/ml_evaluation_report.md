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
- Time split model MAE: 0.5125
- Time split model RMSE: 0.6217
- Time split model R2: -0.5426960327363917

## Baseline Comparison
- global_mean_loss: MAE=1.2001, RMSE=1.3003, MAE delta vs model=0.6876
- product_mean_loss: MAE=1.2001, RMSE=1.3003, MAE delta vs model=0.6876
- stage_mean_loss: MAE=0.0000, RMSE=0.0000, MAE delta vs model=-0.5125
- product_stage_mean_loss: MAE=0.0000, RMSE=0.0000, MAE delta vs model=-0.5125
- stage_season_mean_loss: MAE=0.0000, RMSE=0.0000, MAE delta vs model=-0.5125
- product_stage_season_mean_loss: MAE=0.0000, RMSE=0.0000, MAE delta vs model=-0.5125
- product_stage_rolling_mean_loss: MAE=0.0000, RMSE=0.0000, MAE delta vs model=-0.5125
- previous_batch_loss_baseline: MAE=1.0001, RMSE=1.1184, MAE delta vs model=0.4876

## Classification Evaluation
- Model accuracy=1.0000, macro-F1=1.0000, weighted-F1=1.0000
- Per-class: {'low': {'precision': 1.0, 'recall': 1.0, 'f1': 1.0, 'support': 2}, 'medium': {'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'support': 0}, 'high': {'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'support': 0}}
- Confusion matrix: [[2, 0, 0], [0, 0, 0], [0, 0, 0]]
- Medium recall: 0.0000, High recall: 0.0000, False-low high-risk rate: 0.0000
- Thresholded risk method: {'low_to_medium': 6.0, 'medium_to_high': 12.0}

## Segment Analysis
- Product segments: [{'product': 'mango', 'row_count': 2, 'mae': 0.5124797096789102, 'mean_actual_loss_pct': 6.5002157972558745, 'mean_predicted_loss_pct': 6.148170577017124, 'error_bias': -0.3520452202387503}]
- Canonical stage segments: [{'stage_canonical': 'packaging', 'row_count': 1, 'mae': 0.8645249299176605, 'mean_actual_loss_pct': 7.000797091587765, 'mean_predicted_loss_pct': 6.136272161670105, 'error_bias': -0.8645249299176605}, {'stage_canonical': 'sorting', 'row_count': 1, 'mae': 0.16043448944015992, 'mean_actual_loss_pct': 5.999634502923984, 'mean_predicted_loss_pct': 6.160068992364144, 'error_bias': 0.16043448944015992}]

## Top Prediction Errors
- Top 10 errors: [{'product': 'mango', 'process_type': 'packaging', 'stage_canonical': 'packaging', 'qty_in': 514.37, 'qty_out': 478.36, 'actual_loss_pct': 7.000797091587765, 'predicted_loss_pct': 6.136272161670105, 'abs_error': 0.8645249299176605, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'mango', 'process_type': 'sorting', 'stage_canonical': 'sorting', 'qty_in': 547.2, 'qty_out': 514.37, 'actual_loss_pct': 5.999634502923984, 'predicted_loss_pct': 6.160068992364144, 'abs_error': 0.16043448944015992, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}]

## Anomaly Review
- No anomaly accuracy is reported (no ground-truth anomaly labels).
- Anomaly review: {'anomaly_accuracy_reported': False, 'note': 'Exploratory only: no labeled anomaly ground truth available.', 'flag_rate': 0.0, 'score_negative_rate': 0.0, 'flagged_count': 0, 'flagged_high_loss_rate': 0.0, 'top_anomaly_examples': [{'product': 'mango', 'process_type': 'packaging', 'stage_canonical': 'packaging', 'actual_loss_pct': 7.000797091587765, 'predicted_loss_pct': 6.136272161670105, 'anomaly_score_raw': 0.01708902480183272, 'is_anomalous': False}, {'product': 'mango', 'process_type': 'sorting', 'stage_canonical': 'sorting', 'actual_loss_pct': 5.999634502923984, 'predicted_loss_pct': 6.160068992364144, 'anomaly_score_raw': 0.050997683563564156, 'is_anomalous': False}]}

## Honest Interpretation
- Regression is mixed versus strong baselines across splits.
- Classification remains weak for medium/high risk recall.
- Current anomaly signals are exploratory only, not validated accuracy.

## Recommended Next Actions
- Improve class balance for medium/high risk.
- Add walk-forward validation and calibration tracking.
- Add labeled anomaly feedback to evaluate precision@k.

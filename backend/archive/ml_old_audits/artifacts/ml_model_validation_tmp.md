# ML Evaluation Report

## Dataset Summary
- Rows: 52
- Products: {'mango': 20, 'Mangue': 11, 'Arachide': 8, 'Mil': 8, 'Bissap': 5}
- Raw stages: {'Nettoyage': 12, 'Tri': 9, 'Séchage': 7, 'cleaning': 5, 'drying': 5, 'sorting': 5, 'packaging': 5, 'Emballage': 3, 'Conditionnement': 1}
- Canonical stages: {'cleaning': 17, 'sorting': 14, 'drying': 12, 'packaging': 9}
- Risk classes: {'low': 48, 'medium': 3, 'high': 1}

## Split Strategy
- Time-based split: train=40, test=12
- Random split: train=41, test=11

## Regression Evaluation
- Time split model MAE: 2.3662
- Time split model RMSE: 3.6404
- Time split model R2: -0.4634031610206406

## Baseline Comparison
- global_mean_loss: MAE=2.6272, RMSE=3.5701, MAE delta vs model=0.2609
- product_mean_loss: MAE=2.3126, RMSE=3.2428, MAE delta vs model=-0.0537
- stage_mean_loss: MAE=2.7727, RMSE=3.2136, MAE delta vs model=0.4065
- product_stage_mean_loss: MAE=2.0835, RMSE=3.4523, MAE delta vs model=-0.2827
- stage_season_mean_loss: MAE=2.4879, RMSE=2.9321, MAE delta vs model=0.1216
- product_stage_season_mean_loss: MAE=2.0835, RMSE=3.4523, MAE delta vs model=-0.2827
- product_stage_rolling_mean_loss: MAE=2.0835, RMSE=3.4523, MAE delta vs model=-0.2827
- previous_batch_loss_baseline: MAE=2.5001, RMSE=3.3789, MAE delta vs model=0.1339

## Classification Evaluation
- Model accuracy=0.9167, macro-F1=0.4783, weighted-F1=0.8768
- Per-class: {'low': {'precision': 0.9166666666666666, 'recall': 1.0, 'f1': 0.9565217391304348, 'support': 11}, 'medium': {'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'support': 1}, 'high': {'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'support': 0}}
- Confusion matrix: [[11, 0, 0], [1, 0, 0], [0, 0, 0]]
- Medium recall: 0.0000, High recall: 0.0000, False-low high-risk rate: 0.0000
- Thresholded risk method: {'low_to_medium': 6.0, 'medium_to_high': 12.0}

## Segment Analysis
- Product segments: [{'product': 'mango', 'row_count': 12, 'mae': 2.366245496533157, 'mean_actual_loss_pct': 6.333382172268153, 'mean_predicted_loss_pct': 4.5854755046561975, 'error_bias': -1.7479066676119563}]
- Canonical stage segments: [{'stage_canonical': 'packaging', 'row_count': 4, 'mae': 1.080777972869745, 'mean_actual_loss_pct': 4.750377797463376, 'mean_predicted_loss_pct': 5.278624673193304, 'error_bias': 0.5282468757299289}, {'stage_canonical': 'drying', 'row_count': 3, 'mae': 4.910666618559811, 'mean_actual_loss_pct': 9.33333333333333, 'mean_predicted_loss_pct': 4.750655565658757, 'error_bias': -4.582677767674574}, {'stage_canonical': 'sorting', 'row_count': 3, 'mae': 2.119891103702163, 'mean_actual_loss_pct': 6.666358292454785, 'mean_predicted_loss_pct': 4.546467188752622, 'error_bias': -2.119891103702163}, {'stage_canonical': 'cleaning', 'row_count': 2, 'mae': 1.490080450066491, 'mean_actual_loss_pct': 4.5, 'mean_predicted_loss_pct': 3.009919549933509, 'error_bias': -1.490080450066491}]

## Top Prediction Errors
- Top 10 errors: [{'product': 'mango', 'process_type': 'drying', 'stage_canonical': 'drying', 'qty_in': 950.0, 'qty_out': 817.0, 'actual_loss_pct': 14.000000000000002, 'predicted_loss_pct': 3.7659286101628706, 'abs_error': 10.234071389837132, 'actual_risk_level': 'medium', 'predicted_risk_level': 'low'}, {'product': 'mango', 'process_type': 'sorting', 'stage_canonical': 'sorting', 'qty_in': 817.0, 'qty_out': 751.64, 'actual_loss_pct': 8.000000000000002, 'predicted_loss_pct': 3.3578137437753597, 'abs_error': 4.642186256224642, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'mango', 'process_type': 'drying', 'stage_canonical': 'drying', 'qty_in': 864.0, 'qty_out': 786.24, 'actual_loss_pct': 8.999999999999998, 'predicted_loss_pct': 4.994054810485553, 'abs_error': 4.005945189514446, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'mango', 'process_type': 'packaging', 'stage_canonical': 'packaging', 'qty_in': 739.07, 'qty_out': 724.29, 'actual_loss_pct': 1.999810572746842, 'predicted_loss_pct': 4.545979504459191, 'abs_error': 2.546168931712349, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'mango', 'process_type': 'cleaning', 'stage_canonical': 'cleaning', 'qty_in': 1000.0, 'qty_out': 950.0, 'actual_loss_pct': 5.0, 'predicted_loss_pct': 2.5539067302057905, 'abs_error': 2.4460932697942095, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'mango', 'process_type': 'sorting', 'stage_canonical': 'sorting', 'qty_in': 786.24, 'qty_out': 739.07, 'actual_loss_pct': 5.999440374440369, 'predicted_loss_pct': 4.377875246056011, 'abs_error': 1.6215651283843586, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'mango', 'process_type': 'packaging', 'stage_canonical': 'packaging', 'qty_in': 751.64, 'qty_out': 729.09, 'actual_loss_pct': 3.000106433931131, 'predicted_loss_pct': 3.6719871994181306, 'abs_error': 0.6718807654869994, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'mango', 'process_type': 'packaging', 'stage_canonical': 'packaging', 'qty_in': 514.37, 'qty_out': 478.36, 'actual_loss_pct': 7.000797091587765, 'predicted_loss_pct': 6.432262956334568, 'abs_error': 0.5685341352531976, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'mango', 'process_type': 'packaging', 'stage_canonical': 'packaging', 'qty_in': 514.37, 'qty_out': 478.36, 'actual_loss_pct': 7.000797091587765, 'predicted_loss_pct': 6.46426903256133, 'abs_error': 0.536528059026435, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'mango', 'process_type': 'cleaning', 'stage_canonical': 'cleaning', 'qty_in': 900.0, 'qty_out': 864.0, 'actual_loss_pct': 4.0, 'predicted_loss_pct': 3.4659323696612274, 'abs_error': 0.5340676303387726, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}]

## Anomaly Review
- No anomaly accuracy is reported (no ground-truth anomaly labels).
- Anomaly review: {'anomaly_accuracy_reported': False, 'note': 'Exploratory only: no labeled anomaly ground truth available.', 'flag_rate': 0.16666666666666666, 'score_negative_rate': 0.16666666666666666, 'flagged_count': 2, 'flagged_high_loss_rate': 0.0, 'top_anomaly_examples': [{'product': 'mango', 'process_type': 'packaging', 'stage_canonical': 'packaging', 'actual_loss_pct': 7.000797091587765, 'predicted_loss_pct': 6.46426903256133, 'anomaly_score_raw': -0.0029326919546487362, 'is_anomalous': True}, {'product': 'mango', 'process_type': 'packaging', 'stage_canonical': 'packaging', 'actual_loss_pct': 7.000797091587765, 'predicted_loss_pct': 6.432262956334568, 'anomaly_score_raw': -0.0024110937697027213, 'is_anomalous': True}, {'product': 'mango', 'process_type': 'packaging', 'stage_canonical': 'packaging', 'actual_loss_pct': 3.000106433931131, 'predicted_loss_pct': 3.6719871994181306, 'anomaly_score_raw': 0.008408135797246752, 'is_anomalous': False}, {'product': 'mango', 'process_type': 'packaging', 'stage_canonical': 'packaging', 'actual_loss_pct': 1.999810572746842, 'predicted_loss_pct': 4.545979504459191, 'anomaly_score_raw': 0.010979036968553624, 'is_anomalous': False}, {'product': 'mango', 'process_type': 'sorting', 'stage_canonical': 'sorting', 'actual_loss_pct': 8.000000000000002, 'predicted_loss_pct': 3.3578137437753597, 'anomaly_score_raw': 0.028023587494311164, 'is_anomalous': False}, {'product': 'mango', 'process_type': 'drying', 'stage_canonical': 'drying', 'actual_loss_pct': 14.000000000000002, 'predicted_loss_pct': 3.7659286101628706, 'anomaly_score_raw': 0.02869291310055677, 'is_anomalous': False}, {'product': 'mango', 'process_type': 'drying', 'stage_canonical': 'drying', 'actual_loss_pct': 8.999999999999998, 'predicted_loss_pct': 4.994054810485553, 'anomaly_score_raw': 0.033076746059161555, 'is_anomalous': False}, {'product': 'mango', 'process_type': 'sorting', 'stage_canonical': 'sorting', 'actual_loss_pct': 5.999440374440369, 'predicted_loss_pct': 4.377875246056011, 'anomaly_score_raw': 0.0336760384396626, 'is_anomalous': False}, {'product': 'mango', 'process_type': 'sorting', 'stage_canonical': 'sorting', 'actual_loss_pct': 5.999634502923984, 'predicted_loss_pct': 5.903712576426496, 'anomaly_score_raw': 0.043940013133431044, 'is_anomalous': False}, {'product': 'mango', 'process_type': 'drying', 'stage_canonical': 'drying', 'actual_loss_pct': 4.999999999999992, 'predicted_loss_pct': 5.491983276327848, 'anomaly_score_raw': 0.06761001874998662, 'is_anomalous': False}]}

## Honest Interpretation
- Regression is mixed versus strong baselines across splits.
- Classification remains weak for medium/high risk recall.
- Current anomaly signals are exploratory only, not validated accuracy.

## Recommended Next Actions
- Improve class balance for medium/high risk.
- Add walk-forward validation and calibration tracking.
- Add labeled anomaly feedback to evaluate precision@k.

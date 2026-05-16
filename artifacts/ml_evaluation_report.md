# ML Evaluation Report

## Dataset Summary
- Rows: 1520
- Products: {'Mangue': 517, 'Arachide': 503, 'Mil': 492, 'Bissap': 8}
- Raw stages: {'Nettoyage': 385, 'Tri': 381, 'Séchage': 377, 'Emballage': 373, 'Sechage': 3, 'Conditionnement': 1}
- Canonical stages: {'cleaning': 385, 'sorting': 381, 'drying': 380, 'packaging': 374}
- Risk classes: {'low': 1260, 'medium': 206, 'high': 54}

## Split Strategy
- Time-based split: train=1392, test=128
- Random split: train=1216, test=304

## Regression Evaluation
- Time split model MAE: 4.3735
- Time split model RMSE: 8.0211
- Time split model R2: 0.06562658961762513

## Baseline Comparison
- global_mean_loss: MAE=5.1263, RMSE=8.2980, MAE delta vs model=0.7528
- product_mean_loss: MAE=5.1248, RMSE=8.2971, MAE delta vs model=0.7513
- stage_mean_loss: MAE=3.8330, RMSE=7.3005, MAE delta vs model=-0.5405
- product_stage_mean_loss: MAE=3.8431, RMSE=7.3269, MAE delta vs model=-0.5304
- stage_season_mean_loss: MAE=3.7667, RMSE=7.2981, MAE delta vs model=-0.6068
- product_stage_season_mean_loss: MAE=3.7843, RMSE=7.3744, MAE delta vs model=-0.5892
- product_stage_rolling_mean_loss: MAE=4.0833, RMSE=7.9633, MAE delta vs model=-0.2902
- previous_batch_loss_baseline: MAE=5.4260, RMSE=9.2176, MAE delta vs model=1.0525

## Classification Evaluation
- Model accuracy=0.8359, macro-F1=0.4501, weighted-F1=0.8129
- Per-class: {'low': {'precision': 0.8782608695652174, 'recall': 0.9351851851851852, 'f1': 0.905829596412556, 'support': 108}, 'medium': {'precision': 0.46153846153846156, 'recall': 0.42857142857142855, 'f1': 0.4444444444444444, 'support': 14}, 'high': {'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'support': 6}}
- Confusion matrix: [[101, 7, 0], [8, 6, 0], [6, 0, 0]]
- Medium recall: 0.4286, High recall: 0.0000, False-low high-risk rate: 1.0000
- Thresholded risk method: {'low_to_medium': 6.0, 'medium_to_high': 12.0}

## Segment Analysis
- Product segments: [{'product': 'Arachide', 'row_count': 43, 'mae': 4.795789167746619, 'mean_actual_loss_pct': 6.877511036068099, 'mean_predicted_loss_pct': 7.1481945171221515, 'error_bias': 0.2706834810540544}, {'product': 'Mangue', 'row_count': 43, 'mae': 3.1030716469317015, 'mean_actual_loss_pct': 6.52533777911615, 'mean_predicted_loss_pct': 7.528448103032829, 'error_bias': 1.0031103239166794}, {'product': 'Mil', 'row_count': 34, 'mae': 3.3709952077070784, 'mean_actual_loss_pct': 5.570982543858083, 'mean_predicted_loss_pct': 7.250227671373789, 'error_bias': 1.6792451275157063}, {'product': 'Bissap', 'row_count': 8, 'mae': 13.192970087015809, 'mean_actual_loss_pct': 10.270737461352653, 'mean_predicted_loss_pct': 7.923135753639875, 'error_bias': -2.3476017077127764}]
- Canonical stage segments: [{'stage_canonical': 'cleaning', 'row_count': 35, 'mae': 1.6604345491776067, 'mean_actual_loss_pct': 2.811736575757331, 'mean_predicted_loss_pct': 3.2664822409448226, 'error_bias': 0.454745665187491}, {'stage_canonical': 'sorting', 'row_count': 33, 'mae': 6.716111571197865, 'mean_actual_loss_pct': 9.399613256448802, 'mean_predicted_loss_pct': 10.054514509437483, 'error_bias': 0.6549012529886797}, {'stage_canonical': 'drying', 'row_count': 32, 'mae': 6.951765155529657, 'mean_actual_loss_pct': 11.519702922947715, 'mean_predicted_loss_pct': 12.76929129558702, 'error_bias': 1.2495883726393053}, {'stage_canonical': 'packaging', 'row_count': 28, 'mae': 2.0573298836300045, 'mean_actual_loss_pct': 2.5240462173669553, 'mean_predicted_loss_pct': 3.080188600685775, 'error_bias': 0.5561423833188199}]

## Top Prediction Errors
- Top 10 errors: [{'product': 'Bissap', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'qty_in': 150.0, 'qty_out': 48.0, 'actual_loss_pct': 68.0, 'predicted_loss_pct': 5.837712821085662, 'abs_error': 62.16228717891434, 'actual_risk_level': 'high', 'predicted_risk_level': 'low'}, {'product': 'Arachide', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 96.0, 'qty_out': 51.0, 'actual_loss_pct': 46.875, 'predicted_loss_pct': 12.24472500267931, 'abs_error': 34.63027499732069, 'actual_risk_level': 'high', 'predicted_risk_level': 'low'}, {'product': 'Arachide', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'qty_in': 97.0, 'qty_out': 96.0, 'actual_loss_pct': 1.0309278350515463, 'predicted_loss_pct': 18.349400449992423, 'abs_error': 17.318472614940877, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Arachide', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 980.1, 'qty_out': 965.4, 'actual_loss_pct': 1.4998469543924136, 'predicted_loss_pct': 15.082282196410471, 'abs_error': 13.582435242018057, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Arachide', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 563.907, 'qty_out': 446.643, 'actual_loss_pct': 20.7949183109981, 'predicted_loss_pct': 7.2590924060181194, 'abs_error': 13.53582590497998, 'actual_risk_level': 'high', 'predicted_risk_level': 'low'}, {'product': 'Mil', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'qty_in': 842.8, 'qty_out': 809.09, 'actual_loss_pct': 3.999762695775976, 'predicted_loss_pct': 15.734039432952422, 'abs_error': 11.734276737176446, 'actual_risk_level': 'low', 'predicted_risk_level': 'medium'}, {'product': 'Mangue', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'qty_in': 99.0, 'qty_out': 94.0, 'actual_loss_pct': 5.05050505050505, 'predicted_loss_pct': 15.390791411724306, 'abs_error': 10.340286361219256, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Bissap', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 673.2, 'qty_out': 659.74, 'actual_loss_pct': 1.99940582293524, 'predicted_loss_pct': 12.14531422182105, 'abs_error': 10.14590839888581, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Arachide', 'process_type': 'Conditionnement', 'stage_canonical': 'packaging', 'qty_in': 756.76, 'qty_out': 741.62, 'actual_loss_pct': 2.0006342829959283, 'predicted_loss_pct': 12.09670315576585, 'abs_error': 10.096068872769921, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mangue', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 608.007, 'qty_out': 491.223, 'actual_loss_pct': 19.2076735958632, 'predicted_loss_pct': 9.377512196463616, 'abs_error': 9.830161399399582, 'actual_risk_level': 'high', 'predicted_risk_level': 'low'}]

## Anomaly Review
- No anomaly accuracy is reported (no ground-truth anomaly labels).
- Anomaly review: {'anomaly_accuracy_reported': False, 'note': 'Exploratory only: no labeled anomaly ground truth available.', 'flag_rate': 0.21875, 'score_negative_rate': 0.21875, 'flagged_count': 28, 'flagged_high_loss_rate': 0.14285714285714285, 'top_anomaly_examples': [{'product': 'Bissap', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'actual_loss_pct': 68.0, 'predicted_loss_pct': 5.837712821085662, 'anomaly_score_raw': -0.10504184753824297, 'is_anomalous': True}, {'product': 'Arachide', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 46.875, 'predicted_loss_pct': 12.24472500267931, 'anomaly_score_raw': -0.08781708548688483, 'is_anomalous': True}, {'product': 'Arachide', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'actual_loss_pct': 1.0309278350515463, 'predicted_loss_pct': 18.349400449992423, 'anomaly_score_raw': -0.06370536479016387, 'is_anomalous': True}, {'product': 'Bissap', 'process_type': 'Nettoyage', 'stage_canonical': 'cleaning', 'actual_loss_pct': 0.0, 'predicted_loss_pct': 5.451361425912306, 'anomaly_score_raw': -0.06102864977675704, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'actual_loss_pct': 5.05050505050505, 'predicted_loss_pct': 15.390791411724306, 'anomaly_score_raw': -0.059571991042415284, 'is_anomalous': True}, {'product': 'Bissap', 'process_type': 'Emballage', 'stage_canonical': 'packaging', 'actual_loss_pct': 1.0003940946433478, 'predicted_loss_pct': 7.305855932312226, 'anomaly_score_raw': -0.05911310341851583, 'is_anomalous': True}, {'product': 'Bissap', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 4.166666666666666, 'predicted_loss_pct': 12.052012351830534, 'anomaly_score_raw': -0.055409203031599685, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Nettoyage', 'stage_canonical': 'cleaning', 'actual_loss_pct': 1.0, 'predicted_loss_pct': 3.2180035620908405, 'anomaly_score_raw': -0.044892827040120875, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'actual_loss_pct': 21.999999999999993, 'predicted_loss_pct': 16.109348104610923, 'anomaly_score_raw': -0.0444439148350293, 'is_anomalous': True}, {'product': 'Arachide', 'process_type': 'Nettoyage', 'stage_canonical': 'cleaning', 'actual_loss_pct': 3.0, 'predicted_loss_pct': 4.252752855128987, 'anomaly_score_raw': -0.029046139669237414, 'is_anomalous': True}]}

## Honest Interpretation
- Regression is mixed versus strong baselines across splits.
- Classification remains weak for medium/high risk recall.
- Current anomaly signals are exploratory only, not validated accuracy.

## Recommended Next Actions
- Improve class balance for medium/high risk.
- Add walk-forward validation and calibration tracking.
- Add labeled anomaly feedback to evaluate precision@k.

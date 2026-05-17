# ML Evaluation Report

## Dataset Summary
- Rows: 45
- Products: {'Mangue': 19, 'Arachide': 8, 'Mil': 8, 'Bissap': 5, 'Banane': 5}
- Raw stages: {'Nettoyage': 12, 'Tri': 9, 'Séchage': 7, 'Emballage': 3, 'perte_tri': 3, 'livraison': 3, 'Conditionnement': 1, 'cleaning': 1, 'drying': 1, 'Suivi du régime': 1, 'Protection des régimes': 1, 'Contrôle maturité': 1, 'Testing': 1, 'Récolte verte': 1}
- Canonical stages: {'cleaning': 13, 'unknown': 11, 'sorting': 9, 'drying': 8, 'packaging': 4}
- Risk classes: {'low': 41, 'medium': 3, 'high': 1}

## Split Strategy
- Time-based split: train=28, test=17
- Random split: train=36, test=9

## Regression Evaluation
- Time split model MAE: 3.7136
- Time split model RMSE: 4.6087
- Time split model R2: 0.42679602042479026

## Baseline Comparison
- global_mean_loss: MAE=4.9792, RMSE=6.4792, MAE delta vs model=1.2656
- product_mean_loss: MAE=4.3362, RMSE=6.0675, MAE delta vs model=0.6226
- stage_mean_loss: MAE=4.1507, RMSE=5.0840, MAE delta vs model=0.4371
- product_stage_mean_loss: MAE=3.8362, RMSE=4.7611, MAE delta vs model=0.1226
- stage_season_mean_loss: MAE=4.2478, RMSE=5.2384, MAE delta vs model=0.5342
- product_stage_season_mean_loss: MAE=3.9792, RMSE=4.9267, MAE delta vs model=0.2656
- product_stage_rolling_mean_loss: MAE=4.0380, RMSE=4.9327, MAE delta vs model=0.3244
- previous_batch_loss_baseline: MAE=5.5284, RMSE=7.1696, MAE delta vs model=1.8148

## Classification Evaluation
- Model accuracy=0.8824, macro-F1=0.3125, weighted-F1=0.8272
- Per-class: {'low': {'precision': 0.8823529411764706, 'recall': 1.0, 'f1': 0.9375, 'support': 15}, 'medium': {'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'support': 1}, 'high': {'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'support': 1}}
- Confusion matrix: [[15, 0, 0], [1, 0, 0], [1, 0, 0]]
- Medium recall: 0.0000, High recall: 0.0000, False-low high-risk rate: 1.0000
- Thresholded risk method: {'low_to_medium': 6.0, 'medium_to_high': 12.0}

## Segment Analysis
- Product segments: [{'product': 'Mangue', 'row_count': 9, 'mae': 5.443524368449189, 'mean_actual_loss_pct': 10.72696339777085, 'mean_predicted_loss_pct': 5.283439029321661, 'error_bias': -5.443524368449189}, {'product': 'Banane', 'row_count': 5, 'mae': 1.9758057919553713, 'mean_actual_loss_pct': 0.8937504924598058, 'mean_predicted_loss_pct': 2.8695562844151774, 'error_bias': 1.9758057919553713}, {'product': 'Arachide', 'row_count': 3, 'mae': 1.4201848972964752, 'mean_actual_loss_pct': 1.166477539455297, 'mean_predicted_loss_pct': 2.5866624367517725, 'error_bias': 1.4201848972964752}]
- Canonical stage segments: [{'stage_canonical': 'unknown', 'row_count': 11, 'mae': 3.2379066963005325, 'mean_actual_loss_pct': 4.953607628345628, 'mean_predicted_loss_pct': 3.511888015640888, 'error_bias': -1.4417196127047396}, {'stage_canonical': 'cleaning', 'row_count': 2, 'mae': 3.160068457371511, 'mean_actual_loss_pct': 4.499999999999999, 'mean_predicted_loss_pct': 2.779955121531133, 'error_bias': -1.7200448784688662}, {'stage_canonical': 'drying', 'row_count': 2, 'mae': 9.186830640336664, 'mean_actual_loss_pct': 19.260869565217387, 'mean_predicted_loss_pct': 10.074038924880723, 'error_bias': -9.186830640336664}, {'stage_canonical': 'packaging', 'row_count': 1, 'mae': 1.488612055194447, 'mean_actual_loss_pct': 0.9995856639734803, 'mean_predicted_loss_pct': 2.4881977191679274, 'error_bias': 1.488612055194447}, {'stage_canonical': 'sorting', 'row_count': 1, 'mae': 1.3319190577923334, 'mean_actual_loss_pct': 1.4998469543924136, 'mean_predicted_loss_pct': 2.831766012184747, 'error_bias': 1.3319190577923334}]

## Top Prediction Errors
- Top 10 errors: [{'product': 'Mangue', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'qty_in': 441.0, 'qty_out': 343.98, 'actual_loss_pct': 21.999999999999993, 'predicted_loss_pct': 10.928079082057794, 'abs_error': 11.0719209179422, 'actual_risk_level': 'high', 'predicted_risk_level': 'low'}, {'product': 'Mangue', 'process_type': 'drying', 'stage_canonical': 'drying', 'qty_in': 230.0, 'qty_out': 192.0, 'actual_loss_pct': 16.52173913043478, 'predicted_loss_pct': 9.219998767703652, 'abs_error': 7.301740362731129, 'actual_risk_level': 'medium', 'predicted_risk_level': 'low'}, {'product': 'Mangue', 'process_type': 'livraison', 'stage_canonical': 'unknown', 'qty_in': 280.0, 'qty_out': 250.0, 'actual_loss_pct': 10.714285714285714, 'predicted_loss_pct': 4.09582778612443, 'abs_error': 6.618457928161283, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mangue', 'process_type': 'livraison', 'stage_canonical': 'unknown', 'qty_in': 245.0, 'qty_out': 220.0, 'actual_loss_pct': 10.204081632653061, 'predicted_loss_pct': 4.1278462358251975, 'abs_error': 6.0762353968278635, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mangue', 'process_type': 'perte_tri', 'stage_canonical': 'unknown', 'qty_in': 100.0, 'qty_out': 90.0, 'actual_loss_pct': 10.0, 'predicted_loss_pct': 4.059821568268997, 'abs_error': 5.940178431731003, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mangue', 'process_type': 'cleaning', 'stage_canonical': 'cleaning', 'qty_in': 250.0, 'qty_out': 230.0, 'actual_loss_pct': 8.0, 'predicted_loss_pct': 3.119886664159623, 'abs_error': 4.880113335840377, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Banane', 'process_type': 'Testing', 'stage_canonical': 'unknown', 'qty_in': 2432.0, 'qty_out': 2420.0, 'actual_loss_pct': 0.4934210526315789, 'predicted_loss_pct': 3.2639378758266178, 'abs_error': 2.770516823195039, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mangue', 'process_type': 'perte_tri', 'stage_canonical': 'unknown', 'qty_in': 300.0, 'qty_out': 280.0, 'actual_loss_pct': 6.666666666666667, 'predicted_loss_pct': 4.027826972590203, 'abs_error': 2.638839694076464, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mangue', 'process_type': 'livraison', 'stage_canonical': 'unknown', 'qty_in': 90.0, 'qty_out': 84.0, 'actual_loss_pct': 6.666666666666667, 'predicted_loss_pct': 4.095827517508808, 'abs_error': 2.570839149157859, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Banane', 'process_type': 'Protection des régimes', 'stage_canonical': 'unknown', 'qty_in': 2488.0, 'qty_out': 2482.0, 'actual_loss_pct': 0.2411575562700965, 'predicted_loss_pct': 2.751955363175742, 'abs_error': 2.5107978069056456, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}]

## Anomaly Review
- No anomaly accuracy is reported (no ground-truth anomaly labels).
- Anomaly review: {'anomaly_accuracy_reported': False, 'note': 'Exploratory only: no labeled anomaly ground truth available.', 'flag_rate': 0.17647058823529413, 'score_negative_rate': 0.17647058823529413, 'flagged_count': 3, 'flagged_high_loss_rate': 0.3333333333333333, 'top_anomaly_examples': [{'product': 'Mangue', 'process_type': 'drying', 'stage_canonical': 'drying', 'actual_loss_pct': 16.52173913043478, 'predicted_loss_pct': 9.219998767703652, 'anomaly_score_raw': -0.10128258026177317, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'actual_loss_pct': 21.999999999999993, 'predicted_loss_pct': 10.928079082057794, 'anomaly_score_raw': -0.08237782150546913, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'cleaning', 'stage_canonical': 'cleaning', 'actual_loss_pct': 8.0, 'predicted_loss_pct': 3.119886664159623, 'anomaly_score_raw': -0.019488957531376694, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'livraison', 'stage_canonical': 'unknown', 'actual_loss_pct': 6.666666666666667, 'predicted_loss_pct': 4.095827517508808, 'anomaly_score_raw': 0.0009073941059013491, 'is_anomalous': False}, {'product': 'Mangue', 'process_type': 'livraison', 'stage_canonical': 'unknown', 'actual_loss_pct': 10.714285714285714, 'predicted_loss_pct': 4.09582778612443, 'anomaly_score_raw': 0.005906331716867941, 'is_anomalous': False}, {'product': 'Mangue', 'process_type': 'perte_tri', 'stage_canonical': 'unknown', 'actual_loss_pct': 10.0, 'predicted_loss_pct': 4.059821568268997, 'anomaly_score_raw': 0.0063537796103045885, 'is_anomalous': False}, {'product': 'Mangue', 'process_type': 'livraison', 'stage_canonical': 'unknown', 'actual_loss_pct': 10.204081632653061, 'predicted_loss_pct': 4.1278462358251975, 'anomaly_score_raw': 0.014199049234841832, 'is_anomalous': False}, {'product': 'Arachide', 'process_type': 'Emballage', 'stage_canonical': 'packaging', 'actual_loss_pct': 0.9995856639734803, 'predicted_loss_pct': 2.4881977191679274, 'anomaly_score_raw': 0.014578392564621345, 'is_anomalous': False}, {'product': 'Mangue', 'process_type': 'perte_tri', 'stage_canonical': 'unknown', 'actual_loss_pct': 6.666666666666667, 'predicted_loss_pct': 4.027826972590203, 'anomaly_score_raw': 0.026681861635924953, 'is_anomalous': False}, {'product': 'Mangue', 'process_type': 'perte_tri', 'stage_canonical': 'unknown', 'actual_loss_pct': 5.769230769230769, 'predicted_loss_pct': 3.875836669656251, 'anomaly_score_raw': 0.04112122095445009, 'is_anomalous': False}]}

## Honest Interpretation
- Regression is mixed versus strong baselines across splits.
- Classification remains weak for medium/high risk recall.
- Current anomaly signals are exploratory only, not validated accuracy.

## Recommended Next Actions
- Improve class balance for medium/high risk.
- Add walk-forward validation and calibration tracking.
- Add labeled anomaly feedback to evaluate precision@k.

# ML Evaluation Report

## Dataset Summary
- Rows: 1517
- Products: {'Mangue': 517, 'Arachide': 500, 'Mil': 492, 'Bissap': 8}
- Raw stages: {'Nettoyage': 384, 'Tri': 380, 'Séchage': 377, 'Emballage': 373, 'Sechage': 2, 'Conditionnement': 1}
- Canonical stages: {'cleaning': 384, 'sorting': 380, 'drying': 379, 'packaging': 374}
- Risk classes: {'low': 1258, 'medium': 206, 'high': 53}

## Split Strategy
- Time-based split: train=1388, test=129
- Random split: train=1213, test=304

## Regression Evaluation
- Time split model MAE: 4.0150
- Time split model RMSE: 7.2806
- Time split model R2: 0.06511232771235986

## Baseline Comparison
- global_mean_loss: MAE=4.8505, RMSE=7.5332, MAE delta vs model=0.8355
- product_mean_loss: MAE=4.8484, RMSE=7.5327, MAE delta vs model=0.8334
- stage_mean_loss: MAE=3.5434, RMSE=6.4664, MAE delta vs model=-0.4716
- product_stage_mean_loss: MAE=3.5471, RMSE=6.4737, MAE delta vs model=-0.4680
- stage_season_mean_loss: MAE=3.4808, RMSE=6.4646, MAE delta vs model=-0.5342
- product_stage_season_mean_loss: MAE=3.4671, RMSE=6.4086, MAE delta vs model=-0.5479
- product_stage_rolling_mean_loss: MAE=3.7001, RMSE=7.0256, MAE delta vs model=-0.3149
- previous_batch_loss_baseline: MAE=5.1934, RMSE=8.3642, MAE delta vs model=1.1784

## Classification Evaluation
- Model accuracy=0.8295, macro-F1=0.4435, weighted-F1=0.8085
- Per-class: {'low': {'precision': 0.8782608695652174, 'recall': 0.926605504587156, 'f1': 0.9017857142857143, 'support': 109}, 'medium': {'precision': 0.42857142857142855, 'recall': 0.42857142857142855, 'f1': 0.42857142857142855, 'support': 14}, 'high': {'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'support': 6}}
- Confusion matrix: [[101, 8, 0], [8, 6, 0], [6, 0, 0]]
- Medium recall: 0.4286, High recall: 0.0000, False-low high-risk rate: 1.0000
- Thresholded risk method: {'low_to_medium': 6.0, 'medium_to_high': 12.0}

## Segment Analysis
- Product segments: [{'product': 'Mangue', 'row_count': 45, 'mae': 3.043386660261299, 'mean_actual_loss_pct': 6.404782235779806, 'mean_predicted_loss_pct': 7.143515543085264, 'error_bias': 0.7387333073054552}, {'product': 'Arachide', 'row_count': 40, 'mae': 3.8092874823052996, 'mean_actual_loss_pct': 6.120676167896916, 'mean_predicted_loss_pct': 6.607160574365983, 'error_bias': 0.48648440646906793}, {'product': 'Mil', 'row_count': 36, 'mae': 3.4246470686852892, 'mean_actual_loss_pct': 5.936198504900651, 'mean_predicted_loss_pct': 7.337143954631407, 'error_bias': 1.4009454497307554}, {'product': 'Bissap', 'row_count': 8, 'mae': 13.166006501704697, 'mean_actual_loss_pct': 10.270737461352653, 'mean_predicted_loss_pct': 7.889633116688842, 'error_bias': -2.38110434466381}]
- Canonical stage segments: [{'stage_canonical': 'cleaning', 'row_count': 36, 'mae': 1.6396196725116132, 'mean_actual_loss_pct': 2.862123784988984, 'mean_predicted_loss_pct': 3.200953531035015, 'error_bias': 0.3388297460460309}, {'stage_canonical': 'sorting', 'row_count': 34, 'mae': 5.961303898481465, 'mean_actual_loss_pct': 8.458881680825268, 'mean_predicted_loss_pct': 9.731139622094737, 'error_bias': 1.2722579412694701}, {'stage_canonical': 'drying', 'row_count': 31, 'mae': 6.4718888676636, 'mean_actual_loss_pct': 11.858050506428235, 'mean_predicted_loss_pct': 12.420748633437194, 'error_bias': 0.5626981270089588}, {'stage_canonical': 'packaging', 'row_count': 28, 'mae': 1.9857160654971031, 'mean_actual_loss_pct': 2.5240462173669553, 'mean_predicted_loss_pct': 2.9236638503101013, 'error_bias': 0.39961763294314606}]

## Top Prediction Errors
- Top 10 errors: [{'product': 'Bissap', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'qty_in': 150.0, 'qty_out': 48.0, 'actual_loss_pct': 68.0, 'predicted_loss_pct': 5.811556614525986, 'abs_error': 62.18844338547402, 'actual_risk_level': 'high', 'predicted_risk_level': 'low'}, {'product': 'Arachide', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 980.1, 'qty_out': 965.4, 'actual_loss_pct': 1.4998469543924136, 'predicted_loss_pct': 15.508610121965, 'abs_error': 14.008763167572587, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Arachide', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 563.907, 'qty_out': 446.643, 'actual_loss_pct': 20.7949183109981, 'predicted_loss_pct': 6.809708492414555, 'abs_error': 13.985209818583545, 'actual_risk_level': 'high', 'predicted_risk_level': 'low'}, {'product': 'Arachide', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 553.382, 'qty_out': 449.44, 'actual_loss_pct': 18.78304679227007, 'predicted_loss_pct': 7.875833757625601, 'abs_error': 10.907213034644471, 'actual_risk_level': 'high', 'predicted_risk_level': 'low'}, {'product': 'Mil', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'qty_in': 842.8, 'qty_out': 809.09, 'actual_loss_pct': 3.999762695775976, 'predicted_loss_pct': 14.86491206324362, 'abs_error': 10.865149367467644, 'actual_risk_level': 'low', 'predicted_risk_level': 'medium'}, {'product': 'Mangue', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 608.007, 'qty_out': 491.223, 'actual_loss_pct': 19.2076735958632, 'predicted_loss_pct': 8.474980220897956, 'abs_error': 10.732693374965242, 'actual_risk_level': 'high', 'predicted_risk_level': 'low'}, {'product': 'Bissap', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 673.2, 'qty_out': 659.74, 'actual_loss_pct': 1.99940582293524, 'predicted_loss_pct': 12.456686400469652, 'abs_error': 10.457280577534412, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mangue', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'qty_in': 99.0, 'qty_out': 94.0, 'actual_loss_pct': 5.05050505050505, 'predicted_loss_pct': 15.455598627421047, 'abs_error': 10.405093576915997, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Arachide', 'process_type': 'Conditionnement', 'stage_canonical': 'packaging', 'qty_in': 756.76, 'qty_out': 741.62, 'actual_loss_pct': 2.0006342829959283, 'predicted_loss_pct': 11.976595893912988, 'abs_error': 9.975961610917059, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mil', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 809.09, 'qty_out': 784.82, 'actual_loss_pct': 2.999666291759876, 'predicted_loss_pct': 12.253978164372567, 'abs_error': 9.254311872612691, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}]

## Anomaly Review
- No anomaly accuracy is reported (no ground-truth anomaly labels).
- Anomaly review: {'anomaly_accuracy_reported': False, 'note': 'Exploratory only: no labeled anomaly ground truth available.', 'flag_rate': 0.20155038759689922, 'score_negative_rate': 0.20155038759689922, 'flagged_count': 26, 'flagged_high_loss_rate': 0.11538461538461539, 'top_anomaly_examples': [{'product': 'Bissap', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'actual_loss_pct': 68.0, 'predicted_loss_pct': 5.811556614525986, 'anomaly_score_raw': -0.10257206723600798, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'actual_loss_pct': 5.05050505050505, 'predicted_loss_pct': 15.455598627421047, 'anomaly_score_raw': -0.06359556271956801, 'is_anomalous': True}, {'product': 'Bissap', 'process_type': 'Nettoyage', 'stage_canonical': 'cleaning', 'actual_loss_pct': 0.0, 'predicted_loss_pct': 5.448347847327337, 'anomaly_score_raw': -0.06260407871826446, 'is_anomalous': True}, {'product': 'Bissap', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 4.166666666666666, 'predicted_loss_pct': 12.140314628809962, 'anomaly_score_raw': -0.06206319895857593, 'is_anomalous': True}, {'product': 'Bissap', 'process_type': 'Emballage', 'stage_canonical': 'packaging', 'actual_loss_pct': 1.0003940946433478, 'predicted_loss_pct': 6.35477034043263, 'anomaly_score_raw': -0.0555767377316323, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'actual_loss_pct': 21.999999999999993, 'predicted_loss_pct': 16.428151129056822, 'anomaly_score_raw': -0.044025250910818436, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Nettoyage', 'stage_canonical': 'cleaning', 'actual_loss_pct': 1.0, 'predicted_loss_pct': 3.309967463524896, 'anomaly_score_raw': -0.04131571066448769, 'is_anomalous': True}, {'product': 'Arachide', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 1.4998469543924136, 'predicted_loss_pct': 15.508610121965, 'anomaly_score_raw': -0.03094490228860236, 'is_anomalous': True}, {'product': 'Bissap', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 3.999433106575968, 'predicted_loss_pct': 11.338123054073087, 'anomaly_score_raw': -0.030495083005661283, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 4.000336398295598, 'predicted_loss_pct': 12.443881530774565, 'anomaly_score_raw': -0.029804908466455338, 'is_anomalous': True}]}

## Honest Interpretation
- Regression is mixed versus strong baselines across splits.
- Classification remains weak for medium/high risk recall.
- Current anomaly signals are exploratory only, not validated accuracy.

## Recommended Next Actions
- Improve class balance for medium/high risk.
- Add walk-forward validation and calibration tracking.
- Add labeled anomaly feedback to evaluate precision@k.

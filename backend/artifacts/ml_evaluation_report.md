# ML Evaluation Report

## Dataset Summary
- Rows: 485
- Products: {'Mangue': 170, 'Arachide': 156, 'Mil': 156, 'Bissap': 3}
- Raw stages: {'Nettoyage': 122, 'Tri': 121, 'Séchage': 120, 'Emballage': 120, 'Sechage': 2}
- Canonical stages: {'cleaning': 122, 'drying': 122, 'sorting': 121, 'packaging': 120}
- Risk classes: {'low': 402, 'medium': 68, 'high': 15}

## Split Strategy
- Time-based split: train=396, test=89
- Random split: train=388, test=97

## Regression Evaluation
- Time split model MAE: 3.7337
- Time split model RMSE: 8.0330
- Time split model R2: -0.05877735050456079

## Baseline Comparison
- global_mean_loss: MAE=4.3505, RMSE=7.8213, MAE delta vs model=0.6168
- product_mean_loss: MAE=4.3639, RMSE=7.8361, MAE delta vs model=0.6302
- stage_mean_loss: MAE=2.5950, RMSE=6.5485, MAE delta vs model=-1.1387
- product_stage_mean_loss: MAE=2.6798, RMSE=6.5665, MAE delta vs model=-1.0539
- previous_batch_loss_baseline: MAE=4.5028, RMSE=7.6312, MAE delta vs model=0.7691

## Classification Evaluation
- Model accuracy=0.8989, macro-F1=0.3156, weighted-F1=0.8616
- Per-class: {'low': {'precision': 0.9090909090909091, 'recall': 0.9876543209876543, 'f1': 0.9467455621301775, 'support': 81}, 'medium': {'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'support': 6}, 'high': {'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'support': 2}}
- Confusion matrix: [[80, 0, 1], [6, 0, 0], [2, 0, 0]]

## Segment Analysis
- Product segments: [{'product': 'Mangue', 'row_count': 35, 'mae': 3.216881379261151, 'mean_actual_loss_pct': 5.62582674536926, 'mean_predicted_loss_pct': 8.638411912165065, 'error_bias': 3.0125851667958052}, {'product': 'Mil', 'row_count': 27, 'mae': 3.2635366198799893, 'mean_actual_loss_pct': 5.482670264697098, 'mean_predicted_loss_pct': 7.4717893164218605, 'error_bias': 1.9891190517247639}, {'product': 'Arachide', 'row_count': 24, 'mae': 2.4558496092320286, 'mean_actual_loss_pct': 6.2273562334600046, 'mean_predicted_loss_pct': 7.757805375859214, 'error_bias': 1.5304491423992095}, {'product': 'Bissap', 'row_count': 3, 'mae': 24.217490072529074, 'mean_actual_loss_pct': 24.055555555555557, 'mean_predicted_loss_pct': 4.8028351051616545, 'error_bias': -19.2527204503939}]
- Canonical stage segments: [{'stage_canonical': 'packaging', 'row_count': 24, 'mae': 1.577732590518578, 'mean_actual_loss_pct': 1.598360858976794, 'mean_predicted_loss_pct': 3.1600305404853337, 'error_bias': 1.5616696815085398}, {'stage_canonical': 'drying', 'row_count': 23, 'mae': 7.369653321256038, 'mean_actual_loss_pct': 12.177439171750025, 'mean_predicted_loss_pct': 13.394867148440724, 'error_bias': 1.2174279766907004}, {'stage_canonical': 'sorting', 'row_count': 22, 'mae': 4.618911714751689, 'mean_actual_loss_pct': 8.545732254809861, 'mean_predicted_loss_pct': 11.731432700801962, 'error_bias': 3.185700445992099}, {'stage_canonical': 'cleaning', 'row_count': 20, 'mae': 1.1657765782092004, 'mean_actual_loss_pct': 3.005568916647093, 'mean_predicted_loss_pct': 3.133218300092287, 'error_bias': 0.1276493834451934}]

## Top Prediction Errors
- Top 10 errors: [{'product': 'Bissap', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'qty_in': 150.0, 'qty_out': 48.0, 'actual_loss_pct': 68.0, 'predicted_loss_pct': 2.7946842156155336, 'abs_error': 65.20531578438447, 'actual_risk_level': 'high', 'predicted_risk_level': 'low'}, {'product': 'Mil', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 685.989, 'qty_out': 538.919, 'actual_loss_pct': 21.439119286169316, 'predicted_loss_pct': 9.813322588208312, 'abs_error': 11.625796697961004, 'actual_risk_level': 'high', 'predicted_risk_level': 'low'}, {'product': 'Mil', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'qty_in': 569.625, 'qty_out': 528.022, 'actual_loss_pct': 7.303576914636814, 'predicted_loss_pct': 18.527153794343516, 'abs_error': 11.223576879706702, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mil', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'qty_in': 569.625, 'qty_out': 528.022, 'actual_loss_pct': 7.303576914636814, 'predicted_loss_pct': 18.005281025298544, 'abs_error': 10.70170411066173, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mil', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 528.022, 'qty_out': 492.774, 'actual_loss_pct': 6.6754794307813015, 'predicted_loss_pct': 15.599079422459464, 'abs_error': 8.923599991678163, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mangue', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'qty_in': 927.08, 'qty_out': 864.584, 'actual_loss_pct': 6.741165810933262, 'predicted_loss_pct': 15.636833763940734, 'abs_error': 8.895667953007472, 'actual_risk_level': 'low', 'predicted_risk_level': 'high'}, {'product': 'Mil', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 528.022, 'qty_out': 492.774, 'actual_loss_pct': 6.6754794307813015, 'predicted_loss_pct': 15.515155417145886, 'abs_error': 8.839675986364584, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mangue', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'qty_in': 467.542, 'qty_out': 432.708, 'actual_loss_pct': 7.450453649083921, 'predicted_loss_pct': 16.02493282510008, 'abs_error': 8.574479176016158, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mangue', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'qty_in': 467.542, 'qty_out': 432.708, 'actual_loss_pct': 7.450453649083921, 'predicted_loss_pct': 15.905452955887835, 'abs_error': 8.454999306803913, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mangue', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'qty_in': 99.0, 'qty_out': 94.0, 'actual_loss_pct': 5.05050505050505, 'predicted_loss_pct': 12.917493033677877, 'abs_error': 7.866987983172827, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}]

## Anomaly Review
- No anomaly accuracy is reported (no ground-truth anomaly labels).
- Anomaly review: {'anomaly_accuracy_reported': False, 'note': 'Exploratory only: no labeled anomaly ground truth available.', 'flag_rate': 0.43820224719101125, 'score_negative_rate': 0.43820224719101125, 'flagged_count': 39, 'flagged_high_loss_rate': 0.05128205128205128, 'top_anomaly_examples': [{'product': 'Bissap', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'actual_loss_pct': 68.0, 'predicted_loss_pct': 2.7946842156155336, 'anomaly_score_raw': -0.0901226916491048, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'actual_loss_pct': 5.05050505050505, 'predicted_loss_pct': 12.917493033677877, 'anomaly_score_raw': -0.03791714526662271, 'is_anomalous': True}, {'product': 'Bissap', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 4.166666666666666, 'predicted_loss_pct': 8.870954838955212, 'anomaly_score_raw': -0.03757633365333357, 'is_anomalous': True}, {'product': 'Arachide', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'actual_loss_pct': 15.597041527796138, 'predicted_loss_pct': 12.682699480311076, 'anomaly_score_raw': -0.03509854439302551, 'is_anomalous': True}, {'product': 'Mil', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 21.439119286169316, 'predicted_loss_pct': 9.813322588208312, 'anomaly_score_raw': -0.03328992971040423, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'actual_loss_pct': 4.932774399190942, 'predicted_loss_pct': 11.95939143197987, 'anomaly_score_raw': -0.029358167233791033, 'is_anomalous': True}, {'product': 'Arachide', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'actual_loss_pct': 15.597041527796138, 'predicted_loss_pct': 14.666128086653263, 'anomaly_score_raw': -0.023617698334422732, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Nettoyage', 'stage_canonical': 'cleaning', 'actual_loss_pct': 1.2912832797345084, 'predicted_loss_pct': 3.2879211655294904, 'anomaly_score_raw': -0.023347446928686733, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'actual_loss_pct': 12.161491489762073, 'predicted_loss_pct': 10.525355688512246, 'anomaly_score_raw': -0.02321967990904583, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'actual_loss_pct': 10.770692447108694, 'predicted_loss_pct': 13.429208300259313, 'anomaly_score_raw': -0.023096511791517726, 'is_anomalous': True}]}

## Honest Interpretation
- Regression is mixed versus strong baselines across splits.
- Classification remains weak for medium/high risk recall.
- Current anomaly signals are exploratory only, not validated accuracy.

## Recommended Next Actions
- Improve class balance for medium/high risk.
- Add walk-forward validation and calibration tracking.
- Add labeled anomaly feedback to evaluate precision@k.

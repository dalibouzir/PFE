# ML Evaluation Report

## Dataset Summary
- Rows: 1485
- Products: {'Mangue': 506, 'Arachide': 492, 'Mil': 484, 'Bissap': 3}
- Raw stages: {'Nettoyage': 372, 'Tri': 371, 'Séchage': 370, 'Emballage': 370, 'Sechage': 2}
- Canonical stages: {'cleaning': 372, 'drying': 372, 'sorting': 371, 'packaging': 370}
- Risk classes: {'low': 1229, 'medium': 204, 'high': 52}

## Split Strategy
- Time-based split: train=1210, test=275
- Random split: train=1188, test=297

## Regression Evaluation
- Time split model MAE: 3.7800
- Time split model RMSE: 5.8916
- Time split model R2: 0.09237794471494543

## Baseline Comparison
- global_mean_loss: MAE=4.3716, RMSE=6.1991, MAE delta vs model=0.5916
- product_mean_loss: MAE=4.3720, RMSE=6.2026, MAE delta vs model=0.5920
- stage_mean_loss: MAE=2.6695, RMSE=4.8680, MAE delta vs model=-1.1105
- product_stage_mean_loss: MAE=2.6757, RMSE=4.8844, MAE delta vs model=-1.1043
- stage_season_mean_loss: MAE=2.7470, RMSE=4.9083, MAE delta vs model=-1.0329
- product_stage_season_mean_loss: MAE=2.7622, RMSE=4.9118, MAE delta vs model=-1.0178
- product_stage_rolling_mean_loss: MAE=2.9341, RMSE=5.2690, MAE delta vs model=-0.8459
- previous_batch_loss_baseline: MAE=4.6465, RMSE=6.4654, MAE delta vs model=0.8665

## Classification Evaluation
- Model accuracy=0.8400, macro-F1=0.3043, weighted-F1=0.7802
- Per-class: {'low': {'precision': 0.8523985239852399, 'recall': 0.9829787234042553, 'f1': 0.9130434782608695, 'support': 235}, 'medium': {'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'support': 32}, 'high': {'precision': 0.0, 'recall': 0.0, 'f1': 0.0, 'support': 8}}
- Confusion matrix: [[231, 4, 0], [32, 0, 0], [8, 0, 0]]
- Medium recall: 0.0000, High recall: 0.0000, False-low high-risk rate: 1.0000
- Thresholded risk method: {'low_to_medium': 6.0, 'medium_to_high': 12.0}

## Segment Analysis
- Product segments: [{'product': 'Mangue', 'row_count': 96, 'mae': 3.226396569852566, 'mean_actual_loss_pct': 5.879957574581714, 'mean_predicted_loss_pct': 8.677775316575959, 'error_bias': 2.7978177419942427}, {'product': 'Arachide', 'row_count': 90, 'mae': 3.6067601350128364, 'mean_actual_loss_pct': 6.255062320322709, 'mean_predicted_loss_pct': 8.597027392545344, 'error_bias': 2.3419650722226355}, {'product': 'Mil', 'row_count': 86, 'mae': 3.837041770765675, 'mean_actual_loss_pct': 6.305637874520992, 'mean_predicted_loss_pct': 8.672465848829313, 'error_bias': 2.366827974308321}, {'product': 'Bissap', 'row_count': 3, 'mae': 25.056794212103267, 'mean_actual_loss_pct': 24.055555555555557, 'mean_predicted_loss_pct': 8.046290200293576, 'error_bias': -16.00926535526198}]
- Canonical stage segments: [{'stage_canonical': 'packaging', 'row_count': 71, 'mae': 2.6660949905106217, 'mean_actual_loss_pct': 2.0189611090944406, 'mean_predicted_loss_pct': 4.343178141416323, 'error_bias': 2.324217032321882}, {'stage_canonical': 'sorting', 'row_count': 70, 'mae': 5.634922050186479, 'mean_actual_loss_pct': 9.202757607874915, 'mean_predicted_loss_pct': 13.03459525065628, 'error_bias': 3.8318376427813647}, {'stage_canonical': 'drying', 'row_count': 68, 'mae': 5.543396863538299, 'mean_actual_loss_pct': 11.0325678526367, 'mean_predicted_loss_pct': 13.825671344999293, 'error_bias': 2.793103492362598}, {'stage_canonical': 'cleaning', 'row_count': 66, 'mae': 1.194093685140109, 'mean_actual_loss_pct': 3.0928662816381163, 'mean_predicted_loss_pct': 3.2702554890018782, 'error_bias': 0.17738920736376299}]

## Top Prediction Errors
- Top 10 errors: [{'product': 'Bissap', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'qty_in': 150.0, 'qty_out': 48.0, 'actual_loss_pct': 68.0, 'predicted_loss_pct': 6.400910648952135, 'abs_error': 61.599089351047866, 'actual_risk_level': 'high', 'predicted_risk_level': 'low'}, {'product': 'Mil', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 811.611, 'qty_out': 611.665, 'actual_loss_pct': 24.635693700553592, 'predicted_loss_pct': 9.889765212210795, 'abs_error': 14.745928488342797, 'actual_risk_level': 'high', 'predicted_risk_level': 'low'}, {'product': 'Mangue', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 783.9, 'qty_out': 756.373, 'actual_loss_pct': 3.51154483990304, 'predicted_loss_pct': 14.33994167000864, 'abs_error': 10.8283968301056, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mangue', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 827.463, 'qty_out': 800.102, 'actual_loss_pct': 3.306613105359393, 'predicted_loss_pct': 13.881139562144872, 'abs_error': 10.57452645678548, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Arachide', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 443.488, 'qty_out': 423.878, 'actual_loss_pct': 4.421765639656544, 'predicted_loss_pct': 14.985097947533832, 'abs_error': 10.563332307877289, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mangue', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'qty_in': 877.503, 'qty_out': 827.463, 'actual_loss_pct': 5.702544606685113, 'predicted_loss_pct': 15.989262940552129, 'abs_error': 10.286718333867015, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Arachide', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 514.371, 'qty_out': 497.182, 'actual_loss_pct': 3.341751381784736, 'predicted_loss_pct': 13.566177869077602, 'abs_error': 10.224426487292867, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mangue', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'qty_in': 927.08, 'qty_out': 864.584, 'actual_loss_pct': 6.741165810933262, 'predicted_loss_pct': 16.83270028404427, 'abs_error': 10.09153447311101, 'actual_risk_level': 'low', 'predicted_risk_level': 'medium'}, {'product': 'Mil', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'qty_in': 439.889, 'qty_out': 421.387, 'actual_loss_pct': 4.206061074498342, 'predicted_loss_pct': 14.225679667092859, 'abs_error': 10.019618592594517, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}, {'product': 'Mil', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'qty_in': 862.104, 'qty_out': 838.751, 'actual_loss_pct': 2.70883791282723, 'predicted_loss_pct': 12.691348391187587, 'abs_error': 9.982510478360357, 'actual_risk_level': 'low', 'predicted_risk_level': 'low'}]

## Anomaly Review
- No anomaly accuracy is reported (no ground-truth anomaly labels).
- Anomaly review: {'anomaly_accuracy_reported': False, 'note': 'Exploratory only: no labeled anomaly ground truth available.', 'flag_rate': 0.12727272727272726, 'score_negative_rate': 0.12727272727272726, 'flagged_count': 35, 'flagged_high_loss_rate': 0.17142857142857143, 'top_anomaly_examples': [{'product': 'Bissap', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'actual_loss_pct': 68.0, 'predicted_loss_pct': 6.400910648952135, 'anomaly_score_raw': -0.07873816614643969, 'is_anomalous': True}, {'product': 'Bissap', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 4.166666666666666, 'predicted_loss_pct': 13.32682554023867, 'anomaly_score_raw': -0.04791127724235722, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Sechage', 'stage_canonical': 'drying', 'actual_loss_pct': 5.05050505050505, 'predicted_loss_pct': 11.392018827310311, 'anomaly_score_raw': -0.04234156650549059, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Emballage', 'stage_canonical': 'packaging', 'actual_loss_pct': 0.8085323693688156, 'predicted_loss_pct': 4.683029261807536, 'anomaly_score_raw': -0.024150883141161872, 'is_anomalous': True}, {'product': 'Arachide', 'process_type': 'Emballage', 'stage_canonical': 'packaging', 'actual_loss_pct': 8.737641832782701, 'predicted_loss_pct': 4.576124608073517, 'anomaly_score_raw': -0.020347717537753218, 'is_anomalous': True}, {'product': 'Bissap', 'process_type': 'Nettoyage', 'stage_canonical': 'cleaning', 'actual_loss_pct': 0.0, 'predicted_loss_pct': 4.411134411689923, 'anomaly_score_raw': -0.01945343038555425, 'is_anomalous': True}, {'product': 'Arachide', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 9.035544988702974, 'predicted_loss_pct': 13.686128319275905, 'anomaly_score_raw': -0.01795400515882528, 'is_anomalous': True}, {'product': 'Arachide', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'actual_loss_pct': 11.857470871135606, 'predicted_loss_pct': 14.150902201346197, 'anomaly_score_raw': -0.01503472651993587, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Emballage', 'stage_canonical': 'packaging', 'actual_loss_pct': 2.836534151467769, 'predicted_loss_pct': 3.943295015086354, 'anomaly_score_raw': -0.014783292747234444, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Emballage', 'stage_canonical': 'packaging', 'actual_loss_pct': 1.8851964875714389, 'predicted_loss_pct': 5.192957059927536, 'anomaly_score_raw': -0.013716245968118268, 'is_anomalous': True}]}

## Honest Interpretation
- Regression is mixed versus strong baselines across splits.
- Classification remains weak for medium/high risk recall.
- Current anomaly signals are exploratory only, not validated accuracy.

## Recommended Next Actions
- Improve class balance for medium/high risk.
- Add walk-forward validation and calibration tracking.
- Add labeled anomaly feedback to evaluate precision@k.

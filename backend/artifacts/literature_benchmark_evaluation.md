# Literature-Informed Benchmark Evaluation

## Purpose
This benchmark tests model potential under source-informed post-harvest distributions.
It does NOT represent real cooperative operational accuracy.

## Benchmark Dataset Summary
- Rows: 3000
- Product distribution: {'Arachide': 1052, 'Mil': 980, 'Mangue': 968}
- Raw stage distribution: {'Nettoyage': 750, 'Séchage': 750, 'Tri': 750, 'Emballage': 750}
- Canonical stage distribution: {'cleaning': 750, 'drying': 750, 'sorting': 750, 'packaging': 750}
- Risk class distribution: {'low': 2650, 'medium': 287, 'high': 63}

## Baseline Comparison
- Model MAE (time split): 2.5791
- Beats baselines: ['global_mean_loss', 'product_mean_loss', 'previous_batch_loss_baseline']
- Loses to baselines: ['stage_mean_loss', 'product_stage_mean_loss', 'stage_season_mean_loss', 'product_stage_season_mean_loss', 'product_stage_rolling_mean_loss']

## Risk Detection Evaluation
- RF classifier macro-F1: 0.3343, medium recall: 0.0423, high recall: 0.0000
- Thresholded predicted-loss macro-F1: 0.3622, false-low high-risk rate: 0.0000

## Anomaly Review
- Exploratory only: no anomaly accuracy claim (no ground-truth anomaly labels).
- Summary: {'anomaly_accuracy_reported': False, 'note': 'Exploratory only: no labeled anomaly ground truth available.', 'flag_rate': 0.12709030100334448, 'score_negative_rate': 0.12709030100334448, 'flagged_count': 76, 'flagged_high_loss_rate': 0.09210526315789473, 'top_anomaly_examples': [{'product': 'Arachide', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'actual_loss_pct': 4.45313714315321, 'predicted_loss_pct': 10.788394799036581, 'anomaly_score_raw': -0.04622932891704745, 'is_anomalous': True}, {'product': 'Arachide', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'actual_loss_pct': 17.705359344058913, 'predicted_loss_pct': 10.999403427211465, 'anomaly_score_raw': -0.04112865707102509, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 15.106500106905612, 'predicted_loss_pct': 13.820278061168374, 'anomaly_score_raw': -0.039133553842842894, 'is_anomalous': True}, {'product': 'Arachide', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 11.178979088314012, 'predicted_loss_pct': 11.474712104824722, 'anomaly_score_raw': -0.03616715673798099, 'is_anomalous': True}, {'product': 'Arachide', 'process_type': 'Tri', 'stage_canonical': 'sorting', 'actual_loss_pct': 14.016027290363569, 'predicted_loss_pct': 13.99348922089224, 'anomaly_score_raw': -0.03606015077859037, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'actual_loss_pct': 8.449176870544632, 'predicted_loss_pct': 16.853291337456668, 'anomaly_score_raw': -0.0314348391400644, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'actual_loss_pct': 16.342416309693792, 'predicted_loss_pct': 15.929301323651856, 'anomaly_score_raw': -0.02988706297715471, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'actual_loss_pct': 14.732908744800369, 'predicted_loss_pct': 15.06006803914298, 'anomaly_score_raw': -0.028752344455265866, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'actual_loss_pct': 13.055031164103836, 'predicted_loss_pct': 15.5637703125342, 'anomaly_score_raw': -0.027630905564980046, 'is_anomalous': True}, {'product': 'Mangue', 'process_type': 'Séchage', 'stage_canonical': 'drying', 'actual_loss_pct': 8.19596875199015, 'predicted_loss_pct': 15.566835100338567, 'anomaly_score_raw': -0.026105358073142182, 'is_anomalous': True}]}

## Interpretation
- Results indicate architecture behavior under literature-informed benchmark conditions only.
- This benchmark cannot be used as proof of production readiness or real-world accuracy.

## PFE Report Wording
We trained and evaluated the ML pipeline on a literature-informed benchmark dataset calibrated from APHLIS, Senegal mango/groundnut references, and contextual sources. The benchmark is useful to test architecture potential under plausible distributions, but it does not replace real cooperative operational data and cannot be used to claim production accuracy.

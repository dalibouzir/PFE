# SYNTHETIC BENCHMARK — NOT REAL APP PERFORMANCE. These metrics evaluate pipeline behavior under controlled simulated data and must not be reported as production model accuracy.

## Dataset
- Source: synthetic
- Row count: 2000
- Crops: arachide, mangue, mil
- Stages: emballage, nettoyage, sechage, tri
- Data origin: SYNTHETIC_BENCHMARK

## Generation Assumptions
- Drying sensitivity: sensitive to humidity/rainfall/duration/delay
- Sorting sensitivity: depends on grade and product quality
- Noise: gaussian and random shocks
- Anomalies: explicitly injected and labeled as synthetic

## Time Split (Primary)
- Regression MAE (model): 3.6455
- Best baseline: stage_mean_loss (MAE 2.6350)
- Model beats best baseline: False
- Classification macro-F1 (model): 0.5977
- Classification macro-F1 (majority baseline): 0.2773

## Random Split (Secondary)
- Regression MAE (model): 2.9585
- Classification macro-F1 (model): 0.6140

## Anomaly Metrics (Synthetic Labels Only)
- Label type: synthetic_anomaly_labels_only
- Precision: 0.0189
- Recall: 0.0345
- F1: 0.0244

## Scope Boundary
- Not mixed with Supabase app data.
- Not used for production promotion.
- Not a substitute for real app deployment evidence.

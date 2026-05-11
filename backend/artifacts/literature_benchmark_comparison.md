# Literature-Informed Benchmark Evaluation

## Purpose
Compare current demo/app results with benchmark-data results to isolate architecture-vs-data effects.

## Sources Used
See artifacts/benchmark_sources.md and artifacts/benchmark_sources.json for source mapping and reliability notes.

## Dataset Methodology
See artifacts/literature_benchmark_methodology.md.

## Benchmark Dataset Summary
- Rows: 3000
- Risk distribution: {'low': 2650, 'medium': 287, 'high': 63}

## Current Demo/App Model Results
- Report path: artifacts/ml_evaluation_final.json
- Regression MAE=3.7800, RMSE=5.8916, R2=0.09237794471494543
- Classifier macro-F1=0.3043, medium recall=0.0000, high recall=0.0000

## Benchmark Model Results
- Regression MAE=2.5791, RMSE=3.4462, R2=0.4513120599440301
- RF classifier macro-F1=0.3343, medium recall=0.0423, high recall=0.0000
- Thresholded-risk macro-F1=0.3622, false-low high-risk rate=0.0000

## Baseline Comparison
- Beats baselines: ['global_mean_loss', 'product_mean_loss', 'previous_batch_loss_baseline']
- Loses to baselines: ['stage_mean_loss', 'product_stage_mean_loss', 'stage_season_mean_loss', 'product_stage_season_mean_loss', 'product_stage_rolling_mean_loss']

## Risk Detection Evaluation
- Focus metric for safety: false_low_high_risk_rate.
- Served risk should remain thresholded_predicted_loss unless classifier materially improves medium/high recall.

## Anomaly Review
- Exploratory only; no anomaly accuracy claim without labels.

## Interpretation
- Architecture potential can improve under richer distributions, but this does not prove operational generalization.
- Production validation still requires real cooperative data and feedback labels.
- Can this benchmark be used as proof of production accuracy? NO.

## PFE Report Wording
In addition to the app dataset, we built a literature-informed benchmark dataset from APHLIS and crop-specific references to test ML architecture behavior under realistic post-harvest distributions. Benchmark gains are informative for model potential, but they are not evidence of production accuracy because the benchmark is synthetic and not real cooperative operational history.

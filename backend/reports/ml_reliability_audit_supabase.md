# WeeFarm ML Reliability Audit

## Data Source
- Label: supabase
- Identifier: aws-0-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require
- Fallback used: False
- Generated at: 2026-05-17T01:28:20.671879+00:00
- Python runtime: 3.11.12

## Dataset
- Rows: 45

## Time Split (Primary)
- Regression model MAE: 3.7136
- Best baseline MAE (product_stage_mean_loss): 3.8362
- Regression relative improvement vs best baseline: 3.20%
- Regression numeric winner: model
- Regression gate status (>=10% required): FAIL
- Regression promoted decision: baseline:product_stage_mean_loss
- Classification model macro-F1: 0.3125
- Best threshold baseline macro-F1 (thresholded_predicted_loss_baseline): 0.5556
- Classification relative improvement vs best threshold baseline: -77.78%
- Classification gate status (>=10% required): FAIL
- Classification promoted decision: threshold_baseline:thresholded_predicted_loss_baseline

## Random Split (Secondary)
- Regression model MAE: 2.2065
- Classification model macro-F1: 0.4706

## Baseline Comparison (Time Split)
| Baseline | MAE | Delta vs model MAE | Model beats baseline |
| --- | ---: | ---: | :---: |
| product_stage_mean_loss | 3.8362 | 0.1226 | YES |
| product_stage_season_mean_loss | 3.9792 | 0.2656 | YES |
| product_stage_rolling_mean_loss | 4.0380 | 0.3244 | YES |
| stage_mean_loss | 4.1507 | 0.4371 | YES |
| stage_season_mean_loss | 4.2478 | 0.5342 | YES |
| product_mean_loss | 4.3362 | 0.6226 | YES |
| global_mean_loss | 4.9792 | 1.2656 | YES |
| previous_batch_loss_baseline | 5.5284 | 1.8148 | YES |

## Classification Baseline Comparison (Time Split)
| Candidate | Macro-F1 |
| --- | ---: |
| model | 0.3125 |
| thresholded_predicted_loss_baseline | 0.5556 |
| thresholded_product_stage_average_baseline | 0.5556 |

## Gate Results
- Regression gate: FAIL
- Classification gate: FAIL
- Anomaly gate: EXPLORATORY
- Recommendation policy gate: RULE_BASED

## Selection Decision
- Regression decision: baseline:product_stage_mean_loss
- Classification decision: threshold_baseline:thresholded_predicted_loss_baseline
- Anomaly decision: exploratory_only
- Recommendation decision: rule_engine_templates

## PFE Report Claims
Can claim:
- Classification ML does not beat threshold baselines yet (delta -77.78% on macro-F1, time split).
- Anomaly outputs are operational signals only (not supervised-validated accuracy).
- Recommendation generation is currently rule-based template logic.
Cannot claim:
- Reliable regression superiority over strong statistical baselines for loss prediction.
- Validated anomaly detection accuracy without labeled anomaly ground truth.
- ML-ranked recommendation policy effectiveness without action/outcome feedback evidence.

## Honest Verdict
Current Supabase snapshot is not promotion-ready: regression does not pass the 10% gate against the strongest baseline, classification fails its threshold-baseline gate, anomaly is exploratory, and recommendation remains rule-based.
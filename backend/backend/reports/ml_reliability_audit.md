# WeeFarm ML Reliability Audit

## Dataset
- Rows: 1520

## Time Split (Primary)
- Regression model MAE: 4.3500
- Classification model macro-F1: 0.4356

## Random Split (Secondary)
- Regression model MAE: 2.7740
- Classification model macro-F1: 0.4445

## Baseline Comparison (Time Split)
| Baseline | MAE | Delta vs model MAE | Model beats baseline |
| --- | ---: | ---: | :---: |
| stage_season_mean_loss | 3.7667 | -0.5833 | NO |
| product_stage_season_mean_loss | 3.7843 | -0.5656 | NO |
| stage_mean_loss | 3.8330 | -0.5170 | NO |
| product_stage_mean_loss | 3.8431 | -0.5069 | NO |
| product_stage_rolling_mean_loss | 4.0833 | -0.2667 | NO |
| product_mean_loss | 5.1248 | 0.7748 | YES |
| global_mean_loss | 5.1263 | 0.7763 | YES |
| previous_batch_loss_baseline | 5.4260 | 1.0760 | YES |

## Classification Baseline Comparison (Time Split)
| Candidate | Macro-F1 |
| --- | ---: |
| model | 0.4356 |
| thresholded_predicted_loss_baseline | 0.3334 |
| thresholded_product_stage_average_baseline | 0.3526 |

## Gate Results
- Regression gate: FAIL
- Classification gate: FAIL
- Anomaly gate: EXPLORATORY
- Recommendation policy gate: RULE_BASED

## Selection Decision
- Regression decision: baseline:stage_season_mean_loss
- Classification decision: threshold_baseline:thresholded_product_stage_average_baseline
- Anomaly decision: exploratory_only
- Recommendation decision: rule_engine_templates

## PFE Report Claims
Can claim:
- Classification ML outperforms threshold baselines by -23.51% on macro-F1 (time split).
- Anomaly outputs are operational signals only (not supervised-validated accuracy).
- Recommendation generation is currently rule-based template logic.
Cannot claim:
- Reliable regression superiority over strong statistical baselines for loss prediction.
- Validated anomaly detection accuracy without labeled anomaly ground truth.
- ML-ranked recommendation policy effectiveness without action/outcome feedback evidence.

## Honest Verdict
Current stack is mixed-readiness: classification signal is promising, regression reliability gate fails, anomaly is exploratory, and recommendation remains rule-based.
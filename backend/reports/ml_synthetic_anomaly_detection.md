# SYNTHETIC OFFLINE BENCHMARK — NOT REAL APP PERFORMANCE. These results are for controlled model development only and must not be used as production accuracy claims.

## Classification Freeze
- Decision: PARTIAL (improved_but_non_promoted)
- Frozen best prediction-mode candidate: {'candidate': 'Phase1C_LogRegBalanced_plus_HighOverride_balanced', 'macro_f1': 0.4679, 'high_risk_recall': 0.4783, 'high_risk_precision': 0.0688, 'false_low_high_risk_rate': 0.4348, 'false_alarms': 149}

## IsolationForest Baseline
- precision=0.0222, recall=0.0345, f1=0.0270, precision@10%=0.0000, tp=1, fp=44, fn=28

## Prediction-Mode Anomaly Candidates
| candidate | type | precision | recall | f1 | precision@10% | fp | fn | tp | gate_pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| PredictionRulesPlusStatistical | hybrid | 0.0442 | 0.2759 | 0.0762 | 0.0500 | 173 | 21 | 8 | False |
| PredictionRulesOnly | rule | 0.0506 | 0.2759 | 0.0856 | 0.0250 | 150 | 21 | 8 | False |
| PredictionHybridHighRecall | hybrid | 0.0412 | 0.2759 | 0.0717 | 0.0250 | 186 | 21 | 8 | False |
| PredictionHybridBalanced | hybrid | 0.0417 | 0.0690 | 0.0519 | 0.0250 | 46 | 27 | 2 | False |
| IsolationForestBaseline | ml | 0.0222 | 0.0345 | 0.0270 | 0.0000 | 44 | 28 | 1 | False |
| PredictionStatisticalOnly | statistical | 0.0217 | 0.0345 | 0.0267 | 0.0000 | 45 | 28 | 1 | False |
| PredictionRulesConservative | rule | 0.0000 | 0.0000 | 0.0000 | 0.0250 | 16 | 29 | 0 | False |

## Assessment-Mode Anomaly Candidates
| candidate | type | precision | recall | f1 | precision@10% | fp | fn | tp | gate_pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| AssessmentRulesPlusStatistical | hybrid | 0.8788 | 1.0000 | 0.9355 | 0.7250 | 4 | 0 | 29 | True |
| AssessmentRulesOnly | rule | 0.8750 | 0.9655 | 0.9180 | 0.7000 | 4 | 1 | 28 | True |
| AssessmentStatisticalOnly | statistical | 1.0000 | 0.7931 | 0.8846 | 0.5750 | 0 | 6 | 23 | False |
| AssessmentHybridBalanced | hybrid | 0.9167 | 0.7586 | 0.8302 | 0.7250 | 2 | 7 | 22 | False |
| AssessmentRulesConservative | rule | 1.0000 | 0.6552 | 0.7917 | 0.7000 | 0 | 10 | 19 | False |
| AssessmentHybridHighRecall | hybrid | 0.3867 | 1.0000 | 0.5577 | 0.7250 | 46 | 0 | 29 | False |

## Best Candidates and Decision
- Best prediction-mode anomaly/risk candidate: PredictionRulesPlusStatistical
- Best assessment-mode anomaly candidate: AssessmentRulesPlusStatistical
- Final anomaly decision: PASS (assessment_mode_hybrid_passed_offline_gate)

## Logic and Boundaries
- Explanation: IsolationForest underperforms because synthetic anomaly labels are injected using outcome shocks, while unsupervised context-only separation is weak. Rule/statistical checks align better with operational post-step anomalies.
- Rule definitions: {'prediction_mode_rules': ['weather_stage_sechage_extreme', 'duration_delay_extreme_by_stage', 'grade_c_stage_weather', 'low_qty_with_extreme_duration_or_delay'], 'assessment_mode_rules': ['qty_out_gt_qty_in_or_invalid', 'extreme_loss_by_stage', 'product_stage_iqr_loss_outlier', 'duration_delay_extreme', 'weather_stage_plus_high_loss', 'unexpected_packaging_loss'], 'assessment_only_fields': ['qty_out', 'loss_qty', 'loss_pct', 'efficiency_pct']}
- Gate definition: {'assessment_mode': {'f1_min': 0.75, 'precision_min': 0.6, 'recall_min': 0.8, 'precision_at_10pct_min': 0.6}, 'prediction_mode': {'note': 'Reported separately as context risk indicators; not used for production promotion.'}}
- Promotion note: Anomaly results are synthetic/offline only; runtime remains non-promoted.
- Synthetic offline benchmark only.
- Not production accuracy.
- No runtime promotion or model replacement.

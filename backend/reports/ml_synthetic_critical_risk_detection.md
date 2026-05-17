# SYNTHETIC OFFLINE BENCHMARK — NOT REAL APP PERFORMANCE. These results are for controlled model development only and must not be used as production accuracy claims.

## Focus
- Offline synthetic critical-risk detection analysis only.

## Previous Phase 1 Reference
- Candidate: LogisticRegression_class_weight_balanced
- Macro-F1: 0.5173
- High-risk recall: 0.3913
- High-risk precision: 0.0744
- False-low-high-risk rate: 0.4783

## Previous Phase 1B Reference
- Candidate: Phase1B_LogRegBalanced_plus_HighOverride
- Macro-F1: 0.4691
- High-risk recall: 0.4348
- High-risk precision: 0.0654
- False-low-high-risk rate: 0.4783
- False alarms: 143

## Best Candidates (Time Split)
- Best prediction-mode candidate: Phase1C_LogRegBalanced_plus_HighOverride_balanced
- Prediction-mode macro-F1: 0.4679
- Prediction-mode high-risk recall: 0.4783
- Prediction-mode high-risk precision: 0.0688
- Prediction-mode false-low-high-risk rate: 0.4348
- Prediction-mode gate pass: False
- Best assessment-mode candidate: Phase1B_AssessmentMode_LogReg_plus_PostEventLossSeverity
- Assessment-mode macro-F1: 0.4893
- Assessment-mode high-risk recall: 0.6522
- Assessment-mode high-risk precision: 0.0955
- Assessment-mode false-low-high-risk rate: 0.3478
- Assessment-mode gate pass: False

## Failure Diagnostics
- Train class distribution: {'low': 1108, 'medium': 398, 'high': 98}
- Test class distribution: {'low': 282, 'medium': 91, 'high': 23}
- High-risk support count: 23
- Confusion matrix (current model): [[274, 8, 0], [10, 81, 0], [13, 10, 0]]
- High-risk prediction breakdown: {'predicted_low': 13, 'predicted_medium': 10, 'predicted_high': 0}
- High-risk cluster by stage: {'sechage': 10, 'emballage': 5, 'nettoyage': 4, 'tri': 4}
- High-risk cluster by product: {'arachide': 10, 'mangue': 10, 'mil': 3}
- High-risk cluster by season: {'hot': 9, 'rainy': 8, 'dry': 6}

## Rule Definition
- {'severity_score_components': {'stage_weight': {'sechage': 2.2, 'emballage': 1.3, 'tri': 1.0, 'nettoyage': 1.0}, 'product_weight': {'mangue': 1.4, 'arachide': 1.4, 'mil': 1.1}, 'grade_weight': {'C': 1.3, 'B': 1.0, 'A': 0.9}, 'weather_duration_terms': ['humidity_risk', 'rainfall_risk', 'dew_point_risk', 'step_duration_risk', 'delay_risk'], 'assessment_only_term': 'loss_pct_risk'}, 'mode_boundary': {'prediction_mode': 'does not use loss_pct/loss_qty/efficiency_pct as features', 'assessment_mode': 'may include post-event loss_pct in severity override'}}

## Phase 1C Pareto Frontier (Prediction-Mode)
| candidate | macro_f1 | high_recall | high_precision | false_alarms |
|---|---:|---:|---:|---:|
| Phase1C_LogRegBalanced_plus_HighOverride_balanced | 0.4679 | 0.4783 | 0.0688 | 149 |
| Phase1B_LogRegBalanced_plus_HighOverride | 0.4679 | 0.4783 | 0.0688 | 149 |
| Phase1C_LogRegBalanced_plus_HighOverride_conservative | 0.4768 | 0.4348 | 0.0685 | 136 |
| LogisticRegression_class_weight_balanced_high_threshold_0.50 | 0.5331 | 0.3913 | 0.0804 | 103 |
| RandomForestClassifier_class_weight_balanced_high_threshold_0.10 | 0.5037 | 0.3478 | 0.0889 | 82 |
| Phase1C_RFBalanced_plus_HighOverride_balanced | 0.5741 | 0.2174 | 0.0833 | 55 |
| Phase1B_RFBalanced_plus_HighOverride | 0.5741 | 0.2174 | 0.0833 | 55 |
| Phase1C_BalancedHybrid_t0.18 | 0.5741 | 0.2174 | 0.0833 | 55 |
| Phase1C_BalancedHybrid_t0.22 | 0.5741 | 0.2174 | 0.0833 | 55 |
| Phase1C_BalancedHybrid_t0.26 | 0.5741 | 0.2174 | 0.0833 | 55 |
| Phase1C_RFBalanced_plus_HighOverride_conservative | 0.5801 | 0.1304 | 0.0750 | 37 |
| Phase1C_ConservativeHybrid_t0.18 | 0.5801 | 0.1304 | 0.0750 | 37 |
| Phase1C_ConservativeHybrid_t0.22 | 0.5801 | 0.1304 | 0.0750 | 37 |
| Phase1C_ConservativeHybrid_t0.26 | 0.5801 | 0.1304 | 0.0750 | 37 |
| Phase1B_ConservativeHybrid | 0.5801 | 0.1304 | 0.0750 | 37 |
| CalibratedRandomForestClassifier_high_threshold_0.10 | 0.5742 | 0.1304 | 0.0909 | 30 |
| StageAwareThresholdBalancedRF | 0.5890 | 0.0870 | 0.0500 | 38 |
| CostSensitiveCalibratedRF | 0.4978 | 0.0435 | 1.0000 | 0 |
| threshold_stage_mean_baseline | 0.5997 | 0.0000 | 0.0000 | 0 |
| RandomForestClassifier | 0.5997 | 0.0000 | 0.0000 | 0 |
| RandomForestClassifier_class_weight_balanced | 0.5997 | 0.0000 | 0.0000 | 0 |
| HistGradientBoostingClassifier | 0.5997 | 0.0000 | 0.0000 | 0 |
| CalibratedRandomForestClassifier | 0.5997 | 0.0000 | 0.0000 | 0 |

## Phase 1C Selection Summary
- Best recall candidate: Phase1C_LogRegBalanced_plus_HighOverride_balanced
- Best macro-F1 candidate: threshold_stage_mean_baseline
- Best balanced candidate: LogisticRegression_class_weight_balanced
- Lowest false-alarm candidate with recall>0: CostSensitiveCalibratedRF
- Final classification decision: PARTIAL (recall_improved_materially_but_full_gate_not_met)

## Prediction-Mode Candidates
| candidate | macro_f1 | high_recall | high_precision | false_low_high_rate | false_alarms | gate_pass |
|---|---:|---:|---:|---:|---:|---|
| Phase1C_LogRegBalanced_plus_HighOverride_balanced | 0.4679 | 0.4783 | 0.0688 | 0.4348 | 149 | False |
| Phase1B_LogRegBalanced_plus_HighOverride | 0.4679 | 0.4783 | 0.0688 | 0.4348 | 149 | False |
| Phase1C_LogRegBalanced_plus_HighOverride_conservative | 0.4768 | 0.4348 | 0.0685 | 0.4783 | 136 | False |
| LogisticRegression_class_weight_balanced_high_threshold_0.50 | 0.5331 | 0.3913 | 0.0804 | 0.4783 | 103 | False |
| LogisticRegression_class_weight_balanced | 0.5173 | 0.3913 | 0.0744 | 0.4783 | 112 | False |
| RandomForestClassifier_class_weight_balanced_high_threshold_0.10 | 0.5037 | 0.3478 | 0.0889 | 0.5652 | 82 | False |
| Phase1C_RFBalanced_plus_HighOverride_balanced | 0.5741 | 0.2174 | 0.0833 | 0.5217 | 55 | False |
| Phase1B_RFBalanced_plus_HighOverride | 0.5741 | 0.2174 | 0.0833 | 0.5217 | 55 | False |
| Phase1C_BalancedHybrid_t0.18 | 0.5741 | 0.2174 | 0.0833 | 0.5217 | 55 | False |
| Phase1C_BalancedHybrid_t0.22 | 0.5741 | 0.2174 | 0.0833 | 0.5217 | 55 | False |
| Phase1C_BalancedHybrid_t0.26 | 0.5741 | 0.2174 | 0.0833 | 0.5217 | 55 | False |
| Phase1C_RFBalanced_plus_HighOverride_aggressive | 0.5380 | 0.2174 | 0.0625 | 0.5217 | 75 | False |
| Phase1B_WeatherDurationRiskOverride_BalancedRF | 0.5380 | 0.2174 | 0.0625 | 0.5217 | 75 | False |
| Phase1B_BalancedHybrid | 0.5380 | 0.2174 | 0.0625 | 0.5217 | 75 | False |
| Phase1C_RFBalanced_plus_HighOverride_conservative | 0.5801 | 0.1304 | 0.0750 | 0.5652 | 37 | False |
| Phase1C_ConservativeHybrid_t0.18 | 0.5801 | 0.1304 | 0.0750 | 0.5652 | 37 | False |
| Phase1C_ConservativeHybrid_t0.22 | 0.5801 | 0.1304 | 0.0750 | 0.5652 | 37 | False |
| Phase1C_ConservativeHybrid_t0.26 | 0.5801 | 0.1304 | 0.0750 | 0.5652 | 37 | False |
| Phase1B_ConservativeHybrid | 0.5801 | 0.1304 | 0.0750 | 0.5652 | 37 | False |
| CalibratedRandomForestClassifier_high_threshold_0.10 | 0.5742 | 0.1304 | 0.0909 | 0.5652 | 30 | False |
| StageAwareThresholdBalancedRF | 0.5890 | 0.0870 | 0.0500 | 0.5652 | 38 | False |
| ProductStageAwareThresholdBalancedRF | 0.5542 | 0.0870 | 0.0357 | 0.5652 | 54 | False |
| CostSensitiveCalibratedRF | 0.4978 | 0.0435 | 1.0000 | 0.3043 | 0 | False |
| threshold_stage_mean_baseline | 0.5997 | 0.0000 | 0.0000 | 0.5652 | 0 | False |
| RandomForestClassifier | 0.5997 | 0.0000 | 0.0000 | 0.5652 | 0 | False |
| RandomForestClassifier_class_weight_balanced | 0.5997 | 0.0000 | 0.0000 | 0.5652 | 0 | False |
| HistGradientBoostingClassifier | 0.5997 | 0.0000 | 0.0000 | 0.5652 | 0 | False |
| CalibratedRandomForestClassifier | 0.5997 | 0.0000 | 0.0000 | 0.5652 | 0 | False |

## Assessment-Mode Candidates
| candidate | macro_f1 | high_recall | high_precision | false_low_high_rate | false_alarms | gate_pass |
|---|---:|---:|---:|---:|---:|---|
| Phase1B_AssessmentMode_LogReg_plus_PostEventLossSeverity | 0.4893 | 0.6522 | 0.0955 | 0.3478 | 142 | False |

## Threshold Tuning Tradeoff
| source_model | high_threshold | macro_f1 | high_recall | high_precision | false_low_high_rate |
|---|---:|---:|---:|---:|---:|
| RandomForestClassifier_class_weight_balanced | 0.10 | 0.5037 | 0.3478 | 0.0889 | 0.5652 |
| RandomForestClassifier_class_weight_balanced | 0.15 | 0.5490 | 0.0870 | 0.0476 | 0.5652 |
| RandomForestClassifier_class_weight_balanced | 0.20 | 0.5847 | 0.0870 | 0.0833 | 0.5652 |
| RandomForestClassifier_class_weight_balanced | 0.25 | 0.6263 | 0.0870 | 0.2000 | 0.5652 |
| RandomForestClassifier_class_weight_balanced | 0.30 | 0.6197 | 0.0435 | 0.2500 | 0.5652 |
| RandomForestClassifier_class_weight_balanced | 0.35 | 0.6197 | 0.0435 | 0.2500 | 0.5652 |
| RandomForestClassifier_class_weight_balanced | 0.40 | 0.6197 | 0.0435 | 0.2500 | 0.5652 |
| RandomForestClassifier_class_weight_balanced | 0.45 | 0.6258 | 0.0435 | 0.5000 | 0.5652 |
| RandomForestClassifier_class_weight_balanced | 0.50 | 0.5997 | 0.0000 | 0.0000 | 0.5652 |
| RandomForestClassifier_class_weight_balanced | 0.55 | 0.5997 | 0.0000 | 0.0000 | 0.5652 |
| CalibratedRandomForestClassifier | 0.10 | 0.5742 | 0.1304 | 0.0909 | 0.5652 |
| CalibratedRandomForestClassifier | 0.15 | 0.6138 | 0.0435 | 0.1667 | 0.5652 |
| CalibratedRandomForestClassifier | 0.20 | 0.6228 | 0.0435 | 0.3333 | 0.5652 |
| CalibratedRandomForestClassifier | 0.25 | 0.6258 | 0.0435 | 0.5000 | 0.5652 |
| CalibratedRandomForestClassifier | 0.30 | 0.5997 | 0.0000 | 0.0000 | 0.5652 |
| CalibratedRandomForestClassifier | 0.35 | 0.5997 | 0.0000 | 0.0000 | 0.5652 |
| CalibratedRandomForestClassifier | 0.40 | 0.5997 | 0.0000 | 0.0000 | 0.5652 |
| CalibratedRandomForestClassifier | 0.45 | 0.5997 | 0.0000 | 0.0000 | 0.5652 |
| CalibratedRandomForestClassifier | 0.50 | 0.5997 | 0.0000 | 0.0000 | 0.5652 |
| CalibratedRandomForestClassifier | 0.55 | 0.5997 | 0.0000 | 0.0000 | 0.5652 |
| LogisticRegression_class_weight_balanced | 0.10 | 0.1383 | 0.8696 | 0.0567 | 0.1304 |
| LogisticRegression_class_weight_balanced | 0.15 | 0.2240 | 0.7391 | 0.0548 | 0.1739 |
| LogisticRegression_class_weight_balanced | 0.20 | 0.2933 | 0.7391 | 0.0616 | 0.1739 |
| LogisticRegression_class_weight_balanced | 0.25 | 0.3390 | 0.6957 | 0.0635 | 0.2174 |
| LogisticRegression_class_weight_balanced | 0.30 | 0.3836 | 0.6087 | 0.0645 | 0.3043 |
| LogisticRegression_class_weight_balanced | 0.35 | 0.4263 | 0.5217 | 0.0628 | 0.3913 |
| LogisticRegression_class_weight_balanced | 0.40 | 0.4403 | 0.4348 | 0.0588 | 0.4348 |
| LogisticRegression_class_weight_balanced | 0.45 | 0.4730 | 0.3913 | 0.0629 | 0.4783 |
| LogisticRegression_class_weight_balanced | 0.50 | 0.5331 | 0.3913 | 0.0804 | 0.4783 |
| LogisticRegression_class_weight_balanced | 0.55 | 0.5478 | 0.3043 | 0.0824 | 0.4783 |

## Boundary
- Synthetic offline benchmark only.
- Not production accuracy.
- No runtime promotion or model replacement.

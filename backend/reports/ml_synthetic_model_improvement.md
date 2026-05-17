# SYNTHETIC OFFLINE BENCHMARK — NOT REAL APP PERFORMANCE. These results are for controlled model development only and must not be used as production accuracy claims.

## Dataset
- Source label: SYNTHETIC_OFFLINE_BENCHMARK
- Data origin expected: SYNTHETIC_BENCHMARK
- Row count: 2000
- Products: arachide, mangue, mil
- Stages: emballage, nettoyage, sechage, tri

## Split Summary
- time_split: {'strategy': 'time_based', 'split_cutoff_event_ordinal': 739452, 'train_rows': 1604, 'test_rows': 396, 'lot_overlap_count': 2}
- random_split: {'strategy': 'random_80_20', 'train_rows': 1600, 'test_rows': 400}
- grouped_lot_time_split: {'strategy': 'grouped_lot_time', 'train_rows': 1600, 'test_rows': 400, 'train_lots': 400, 'test_lots': 100, 'lot_overlap_count': 0}

## Regression Candidate Table (Time Split Primary)
| candidate | mae | best_baseline | best_baseline_mae | rel_improvement_pct | beats_baseline | sechage_beats_baseline | gate_pass |
|---|---:|---|---:|---:|---|---|---|
| stage_season_mean_loss | 2.5622 | stage_season_mean_loss | 2.5622 | 0.00% | False | True | False |
| product_stage_season_mean_loss | 2.6146 | stage_season_mean_loss | 2.5622 | -2.04% | False | True | False |
| stage_mean_loss | 2.6350 | stage_season_mean_loss | 2.5622 | -2.84% | False | False | False |
| product_stage_mean_loss | 2.6664 | stage_season_mean_loss | 2.5622 | -4.07% | False | True | False |
| WeatherDurationResidualOnStageSeason | 2.7056 | stage_season_mean_loss | 2.5622 | -5.60% | False | True | False |
| ResidualOnBestBaselineRegressor | 2.7599 | stage_season_mean_loss | 2.5622 | -7.72% | False | True | False |
| ResidualOnStageSeasonBaselineRegressor | 2.7599 | stage_season_mean_loss | 2.5622 | -7.72% | False | True | False |
| GradientBoostingRegressor | 2.9127 | stage_season_mean_loss | 2.5622 | -13.68% | False | False | False |
| HistGradientBoostingRegressor | 2.9490 | stage_season_mean_loss | 2.5622 | -15.10% | False | False | False |
| ProductStageSpecificHistGradientBoostingRegressor | 3.1909 | stage_season_mean_loss | 2.5622 | -24.54% | False | False | False |
| StageSpecificHistGradientBoostingRegressor | 3.4543 | stage_season_mean_loss | 2.5622 | -34.82% | False | False | False |
| RandomForestRegressor | 3.7589 | stage_season_mean_loss | 2.5622 | -46.70% | False | False | False |
| global_mean_loss | 4.6576 | stage_season_mean_loss | 2.5622 | -81.78% | False | False | False |

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

## Phase 1B Prediction-Mode Candidate Table (Time Split Primary)
| candidate | macro_f1 | high_recall | high_precision | false_low_high_rate | high_detected | false_alarms | gate_pass |
|---|---:|---:|---:|---:|---:|---:|---|
| Phase1C_LogRegBalanced_plus_HighOverride_balanced | 0.4679 | 0.4783 | 0.0688 | 0.4348 | 11 | 149 | False |
| Phase1B_LogRegBalanced_plus_HighOverride | 0.4679 | 0.4783 | 0.0688 | 0.4348 | 11 | 149 | False |
| Phase1C_LogRegBalanced_plus_HighOverride_conservative | 0.4768 | 0.4348 | 0.0685 | 0.4783 | 10 | 136 | False |
| LogisticRegression_class_weight_balanced_high_threshold_0.50 | 0.5331 | 0.3913 | 0.0804 | 0.4783 | 9 | 103 | False |
| LogisticRegression_class_weight_balanced | 0.5173 | 0.3913 | 0.0744 | 0.4783 | 9 | 112 | False |
| RandomForestClassifier_class_weight_balanced_high_threshold_0.10 | 0.5037 | 0.3478 | 0.0889 | 0.5652 | 8 | 82 | False |
| Phase1C_RFBalanced_plus_HighOverride_balanced | 0.5741 | 0.2174 | 0.0833 | 0.5217 | 5 | 55 | False |
| Phase1B_RFBalanced_plus_HighOverride | 0.5741 | 0.2174 | 0.0833 | 0.5217 | 5 | 55 | False |
| Phase1C_BalancedHybrid_t0.18 | 0.5741 | 0.2174 | 0.0833 | 0.5217 | 5 | 55 | False |
| Phase1C_BalancedHybrid_t0.22 | 0.5741 | 0.2174 | 0.0833 | 0.5217 | 5 | 55 | False |
| Phase1C_BalancedHybrid_t0.26 | 0.5741 | 0.2174 | 0.0833 | 0.5217 | 5 | 55 | False |
| Phase1C_RFBalanced_plus_HighOverride_aggressive | 0.5380 | 0.2174 | 0.0625 | 0.5217 | 5 | 75 | False |
| Phase1B_WeatherDurationRiskOverride_BalancedRF | 0.5380 | 0.2174 | 0.0625 | 0.5217 | 5 | 75 | False |
| Phase1B_BalancedHybrid | 0.5380 | 0.2174 | 0.0625 | 0.5217 | 5 | 75 | False |
| Phase1C_RFBalanced_plus_HighOverride_conservative | 0.5801 | 0.1304 | 0.0750 | 0.5652 | 3 | 37 | False |
| Phase1C_ConservativeHybrid_t0.18 | 0.5801 | 0.1304 | 0.0750 | 0.5652 | 3 | 37 | False |
| Phase1C_ConservativeHybrid_t0.22 | 0.5801 | 0.1304 | 0.0750 | 0.5652 | 3 | 37 | False |
| Phase1C_ConservativeHybrid_t0.26 | 0.5801 | 0.1304 | 0.0750 | 0.5652 | 3 | 37 | False |
| Phase1B_ConservativeHybrid | 0.5801 | 0.1304 | 0.0750 | 0.5652 | 3 | 37 | False |
| CalibratedRandomForestClassifier_high_threshold_0.10 | 0.5742 | 0.1304 | 0.0909 | 0.5652 | 3 | 30 | False |
| StageAwareThresholdBalancedRF | 0.5890 | 0.0870 | 0.0500 | 0.5652 | 2 | 38 | False |
| ProductStageAwareThresholdBalancedRF | 0.5542 | 0.0870 | 0.0357 | 0.5652 | 2 | 54 | False |
| CostSensitiveCalibratedRF | 0.4978 | 0.0435 | 1.0000 | 0.3043 | 1 | 0 | False |
| threshold_stage_mean_baseline | 0.5997 | 0.0000 | 0.0000 | 0.5652 | 0 | 0 | False |
| RandomForestClassifier | 0.5997 | 0.0000 | 0.0000 | 0.5652 | 0 | 0 | False |
| RandomForestClassifier_class_weight_balanced | 0.5997 | 0.0000 | 0.0000 | 0.5652 | 0 | 0 | False |
| HistGradientBoostingClassifier | 0.5997 | 0.0000 | 0.0000 | 0.5652 | 0 | 0 | False |
| CalibratedRandomForestClassifier | 0.5997 | 0.0000 | 0.0000 | 0.5652 | 0 | 0 | False |

## Phase 1B Assessment-Mode Candidate Table (Time Split Primary)
| candidate | macro_f1 | high_recall | high_precision | false_low_high_rate | high_detected | false_alarms | gate_pass |
|---|---:|---:|---:|---:|---:|---:|---|
| Phase1B_AssessmentMode_LogReg_plus_PostEventLossSeverity | 0.4893 | 0.6522 | 0.0955 | 0.3478 | 15 | 142 | False |

## Best Phase 1B Candidates
- Best prediction-mode: Phase1C_LogRegBalanced_plus_HighOverride_balanced
- Best assessment-mode: Phase1B_AssessmentMode_LogReg_plus_PostEventLossSeverity

## Critical-Risk Diagnostics (Time Split Primary)
- Current reference model: RandomForestClassifier
- Current reference macro-F1: 0.5997
- Current reference high-risk recall: 0.0000
- Current reference false-low-high-risk rate: 0.5652
- Train class distribution: {'low': 1108, 'medium': 398, 'high': 98}
- Test class distribution: {'low': 282, 'medium': 91, 'high': 23}
- High-risk support count: 23
- Confusion matrix (current model): [[274, 8, 0], [10, 81, 0], [13, 10, 0]]
- High-risk predicted as low/medium/high: {'predicted_low': 13, 'predicted_medium': 10, 'predicted_high': 0}
- High-risk cluster by stage: {'sechage': 10, 'emballage': 5, 'nettoyage': 4, 'tri': 4}
- High-risk cluster by product: {'arachide': 10, 'mangue': 10, 'mil': 3}
- High-risk cluster by season: {'hot': 9, 'rainy': 8, 'dry': 6}

## Rule Definition (Phase 1B)
- Definition: {'severity_score_components': {'stage_weight': {'sechage': 2.2, 'emballage': 1.3, 'tri': 1.0, 'nettoyage': 1.0}, 'product_weight': {'mangue': 1.4, 'arachide': 1.4, 'mil': 1.1}, 'grade_weight': {'C': 1.3, 'B': 1.0, 'A': 0.9}, 'weather_duration_terms': ['humidity_risk', 'rainfall_risk', 'dew_point_risk', 'step_duration_risk', 'delay_risk'], 'assessment_only_term': 'loss_pct_risk'}, 'mode_boundary': {'prediction_mode': 'does not use loss_pct/loss_qty/efficiency_pct as features', 'assessment_mode': 'may include post-event loss_pct in severity override'}}

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
- Final classification decision (Phase 1C): PARTIAL (recall_improved_materially_but_full_gate_not_met)

## Threshold Tuning Tradeoff (Time Split Primary)
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

## Classification Gate (Primary)
- high-risk recall >= 0.40
- macro-F1 >= 0.50
- false-low-high-risk rate must improve vs current reference
- Any candidate passed: False

## Classification Freeze (Phase 2)
- Classification decision remains: PARTIAL (improved_but_non_promoted). No further classification tuning in this phase.
- Frozen best prediction-mode candidate: {'candidate': 'Phase1C_LogRegBalanced_plus_HighOverride_balanced', 'macro_f1': 0.4679, 'high_risk_recall': 0.4783, 'high_risk_precision': 0.0688, 'false_low_high_risk_rate': 0.4348, 'false_alarms': 149}

## Anomaly Diagnostic
- Explanation: IsolationForest underperforms because synthetic anomaly labels are injected using outcome shocks, while unsupervised context-only separation is weak. Rule/statistical checks align better with operational post-step anomalies.
- IsolationForest baseline: precision=0.0222, recall=0.0345, f1=0.0270, precision@10%=0.0000, tp=1, fp=44, fn=28

## Anomaly Candidate Table (Prediction-Mode)
| candidate | type | precision | recall | f1 | precision@10% | fp | fn | tp | gate_pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| PredictionRulesPlusStatistical | hybrid | 0.0442 | 0.2759 | 0.0762 | 0.0500 | 173 | 21 | 8 | False |
| PredictionRulesOnly | rule | 0.0506 | 0.2759 | 0.0856 | 0.0250 | 150 | 21 | 8 | False |
| PredictionHybridHighRecall | hybrid | 0.0412 | 0.2759 | 0.0717 | 0.0250 | 186 | 21 | 8 | False |
| PredictionHybridBalanced | hybrid | 0.0417 | 0.0690 | 0.0519 | 0.0250 | 46 | 27 | 2 | False |
| IsolationForestBaseline | ml | 0.0222 | 0.0345 | 0.0270 | 0.0000 | 44 | 28 | 1 | False |
| PredictionStatisticalOnly | statistical | 0.0217 | 0.0345 | 0.0267 | 0.0000 | 45 | 28 | 1 | False |
| PredictionRulesConservative | rule | 0.0000 | 0.0000 | 0.0000 | 0.0250 | 16 | 29 | 0 | False |

## Anomaly Candidate Table (Assessment-Mode)
| candidate | type | precision | recall | f1 | precision@10% | fp | fn | tp | gate_pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| AssessmentRulesPlusStatistical | hybrid | 0.8788 | 1.0000 | 0.9355 | 0.7250 | 4 | 0 | 29 | True |
| AssessmentRulesOnly | rule | 0.8750 | 0.9655 | 0.9180 | 0.7000 | 4 | 1 | 28 | True |
| AssessmentStatisticalOnly | statistical | 1.0000 | 0.7931 | 0.8846 | 0.5750 | 0 | 6 | 23 | False |
| AssessmentHybridBalanced | hybrid | 0.9167 | 0.7586 | 0.8302 | 0.7250 | 2 | 7 | 22 | False |
| AssessmentRulesConservative | rule | 1.0000 | 0.6552 | 0.7917 | 0.7000 | 0 | 10 | 19 | False |
| AssessmentHybridHighRecall | hybrid | 0.3867 | 1.0000 | 0.5577 | 0.7250 | 46 | 0 | 29 | False |

## Anomaly Best Candidates
- Best prediction-mode anomaly/risk candidate: PredictionRulesPlusStatistical
- Best assessment-mode anomaly candidate: AssessmentRulesPlusStatistical
- Final anomaly decision: PASS (assessment_mode_hybrid_passed_offline_gate)

## Anomaly Rule Logic
- Rule definitions: {'prediction_mode_rules': ['weather_stage_sechage_extreme', 'duration_delay_extreme_by_stage', 'grade_c_stage_weather', 'low_qty_with_extreme_duration_or_delay'], 'assessment_mode_rules': ['qty_out_gt_qty_in_or_invalid', 'extreme_loss_by_stage', 'product_stage_iqr_loss_outlier', 'duration_delay_extreme', 'weather_stage_plus_high_loss', 'unexpected_packaging_loss'], 'assessment_only_fields': ['qty_out', 'loss_qty', 'loss_pct', 'efficiency_pct']}
- Gate definition: {'assessment_mode': {'f1_min': 0.75, 'precision_min': 0.6, 'recall_min': 0.8, 'precision_at_10pct_min': 0.6}, 'prediction_mode': {'note': 'Reported separately as context risk indicators; not used for production promotion.'}}
- Promotion note: Anomaly results are synthetic/offline only; runtime remains non-promoted.

## Recommendation Ranking (Phase 3)
- Proxy relevance warning: Synthetic proxy relevance is not real recommendation outcome evidence.
- Frozen status summary: {'regression': 'baseline_fallback_not_ml_promoted', 'classification': 'PARTIAL_improved_but_non_promoted', 'anomaly': {'decision': 'PASS', 'reason': 'assessment_mode_hybrid_passed_offline_gate'}, 'runtime': 'unchanged_non_promoted_rule_based'}
- Action templates: {'increase_ventilation_delay_drying': 'increase ventilation / delay drying / protect from humidity', 'inspect_process_step_material_balance': 'inspect process step and verify material balance', 'reduce_waiting_time_before_next_stage': 'reduce waiting time before next stage', 'verify_packaging_method_material': 'verify packaging method and material', 'review_stage_procedure_operator_method': 'review stage procedure and operator method', 'monitor_only_no_strong_action': 'monitor only / no strong action'}
- Ranking score definition: {'components': ['loss_severity_score', 'anomaly_score_assessment_mode', 'classification_risk_score', 'weather_duration_risk_score', 'stage_priority_score', 'recurrence_or_product_stage_baseline_score', 'evidence_quality_score', 'confidence_penalty'], 'strategies': ['RuleDefaultRanking', 'SeverityFirstRanking', 'HybridEvidenceRanking', 'ConservativeRanking', 'FinalConservativeEvidenceRanking']}

## Recommendation Ranking Candidates (Prediction-Mode)
| strategy | Precision@3 | Precision@5 | NDCG@5 | mean top relevance | anomaly/high-loss top coverage | gate_pass |
|---|---:|---:|---:|---:|---:|---|
| FinalConservativeEvidenceRanking | 0.7096 | 0.4758 | 0.9380 | 1.1162 | 1.0000 | False |
| ConservativeRanking | 0.7054 | 0.4768 | 0.8643 | 0.8889 | 0.6471 | False |
| RuleDefaultRanking | 0.6726 | 0.4717 | 0.8103 | 0.7955 | 0.9412 | False |
| HybridEvidenceRanking | 0.6347 | 0.4717 | 0.8146 | 0.8460 | 0.9412 | False |
| SeverityFirstRanking | 0.5572 | 0.4258 | 0.6651 | 0.6616 | 1.0000 | False |

## Recommendation Ranking Candidates (Assessment-Mode)
| strategy | Precision@3 | Precision@5 | NDCG@5 | mean top relevance | anomaly/high-loss top coverage | gate_pass |
|---|---:|---:|---:|---:|---:|---|
| ConservativeRanking | 0.6734 | 0.4621 | 0.9172 | 0.9924 | 1.0000 | False |
| RuleDefaultRanking | 0.6667 | 0.4667 | 0.8598 | 0.8359 | 1.0000 | False |
| FinalConservativeEvidenceRanking | 0.6650 | 0.4606 | 0.9523 | 1.1136 | 1.0000 | False |
| HybridEvidenceRanking | 0.6456 | 0.4672 | 0.8595 | 0.8611 | 1.0000 | False |
| SeverityFirstRanking | 0.5850 | 0.4540 | 0.7584 | 0.7045 | 1.0000 | False |

## Recommendation Ranking Best Candidates
- Best prediction-mode ranking candidate: FinalConservativeEvidenceRanking
- Best assessment-mode ranking candidate: ConservativeRanking
- Final recommendation-ranking decision: PARTIAL (proxy_ranking_is_useful_but_gate_not_fully_met)

## Claims Guardrail
### Allowed claims
- synthetic benchmark improved or did not improve specific model candidates
- classification has potential if high-risk recall improves
- regression remains baseline-fallback when it does not beat baseline
- synthetic benchmark is controlled and non-production

### Forbidden claims
- production-ready ML
- real cooperative accuracy
- promoted runtime model
- validated anomaly detection in production
- fully learned recommendations

## Scope Boundary
- Offline synthetic benchmark only.
- Not mixed with Supabase app data.
- Not used for production promotion.
- No runtime model replacement.

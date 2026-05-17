# SYNTHETIC OFFLINE BENCHMARK — NOT REAL APP PERFORMANCE. These results are for controlled model development only and must not be used as production accuracy claims.

## Frozen Model Status
- {'regression': 'baseline_fallback_not_ml_promoted', 'classification': 'PARTIAL_improved_but_non_promoted', 'anomaly': {'decision': 'PASS', 'reason': 'assessment_mode_hybrid_passed_offline_gate'}, 'runtime': 'unchanged_non_promoted_rule_based'}

## Action Templates
- increase_ventilation_delay_drying: increase ventilation / delay drying / protect from humidity
- inspect_process_step_material_balance: inspect process step and verify material balance
- reduce_waiting_time_before_next_stage: reduce waiting time before next stage
- verify_packaging_method_material: verify packaging method and material
- review_stage_procedure_operator_method: review stage procedure and operator method
- monitor_only_no_strong_action: monitor only / no strong action

## Ranking Score Definition
- {'components': ['loss_severity_score', 'anomaly_score_assessment_mode', 'classification_risk_score', 'weather_duration_risk_score', 'stage_priority_score', 'recurrence_or_product_stage_baseline_score', 'evidence_quality_score', 'confidence_penalty'], 'strategies': ['RuleDefaultRanking', 'SeverityFirstRanking', 'HybridEvidenceRanking', 'ConservativeRanking', 'FinalConservativeEvidenceRanking']}

## Proxy Relevance Boundary
- Synthetic proxy relevance is not real recommendation outcome evidence.
- {'high': 'anomaly true OR high loss OR severe stage/weather/duration condition', 'medium': 'moderate loss or moderate contextual risk', 'low': 'otherwise', 'boundary': 'Synthetic proxy relevance is not real recommendation outcome evidence.'}

## Prediction-Mode Ranking Candidates
| strategy | Precision@3 | Precision@5 | NDCG@5 | mean top relevance | anomaly/high-loss top coverage | gate_pass |
|---|---:|---:|---:|---:|---:|---|
| FinalConservativeEvidenceRanking | 0.7096 | 0.4758 | 0.9380 | 1.1162 | 1.0000 | False |
| ConservativeRanking | 0.7054 | 0.4768 | 0.8643 | 0.8889 | 0.6471 | False |
| RuleDefaultRanking | 0.6726 | 0.4717 | 0.8103 | 0.7955 | 0.9412 | False |
| HybridEvidenceRanking | 0.6347 | 0.4717 | 0.8146 | 0.8460 | 0.9412 | False |
| SeverityFirstRanking | 0.5572 | 0.4258 | 0.6651 | 0.6616 | 1.0000 | False |

## Assessment-Mode Ranking Candidates
| strategy | Precision@3 | Precision@5 | NDCG@5 | mean top relevance | anomaly/high-loss top coverage | gate_pass |
|---|---:|---:|---:|---:|---:|---|
| ConservativeRanking | 0.6734 | 0.4621 | 0.9172 | 0.9924 | 1.0000 | False |
| RuleDefaultRanking | 0.6667 | 0.4667 | 0.8598 | 0.8359 | 1.0000 | False |
| FinalConservativeEvidenceRanking | 0.6650 | 0.4606 | 0.9523 | 1.1136 | 1.0000 | False |
| HybridEvidenceRanking | 0.6456 | 0.4672 | 0.8595 | 0.8611 | 1.0000 | False |
| SeverityFirstRanking | 0.5850 | 0.4540 | 0.7584 | 0.7045 | 1.0000 | False |

## Best Candidates and Decision
- Best prediction-mode ranking candidate: FinalConservativeEvidenceRanking
- Best assessment-mode ranking candidate: ConservativeRanking
- Final recommendation-ranking decision: PARTIAL (proxy_ranking_is_useful_but_gate_not_fully_met)

## Forbidden Claims
- production-ready learned recommender
- real cooperative recommendation uplift
- runtime promoted recommendation model

## Boundary
- Synthetic offline benchmark only.
- Not production accuracy.
- No runtime promotion or model replacement.

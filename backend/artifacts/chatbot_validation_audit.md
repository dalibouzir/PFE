# Chatbot Pre-Phase-6 Validation Audit

## Executive Summary
- Generated at: 2026-05-08T10:42:20.511979+00:00
- Pass rate: 0.9
- Avg factual accuracy: 0.905
- Avg citation relevance: 0.26
- Avg scope purity: 1.0
- Avg answer usefulness: 0.93

## Actual Data Snapshot
- Cooperative: 356f4e38-f4f8-4559-a005-0a9c10366d37
- Stocks tracked: 3
- Batches tracked: 3
- Mango drying weekly step count: 0
- Reference metric rows: 12

## Per-question Validation

### current stock of mango
- category: SQL_ONLY
- intent: expected `SQL_ONLY`, observed `SQL_ONLY`
- sql_needed: True | rag_needed: False
- factual_accuracy_score: 1.0
- citation_relevance_score: 0.0
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 0.9
- passed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- chunk_types: {}
- answer: Mangue stock: total 210.0 kg, 100.0 kg reserved in lots, 110.0 kg remaining. Status: stable.

### how much arachide stock is remaining?
- category: SQL_ONLY
- intent: expected `SQL_ONLY`, observed `SQL_ONLY`
- sql_needed: True | rag_needed: False
- factual_accuracy_score: 1.0
- citation_relevance_score: 0.0
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 0.9
- passed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- chunk_types: {}
- answer: Arachide stock: total 60.0 kg, 0.0 kg reserved in lots, 60.0 kg remaining. Status: stable.

### what is the status of LOT-MANG-001?
- category: SQL_ONLY
- intent: expected `SQL_ONLY`, observed `SQL_ONLY`
- sql_needed: True | rag_needed: False
- factual_accuracy_score: 1.0
- citation_relevance_score: 0.0
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 0.9
- passed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- chunk_types: {}
- answer: LOT-MANG-001 (Mangue): status in_progress, initial 100.0 kg, current 94.0 kg, cumulative loss 6.0%, latest step Sechage, pending step none, anomaly/risk none.

### what does benchmark say about millet losses?
- category: RAG_ONLY
- intent: expected `RAG_ONLY`, observed `RAG_ONLY`
- sql_needed: False | rag_needed: True
- factual_accuracy_score: 0.85
- citation_relevance_score: 0.55
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 0.9
- passed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE', 'SQL_CONTEXT_MISSING']
- chunk_types: {}
- answer: No benchmark/agronomic evidence was retrieved for this question. I cannot provide a grounded reference answer yet.

### best practices for mango drying
- category: RAG_ONLY
- intent: expected `RAG_ONLY`, observed `RAG_ONLY`
- sql_needed: False | rag_needed: True
- factual_accuracy_score: 0.85
- citation_relevance_score: 0.55
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 0.9
- passed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE', 'SQL_CONTEXT_MISSING']
- chunk_types: {}
- answer: Aucune evidence benchmark/agronomique n'a ete recuperee pour cette question. Je ne peux pas fournir une reponse referencee fiable pour le moment.

### why are drying losses high this week for mango?
- category: HYBRID
- intent: expected `HYBRID`, observed `HYBRID`
- sql_needed: True | rag_needed: True
- factual_accuracy_score: 0.95
- citation_relevance_score: 0.5
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 0.9
- passed: True
- warning_flags: ['CONTRADICTORY_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE', 'ML_LOGS_EMPTY']
- chunk_types: {'operational_risk_summary': 1, 'product_stage_summary': 1, 'scoped_loss_summary': 1, 'process_step_summary': 1}
- answer: The high drying losses for mango this week can be attributed to several factors. The current loss rate for the cooperative is 15.71%, with a specific loss of 5.05% at the drying stage for mango. This indicates that the drying process is the most sensitive stage, contributing significantly to the overall losses.

For the specific lot LOT-MANG-001, the cumulative loss is reported at 6.0%, with the drying stage being a critical point of concern. The operational risk summary classifies this risk as low, but the losses at the drying stage are notable.

At the product-stage level, the recent average loss for mango during the drying process is 5.05%, which is higher than the cooperative-wide average loss of 15.64%. This suggests that while the cooperative is experiencing losses, the mango drying stage is particularly problematic.

At the cooperative level, the overall efficiency rate is 84.29%, which indicates that there is room for improvement in the drying process. The average loss percentage across all batches is 25.11%, which is significantly higher than the specific loss for mango, indicating that other products may be contributing to the overall loss metrics.

Compared with benchmark data, the average loss for mango at the drying stage is 12.0%, which is lower than the current loss rate observed in the cooperative. This suggests that there is potential for improvement in the

### compare current mango drying losses with benchmark references
- category: HYBRID
- intent: expected `HYBRID`, observed `HYBRID`
- sql_needed: True | rag_needed: True
- factual_accuracy_score: 0.8
- citation_relevance_score: 0.5
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 0.9
- passed: True
- warning_flags: ['CONTRADICTORY_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE', 'ML_LOGS_EMPTY']
- chunk_types: {'operational_risk_summary': 1, 'product_stage_summary': 1, 'scoped_loss_summary': 1, 'process_step_summary': 1}
- answer: Pour le séchage des mangues, le taux de perte actuel dans la coopérative Deggo Thies est de 15,71 %. En comparaison, le taux de perte de référence pour le séchage des mangues dans la région de l'Afrique de l'Ouest est de 12,0 %. Cela indique que les pertes de la coopérative sont supérieures à la référence.

Pour le lot spécifique LOT-MANG-001, le résumé des risques opérationnels indique une perte cumulative de 6,0 %, avec un risque classé comme faible. La phase la plus sensible est le séchage, avec une perte de 5,05 %. Cela montre que, bien que les pertes soient inférieures à celles observées au niveau coopératif, elles restent préoccupantes.

À un niveau de produit, le taux de perte pour le séchage des mangues est de 5,05 %, ce qui est supérieur à la perte moyenne de 3,03 % pour le produit mangue dans son ensemble. Cela suggère que le processus de séchage nécessite une attention particulière.

Comparé aux références, les pertes de la coopérative sont significativement plus élevées que celles observées dans d'autres contextes, ce qui pourrait indiquer des inefficacités dans le processus de séchage.

Il est recommandé d'examiner les processus

### which lot is most risky and what should we do?
- category: HYBRID
- intent: expected `HYBRID`, observed `HYBRID`
- sql_needed: True | rag_needed: True
- factual_accuracy_score: 0.8
- citation_relevance_score: 0.5
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 1.0
- passed: True
- warning_flags: ['ML_LOGS_EMPTY']
- chunk_types: {'operational_risk_summary': 2, 'lot_status_summary': 2}
- answer: For the specific lot, LOT-BISS-002 (Bissap) is the most risky, with a cumulative loss of 69.33% and classified as HIGH risk. The most sensitive stage is Sechage, which accounts for 68.0% of the loss. The recommended mitigation is to audit the full stage sequence to identify and address the issues causing such high losses.

At product-stage level, the Sechage stage for Bissap is critically underperforming, indicating a need for immediate attention to improve processing methods or conditions.

At cooperative level, the overall loss rate is 15.71%, with an efficiency rate of 84.29%. The average batch loss percentage across all lots is 25.11%, and the worst batch loss percentage is 69.33%. This suggests that while some lots are performing adequately, there are significant outliers that require focused intervention.

Compared with benchmark metrics, the current loss rates indicate that LOT-BISS-002 is significantly underperforming, as the average loss percentage is much lower than the 69.33% observed in this lot.

A practical next step is to conduct an audit of the Sechage stage for LOT-BISS-002 to identify specific issues and implement corrective actions.

### why does the ML prediction differ from current operational losses?
- category: HYBRID
- intent: expected `HYBRID`, observed `HYBRID`
- sql_needed: True | rag_needed: True
- factual_accuracy_score: 0.8
- citation_relevance_score: 0.0
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 1.0
- passed: False
- warning_flags: ['CONTRADICTORY_EVIDENCE', 'LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- chunk_types: {}
- answer: The ML prediction indicates a loss rate of 3.44%, while the current operational loss rate is 15.71%. This discrepancy arises from conflicting evidence between the SQL operational metrics and the ML predictions. Specifically, the average batch loss percentage is reported at 25.11%, which is significantly higher than the ML prediction.

For the specific lot, the average batch loss percentage (25.11%) suggests that there are batches experiencing higher losses, which the ML model may not be capturing accurately. The worst batch loss percentage is even higher at 69.33%, indicating that some batches are performing poorly.

At the cooperative level, the operational loss rate of 15.71% reflects the overall performance across all batches, which is not aligned with the ML prediction. This suggests that the ML model may not be fully accounting for the current operational realities.

Compared with benchmark data, the ML prediction appears to underestimate the actual losses experienced in the cooperative. The operational metrics indicate a more severe loss situation than what the ML model predicts.

ML interpretation indicates that the model may be outdated or not sufficiently trained on recent data, leading to a low-risk assessment that does not align with current operational facts. The confidence score of 0.42 suggests low reliability in the ML predictions.

A practical next step would be to review the ML model's training data and update it with the latest operational data to improve its accuracy in

### what is the best movie this week?
- category: UNSUPPORTED
- intent: expected `UNSUPPORTED`, observed `UNSUPPORTED`
- sql_needed: False | rag_needed: False
- factual_accuracy_score: 1.0
- citation_relevance_score: 0.0
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 1.0
- passed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE', 'SQL_CONTEXT_MISSING']
- chunk_types: {}
- answer: I am designed for agricultural cooperative operations: stocks, batches, post-harvest process, members, commercialization, invoicing, treasury, recommendations, and agronomic context. Please ask a question in that scope.

## Aggregate Metrics
- pass_rate: 0.9
- avg_factual_accuracy: 0.905
- avg_citation_relevance: 0.26
- avg_scope_purity: 1.0
- avg_answer_usefulness: 0.93
- SQL_ONLY pass rate: 1.0
- RAG_ONLY pass rate: 1.0
- HYBRID pass rate: 0.75
- unsupported pass rate: 1.0

## Failure Patterns
- Hybrid answers show weak citation relevance in some cases.

## Recommendation
Phase 6 should start only if hybrid and RAG-only pass rates are both >= 0.70 and no contamination failures are present.
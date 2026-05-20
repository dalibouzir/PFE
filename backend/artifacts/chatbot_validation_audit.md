# Chatbot Pre-Phase-6 Validation Audit

## Executive Summary
- Generated at: 2026-05-19T00:30:32.939621+00:00
- Pass rate: 0.0
- Avg factual accuracy: 0.695
- Avg citation relevance: 0.0
- Avg scope purity: 1.0
- Avg answer usefulness: 0.77

## Actual Data Snapshot
- Cooperative: 4cbc6020-def9-4d24-bb75-9d40bc031466
- Stocks tracked: 4
- Batches tracked: 23
- Mango drying weekly step count: 1
- Reference metric rows: 17

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
- passed: False
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- chunk_types: {}
- answer: Stock Mangue : total 5504.0 kg, 2350.0 kg réservés dans les lots, 3154.0 kg disponibles. Statut : stable.

### how much arachide stock is remaining?
- category: SQL_ONLY
- intent: expected `SQL_ONLY`, observed `SQL_ONLY`
- sql_needed: True | rag_needed: False
- factual_accuracy_score: 1.0
- citation_relevance_score: 0.0
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 0.9
- passed: False
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- chunk_types: {}
- answer: Stock Arachide : total 2991.0 kg, 1960.0 kg réservés dans les lots, 1031.0 kg disponibles. Statut : stable.

### what is the status of LOT-MANG-001?
- category: SQL_ONLY
- intent: expected `SQL_ONLY`, observed `SQL_ONLY`
- sql_needed: True | rag_needed: False
- factual_accuracy_score: 1.0
- citation_relevance_score: 0.0
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 0.9
- passed: False
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- chunk_types: {}
- answer: LOT-MANG-001 (Mangue) : statut completed, quantité initiale 250.0 kg, quantité actuelle 192.0 kg, perte cumulée 23.2%, dernière étape drying, étape en attente none, anomalie/risque none.

### what does benchmark say about millet losses?
- category: RAG_ONLY
- intent: expected `RAG_ONLY`, observed `RAG_ONLY`
- sql_needed: False | rag_needed: True
- factual_accuracy_score: 0.35
- citation_relevance_score: 0.0
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 0.7
- passed: False
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE', 'SQL_CONTEXT_MISSING']
- chunk_types: {}
- answer: Aucune preuve benchmark/agronomique n'a été récupérée pour cette question. Je ne peux pas fournir une réponse de référence fiable pour le moment.

### best practices for mango drying
- category: RAG_ONLY
- intent: expected `RAG_ONLY`, observed `RAG_ONLY`
- sql_needed: False | rag_needed: True
- factual_accuracy_score: 0.45
- citation_relevance_score: 0.0
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 0.7
- passed: False
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE', 'SQL_CONTEXT_MISSING']
- chunk_types: {}
- answer: Aucune preuve benchmark/agronomique n'a été récupérée pour cette question. Je ne peux pas fournir une réponse de référence fiable pour le moment.

### why are drying losses high this week for mango?
- category: HYBRID
- intent: expected `HYBRID`, observed `HYBRID`
- sql_needed: True | rag_needed: True
- factual_accuracy_score: 0.55
- citation_relevance_score: 0.0
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 0.7
- passed: False
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- chunk_types: {}
- answer: Le fournisseur LLM est indisponible. Analyse limitée aux données structurées et aux références disponibles. Sources clés: sql:ops-batch-loss-summary:avg_batch_loss_pct (avg_batch_loss_pct); sql:ops-batch-loss-summary:worst_batch_loss_pct (worst_batch_loss_pct). Données SQL clés: rag_hit_count=0.0 count; loss_rate=23.32 %.

### compare current mango drying losses with benchmark references
- category: HYBRID
- intent: expected `HYBRID`, observed `HYBRID`
- sql_needed: True | rag_needed: True
- factual_accuracy_score: 0.8
- citation_relevance_score: 0.0
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 0.9
- passed: False
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- chunk_types: {}
- answer: Le fournisseur LLM est indisponible. Analyse limitée aux données structurées et aux références disponibles. Sources clés: sql:ops-batch-loss-summary:avg_batch_loss_pct (avg_batch_loss_pct); sql:ops-batch-loss-summary:worst_batch_loss_pct (worst_batch_loss_pct). Données SQL clés: rag_hit_count=0.0 count; loss_rate=23.32 %.

### which lot is most risky and what should we do?
- category: HYBRID
- intent: expected `HYBRID`, observed `HYBRID`
- sql_needed: True | rag_needed: True
- factual_accuracy_score: 0.8
- citation_relevance_score: 0.0
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 0.9
- passed: False
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- chunk_types: {}
- answer: Le fournisseur LLM est indisponible. Analyse limitée aux données structurées et aux références disponibles. Sources clés: sql:ops-batch-loss-summary:avg_batch_loss_pct (avg_batch_loss_pct); sql:ops-batch-loss-summary:worst_batch_loss_pct (worst_batch_loss_pct). Données SQL clés: rag_hit_count=0.0 count; loss_rate=23.32 %.

### why does the ML prediction differ from current operational losses?
- category: HYBRID
- intent: expected `HYBRID`, observed `HYBRID`
- sql_needed: True | rag_needed: True
- factual_accuracy_score: 0.8
- citation_relevance_score: 0.0
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 0.9
- passed: False
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- chunk_types: {}
- answer: Le fournisseur LLM est indisponible. Analyse limitée aux données structurées et aux références disponibles. Sources clés: sql:ops-batch-loss-summary:avg_batch_loss_pct (avg_batch_loss_pct); sql:ops-batch-loss-summary:worst_batch_loss_pct (worst_batch_loss_pct). Données SQL clés: rag_hit_count=0.0 count; loss_rate=23.32 %.

### what is the best movie this week?
- category: UNSUPPORTED
- intent: expected `UNSUPPORTED`, observed `UNKNOWN`
- sql_needed: False | rag_needed: False
- factual_accuracy_score: 0.2
- citation_relevance_score: 0.0
- scope_purity_score: 1.0
- contamination_detected: False
- answer_usefulness_score: 0.2
- passed: False
- warning_flags: []
- chunk_types: {}
- answer: Cette question sort du périmètre actuel. Je peux répondre aux questions liées aux stocks, lots, pertes, transformation post-récolte, recommandations et indicateurs de la coopérative.

## Aggregate Metrics
- pass_rate: 0.0
- avg_factual_accuracy: 0.695
- avg_citation_relevance: 0.0
- avg_scope_purity: 1.0
- avg_answer_usefulness: 0.77
- SQL_ONLY pass rate: 0.0
- RAG_ONLY pass rate: 0.0
- HYBRID pass rate: 0.0
- unsupported pass rate: 0.0

## Failure Patterns
- Routing mismatch detected for one or more questions.
- Unsupported query handling is not consistently safe.
- Hybrid answers show weak citation relevance in some cases.

## Recommendation
Phase 6 should NOT start yet; resolve routing/grounding/citation gaps first.
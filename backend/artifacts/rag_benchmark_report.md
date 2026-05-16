# RAG Benchmark Report

Generated at: 2026-05-15T21:48:06.190493+00:00

## Summary
- scenarios: 10
- avg_retrieval_relevance_score: 0.0
- avg_grounding_score: 0.41
- avg_freshness_score: 0.5
- avg_SQL_alignment_score: 1.0
- avg_expected_chunk_coverage: 0.1
- avg_scope_purity_score: 1.0
- avg_contamination_rate: 0.0
- avg_operational_priority_score: 0.0

## Scenario Results

### current stock of mango
- intent_type: SQL_ONLY
- sql_needed: True
- rag_needed: False
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE', 'ML_LOGS_EMPTY']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.65}
- hit_count: 0
- chunk_types: {}
- freshness: {'freshness_count': 0}
- metrics: {'retrieval_relevance_score': 0.0, 'grounding_score': 0.41000000000000003, 'freshness_score': 0.5, 'citation_quality_score': 0.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.0, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 0.0, 'expected_chunk_coverage': 1.0, 'expected_chunk_hits': [], 'observed_chunk_types': [], 'filters_used_count': 2}
- latency_ms: 9.828

### why are drying losses high this week for mango?
- intent_type: HYBRID
- sql_needed: True
- rag_needed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE', 'ML_LOGS_EMPTY']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.65}
- hit_count: 0
- chunk_types: {}
- freshness: {'freshness_count': 0}
- metrics: {'retrieval_relevance_score': 0.0, 'grounding_score': 0.41000000000000003, 'freshness_score': 0.5, 'citation_quality_score': 0.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.0, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 0.0, 'expected_chunk_coverage': 0.0, 'expected_chunk_hits': [], 'observed_chunk_types': [], 'filters_used_count': 6}
- latency_ms: 3.313

### which lot is most risky and what should we do?
- intent_type: HYBRID
- sql_needed: True
- rag_needed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE', 'ML_LOGS_EMPTY']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.65}
- hit_count: 0
- chunk_types: {}
- freshness: {'freshness_count': 0}
- metrics: {'retrieval_relevance_score': 0.0, 'grounding_score': 0.41000000000000003, 'freshness_score': 0.5, 'citation_quality_score': 0.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.0, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 0.0, 'expected_chunk_coverage': 0.0, 'expected_chunk_hits': [], 'observed_chunk_types': [], 'filters_used_count': 2}
- latency_ms: 1.854

### what does benchmark say about millet losses?
- intent_type: RAG_ONLY
- sql_needed: False
- rag_needed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE', 'ML_LOGS_EMPTY']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.65}
- hit_count: 0
- chunk_types: {}
- freshness: {'freshness_count': 0}
- metrics: {'retrieval_relevance_score': 0.0, 'grounding_score': 0.41000000000000003, 'freshness_score': 0.5, 'citation_quality_score': 0.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.0, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 0.0, 'expected_chunk_coverage': 0.0, 'expected_chunk_hits': [], 'observed_chunk_types': [], 'filters_used_count': 3}
- latency_ms: 4.221

### what happened to LOT-MANG-004?
- intent_type: SQL_ONLY
- sql_needed: True
- rag_needed: False
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE', 'ML_LOGS_EMPTY']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.65}
- hit_count: 0
- chunk_types: {}
- freshness: {'freshness_count': 0}
- metrics: {'retrieval_relevance_score': 0.0, 'grounding_score': 0.41000000000000003, 'freshness_score': 0.5, 'citation_quality_score': 0.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.0, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 0.0, 'expected_chunk_coverage': 0.0, 'expected_chunk_hits': [], 'observed_chunk_types': [], 'filters_used_count': 2}
- latency_ms: 1.554

### why do recommendations conflict with current losses?
- intent_type: HYBRID
- sql_needed: True
- rag_needed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE', 'ML_LOGS_EMPTY']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.65}
- hit_count: 0
- chunk_types: {}
- freshness: {'freshness_count': 0}
- metrics: {'retrieval_relevance_score': 0.0, 'grounding_score': 0.41000000000000003, 'freshness_score': 0.5, 'citation_quality_score': 0.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.0, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 0.0, 'expected_chunk_coverage': 0.0, 'expected_chunk_hits': [], 'observed_chunk_types': [], 'filters_used_count': 3}
- latency_ms: 0.677

### why are mango drying losses high compared with bissap losses?
- intent_type: HYBRID
- sql_needed: True
- rag_needed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE', 'ML_LOGS_EMPTY']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.65}
- hit_count: 0
- chunk_types: {}
- freshness: {'freshness_count': 0}
- metrics: {'retrieval_relevance_score': 0.0, 'grounding_score': 0.41000000000000003, 'freshness_score': 0.5, 'citation_quality_score': 0.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.0, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 0.0, 'expected_chunk_coverage': 0.0, 'expected_chunk_hits': [], 'observed_chunk_types': [], 'filters_used_count': 5}
- latency_ms: 1.684

### what happened to LOT-MANG-004 and which stage caused losses?
- intent_type: HYBRID
- sql_needed: True
- rag_needed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE', 'ML_LOGS_EMPTY']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.65}
- hit_count: 0
- chunk_types: {}
- freshness: {'freshness_count': 0}
- metrics: {'retrieval_relevance_score': 0.0, 'grounding_score': 0.41000000000000003, 'freshness_score': 0.5, 'citation_quality_score': 0.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.0, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 0.0, 'expected_chunk_coverage': 0.0, 'expected_chunk_hits': [], 'observed_chunk_types': [], 'filters_used_count': 3}
- latency_ms: 1.667

### best practices benchmark for peanut storage losses in west africa
- intent_type: RAG_ONLY
- sql_needed: False
- rag_needed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE', 'ML_LOGS_EMPTY']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.65}
- hit_count: 0
- chunk_types: {}
- freshness: {'freshness_count': 0}
- metrics: {'retrieval_relevance_score': 0.0, 'grounding_score': 0.41000000000000003, 'freshness_score': 0.5, 'citation_quality_score': 0.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.0, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 0.0, 'expected_chunk_coverage': 0.0, 'expected_chunk_hits': [], 'observed_chunk_types': [], 'filters_used_count': 3}
- latency_ms: 1.574

### compare cooperative losses versus mango drying losses this month
- intent_type: HYBRID
- sql_needed: True
- rag_needed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE', 'ML_LOGS_EMPTY']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.65}
- hit_count: 0
- chunk_types: {}
- freshness: {'freshness_count': 0}
- metrics: {'retrieval_relevance_score': 0.0, 'grounding_score': 0.41000000000000003, 'freshness_score': 0.5, 'citation_quality_score': 0.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.0, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 0.0, 'expected_chunk_coverage': 0.0, 'expected_chunk_hits': [], 'observed_chunk_types': [], 'filters_used_count': 6}
- latency_ms: 1.475
# RAG Benchmark Report

Generated at: 2026-05-08T22:05:30.191514+00:00

## Summary
- scenarios: 10
- avg_retrieval_relevance_score: 0.2206
- avg_grounding_score: 0.552
- avg_freshness_score: 0.59
- avg_SQL_alignment_score: 1.0
- avg_expected_chunk_coverage: 0.1333
- avg_scope_purity_score: 0.9
- avg_contamination_rate: 0.1
- avg_operational_priority_score: 0.3

## Scenario Results

### current stock of mango
- intent_type: SQL_ONLY
- sql_needed: True
- rag_needed: False
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.67}
- hit_count: 0
- chunk_types: {}
- freshness: {'freshness_count': 0}
- metrics: {'retrieval_relevance_score': 0.0, 'grounding_score': 0.51, 'freshness_score': 0.5, 'citation_quality_score': 0.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.0, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 0.0, 'expected_chunk_coverage': 1.0, 'expected_chunk_hits': [], 'observed_chunk_types': [], 'filters_used_count': 2}
- latency_ms: 550.543

### why are drying losses high this week for mango?
- intent_type: HYBRID
- sql_needed: True
- rag_needed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.69}
- hit_count: 1
- chunk_types: {'scoped_loss_summary': 1}
- freshness: {'freshness_count': 1, 'freshness_min_minutes': 264.94, 'freshness_max_minutes': 264.94, 'freshness_avg_minutes': 264.94}
- metrics: {'retrieval_relevance_score': 1.0, 'grounding_score': 0.5299999999999999, 'freshness_score': 0.8, 'citation_quality_score': 0.6, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.5, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 1.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 1.0, 'expected_chunk_coverage': 0.0, 'expected_chunk_hits': [], 'observed_chunk_types': ['scoped_loss_summary'], 'filters_used_count': 6}
- latency_ms: 1650.321

### which lot is most risky and what should we do?
- intent_type: HYBRID
- sql_needed: True
- rag_needed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.67}
- hit_count: 0
- chunk_types: {}
- freshness: {'freshness_count': 0}
- metrics: {'retrieval_relevance_score': 0.0, 'grounding_score': 0.51, 'freshness_score': 0.5, 'citation_quality_score': 0.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.0, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 0.0, 'expected_chunk_coverage': 0.0, 'expected_chunk_hits': [], 'observed_chunk_types': [], 'filters_used_count': 2}
- latency_ms: 585.007

### what does benchmark say about millet losses?
- intent_type: RAG_ONLY
- sql_needed: False
- rag_needed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.67}
- hit_count: 0
- chunk_types: {}
- freshness: {'freshness_count': 0}
- metrics: {'retrieval_relevance_score': 0.0, 'grounding_score': 0.51, 'freshness_score': 0.5, 'citation_quality_score': 0.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.0, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 0.0, 'expected_chunk_coverage': 0.0, 'expected_chunk_hits': [], 'observed_chunk_types': [], 'filters_used_count': 3}
- latency_ms: 987.901

### what happened to LOT-MANG-004?
- intent_type: SQL_ONLY
- sql_needed: True
- rag_needed: False
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.67}
- hit_count: 0
- chunk_types: {}
- freshness: {'freshness_count': 0}
- metrics: {'retrieval_relevance_score': 0.0, 'grounding_score': 0.51, 'freshness_score': 0.5, 'citation_quality_score': 0.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.0, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 0.0, 'expected_chunk_coverage': 0.0, 'expected_chunk_hits': [], 'observed_chunk_types': [], 'filters_used_count': 2}
- latency_ms: 321.951

### why do recommendations conflict with current losses?
- intent_type: HYBRID
- sql_needed: True
- rag_needed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.67}
- hit_count: 0
- chunk_types: {}
- freshness: {'freshness_count': 0}
- metrics: {'retrieval_relevance_score': 0.0, 'grounding_score': 0.51, 'freshness_score': 0.5, 'citation_quality_score': 0.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.0, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 0.0, 'expected_chunk_coverage': 0.0, 'expected_chunk_hits': [], 'observed_chunk_types': [], 'filters_used_count': 3}
- latency_ms: 1220.776

### why are mango drying losses high compared with bissap losses?
- intent_type: HYBRID
- sql_needed: True
- rag_needed: True
- warning_flags: []
- confidence_estimate: {'label': 'HIGH', 'score': 0.85}
- hit_count: 5
- chunk_types: {'pre_harvest_context': 5}
- freshness: {'freshness_count': 5, 'freshness_min_minutes': 263.17, 'freshness_max_minutes': 263.6, 'freshness_avg_minutes': 263.45}
- metrics: {'retrieval_relevance_score': 0.4166666666666667, 'grounding_score': 0.85, 'freshness_score': 0.8, 'citation_quality_score': 1.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.5, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 1.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 1.0, 'expected_chunk_coverage': 0.0, 'expected_chunk_hits': [], 'observed_chunk_types': ['pre_harvest_context'], 'filters_used_count': 5}
- latency_ms: 1297.649

### what happened to LOT-MANG-004 and which stage caused losses?
- intent_type: HYBRID
- sql_needed: True
- rag_needed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.67}
- hit_count: 0
- chunk_types: {}
- freshness: {'freshness_count': 0}
- metrics: {'retrieval_relevance_score': 0.0, 'grounding_score': 0.51, 'freshness_score': 0.5, 'citation_quality_score': 0.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.0, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 0.0, 'expected_chunk_coverage': 0.0, 'expected_chunk_hits': [], 'observed_chunk_types': [], 'filters_used_count': 3}
- latency_ms: 938.962

### best practices benchmark for peanut storage losses in west africa
- intent_type: RAG_ONLY
- sql_needed: False
- rag_needed: True
- warning_flags: ['LIMITED_EVIDENCE', 'LOW_GROUNDING_CONFIDENCE']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.67}
- hit_count: 0
- chunk_types: {}
- freshness: {'freshness_count': 0}
- metrics: {'retrieval_relevance_score': 0.0, 'grounding_score': 0.51, 'freshness_score': 0.5, 'citation_quality_score': 0.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.0, 'scope_purity_score': 1.0, 'contamination_rate': 0.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.0, 'operational_priority_score': 0.0, 'expected_chunk_coverage': 0.0, 'expected_chunk_hits': [], 'observed_chunk_types': [], 'filters_used_count': 3}
- latency_ms: 1107.441

### compare cooperative losses versus mango drying losses this month
- intent_type: HYBRID
- sql_needed: True
- rag_needed: True
- warning_flags: ['LOW_GROUNDING_CONFIDENCE', 'SCOPE_CONTAMINATION_RISK']
- confidence_estimate: {'label': 'MEDIUM', 'score': 0.73}
- hit_count: 6
- chunk_types: {'scoped_loss_summary': 6}
- freshness: {'freshness_count': 6, 'freshness_min_minutes': 264.67, 'freshness_max_minutes': 264.83, 'freshness_avg_minutes': 264.76}
- metrics: {'retrieval_relevance_score': 0.788888888888889, 'grounding_score': 0.57, 'freshness_score': 0.8, 'citation_quality_score': 1.0, 'contradiction_rate': 0.0, 'SQL_alignment_score': 1.0, 'chunk_diversity_score': 0.5, 'scope_purity_score': 0.0, 'contamination_rate': 1.0, 'product_alignment_score': 0.0, 'stage_alignment_score': 0.5, 'operational_priority_score': 1.0, 'expected_chunk_coverage': 0.3333, 'expected_chunk_hits': ['scoped_loss_summary'], 'observed_chunk_types': ['scoped_loss_summary'], 'filters_used_count': 6}
- latency_ms: 1169.056
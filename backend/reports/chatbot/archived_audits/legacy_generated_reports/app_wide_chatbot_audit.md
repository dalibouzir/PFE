# App-wide Chatbot Audit

## Executive Summary
- Total: 46 | PASS=35 | PARTIAL=11 | FAIL=0
- Route status: exact=45 | compatible=1 | failure=0
- SQL/ML contradiction warnings: explained=2 | unresolved=5

## Coverage Matrix
| Module | list | detail | count_summary | filter | ambiguous | empty_missing | high_risk | low_risk | multi_turn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AI recommendations | N/A | PASS | N/A | N/A | PARTIAL | PARTIAL | PASS | N/A | N/A |
| ML risk/anomaly insights | PARTIAL | N/A | N/A | N/A | N/A | PASS | PARTIAL | N/A | N/A |
| RAG explanations/best practices | PASS | PASS | N/A | N/A | N/A | N/A | PASS | N/A | N/A |
| collections/inputs | PASS | N/A | PASS | PASS | PASS | PASS | N/A | N/A | N/A |
| efficiency analysis | N/A | N/A | N/A | N/A | N/A | N/A | PASS | N/A | N/A |
| loss analysis | N/A | PASS | N/A | N/A | N/A | N/A | N/A | PASS | N/A |
| lots/batches | PASS | PASS | N/A | N/A | N/A | N/A | PASS | N/A | N/A |
| material balance | N/A | PASS | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| members/farmers | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PASS | PARTIAL | N/A | N/A | N/A |
| memory/context | PASS | N/A | N/A | N/A | N/A | N/A | PARTIAL | N/A | PARTIAL |
| parcels/cultures | PASS | PASS | PASS | PASS | N/A | N/A | N/A | N/A | N/A |
| post-harvest process steps | N/A | N/A | N/A | PASS | N/A | N/A | PASS | N/A | N/A |
| pre-harvest steps | PASS | N/A | PASS | N/A | N/A | N/A | N/A | N/A | N/A |
| route-type | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| stocks | PASS | PASS | N/A | PASS | N/A | PASS | PASS | N/A | N/A |

## Results By Module
| Module | PASS | PARTIAL | FAIL |
| --- | ---: | ---: | ---: |
| AI recommendations | 2 | 1 | 0 |
| ML risk/anomaly insights | 1 | 3 | 0 |
| RAG explanations/best practices | 4 | 0 | 0 |
| collections/inputs | 5 | 0 | 0 |
| efficiency analysis | 1 | 0 | 0 |
| loss analysis | 1 | 0 | 0 |
| lots/batches | 3 | 0 | 0 |
| material balance | 1 | 0 | 0 |
| members/farmers | 1 | 5 | 0 |
| memory/context | 2 | 2 | 0 |
| parcels/cultures | 4 | 0 | 0 |
| post-harvest process steps | 2 | 0 | 0 |
| pre-harvest steps | 2 | 0 | 0 |
| route-type | 2 | 0 | 0 |
| stocks | 4 | 0 | 0 |

## Results By Route Type
| Route type | PASS | PARTIAL | FAIL |
| --- | ---: | ---: | ---: |
| HYBRID_FULL | 1 | 1 | 0 |
| HYBRID_RAG_RECOMMENDATION | 1 | 0 | 0 |
| HYBRID_SQL_ML | 1 | 5 | 0 |
| HYBRID_SQL_RAG | 3 | 0 | 0 |
| RAG_ONLY | 3 | 0 | 0 |
| SQL_ONLY | 26 | 5 | 0 |

## Results By Data State
| Data state | PASS | PARTIAL | FAIL |
| --- | ---: | ---: | ---: |
| ambiguous | 2 | 0 | 0 |
| high_risk | 8 | 5 | 0 |
| low_risk | 1 | 0 | 0 |
| missing | 3 | 2 | 0 |
| normal | 21 | 4 | 0 |

## Failure Categories
- CONTENT_SEMANTIC_ERROR: 5
- CONTRADICTION_NOT_EXPLAINED: 5
- UNSUPPORTED_RECOMMENDATION: 1

## Uncovered Areas
- AI recommendations: list, count_summary, filter, low_risk, multi_turn
- ML risk/anomaly insights: detail, count_summary, filter, ambiguous, low_risk, multi_turn
- RAG explanations/best practices: count_summary, filter, ambiguous, empty_missing, low_risk, multi_turn
- collections/inputs: detail, high_risk, low_risk, multi_turn
- efficiency analysis: list, detail, count_summary, filter, ambiguous, empty_missing, low_risk, multi_turn
- loss analysis: list, count_summary, filter, ambiguous, empty_missing, high_risk, multi_turn
- lots/batches: count_summary, filter, ambiguous, empty_missing, low_risk, multi_turn
- material balance: list, count_summary, filter, ambiguous, empty_missing, high_risk, low_risk, multi_turn
- members/farmers: high_risk, low_risk, multi_turn
- memory/context: detail, count_summary, filter, ambiguous, empty_missing, low_risk
- parcels/cultures: ambiguous, empty_missing, high_risk, low_risk, multi_turn
- post-harvest process steps: list, detail, count_summary, ambiguous, empty_missing, low_risk, multi_turn
- pre-harvest steps: detail, filter, ambiguous, empty_missing, high_risk, low_risk, multi_turn
- route-type: list, detail, count_summary, filter, ambiguous, empty_missing, high_risk, low_risk, multi_turn
- stocks: count_summary, ambiguous, low_risk, multi_turn

## Suspected Root Causes
- CONTENT_SEMANTIC_ERROR (5): CONTENT_SEMANTIC_ERROR
- CONTRADICTION_NOT_EXPLAINED (5): Contradiction SQL/ML non explicitée.
- UNSUPPORTED_RECOMMENDATION (1): Recommandation prioritaire sans base de preuve suffisante.

## Exact Next Recommended Fix
- Corriger en priorité la conformité linguistique des réponses stock SQL (cas partiels NOT_FRENCH), puis affiner l’extraction d’entités dans les cas ML ambigus restants.

## Detailed Cases
| Case | Module | Route exp/act | Route status | Data state | Status | Failures |
| --- | --- | --- | --- | --- | --- | --- |
| mbr-01 | members/farmers | SQL_ONLY / SQL_ONLY | exact_match | normal | PARTIAL | CONTENT_SEMANTIC_ERROR |
| mbr-02 | members/farmers | SQL_ONLY / SQL_ONLY | exact_match | normal | PARTIAL | CONTENT_SEMANTIC_ERROR |
| mbr-03 | members/farmers | SQL_ONLY / SQL_ONLY | exact_match | normal | PARTIAL | CONTENT_SEMANTIC_ERROR |
| mbr-04 | members/farmers | SQL_ONLY / SQL_ONLY | exact_match | normal | PARTIAL | CONTENT_SEMANTIC_ERROR |
| mbr-05 | members/farmers | SQL_ONLY / SQL_ONLY | exact_match | ambiguous | PASS | - |
| mbr-06 | members/farmers | SQL_ONLY / SQL_ONLY | exact_match | missing | PARTIAL | CONTENT_SEMANTIC_ERROR |
| par-01 | parcels/cultures | SQL_ONLY / SQL_ONLY | exact_match | normal | PASS | - |
| par-02 | parcels/cultures | SQL_ONLY / SQL_ONLY | exact_match | normal | PASS | - |
| par-03 | parcels/cultures | SQL_ONLY / SQL_ONLY | exact_match | normal | PASS | - |
| par-04 | parcels/cultures | SQL_ONLY / SQL_ONLY | exact_match | normal | PASS | - |
| par-05 | pre-harvest steps | SQL_ONLY / SQL_ONLY | exact_match | normal | PASS | - |
| par-06 | pre-harvest steps | SQL_ONLY / SQL_ONLY | exact_match | normal | PASS | - |
| col-01 | collections/inputs | SQL_ONLY / SQL_ONLY | exact_match | normal | PASS | - |
| col-02 | collections/inputs | SQL_ONLY / SQL_ONLY | exact_match | normal | PASS | - |
| col-03 | collections/inputs | SQL_ONLY / SQL_ONLY | exact_match | normal | PASS | - |
| col-04 | collections/inputs | SQL_ONLY / SQL_ONLY | exact_match | missing | PASS | - |
| col-05 | collections/inputs | SQL_ONLY / SQL_ONLY | exact_match | ambiguous | PASS | - |
| stk-01 | stocks | SQL_ONLY / SQL_ONLY | exact_match | normal | PASS | - |
| stk-02 | stocks | SQL_ONLY / SQL_ONLY | exact_match | normal | PASS | - |
| stk-03 | stocks | SQL_ONLY / SQL_ONLY | exact_match | high_risk | PASS | - |
| stk-04 | stocks | SQL_ONLY / SQL_ONLY | exact_match | missing | PASS | - |
| lot-01 | lots/batches | SQL_ONLY / SQL_ONLY | exact_match | normal | PASS | - |
| lot-02 | lots/batches | SQL_ONLY / SQL_ONLY | exact_match | high_risk | PASS | - |
| lot-03 | lots/batches | SQL_ONLY / SQL_ONLY | exact_match | high_risk | PASS | - |
| proc-01 | post-harvest process steps | SQL_ONLY / SQL_ONLY | exact_match | high_risk | PASS | - |
| proc-02 | post-harvest process steps | SQL_ONLY / SQL_ONLY | exact_match | normal | PASS | - |
| mat-01 | material balance | HYBRID_SQL_RAG / HYBRID_SQL_RAG | exact_match | normal | PASS | - |
| eff-01 | efficiency analysis | SQL_ONLY / SQL_ONLY | exact_match | high_risk | PASS | - |
| ml-01 | ML risk/anomaly insights | HYBRID_SQL_ML / HYBRID_SQL_ML | exact_match | high_risk | PARTIAL | CONTRADICTION_NOT_EXPLAINED |
| ml-02 | ML risk/anomaly insights | HYBRID_SQL_ML / HYBRID_SQL_ML | exact_match | high_risk | PARTIAL | CONTRADICTION_NOT_EXPLAINED |
| ml-03 | ML risk/anomaly insights | HYBRID_SQL_ML / HYBRID_SQL_ML | exact_match | high_risk | PARTIAL | CONTRADICTION_NOT_EXPLAINED |
| ml-04 | ML risk/anomaly insights | HYBRID_SQL_ML / HYBRID_SQL_ML | exact_match | missing | PASS | - |
| ml-05 | loss analysis | SQL_ONLY / SQL_ONLY | exact_match | low_risk | PASS | - |
| rag-01 | RAG explanations/best practices | RAG_ONLY / RAG_ONLY | exact_match | normal | PASS | - |
| rag-02 | RAG explanations/best practices | RAG_ONLY / RAG_ONLY | exact_match | normal | PASS | - |
| rag-03 | RAG explanations/best practices | RAG_ONLY / RAG_ONLY | exact_match | normal | PASS | - |
| rag-04 | RAG explanations/best practices | HYBRID_SQL_RAG / HYBRID_SQL_RAG | exact_match | high_risk | PASS | - |
| rec-01 | AI recommendations | HYBRID_FULL / HYBRID_FULL | exact_match | high_risk | PASS | - |
| rec-02 | AI recommendations | HYBRID_RAG_RECOMMENDATION / HYBRID_FULL | compatible_route | normal | PASS | - |
| rec-03 | AI recommendations | RECOMMENDATION_ONLY / RECOMMENDATION_ONLY | exact_match | missing | PARTIAL | UNSUPPORTED_RECOMMENDATION |
| mem-01 | memory/context | SQL_ONLY / SQL_ONLY | exact_match | normal | PASS | - |
| mem-02 | memory/context | HYBRID_SQL_ML / HYBRID_SQL_ML | exact_match | high_risk | PARTIAL | CONTRADICTION_NOT_EXPLAINED |
| mem-03 | memory/context | HYBRID_SQL_ML / HYBRID_SQL_ML | exact_match | high_risk | PARTIAL | CONTRADICTION_NOT_EXPLAINED |
| mem-04 | memory/context | SQL_ONLY / SQL_ONLY | exact_match | normal | PASS | - |
| rt-01 | route-type | HYBRID_SQL_RAG / HYBRID_SQL_RAG | exact_match | high_risk | PASS | - |
| rt-02 | route-type | SQL_ONLY / SQL_ONLY | exact_match | normal | PASS | - |
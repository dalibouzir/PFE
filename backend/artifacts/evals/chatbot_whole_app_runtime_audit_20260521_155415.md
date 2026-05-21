# Chatbot Whole-App Runtime Audit

- Generated at: `2026-05-21T14:54:15.176310+00:00`
- Total cases: `60`
- PASS/PARTIAL/FAIL: `17/2/41`

## Score by Module

| Module | PASS | PARTIAL | FAIL |
|---|---:|---:|---:|
| collectes | 0 | 0 | 6 |
| commercial | 0 | 0 | 6 |
| dashboard | 2 | 0 | 4 |
| invoices | 0 | 0 | 4 |
| lots | 1 | 0 | 2 |
| material_balance | 3 | 0 | 1 |
| members | 2 | 0 | 4 |
| memory | 1 | 0 | 0 |
| ml | 0 | 0 | 2 |
| process_steps | 0 | 0 | 3 |
| rag | 2 | 0 | 1 |
| recommendations | 1 | 2 | 1 |
| stock_movements | 2 | 0 | 0 |
| stocks | 3 | 0 | 3 |
| treasury | 0 | 0 | 4 |

## Score by Failure Category

| Failure category | Count |
|---|---:|
| SQL_OPERATION_MISSING | 33 |
| NO_FAILURE | 17 |
| INTENT_MISMATCH | 4 |
| ROUTING_ERROR | 4 |
| EVIDENCE_INSUFFICIENT | 1 |
| WARNING_NOISE | 1 |

## Top 10 P0 Failures

| QID | Module | Category | Reason | Route | Intent |
|---|---|---|---|---|---|
| O06 | commercial | SQL_OPERATION_MISSING | no sql_dispatch_trace.sql_operation | SQL_ONLY | factual_sql |
| O04 | commercial | SQL_OPERATION_MISSING | no sql_dispatch_trace.sql_operation | SQL_ONLY | factual_sql |
| T02 | treasury | SQL_OPERATION_MISSING | no sql_dispatch_trace.sql_operation | SQL_ONLY | factual_sql |
| O05 | commercial | SQL_OPERATION_MISSING | no sql_dispatch_trace.sql_operation | SQL_ONLY | factual_sql |
| F02 | invoices | SQL_OPERATION_MISSING | no sql_dispatch_trace.sql_operation | SQL_ONLY | factual_sql |
| T01 | treasury | SQL_OPERATION_MISSING | no sql_dispatch_trace.sql_operation | SQL_ONLY | factual_sql |
| T03 | treasury | SQL_OPERATION_MISSING | no sql_dispatch_trace.sql_operation | SQL_ONLY | factual_sql |
| L03 | lots | SQL_OPERATION_MISSING | no sql_dispatch_trace.sql_operation | SQL_ONLY | factual_sql |
| O02 | commercial | SQL_OPERATION_MISSING | no sql_dispatch_trace.sql_operation | SQL_ONLY | factual_sql |
| M03 | members | SQL_OPERATION_MISSING | no sql_dispatch_trace.sql_operation | SQL_ONLY | factual_sql |

## Full Results

| QID | Module | Status | Failure | Expected route | Actual route | Expected intent | Actual intent | SQL op | Evidence rows | Confidence |
|---|---|---|---|---|---|---|---|---|---:|---:|
| D01 | dashboard | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| D02 | dashboard | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | PREHARVEST_STEPS | get_parcel_preharvest_status | 5 | 0.94 |
| D03 | dashboard | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| D04 | dashboard | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.26 |
| D05 | dashboard | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.96 |
| D06 | dashboard | FAIL | INTENT_MISMATCH | SQL_ONLY | SQL_ONLY | LOSS_RANKING | factual_sql |  | 0 | 0.26 |
| S01 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| S02 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| S03 | stocks | FAIL | INTENT_MISMATCH | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | factual_sql |  | 0 | 0.94 |
| S04 | stocks | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.42 |
| S05 | stock_movements | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| S06 | stock_movements | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| S07 | stocks | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.96 |
| S08 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| C01 | collectes | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| C02 | collectes | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.96 |
| C03 | collectes | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| C04 | collectes | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.26 |
| C05 | collectes | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.26 |
| C06 | collectes | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| M01 | members | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| M02 | members | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.26 |
| M03 | members | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.96 |
| M04 | members | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.42 |
| M05 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | PREHARVEST_STEPS | get_parcel_preharvest_status | 4 | 0.94 |
| M06 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | PREHARVEST_STEPS | get_parcel_preharvest_status | 5 | 0.94 |
| L01 | lots | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | POSTHARVEST_AVAILABLE_LOTS | POSTHARVEST_AVAILABLE_LOTS | get_available_postharvest_lots | 2 | 0.94 |
| L02 | lots | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.26 |
| L03 | lots | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.26 |
| L04 | material_balance | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | LOSS_RANKING | LOSS_RANKING | get_canonical_material_balance | 2 | 0.94 |
| L05 | material_balance | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | INPUT_OUTPUT_GAP | INPUT_OUTPUT_GAP | get_canonical_material_balance | 2 | 0.94 |
| L06 | material_balance | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | LOT_COMPARISON | LOT_COMPARISON | get_canonical_material_balance_for_lots | 2 | 0.94 |
| L07 | process_steps | FAIL | INTENT_MISMATCH | SQL_ONLY | SQL_ONLY | STAGE_LOSS_ANALYSIS | factual_sql |  | 0 | 0.26 |
| L08 | process_steps | FAIL | INTENT_MISMATCH | SQL_ONLY | SQL_ONLY | STAGE_LOSS_ANALYSIS | factual_sql |  | 0 | 0.26 |
| L09 | process_steps | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.14 |
| L10 | material_balance | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.26 |
| R01 | recommendations | PARTIAL | WARNING_NOISE | HYBRID_FULL | HYBRID_FULL | LOT_SPECIFIC_RECOMMENDATION | LOT_SPECIFIC_RECOMMENDATION | get_canonical_material_balance | 1 | 0.21 |
| R02 | recommendations | PASS | NO_FAILURE | HYBRID_FULL | HYBRID_FULL | RECOMMENDATION | RECOMMENDATION | get_canonical_material_balance | 2 | 0.43 |
| R03 | recommendations | PARTIAL | EVIDENCE_INSUFFICIENT | HYBRID_FULL | HYBRID_FULL | action_recommendation | action_recommendation |  | 0 | 0.42 |
| R04 | recommendations | FAIL | ROUTING_ERROR | HYBRID_FULL | RECOMMENDATION_ONLY | RECOMMENDATION | RECOMMENDATION |  | 0 | 0.23 |
| G01 | rag | FAIL | ROUTING_ERROR | RAG_ONLY | HYBRID_SQL_RAG | BEST_PRACTICES | hybrid_analysis |  | 0 | 0.52 |
| G02 | rag | PASS | NO_FAILURE | RAG_ONLY | RAG_ONLY | BEST_PRACTICES | BEST_PRACTICES |  | 0 | 0.61 |
| G03 | rag | PASS | NO_FAILURE | RAG_ONLY | RAG_ONLY | BEST_PRACTICES | BEST_PRACTICES |  | 0 | 0.12 |
| O01 | commercial | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| O02 | commercial | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| O03 | commercial | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| O04 | commercial | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| O05 | commercial | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| O06 | commercial | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| F01 | invoices | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.34 |
| F02 | invoices | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| F03 | invoices | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| F04 | invoices | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| T01 | treasury | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| T02 | treasury | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| T03 | treasury | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| T04 | treasury | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql |  | 0 | 0.94 |
| ML1 | ml | FAIL | ROUTING_ERROR | ML_ONLY | HYBRID_SQL_ML | risk_ml | risk_ml |  | 0 | 0.55 |
| ML2 | ml | FAIL | ROUTING_ERROR | ML_ONLY | HYBRID_SQL_ML | risk_ml | RISK_ANALYSIS | get_canonical_material_balance | 2 | 0.62 |
| MEM1 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 1 | 0.94 |

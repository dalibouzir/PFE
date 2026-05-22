# Chatbot Whole-App Runtime Audit (Latency)

- Generated at: `2026-05-22T02:56:13.019474+00:00`
- Total cases: `25`
- PASS/PARTIAL/FAIL: `17/6/2`

## Score by Module

| Module | PASS | PARTIAL | FAIL |
|---|---:|---:|---:|
| collectes | 1 | 0 | 0 |
| commercial | 1 | 1 | 0 |
| invoices | 1 | 1 | 0 |
| lots | 1 | 0 | 0 |
| material_balance | 2 | 0 | 1 |
| members | 2 | 1 | 0 |
| memory | 2 | 0 | 0 |
| ml | 1 | 0 | 0 |
| process_steps | 1 | 0 | 0 |
| rag | 2 | 0 | 0 |
| recommendations | 0 | 1 | 1 |
| stock_movements | 1 | 0 | 0 |
| stocks | 2 | 1 | 0 |
| treasury | 0 | 1 | 0 |

## Score by Failure Category

| Failure category | Count |
|---|---:|
| NO_FAILURE | 17 |
| LATENCY_SLOW_PATH | 6 |
| ROUTING_ERROR | 2 |

## Top 10 P0 Failures

| QID | Module | Category | Reason | Route | Intent |
|---|---|---|---|---|---|
| LT19 | material_balance | ROUTING_ERROR | expected route HYBRID_FULL, got SQL_ONLY | SQL_ONLY | LOSS_RANKING |
| LT18 | recommendations | ROUTING_ERROR | expected route HYBRID_FULL, got SQL_ONLY | SQL_ONLY | factual_sql |

## Full Results

| QID | Module | Status | Failure | Expected route | Actual route | Expected intent | Actual intent | SQL op | Evidence rows | Confidence |
|---|---|---|---|---|---|---|---|---|---:|---:|
| LT01 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| LT02 | stocks | PARTIAL | LATENCY_SLOW_PATH | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| LT03 | stock_movements | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_stock_movements_journal | 10 | 0.96 |
| LT04 | collectes | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_collections_summary | 1 | 0.96 |
| LT05 | members | PARTIAL | LATENCY_SLOW_PATH | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_members_list | 4 | 0.94 |
| LT06 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_top_farmers | 1 | 0.96 |
| LT07 | commercial | PARTIAL | LATENCY_SLOW_PATH | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_commercial_orders_summary | 4 | 0.94 |
| LT08 | invoices | PARTIAL | LATENCY_SLOW_PATH | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_invoices_summary | 4 | 0.94 |
| LT09 | treasury | PARTIAL | LATENCY_SLOW_PATH | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_treasury_traceability | 10 | 0.96 |
| LT10 | material_balance | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | LOSS_RANKING | LOSS_RANKING | get_canonical_material_balance | 2 | 0.94 |
| LT11 | material_balance | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | INPUT_OUTPUT_GAP | INPUT_OUTPUT_GAP | get_canonical_material_balance | 2 | 0.94 |
| LT12 | process_steps | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STAGE_LOSS_ANALYSIS | STAGE_LOSS_ANALYSIS | get_stage_loss_analysis | 3 | 0.94 |
| LT13 | lots | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | POSTHARVEST_AVAILABLE_LOTS | POSTHARVEST_AVAILABLE_LOTS | get_available_postharvest_lots | 2 | 0.94 |
| LT14 | rag | PASS | NO_FAILURE | RAG_ONLY | RAG_ONLY | BEST_PRACTICES | BEST_PRACTICES |  | 0 | 0.61 |
| LT15 | rag | PASS | NO_FAILURE | RAG_ONLY | RAG_ONLY | BEST_PRACTICES | BEST_PRACTICES |  | 0 | 0.61 |
| LT16 | ml | PASS | NO_FAILURE | ML_ONLY | ML_ONLY | risk_ml | risk_ml |  | 1 | 0.77 |
| LT17 | recommendations | PARTIAL | LATENCY_SLOW_PATH | HYBRID_FULL | HYBRID_FULL | LOT_SPECIFIC_RECOMMENDATION | LOT_SPECIFIC_RECOMMENDATION | get_canonical_material_balance | 1 | 0.85 |
| LT18 | recommendations | FAIL | ROUTING_ERROR | HYBRID_FULL | SQL_ONLY | RECOMMENDATION | factual_sql | get_process_step_losses | 4 | 0.31 |
| LT19 | material_balance | FAIL | ROUTING_ERROR | HYBRID_FULL | SQL_ONLY | HYBRID_ANALYSIS | LOSS_RANKING | get_canonical_material_balance | 1 | 0.94 |
| LT20 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_low_stock_alerts | 0 | 0.78 |
| LT21 | invoices | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | avg_paid_invoices_current_quarter | 0 | 0.78 |
| LT22 | memory | PASS | NO_FAILURE | HYBRID_FULL | HYBRID_FULL | LOT_SPECIFIC_RECOMMENDATION | FOLLOW_UP | get_canonical_material_balance | 1 | 0.85 |
| LT23 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | FOLLOW_UP | clarification_required | 0 | 0.41 |
| LT24 | commercial | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | top_customer_by_orders | 1 | 0.96 |
| LT25 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_process_step_losses | 4 | 0.31 |

## Latency Details

| QID | Total ms | SQL ms | RAG ms | ML ms | LLM ms | Compose ms | Class |
|---|---:|---:|---:|---:|---:|---:|---|
| LT01 | 8726.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT02 | 10331.45 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | CRITICAL |
| LT03 | 8684.50 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT04 | 8204.50 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT05 | 10226.63 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | CRITICAL |
| LT06 | 9930.56 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT07 | 11985.04 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | CRITICAL |
| LT08 | 10090.23 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | CRITICAL |
| LT09 | 11512.05 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | CRITICAL |
| LT10 | 7908.56 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT11 | 8146.29 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT12 | 8025.70 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT13 | 8084.58 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT14 | 3721.44 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | ACCEPTABLE |
| LT15 | 5602.24 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | ACCEPTABLE |
| LT16 | 1571.84 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | FAST |
| LT17 | 11314.46 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | CRITICAL |
| LT18 | 7949.26 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT19 | 10552.03 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | CRITICAL |
| LT20 | 7880.64 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT21 | 8133.18 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT22 | 19433.47 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | CRITICAL |
| LT23 | 23959.63 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | CRITICAL |
| LT24 | 8001.37 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT25 | 8127.42 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |

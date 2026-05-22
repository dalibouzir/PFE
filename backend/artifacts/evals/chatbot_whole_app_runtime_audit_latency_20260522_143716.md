# Chatbot Whole-App Runtime Audit (Latency)

- Generated at: `2026-05-22T13:37:16.674918+00:00`
- Total cases: `25`
- PASS/PARTIAL/FAIL: `25/0/0`

## Score by Module

| Module | PASS | PARTIAL | FAIL |
|---|---:|---:|---:|
| collectes | 1 | 0 | 0 |
| commercial | 2 | 0 | 0 |
| invoices | 2 | 0 | 0 |
| lots | 1 | 0 | 0 |
| material_balance | 3 | 0 | 0 |
| members | 3 | 0 | 0 |
| memory | 2 | 0 | 0 |
| ml | 1 | 0 | 0 |
| process_steps | 1 | 0 | 0 |
| rag | 2 | 0 | 0 |
| recommendations | 2 | 0 | 0 |
| stock_movements | 1 | 0 | 0 |
| stocks | 3 | 0 | 0 |
| treasury | 1 | 0 | 0 |

## Score by Failure Category

| Failure category | Count |
|---|---:|
| NO_FAILURE | 25 |

## Top 10 P0 Failures

| QID | Module | Category | Reason | Route | Intent |
|---|---|---|---|---|---|

## Full Results

| QID | Module | Status | Failure | Expected route | Actual route | Expected intent | Actual intent | SQL op | Evidence rows | Confidence |
|---|---|---|---|---|---|---|---|---|---:|---:|
| LT01 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| LT02 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| LT03 | stock_movements | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_stock_movements_journal | 10 | 0.96 |
| LT04 | collectes | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_collections_summary | 1 | 0.96 |
| LT05 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_members_list | 4 | 0.94 |
| LT06 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_top_farmers | 1 | 0.96 |
| LT07 | commercial | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_commercial_orders_summary | 4 | 0.94 |
| LT08 | invoices | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_invoices_summary | 4 | 0.94 |
| LT09 | treasury | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_treasury_traceability | 10 | 0.96 |
| LT10 | material_balance | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | LOSS_RANKING | LOSS_RANKING | get_canonical_material_balance | 2 | 0.94 |
| LT11 | material_balance | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | INPUT_OUTPUT_GAP | INPUT_OUTPUT_GAP | get_canonical_material_balance | 2 | 0.94 |
| LT12 | process_steps | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STAGE_LOSS_ANALYSIS | STAGE_LOSS_ANALYSIS | get_stage_loss_analysis | 3 | 0.94 |
| LT13 | lots | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | POSTHARVEST_AVAILABLE_LOTS | POSTHARVEST_AVAILABLE_LOTS | get_available_postharvest_lots | 2 | 0.94 |
| LT14 | rag | PASS | NO_FAILURE | RAG_ONLY | RAG_ONLY | BEST_PRACTICES | BEST_PRACTICES |  | 0 | 0.61 |
| LT15 | rag | PASS | NO_FAILURE | RAG_ONLY | RAG_ONLY | BEST_PRACTICES | BEST_PRACTICES |  | 0 | 0.61 |
| LT16 | ml | PASS | NO_FAILURE | ML_ONLY | ML_ONLY | risk_ml | risk_ml |  | 1 | 0.77 |
| LT17 | recommendations | PASS | NO_FAILURE | HYBRID_FULL | HYBRID_FULL | LOT_SPECIFIC_RECOMMENDATION | LOT_SPECIFIC_RECOMMENDATION | get_canonical_material_balance | 1 | 0.85 |
| LT18 | recommendations | PASS | NO_FAILURE | HYBRID_FULL | HYBRID_FULL | RECOMMENDATION | RECOMMENDATION | get_canonical_material_balance | 2 | 0.55 |
| LT19 | material_balance | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | INPUT_OUTPUT_GAP | get_canonical_material_balance | 1 | 0.94 |
| LT20 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_low_stock_alerts | 0 | 0.78 |
| LT21 | invoices | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | avg_paid_invoices_current_quarter | 0 | 0.78 |
| LT22 | memory | PASS | NO_FAILURE | HYBRID_FULL | HYBRID_FULL | LOT_SPECIFIC_RECOMMENDATION | FOLLOW_UP | get_canonical_material_balance | 1 | 0.85 |
| LT23 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | FOLLOW_UP | clarification_required | 0 | 0.41 |
| LT24 | commercial | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | top_customer_by_orders | 1 | 0.96 |
| LT25 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_process_step_losses | 4 | 0.31 |

## Latency Details

| QID | Total ms | SQL ms | RAG ms | ML ms | LLM ms | Compose ms | Class |
|---|---:|---:|---:|---:|---:|---:|---|
| LT01 | 8119.00 | 7796.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT02 | 7328.00 | 7013.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT03 | 7972.00 | 7650.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT04 | 7220.00 | 6875.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT05 | 7453.00 | 7141.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT06 | 7360.00 | 7045.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT07 | 8872.00 | 8560.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT08 | 8826.00 | 8496.00 | 0.00 | 0.00 | 2.00 | 2.00 | SLOW |
| LT09 | 7932.00 | 7612.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT10 | 7333.00 | 7024.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT11 | 7380.00 | 7084.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT12 | 7398.00 | 7085.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT13 | 7502.00 | 7178.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT14 | 2772.00 | 0.00 | 833.00 | 0.00 | 1646.00 | 1646.00 | ACCEPTABLE |
| LT15 | 2193.00 | 0.00 | 672.00 | 0.00 | 1225.00 | 1225.00 | ACCEPTABLE |
| LT16 | 419.00 | 0.00 | 0.00 | 100.00 | 0.00 | 0.00 | FAST |
| LT17 | 10447.00 | 7141.00 | 658.00 | 170.00 | 2127.00 | 2127.00 | CRITICAL |
| LT18 | 12012.00 | 7062.00 | 784.00 | 157.00 | 3649.00 | 3649.00 | CRITICAL |
| LT19 | 8038.00 | 7748.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT20 | 7395.00 | 7093.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT21 | 7423.00 | 7108.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT22 | 21653.99 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | CRITICAL |
| LT23 | 26449.41 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | CRITICAL |
| LT24 | 7603.00 | 7294.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT25 | 7655.00 | 7353.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |

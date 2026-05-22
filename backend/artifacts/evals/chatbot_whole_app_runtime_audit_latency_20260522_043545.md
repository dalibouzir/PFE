# Chatbot Whole-App Runtime Audit (Latency)

- Generated at: `2026-05-22T03:35:45.988006+00:00`
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
| LT01 | 6803.00 | 6527.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT02 | 6589.00 | 6314.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT03 | 6833.00 | 6532.00 | 0.00 | 0.00 | 1.00 | 1.00 | SLOW |
| LT04 | 6541.00 | 6250.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT05 | 6495.00 | 6199.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT06 | 6582.00 | 6297.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT07 | 7830.00 | 7541.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT08 | 7279.00 | 6986.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT09 | 7011.00 | 6711.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT10 | 6623.00 | 6336.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT11 | 6623.00 | 6321.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT12 | 6716.00 | 6425.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT13 | 6533.00 | 6240.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT14 | 2232.00 | 0.00 | 659.00 | 0.00 | 1275.00 | 1275.00 | ACCEPTABLE |
| LT15 | 3584.00 | 0.00 | 664.00 | 0.00 | 2621.00 | 2621.00 | ACCEPTABLE |
| LT16 | 366.00 | 0.00 | 0.00 | 75.00 | 0.00 | 0.00 | FAST |
| LT17 | 8927.00 | 6739.00 | 627.00 | 165.00 | 1100.00 | 1100.00 | SLOW |
| LT18 | 9211.00 | 6306.00 | 766.00 | 143.00 | 1710.00 | 1710.00 | SLOW |
| LT19 | 6625.00 | 6349.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT20 | 6503.00 | 6221.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT21 | 6579.00 | 6278.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT22 | 18343.93 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | CRITICAL |
| LT23 | 23193.94 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | CRITICAL |
| LT24 | 6606.00 | 6317.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |
| LT25 | 6815.00 | 6505.00 | 0.00 | 0.00 | 0.00 | 0.00 | SLOW |

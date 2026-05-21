# Chatbot Whole-App Runtime Audit (Manual Semantic Regression)

- Generated at: `2026-05-21T20:11:47.917248+00:00`
- Total cases: `18`
- PASS/PARTIAL/FAIL: `4/0/14`

## Score by Module

| Module | PASS | PARTIAL | FAIL |
|---|---:|---:|---:|
| collectes | 1 | 0 | 2 |
| commercial | 0 | 0 | 2 |
| invoices | 0 | 0 | 1 |
| lots | 0 | 0 | 1 |
| material_balance | 0 | 0 | 1 |
| members | 0 | 0 | 2 |
| ml | 0 | 0 | 1 |
| process_steps | 1 | 0 | 1 |
| stock_movements | 0 | 0 | 1 |
| stocks | 1 | 0 | 1 |
| treasury | 1 | 0 | 1 |

## Score by Failure Category

| Failure category | Count |
|---|---:|
| WRONG_RESPONSE_SHAPE | 11 |
| NO_FAILURE | 4 |
| INTENT_MISMATCH | 2 |
| ROUTING_ERROR | 1 |

## Top 10 P0 Failures

| QID | Module | Category | Reason | Route | Intent |
|---|---|---|---|---|---|
| MR17 | treasury | ROUTING_ERROR | expected route SQL_ONLY, got RAG_ONLY | RAG_ONLY | explanation |
| MR08 | material_balance | INTENT_MISMATCH | expected intent INPUT_OUTPUT_GAP, got LOSS_RANKING | SQL_ONLY | LOSS_RANKING |
| MR07 | lots | INTENT_MISMATCH | expected intent POSTHARVEST_AVAILABLE_LOTS, got FACTUAL_SQL | SQL_ONLY | factual_sql |

## Full Results

| QID | Module | Status | Failure | Expected route | Actual route | Expected intent | Actual intent | SQL op | Evidence rows | Confidence |
|---|---|---|---|---|---|---|---|---|---:|---:|
| MR01 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| MR02 | stock_movements | FAIL | WRONG_RESPONSE_SHAPE | SQL_ONLY | SQL_ONLY | factual_sql | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| MR03 | collectes | FAIL | WRONG_RESPONSE_SHAPE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_collecte_traceability | 1 | 0.94 |
| MR04 | collectes | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_collecte_traceability | 1 | 0.31 |
| MR05 | members | FAIL | WRONG_RESPONSE_SHAPE | SQL_ONLY | SQL_ONLY | factual_sql | PREHARVEST_STEPS | get_parcel_preharvest_status | 5 | 0.94 |
| MR06 | members | FAIL | WRONG_RESPONSE_SHAPE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_members_list | 4 | 0.94 |
| MR07 | lots | FAIL | INTENT_MISMATCH | SQL_ONLY | SQL_ONLY | POSTHARVEST_AVAILABLE_LOTS | factual_sql | get_batch_summary | 3 | 0.31 |
| MR08 | material_balance | FAIL | INTENT_MISMATCH | SQL_ONLY | SQL_ONLY | INPUT_OUTPUT_GAP | LOSS_RANKING | get_canonical_material_balance | 2 | 0.94 |
| MR09 | process_steps | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STAGE_LOSS_ANALYSIS | STAGE_LOSS_ANALYSIS | get_stage_loss_analysis | 3 | 0.94 |
| MR10 | commercial | FAIL | WRONG_RESPONSE_SHAPE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_commercial_orders_summary | 4 | 0.94 |
| MR11 | invoices | FAIL | WRONG_RESPONSE_SHAPE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_invoices_summary | 4 | 0.94 |
| MR12 | treasury | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_treasury_traceability | 10 | 0.94 |
| MR13 | stocks | FAIL | WRONG_RESPONSE_SHAPE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| MR14 | collectes | FAIL | WRONG_RESPONSE_SHAPE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_collecte_traceability | 1 | 0.94 |
| MR15 | process_steps | FAIL | WRONG_RESPONSE_SHAPE | SQL_ONLY | SQL_ONLY | STAGE_LOSS_ANALYSIS | STAGE_LOSS_ANALYSIS | get_stage_loss_analysis | 3 | 0.94 |
| MR16 | commercial | FAIL | WRONG_RESPONSE_SHAPE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_commercial_orders_summary | 4 | 0.94 |
| MR17 | treasury | FAIL | ROUTING_ERROR | SQL_ONLY | RAG_ONLY | factual_sql | explanation |  | 0 | 0.40 |
| MR18 | ml | FAIL | WRONG_RESPONSE_SHAPE | ML_ONLY | ML_ONLY | risk_ml | risk_ml |  | 1 | 0.95 |

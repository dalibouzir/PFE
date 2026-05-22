# Chatbot Whole-App Runtime Audit (Detail + Members + Memory)

- Generated at: `2026-05-22T01:05:24.428044+00:00`
- Total cases: `31`
- PASS/PARTIAL/FAIL: `22/2/7`

## Score by Module

| Module | PASS | PARTIAL | FAIL |
|---|---:|---:|---:|
| commercial | 1 | 0 | 1 |
| invoices | 1 | 0 | 1 |
| members | 8 | 1 | 1 |
| memory | 8 | 0 | 2 |
| stock_movements | 2 | 0 | 0 |
| stocks | 2 | 1 | 2 |

## Score by Failure Category

| Failure category | Count |
|---|---:|
| NO_FAILURE | 22 |
| WRONG_RESPONSE_SHAPE | 3 |
| EVIDENCE_INSUFFICIENT | 2 |
| MEMORY_CONTEXT_ERROR | 2 |
| ROUTING_ERROR | 1 |
| SQL_OPERATION_MISSING | 1 |

## Top 10 P0 Failures

| QID | Module | Category | Reason | Route | Intent |
|---|---|---|---|---|---|
| DM26 | memory | MEMORY_CONTEXT_ERROR | reset ignored: route=HYBRID_FULL intent=FOLLOW_UP | HYBRID_FULL | FOLLOW_UP |
| DM28 | memory | MEMORY_CONTEXT_ERROR | reset ignored: route=SQL_ONLY intent=FOLLOW_UP | SQL_ONLY | FOLLOW_UP |
| DM03 | stocks | ROUTING_ERROR | expected route SQL_ONLY, got HYBRID_SQL_ML | HYBRID_SQL_ML | RISK_ANALYSIS |
| DM01 | stocks | SQL_OPERATION_MISSING | low-stock intent expected get_low_stock_alerts, got get_current_stock | SQL_ONLY | factual_sql |

## Full Results

| QID | Module | Status | Failure | Expected route | Actual route | Expected intent | Actual intent | SQL op | Evidence rows | Confidence |
|---|---|---|---|---|---|---|---|---|---:|---:|
| DM01 | stocks | FAIL | SQL_OPERATION_MISSING | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_current_stock | 4 | 0.31 |
| DM02 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_low_stock_alerts | 0 | 0.78 |
| DM03 | stocks | FAIL | ROUTING_ERROR | SQL_ONLY | HYBRID_SQL_ML | factual_sql | RISK_ANALYSIS | get_canonical_material_balance | 2 | 0.55 |
| DM04 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| DM05 | stocks | PARTIAL | EVIDENCE_INSUFFICIENT | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | UNSUPPORTED_STOCKS_CAPABILITY | 0 | 0.31 |
| DM06 | stock_movements | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_stock_movements_journal | 10 | 0.96 |
| DM07 | stock_movements | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_stock_movements_journal | 4 | 0.96 |
| DM08 | commercial | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_commercial_orders_summary | 4 | 0.94 |
| DM09 | commercial | FAIL | WRONG_RESPONSE_SHAPE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_commercial_orders_summary | 4 | 0.94 |
| DM10 | invoices | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_invoices_summary | 4 | 0.94 |
| DM11 | invoices | FAIL | WRONG_RESPONSE_SHAPE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_invoices_summary | 4 | 0.94 |
| DM12 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_top_farmers | 1 | 0.96 |
| DM13 | members | FAIL | WRONG_RESPONSE_SHAPE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_farmer_advances_traceability | 5 | 0.94 |
| DM14 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_members_list | 4 | 0.94 |
| DM15 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | PREHARVEST_STEPS | get_parcel_preharvest_status | 5 | 0.94 |
| DM16 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_members_list | 4 | 0.94 |
| DM17 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_top_farmers | 1 | 0.96 |
| DM18 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_process_step_losses | 4 | 0.31 |
| DM19 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_members_list | 4 | 0.94 |
| DM20 | members | PARTIAL | EVIDENCE_INSUFFICIENT | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | producer_efficiency_unsupported | 0 | 0.35 |
| DM21 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_farmer_advances_traceability | 5 | 0.94 |
| DM22 | memory | PASS | NO_FAILURE | HYBRID_FULL | HYBRID_FULL | LOT_SPECIFIC_RECOMMENDATION | FOLLOW_UP | get_canonical_material_balance | 1 | 0.85 |
| DM23 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_members_list | 4 | 0.94 |
| DM24 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_stock_movements_journal | 3 | 0.94 |
| DM25 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | followup_postharvest_reasoning | get_process_step_losses | 6 | 0.94 |
| DM26 | memory | FAIL | MEMORY_CONTEXT_ERROR | SQL_ONLY | HYBRID_FULL | factual_sql | FOLLOW_UP | get_canonical_material_balance | 0 | 0.68 |
| DM27 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 1 | 0.94 |
| DM28 | memory | FAIL | MEMORY_CONTEXT_ERROR | SQL_ONLY | SQL_ONLY | factual_sql | FOLLOW_UP | clarification_required | 0 | 0.41 |
| DM29 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | FOLLOW_UP | clarification_required | 0 | 0.41 |
| DM30 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | FOLLOW_UP | clarification_required | 0 | 0.41 |
| DM31 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | FOLLOW_UP | clarification_required | 0 | 0.41 |

# Chatbot Whole-App Runtime Audit (Detail + Members + Memory)

- Generated at: `2026-05-22T01:41:37.292008+00:00`
- Total cases: `31`
- PASS/PARTIAL/FAIL: `31/0/0`

## Score by Module

| Module | PASS | PARTIAL | FAIL |
|---|---:|---:|---:|
| commercial | 2 | 0 | 0 |
| invoices | 2 | 0 | 0 |
| members | 10 | 0 | 0 |
| memory | 10 | 0 | 0 |
| stock_movements | 2 | 0 | 0 |
| stocks | 5 | 0 | 0 |

## Score by Failure Category

| Failure category | Count |
|---|---:|
| NO_FAILURE | 31 |

## Top 10 P0 Failures

| QID | Module | Category | Reason | Route | Intent |
|---|---|---|---|---|---|

## Full Results

| QID | Module | Status | Failure | Expected route | Actual route | Expected intent | Actual intent | SQL op | Evidence rows | Confidence |
|---|---|---|---|---|---|---|---|---|---:|---:|
| DM01 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_low_stock_alerts | 0 | 0.78 |
| DM02 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_low_stock_alerts | 0 | 0.78 |
| DM03 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_low_stock_alerts | 0 | 0.78 |
| DM04 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| DM05 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_current_stock | 0 | 0.78 |
| DM06 | stock_movements | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_stock_movements_journal | 10 | 0.96 |
| DM07 | stock_movements | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_stock_movements_journal | 4 | 0.96 |
| DM08 | commercial | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_commercial_orders_summary | 4 | 0.94 |
| DM09 | commercial | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_commercial_orders_summary | 4 | 0.94 |
| DM10 | invoices | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_invoices_summary | 4 | 0.94 |
| DM11 | invoices | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_invoices_summary | 4 | 0.94 |
| DM12 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_top_farmers | 1 | 0.96 |
| DM13 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_members_list | 0 | 0.78 |
| DM14 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_members_list | 4 | 0.94 |
| DM15 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | PREHARVEST_STEPS | get_parcel_preharvest_status | 5 | 0.94 |
| DM16 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_members_list | 4 | 0.94 |
| DM17 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_top_farmers | 1 | 0.96 |
| DM18 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_process_step_losses | 4 | 0.31 |
| DM19 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_members_list | 4 | 0.94 |
| DM20 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | producer_efficiency_unsupported | 0 | 0.35 |
| DM21 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_members_list | 0 | 0.78 |
| DM22 | memory | PASS | NO_FAILURE | HYBRID_FULL | HYBRID_FULL | LOT_SPECIFIC_RECOMMENDATION | FOLLOW_UP | get_canonical_material_balance | 1 | 0.85 |
| DM23 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_members_list | 4 | 0.94 |
| DM24 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_stock_movements_journal | 3 | 0.94 |
| DM25 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | followup_postharvest_reasoning | get_process_step_losses | 6 | 0.94 |
| DM26 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | FOLLOW_UP | clarification_required | 0 | 0.41 |
| DM27 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 1 | 0.94 |
| DM28 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | FOLLOW_UP | clarification_required | 0 | 0.41 |
| DM29 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | FOLLOW_UP | clarification_required | 0 | 0.41 |
| DM30 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | FOLLOW_UP | clarification_required | 0 | 0.41 |
| DM31 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | FOLLOW_UP | clarification_required | 0 | 0.41 |

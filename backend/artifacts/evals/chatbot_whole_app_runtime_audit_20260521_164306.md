# Chatbot Whole-App Runtime Audit

- Generated at: `2026-05-21T15:43:06.403871+00:00`
- Total cases: `60`
- PASS/PARTIAL/FAIL: `55/5/0`

## Score by Module

| Module | PASS | PARTIAL | FAIL |
|---|---:|---:|---:|
| collectes | 6 | 0 | 0 |
| commercial | 6 | 0 | 0 |
| dashboard | 6 | 0 | 0 |
| invoices | 3 | 1 | 0 |
| lots | 3 | 0 | 0 |
| material_balance | 4 | 0 | 0 |
| members | 6 | 0 | 0 |
| memory | 1 | 0 | 0 |
| ml | 0 | 2 | 0 |
| process_steps | 3 | 0 | 0 |
| rag | 3 | 0 | 0 |
| recommendations | 3 | 1 | 0 |
| stock_movements | 2 | 0 | 0 |
| stocks | 5 | 1 | 0 |
| treasury | 4 | 0 | 0 |

## Score by Failure Category

| Failure category | Count |
|---|---:|
| NO_FAILURE | 55 |
| EVIDENCE_INSUFFICIENT | 4 |
| WARNING_NOISE | 1 |

## Top 10 P0 Failures

| QID | Module | Category | Reason | Route | Intent |
|---|---|---|---|---|---|

## Full Results

| QID | Module | Status | Failure | Expected route | Actual route | Expected intent | Actual intent | SQL op | Evidence rows | Confidence |
|---|---|---|---|---|---|---|---|---|---:|---:|
| D01 | dashboard | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_cooperative_overview | 1 | 0.94 |
| D02 | dashboard | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | PREHARVEST_STEPS | get_parcel_preharvest_status | 5 | 0.94 |
| D03 | dashboard | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| D04 | dashboard | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_process_step_losses | 4 | 0.31 |
| D05 | dashboard | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | month_vs_month_charges | 1 | 0.96 |
| D06 | dashboard | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | LOSS_RANKING | LOSS_RANKING | get_canonical_material_balance | 2 | 0.94 |
| S01 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| S02 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| S03 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| S04 | stocks | PARTIAL | EVIDENCE_INSUFFICIENT | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_low_stock_alerts | 0 | 0.26 |
| S05 | stock_movements | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| S06 | stock_movements | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| S07 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | available_stock_gap | 1 | 0.96 |
| S08 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| C01 | collectes | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_collecte_traceability | 1 | 0.94 |
| C02 | collectes | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | top_collection_days | 1 | 0.96 |
| C03 | collectes | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_collections_summary | 1 | 0.94 |
| C04 | collectes | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_collecte_traceability | 1 | 0.31 |
| C05 | collectes | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_collecte_traceability | 1 | 0.31 |
| C06 | collectes | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_uploaded_files_evidence | 9 | 0.94 |
| M01 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_members_list | 4 | 0.94 |
| M02 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_process_step_losses | 4 | 0.31 |
| M03 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | lowest_nonzero_member_contributor | 1 | 0.96 |
| M04 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_members_list | 4 | 0.42 |
| M05 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | PREHARVEST_STEPS | get_parcel_preharvest_status | 4 | 0.94 |
| M06 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | PREHARVEST_STEPS | get_parcel_preharvest_status | 5 | 0.94 |
| L01 | lots | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | POSTHARVEST_AVAILABLE_LOTS | POSTHARVEST_AVAILABLE_LOTS | get_available_postharvest_lots | 2 | 0.94 |
| L02 | lots | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_batch_summary | 1 | 0.31 |
| L03 | lots | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_batch_summary | 3 | 0.31 |
| L04 | material_balance | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | LOSS_RANKING | LOSS_RANKING | get_canonical_material_balance | 2 | 0.94 |
| L05 | material_balance | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | INPUT_OUTPUT_GAP | INPUT_OUTPUT_GAP | get_canonical_material_balance | 2 | 0.94 |
| L06 | material_balance | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | LOT_COMPARISON | LOT_COMPARISON | get_canonical_material_balance_for_lots | 2 | 0.94 |
| L07 | process_steps | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STAGE_LOSS_ANALYSIS | STAGE_LOSS_ANALYSIS | get_stage_loss_analysis | 3 | 0.94 |
| L08 | process_steps | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STAGE_LOSS_ANALYSIS | STAGE_LOSS_ANALYSIS | get_stage_loss_analysis | 3 | 0.94 |
| L09 | process_steps | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_stage_efficiency_summary | 3 | 0.19 |
| L10 | material_balance | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_collecte_traceability | 1 | 0.31 |
| R01 | recommendations | PARTIAL | WARNING_NOISE | HYBRID_FULL | HYBRID_FULL | LOT_SPECIFIC_RECOMMENDATION | LOT_SPECIFIC_RECOMMENDATION | get_canonical_material_balance | 1 | 0.21 |
| R02 | recommendations | PASS | NO_FAILURE | HYBRID_FULL | HYBRID_FULL | RECOMMENDATION | RECOMMENDATION | get_canonical_material_balance | 2 | 0.43 |
| R03 | recommendations | PASS | NO_FAILURE | HYBRID_FULL | HYBRID_FULL | action_recommendation | action_recommendation | get_process_step_losses | 6 | 0.42 |
| R04 | recommendations | PASS | NO_FAILURE | HYBRID_FULL | HYBRID_FULL | RECOMMENDATION | RECOMMENDATION | get_canonical_material_balance | 2 | 0.43 |
| G01 | rag | PASS | NO_FAILURE | RAG_ONLY | RAG_ONLY | BEST_PRACTICES | BEST_PRACTICES |  | 0 | 0.61 |
| G02 | rag | PASS | NO_FAILURE | RAG_ONLY | RAG_ONLY | BEST_PRACTICES | BEST_PRACTICES |  | 0 | 0.61 |
| G03 | rag | PASS | NO_FAILURE | RAG_ONLY | RAG_ONLY | BEST_PRACTICES | BEST_PRACTICES |  | 0 | 0.12 |
| O01 | commercial | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | top_customer_by_orders | 1 | 0.96 |
| O02 | commercial | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_commercial_orders_summary | 4 | 0.94 |
| O03 | commercial | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_commercial_orders_summary | 4 | 0.94 |
| O04 | commercial | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_commercial_invoice_linkage | 4 | 0.94 |
| O05 | commercial | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_commercial_invoice_linkage | 4 | 0.94 |
| O06 | commercial | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_treasury_traceability | 10 | 0.94 |
| F01 | invoices | PARTIAL | EVIDENCE_INSUFFICIENT | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | avg_paid_invoices_current_quarter | 0 | 0.24 |
| F02 | invoices | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_invoices_summary | 4 | 0.94 |
| F03 | invoices | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_invoices_summary | 4 | 0.94 |
| F04 | invoices | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_invoices_summary | 4 | 0.94 |
| T01 | treasury | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_treasury_traceability | 10 | 0.94 |
| T02 | treasury | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_treasury_traceability | 10 | 0.94 |
| T03 | treasury | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_treasury_traceability | 10 | 0.94 |
| T04 | treasury | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_treasury_traceability | 10 | 0.94 |
| ML1 | ml | PARTIAL | EVIDENCE_INSUFFICIENT | ML_ONLY | ML_ONLY | risk_ml | risk_ml |  | 0 | 0.40 |
| ML2 | ml | PARTIAL | EVIDENCE_INSUFFICIENT | ML_ONLY | ML_ONLY | risk_ml | risk_ml |  | 0 | 0.32 |
| MEM1 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 1 | 0.94 |

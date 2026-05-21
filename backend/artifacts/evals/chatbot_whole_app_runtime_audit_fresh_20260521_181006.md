# Chatbot Whole-App Runtime Audit (Fresh Anti-Overfit)

- Generated at: `2026-05-21T17:10:06.655304+00:00`
- Total cases: `57`
- PASS/PARTIAL/FAIL: `54/0/3`

## Score by Module

| Module | PASS | PARTIAL | FAIL |
|---|---:|---:|---:|
| collectes | 4 | 0 | 0 |
| commercial | 4 | 0 | 0 |
| dashboard | 5 | 0 | 0 |
| invoices | 6 | 0 | 0 |
| lots | 3 | 0 | 0 |
| material_balance | 3 | 0 | 0 |
| members | 4 | 0 | 0 |
| memory | 1 | 0 | 0 |
| ml | 3 | 0 | 1 |
| process_steps | 2 | 0 | 0 |
| rag | 5 | 0 | 0 |
| recommendations | 4 | 0 | 2 |
| stock_movements | 2 | 0 | 0 |
| stocks | 5 | 0 | 0 |
| treasury | 3 | 0 | 0 |

## Score by Failure Category

| Failure category | Count |
|---|---:|
| NO_FAILURE | 54 |
| ROUTING_ERROR | 2 |
| INTENT_MISMATCH | 1 |

## Top 10 P0 Failures

| QID | Module | Category | Reason | Route | Intent |
|---|---|---|---|---|---|
| FN04 | ml | ROUTING_ERROR | expected route ML_ONLY, got HYBRID_SQL_ML | HYBRID_SQL_ML | RISK_ANALYSIS |
| FN06 | recommendations | INTENT_MISMATCH | expected intent LOT_SPECIFIC_RECOMMENDATION, got ACTION_RECOMMENDATION | HYBRID_FULL | action_recommendation |
| FN07 | recommendations | ROUTING_ERROR | expected route HYBRID_FULL, got OUT_OF_SCOPE | OUT_OF_SCOPE | unsupported |

## Full Results

| QID | Module | Status | Failure | Expected route | Actual route | Expected intent | Actual intent | SQL op | Evidence rows | Confidence |
|---|---|---|---|---|---|---|---|---|---:|---:|
| FD01 | dashboard | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_cooperative_overview | 1 | 0.94 |
| FD02 | dashboard | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | PREHARVEST_STEPS | get_parcel_preharvest_status | 5 | 0.94 |
| FD03 | dashboard | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| FD04 | dashboard | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | LOSS_RANKING | get_canonical_material_balance | 2 | 0.94 |
| FD05 | dashboard | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | LOSS_RANKING | LOSS_RANKING | get_canonical_material_balance | 2 | 0.94 |
| FS01 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| FS02 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| FS03 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| FS04 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| FS05 | stock_movements | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| FS06 | stock_movements | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_stock_movements_journal | 3 | 0.31 |
| FC01 | collectes | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_collecte_traceability | 1 | 0.31 |
| FC02 | collectes | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_collections_summary | 1 | 0.94 |
| FC03 | collectes | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_collections_summary | 1 | 0.94 |
| FC04 | collectes | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_collecte_traceability | 1 | 0.31 |
| FM01 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_members_list | 4 | 0.94 |
| FM02 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_process_step_losses | 4 | 0.31 |
| FM03 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_process_step_losses | 4 | 0.31 |
| FM04 | members | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | PREHARVEST_STEPS | get_parcel_preharvest_status | 5 | 0.94 |
| FL01 | lots | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | POSTHARVEST_AVAILABLE_LOTS | POSTHARVEST_AVAILABLE_LOTS | get_available_postharvest_lots | 2 | 0.94 |
| FL02 | lots | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_batch_summary | 1 | 0.31 |
| FL03 | lots | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_batch_summary | 3 | 0.31 |
| FL04 | material_balance | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | LOSS_RANKING | LOSS_RANKING | get_canonical_material_balance | 2 | 0.94 |
| FL05 | material_balance | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | INPUT_OUTPUT_GAP | INPUT_OUTPUT_GAP | get_canonical_material_balance | 2 | 0.94 |
| FL06 | material_balance | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | LOT_COMPARISON | LOT_COMPARISON | get_canonical_material_balance_for_lots | 2 | 0.94 |
| FL07 | process_steps | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STAGE_LOSS_ANALYSIS | STAGE_LOSS_ANALYSIS | get_stage_loss_analysis | 3 | 0.94 |
| FL08 | process_steps | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STAGE_LOSS_ANALYSIS | STAGE_LOSS_ANALYSIS | get_stage_loss_analysis | 3 | 0.94 |
| FR01 | recommendations | PASS | NO_FAILURE | HYBRID_FULL | HYBRID_FULL | LOT_SPECIFIC_RECOMMENDATION | LOT_SPECIFIC_RECOMMENDATION | get_canonical_material_balance | 1 | 0.85 |
| FR02 | recommendations | PASS | NO_FAILURE | HYBRID_FULL | HYBRID_FULL | RECOMMENDATION | RECOMMENDATION | get_canonical_material_balance | 2 | 0.55 |
| FR03 | recommendations | PASS | NO_FAILURE | HYBRID_FULL | HYBRID_FULL | action_recommendation | action_recommendation | get_process_step_losses | 6 | 0.55 |
| FR04 | recommendations | PASS | NO_FAILURE | HYBRID_FULL | HYBRID_FULL | RECOMMENDATION | RECOMMENDATION | get_canonical_material_balance | 2 | 0.55 |
| FG01 | rag | PASS | NO_FAILURE | RAG_ONLY | RAG_ONLY | BEST_PRACTICES | BEST_PRACTICES |  | 0 | 0.40 |
| FG02 | rag | PASS | NO_FAILURE | RAG_ONLY | RAG_ONLY | BEST_PRACTICES | BEST_PRACTICES |  | 0 | 0.61 |
| FG03 | rag | PASS | NO_FAILURE | RAG_ONLY | RAG_ONLY | BEST_PRACTICES | BEST_PRACTICES |  | 0 | 0.40 |
| FO01 | commercial | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | top_customer_by_orders | 1 | 0.96 |
| FO02 | commercial | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_commercial_orders_summary | 4 | 0.31 |
| FO03 | commercial | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_commercial_orders_summary | 4 | 0.94 |
| FO04 | commercial | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_commercial_invoice_linkage | 4 | 0.94 |
| FF01 | invoices | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | avg_paid_invoices_current_quarter | 0 | 0.78 |
| FF02 | invoices | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_invoices_summary | 4 | 0.94 |
| FF03 | invoices | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_invoices_summary | 4 | 0.94 |
| FT01 | treasury | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_treasury_traceability | 10 | 0.31 |
| FT02 | treasury | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_treasury_traceability | 10 | 0.94 |
| FT03 | treasury | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_treasury_traceability | 10 | 0.94 |
| FML1 | ml | PASS | NO_FAILURE | ML_ONLY | ML_ONLY | risk_ml | risk_ml |  | 1 | 0.95 |
| FML2 | ml | PASS | NO_FAILURE | ML_ONLY | ML_ONLY | risk_ml | risk_ml |  | 0 | 0.77 |
| FN01 | invoices | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_invoices_summary | 4 | 0.31 |
| FN02 | invoices | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | avg_paid_invoices_current_quarter | 0 | 0.78 |
| FN03 | ml | PASS | NO_FAILURE | ML_ONLY | ML_ONLY | risk_ml | risk_ml |  | 1 | 0.77 |
| FN04 | ml | FAIL | ROUTING_ERROR | ML_ONLY | HYBRID_SQL_ML | risk_ml | RISK_ANALYSIS | get_canonical_material_balance | 2 | 0.55 |
| FN05 | stocks | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | STOCK_CURRENT | get_current_stock | 4 | 0.94 |
| FN06 | recommendations | FAIL | INTENT_MISMATCH | HYBRID_FULL | HYBRID_FULL | LOT_SPECIFIC_RECOMMENDATION | action_recommendation | get_batch_summary | 1 | 0.85 |
| FN07 | recommendations | FAIL | ROUTING_ERROR | HYBRID_FULL | OUT_OF_SCOPE | RECOMMENDATION | unsupported |  | 0 | 0.40 |
| FN08 | rag | PASS | NO_FAILURE | RAG_ONLY | RAG_ONLY | BEST_PRACTICES | BEST_PRACTICES |  | 0 | 0.40 |
| FN09 | rag | PASS | NO_FAILURE | RAG_ONLY | RAG_ONLY | BEST_PRACTICES | BEST_PRACTICES |  | 0 | 0.40 |
| FN10 | invoices | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | factual_sql | factual_sql | get_invoices_summary | 4 | 0.31 |
| FMEM1 | memory | PASS | NO_FAILURE | SQL_ONLY | SQL_ONLY | STOCK_CURRENT | STOCK_CURRENT | get_current_stock | 1 | 0.94 |

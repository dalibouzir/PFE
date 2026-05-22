# Final Chatbot Parity Validation

- Generated at: `2026-05-22T11:17:55.452975+00:00`
- Deployed backend: `https://weefarm-backend-app.prouddune-c85ebf6e.germanywestcentral.azurecontainerapps.io`
- Cases: `20`
- Same: `18` | Diff: `2`

| Case | Same | Diagnosis | Local route | Deployed route | Local sql_op | Deployed sql_op | Local latency ms | Deployed latency ms |
|---|---|---|---|---|---|---|---:|---:|
| P01 | no | mismatch_intent_family | SQL_ONLY | SQL_ONLY | get_low_stock_alerts | get_current_stock | 7652 | 2734 |
| P02 | yes | match | SQL_ONLY | SQL_ONLY | get_stock_movements_journal | get_stock_movements_journal | 7568 | 2734 |
| P03 | yes | match | SQL_ONLY | SQL_ONLY | get_current_stock | get_current_stock | 7174 | 2511 |
| P04 | yes | match | SQL_ONLY | SQL_ONLY | get_members_list | get_members_list | 7164 | 2646 |
| P05 | yes | match | SQL_ONLY | SQL_ONLY | get_top_farmers | get_top_farmers | 7187 | 2402 |
| P06 | yes | match | SQL_ONLY | SQL_ONLY | get_available_postharvest_lots | get_available_postharvest_lots | 7200 | 2522 |
| P07 | yes | match | SQL_ONLY | SQL_ONLY | get_canonical_material_balance | get_canonical_material_balance | 7280 | 2762 |
| P08 | yes | match | SQL_ONLY | SQL_ONLY | get_stage_loss_analysis | get_stage_loss_analysis | 7235 | 2427 |
| P09 | yes | match | SQL_ONLY | SQL_ONLY | get_commercial_orders_summary | get_commercial_orders_summary | 8841 | 2923 |
| P10 | yes | match | SQL_ONLY | SQL_ONLY | get_invoices_summary | get_invoices_summary | 8058 | 2700 |
| P11 | yes | match | SQL_ONLY | SQL_ONLY | get_commercial_invoice_linkage | get_commercial_invoice_linkage | 8221 | 2863 |
| P12 | yes | match | SQL_ONLY | SQL_ONLY | get_treasury_traceability | get_treasury_traceability | 7517 | 2755 |
| P13 | yes | match | OUT_OF_SCOPE | OUT_OF_SCOPE |  |  | 328 | 97 |
| P14 | yes | match | HYBRID_FULL | HYBRID_FULL | get_canonical_material_balance | get_canonical_material_balance | 10789 | 16791 |
| P15 | yes | match | SQL_ONLY | SQL_ONLY | avg_paid_invoices_current_quarter | avg_paid_invoices_current_quarter | 7135 | 2402 |
| P16 | yes | match | ML_ONLY | ML_ONLY |  |  | 381 | 373 |
| P17 | yes | match | RAG_ONLY | RAG_ONLY |  |  | 2434 | 2334 |
| P18 | yes | match | SQL_ONLY | SQL_ONLY | get_current_stock | get_current_stock | 7088 | 2689 |
| P19 | yes | match | HYBRID_FULL | HYBRID_FULL | get_canonical_material_balance | get_canonical_material_balance | 10338 | 3017 |
| P20 | no | mismatch_sql_operation | SQL_ONLY | SQL_ONLY | clarification_required | get_canonical_material_balance | 6935 | 2448 |

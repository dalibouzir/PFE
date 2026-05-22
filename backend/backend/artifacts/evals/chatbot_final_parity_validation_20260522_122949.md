# Final Chatbot Parity Validation

- Generated at: `2026-05-22T11:29:49.520909+00:00`
- Deployed backend: `https://weefarm-backend-app.prouddune-c85ebf6e.germanywestcentral.azurecontainerapps.io`
- Cases: `20`
- Same: `18` | Diff: `2`

| Case | Same | Diagnosis | Local route | Deployed route | Local sql_op | Deployed sql_op | Local latency ms | Deployed latency ms |
|---|---|---|---|---|---|---|---:|---:|
| P01 | no | mismatch_intent_family | SQL_ONLY | SQL_ONLY | get_low_stock_alerts | get_current_stock | 7704 | 2541 |
| P02 | yes | match | SQL_ONLY | SQL_ONLY | get_stock_movements_journal | get_stock_movements_journal | 7968 | 2681 |
| P03 | yes | match | SQL_ONLY | SQL_ONLY | get_current_stock | get_current_stock | 7197 | 2407 |
| P04 | yes | match | SQL_ONLY | SQL_ONLY | get_members_list | get_members_list | 7323 | 2638 |
| P05 | yes | match | SQL_ONLY | SQL_ONLY | get_top_farmers | get_top_farmers | 7234 | 2386 |
| P06 | yes | match | SQL_ONLY | SQL_ONLY | get_available_postharvest_lots | get_available_postharvest_lots | 7314 | 2469 |
| P07 | yes | match | SQL_ONLY | SQL_ONLY | get_canonical_material_balance | get_canonical_material_balance | 7321 | 2663 |
| P08 | yes | match | SQL_ONLY | SQL_ONLY | get_stage_loss_analysis | get_stage_loss_analysis | 7374 | 2674 |
| P09 | yes | match | SQL_ONLY | SQL_ONLY | get_commercial_orders_summary | get_commercial_orders_summary | 9293 | 2950 |
| P10 | yes | match | SQL_ONLY | SQL_ONLY | get_invoices_summary | get_invoices_summary | 8158 | 2678 |
| P11 | yes | match | SQL_ONLY | SQL_ONLY | get_commercial_invoice_linkage | get_commercial_invoice_linkage | 7999 | 2651 |
| P12 | yes | match | SQL_ONLY | SQL_ONLY | get_treasury_traceability | get_treasury_traceability | 7790 | 2578 |
| P13 | yes | match | OUT_OF_SCOPE | OUT_OF_SCOPE |  |  | 310 | 98 |
| P14 | yes | match | HYBRID_FULL | HYBRID_FULL | get_canonical_material_balance | get_canonical_material_balance | 10343 | 4077 |
| P15 | yes | match | SQL_ONLY | SQL_ONLY | avg_paid_invoices_current_quarter | avg_paid_invoices_current_quarter | 7443 | 2394 |
| P16 | yes | match | ML_ONLY | ML_ONLY |  |  | 410 | 355 |
| P17 | yes | match | RAG_ONLY | RAG_ONLY |  |  | 3194 | 620 |
| P18 | yes | match | SQL_ONLY | SQL_ONLY | get_current_stock | get_current_stock | 7283 | 2456 |
| P19 | yes | match | HYBRID_FULL | HYBRID_FULL | get_canonical_material_balance | get_canonical_material_balance | 10754 | 3418 |
| P20 | no | mismatch_sql_operation | SQL_ONLY | SQL_ONLY | clarification_required | get_canonical_material_balance | 7248 | 2530 |

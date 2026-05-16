# Chat SQL/RAG Eval Harness (2026-05-13)

- Manager: `manager@test.local`
- Score: **100.0%** (5/5 cases passed)

## Ground Truth
- Members (max 25): **17**
- Active lots: **0**
- Latest lots used for 10-row check: **10**

## Case Results
- `sql_active_lots_exact` intent=`SQL_ONLY` mode=`sql_only` pass=`True`
  - status_code_200: PASS
  - intent_sql_only: PASS
  - active_lot_count_matches_db: PASS
- `sql_members_table` intent=`SQL_ONLY` mode=`sql_only` pass=`True`
  - status_code_200: PASS
  - intent_sql_only: PASS
  - table_present: PASS
  - member_columns_match_contract: PASS
  - member_row_count_matches_db: PASS
  - member_first_row_matches_db: PASS
  - no_lot_loss_contamination: PASS
- `sql_lots_table_latest` intent=`SQL_ONLY` mode=`sql_only` pass=`True`
  - status_code_200: PASS
  - intent_sql_only: PASS
  - table_present: PASS
  - lot_columns_match_contract: PASS
  - row_count_matches_requested_limit: PASS
- `hybrid_operational_analysis` intent=`HYBRID` mode=`fallback_rag` pass=`True`
  - status_code_200: PASS
  - intent_hybrid: PASS
  - hybrid_has_nonempty_message: PASS
- `rag_only_reference` intent=`RAG_ONLY` mode=`fallback_rag` pass=`True`
  - status_code_200: PASS
  - intent_rag_only: PASS
  - citations_present: PASS
  - message_source_grounded: PASS

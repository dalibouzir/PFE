# Demo Data Integrity Report

Generated: 2026-05-13T10:43:58.824417+00:00

## Checked Tables
- batches: 19 records checked
- commercial_invoice_lines: 14 records checked
- commercial_invoices: 7 records checked
- commercial_order_lines: 20 records checked
- commercial_orders: 10 records checked
- farmer_advances: 15 records checked
- global_charges: 24 records checked
- process_steps: 52 records checked
- stocks: 6 records checked
- treasury_transactions: 6 records checked

## Inconsistency Summary
- Total inconsistencies: 0
- Critical: 0
- High: 0
- Medium: 0
- Low: 0
- Data integrity score: 100.00/100

## Findings

## Applied Reconciliation Fixes
- batch_current_qty_synced: 2
- stock_reserved_synced: 0
- stock_available_synced: 0
- stock_total_raised_to_reserved: 0
- No inconsistencies found.
## Final Assessment
- Final grade: PASS
- Acceptance criterion: no critical data inconsistency.

## Rerun
```bash
./.venv/bin/python backend/scripts/validate_demo_data_integrity.py
./.venv/bin/python backend/scripts/validate_demo_data_integrity.py --fix
```
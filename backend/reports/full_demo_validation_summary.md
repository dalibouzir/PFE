# Full Demo Validation Summary

Generated: 2026-05-08 (Africa/Tunis)

## 1) Seeded Data Summary (DEMOFP)
Seed script: `backend/scripts/seed_full_demo_dataset.py`

Latest rerun summary:
- batches: updated=14
- commercial_catalog_products: updated=4
- commercial_orders: updated=10
- commercial_order_lines: created=20, deleted=20
- commercial_invoices: updated=7
- commercial_invoice_lines: created=14, deleted=14
- members: updated=14
- fields: updated=17
- parcels: updated=17
- pre_harvest_steps: updated=68
- inputs: updated=72
- stocks: updated=4
- process_steps: created=32, deleted=32
- recommendations: updated=12
- recommendation_feedback_logs: updated=12
- ml_prediction_logs: updated=12
- ml_recommendation_logs: updated=12
- global_charges: updated=24
- farmer_advances: updated=15
- treasury_transactions: updated=6
- knowledge_chunks: updated=8
- reference_metrics: updated=5

## 2) Data Integrity
Validation script: `backend/scripts/validate_demo_data_integrity.py`

Latest result (`--fix` run):
- inconsistencies: 0
- critical: 0
- high: 0
- score: 100/100

## 3) Modules Covered by Chatbot
Modules covered and tested:
- members/farmers
- parcels/cultures
- collections/inputs
- stocks
- lots/batches
- process steps/losses
- recommendations/feedback
- commercial orders
- invoices
- finance (charges/advances/treasury)
- ML prediction logs
- RAG/reference knowledge

Coverage from full-platform audit:
- seeded major modules: 12/12
- tested major modules: 12/12
- module coverage rate: 100%

## 4) RAG / Index Coverage
Report: `backend/reports/full_rag_index_coverage_report.md`

Current totals:
- total documents: 577
- total chunks: 577

## 5) Chatbot Audit Results
Baseline audit:
- 50/50 (100%)

Unseen robustness audit:
- 60/60 (100%)

Full-platform coverage audit:
- total: 112
- overall: 112/112 (100%)
- SQL_ONLY: 64/64 (100%)
- RAG_ONLY: 9/9 (100%)
- HYBRID: 31/31 (100%)
- SMALL_TALK: 4/4 (100%)
- UNSUPPORTED: 4/4 (100%)
- fake-entity high-risk hallucination: 0
- stale response issues: 0
- UI/debug leakage: 0

## 6) ML Validation Results
Script: `backend/scripts/ml_full_demo_validation.py`

Computed metrics:
- dataset rows: 1517
- classification accuracy: 0.8295
- classification macro-F1: 0.4435
- regression MAE: 4.0150
- regression RMSE: 7.2806
- regression R²: 0.0651

Anomaly limitation:
- TP/FP/FN unavailable due missing labeled anomaly ground truth.

## 7) Remaining Limitations
- validation is on synthetic demo data; external validity is limited.
- ML quality is moderate; macro-F1 and R² indicate room for improvement.
- anomaly detection remains unsupervised.
- some RAG metadata fields remain sparse (`source_id`, `severity`, product/member tagging gaps on certain chunk types).

## 8) Exact Commands to Rerun Everything
```bash
./.venv/bin/python backend/scripts/seed_full_demo_dataset.py
./.venv/bin/python backend/scripts/validate_demo_data_integrity.py --fix
./.venv/bin/python backend/scripts/full_rag_index_coverage_report.py --skip-reindex
./.venv/bin/python backend/scripts/chatbot_quality_audit.py
./.venv/bin/python backend/scripts/chatbot_unseen_robustness_audit.py
./.venv/bin/python backend/scripts/chatbot_full_platform_coverage_audit.py
./.venv/bin/python backend/scripts/ml_full_demo_validation.py
```

# PFE Final Validation Summary

Generated: 2026-05-08 (Africa/Tunis)

## 1) Project Scope
AI-first decision-support prototype for agricultural cooperative management.

In-scope:
- operational monitoring (stocks, lots, losses, process)
- cross-module managerial support (members, parcels, collections, recommendations, orders, invoices, finance)
- evidence-aware assistant routing (SQL_ONLY / RAG_ONLY / HYBRID / SMALL_TALK / UNSUPPORTED)

Out-of-scope:
- full ERP replacement
- production-grade real-world ML guarantees

## 2) Modules Covered
Covered in seeded data and audited chatbot scope:
- members/farmers
- parcels/cultures
- collections/inputs
- stocks
- lots/batches
- process steps/losses/material balance
- recommendations/feedback
- commercial orders
- invoices/factures
- finance (charges/advances/treasury)
- ML logs/predictions
- reference/RAG knowledge

Coverage result:
- seeded modules: 12/12
- tested modules: 12/12
- coverage rate: 100%

## 3) Data Integrity and Reproducibility
Data integrity script:
- `backend/scripts/validate_demo_data_integrity.py`
- report: `backend/reports/demo_data_integrity_report.md`

Latest integrity result:
- critical inconsistencies: 0
- high inconsistencies: 0
- score: 100/100
- safe reconciliation mode available: `--fix`

## 4) RAG Index Summary
Report:
- `backend/reports/full_rag_index_coverage_report.md`

Current totals:
- documents: 577
- chunks: 577

Cross-module indexing is active (members, parcels, collections, stocks, lots, process, recommendations, commercial, invoices, finance, ML, references).

## 5) Chatbot Validation Metrics
Baseline audit:
- `backend/scripts/chatbot_quality_audit.py`
- result: 50/50 (100%)

Unseen robustness audit:
- `backend/scripts/chatbot_unseen_robustness_audit.py`
- result: 60/60 (100%)

Full-platform coverage audit:
- `backend/scripts/chatbot_full_platform_coverage_audit.py`
- result: 112/112 (100%)
- SQL_ONLY: 64/64
- RAG_ONLY: 9/9
- HYBRID: 31/31
- SMALL_TALK: 4/4
- UNSUPPORTED: 4/4
- high-risk hallucination: 0
- stale response issues: 0
- UI/debug leakage: 0

## 6) ML Validation (Computed, Not Claimed Beyond Scope)
Validation script:
- `backend/scripts/ml_full_demo_validation.py`

Reports:
- `backend/reports/ml_model_validation_report.md`
- `backend/reports/ml_model_validation_report.json`

Latest computed metrics:
- dataset rows: 1517
- classification accuracy: 0.8295
- classification macro-F1: 0.4435
- regression MAE: 4.0150
- regression RMSE: 7.2806
- regression R²: 0.0651

Anomaly limitation:
- no labeled anomaly ground truth in schema, so TP/FP/FN are unavailable.
- only exploratory anomaly diagnostics are reported.

## 7) Key Limitations (Explicit)
- synthetic demo dataset: useful for controlled validation, not equivalent to field deployment.
- limited real-world external validation.
- ML class imbalance and weak regression fit (low R²) limit predictive confidence.
- anomaly evaluation lacks supervised labels.
- RAG quality depends on metadata quality and reference corpus quality.
- LLM-provider availability can impact HYBRID/RAG narrative generation.

## 8) Reproducibility Commands
From repository root:

```bash
# 1) Seed/update full synthetic demo data
./.venv/bin/python backend/scripts/seed_full_demo_dataset.py

# 2) Validate data integrity (read-only)
./.venv/bin/python backend/scripts/validate_demo_data_integrity.py

# 3) Optional safe reconciliation + integrity check
./.venv/bin/python backend/scripts/validate_demo_data_integrity.py --fix

# 4) RAG coverage report (fast snapshot mode)
./.venv/bin/python backend/scripts/full_rag_index_coverage_report.py --skip-reindex

# 5) Baseline chatbot audit
./.venv/bin/python backend/scripts/chatbot_quality_audit.py

# 6) Unseen robustness chatbot audit
./.venv/bin/python backend/scripts/chatbot_unseen_robustness_audit.py

# 7) Full-platform chatbot audit
./.venv/bin/python backend/scripts/chatbot_full_platform_coverage_audit.py

# 8) ML validation report
./.venv/bin/python backend/scripts/ml_full_demo_validation.py
```

## 9) Positioning Statement
An AI-first decision-support prototype validated on a synthetic full-platform demo dataset.

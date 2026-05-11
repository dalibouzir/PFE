# PFE Metrics Table

Generated: 2026-05-08 (Africa/Tunis)

| Metric | Value | Source |
|---|---:|---|
| Chatbot baseline pass rate | 50/50 (100.00%) | `backend/artifacts/chatbot_quality_audit.json` |
| Chatbot unseen pass rate | 60/60 (100.00%) | `backend/reports/chatbot_unseen_robustness_audit.json` |
| Chatbot full-platform pass rate | 112/112 (100.00%) | `backend/reports/chatbot_full_platform_coverage_audit.json` |
| Module coverage rate | 12/12 (100.00%) | `backend/reports/chatbot_full_platform_coverage_audit.json` |
| RAG documents count | 577 | `backend/reports/full_rag_index_coverage_report.md` |
| RAG chunks count | 577 | `backend/reports/full_rag_index_coverage_report.md` |
| High-risk hallucination count | 0 | `backend/reports/chatbot_full_platform_coverage_audit.json` |
| Stale response issue count | 0 | `backend/reports/chatbot_full_platform_coverage_audit.json` |
| UI/debug leakage count | 0 | `backend/reports/chatbot_full_platform_coverage_audit.json` |
| ML classification accuracy | 0.8295 | `backend/reports/ml_model_validation_report.json` |
| ML classification macro-F1 | 0.4435 | `backend/reports/ml_model_validation_report.json` |
| ML regression MAE | 4.0150 | `backend/reports/ml_model_validation_report.json` |
| ML regression RMSE | 7.2806 | `backend/reports/ml_model_validation_report.json` |
| ML regression R² | 0.0651 | `backend/reports/ml_model_validation_report.json` |
| Anomaly validation limitation | No labeled anomaly TP/FP/FN available | `backend/reports/ml_model_validation_report.json` |

## Notes
- Metrics are computed from scripts and generated artifacts; no manual/fake values are injected.
- ML results are valid for the synthetic demo dataset and must not be over-generalized.

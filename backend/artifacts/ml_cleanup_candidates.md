# ML Cleanup Candidates

## Policy Used
- Keep anything required for active ML serving, reproducibility, diagnostics, evaluation, governance, and PFE reporting.
- Delete only clearly disposable cache/temp files.
- Archive historical reports that are superseded by final reports.
- Leave uncertain files for manual review.

## Candidates

| Path | Classification | Reason |
|---|---|---|
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/.pytest_cache/` | delete | Pytest cache only; safe to regenerate |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/.pytest_cache/` | delete | Pytest cache only; safe to regenerate |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/**/__pycache__/` | delete | Python bytecode cache only; safe to regenerate |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_diagnostics_phase2.json` | archive | Superseded by final diagnostics |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_diagnostics_phase4.json` | archive | Superseded by final diagnostics |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_diagnostics_phase5.json` | archive | Kept as phase trace; final file now authoritative |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_diagnostics_after_clean_retrain.json` | archive | Intermediate run artifact |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_diagnostics_after_retrain.json` | archive | Intermediate run artifact |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_diagnostics_seeded.json` | archive | Intermediate run artifact |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_diagnostics.json` | archive | Generic historical snapshot |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_evaluation_phase4.json` | archive | Superseded by final evaluation |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_evaluation_phase4.md` | archive | Superseded by final evaluation |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_evaluation_phase5.json` | archive | Superseded by final evaluation |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_evaluation_phase5.md` | archive | Superseded by final evaluation |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_evaluation_report.json` | archive | Older generic report name |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_evaluation_report.md` | archive | Older generic report name |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/model_registry.json` | keep | Required for governance/activation history |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/active_model.json` | keep | Required active model pointer |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/versions/` | keep | Versioned artifact backups |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/feature_metadata.json` | keep | Required current bundle metadata |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/loss_regressor.joblib` | keep | Required current bundle model |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/risk_classifier.joblib` | keep | Required current bundle model (experimental/eval) |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/anomaly_detector.joblib` | keep | Required current bundle model |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_diagnostics_final.json` | keep | Required final diagnostics |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_evaluation_final.json` | keep | Required final evaluation |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_evaluation_final.md` | keep | Required final evaluation narrative |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_before_after_report.json` | keep | Required final before/after report |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_before_after_report.md` | keep | Required final before/after report |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/ml_cleanup_candidates.md` | keep | Required final cleanup audit |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/.vscode/` | review manually | Editor-local config; not ML runtime-critical |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/tsconfig.tsbuildinfo` | review manually | Frontend build artifact, outside ML scope |
| `/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/docs/Script for rapport pfe.md` | review manually | Could be PFE documentation source |

## Cleanup Execution Decision
- Execute now: only `delete` class entries.
- Do not delete `archive` or `review manually` entries in this pass.


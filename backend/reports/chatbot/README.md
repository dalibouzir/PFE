# Chatbot Reports Organization

## Final evidence (PFE-ready)
Folder: `backend/reports/chatbot/final_metrics/`

This folder contains the latest, presentation-ready chatbot evidence:
- latest Supabase real-app audits
- latest conversation flow audit
- latest unseen robustness audit
- full platform coverage audit snapshot
- final AI validation summary
- final chatbot curl/real response evidence

## Archived historical audits
Folder: `backend/reports/chatbot/archived_audits/`

This folder keeps historical and superseded chatbot audits, generated snapshots, and run logs.
These are retained for traceability but are not considered active regression outputs.

Subfolders:
- `legacy_tests/`: previous audit-style pytest files archived as text snapshots.
- `legacy_generated_reports/`: historical generated reports from `backend/app/ai/reports/`.
- `legacy_run_logs/`: historical execution logs.

## Active chatbot regression tests
Active tests remain in `backend/tests/` (pytest discovery path) and include:
- `test_phase1_chatbot_behavior.py`
- `test_chat_orchestrator.py`
- `test_chat_retrieval_router.py`
- `test_chat_retrieval_integration.py`
- `test_coop_agent_*.py`
- `test_rag_*.py`

Archived legacy audit tests are outside `backend/tests/` and will not be auto-discovered by pytest.

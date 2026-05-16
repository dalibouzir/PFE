# WeeFarm PFE — Evidence-Based Project Overview

Date: 2026-05-13
Scope inspected: repository code, tests, scripts, reports, configs (no feature invention).

## Executive Overview

| Claim | Status | Evidence |
|---|---|---|
| WeeFarm is implemented as an AI-assisted cooperative operations platform (not only a UI mock). | confirmed by code | `backend/app/main.py`, `backend/app/api/router.py`, `backend/app/services/assistant.py`, `backend/app/services/agent_assistant.py`, `app/(platform)/manager/assistant-ia/page.tsx`, `lib/api/endpoints.ts` |
| Active runtime architecture is `Next.js` frontend + `FastAPI` backend + SQLAlchemy/Alembic data layer. | confirmed by code | `package.json`, `backend/app/main.py`, `backend/app/api/router.py`, `backend/requirements.txt`, `backend/alembic/versions/ba235d013f9c_initial_schema.py` |
| PostgreSQL/pgvector is explicitly supported for RAG, while SQLite is supported for local/audit modes. | confirmed by code | `backend/app/core/config.py`, `backend/alembic/versions/3f4c2a1b9d7e_add_rag_pgvector_tables.py`, `backend/app/models/rag.py`, `backend/app/db/session.py` |
| The repository also contains a legacy Express + Prisma backend that overlaps with FastAPI capabilities. | confirmed by code | `src/server.ts`, `src/app.ts`, `src/routes/chat.ts`, `src/lib/prisma.ts`, `prisma/schema.prisma` |
| Some top-level documentation is stale and describes frontend/mock-only behavior, which no longer matches current backend implementation. | confirmed by code | `README.md`, `docs/architecture.md` |

## Module-by-Module Evidence Table

| Module | Implementation Level | What Is Actually Implemented | Status | Evidence |
|---|---|---|---|---|
| Frontend (Next.js App Router) | Implemented | Admin/manager pages, assistant UI, API-driven hooks, session-based assistant UX. | confirmed by code | `app/(platform)/**/page.tsx`, `app/(platform)/manager/assistant-ia/page.tsx`, `hooks/*.ts`, `lib/api/client.ts`, `lib/api/endpoints.ts`, `lib/api/types.ts` |
| Backend API (FastAPI) | Implemented | Auth, admin, members, parcels, stocks, batches, process, analytics, chat, ML, commercial, treasury, references. | confirmed by code | `backend/app/main.py`, `backend/app/api/router.py`, `backend/app/api/routes/*.py` |
| Operational core workflows | Implemented | Collection→stock updates, stock reservation by lot, ordered process-step execution, auto recommendation generation, commercial order/invoice/treasury transitions. | confirmed by code | `backend/app/services/inputs.py`, `backend/app/services/stocks.py`, `backend/app/services/batches.py`, `backend/app/services/process_steps.py`, `backend/app/services/analytics.py`, `backend/app/services/commercial.py`, `backend/app/services/treasury.py` |
| Chatbot (deterministic path `/chat`) | Implemented | Intent routing (`SQL_ONLY/RAG_ONLY/HYBRID/...`), SQL fact bundle, RAG hits, orchestration context, persisted citations/metrics/UI blocks. | confirmed by code | `backend/app/services/chat_retrieval_router.py`, `backend/app/services/assistant.py`, `backend/app/services/chat_orchestrator.py`, `backend/app/models/chat.py`, `backend/app/schemas/chat.py` |
| Chatbot (agentic path `/chat/agent`) | Implemented | Multi-agent orchestration with dedicated SQL/RAG/ML/recommendation agents, source contracts, response verification, audit logs. | confirmed by code | `backend/app/services/agent_assistant.py`, `backend/app/ai/orchestrator/agent_orchestrator.py`, `backend/app/ai/orchestrator/agent_registry.py`, `backend/app/ai/agents/*.py`, `backend/app/models/ai_audit.py` |
| RAG indexing/retrieval | Implemented | App-data indexing into `rag_documents/rag_chunks`, embedding generation, hybrid retrieval, reranking, metadata validation, freshness/scope diagnostics. | confirmed by code | `backend/app/services/rag_indexer.py`, `backend/app/services/rag_embeddings.py`, `backend/app/ai/retrieval/hybrid_retriever.py`, `backend/app/services/rag_context_builders.py`, `backend/app/services/rag_grounding.py` |
| ML pipeline | Implemented (prototype-grade) | Feature engineering, training (RF regressor/classifier + IsolationForest), prediction/assessment endpoints, model registry/logging, impact recommender feedback loop. | confirmed by code | `backend/app/services/ml.py`, `backend/app/ml/features/engineer.py`, `backend/app/ml/training/trainer.py`, `backend/app/ml/inference/predictor.py`, `backend/app/ml/recommendations/impact_engine.py`, `backend/app/models/ml.py` |
| Recommendation logic | Implemented (multi-layer) | Rule-based operational recommendations, ML recommendation mapping, orchestrated recommendation synthesis from SQL/RAG/ML evidence. | confirmed by code | `backend/app/services/analytics.py`, `backend/app/ml/recommendations/rule_engine.py`, `backend/app/ai/tools/recommendation_tools.py` |
| Validation/audit harnesses | Implemented | Multiple scripted audits and JSON/MD outputs for chatbot, RAG, ML, full-demo checks. | confirmed by code | `backend/scripts/*.py`, `backend/reports/*.json`, `backend/reports/*.md`, `backend/artifacts/*.json` |
| Legacy Express + Prisma backend | Partial / Legacy | Still present and runnable by script, but duplicates FastAPI domain; unclear if still part of target architecture. | inferred | `package.json` (`api:dev`), `src/server.ts`, `src/routes/*.ts`, `prisma/schema.prisma` |
| Older SQL schema files in `database/` | Partial / Legacy | Schema differs from current FastAPI SQLAlchemy/Alembic domain (e.g., old entities/vector dims). | confirmed by code | `database/schema.sql`, `backend/app/models/*.py`, `backend/alembic/versions/*.py` |

## Architecture Summary (Current Implemented)

### 1) Application stack
- Frontend: Next.js 15 + React 19 + React Query.  
  Status: confirmed by code.  
  Evidence: `package.json`, `app/`, `hooks/`.
- Backend: FastAPI with route modules and dependency-based auth.  
  Status: confirmed by code.  
  Evidence: `backend/app/main.py`, `backend/app/api/router.py`, `backend/app/api/routes/*.py`.
- Data access: SQLAlchemy ORM + Alembic migrations.  
  Status: confirmed by code.  
  Evidence: `backend/app/models/*.py`, `backend/alembic/versions/*.py`.
- RAG storage: `rag_documents` + `rag_chunks` with `vector(1536)` on PostgreSQL.  
  Status: confirmed by code.  
  Evidence: `backend/alembic/versions/3f4c2a1b9d7e_add_rag_pgvector_tables.py`, `backend/app/models/rag.py`.

### 2) Chat architecture split
- `/chat`: deterministic SQL/RAG/hybrid planner with structured context and UI blocks.  
  Status: confirmed by code.  
  Evidence: `backend/app/api/routes/chat.py`, `backend/app/services/assistant.py`, `backend/app/services/chat_retrieval_router.py`.
- `/chat/agent`: agent orchestrator route with specialized agents and audit logging.  
  Status: confirmed by code.  
  Evidence: `backend/app/api/routes/chat.py`, `backend/app/services/agent_assistant.py`, `backend/app/ai/orchestrator/*`.

### 3) Data persistence
- Chat sessions/messages persisted with citations, context metrics, dashboards, UI blocks.  
  Status: confirmed by code.  
  Evidence: `backend/app/models/chat.py`, `backend/alembic/versions/d3e8b92a1f07_add_chat_sessions_and_messages.py`, `backend/alembic/versions/7c9d2e4a1b3f_add_chat_ui_blocks.py`.
- AI audit logs persisted (route, confidence, sources, warnings, preview).  
  Status: confirmed by code.  
  Evidence: `backend/app/models/ai_audit.py`, `backend/alembic/versions/1f3e5a7b9c21_add_ai_chat_audit_logs.py`.

## Database Entities and Operational Workflows

### Core entities (implemented)
- Cooperative/users/access: `cooperatives`, `users`.  
  Status: confirmed by code.  
  Evidence: `backend/app/models/cooperative.py`, `backend/app/models/user.py`.
- Producer operations: `members`, `fields`, `parcels`, `pre_harvest_steps`, `inputs`, `stocks`, `batches`, `process_steps`.  
  Status: confirmed by code.  
  Evidence: `backend/app/models/member.py`, `field.py`, `parcel.py`, `pre_harvest_step.py`, `input.py`, `stock.py`, `batch.py`, `process_step.py`.
- Finance/commercial: `global_charges`, `farmer_advances`, `treasury_transactions`, `commercial_catalog_products`, `commercial_orders`, `commercial_invoices`.  
  Status: confirmed by code.  
  Evidence: `backend/app/models/global_charge.py`, `farmer_advance.py`, `treasury_transaction.py`, `commercial_*.py`.
- AI/RAG/ML/chat: `recommendations`, `ml_*`, `recommendation_feedback_logs`, `rag_*`, `chat_*`, `ai_chat_audit_logs`.  
  Status: confirmed by code.  
  Evidence: `backend/app/models/recommendation.py`, `ml.py`, `rag.py`, `chat.py`, `ai_audit.py`.

### Operational workflows (implemented)
- Input collection updates stock totals automatically; manual stock CRUD is intentionally blocked.  
  Status: confirmed by code.  
  Evidence: `backend/app/services/inputs.py`, `backend/app/services/stocks.py`.
- Lot creation reserves stock; process-step execution updates lot status/current quantity; completion releases reserved stock and moves processed output.  
  Status: confirmed by code.  
  Evidence: `backend/app/services/batches.py`, `backend/app/services/process_steps.py`.
- Recommendation generation follows process-step analytics and anomaly/risk logic.  
  Status: confirmed by code.  
  Evidence: `backend/app/services/analytics.py`.
- Commercial flow supports order lifecycle transitions, stock reservation/deduction, invoice creation, and treasury income on payment.  
  Status: confirmed by code.  
  Evidence: `backend/app/services/commercial.py`.
- Farmer advances are linked to treasury expense transactions and synchronized/cancelled together.  
  Status: confirmed by code.  
  Evidence: `backend/app/services/farmer_advances.py`, `backend/app/services/treasury.py`.

## Chatbot Architecture Details

### Routing and separation
- Intent-based retrieval planner separates `SQL_ONLY`, `RAG_ONLY`, `HYBRID`, `SMALL_TALK`, `CLARIFICATION_NEEDED`, `UNSUPPORTED`.  
  Status: confirmed by code.  
  Evidence: `backend/app/services/chat_retrieval_router.py`.
- Agentic orchestrator maps routes to SQL/RAG/ML/recommendation agents.  
  Status: confirmed by code.  
  Evidence: `backend/app/ai/orchestrator/agent_registry.py`, `backend/app/ai/orchestrator/intent_router.py`.

### Response blocks and persistence
- Deterministic chat builds structured blocks (`executive_summary`, `kpi_grid`, `risk_cards`, `analysis_section`, `recommendation_cards`, `confidence_block`, `evidence_drawer`, `table`).  
  Status: confirmed by code.  
  Evidence: `backend/app/services/assistant.py` (`_build_executive_ui_blocks`).
- Agentic path maps agent blocks to legacy UI block types for frontend compatibility.  
  Status: confirmed by code.  
  Evidence: `backend/app/services/agent_assistant.py` (`_to_legacy_ui_blocks`).
- Sessions/messages and block payloads are persisted and replayed.  
  Status: confirmed by code.  
  Evidence: `backend/app/services/assistant.py`, `backend/app/models/chat.py`, `app/(platform)/manager/assistant-ia/page.tsx`.

## ML Pipeline (Models, Features, Metrics, Limitations)

### Implemented ML pipeline
- Feature engineering includes historical/stage/product/season/rolling features and canonical stage normalization.  
  Status: confirmed by code.  
  Evidence: `backend/app/ml/features/engineer.py`, `backend/app/ml/utils/stage_normalization.py`.
- Training pipeline uses RandomForest regressor/classifier + IsolationForest, time-based split, baseline comparisons, artifact export, model registry.  
  Status: confirmed by code.  
  Evidence: `backend/app/ml/training/trainer.py`, `backend/app/ml/utils/model_registry.py`, `backend/app/ml/utils/model_store.py`.
- Inference/assessment endpoints and logs are implemented (`/ml/predict`, `/ml/assess`, `/ml/recommendation`, feedback).  
  Status: confirmed by code.  
  Evidence: `backend/app/api/routes/ml.py`, `backend/app/services/ml.py`, `backend/app/ml/inference/predictor.py`, `backend/app/models/ml.py`.

### Reported metrics/limits (latest artifacts)
- Internal validation reports show moderate classification, weak regression fit, no supervised anomaly ground-truth metrics.  
  Status: confirmed by audit/test.  
  Evidence: `backend/reports/ml_model_validation_report.json`, `backend/reports/final_ai_validation_report.json`.

## RAG Pipeline (Indexing, Retrieval, Metadata, Evaluation, Limitations)

### Implemented RAG pipeline
- Reindexer collects multi-domain source docs, hashes content, chunks text, embeds, upserts, and prunes stale records.  
  Status: confirmed by code.  
  Evidence: `backend/app/services/rag_indexer.py`.
- Embedding providers support OpenAI/OpenRouter/custom with dimension guardrails (1536 expected).  
  Status: confirmed by code.  
  Evidence: `backend/app/services/rag_embeddings.py`, `backend/app/core/config.py`.
- Retrieval is hybrid vector+keyword with reranking/filter boosts/fallbacks.  
  Status: confirmed by code.  
  Evidence: `backend/app/ai/retrieval/hybrid_retriever.py`, `backend/app/ai/retrieval/retrieval_filters.py`, `backend/app/ai/retrieval/reranker.py`.
- Chunk builders enforce semantic chunk types and metadata contract for operational + reference data.  
  Status: confirmed by code.  
  Evidence: `backend/app/services/rag_context_builders.py`, `backend/app/services/rag_chunk_registry.py`.

### Reported RAG evaluation limits
- Reported grounding/retrieval quality is mixed; chunk coverage and citation relevance are limited in some evaluations.  
  Status: confirmed by audit/test.  
  Evidence: `backend/reports/final_ai_validation_report.json`, `backend/artifacts/rag_benchmark_report.json`, `backend/reports/chat_sql_rag_eval_harness_2026-05-11.json`.

## Recommendation Engine (Inputs, Logic, Outputs, Limits)

| Layer | Inputs | Logic | Outputs | Status | Evidence |
|---|---|---|---|---|---|
| Operational analytics recommender | Batch + process-step losses + anomaly score + stock alerts | Threshold/risk logic, stage-specific actions, risk-level mapping | `recommendations` table entries and API payloads | confirmed by code | `backend/app/services/analytics.py`, `backend/app/models/recommendation.py` |
| ML recommendation mapper | ML prediction/assessment payloads | Rule-engine actions and reasoning signals | structured recommendation JSON + optional LLM explanation + feedback logging | confirmed by code | `backend/app/ml/recommendations/rule_engine.py`, `backend/app/services/ml.py`, `backend/app/models/ml.py` |
| Agentic recommendation synthesizer | SQL/RAG/ML evidence packs | Evidence-gated priority recommendations with source tags | response blocks and recommendation list in agent response | confirmed by code | `backend/app/ai/tools/recommendation_tools.py`, `backend/app/ai/agents/recommendation_agent.py` |

Limit caveat: quality depends on available evidence and data quality; fallback messages occur when evidence is insufficient.  
Status: confirmed by code + confirmed by audit/test.  
Evidence: `backend/app/ai/agents/recommendation_agent.py`, `backend/reports/final_ai_validation_report.json`.

## Validation Summary

### Direct local test evidence (this repo state)
- Command attempted: `cd backend && ../.venv/bin/python -m pytest --collect-only -q`  
  Result: `206 tests collected`, `5 collection errors`.  
  Status: confirmed by audit/test.
- Blocking errors are import failures: scripts expect `SessionLocal` symbol missing from `app.db.session`.  
  Status: confirmed by audit/test.  
  Evidence: `backend/app/db/session.py`, `backend/scripts/evaluate_ml_models.py`, `backend/tests/test_ml_evaluation.py`.

### Scripted audit evidence (checked-in reports)
- Chat/RAG eval harness on 2026-05-11 shows 5/5 cases passed in that harness run.  
  Status: confirmed by audit/test.  
  Evidence: `backend/reports/chat_sql_rag_eval_harness_2026-05-11.json`.
- Final AI report (2026-05-08) reports strong chatbot pass rates but also grounding/latency limitations.  
  Status: confirmed by audit/test.  
  Evidence: `backend/reports/final_ai_validation_report.json`, `backend/reports/performance_summary.md`.
- ML validation report (2026-05-08) reports dataset size, class imbalance, weak regression fit, and anomaly-label limitation.  
  Status: confirmed by audit/test.  
  Evidence: `backend/reports/ml_model_validation_report.json`.

## Deployment / Runtime Setup

| Item | Status | Evidence |
|---|---|---|
| Frontend dev server on port 3001 | confirmed by code | `package.json`, `scripts/dev.sh` |
| FastAPI service startup + migrations in container entrypoint | confirmed by code | `backend/scripts/container-start.sh`, `backend/Dockerfile` |
| Local compose includes pgvector Postgres + backend service | confirmed by code | `docker/docker-compose.yml` |
| Azure backend deployment script exists | confirmed by code | `scripts/deploy-backend-azure.sh` |
| Env-driven LLM/RAG/DB configuration | confirmed by code | `backend/app/core/config.py`, `backend/.env.example`, `.env.example` |

## What Can Be Safely Claimed in the PFE Report

1. The implemented system is a multi-module cooperative operations platform with AI-assisted decision support, not just a mock UI.  
   Status: confirmed by code.  
   Evidence: `backend/app/api/router.py`, `backend/app/services/*.py`, `app/(platform)/manager/assistant-ia/page.tsx`.
2. The chatbot architecture includes explicit routing and separation of SQL, RAG, ML, and recommendation responsibilities.  
   Status: confirmed by code.  
   Evidence: `backend/app/services/chat_retrieval_router.py`, `backend/app/ai/orchestrator/agent_registry.py`.
3. RAG indexing/retrieval and ML pipelines are implemented end-to-end with persistence, scripts, and evaluation artifacts.  
   Status: confirmed by code + confirmed by audit/test.  
   Evidence: `backend/app/services/rag_indexer.py`, `backend/app/services/ml.py`, `backend/reports/*.json`.
4. Validation is reproducible via repository scripts and includes explicit limitation reporting.  
   Status: confirmed by code + confirmed by audit/test.  
   Evidence: `backend/scripts/*.py`, `backend/reports/full_demo_validation_summary.md`, `backend/reports/pfe_final_validation_summary.md`.

## What Must NOT Be Overclaimed

1. Do not claim real-field external validity; evidence is predominantly synthetic/demo and scripted.  
   Status: confirmed by audit/test.  
   Evidence: `backend/reports/ml_model_validation_report.json`, `backend/reports/final_ai_validation_report.json`.
2. Do not claim strong predictive performance for all classes/stages; high-risk recall and regression fit are limited.  
   Status: confirmed by audit/test.  
   Evidence: `backend/reports/ml_model_validation_report.json`.
3. Do not claim supervised anomaly detection accuracy metrics (TP/FP/FN) are established.  
   Status: confirmed by audit/test.  
   Evidence: `backend/reports/ml_model_validation_report.json`.
4. Do not claim all automated tests currently pass in the checked repository state.  
   Status: confirmed by audit/test.  
   Evidence: local pytest run output; `backend/app/db/session.py`, `backend/scripts/evaluate_ml_models.py`.
5. Do not present legacy Express/Prisma paths as the authoritative runtime unless explicitly scoped as legacy/historical.  
   Status: inferred.  
   Evidence: `src/`, `prisma/schema.prisma`, `backend/app/` coexistence.

## Missing Evidence / Open Questions Before Final Chapter Writing

| Gap | Why It Matters | Status | Evidence |
|---|---|---|---|
| FastAPI vs Express/Prisma canonical scope not formally documented | Risk of architectural inconsistency in report chapters | unclear / needs verification | `src/app.ts`, `backend/app/main.py`, `README.md`, `docs/architecture.md` |
| Test suite collection failures (`SessionLocal` imports) | Reported reproducibility and CI health are weakened | confirmed by audit/test | `backend/app/db/session.py`, `backend/tests/test_ml_evaluation.py`, `backend/scripts/evaluate_ml_models.py` |
| Current (2026-05-13) full test pass rate after latest code changes is unknown | Needed for final “validation achieved” claims | unclear / needs verification | local pytest run stopped at collection errors |
| RAG quality metrics are mixed despite high scenario pass rates in some audits | Need nuanced claim language (routing pass != grounding quality) | confirmed by audit/test | `backend/reports/final_ai_validation_report.json`, `backend/artifacts/rag_benchmark_report.json` |
| Top-level docs are outdated relative to current backend | Report chapter intro may accidentally understate/overstate real scope | confirmed by code | `README.md`, `docs/architecture.md` |

## Recommended Immediate Pre-Report Fixes

1. Decide and document canonical runtime architecture (FastAPI-first, legacy Express marked deprecated).  
   Status: inferred.
2. Restore compatibility for script imports expecting `SessionLocal` or refactor scripts/tests to use `get_db` pattern consistently.  
   Status: confirmed by audit/test.
3. Re-run full backend test suite after fix and record updated pass/fail counts with date stamp.  
   Status: unclear / needs verification.
4. Re-run key validation scripts and regenerate report artifacts with explicit timestamp and dataset provenance.  
   Status: confirmed by code (scripts exist).


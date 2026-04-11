# Architecture

## Overview
- Frontend (`Next.js + TypeScript + Tailwind`): operational dashboard, transformation analysis UI, RAG chat UI.
- Backend (`FastAPI`): API layer, orchestration, validation, service modules.
- AI Layer (`ai/`): reusable RAG and analytics modules shared by backend services.
- Database (`PostgreSQL + pgvector`): operational tables + vectorized knowledge base.

## Service Flow
1. Cooperative data is sent to `/api/inputs` and `/api/process`.
2. `/api/analyze` computes loss/efficiency and anomaly flags.
3. `/api/recommend` returns practical corrective actions.
4. `/api/chat` runs RAG retrieval over `knowledge_chunks` and queries LLM.

## Scalability Notes
- Keep model providers behind service interfaces.
- Move ingestion/embedding to async workers for large document sets.
- Add Alembic for schema migrations as soon as schema starts evolving.

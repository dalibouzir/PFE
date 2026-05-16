# Architecture (Canonical PFE Scope)

## Positioning

This repository is **FastAPI-first** for the PFE runtime and evidence scope.

## Runtime Components

- Frontend: `Next.js` app router (`app/`, `components/`, `hooks/`, `lib/api`).
- Backend API: `FastAPI` (`backend/app/main.py`, `backend/app/api/routes`).
- Persistence: `SQLAlchemy` models + `Alembic` migrations (`backend/app/models`, `backend/alembic/versions`).
- Database target: `PostgreSQL` (local SQLite supported for test/audit mode).
- RAG: `pgvector` tables (`rag_documents`, `rag_chunks`) + hybrid retrieval.
- ML: feature engineering, training, inference, recommendation feedback loop.

## High-Level Flow

1. Next.js frontend calls FastAPI endpoints.
2. FastAPI services orchestrate operational SQL context, RAG retrieval, and ML signals.
3. Chat endpoints persist sessions/messages, citations, metrics, and UI blocks.
4. RAG indexing synchronizes operational/reference rows into `rag_documents`/`rag_chunks`.
5. ML endpoints produce predictions/assessments and recommendation artifacts.

## Explicitly Excluded from Canonical Runtime Scope

These paths exist but are treated as **legacy** for PFE runtime claims:

- `_archive/legacy-express-prisma/src/` (Express backend surface)
- `_archive/legacy-express-prisma/prisma/` (Prisma schema stack)

Use them only for backward compatibility, not as the architecture baseline for chapters 3–5.

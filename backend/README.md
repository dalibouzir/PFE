# WeeFarm Backend

FastAPI backend for the WeeFarm cooperative platform.

## Quick start

```bash
cd backend
python3 -m pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python3 -m app.seeds.seed_data
uvicorn app.main:app --reload --port 8000
```

Docs:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Supabase pgvector bootstrap (RAG)

1. Set `DATABASE_URL` to your Supabase Postgres URL (with `sslmode=require`).
2. Run migrations:

```bash
cd backend
../.venv/bin/alembic upgrade head
```

This creates:
- `rag_documents` (source tracking per cooperative)
- `rag_chunks` (chunk text + `vector(1536)` embeddings)

Reindex endpoint:

```http
POST /chat/rag/reindex
Authorization: Bearer <token>
Content-Type: application/json

{
  "cooperative_id": "<uuid-admin-only-optional-for-manager>",
  "force": false
}
```

Refresh behavior:
- unchanged source rows are skipped with `content_hash`
- changed rows replace old chunks
- missing rows are deleted from RAG tables (stale cleanup)

Seeded local credentials:

- `admin@weefarm.local / Admin123!`
- `manager@weefarm.local / Manager123!`

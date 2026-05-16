# WeeFarm

Plateforme de support à la décision opérationnelle pour coopératives agricoles.

## Canonical Runtime Architecture (FastAPI-first)

Ce depot est positionne **FastAPI-first** pour le PFE:

- Frontend: `Next.js` (App Router) dans `app/`, `components/`, `hooks/`, `lib/api`.
- Backend canonique: `FastAPI` dans `backend/app/`.
- Data layer canonique: `SQLAlchemy + Alembic` dans `backend/app/models` et `backend/alembic`.
- Base cible: `PostgreSQL`/`pgvector` (Supabase en cible cloud).
- Deploiement backend: image Docker via `backend/Dockerfile`.
- IA metier: RAG, ML, chatbot/agent orchestration dans `backend/app/ai` et `backend/app/services`.

Références:
- `backend/app/main.py`
- `backend/app/api/router.py`
- `backend/app/models/`
- `backend/alembic/versions/`
- `backend/alembic/versions/3f4c2a1b9d7e_add_rag_pgvector_tables.py`
- `backend/Dockerfile`
- `backend/scripts/container-start.sh`

## Archived Legacy Components (Not Canonical Runtime)

Les composants Express/Prisma historiques ont ete archives ici:

- `_archive/legacy-express-prisma/src/`
- `_archive/legacy-express-prisma/prisma/`

Voir aussi:
- `_archive/legacy-express-prisma/src/LEGACY_SCOPE.md`
- `_archive/legacy-express-prisma/prisma/LEGACY_SCOPE.md`

Note importante: le dossier `database/` est conserve uniquement pour le bootstrap local `docker-compose` (mount de `database/schema.sql` et `database/seed.sql`). Il ne represente pas le schema de production canonique, qui est `Supabase/PostgreSQL + SQLAlchemy/Alembic` via `backend/alembic/`.

## Quick Start

### Frontend

```bash
npm install
npm run dev
```

Frontend disponible sur `http://localhost:3001`.

### Backend (FastAPI)

```bash
cd backend
python3 -m pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python3 -m app.seeds.seed_data
uvicorn app.main:app --reload --port 8000
```

Docs API:
- Swagger: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Functional Scope Implemented

- Gestion coopérative: membres, parcelles, intrants/collectes, stocks.
- Flux de transformation: lots, étapes process, pertes/efficacité.
- Finance/commercial: avances, trésorerie, catalogue, commandes, factures.
- IA opérationnelle: chatbot (SQL/RAG/HYBRID + voie agentique), RAG pgvector, ML et recommandations.

## License

Usage académique / demo PFE.

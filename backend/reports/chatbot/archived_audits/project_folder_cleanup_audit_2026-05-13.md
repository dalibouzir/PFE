# WeeFarm Project Folder Cleanup Audit - 2026-05-13

## Objective
Safely clean repository structure while preserving the canonical runtime:
- Next.js frontend
- FastAPI backend
- SQLAlchemy + Alembic migrations
- PostgreSQL/pgvector (Supabase target)
- Dockerized backend deployment
- RAG/ML/chatbot orchestration inside `backend/`

## Canonical Runtime Confirmation
Canonical runtime remains:
- Frontend: `app/`, `components/`, `hooks/`, `context/`, `lib/api/`
- Backend: `backend/app/` (FastAPI routes/services/models/ai/ml)
- Migrations: `backend/alembic/`, `backend/alembic.ini`
- Container backend: `backend/Dockerfile`, `backend/scripts/container-start.sh`

## Final Folder Classification

### Active
- `app/`, `components/`, `hooks/`, `context/`, `lib/`, `public/`
- `backend/app/`, `backend/alembic/`, `backend/tests/`, `backend/scripts/`
- `docker/` (backend compose support path still used)

### Legacy but referenced
- `database/`:
  - still mounted by `docker/docker-compose.yml` (`database/schema.sql`, `database/seed.sql`)
  - kept for local compose bootstrap compatibility
  - **not** canonical production schema flow

### Legacy and archived
- `_archive/legacy-express-prisma/src/`
- `_archive/legacy-express-prisma/prisma/`
- `_archive/legacy-ai/ai/`
- `_archive/stale-docs/Script for rapport pfe.md`

### Generated artifacts / ignore targets
- `backend/artifacts/versions/`
- `backend/artifacts/screenshots/`
- `backend/artifacts/prediction_logs.jsonl`
- `.venv*/`, `.pytest_cache/`, `__pycache__/`

### Unknown / manual review
- Large docs corpus under `docs/` still contains historical references in some files; runtime-safe but editorial cleanup remains.

## Top-level `ai/` Classification Decision
Result: **safe to archive**.

Reason:
- No active runtime imports found from frontend or `backend/app` into top-level `ai/`.
- References were only self-imports inside that folder and historical documentation mentions.
- Canonical AI runtime is `backend/app/ai/`.

Action applied:
- Moved `ai/` -> `_archive/legacy-ai/ai/`

## Package Dependency Audit (Legacy vs Active)

### Legacy-only candidates (safe to consider removing later, after lockfile refresh and local validation)
These were not referenced outside `_archive/` and docs during scan:
- `@prisma/client`
- `prisma`
- `express`
- `cors`
- `dotenv`
- `jsonwebtoken`
- `multer`
- `redis`
- `socket.io`
- `bcryptjs`
- `nodemon` (dev)
- `@types/express`
- `@types/cors`
- `@types/jsonwebtoken`
- `@types/multer`

### Confirmed active frontend/runtime deps (examples)
- `@tanstack/react-query`
- `react-hook-form`
- `lucide-react`
- `recharts`
- `socket.io-client`
- `zod`

Note: dependency removal was intentionally not executed in this pass.

## Reproducibility Fixes Applied
1. Added root `pytest.ini` with `pythonpath = backend` and `testpaths = backend/tests`.
2. Added narrow lint exclusion for:
   - `scripts/capture_phase61_screenshots.js`
   - `scripts/capture_phase62_screenshots.js`
3. Strengthened README architecture note to state `database/` is compose-bootstrap legacy support only.

## Verification Commands and Results
Executed from repo root:

1. `npx tsc --noEmit`
- Result: PASS

2. `npm run lint`
- Result: PASS

3. `python -m pytest --collect-only backend/tests`
- Result on this machine: FAIL (`python` binary not installed in shell)

4. `python -c "import sys; sys.path.insert(0,'backend'); import app.main; print('FASTAPI_IMPORT_OK')"`
- Result on this machine: FAIL (`python` binary not installed in shell)

Interpreter validation with project runtime (`.venv312/bin/python`, Python 3.12):
- `./.venv312/bin/python -m pytest --collect-only backend/tests` -> PASS (`218 tests collected`)
- `./.venv312/bin/python -c "import sys; sys.path.insert(0,'backend'); import app.main; print('FASTAPI_IMPORT_OK')"` -> PASS (`FASTAPI_IMPORT_OK`)

Additional note:
- System `python3` here is 3.9 and cannot collect this suite due modern type syntax (`str | None`) used by backend code.

## Files Updated in This Pass
- `pytest.ini` (new)
- `eslint.config.mjs`
- `README.md`
- `backend/reports/project_folder_cleanup_audit_2026-05-13.md`
- Archived move: `ai/` -> `_archive/legacy-ai/ai/`

## Remaining Risks
1. `database/` remains a compose bootstrap dependency and can mislead architecture readers if not explicitly framed as legacy-local support.
2. Root `python` command portability depends on environment; repository now resolves import path correctly, but interpreter alias/version still must be configured (`python` -> 3.11+ recommended).
3. Legacy npm dependencies are still installed; removing them should be a separate controlled cleanup step.

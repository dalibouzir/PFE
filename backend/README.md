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

Seeded local credentials:

- `admin@weefarm.local / Admin123!`
- `manager@weefarm.local / Manager123!`

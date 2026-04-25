FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY docs/ ./docs/

EXPOSE 8000

CMD ["/bin/sh", "-c", "alembic upgrade head && python3 -m app.seeds.seed_data && (python3 -m app.ml.training.runner || echo 'ML training skipped at startup due to runtime configuration') && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

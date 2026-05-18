FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    HF_HOME=/tmp/hf

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY backend/app ./app
COPY backend/scripts/container-start.sh ./scripts/container-start.sh
COPY docs/ ./docs/

RUN chmod +x ./scripts/container-start.sh \
    && addgroup --system app \
    && adduser --system --ingroup app app \
    && mkdir -p /app/artifacts \
    && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python3 -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\", \"8000\")}/health', timeout=3).read()"

ENTRYPOINT ["./scripts/container-start.sh"]

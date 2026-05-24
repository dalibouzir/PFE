from pathlib import Path
import logging
import time
from threading import Thread

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError

from app.api.router import api_router
from app.core.config import settings
from app.db.schema_compat import ensure_runtime_schema_compat
from app.services.runtime_warmup import start_runtime_warmup_background
from app.utils.exceptions import AppError


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Backend API for WeeFarm cooperative management workflows.",
)
logger = logging.getLogger(__name__)


def _parse_cors_origins() -> list[str]:
    return [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _run_schema_compat_background() -> None:
    started = time.perf_counter()
    logger.info("Background schema compatibility check starting")
    try:
        ensure_runtime_schema_compat()
    except Exception:
        logger.exception("Background schema compatibility check failed")
        return
    logger.info(
        "Background schema compatibility check completed in %.2f ms",
        (time.perf_counter() - started) * 1000.0,
    )

@app.on_event("startup")
def startup_schema_compat():
    logger.info("Scheduling background schema compatibility check")
    Thread(target=_run_schema_compat_background, name="schema-compat-startup", daemon=True).start()
    start_runtime_warmup_background()


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(OperationalError)
async def db_operational_error_handler(request: Request, exc: OperationalError):
    message = str(exc).lower()
    if "emaxconnsession" in message or "max clients reached" in message:
        return JSONResponse(
            status_code=503,
            content={"detail": "Database connection pool is temporarily saturated. Please retry shortly."},
        )
    return JSONResponse(status_code=500, content={"detail": "Database operation failed."})


@app.get("/health", tags=["Health"], summary="Health-check endpoint.")
def health():
    return {"status": "ok", "environment": settings.app_env}


uploads_dir = Path(settings.uploads_dir)
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

app.include_router(api_router)

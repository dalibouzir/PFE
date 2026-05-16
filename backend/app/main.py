from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.db.schema_compat import ensure_runtime_schema_compat
from app.utils.exceptions import AppError


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Backend API for WeeFarm cooperative management workflows.",
)


def _parse_cors_origins() -> list[str]:
    return [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_schema_compat():
    ensure_runtime_schema_compat()


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/health", tags=["Health"], summary="Health-check endpoint.")
def health():
    return {"status": "ok", "environment": settings.app_env}


app.include_router(api_router)

from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import OperationalError

from app.core.config import settings

logger = logging.getLogger(__name__)

_ctx_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_ctx_sql_operation: ContextVar[str | None] = ContextVar("sql_operation", default=None)


# Lazy engine creation to respect audit_mode set by pytest_configure
_engine = None
_session_local = None


def _get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        db_url = settings.effective_database_url
        _engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=2,
            pool_timeout=10,
            pool_recycle=120,
            pool_use_lifo=True,
            connect_args={
                # Prevent leaked transactions from pinning Supabase session slots.
                "options": "-c idle_in_transaction_session_timeout=60000 -c statement_timeout=30000",
            },
        )
        _install_engine_observability(_engine)
    return _engine


def get_engine():
    """Public engine accessor for startup checks/maintenance."""
    return _get_engine()


def _get_session_local():
    """Get or create the SessionLocal factory."""
    global _session_local
    if _session_local is None:
        engine = _get_engine()
        _session_local = sessionmaker(
            bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session
        )
    return _session_local


class _LazySessionLocal:
    """Compatibility shim for scripts/tests importing `SessionLocal`.

    This keeps lazy initialization semantics so pytest audit modes can swap
    database targets before the first session is created.
    """

    def __call__(self, *args: Any, **kwargs: Any) -> Session:
        session_factory = _get_session_local()
        return session_factory(*args, **kwargs)


# Public compatibility handle used across scripts/tests.
SessionLocal = _LazySessionLocal()


def reset_engine():
    """Reset global engine and session_local (used for testing mode transitions)."""
    global _engine, _session_local
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_local = None


def get_db():
    session_local = _get_session_local()
    db = session_local()
    try:
        yield db
    finally:
        db.close()


def set_request_id_context(request_id: str | None) -> None:
    _ctx_request_id.set(request_id)


def set_sql_operation_context(sql_operation: str | None) -> None:
    _ctx_sql_operation.set(sql_operation)


def _install_engine_observability(engine) -> None:
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, connection_record):
        logger.info(
            "db.connect",
            extra={
                "event": {
                    "request_id": _ctx_request_id.get(),
                    "sql_operation": _ctx_sql_operation.get(),
                    "connect_ms": None,
                }
            },
        )

    @event.listens_for(engine, "checkout")
    def _on_checkout(dbapi_connection, connection_record, connection_proxy):
        logger.info(
            "db.checkout",
            extra={
                "event": {
                    "request_id": _ctx_request_id.get(),
                    "sql_operation": _ctx_sql_operation.get(),
                    "checkout_ms": None,
                }
            },
        )

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_started_at", []).append(time.perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        started_stack = conn.info.get("query_started_at", [])
        if not started_stack:
            return
        started_at = started_stack.pop(-1)
        elapsed_ms = round((time.perf_counter() - started_at) * 1000.0, 3)
        row_count = int(getattr(cursor, "rowcount", -1) or 0)
        logger.info(
            "db.sql_execution",
            extra={
                "event": {
                    "request_id": _ctx_request_id.get(),
                    "sql_operation": _ctx_sql_operation.get(),
                    "sql_execution_ms": elapsed_ms,
                    "row_count": row_count,
                }
            },
        )

    @event.listens_for(engine, "handle_error")
    def _handle_error(exception_context):
        original = exception_context.original_exception
        error_name = type(original).__name__
        db_error_type = "OperationalError" if isinstance(original, OperationalError) else error_name
        logger.exception(
            "db.sql_error",
            extra={
                "event": {
                    "request_id": _ctx_request_id.get(),
                    "sql_operation": _ctx_sql_operation.get(),
                    "db_error_type": db_error_type,
                }
            },
        )

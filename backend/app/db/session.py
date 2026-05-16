from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


# Lazy engine creation to respect audit_mode set by pytest_configure
_engine = None
_session_local = None


def _get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        db_url = settings.effective_database_url
        _engine = create_engine(db_url, pool_pre_ping=True)
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

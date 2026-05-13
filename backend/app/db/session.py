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
        connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
        _engine = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
    return _engine


def _get_session_local():
    """Get or create the SessionLocal factory."""
    global _session_local
    if _session_local is None:
        engine = _get_engine()
        _session_local = sessionmaker(
            bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session
        )
    return _session_local


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


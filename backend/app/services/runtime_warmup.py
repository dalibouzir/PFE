from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from sqlalchemy import select

from app.ai.retrieval.hybrid_retriever import HybridRetriever
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User
from app.services.rag_embeddings import embed_texts

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_STATE: dict[str, Any] = {
    "started": False,
    "in_progress": False,
    "completed": False,
    "error": None,
    "started_at": None,
    "finished_at": None,
    "duration_ms": 0,
}


def _enabled() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    raw = str(os.environ.get("AI_RUNTIME_WARMUP_ENABLED", "1")).strip().lower()
    return raw not in {"0", "false", "no", "off"}


def get_runtime_warmup_status() -> dict[str, Any]:
    with _LOCK:
        return dict(_STATE)


def start_runtime_warmup_background() -> bool:
    if not _enabled() or not settings.rag_enabled:
        return False
    with _LOCK:
        if _STATE["in_progress"] or _STATE["completed"]:
            return False
        _STATE["started"] = True
        _STATE["in_progress"] = True
        _STATE["error"] = None
        _STATE["started_at"] = time.time()
    thread = threading.Thread(target=_run_warmup, name="runtime-warmup", daemon=True)
    thread.start()
    logger.info("runtime.warmup.scheduled")
    return True


def _run_warmup() -> None:
    started = time.perf_counter()
    logger.info("runtime.warmup.start")
    error_text = None
    try:
        _warm_embedding_components()
        _warm_retriever_components()
    except Exception as exc:
        error_text = f"{type(exc).__name__}: {exc}"
        logger.exception("runtime.warmup.failed")
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        with _LOCK:
            _STATE["in_progress"] = False
            _STATE["completed"] = error_text is None
            _STATE["error"] = error_text
            _STATE["finished_at"] = time.time()
            _STATE["duration_ms"] = duration_ms
        logger.info(
            "runtime.warmup.done",
            extra={
                "event": {
                    "completed": error_text is None,
                    "error": error_text,
                    "duration_ms": duration_ms,
                }
            },
        )


def _warm_embedding_components() -> None:
    provider = str(settings.rag_embedding_provider or "").strip().lower()
    if provider != "local":
        logger.info("runtime.warmup.embed.skip provider=%s", provider)
        return
    started = time.perf_counter()
    embed_texts(["checklist post-recolte warmup"])
    logger.info("runtime.warmup.embed.ok ms=%s", int((time.perf_counter() - started) * 1000))


def _warm_retriever_components() -> None:
    session = SessionLocal()
    try:
        user = session.scalar(select(User).where(User.cooperative_id.isnot(None)).limit(1))
        if user is None:
            logger.info("runtime.warmup.retriever.skip no_cooperative_user")
            return
        retriever = HybridRetriever(session, user)
        started = time.perf_counter()
        retriever.retrieve_with_diagnostics(
            query="checklist avant emballage",
            filters={
                "product": set(),
                "stage": set(),
                "language": "fr",
                "batch_ref": None,
                "prefer_knowledge_sources": True,
                "avoid_operational_sources": True,
            },
            top_k=2,
        )
        logger.info("runtime.warmup.retriever.ok ms=%s", int((time.perf_counter() - started) * 1000))
    finally:
        session.close()

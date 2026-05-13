from __future__ import annotations

from uuid import UUID

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.models.ai_audit import AIChatAuditLog
from app.models.user import User


class AuditLogger:
    """Stores traceable orchestration metadata for auditability."""

    def __init__(self, db: Session):
        self.db = db
        self._table_exists_cache: bool | None = None

    def _audit_table_exists(self) -> bool:
        if self._table_exists_cache is not None:
            return self._table_exists_cache
        try:
            tables = sa_inspect(self.db.get_bind()).get_table_names()
            self._table_exists_cache = "ai_chat_audit_logs" in tables
        except Exception:
            self._table_exists_cache = False
        return self._table_exists_cache

    def log(
        self,
        *,
        current_user: User,
        conversation_id: str | None,
        user_query: str,
        language: str,
        detected_entities: dict,
        selected_route: str,
        route_confidence: float,
        agents_used: list[str],
        sources: list[dict],
        final_confidence: float,
        warnings: list[str],
        response_preview: str,
        execution_time_ms: int,
    ) -> None:
        if not self._audit_table_exists():
            return

        sql_sources = [source for source in sources if source.get("type") == "sql"]
        rag_sources = [source for source in sources if source.get("type") == "rag"]
        ml_sources = [source for source in sources if source.get("type") == "ml"]

        user_id = current_user.id if isinstance(current_user.id, UUID) else None

        entry = AIChatAuditLog(
            conversation_id=conversation_id,
            user_id=user_id,
            cooperative_id=current_user.cooperative_id,
            user_query=user_query,
            detected_language=language,
            detected_entities=detected_entities,
            selected_route=selected_route,
            route_confidence=route_confidence,
            agents_used=agents_used,
            sql_sources=sql_sources,
            rag_sources=rag_sources,
            ml_sources=ml_sources,
            final_confidence=final_confidence,
            warnings=warnings,
            response_preview=response_preview[:1200],
            execution_time_ms=execution_time_ms,
        )
        try:
            # Keep logger failures isolated from chat persistence transaction.
            with self.db.begin_nested():
                self.db.add(entry)
                self.db.flush()
        except Exception:
            return

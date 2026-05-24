from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import logging
import time
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.orchestrator.agent_orchestrator import AgentOrchestrator
from app.ai.orchestrator.intent_router import IntentRouter
from app.ai.schemas.agent_schemas import AgentRoute
from app.ai.schemas.chat_schemas import ChatAgentResponse
from app.models.chat import ChatMessage, ChatSession
from app.models.mixins import current_utc
from app.models.user import User
from app.db.session import SessionLocal, set_request_id_context


logger = logging.getLogger(__name__)
_TIMEOUT_INTENT_ROUTER = IntentRouter()


def generate_agent_chat_reply(
    db: Session,
    *,
    current_user: User,
    message: str,
    conversation_id: str | None = None,
    user_id: str | None = None,
    language: str | None = "fr",
) -> ChatAgentResponse:
    request_id = str(uuid4())
    set_request_id_context(request_id)
    started_at = time.perf_counter()
    session = _resolve_or_create_session(db, current_user=current_user, conversation_id=conversation_id, seed_text=message)

    try:
        persistence_started_at = time.perf_counter()
        db.add(ChatMessage(session_id=session.id, role="user", content=message))
        db.flush()

        try:
            pool = ThreadPoolExecutor(max_workers=1)
            future = pool.submit(
                _run_orchestrator_with_worker_session,
                request_id=request_id,
                user_id_value=current_user.id,
                fallback_user=current_user,
                message=message,
                language=language,
                conversation_id=str(session.id),
                caller_user_id=user_id,
            )
            response = future.result(timeout=_request_timeout_seconds())
            pool.shutdown(wait=True, cancel_futures=False)
        except FutureTimeoutError:
            try:
                pool.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
            timeout_route = _classify_timeout_route(message=message)
            response = ChatAgentResponse(
                answer="La requête a dépassé le délai d’exécution. Réessayez avec une question plus ciblée.",
                route=timeout_route,
                agents_used=[],
                response_blocks=[],
                sources=[],
                confidence=0.0,
                warnings=["Délai d’exécution dépassé sur cette requête."],
                metadata={
                    "warning_codes": ["REQUEST_TIMEOUT"],
                    "request_id": request_id,
                    "timeout_fallback_route": timeout_route.value,
                },
            )

        db.add(
            ChatMessage(
                session_id=session.id,
                role="assistant",
                content=response.answer,
                mode=f"agentic:{response.route.value}",
                citations_json=_to_legacy_citations(response.sources),
                context_metrics_json=[
                    {
                        "source_id": "agent",
                        "region": "cooperative",
                        "crop": "multi",
                        "metric": "agent.route",
                        "period": "current",
                        "value": 1.0,
                        "unit": response.route.value,
                    },
                    {
                        "source_id": "agent",
                        "region": "cooperative",
                        "crop": "multi",
                        "metric": "agent.confidence",
                        "period": "current",
                        "value": float(response.confidence),
                        "unit": "score",
                    },
                ],
                ui_blocks_json=_to_legacy_ui_blocks(response.response_blocks),
            )
        )
        # Flush both messages before updating session to ensure foreign key visibility.
        db.flush()

        # Persist updated_at once messages are staged.
        db.query(ChatSession).where(ChatSession.id == session.id).update(
            {"updated_at": current_utc()},
            synchronize_session=False,
        )
        db.commit()
        persistence_ms = int((time.perf_counter() - persistence_started_at) * 1000)
    except Exception as exc:
        total_latency_ms = int((time.perf_counter() - started_at) * 1000)
        logger.exception(
            "chat.agent.request_summary",
            extra={
                "event": {
                    "request_id": request_id,
                    "route": None,
                    "intent": None,
                    "sql_operation": None,
                    "total_latency_ms": total_latency_ms,
                    "status": "error",
                    "error_type": type(exc).__name__,
                }
            },
        )
        set_request_id_context(None)
        db.rollback()
        raise

    payload = response.model_dump()
    route_value = str(getattr(response.route, "value", response.route))
    sql_trace = (payload.get("metadata") or {}).get("sql_dispatch_trace") if isinstance(payload.get("metadata"), dict) else {}
    sql_operation = sql_trace.get("sql_operation") if isinstance(sql_trace, dict) else None
    error_type = "REQUEST_TIMEOUT" if "REQUEST_TIMEOUT" in ((payload.get("metadata") or {}).get("warning_codes") or []) else None
    payload["metadata"] = {
        **payload.get("metadata", {}),
        "request_id": request_id,
        "conversation_id": str(session.id),
        "persistence_ms": persistence_ms,
    }
    total_latency_ms = int((time.perf_counter() - started_at) * 1000)
    logger.info(
        "chat.agent.request_summary",
        extra={
            "event": {
                "request_id": request_id,
                "route": route_value,
                "intent": (payload.get("metadata") or {}).get("intent_family"),
                "sql_operation": sql_operation,
                "total_latency_ms": total_latency_ms,
                "status": "ok",
                "error_type": error_type,
            }
        },
    )
    set_request_id_context(None)
    return ChatAgentResponse(**payload)


def _request_timeout_seconds() -> float:
    raw = str(__import__("os").environ.get("AGENT_REQUEST_TIMEOUT_SECONDS", "")).strip()
    try:
        value = float(raw) if raw else 60.0
    except ValueError:
        value = 60.0
    return max(10.0, min(value, 300.0))


def _classify_timeout_route(*, message: str) -> AgentRoute:
    try:
        decision = _TIMEOUT_INTENT_ROUTER.classify(message or "")
        route = decision.route
        if isinstance(route, AgentRoute):
            return route
    except Exception:
        pass
    return AgentRoute.OUT_OF_SCOPE


def _run_orchestrator_with_worker_session(
    *,
    request_id: str,
    user_id_value,
    fallback_user: User,
    message: str,
    language: str | None,
    conversation_id: str,
    caller_user_id: str | None,
) -> ChatAgentResponse:
    worker_db = SessionLocal()
    set_request_id_context(request_id)
    try:
        worker_user = worker_db.get(User, user_id_value) or fallback_user
        orchestrator = AgentOrchestrator(worker_db, worker_user)
        return asyncio.run(
            orchestrator.handle(
                message=message,
                language=language,
                conversation_id=conversation_id,
                user_id=caller_user_id,
            )
        )
    finally:
        try:
            worker_db.close()
        except Exception:
            pass
        set_request_id_context(None)


def _resolve_or_create_session(db: Session, *, current_user: User, conversation_id: str | None, seed_text: str) -> ChatSession:
    if conversation_id:
        try:
            session_uuid = UUID(str(conversation_id))
            existing = db.scalar(select(ChatSession).where(ChatSession.id == session_uuid, ChatSession.user_id == current_user.id))
            if existing:
                return existing
        except ValueError:
            pass

    title = seed_text.strip().splitlines()[0][:80] or "Agent conversation"
    session = ChatSession(
        id=uuid4(),
        user_id=current_user.id,
        cooperative_id=current_user.cooperative_id,
        title=title,
    )
    db.add(session)
    db.flush()
    return session


def _to_legacy_citations(sources: list[dict]) -> list[dict]:
    legacy = []
    for source in sources:
        legacy.append(
            {
                "source_id": str(source.get("title") or source.get("table") or source.get("model") or "source"),
                "source_url": "",
                "region": "cooperative",
                "crop": str(source.get("related_product") or "multi"),
                "topic": str(source.get("type") or "source"),
                "excerpt": str(source.get("label") or source.get("title") or source.get("model") or ""),
            }
        )
    return legacy


def _to_legacy_ui_blocks(response_blocks: list[dict]) -> list[dict]:
    legacy: list[dict] = []
    for block in response_blocks or []:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "custom")
        title = str(block.get("title") or "Bloc")
        payload = {key: value for key, value in block.items() if key not in {"type", "title"}}

        if block_type == "summary":
            legacy.append({"type": "executive_summary", "title": title, "payload": {"text": str(block.get("content") or "")}})
            continue
        if block_type == "recommendations":
            legacy.append({"type": "recommendation_cards", "title": title, "payload": {"items": block.get("items") or []}})
            continue
        if block_type == "chart":
            chart_rows = block.get("data") or []
            x_key = str(block.get("x_key") or "x")
            y_key = str(block.get("y_key") or "y")

            labels: list[str] = []
            values: list[float] = []
            normalized_rows: list[dict] = []
            for item in chart_rows:
                if not isinstance(item, dict):
                    continue
                row = dict(item)
                normalized_rows.append(row)
                label_raw = row.get(x_key, row.get("stage", row.get("product", row.get("batch_ref", row.get("x", "")))))
                labels.append(str(label_raw or ""))
                value_raw = row.get(y_key, row.get("loss_pct", row.get("available_stock_kg", row.get("y", 0.0))))
                try:
                    values.append(float(value_raw or 0.0))
                except (TypeError, ValueError):
                    values.append(0.0)

            legacy.append(
                {
                    "type": "bar_chart" if str(block.get("chart_type") or "").lower() == "bar" else "line_chart",
                    "title": title,
                    "payload": {
                        "chart_type": str(block.get("chart_type") or "bar"),
                        "x_key": x_key,
                        "y_key": y_key,
                        "data": normalized_rows,
                        "labels": labels,
                        "series": [{"name": y_key or "value", "data": values}],
                    },
                }
            )
            continue
        if block_type == "warnings":
            legacy.append({"type": "analysis_section", "title": title, "payload": {"points": [{"text": str(item)} for item in (block.get("items") or [])]}})
            continue

        legacy.append({"type": block_type, "title": title, "payload": payload})
    return legacy

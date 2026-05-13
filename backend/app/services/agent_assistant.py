from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.orchestrator.agent_orchestrator import AgentOrchestrator
from app.ai.schemas.chat_schemas import ChatAgentResponse
from app.models.chat import ChatMessage, ChatSession
from app.models.mixins import current_utc
from app.models.user import User


def generate_agent_chat_reply(
    db: Session,
    *,
    current_user: User,
    message: str,
    conversation_id: str | None = None,
    user_id: str | None = None,
    language: str | None = "fr",
) -> ChatAgentResponse:
    session = _resolve_or_create_session(db, current_user=current_user, conversation_id=conversation_id, seed_text=message)

    try:
        db.add(ChatMessage(session_id=session.id, role="user", content=message))
        db.flush()

        orchestrator = AgentOrchestrator(db, current_user)
        response = asyncio.run(
            orchestrator.handle(
                message=message,
                language=language,
                conversation_id=str(session.id),
                user_id=user_id,
            )
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
    except Exception:
        db.rollback()
        raise

    payload = response.model_dump()
    payload["metadata"] = {**payload.get("metadata", {}), "conversation_id": str(session.id)}
    return ChatAgentResponse(**payload)


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

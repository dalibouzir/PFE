from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.agents.base_agent import BaseAgent
from app.ai.orchestrator.entity_extractor import EntityExtractor
from app.ai.schemas.agent_schemas import AgentContext, AgentResult
from app.models.batch import Batch
from app.models.chat import ChatMessage
from app.models.user import User

STAGE_PATTERN = re.compile(r"\b(cleaning|drying|sorting|packaging|nettoyage|séchage|sechage|tri|emballage)\b", re.IGNORECASE)
PRODUCT_PATTERN = re.compile(r"\b(mango|mangue|peanut|arachide|millet|mil)\b", re.IGNORECASE)
REFERENCE_PRONOUN_PATTERN = re.compile(
    r"\b(ce lot|celui-ci|celui ci|ces risques|ce risque|cette étape|cette etape|ceux-ci|cela)\b",
    re.IGNORECASE,
)


class MemoryAgent(BaseAgent):
    name = "MemoryAgent"
    description = "Maintains conversational references without overriding factual evidence."

    def __init__(self, db: Session, current_user: User | None = None):
        self.db = db
        self.current_user = current_user
        self.entity_extractor = EntityExtractor()

    async def run(self, query: str, context: AgentContext) -> AgentResult:
        if not context.conversation_id:
            return AgentResult(
                agent_name=self.name,
                route=context.route,
                answer_part="",
                data={"entities": context.detected_entities},
                confidence=0.5,
                execution_time_ms=1,
            )

        previous = self.get_recent_conversation_context(context.conversation_id)
        previous_entities = self.extract_last_entities_from_history(previous, current_query=query)
        should_reuse = self.should_reuse_context(query=query, current_entities=context.detected_entities, previous_entities=previous_entities)
        merged = self.merge_entities(context.detected_entities, previous_entities) if should_reuse else dict(context.detected_entities or {})
        return AgentResult(
            agent_name=self.name,
            route=context.route,
            answer_part="",
            data={
                "entities": merged,
                "history_count": len(previous),
                "memory_reused": should_reuse,
            },
            confidence=0.72 if previous and should_reuse else 0.45,
            execution_time_ms=3,
        )

    def get_recent_conversation_context(self, conversation_id: str, limit: int = 12) -> list[dict]:
        try:
            session_id = UUID(str(conversation_id))
        except ValueError:
            return []
        rows = self.db.execute(
            select(ChatMessage.role, ChatMessage.content)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        ).all()
        return [{"role": str(role), "content": str(content)} for role, content in rows]

    def extract_last_entities_from_history(self, history: list[dict], *, current_query: str) -> dict:
        entities: dict = {}
        known_refs = self._known_batch_refs()
        skipped_current = False
        for item in history:
            role = str(item.get("role") or "")
            content = str(item.get("content") or "")

            if not skipped_current and role == "user" and content.strip() == str(current_query or "").strip():
                skipped_current = True
                continue

            if role != "user":
                continue

            extracted = self.entity_extractor.extract(content, known_batch_refs=known_refs)
            extracted_dict = extracted.as_dict()
            if extracted_dict.get("scope") and "scope" not in entities:
                entities["scope"] = extracted_dict.get("scope")
            if extracted_dict.get("module") and "module" not in entities:
                entities["module"] = extracted_dict.get("module")
            if extracted.batch_ref and "batch_ref" not in entities:
                entities["batch_ref"] = extracted.batch_ref

            stage_match = STAGE_PATTERN.search(content)
            if stage_match and "stage" not in entities:
                entities["stage"] = [stage_match.group(1).lower()]

            product_match = PRODUCT_PATTERN.search(content)
            if product_match and "product" not in entities:
                token = product_match.group(1).lower()
                entities["product"] = ["mango" if token in {"mangue", "mango"} else "peanut" if token in {"peanut", "arachide"} else "millet"]

            if len(entities) >= 5:
                break
        return entities

    def should_reuse_context(self, *, query: str, current_entities: dict, previous_entities: dict) -> bool:
        if not previous_entities:
            return False
        lowered = str(query or "").lower()
        if REFERENCE_PRONOUN_PATTERN.search(lowered):
            return True

        current_scope = str((current_entities or {}).get("scope") or "")
        previous_scope = str((previous_entities or {}).get("scope") or "")
        current_module = str((current_entities or {}).get("module") or "")
        previous_module = str((previous_entities or {}).get("module") or "")

        if current_scope and previous_scope and current_scope != previous_scope:
            return False
        if current_module and previous_module and current_module != previous_module:
            return False

        # Reuse only when current turn is underspecified.
        has_explicit_entity = bool(
            (current_entities or {}).get("batch_ref")
            or (current_entities or {}).get("member_name")
            or (current_entities or {}).get("product")
            or (current_entities or {}).get("stage")
        )
        return not has_explicit_entity

    def merge_entities(self, current_entities: dict, previous_entities: dict) -> dict:
        merged = dict(previous_entities)
        for key, value in (current_entities or {}).items():
            if value in (None, "", [], {}):
                continue
            merged[key] = value
        return merged

    def _known_batch_refs(self) -> set[str]:
        try:
            stmt = select(Batch.code)
            if self.current_user is not None and self.current_user.cooperative_id is not None:
                stmt = stmt.where(Batch.cooperative_id == self.current_user.cooperative_id)
            rows = self.db.scalars(stmt).all()
        except Exception:
            return set()
        return {str(row).upper() for row in rows if str(row or "").strip()}

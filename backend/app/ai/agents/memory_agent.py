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
    r"\b(ce lot|ce produit|ce producteur|celui-ci|celui ci|ces risques|ce risque|cette étape|cette etape|ceux-ci|cela|et celui-ci|et celui ci|le premier)\b",
    re.IGNORECASE,
)
AMBIGUOUS_LOT_REFERENCE_PATTERN = re.compile(
    r"\b(celui-ci|celui ci|celui-là|celui la|ce lot|ceci|sa perte|ses pertes|le precedent|le précédent|ce meme lot|ce même lot)\b",
    re.IGNORECASE,
)
FOLLOWUP_PRODUCT_PATTERN = re.compile(
    r"^(?:et\s+)?pour\s+(?:la|le|les|l')?\s*(mangue|mango|arachide|peanut|mil|millet|bissap)\b",
    re.IGNORECASE,
)
RESET_CONTEXT_PATTERN = re.compile(
    r"\b(autre sujet|changeons de sujet|sans rapport|indépendamment|independamment|nouvelle question|hors sujet|oublie ce lot|oublier ce lot|maintenant oublie|maintenant|passons|météo|meteo|football|nba|crypto|bitcoin|film)\b",
    re.IGNORECASE,
)
SMALL_TALK_PATTERN = re.compile(r"^(bonjour|salut|hello|hi|bonsoir|ok|merci|coucou|ca va|ça va)\b", re.IGNORECASE)


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
        if self._is_combined_reset_and_ambiguous_lot_query(query):
            # Reset + ambiguous lot reference in the same user turn must never reuse stale lot context.
            sanitized_entities = dict(context.detected_entities or {})
            sanitized_entities.pop("batch_ref", None)
            sanitized_entities.pop("batch_ref_candidate", None)
            sanitized_entities["needs_batch_clarification"] = True
            return AgentResult(
                agent_name=self.name,
                route=context.route,
                answer_part="",
                data={
                    "entities": sanitized_entities,
                    "history_count": len(previous),
                    "memory_reused": False,
                },
                confidence=0.78,
                execution_time_ms=3,
            )
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

            extracted = self.entity_extractor.extract(content, known_batch_refs=known_refs)
            extracted_dict = extracted.as_dict()
            if role == "user" and extracted_dict.get("scope") and "scope" not in entities:
                entities["scope"] = extracted_dict.get("scope")
            if role == "user" and extracted_dict.get("module") and "module" not in entities:
                entities["module"] = extracted_dict.get("module")
            if extracted.batch_ref and "batch_ref" not in entities:
                entities["batch_ref"] = extracted.batch_ref

            stage_match = STAGE_PATTERN.search(content)
            if role == "user" and stage_match and "stage" not in entities:
                entities["stage"] = [stage_match.group(1).lower()]

            product_match = PRODUCT_PATTERN.search(content)
            if role == "user" and product_match and "product" not in entities:
                token = product_match.group(1).lower()
                entities["product"] = ["mango" if token in {"mangue", "mango"} else "peanut" if token in {"peanut", "arachide"} else "millet"]

            if len(entities) >= 5:
                break
        return entities

    def should_reuse_context(self, *, query: str, current_entities: dict, previous_entities: dict) -> bool:
        if not previous_entities:
            return False
        lowered = str(query or "").lower().strip()
        if SMALL_TALK_PATTERN.search(lowered):
            return False
        if RESET_CONTEXT_PATTERN.search(lowered):
            return False
        if REFERENCE_PRONOUN_PATTERN.search(lowered):
            return True
        if FOLLOWUP_PRODUCT_PATTERN.search(lowered):
            return True

        current_scope = str((current_entities or {}).get("scope") or "")
        previous_scope = str((previous_entities or {}).get("scope") or "")
        current_module = str((current_entities or {}).get("module") or "")
        previous_module = str((previous_entities or {}).get("module") or "")

        if current_scope and previous_scope and current_scope != "global" and previous_scope != "global" and current_scope != previous_scope:
            return False
        if current_module and previous_module and current_module != "global" and previous_module != "global" and current_module != previous_module:
            return False

        # Reuse only on explicit follow-up markers.
        has_explicit_entity = bool(
            (current_entities or {}).get("batch_ref")
            or (current_entities or {}).get("member_name")
            or (current_entities or {}).get("stage")
        )
        has_only_product = bool((current_entities or {}).get("product")) and not has_explicit_entity
        if has_only_product and lowered.startswith(("pour ", "et pour ")):
            return True
        return False

    def merge_entities(self, current_entities: dict, previous_entities: dict) -> dict:
        merged = dict(previous_entities)
        previous_product = tuple(previous_entities.get("product") or [])
        current_product = tuple((current_entities or {}).get("product") or [])
        if current_product and previous_product and current_product != previous_product:
            merged.pop("batch_ref", None)
            merged.pop("batch_ref_candidate", None)
            merged["scope"] = "post_harvest"
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

    def _is_combined_reset_and_ambiguous_lot_query(self, query: str) -> bool:
        lowered = str(query or "").lower().strip()
        return bool(RESET_CONTEXT_PATTERN.search(lowered) and AMBIGUOUS_LOT_REFERENCE_PATTERN.search(lowered))

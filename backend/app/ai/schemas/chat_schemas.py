from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.ai.schemas.agent_schemas import FinalAgentResponse


class ChatAgentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    language: Optional[str] = "fr"


class ChatAgentResponse(FinalAgentResponse):
    pass

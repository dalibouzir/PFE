import sys
import os
import asyncio
from pydantic import BaseModel
from typing import Optional

# Setup path
sys.path.insert(0, '/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend')

from app.core.config import settings
from app.db.session import SessionLocal
from app.ai.orchestrator.agent_registry import AgentRegistry
from app.ai.orchestrator.agent_orchestrator import AgentOrchestrator

class MockUser(BaseModel):
    id: str = "test-user"
    email: str = "test@example.com"
    role: str = "admin"
    cooperative_id: Optional[int] = 1

async def debug():
    # SessionLocal is synchronous in this project
    session = SessionLocal()
    try:
        mock_user = MockUser()
        registry = AgentRegistry(db=session, current_user=mock_user)
        orchestrator = AgentOrchestrator(registry, current_user=mock_user)
        
        question = "Quelle est la sitation du LOT-MANG-001"
        result = await orchestrator.handle(
            message=question,
            conversation_id=None
        )
        
        print(f"Question: {question}")
        print(f"Route: {result.decision.route}")
        print(f"\n=== FULL ANSWER ===")
        print(result.answer)
        print(f"\n=== ANSWER LENGTH ===")
        print(len(result.answer))
        
        # Check for fallback phrases
        fallback_phrases = [
            "données indisponibles",
            "no data",
            "aucune donnée",
            "je ne peux pas",
            "unable to find",
            "pas de données",
        ]
        for phrase in fallback_phrases:
            if phrase.lower() in result.answer.lower():
                print(f"Found fallback: {phrase}")
    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(debug())

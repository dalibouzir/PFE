#!/usr/bin/env python3
"""
Quick Groq LLM + RAG Integration Test
Tests 5 sample RAG questions to verify Groq works with knowledge base.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.models.enums import UserRole, UserStatus
from app.ai.orchestrator.agent_orchestrator import AgentOrchestrator
from uuid import UUID
from datetime import datetime

# Sample questions for RAG testing
TEST_QUESTIONS = [
    "Quels sont les meilleurs conseils pour sécher correctement les mangues?",
    "Comment prévenir les pertes post-récolte dans les produits agricoles?",
    "Quelles sont les étapes importantes de tri pour le mil?",
    "Comment doit-on stocker l'arachide pour conserver sa qualité?",
    "Quelles sont les bonnes pratiques de conditionnement des fruits?",
]

async def test_rag_with_groq():
    """Test RAG + Groq with sample questions."""
    print("\n" + "=" * 70)
    print("GROQ + RAG INTEGRATION TEST")
    print("=" * 70)
    
    # Get database session
    db = next(get_db())
    
    # Create a test user for manager context
    test_user = User(
        id=UUID("12345678-1234-1234-1234-123456789012"),
        full_name="Test Manager",
        email="test@weefarm.local",
        password_hash="",
        cooperative_id=UUID("4cbc6020-def9-4d24-bb75-9d40bc031466"),
        role=UserRole.MANAGER,
        status=UserStatus.ACTIVE,
    )
    
    # Initialize orchestrator
    orchestrator = AgentOrchestrator(db=db, current_user=test_user)
    
    results = {
        "total": len(TEST_QUESTIONS),
        "passed": 0,
        "failed": 0,
        "errors": []
    }
    
    for i, question in enumerate(TEST_QUESTIONS, 1):
        print(f"\n{i}. Testing: {question[:60]}...")
        try:
            response = await orchestrator.handle(
                message=question,
                language="fr",
                conversation_id=None,
                user_id=None
            )
            
            # Check response quality
            answer_text = response.answer.strip()
            has_sources = len(response.sources) > 0
            
            if answer_text and "Le fournisseur LLM est indisponible" not in answer_text:
                print(f"   ✅ PASS")
                print(f"      Route: {response.route}")
                print(f"      Answer: {answer_text[:80]}...")
                print(f"      Sources: {len(response.sources)} found")
                results["passed"] += 1
            else:
                print(f"   ❌ FAIL")
                if "Le fournisseur LLM est indisponible" in answer_text:
                    print(f"      LLM unavailable (this should not happen with Groq)")
                else:
                    print(f"      Empty response")
                results["failed"] += 1
                results["errors"].append({
                    "question": question,
                    "error": answer_text[:100] if answer_text else "No response"
                })
        except Exception as e:
            print(f"   ❌ ERROR: {str(e)[:80]}")
            results["failed"] += 1
            results["errors"].append({
                "question": question,
                "error": str(e)[:100]
            })
    
    # Summary
    print("\n" + "=" * 70)
    print(f"RESULTS: {results['passed']}/{results['total']} PASSED")
    print("=" * 70)
    
    if results["errors"]:
        print("\nErrors:")
        for err in results["errors"]:
            print(f"  - {err['question'][:50]}: {err['error']}")
    
    return results["passed"] >= 3  # At least 3 out of 5 should pass


if __name__ == "__main__":
    success = asyncio.run(test_rag_with_groq())
    sys.exit(0 if success else 1)

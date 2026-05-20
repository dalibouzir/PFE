#!/usr/bin/env python3
"""
Quick test of the 6 user questions to verify fixes.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
from app.ai.agents.sql_analytics_agent import SQLAnalyticsAgent
from app.ai.tools.sql_tools import SQLTools
from app.db.session import SessionLocal
from app.models.user import User
from app.ai.schemas.agent_schemas import AgentContext

# Get a test user/cooperative
db = SessionLocal()
test_user = db.query(User).filter(User.cooperative_id.isnot(None)).first()

if not test_user:
    print("❌ No test user found")
    sys.exit(1)

print(f"✅ Test User: {test_user.email}, Cooperative: {test_user.cooperative_id}\n")

sql_tools = SQLTools(db, test_user)
agent = SQLAnalyticsAgent(sql_tools)

# Test questions
test_questions = [
    "Quel est le stock actuel par produit ?",
    "Quels sont les lots post-récolte disponibles dans cette coopérative ?",
    "Quels lots ont les pertes les plus élevées ?",
    "Quels lots ont le plus grand écart entre entrée et sortie ?",
    "Quelles sont les étapes pré-récolte enregistrées ?",
    "Quelles bonnes pratiques appliquer avant l'emballage ?",
]

async def test_questions_async():
    print("=" * 120)
    print("TESTING THE 6 USER QUESTIONS")
    print("=" * 120)
    
    for idx, query in enumerate(test_questions, 1):
        print(f"\n[Q{idx}] {query}")
        print("-" * 120)
        
        try:
            context = AgentContext(
                query=query,
                route="SQL_ONLY",  # Will be determined by routing
                detected_entities={},
            )
            
            result = await agent.run(query, context)
            
            # Check if we got data
            if result.answer_part:
                print(f"✅ Answer generated: {result.answer_part[:200]}...")
            else:
                print(f"⚠️  No answer part")
            
            # Check payload
            payload_keys = list(result.data.keys())
            print(f"📊 Payload keys: {', '.join(payload_keys[:5])}")
            
            # Check for specific data based on question
            if "current_stock" in result.data and result.data["current_stock"]:
                print(f"   Stock items: {len(result.data['current_stock'])}")
            
            if "available_postharvest_lots" in result.data and result.data["available_postharvest_lots"]:
                print(f"   Available post-harvest lots: {len(result.data['available_postharvest_lots'])}")
                for lot in result.data["available_postharvest_lots"][:2]:
                    print(f"      - {lot.get('batch_ref')}: {lot.get('product')}")
            
            if "batch_summary" in result.data and result.data["batch_summary"]:
                print(f"   Batch summary items: {len(result.data['batch_summary'])}")
            
            if "process_step_losses" in result.data and result.data["process_step_losses"]:
                print(f"   Process losses: {len(result.data['process_step_losses'])}")
            
            if "parcel_status" in result.data and result.data["parcel_status"]:
                print(f"   Parcel status: {result.data['parcel_status']}")
            
            print(f"✅ Confidence: {result.confidence:.1%}")
            print(f"📍 Route: {result.route}")
            print(f"⚠️  Warnings: {', '.join(result.warnings) if result.warnings else 'None'}")
            
        except Exception as e:
            print(f"❌ ERROR: {str(e)[:200]}")
            import traceback
            traceback.print_exc()

# Run the async test
asyncio.run(test_questions_async())

db.close()

print("\n" + "=" * 120)
print("TEST COMPLETE")
print("=" * 120)

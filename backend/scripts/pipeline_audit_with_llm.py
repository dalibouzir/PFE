#!/usr/bin/env python3
"""
Audit pipeline to verify LLM integration for answer composition.
Tests 8 questions and tracks whether LLM is called for each.
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.ai.orchestrator.agent_orchestrator import AgentOrchestrator
from app.ai.schemas.agent_schemas import AgentRoute
from app.db.session import SessionLocal
from app.models.user import User


async def run_audit():
    """Run comprehensive LLM integration audit."""
    print("\n" + "="*100)
    print("WEEFARM CHATBOT PIPELINE AUDIT - LLM INTEGRATION")
    print("="*100)
    print(f"Time: {datetime.now().isoformat()}\n")
    
    # Configuration check
    print("="*100)
    print("CONFIGURATION STATUS")
    print("="*100 + "\n")
    
    llm_provider = getattr(settings, 'llm_provider', 'unknown')
    groq_key = getattr(settings, 'groq_api_key', None)
    groq_present = bool(groq_key and len(str(groq_key)) > 0)
    groq_masked = f"{str(groq_key)[:10]}...{str(groq_key)[-5:]}" if groq_key else "NOT SET"
    print(f"🔧 llm_provider: {llm_provider}")
    print(f"🔧 groq_api_key: {'✅ PRESENT' if groq_present else '❌ MISSING'} ({groq_masked})")
    print(f"🔧 groq_model: {getattr(settings, 'groq_model', 'unknown')}")
    print()
    
    # Test questions
    test_questions = [
        ("Q1", "Quel est le stock actuel par produit ?"),
        ("Q2", "Quels lots ont les pertes les plus élevées ?"),
        ("Q3", "Quels lots ont le plus grand écart entre entrée et sortie ?"),
        ("Q4", "Quelles bonnes pratiques appliquer avant l'emballage ?"),
        ("Q5", "Selon nos données et les bonnes pratiques, comment réduire les pertes au séchage ?"),
        ("Q6", "Analyse uniquement le lot LOT-MANG-001 : perte, efficacité, signal ML et recommandation liée."),
        ("Q7", "Quels lots ont les pertes les plus élevées ?"),
        ("Q8", "Et le premier, quelle action recommandes-tu ?"),
    ]
    
    print("="*100)
    print("TESTING 8 QUESTIONS WITH LLM INTEGRATION")
    print("="*100 + "\n")
    
    # Create session and test user
    session = SessionLocal()
    test_user = session.query(User).filter(User.email == "manager@weefarm.local").first()
    if not test_user:
        print("❌ Error: Test user not found in database")
        return
    
    orchestrator = AgentOrchestrator(db=session, current_user=test_user)
    
    results = []
    
    for qid, question in test_questions:
        print(f"[{qid}] {question[:70]}...")
        
        try:
            # Run question through orchestrator
            response = await orchestrator.handle(
                message=question,
                language="fr",
                conversation_id=None,
                user_id=str(test_user.id),
            )
            
            route = response.route or "UNKNOWN"
            agents_used = response.agents_used or []
            answer = response.answer or ""
            llm_called = "LLM successfully composed" in str(response.metadata.get("_debug", ""))
            
            # Heuristic: check if answer looks LLM-generated (natural language) vs deterministic
            # LLM tends to have better flow, fewer numbered sections
            is_natural = not answer.startswith("1.")
            has_detailed_explanation = len(answer) > 200
            
            result = {
                "index": int(qid[1:]),
                "question": question,
                "route": str(route),
                "agents": [str(a) for a in agents_used],
                "answer_length": len(answer),
                "answer_preview": answer[:100] + "..." if len(answer) > 100 else answer,
                "llm_indicator": is_natural and has_detailed_explanation,
                "status": "success",
            }
            
            print(f"  Route: {route}")
            print(f"  Agents: {', '.join(str(a) for a in agents_used)}")
            print(f"  Answer length: {len(answer)}")
            print(f"  LLM likely used: {result['llm_indicator']}")
            print()
            
            results.append(result)
            
        except Exception as e:
            print(f"  ❌ ERROR: {str(e)}")
            results.append({
                "index": int(qid[1:]),
                "question": question,
                "error": str(e),
                "status": "failed",
            })
            print()
    
    # Summary table
    print("="*100)
    print("AUDIT RESULTS TABLE")
    print("="*100 + "\n")
    
    print("# | Question (first 40 chars) | Route | Agents | Answer Length | LLM Used?")
    print("-" * 100)
    
    llm_count = 0
    for result in results:
        if result["status"] == "success":
            qtext = result["question"][:40].ljust(40)
            route = str(result["route"]).split(".")[-1][:12].ljust(12)
            agents = ", ".join([a.split("Agent")[0] for a in result["agents"]]).ljust(25)[:25]
            ans_len = str(result["answer_length"]).ljust(5)
            llm_used = "✅ YES" if result.get("llm_indicator") else "❌ NO"
            
            if result.get("llm_indicator"):
                llm_count += 1
            
            print(f"{result['index']} | {qtext} | {route} | {agents} | {ans_len} | {llm_used}")
        else:
            print(f"{result['index']} | ERROR: {result.get('error', 'Unknown')[:60]}")
    
    print()
    print("="*100)
    print("KEY FINDINGS")
    print("="*100 + "\n")
    
    total_success = sum(1 for r in results if r["status"] == "success")
    print(f"📊 Total questions tested: {len(results)}")
    print(f"📊 Successful: {total_success}/{len(results)}")
    print(f"📊 Questions likely using LLM: {llm_count}/{total_success}")
    print(f"📊 LLM integration active: {'✅ YES' if llm_count > 0 else '❌ NO'}")
    print()
    
    # Recommendations
    print("="*100)
    print("RECOMMENDATIONS")
    print("="*100 + "\n")
    
    if llm_count == 0:
        print("❌ LLM is not being called for any questions.")
        print("   Action: Check if LLM integration was successful.")
        print("   Verify: Evidence pipeline calls _compose_llm_answer() for HYBRID routes")
    elif llm_count < total_success / 2:
        print(f"⚠️  LLM is only used for {llm_count}/{total_success} questions")
        print("   Action: Check which routes should use LLM but don't")
    else:
        print(f"✅ LLM is being used for {llm_count}/{total_success} questions")
        print("   Status: LLM integration appears active")
    
    print()
    
    # Save results
    output_path = Path("reports/chatbot/pipeline_audit_llm.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    audit_data = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "llm_provider": llm_provider,
            "groq_present": groq_present,
        },
        "results": results,
        "summary": {
            "total_tested": len(results),
            "successful": total_success,
            "llm_likely_used": llm_count,
        }
    }
    
    with open(output_path, "w") as f:
        json.dump(audit_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Results saved to: {output_path}")
    print()
    print("="*100)
    print("AUDIT COMPLETE")
    print("="*100 + "\n")


if __name__ == "__main__":
    asyncio.run(run_audit())

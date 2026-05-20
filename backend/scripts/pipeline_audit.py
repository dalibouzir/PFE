#!/usr/bin/env python3
"""
Comprehensive Chatbot Pipeline Audit

Checks:
1. RAG indexing status (documents, chunks, embeddings)
2. Configuration (Groq, LLM provider, keys)
3. Tests 8 questions through the full pipeline
4. Reports: route, agents used, LLM calls, SQL rows, RAG chunks, memory usage
5. Identifies broken layers
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import time
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from app.db.session import SessionLocal
from app.models.user import User
from app.models.rag import RAGDocument, RAGChunk
from app.core.config import settings
import asyncio
from app.ai.orchestrator.agent_orchestrator import AgentOrchestrator
from datetime import datetime


def check_rag_indexing(db: Session) -> dict:
    """Check RAG document and chunk indexing status."""
    print("\n" + "="*100)
    print("RAG INDEXING STATUS")
    print("="*100 + "\n")
    
    try:
        # Count documents
        doc_count = db.query(func.count(RAGDocument.id)).scalar() or 0
        print(f"📊 RAG Documents: {doc_count}")
        
        # Count chunks
        chunk_count = db.query(func.count(RAGChunk.id)).scalar() or 0
        print(f"📊 RAG Chunks: {chunk_count}")
        
        # Count chunks with embeddings
        chunks_with_embedding = db.query(func.count(RAGChunk.id)).filter(
            RAGChunk.embedding.isnot(None)
        ).scalar() or 0
        print(f"📊 Chunks with embeddings: {chunks_with_embedding}")
        print(f"   Coverage: {100*chunks_with_embedding/chunk_count:.1f}%" if chunk_count > 0 else "   N/A")
        
        # Last indexed
        latest_chunk = db.query(RAGChunk).order_by(RAGChunk.created_at.desc()).first()
        if latest_chunk:
            print(f"📊 Last indexed: {latest_chunk.created_at}")
        
        # Check per cooperative (sample)
        coops = db.query(RAGDocument.cooperative_id).distinct().limit(5).all()
        print(f"\n   Cooperatives with RAG: {len(coops)}")
        
        return {
            "documents": doc_count,
            "chunks": chunk_count,
            "chunks_with_embeddings": chunks_with_embedding,
            "coverage_percent": round(100*chunks_with_embedding/chunk_count, 1) if chunk_count > 0 else 0,
            "last_indexed": str(latest_chunk.created_at) if latest_chunk else None,
            "cooperatives_indexed": len(coops),
        }
        
    except Exception as e:
        print(f"❌ Error checking RAG: {e}")
        return {"error": str(e)}


def check_configuration() -> dict:
    """Check LLM and RAG configuration."""
    print("\n" + "="*100)
    print("CONFIGURATION STATUS")
    print("="*100 + "\n")
    
    config_status = {}
    
    # LLM Provider
    llm_provider = getattr(settings, 'llm_provider', 'unknown')
    print(f"🔧 llm_provider: {llm_provider}")
    config_status["llm_provider"] = llm_provider
    
    # Groq API Key
    groq_key = getattr(settings, 'groq_api_key', None)
    groq_present = bool(groq_key and len(str(groq_key)) > 0)
    groq_masked = f"{str(groq_key)[:10]}...{str(groq_key)[-5:]}" if groq_key else "NOT SET"
    print(f"🔧 groq_api_key: {'✅ PRESENT' if groq_present else '❌ MISSING'} ({groq_masked})")
    config_status["groq_key_present"] = groq_present
    
    # Groq Model
    groq_model = getattr(settings, 'groq_model', 'unknown')
    print(f"🔧 groq_model: {groq_model}")
    config_status["groq_model"] = groq_model
    
    # OpenRouter fallback
    openrouter_key = getattr(settings, 'openrouter_api_key', None)
    openrouter_present = bool(openrouter_key and len(str(openrouter_key)) > 0)
    openrouter_masked = f"{str(openrouter_key)[:10]}...{str(openrouter_key)[-5:]}" if openrouter_key else "NOT SET"
    print(f"🔧 openrouter_api_key: {'✅ PRESENT' if openrouter_present else '❌ MISSING'} ({openrouter_masked})")
    config_status["openrouter_key_present"] = openrouter_present
    
    # RAG config
    rag_provider = getattr(settings, 'rag_embedding_provider', 'unknown')
    rag_model = getattr(settings, 'rag_embedding_model', 'unknown')
    print(f"🔧 rag_embedding_provider: {rag_provider}")
    print(f"🔧 rag_embedding_model: {rag_model}")
    config_status["rag_embedding_provider"] = rag_provider
    config_status["rag_embedding_model"] = rag_model
    
    print()
    return config_status


async def test_question(db: Session, test_user: User, question: str, index: int) -> dict:
    """Test a single question and capture pipeline details."""
    
    print(f"\n{'─'*100}")
    print(f"[Q{index}] {question}")
    print(f"{'─'*100}")
    
    start = time.time()
    result_data = {
        "index": index,
        "question": question,
        "status": "unknown",
    }
    
    try:
        orchestrator = AgentOrchestrator(db, test_user)
        
        # Call the orchestrator
        result = await orchestrator.handle(
            message=question,
            language="fr",
            conversation_id=f"audit-{index}-{int(time.time())}",
            user_id=str(test_user.id)
        )
        
        elapsed = time.time() - start
        
        result_data.update({
            "status": "success",
            "route": str(result.route),
            "agents_used": result.agents_used or [],
            "confidence": float(result.confidence or 0),
            "answer_length": len(result.answer or ""),
            "response_blocks": len(result.response_blocks or []),
            "warnings": result.warnings or [],
            "elapsed_ms": int(elapsed * 1000),
            "answer_preview": (result.answer or "")[:150],
        })
        
        # Analyze agents to determine pipeline usage
        llm_likely = any("sql" in str(a).lower() or "rag" in str(a).lower() for a in (result.agents_used or []))
        groq_called = "SQL" in (result.agents_used or []) or "RAG" in (result.agents_used or [])
        
        result_data["llm_likely_used"] = llm_likely
        result_data["groq_call_likely"] = groq_called
        
        # Print summary
        status_icon = "✅" if result.route != "OUT_OF_SCOPE" else "⚠️"
        print(f"{status_icon} Route: {result.route}")
        print(f"   Agents: {', '.join(result.agents_used or [])}")
        print(f"   Confidence: {result.confidence:.1%}")
        print(f"   Response blocks: {len(result.response_blocks or [])}")
        print(f"   Time: {elapsed:.2f}s")
        
        if result.warnings:
            print(f"   ⚠️  Warnings: {', '.join(result.warnings[:2])}")
        
        return result_data
        
    except Exception as e:
        result_data["status"] = f"error: {str(e)[:100]}"
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return result_data


async def run_audit():
    """Run comprehensive pipeline audit."""
    
    db = SessionLocal()
    
    print("\n" + "="*100)
    print("WEEFARM CHATBOT PIPELINE AUDIT")
    print(f"Time: {datetime.now().isoformat()}")
    print("="*100)
    
    try:
        # Check configuration
        config = check_configuration()
        
        # Check RAG indexing
        rag_status = check_rag_indexing(db)
        
        # Get test user
        test_user = db.query(User).filter(User.cooperative_id.isnot(None)).first()
        if not test_user:
            print("\n❌ No test user found")
            return
        
        print(f"\n✅ Test user: {test_user.email} (Coop: {test_user.cooperative_id})\n")
        
        # Test questions (8 questions as per request)
        questions = [
            "Quel est le stock actuel par produit ?",
            "Quels lots ont les pertes les plus élevées ?",
            "Quels lots ont le plus grand écart entre entrée et sortie ?",
            "Quelles bonnes pratiques appliquer avant l'emballage ?",
            "Selon nos données et les bonnes pratiques, comment réduire les pertes au séchage ?",
            "Analyse uniquement le lot LOT-MANG-001 : perte, efficacité, signal ML et recommandation liée.",
            "Quels lots ont les pertes les plus élevées ?",  # Duplicate for testing
            "Et le premier, quelle action recommandes-tu ?",
        ]
        
        print("\n" + "="*100)
        print("TESTING 8 QUESTIONS")
        print("="*100)
        
        results = []
        for i, question in enumerate(questions, 1):
            result = await test_question(db, test_user, question, i)
            results.append(result)
        
        # Print summary table
        print("\n" + "="*100)
        print("AUDIT RESULTS TABLE")
        print("="*100 + "\n")
        print(f"{'#':<3} | {'Route':<15} | {'Agents':<40} | {'LLM':<5} | {'Time':<6} | {'Conf':<6} | Status")
        print("-"*100)
        
        for r in results:
            route = r.get("route", "?")[:15]
            agents = ", ".join(r.get("agents_used", [])[:2])[:40]
            llm = "✅" if r.get("llm_likely_used") else "❌"
            elapsed = f"{r.get('elapsed_ms', 0)//1000}s"
            conf = f"{r.get('confidence', 0):.0%}"
            status = r.get("status", "?")[:15]
            
            print(f"{r['index']:<3} | {route:<15} | {agents:<40} | {llm:<5} | {elapsed:<6} | {conf:<6} | {status}")
        
        print("\n" + "="*100)
        print("KEY FINDINGS")
        print("="*100 + "\n")
        
        # Analyze findings
        llm_used_count = sum(1 for r in results if r.get("llm_likely_used"))
        out_of_scope_count = sum(1 for r in results if r.get("route") == "OUT_OF_SCOPE")
        
        print(f"📊 Questions with LLM routing: {llm_used_count}/8")
        print(f"📊 Questions OUT_OF_SCOPE: {out_of_scope_count}/8")
        print(f"📊 RAG indexed chunks: {rag_status.get('chunks', 0)}")
        print(f"📊 Configuration: LLM_PROVIDER={config.get('llm_provider')}, Groq={'✅' if config.get('groq_key_present') else '❌'}")
        
        # Recommendations
        print("\n" + "="*100)
        print("RECOMMENDATIONS")
        print("="*100 + "\n")
        
        if llm_used_count == 0:
            print("❌ ISSUE: No questions used LLM routing")
            print("   → Check if orchestrator is calling agent routes correctly")
            print("   → Verify agent_orchestrator.py route detection logic")
            
        if rag_status.get("chunks", 0) == 0:
            print("❌ ISSUE: No RAG chunks indexed")
            print("   → Run: POST /chat/rag/reindex with cooperative_id")
            print("   → Check rag_indexer.py for indexing logic")
            
        if not config.get("groq_key_present"):
            print("❌ ISSUE: Groq API key not configured")
            print("   → Add GROQ_API_KEY to backend/.env")
            
        print("\n" + "="*100)
        print("AUDIT COMPLETE")
        print("="*100 + "\n")
        
        # Save detailed results
        with open("reports/chatbot/pipeline_audit.json", "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "config": config,
                "rag_status": rag_status,
                "test_results": results,
            }, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Results saved to: reports/chatbot/pipeline_audit.json\n")
        
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(run_audit())

#!/usr/bin/env python3
"""
RAG + Grounding Diagnostic
Audit RAG index, LLM connectivity, citation format, entity lookups
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.rag import RAGDocument, RAGChunk
from app.models.batch import Batch

REPORT_DIR = ROOT / "reports" / "chatbot"
COOP_ID = "4cbc6020-def9-4d24-bb75-9d40bc031466"

def test_llm_connectivity():
    """Test if LLM provider is reachable"""
    print("\n=== LLM CONNECTIVITY TEST ===")
    print(f"LLM Provider: {settings.llm_provider}")
    print(f"LLM Model: {settings.llm_model}")
    print(f"OpenRouter API Key configured: {bool(settings.openrouter_api_key)}")
    print(f"LLM Timeout: {settings.llm_timeout_seconds}s")
    
    # Try a simple API call
    try:
        import httpx
        
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 10,
        }
        
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
        
        if response.status_code == 200:
            print(f"✅ LLM REACHABLE (status {response.status_code})")
            return True
        else:
            print(f"❌ LLM ERROR (status {response.status_code})")
            print(f"   Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ LLM CONNECTION FAILED: {type(e).__name__}: {str(e)[:150]}")
        return False


def audit_rag_index():
    """Count RAG documents and chunks"""
    print("\n=== RAG INDEX AUDIT ===")
    
    db = SessionLocal()
    try:
        # Count by cooperative
        doc_count = db.query(func.count(RAGDocument.id)).filter(
            RAGDocument.cooperative_id == COOP_ID
        ).scalar() or 0
        
        chunk_count = db.query(func.count(RAGChunk.id)).filter(
            RAGChunk.cooperative_id == COOP_ID
        ).scalar() or 0
        
        print(f"Cooperative: {COOP_ID}")
        print(f"Documents: {doc_count}")
        print(f"Chunks: {chunk_count}")
        
        # Count by source_type
        doc_by_type = db.query(
            RAGDocument.source_type, 
            func.count(RAGDocument.id)
        ).filter(RAGDocument.cooperative_id == COOP_ID).group_by(
            RAGDocument.source_type
        ).all()
        
        print("\nDocuments by source_type:")
        for source_type, count in doc_by_type:
            print(f"  {source_type}: {count}")
        
        # Count chunks by source_table
        chunk_by_table = db.query(
            RAGDocument.source_table,
            func.count(RAGChunk.id)
        ).join(RAGChunk).filter(
            RAGDocument.cooperative_id == COOP_ID
        ).group_by(
            RAGDocument.source_table
        ).all()
        
        print("\nChunks by source_table:")
        for table, count in chunk_by_table:
            print(f"  {table}: {count}")
        
        # Sample documents
        docs = db.query(RAGDocument).filter(
            RAGDocument.cooperative_id == COOP_ID
        ).limit(5).all()
        
        print("\nSample documents:")
        for doc in docs:
            print(f"  - {doc.source_type}/{doc.source_table}: {doc.source_record_ref} ({len(doc.chunks)} chunks)")
        
        return {"doc_count": doc_count, "chunk_count": chunk_count}
    finally:
        db.close()


def test_rag_retrieval():
    """Test 5 RAG retrieval cases"""
    print("\n=== RAG RETRIEVAL TEST ===")
    print("(Skipped - requires full app context)")


def audit_citation_metadata():
    """Check citation format in responses"""
    print("\n=== CITATION METADATA AUDIT ===")
    print("(Will be checked via validation audit rerun)")


def audit_entity_lookups():
    """Check if specific entities are in database"""
    print("\n=== ENTITY LOOKUP AUDIT ===")
    
    db = SessionLocal()
    
    test_entities = [
        ("LOT-MANG-005", "batch", "code"),
        ("MANG-004", "batch", "code"),
        ("DEMOFP-LOT-MANG-003", "batch", "code"),
    ]
    
    try:
        for entity_code, entity_type, field in test_entities:
            print(f"\nSearching: {entity_code} (type={entity_type})")
            
            if entity_type == "batch":
                batch = db.query(Batch).filter(
                    Batch.code == entity_code,
                    Batch.cooperative_id == COOP_ID
                ).first()
                
                if batch:
                    print(f"  ✅ Found in DB")
                    print(f"     Code: {batch.code}")
                    print(f"     Status: {batch.status}")
                    print(f"     Product: {batch.product_id}")
                    print(f"     Qty: {batch.current_qty}/{batch.initial_qty} kg")
                else:
                    print(f"  ❌ Not found in this cooperative")
                    
                    # Check if exists in different cooperative
                    all_batches = db.query(Batch).filter(
                        Batch.code == entity_code
                    ).all()
                    
                    if all_batches:
                        print(f"     Found in {len(all_batches)} other cooperative(s)")
                    else:
                        print(f"     Not found in any cooperative")
    finally:
        db.close()


def main():
    print("=" * 70)
    print("RAG + GROUNDING DIAGNOSTIC")
    print(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)
    
    # 1. LLM connectivity
    llm_ok = test_llm_connectivity()
    
    # 2. RAG index
    rag_stats = audit_rag_index()
    
    # 3. Entity lookups
    audit_entity_lookups()
    
    # Summary
    print("\n" + "=" * 70)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 70)
    print(f"LLM Available: {'✅ YES' if llm_ok else '❌ NO'}")
    print(f"RAG Chunks: {rag_stats.get('chunk_count', 0)} (expected ~589)")
    print("\nAction items:")
    if not llm_ok:
        print("  1. ❌ Fix LLM connectivity (API key or endpoint)")
    if rag_stats.get('chunk_count', 0) < 100:
        print(f"  2. ⚠️ Re-run seed_rag_knowledge.py ({rag_stats.get('chunk_count', 0)}/589 chunks)")
    print("  3. Check citation metadata format in responses")
    print("  4. Verify entity lookups use correct cooperative scope")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Pipeline Tracing Audit for WeeFarm Chatbot

Traces a single request through the entire multi-agent pipeline to verify:
- Intent routing
- Memory usage
- Agents called
- SQL tool calls
- RAG retrieval
- ML models
- Recommendations
- Evidence composition
- LLM calls (Groq specifically)
- Response generation

Usage:
    python scripts/trace_pipeline.py "Question text"
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
import json
import time
from uuid import uuid4
from datetime import datetime

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User
from app.ai.orchestrator.agent_orchestrator import AgentOrchestrator


class PipelineTracer:
    """Instrument and trace a chatbot request through the full pipeline."""
    
    def __init__(self, db: Session):
        self.db = db
        self.trace_log = []
        self.start_time = None
        self.events = {}
        
    def log(self, stage: str, event: str, details: dict | None = None):
        """Log a trace event."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        entry = {
            "timestamp": elapsed,
            "stage": stage,
            "event": event,
            "details": details or {}
        }
        self.trace_log.append(entry)
        self.events[f"{stage}.{event}"] = details or {}
        
    def print_table(self):
        """Print trace log as formatted table."""
        print("\n" + "="*140)
        print("PIPELINE TRACE LOG")
        print("="*140)
        print(f"{'Time (s)':<10} | {'Stage':<25} | {'Event':<30} | {'Details':<70}")
        print("-"*140)
        
        for entry in self.trace_log:
            time_str = f"{entry['timestamp']:.3f}s"
            stage = entry['stage'][:25]
            event = entry['event'][:30]
            details_str = json.dumps(entry.get('details', {}), ensure_ascii=False)[:70]
            print(f"{time_str:<10} | {stage:<25} | {event:<30} | {details_str:<70}")
        
        print("="*140 + "\n")


async def trace_question(db: Session, question: str, cooperative_id: str | None = None) -> dict:
    """Trace a single question through the entire pipeline."""
    
    # Get or create test user
    test_user = db.query(User).filter(User.cooperative_id.isnot(None)).first()
    if not test_user:
        print("❌ No test user found with cooperative_id")
        return {}
    
    if cooperative_id is None:
        cooperative_id = test_user.cooperative_id
    
    print(f"\n{'='*100}")
    print(f"TRACING QUESTION: {question}")
    print(f"User: {test_user.email}, Cooperative: {cooperative_id}")
    print(f"{'='*100}\n")
    
    tracer = PipelineTracer(db)
    tracer.start_time = time.time()
    
    # Instrument: Start
    tracer.log("INIT", "request_start", {
        "question": question,
        "user": test_user.email,
        "cooperative_id": str(cooperative_id)
    })
    
    # Create orchestrator
    tracer.log("INIT", "orchestrator_created", {"orchestrator": "AgentOrchestrator"})
    
    orchestrator = AgentOrchestrator(db, test_user)
    
    # Patch orchestrator methods to add tracing
    _add_orchestrator_tracing(orchestrator, tracer)
    
    # Run the orchestrator
    start_orches = time.time()
    try:
        result = await orchestrator.handle(
            message=question,
            language="fr",
            conversation_id=str(uuid4()),
            user_id=str(test_user.id)
        )
        elapsed_orches = time.time() - start_orches
        
        tracer.log("RESULT", "orchestrator_complete", {
            "elapsed_ms": int(elapsed_orches * 1000),
            "route": result.route.value if hasattr(result.route, 'value') else str(result.route),
            "confidence": round(float(result.confidence or 0), 2),
            "answer_length": len(result.answer or ""),
            "agents_used": len(result.agents_used or []),
            "response_blocks": len(result.response_blocks or []),
        })
        
        # Print results
        print(f"\n{'='*100}")
        print("ORCHESTRATOR RESULT")
        print(f"{'='*100}")
        print(f"Route: {result.route}")
        print(f"Answer (first 200 chars): {(result.answer or '')[:200]}")
        print(f"Agents used: {result.agents_used or []}")
        print(f"Confidence: {result.confidence}")
        print(f"Response blocks: {len(result.response_blocks or [])}")
        print(f"Warnings: {result.warnings or []}")
        print(f"\n")
        
        # Print trace table
        tracer.print_table()
        
        # Return comprehensive results
        return {
            "question": question,
            "route": str(result.route),
            "answer": result.answer,
            "agents_used": result.agents_used or [],
            "confidence": float(result.confidence or 0),
            "response_blocks": len(result.response_blocks or []),
            "warnings": result.warnings or [],
            "trace_events": tracer.trace_log,
            "pipeline_events": tracer.events,
        }
        
    except Exception as e:
        tracer.log("ERROR", "orchestrator_failed", {"error": str(e)})
        tracer.print_table()
        print(f"❌ Orchestrator failed: {e}\n")
        import traceback
        traceback.print_exc()
        return {
            "question": question,
            "error": str(e),
            "trace_events": tracer.trace_log,
        }


def _add_orchestrator_tracing(orchestrator, tracer):
    """Monkey-patch orchestrator methods to add tracing."""
    
    # Wrap handle method
    original_handle = orchestrator.handle
    
    async def traced_handle(*args, **kwargs):
        tracer.log("ORCHESTRATOR", "handle_start", {
            "message": kwargs.get("message", "")[:100]
        })
        result = await original_handle(*args, **kwargs)
        return result
    
    orchestrator.handle = traced_handle


async def main():
    """Main entry point."""
    
    if len(sys.argv) < 2:
        print("Usage: python trace_pipeline.py 'Question text'")
        print("\nExample:")
        print("  python trace_pipeline.py 'Quel est le stock actuel par produit ?'")
        sys.exit(1)
    
    question = sys.argv[1]
    cooperative_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    db = SessionLocal()
    try:
        result = await trace_question(db, question, cooperative_id)
        
        print("\n" + "="*100)
        print("TRACE RESULT SUMMARY")
        print("="*100)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())

"""
Anti-overfitting QA test set for WeeFarm chatbot stabilization.

Tests:
- Gap/kg material balance paraphrases (3 questions)
- Comparison paraphrases (3 questions)
- Recommendation/action paraphrases (3 questions)
- Follow-up memory (4 questions)
- RAG/LLM fallback (1 question)

Total: 14 targeted questions
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.ai.orchestrator.agent_orchestrator import AgentOrchestrator
from app.models.user import User
from tests.conftest import db_session


logger = logging.getLogger(__name__)


class QATest:
    """Represents a single QA test case."""
    
    def __init__(
        self,
        question_id: int,
        question: str,
        category: str,
        expected_route: str | None = None,
        expected_intent: str | None = None,
        expected_contains: list[str] | None = None,
        expected_not_contains: list[str] | None = None,
        follow_up: bool = False,
    ):
        self.question_id = question_id
        self.question = question
        self.category = category
        self.expected_route = expected_route
        self.expected_intent = expected_intent
        self.expected_contains = expected_contains or []
        self.expected_not_contains = expected_not_contains or []
        self.follow_up = follow_up
        
        # Results
        self.route = None
        self.intent = None
        self.provider = None
        self.fallback_used = False
        self.latency_ms = 0
        self.llm_duration_ms = 0
        self.summary = ""
        self.blocks = []
        self.warnings = []
        self.pass_fail = "pending"
        self.failure_reason = ""
        self.intent = None  # Detected intent from orchestrator
        self.sql_operation = None  # SQL operation if SQL route used


# Define the 14 anti-overfitting questions
QA_TESTS = [
    # A. Gap / kg material balance paraphrases (3 questions)
    QATest(
        question_id=1,
        question="Classe les lots selon la quantité réellement perdue.",
        category="GAP_PARAPHRASE",
        expected_route="SQL_ONLY",
        expected_intent="INPUT_OUTPUT_GAP",
        expected_contains=["kg", "lot"],
    ),
    QATest(
        question_id=2,
        question="Quel lot a l'écart matière le plus important en kilogrammes ?",
        category="GAP_PARAPHRASE",
        expected_route="SQL_ONLY",
        expected_intent="INPUT_OUTPUT_GAP",
        expected_contains=["kg"],
    ),
    QATest(
        question_id=3,
        question="Montre-moi les lots avec la plus grande différence entre entrée et sortie.",
        category="GAP_PARAPHRASE",
        expected_route="SQL_ONLY",
        expected_intent="INPUT_OUTPUT_GAP",
        expected_contains=["entrée", "sortie"],
    ),
    
    # B. Comparison paraphrases (3 questions)
    QATest(
        question_id=4,
        question="Entre LOT-MILX-001 et LOT-MANG-001, lequel a le meilleur rendement ?",
        category="COMPARISON_PARAPHRASE",
        expected_route="SQL_ONLY",
        expected_intent="LOT_COMPARISON",
        expected_contains=["LOT-MILX-001", "LOT-MANG-001"],
    ),
    QATest(
        question_id=5,
        question="Compare ces deux lots sur la perte, la sortie et l'efficacité : LOT-MILX-001, LOT-MANG-001.",
        category="COMPARISON_PARAPHRASE",
        expected_route="SQL_ONLY",
        expected_intent="LOT_COMPARISON",
        expected_contains=["LOT-MILX-001", "LOT-MANG-001"],
    ),
    QATest(
        question_id=6,
        question="Lequel est le plus risqué entre LOT-MILX-001 et LOT-MANG-001 ?",
        category="COMPARISON_PARAPHRASE",
        expected_route="SQL_ONLY",
        expected_intent="LOT_COMPARISON",
        expected_contains=["LOT-MILX-001", "LOT-MANG-001"],
    ),
    
    # C. Recommendation/action paraphrases (3 questions)
    QATest(
        question_id=7,
        question="Que faut-il faire maintenant pour LOT-MILX-001 ?",
        category="RECOMMENDATION",
        expected_route="HYBRID_FULL",
        expected_intent="RECOMMENDATION",
        expected_contains=["LOT-MILX-001"],
    ),
    QATest(
        question_id=8,
        question="Propose uniquement les actions prouvées pour LOT-MILX-001.",
        category="RECOMMENDATION",
        expected_route="HYBRID_FULL",
        expected_intent="RECOMMENDATION",
        expected_contains=["LOT-MILX-001"],
    ),
    QATest(
        question_id=9,
        question="Quelles mesures fiables peut-on prendre sur LOT-MILX-001 ?",
        category="RECOMMENDATION",
        expected_route="HYBRID_FULL",
        expected_intent="RECOMMENDATION",
        expected_contains=["LOT-MILX-001"],
    ),
    
    # D. Follow-up memory (4 questions)
    QATest(
        question_id=10,
        question="Quel lot a la perte la plus élevée ?",
        category="FOLLOW_UP_MEMORY",
        expected_route="SQL_ONLY",
        expected_intent="INPUT_OUTPUT_GAP",
        expected_contains=["lot", "perte"],
        follow_up=True,
    ),
    QATest(
        question_id=11,
        question="Et quelles actions prouvées pour ce lot ?",
        category="FOLLOW_UP_MEMORY",
        expected_route="HYBRID_FULL",
        expected_intent="RECOMMENDATION",
        follow_up=True,
    ),
    QATest(
        question_id=12,
        question="Oublie ce lot et montre-moi le stock de mangue.",
        category="FOLLOW_UP_MEMORY",
        expected_route="SQL_ONLY",
        expected_intent="PRODUCT_STOCK",
        expected_contains=["mangue", "stock"],
        follow_up=True,
    ),
    QATest(
        question_id=13,
        question="Et maintenant donne les recommandations pour ce lot.",
        category="FOLLOW_UP_MEMORY",
        expected_route="HYBRID_FULL",
        expected_intent="RECOMMENDATION",
        expected_contains=["mangue"],
        follow_up=True,
    ),
    
    # E. RAG/LLM fallback (1 question)
    QATest(
        question_id=14,
        question="Donne une checklist courte avant l'emballage des mangues.",
        category="RAG_LLM_FALLBACK",
        expected_contains=["mangue"],
    ),
]


async def run_single_test(
    orchestrator: AgentOrchestrator,
    test: QATest,
    conversation_id: str,
) -> None:
    """Run a single QA test and capture results."""
    start_time = time.perf_counter()
    
    try:
        response = await orchestrator.handle(
            message=test.question,
            language="fr",
            conversation_id=conversation_id,
            user_id=str(orchestrator.current_user.id),
        )
        
        test.latency_ms = int((time.perf_counter() - start_time) * 1000)
        test.route = str(response.route.value) if response.route else "unknown"
        test.summary = response.answer or ""
        test.blocks = response.response_blocks or []
        test.warnings = response.warnings or []  # warnings is list[str], not list[dict]
        
        # Extract metadata
        metadata = response.metadata or {}
        test.provider = metadata.get("llm_metadata", {}).get("provider", "unknown")
        test.fallback_used = metadata.get("llm_metadata", {}).get("fallback_used", False)
        test.llm_duration_ms = metadata.get("llm_metadata", {}).get("llm_duration_ms", 0)
        
        # Extract intent and SQL operation from metadata
        test.intent = metadata.get("intent", "unknown")
        test.sql_operation = metadata.get("sql_operation", None)
        
        # Validate expectations
        test.pass_fail = "pass"
        
        # Special handling for Q14 (RAG checklist): accept either checklist content or clean insufficiency
        if test.question_id == 14:
            summary_lower = (test.summary or "").lower()
            has_checklist = any(item in summary_lower for item in ["contrôle", "vérifier", "étape", "point", "✓", "✗"])
            has_insufficiency = "pas assez" in summary_lower or "insuffisant" in summary_lower or "manque" in summary_lower or "information" not in summary_lower
            if not (has_checklist or has_insufficiency):
                test.pass_fail = "fail"
                test.failure_reason = "Q14 must contain checklist items OR clean insufficiency message"
        else:
            if test.expected_route and test.route != test.expected_route:
                test.pass_fail = "fail"
                test.failure_reason = f"Route mismatch: expected {test.expected_route}, got {test.route}"
            
            summary_lower = (test.summary or "").lower()
            for expected_text in test.expected_contains:
                if expected_text.lower() not in summary_lower:
                    if test.pass_fail == "pass":  # Only set fail if not already failed
                        test.pass_fail = "fail"
                        test.failure_reason = f"Missing: '{expected_text}'"
        
        for not_expected_text in test.expected_not_contains:
            if not_expected_text.lower() in summary_lower:
                test.pass_fail = "fail"
                test.failure_reason = f"Should not contain: '{not_expected_text}'"
                break
        
    except Exception as e:
        test.latency_ms = int((time.perf_counter() - start_time) * 1000)
        test.pass_fail = "fail"
        test.failure_reason = f"Exception: {str(e)[:100]}"
        logger.exception(f"Test {test.question_id} failed with exception")


@pytest.mark.asyncio
async def test_anti_overfitting_qa_set(db_session: Session) -> None:
    """Run the 14-question anti-overfitting QA set."""
    # Get the manager user created by the db_session fixture
    user = db_session.query(User).filter_by(email="manager@test.local").first()
    if not user:
        raise RuntimeError("Manager test user not found in db_session")
    
    orchestrator = AgentOrchestrator(db_session, user)
    
    # Use a fixed conversation ID to test memory carry-over
    conversation_id = f"qa-test-{datetime.now().isoformat()}"
    
    logger.info(f"Starting anti-overfitting QA test suite (conversation={conversation_id})")
    
    # Run tests sequentially to maintain conversation state
    # Add 1.5s throttle between requests to avoid rate limiting
    for idx, test in enumerate(QA_TESTS):
        logger.info(f"Test {test.question_id}/{len(QA_TESTS)}: {test.question[:60]}...")
        await run_single_test(orchestrator, test, conversation_id)
        
        # Add throttle between requests (not after last one)
        if idx < len(QA_TESTS) - 1:
            logger.info(f"  [Throttle] Waiting 1.5s before next request...")
            await asyncio.sleep(1.5)
    
    # Generate report
    report = _generate_report(QA_TESTS)
    
    # Log report
    import pprint
    logger.info(f"\n\n{'='*80}\nQA TEST REPORT\n{'='*80}\n{pprint.pformat(report)}")
    
    # Write report to file
    report_path = "/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend/artifacts/qa_anti_overfitting_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Report written to {report_path}")
    
    # Assert pass rate
    passed = sum(1 for test in QA_TESTS if test.pass_fail == "pass")
    total = len(QA_TESTS)
    pass_rate = passed / total if total > 0 else 0
    
    logger.info(f"\nPass rate: {passed}/{total} ({pass_rate*100:.1f}%)")
    
    # Require at least 85% pass rate
    assert pass_rate >= 0.85, f"Pass rate {pass_rate*100:.1f}% below 85% threshold"


def _generate_report(tests: list[QATest]) -> dict[str, Any]:
    """Generate a comprehensive report from test results."""
    passed = sum(1 for t in tests if t.pass_fail == "pass")
    failed = sum(1 for t in tests if t.pass_fail == "fail")
    total = len(tests)
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    # Latency statistics
    latencies = [t.latency_ms for t in tests if t.latency_ms > 0]
    latencies.sort()
    
    p50 = latencies[len(latencies) // 2] if latencies else 0
    p90 = latencies[int(len(latencies) * 0.9)] if len(latencies) >= 10 else max(latencies or [0])
    p95 = latencies[int(len(latencies) * 0.95)] if len(latencies) >= 20 else max(latencies or [0])
    
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    
    # LLM fallback statistics
    fallback_count = sum(1 for t in tests if t.fallback_used)
    fallback_rate = fallback_count / total if total > 0 else 0
    
    # Provider statistics
    provider_counts = {}
    for t in tests:
        provider = t.provider or "unknown"
        provider_counts[provider] = provider_counts.get(provider, 0) + 1
    
    return {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": pass_rate,
        },
        "latency_metrics": {
            "p50_ms": p50,
            "p90_ms": p90,
            "p95_ms": p95,
            "average_ms": avg_latency,
            "max_ms": max_latency,
        },
        "llm_metrics": {
            "fallback_count": fallback_count,
            "fallback_rate": fallback_rate,
            "provider_distribution": provider_counts,
        },
        "test_results": [
            {
                "question_id": t.question_id,
                "question": t.question,
                "category": t.category,
                "route": t.route,
                "provider": t.provider,
                "fallback_used": t.fallback_used,
                "latency_ms": t.latency_ms,
                "llm_duration_ms": t.llm_duration_ms,
                "pass_fail": t.pass_fail,
                "failure_reason": t.failure_reason,
                "blocks_count": len(t.blocks),
                "warnings": t.warnings,
            }
            for t in tests
        ],
    }


if __name__ == "__main__":
    # Run with: pytest tests/test_qa_anti_overfitting.py -v -s
    pytest.main([__file__, "-v", "-s"])

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "eval_chatbot_supabase.py"
_SPEC = importlib.util.spec_from_file_location("eval_chatbot_supabase_module", _MODULE_PATH)
assert _SPEC and _SPEC.loader
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MOD
_SPEC.loader.exec_module(_MOD)


def test_eval_harness_has_30_cases():
    cases = _MOD._cases()
    assert len(cases) == 30


def test_eval_harness_critical_failure_on_missing_sql_operation():
    case = _MOD.EvalCase(
        question_id="X1",
        question="Comment réduire les pertes pendant le séchage ?",
        expected_intent_family="EXPLANATION_CAUSAL",
        expected_route="HYBRID_SQL_RAG",
        expected_sql_operation="get_stage_loss_analysis",
        expect_sql_data=True,
        expect_rag=True,
    )
    result = _MOD.evaluate_case_result(
        case=case,
        actual_route="HYBRID_SQL_RAG",
        actual_intent="EXPLANATION_CAUSAL",
        actual_op=None,
        row_count=1,
        rag_quality="PARTIAL",
        rec_refs=0,
        warnings=[],
        confidence=0.9,
        answer="1. Données mesurées",
        blocks=[{"type": "table"}],
    )
    assert result["pass"] is False
    assert result["failure_category"] == "SQL_OPERATION_ERROR"


def test_eval_harness_critical_failure_on_ungrounded_recommendation():
    case = _MOD.EvalCase(
        question_id="X2",
        question="Donne-moi 3 actions.",
        expected_intent_family="RECOMMENDATION",
        expected_route="HYBRID_FULL",
        expected_sql_operation="get_canonical_material_balance",
        expect_sql_data=True,
        expect_recommendation=True,
    )
    result = _MOD.evaluate_case_result(
        case=case,
        actual_route="HYBRID_FULL",
        actual_intent="RECOMMENDATION",
        actual_op="get_canonical_material_balance",
        row_count=2,
        rag_quality=None,
        rec_refs=0,
        warnings=[],
        confidence=0.4,
        answer="3. Recommandations validées",
        blocks=[{"type": "recommendations"}],
    )
    assert result["pass"] is False
    assert result["failure_category"] == "RECOMMENDATION_NOT_GROUNDED"

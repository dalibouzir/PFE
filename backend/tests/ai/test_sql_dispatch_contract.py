from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest

from app.ai.schemas.agent_schemas import AgentContext, AgentRoute


_MODULE_PATH = Path(__file__).resolve().parents[2] / "app" / "ai" / "agents" / "sql_analytics_agent.py"
_SPEC = importlib.util.spec_from_file_location("sql_analytics_agent_module", _MODULE_PATH)
assert _SPEC and _SPEC.loader
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
SQLAnalyticsAgent = _MOD.SQLAnalyticsAgent


class _FakePreharvest:
    def get_parcel_preharvest_status(self, product=None):
        return {"data": [{"parcel": "P1", "product": product or "mango"}], "sources": [{"type": "sql", "table": "parcels"}], "warnings": []}


class _FakeSQLTools:
    cooperative_id = "coop-1"

    def __init__(self):
        self.calls: list[str] = []
        self.preharvest = _FakePreharvest()

    def get_module_capabilities(self):
        return {}

    def get_current_stock(self, product=None):
        self.calls.append("get_current_stock")
        return {
            "items": [{"product": product or "mango", "available_stock_kg": 100.0, "unit": "kg"}],
            "sources": [{"type": "sql", "table": "stocks"}],
            "warnings": [],
        }

    def get_available_postharvest_lots(self, product=None):
        self.calls.append("get_available_postharvest_lots")
        return {
            "items": [{"batch_ref": "LOT-1", "product": product or "mango", "initial_qty": 100.0, "current_qty": 90.0, "loss_qty": 10.0, "status": "open"}],
            "sources": [{"type": "sql", "table": "batches"}],
            "warnings": [],
        }

    def get_canonical_material_balance(self, batch_ref=None, product=None):
        self.calls.append("get_canonical_material_balance")
        return {
            "items": [
                {
                    "batch_id": "b1",
                    "batch_ref": "LOT-1",
                    "product": product or "mango",
                    "input_qty": 100.0,
                    "output_qty": 80.0,
                    "gap_qty": 20.0,
                    "loss_pct": 20.0,
                    "efficiency_pct": 80.0,
                    "source_tables": ["process_steps", "batches"],
                    "validity_status": "VALID",
                }
            ],
            "sources": [{"type": "sql", "table": "process_steps,batches"}],
            "warnings": [],
        }

    def get_canonical_material_balance_for_lots(self, batch_refs):
        self.calls.append("get_canonical_material_balance_for_lots")
        refs = batch_refs or ["LOT-1", "LOT-2"]
        return {
            "items": [
                {
                    "batch_id": f"b{idx}",
                    "batch_ref": ref,
                    "product": "mango",
                    "input_qty": 100.0,
                    "output_qty": 80.0 - idx,
                    "gap_qty": 20.0 + idx,
                    "loss_pct": 20.0 + idx,
                    "efficiency_pct": 80.0 - idx,
                    "source_tables": ["process_steps", "batches"],
                    "validity_status": "VALID",
                }
                for idx, ref in enumerate(refs, start=1)
            ],
            "sources": [{"type": "sql", "table": "process_steps,batches"}],
            "warnings": [],
        }

    def get_stage_loss_analysis(self, *, batch_ref=None, product=None, stage=None):
        self.calls.append("get_stage_loss_analysis")
        return {
            "items": [
                {
                    "batch_ref": batch_ref or "LOT-1",
                    "product": product or "mango",
                    "stage_name": stage or "tri",
                    "input_qty": 27.0,
                    "output_qty": 7.0,
                    "gap_qty": 20.0,
                    "loss_pct": 74.1,
                    "efficiency_pct": 25.9,
                    "validity_status": "VALID",
                    "source_tables": ["process_steps", "batches"],
                }
            ],
            "sources": [{"type": "sql", "table": "process_steps,batches"}],
            "warnings": [],
        }


@pytest.mark.parametrize(
    ("family", "expected_call", "expected_operation", "forbidden_call"),
    [
        ("STOCK_CURRENT", "get_current_stock", "get_current_stock", "get_canonical_material_balance"),
        ("POSTHARVEST_AVAILABLE_LOTS", "get_available_postharvest_lots", "get_available_postharvest_lots", "get_canonical_material_balance"),
    ],
)
def test_contract_dispatch_uses_expected_sql_operation(family, expected_call, expected_operation, forbidden_call):
    tools = _FakeSQLTools()
    agent = SQLAnalyticsAgent(tools)
    context = AgentContext(
        user_query="q",
        route=AgentRoute.SQL_ONLY,
        detected_entities={"intent_family": family},
    )

    result = asyncio.run(agent.run("question", context))

    assert expected_call in tools.calls
    assert forbidden_call not in tools.calls
    trace = result.data.get("sql_dispatch_trace") or {}
    assert trace.get("intent_family") == family
    assert trace.get("sql_operation") == expected_operation


def test_postharvest_available_lots_never_returns_loss_ranking_block():
    tools = _FakeSQLTools()
    agent = SQLAnalyticsAgent(tools)
    context = AgentContext(
        user_query="q",
        route=AgentRoute.SQL_ONLY,
        detected_entities={"intent_family": "POSTHARVEST_AVAILABLE_LOTS"},
    )

    result = asyncio.run(agent.run("lots disponibles", context))

    assert "post-récolte" in result.answer_part
    assert "plus de pertes" not in result.answer_part.lower()


def test_loss_ranking_and_gap_share_canonical_material_balance_source():
    tools = _FakeSQLTools()
    agent = SQLAnalyticsAgent(tools)

    loss_ctx = AgentContext(user_query="q1", route=AgentRoute.SQL_ONLY, detected_entities={"intent_family": "LOSS_RANKING"})
    gap_ctx = AgentContext(user_query="q2", route=AgentRoute.SQL_ONLY, detected_entities={"intent_family": "INPUT_OUTPUT_GAP"})

    loss_res = asyncio.run(agent.run("pertes", loss_ctx))
    gap_res = asyncio.run(agent.run("ecart", gap_ctx))

    assert loss_res.data["sql_dispatch_trace"]["sql_operation"] == "get_canonical_material_balance"
    assert gap_res.data["sql_dispatch_trace"]["sql_operation"] == "get_canonical_material_balance"
    assert loss_res.data.get("material_balance", [])[0].get("loss_pct") == gap_res.data.get("material_balance", [])[0].get("loss_pct")


def test_empty_stock_returns_business_empty_state_not_technical_warning():
    class _EmptyStockTools(_FakeSQLTools):
        def get_current_stock(self, product=None):
            self.calls.append("get_current_stock")
            return {"items": [], "sources": [{"type": "sql", "table": "stocks"}], "warnings": ["NO_SQL_DATA"]}

    tools = _EmptyStockTools()
    agent = SQLAnalyticsAgent(tools)
    context = AgentContext(user_query="q", route=AgentRoute.SQL_ONLY, detected_entities={"intent_family": "STOCK_CURRENT"})

    result = asyncio.run(agent.run("stock", context))

    assert "Aucune mesure opérationnelle exploitable" in result.answer_part
    assert "NO_SQL_DATA" in result.warnings
    assert all("ERROR" not in w and "TIMEOUT" not in w for w in result.warnings)


def test_lot_comparison_dispatch_uses_explicit_operation():
    tools = _FakeSQLTools()
    agent = SQLAnalyticsAgent(tools)
    context = AgentContext(
        user_query="q",
        route=AgentRoute.SQL_ONLY,
        detected_entities={"intent_family": "LOT_COMPARISON"},
    )
    result = asyncio.run(agent.run("Compare LOT-MILX-001 et LOT-MANG-001", context))
    assert "get_canonical_material_balance_for_lots" in tools.calls
    assert result.data.get("sql_dispatch_trace", {}).get("sql_operation") == "get_canonical_material_balance_for_lots"


def test_stage_loss_analysis_dispatch_uses_explicit_operation():
    tools = _FakeSQLTools()
    agent = SQLAnalyticsAgent(tools)
    context = AgentContext(
        user_query="q",
        route=AgentRoute.SQL_ONLY,
        detected_entities={"intent_family": "STAGE_LOSS_ANALYSIS", "batch_ref": "LOT-MILX-001"},
    )
    result = asyncio.run(agent.run("A quelle étape LOT-MILX-001 perd le plus ?", context))
    assert "get_stage_loss_analysis" in tools.calls
    assert result.data.get("sql_dispatch_trace", {}).get("sql_operation") == "get_stage_loss_analysis"


def test_explanation_causal_process_advisory_dispatch_uses_stage_loss_operation():
    tools = _FakeSQLTools()
    agent = SQLAnalyticsAgent(tools)
    context = AgentContext(
        user_query="q",
        route=AgentRoute.HYBRID_SQL_RAG,
        detected_entities={"intent_family": "EXPLANATION_CAUSAL", "stage": "drying"},
    )
    result = asyncio.run(agent.run("Comment réduire les pertes pendant le séchage ?", context))
    assert "get_stage_loss_analysis" in tools.calls
    assert result.data.get("sql_dispatch_trace", {}).get("sql_operation") == "get_stage_loss_analysis"


def test_unmapped_operational_sql_fallback_is_low_confidence():
    tools = _FakeSQLTools()
    agent = SQLAnalyticsAgent(tools)
    context = AgentContext(
        user_query="q",
        route=AgentRoute.SQL_ONLY,
        detected_entities={"intent_family": "factual_sql"},
    )
    result = asyncio.run(agent.run("stock operationnel non mappe", context))
    assert "UNMAPPED_SQL_OPERATION" in result.warnings
    assert result.confidence <= 0.3
    assert "pas encore mappée" in result.answer_part

import re

from app.ai.tools.app_data_tools import AppDataTools, MISSING_MODULE_WARNING
from app.models.user import User


def _current_user(db_session):
    return db_session.query(User).first()


def _assert_standard_tool_result(result):
    assert set(result.keys()) == {"ok", "data", "sources", "warnings"}
    assert isinstance(result["ok"], bool)
    assert isinstance(result["sources"], list)
    assert isinstance(result["warnings"], list)
    for warning in result["warnings"]:
        assert isinstance(warning, str)
        assert warning
        assert not re.fullmatch(r"[A-Z0-9_]+", warning)


def test_core_app_data_tools_return_standard_schema_or_french_warning(db_session):
    tools = AppDataTools(db_session, _current_user(db_session))

    results = [
        tools.members.get_members_summary(),
        tools.preharvest.get_parcels_summary(),
        tools.preharvest.get_preharvest_alerts(),
        tools.collections.get_collections_summary(),
        tools.stocks.get_stock_summary_by_product(),
        tools.postharvest.get_batches_summary(),
        tools.postharvest.get_process_step_losses(),
        tools.material_balance.get_material_balance_summary(),
        tools.recommendations.get_top_recommendations(),
        tools.ml.get_high_risk_batches(),
        tools.rag.retrieve_material_balance_knowledge(),
    ]

    for result in results:
        _assert_standard_tool_result(result)


def test_missing_optional_module_returns_french_missing_module_warning(db_session):
    tools = AppDataTools(db_session, _current_user(db_session))

    result = tools.stocks.get_stock_movements(product="mango")

    assert result["ok"] is False
    assert result["data"] is None
    assert result["sources"] == []
    assert result["warnings"] == [MISSING_MODULE_WARNING]


def test_material_balance_tool_uses_existing_batch_data(db_session):
    tools = AppDataTools(db_session, _current_user(db_session))

    result = tools.material_balance.get_material_balance()

    _assert_standard_tool_result(result)
    assert result["ok"] is True
    assert result["data"]
    assert {"input_quantity", "output_quantity", "loss_percentage", "efficiency_percentage"} <= set(result["data"][0].keys())

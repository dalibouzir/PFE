from app.ml.recommendations.rule_engine import build_recommendation
from app.ml.utils.stage_normalization import is_known_stage, normalize_stage


def test_recommendation_mapping_high_loss_drying():
    prediction = {
        "critical_stage": "drying",
        "risk_level": "high",
        "predicted_loss_pct": 22.0,
        "is_anomalous": True,
        "top_signals": ["Stage loss above historical average"],
    }
    recommendation = build_recommendation(prediction)
    assert recommendation["issue_type"] == "high_loss"
    assert recommendation["severity"] == "high"
    assert any("drying" in action.lower() for action in recommendation["recommended_actions"])


def test_recommendation_mapping_low_risk_monitoring():
    prediction = {
        "critical_stage": "drying",
        "risk_level": "low",
        "predicted_loss_pct": 5.5,
        "is_anomalous": False,
        "top_signals": ["Batch performance within expected range"],
    }
    recommendation = build_recommendation(prediction)
    assert recommendation["issue_type"] == "monitor"
    assert recommendation["severity"] == "low"
    assert recommendation["recommended_actions"] == [
        "Continue current process",
        "Monitor upcoming batches",
        "Verify basic stage checklist compliance",
    ]


def test_recommendation_actions_do_not_leak_between_calls():
    build_recommendation(
        {
            "critical_stage": "sorting",
            "risk_level": "high",
            "predicted_loss_pct": 22.0,
            "is_anomalous": True,
            "top_signals": ["Stage loss above historical average"],
        }
    )

    recommendation = build_recommendation(
        {
            "critical_stage": "sorting",
            "risk_level": "low",
            "predicted_loss_pct": 6.0,
            "is_anomalous": False,
            "top_signals": ["Stage loss above historical average"],
        }
    )

    assert "Investigate anomaly drivers and log findings" not in recommendation["recommended_actions"]


def test_stage_normalization_bilingual_mapping():
    assert normalize_stage("Nettoyage") == "cleaning"
    assert normalize_stage("Séchage") == "drying"
    assert normalize_stage("Sechage") == "drying"
    assert normalize_stage("Tri") == "sorting"
    assert normalize_stage("Emballage") == "packaging"
    assert normalize_stage("Conditionnement") == "packaging"
    assert is_known_stage("Conditionnement") is True


def test_unknown_stage_normalization_is_safe():
    assert normalize_stage(None) == "unknown"
    assert normalize_stage("") == "unknown"
    assert normalize_stage("  ") == "unknown"
    assert normalize_stage("fermentation") == "unknown"
    assert is_known_stage("fermentation") is False


def test_french_stage_gets_stage_specific_recommendation_without_fallback():
    recommendation = build_recommendation(
        {
            "critical_stage": "Séchage",
            "risk_level": "medium",
            "predicted_loss_pct": 14.0,
            "is_anomalous": False,
            "top_signals": ["Stage loss above historical average"],
        }
    )
    assert recommendation["stage_canonical"] == "drying"
    assert recommendation["used_fallback"] is False
    assert any("drying" in action.lower() for action in recommendation["recommended_actions"])


def test_fallback_is_only_for_unknown_stage():
    known = build_recommendation(
        {
            "critical_stage": "Nettoyage",
            "risk_level": "medium",
            "predicted_loss_pct": 10.0,
            "is_anomalous": False,
            "top_signals": ["Stage loss above historical average"],
        }
    )
    unknown = build_recommendation(
        {
            "critical_stage": "Fermentation",
            "risk_level": "medium",
            "predicted_loss_pct": 10.0,
            "is_anomalous": False,
            "top_signals": ["Stage loss above historical average"],
        }
    )
    assert known["used_fallback"] is False
    assert unknown["used_fallback"] is True
    assert known["recommended_actions"]
    assert unknown["recommended_actions"]

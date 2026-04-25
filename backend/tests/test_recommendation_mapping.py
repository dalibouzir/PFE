from app.ml.recommendations.rule_engine import build_recommendation


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

from __future__ import annotations

from typing import Dict, List


DEFAULT_PRIOR_CAVEAT = (
    "Prior contextuel non supervise: utiliser pour aide explicative et fallback, "
    "pas comme label d'entrainement lot-level."
)


COLD_START_PRIORS: List[Dict] = [
    {
        "crop": "mangue",
        "stage": "nettoyage",
        "expected_loss_range_pct": [1.0, 4.0],
        "risk_thresholds": {"medium": 5.0, "high": 8.0},
        "weather_sensitivity": "low",
        "duration_sensitivity": "medium",
        "source_type": "expert_rule",
        "caveat": DEFAULT_PRIOR_CAVEAT,
    },
    {
        "crop": "mangue",
        "stage": "sechage",
        "expected_loss_range_pct": [6.0, 14.0],
        "risk_thresholds": {"medium": 12.0, "high": 18.0},
        "weather_sensitivity": "high",
        "duration_sensitivity": "high",
        "source_type": "external_context",
        "caveat": DEFAULT_PRIOR_CAVEAT,
    },
    {
        "crop": "mangue",
        "stage": "tri",
        "expected_loss_range_pct": [2.0, 7.0],
        "risk_thresholds": {"medium": 8.0, "high": 12.0},
        "weather_sensitivity": "low",
        "duration_sensitivity": "medium",
        "source_type": "expert_rule",
        "caveat": DEFAULT_PRIOR_CAVEAT,
    },
    {
        "crop": "mangue",
        "stage": "emballage",
        "expected_loss_range_pct": [1.0, 4.0],
        "risk_thresholds": {"medium": 5.0, "high": 8.0},
        "weather_sensitivity": "low",
        "duration_sensitivity": "medium",
        "source_type": "expert_rule",
        "caveat": DEFAULT_PRIOR_CAVEAT,
    },
    {
        "crop": "arachide",
        "stage": "nettoyage",
        "expected_loss_range_pct": [1.0, 5.0],
        "risk_thresholds": {"medium": 6.0, "high": 10.0},
        "weather_sensitivity": "low",
        "duration_sensitivity": "medium",
        "source_type": "expert_rule",
        "caveat": DEFAULT_PRIOR_CAVEAT,
    },
    {
        "crop": "arachide",
        "stage": "sechage",
        "expected_loss_range_pct": [4.0, 10.0],
        "risk_thresholds": {"medium": 10.0, "high": 15.0},
        "weather_sensitivity": "high",
        "duration_sensitivity": "high",
        "source_type": "external_context",
        "caveat": DEFAULT_PRIOR_CAVEAT,
    },
    {
        "crop": "arachide",
        "stage": "tri",
        "expected_loss_range_pct": [2.0, 6.0],
        "risk_thresholds": {"medium": 7.0, "high": 11.0},
        "weather_sensitivity": "low",
        "duration_sensitivity": "medium",
        "source_type": "expert_rule",
        "caveat": DEFAULT_PRIOR_CAVEAT,
    },
    {
        "crop": "arachide",
        "stage": "emballage",
        "expected_loss_range_pct": [1.0, 4.0],
        "risk_thresholds": {"medium": 5.0, "high": 8.0},
        "weather_sensitivity": "low",
        "duration_sensitivity": "medium",
        "source_type": "expert_rule",
        "caveat": DEFAULT_PRIOR_CAVEAT,
    },
    {
        "crop": "mil",
        "stage": "nettoyage",
        "expected_loss_range_pct": [1.0, 4.0],
        "risk_thresholds": {"medium": 5.0, "high": 8.0},
        "weather_sensitivity": "low",
        "duration_sensitivity": "medium",
        "source_type": "expert_rule",
        "caveat": DEFAULT_PRIOR_CAVEAT,
    },
    {
        "crop": "mil",
        "stage": "sechage",
        "expected_loss_range_pct": [3.0, 9.0],
        "risk_thresholds": {"medium": 9.0, "high": 14.0},
        "weather_sensitivity": "medium",
        "duration_sensitivity": "high",
        "source_type": "external_context",
        "caveat": DEFAULT_PRIOR_CAVEAT,
    },
    {
        "crop": "mil",
        "stage": "tri",
        "expected_loss_range_pct": [1.0, 5.0],
        "risk_thresholds": {"medium": 6.0, "high": 10.0},
        "weather_sensitivity": "low",
        "duration_sensitivity": "medium",
        "source_type": "expert_rule",
        "caveat": DEFAULT_PRIOR_CAVEAT,
    },
    {
        "crop": "mil",
        "stage": "emballage",
        "expected_loss_range_pct": [1.0, 3.0],
        "risk_thresholds": {"medium": 4.0, "high": 7.0},
        "weather_sensitivity": "low",
        "duration_sensitivity": "medium",
        "source_type": "expert_rule",
        "caveat": DEFAULT_PRIOR_CAVEAT,
    },
]


def get_cold_start_priors() -> List[Dict]:
    return [dict(item) for item in COLD_START_PRIORS]


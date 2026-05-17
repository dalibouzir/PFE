from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Sequence


class MLReadinessState(str, Enum):
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    BASELINE_ONLY = "BASELINE_ONLY"
    RULE_BASED = "RULE_BASED"
    ML_ASSISTED = "ML_ASSISTED"
    ML_PROMOTED = "ML_PROMOTED"


class DatasetReadinessLevel(str, Enum):
    VERY_LOW_DATA = "VERY_LOW_DATA"
    DEMO_ONLY = "DEMO_ONLY"
    RELIABLE_CANDIDATE = "RELIABLE_CANDIDATE"
    PRODUCTION_CANDIDATE = "PRODUCTION_CANDIDATE"


class RecommendationMode(str, Enum):
    RULE_BASED = "RULE_BASED"
    ML_ASSISTED = "ML_ASSISTED"
    ML_PROMOTED = "ML_PROMOTED"


@dataclass(frozen=True)
class DatasetThresholds:
    min_rows_for_demo_model: int = 100
    min_rows_for_reliable_model: int = 500
    min_rows_for_production_candidate: int = 1000


DEFAULT_DATASET_THRESHOLDS = DatasetThresholds()

DEFAULT_CAVEAT_FR = (
    "Le signal ML est utilisé comme aide à la décision. "
    "Le modèle n’est pas promu comme prédicteur fiable tant que le volume de données "
    "et les seuils de validation ne sont pas suffisants."
)


def dataset_readiness_level(
    dataset_n: int,
    thresholds: DatasetThresholds = DEFAULT_DATASET_THRESHOLDS,
) -> DatasetReadinessLevel:
    n = max(int(dataset_n), 0)
    if n < thresholds.min_rows_for_demo_model:
        return DatasetReadinessLevel.VERY_LOW_DATA
    if n < thresholds.min_rows_for_reliable_model:
        return DatasetReadinessLevel.DEMO_ONLY
    if n < thresholds.min_rows_for_production_candidate:
        return DatasetReadinessLevel.RELIABLE_CANDIDATE
    return DatasetReadinessLevel.PRODUCTION_CANDIDATE


def evaluate_model_gate(active_model_version: Optional[Dict[str, Any]]) -> tuple[str, bool, Optional[str]]:
    if not active_model_version:
        return "FAIL", False, "no_active_model"

    validation = active_model_version.get("validation") or {}
    if not validation:
        return "UNKNOWN", False, "validation_missing"

    if bool(validation.get("production_ready")):
        return "PASS", True, None

    if bool(validation.get("all_required_passed")):
        return "FAIL", False, "production_gate_not_met"
    return "FAIL", False, "validation_gate_failed"


def recommendation_mode(
    *,
    recommendation_source: str,
    ml_support_used: bool,
    promoted_by_policy: bool = False,
) -> RecommendationMode:
    source = (recommendation_source or "").strip().lower()
    if source == "rule_engine":
        if promoted_by_policy:
            return RecommendationMode.ML_PROMOTED
        if ml_support_used:
            return RecommendationMode.ML_ASSISTED
        return RecommendationMode.RULE_BASED
    if promoted_by_policy:
        return RecommendationMode.ML_PROMOTED
    return RecommendationMode.ML_ASSISTED if ml_support_used else RecommendationMode.RULE_BASED


def _fallback_reason(
    *,
    dataset_n: int,
    model_gate_passed: bool,
    mode: RecommendationMode,
    current_fallback_reason: Optional[str],
    thresholds: DatasetThresholds,
) -> Optional[str]:
    if current_fallback_reason:
        return current_fallback_reason
    if dataset_n < thresholds.min_rows_for_production_candidate:
        return "insufficient_dataset_rows"
    if not model_gate_passed:
        return "model_gate_failed"
    if mode == RecommendationMode.RULE_BASED:
        return "rule_engine_primary"
    if mode == RecommendationMode.ML_ASSISTED:
        return "ml_support_non_promoted"
    return None


def _state_for_mode(
    *,
    mode: RecommendationMode,
    dataset_n: int,
    model_gate_passed: bool,
    thresholds: DatasetThresholds,
) -> MLReadinessState:
    if dataset_n < thresholds.min_rows_for_demo_model:
        return MLReadinessState.INSUFFICIENT_DATA
    if mode == RecommendationMode.RULE_BASED:
        return (
            MLReadinessState.BASELINE_ONLY
            if dataset_n < thresholds.min_rows_for_reliable_model
            else MLReadinessState.RULE_BASED
        )
    if mode == RecommendationMode.ML_ASSISTED:
        return MLReadinessState.ML_ASSISTED
    if (
        mode == RecommendationMode.ML_PROMOTED
        and dataset_n >= thresholds.min_rows_for_production_candidate
        and model_gate_passed
    ):
        return MLReadinessState.ML_PROMOTED
    return MLReadinessState.ML_ASSISTED


def build_readiness_metadata(
    *,
    dataset_n: int,
    model_gate_status: str,
    model_gate_passed: bool,
    mode: RecommendationMode,
    evidence_sources: Sequence[str],
    fallback_reason: Optional[str] = None,
    caveat: str = DEFAULT_CAVEAT_FR,
    thresholds: DatasetThresholds = DEFAULT_DATASET_THRESHOLDS,
) -> Dict[str, Any]:
    n = max(int(dataset_n), 0)
    min_required = int(thresholds.min_rows_for_production_candidate)
    resolved_state = _state_for_mode(
        mode=mode,
        dataset_n=n,
        model_gate_passed=model_gate_passed,
        thresholds=thresholds,
    )
    resolved_fallback = _fallback_reason(
        dataset_n=n,
        model_gate_passed=model_gate_passed,
        mode=mode,
        current_fallback_reason=fallback_reason,
        thresholds=thresholds,
    )
    deduped_sources = list(dict.fromkeys(str(item) for item in evidence_sources if str(item).strip()))
    return {
        "ml_readiness_state": resolved_state.value,
        "dataset_n": n,
        "minimum_required_n": min_required,
        "dataset_readiness_level": dataset_readiness_level(n, thresholds).value,
        "model_gate_status": str(model_gate_status or "UNKNOWN"),
        "promoted": resolved_state == MLReadinessState.ML_PROMOTED,
        "fallback_reason": resolved_fallback,
        "recommendation_mode": mode.value,
        "evidence_sources": deduped_sources,
        "caveat": caveat,
    }


def infer_evidence_sources(
    *,
    include_weather: bool,
    include_duration: bool,
    include_ml_support: bool,
) -> list[str]:
    sources = [
        "process_steps",
        "batches",
        "products",
        "stocks",
        "historical_rolling_stats",
        "rule_engine",
    ]
    if include_weather:
        sources.append("weather_features")
    if include_duration:
        sources.append("duration_features")
    if include_ml_support:
        sources.append("impact_model")
    return sources

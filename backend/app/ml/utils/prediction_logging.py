from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from app.core.config import settings

PREDICTION_LOG_FILE = "prediction_logs.jsonl"


def _log_path() -> Path:
    artifacts_dir = Path(settings.ml_artifacts_path)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir / PREDICTION_LOG_FILE


def prediction_warning_flags(metadata: Dict) -> List[str]:
    metrics = metadata.get("metrics", {}) or {}
    warnings: List[str] = []

    if int(metadata.get("trained_rows", 0) or 0) < int(getattr(settings, "ml_monitoring_low_data_rows", 2000)):
        warnings.append("low_data_confidence")

    stage_mean_mae = metrics.get("regression_stage_mean_mae")
    model_mae = metrics.get("regression_mae")
    if isinstance(stage_mean_mae, (int, float)) and isinstance(model_mae, (int, float)) and model_mae > stage_mean_mae:
        warnings.append("model_underperforms_stage_baseline")

    if bool(metadata.get("contains_demo_seed_data", False)):
        warnings.append("synthetic_demo_data_used")

    if int(metrics.get("impact_real_feedback_rows", 0) or 0) == 0:
        warnings.append("no_real_feedback_available")

    return warnings


def append_prediction_log(entry: Dict) -> None:
    entry = dict(entry)
    entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    line = json.dumps(entry, ensure_ascii=True)
    with _log_path().open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def read_prediction_logs(limit: int | None = None) -> List[Dict]:
    path = _log_path()
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    if limit is not None and limit > 0:
        lines = lines[-limit:]

    parsed: List[Dict] = []
    for line in lines:
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return parsed

from pathlib import Path
import sys

from app.schemas.analysis import AnalyzeRequest

# Allow importing shared AI modules from project root.
ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from ai.analytics.loss_detection import calculate_loss  # noqa: E402
from ai.analytics.efficiency import process_efficiency  # noqa: E402


def run_analysis(payload: AnalyzeRequest) -> dict:
    loss = calculate_loss(payload.input_kg, payload.output_kg)
    expected_output = payload.input_kg * 0.82
    efficiency = process_efficiency(payload.output_kg, expected_output)
    anomaly_flag = loss["loss_pct"] > 20 or payload.duration_hours > 18

    return {
        "loss_kg": loss["loss_kg"],
        "loss_pct": loss["loss_pct"],
        "efficiency_score": efficiency,
        "anomaly_flag": anomaly_flag,
    }

from pathlib import Path
import sys

from app.schemas.recommendation import RecommendRequest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from ai.analytics.recommendation import generate_recommendation  # noqa: E402


def run_recommendation(payload: RecommendRequest) -> dict:
    recs = generate_recommendation(
        loss_pct=payload.loss_pct,
        drying_hours=payload.duration_hours,
    )
    return {"recommendations": recs}

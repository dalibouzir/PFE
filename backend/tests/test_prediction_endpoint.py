from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_current_manager
from app.core import config
from app.db.session import get_db
from app.main import app
from app.ml.features.engineer import build_features
from app.ml.training.trainer import train_models
from app.models.batch import Batch
from app.models.user import User


def test_predictive_and_assessment_endpoints(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "ml_min_rows", 1)
    monkeypatch.setattr(config.settings, "ml_artifacts_path", str(tmp_path))

    train_models(db_session, run_name="test-run")

    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_manager] = lambda: db_session.query(User).first()

    client = TestClient(app)

    first_feature = build_features(db_session).raw[0]
    predictive_payload = {
        "features": [
            {
                "product": first_feature["product"],
                "process_type": first_feature["process_type"],
                "qty_in": first_feature["qty_in"],
                "batch_size": first_feature["batch_size"],
                "stock_level": first_feature["stock_level"],
                "date": datetime.fromisoformat(str(first_feature["date"])).isoformat(),
                "month": first_feature["month"],
                "week_of_year": first_feature["week_of_year"],
                "season": first_feature["season"],
                "historical_avg_loss_same_product": first_feature["historical_avg_loss_same_product"],
                "historical_avg_loss_same_stage": first_feature["historical_avg_loss_same_stage"],
                "historical_avg_efficiency_same_stage": first_feature["historical_avg_efficiency_same_stage"],
                "previous_batch_loss": first_feature["previous_batch_loss"],
                "rolling_loss_last_n_batches": first_feature["rolling_loss_last_n_batches"],
                "rolling_efficiency_last_n_batches": first_feature["rolling_efficiency_last_n_batches"],
            }
        ],
        "include_explanation": False,
    }
    predict_response = client.post("/ml/predict", json=predictive_payload)
    assert predict_response.status_code == 200
    assert "prediction" in predict_response.json()

    batch_id = str(db_session.scalar(select(Batch.id).limit(1)))
    assess_response = client.post("/ml/assess", json={"batch_id": batch_id, "include_explanation": False})
    assert assess_response.status_code == 200
    assert "assessment" in assess_response.json()

    app.dependency_overrides.clear()

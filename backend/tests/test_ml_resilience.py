import json

import httpx
import joblib
import pandas as pd
import pytest

from app.core import config
from app.ml.inference.predictor import predict_from_features
from app.ml.llm.provider import LLMClient
from app.ml.training.trainer import MODEL_FILES
from app.ml.utils.model_store import load_model_bundle
from app.utils.exceptions import ValidationError


def test_load_model_bundle_rejects_missing_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "ml_artifacts_path", str(tmp_path))

    with pytest.raises(ValidationError, match="missing or invalid"):
        load_model_bundle()


def test_load_model_bundle_rejects_invalid_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "ml_artifacts_path", str(tmp_path))

    joblib.dump(object(), tmp_path / MODEL_FILES["loss_regressor"])
    joblib.dump(object(), tmp_path / MODEL_FILES["risk_classifier"])
    joblib.dump(object(), tmp_path / MODEL_FILES["anomaly_detector"])
    (tmp_path / MODEL_FILES["feature_metadata"]).write_text(
        json.dumps({"model_version": "invalid", "metrics": {}})
    )

    with pytest.raises(ValidationError, match="missing or invalid"):
        load_model_bundle()


def test_llm_client_timeout_raises_validation_error(monkeypatch):
    class TimeoutClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx, "Client", TimeoutClient)

    client = LLMClient(
        api_key="test-key",
        base_url="https://api.groq.com/openai/v1/chat/completions",
        model="test-model",
    )

    with pytest.raises(ValidationError, match="timed out"):
        client.chat([{"role": "user", "content": "test"}])


def test_predict_from_features_rejects_empty_frame(db_session):
    with pytest.raises(ValidationError, match="No features available for prediction"):
        predict_from_features(db_session, pd.DataFrame())

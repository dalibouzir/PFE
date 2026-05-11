from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select

from app.core import config
from app.ml.training.trainer import train_models
from app.ml.utils.feature_prep import forbidden_predictive_violations
from app.models.batch import Batch
from app.models.process_step import ProcessStep
from scripts.seed_ml_training_data import seed_ml_training_data


def test_seed_script_creates_enough_rows(db_session):
    summary = seed_ml_training_data(db_session, target_rows=500, random_seed=42, demo_only=True)
    assert summary["created_process_steps"] >= 500

    batch_codes = summary["created_batch_codes"]
    demo_step_count = db_session.scalar(
        select(func.count(ProcessStep.id))
        .join(Batch, Batch.id == ProcessStep.batch_id)
        .where(Batch.code.in_(batch_codes))
    )
    assert demo_step_count >= 500


def test_seed_script_covers_low_medium_high_loss(db_session):
    summary = seed_ml_training_data(db_session, target_rows=500, random_seed=42, demo_only=True)
    batch_codes = summary["created_batch_codes"]
    rows = db_session.execute(
        select(ProcessStep.qty_in, ProcessStep.qty_out)
        .join(Batch, Batch.id == ProcessStep.batch_id)
        .where(Batch.code.in_(batch_codes))
    ).all()
    losses = [((qty_in - qty_out) / qty_in) * 100.0 if qty_in > 0 else 0.0 for qty_in, qty_out in rows]

    low = sum(1 for value in losses if value < config.settings.step_loss_threshold)
    medium = sum(1 for value in losses if config.settings.step_loss_threshold <= value < config.settings.anomaly_loss_threshold)
    high = sum(1 for value in losses if value >= config.settings.anomaly_loss_threshold)

    assert low > 0
    assert medium > 0
    assert high > 0
    total = len(losses)
    low_ratio = low / total
    medium_ratio = medium / total
    high_ratio = high / total
    assert 0.60 <= low_ratio <= 0.80
    assert 0.12 <= medium_ratio <= 0.30
    assert 0.03 <= high_ratio <= 0.14


def test_retrained_artifacts_from_seed_are_clean(db_session, tmp_path, monkeypatch):
    seed_ml_training_data(db_session, target_rows=500, random_seed=42, demo_only=True)
    monkeypatch.setattr(config.settings, "ml_artifacts_path", str(tmp_path))
    monkeypatch.setattr(config.settings, "ml_min_rows", 1)

    train_models(db_session, run_name="seed-clean-check")
    metadata = json.loads(Path(tmp_path / "feature_metadata.json").read_text())

    assert forbidden_predictive_violations(metadata["predictive_regression_features"]) == []
    assert forbidden_predictive_violations(metadata["predictive_classification_features"]) == []
    assert metadata["predictive_features_clean"] is True

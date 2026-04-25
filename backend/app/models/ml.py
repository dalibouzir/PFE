from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import RiskLevel
from app.models.mixins import current_utc


class MLTrainingRun(Base):
    __tablename__ = "ml_training_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="completed")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=current_utc)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dataset_rows: Mapped[int] = mapped_column(nullable=False, default=0)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    models: Mapped[list["MLModelRegistry"]] = relationship(back_populates="training_run")


class MLModelRegistry(Base):
    __tablename__ = "ml_model_registry"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    model_name: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    artifact_path: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=current_utc)
    training_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("ml_training_runs.id", ondelete="SET NULL"))

    training_run: Mapped[Optional["MLTrainingRun"]] = relationship(back_populates="models")


class MLPredictionLog(Base):
    __tablename__ = "ml_prediction_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True, index=True)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    product: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    critical_stage: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    predicted_loss_pct: Mapped[Optional[float]] = mapped_column(nullable=True)
    expected_efficiency_pct: Mapped[Optional[float]] = mapped_column(nullable=True)
    risk_level: Mapped[Optional[RiskLevel]] = mapped_column(Enum(RiskLevel, native_enum=False), nullable=True)
    anomaly_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    is_anomalous: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    input_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=current_utc)


class MLRecommendationLog(Base):
    __tablename__ = "ml_recommendation_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True, index=True)
    structured_recommendation: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    llm_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=current_utc)


class RecommendationFeedbackLog(Base):
    __tablename__ = "recommendation_feedback_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recommendation_log_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("ml_recommendation_logs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True, index=True)
    stage: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    context_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    recommendation_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    shown_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=current_utc)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    outcome_window_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=48)
    outcome_recorded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    loss_before: Mapped[Optional[float]] = mapped_column(nullable=True)
    loss_after: Mapped[Optional[float]] = mapped_column(nullable=True)
    delta_loss: Mapped[Optional[float]] = mapped_column(nullable=True)
    operator_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outcome_label: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    confidence_bucket: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    harmful_probability: Mapped[Optional[float]] = mapped_column(nullable=True)
    manual_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_holdout: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    rating: Mapped[Optional[int]] = mapped_column(nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=current_utc)

    recommendation: Mapped[Optional["MLRecommendationLog"]] = relationship()

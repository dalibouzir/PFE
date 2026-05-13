from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.tools.app_data_tools import source, tool_response, warnings_for_empty
from app.models.batch import Batch
from app.models.enums import RiskLevel
from app.models.ml import MLModelRegistry, MLPredictionLog, MLTrainingRun
from app.models.process_step import ProcessStep
from app.models.user import User


class MLTools:
    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.current_user = current_user

    def analyze_loss_risk(self, *, batch_ref: str | None = None, stage: str | None = None) -> dict[str, Any]:
        batch_id = None
        if batch_ref:
            batch = self.db.scalar(
                select(Batch).where(
                    Batch.cooperative_id == self.current_user.cooperative_id,
                    func.upper(Batch.code) == str(batch_ref).upper(),
                )
            )
            if batch:
                batch_id = batch.id
            else:
                return {
                    "anomaly_detected": False,
                    "risk_level": "UNKNOWN",
                    "observed_loss_pct": None,
                    "expected_loss_pct": None,
                    "deviation": None,
                    "affected_stage": stage,
                    "affected_batch": batch_ref,
                    "confidence": 0.2,
                    "warnings": ["NO_MATCHING_BATCH_FOR_ML"],
                    "sources": [],
                }

        query = select(MLPredictionLog).order_by(MLPredictionLog.created_at.desc())
        if batch_id:
            query = query.where(MLPredictionLog.batch_id == batch_id)
        row = self.db.scalar(query.limit(1))

        warnings: list[str] = []
        if row is None:
            warnings.append("ML_SERVICE_UNAVAILABLE")
            return {
                "anomaly_detected": False,
                "risk_level": "MEDIUM",
                "observed_loss_pct": None,
                "expected_loss_pct": None,
                "deviation": None,
                "affected_stage": stage,
                "affected_batch": batch_ref,
                "confidence": 0.35,
                "warnings": warnings,
                "sources": [],
            }

        observed_loss = _compute_observed_loss(self.db, cooperative_id=self.current_user.cooperative_id, batch_id=row.batch_id, stage=stage)
        expected_loss = float(row.predicted_loss_pct or 0.0)
        deviation = None if observed_loss is None else float(observed_loss - expected_loss)

        confidence = 0.55
        if row.anomaly_score is not None:
            confidence = min(0.92, max(0.45, 0.5 + float(row.anomaly_score or 0.0) * 0.4))

        if confidence < 0.6:
            warnings.append(
                "Le modèle indique un risque, mais la confiance est limitée car les données d'entraînement sont synthétiques ou insuffisantes."
            )

        return {
            "anomaly_detected": bool(row.is_anomalous),
            "risk_level": str((row.risk_level.value if hasattr(row.risk_level, "value") else row.risk_level) or "MEDIUM").upper(),
            "observed_loss_pct": observed_loss,
            "expected_loss_pct": expected_loss,
            "deviation": deviation,
            "affected_stage": stage or row.critical_stage,
            "affected_batch": batch_ref,
            "confidence": confidence,
            "warnings": warnings,
            "sources": [
                {
                    "type": "ml",
                    "model": "loss_anomaly_detector",
                    "result_id": str(row.id),
                    "risk_level": str((row.risk_level.value if hasattr(row.risk_level, "value") else row.risk_level) or "unknown"),
                }
            ],
        }

    def get_high_risk_batches(self, limit: int = 10) -> dict[str, Any]:
        rows = self.db.scalars(
            select(MLPredictionLog)
            .where(MLPredictionLog.risk_level.in_([RiskLevel.HIGH, RiskLevel.MEDIUM]))
            .order_by(MLPredictionLog.created_at.desc())
            .limit(max(1, min(int(limit or 10), 50)))
        ).all()
        data = [_prediction_payload(row) for row in rows]
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="ml_prediction_logs", label="Lots à risque détectés par le modèle", record_count=len(data), source_type="ml")],
            warnings=warnings_for_empty(data) or (["Aucun lot à risque confirmé n’a été trouvé avec les données disponibles."] if not data else []),
        )

    def detect_loss_anomaly(self, batch_ref: str | None = None, stage: str | None = None, product: str | None = None) -> dict[str, Any]:
        result = self.analyze_loss_risk(batch_ref=batch_ref, stage=stage)
        warnings = [warning for warning in result.get("warnings", []) if not str(warning).isupper()]
        if result.get("warnings") and not warnings:
            warnings = ["L’analyse ML n’a pas pu confirmer une anomalie avec les données disponibles."]
        return tool_response(
            ok=True,
            data=result,
            sources=result.get("sources", []),
            warnings=warnings,
        )

    def get_ml_insight_summary(self, product: str | None = None, stage: str | None = None, date_range: list[str] | None = None) -> dict[str, Any]:
        rows = self.db.scalars(select(MLPredictionLog).order_by(MLPredictionLog.created_at.desc()).limit(20)).all()
        data = [_prediction_payload(row) for row in rows]
        if product:
            data = [item for item in data if str(item.get("product") or "").lower() == str(product).lower()]
        if stage:
            data = [item for item in data if str(item.get("critical_stage") or "").lower() == str(stage).lower()]
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="ml_prediction_logs", label="Résumé des signaux ML", record_count=len(data), source_type="ml")],
            warnings=warnings_for_empty(data),
        )

    def get_model_evaluation_summary(self) -> dict[str, Any]:
        runs = self.db.scalars(select(MLTrainingRun).order_by(MLTrainingRun.started_at.desc()).limit(5)).all()
        models = self.db.scalars(select(MLModelRegistry).order_by(MLModelRegistry.created_at.desc()).limit(5)).all()
        data = {
            "training_runs": [
                {
                    "run_name": row.run_name,
                    "status": row.status,
                    "dataset_rows": row.dataset_rows,
                    "metrics": row.metrics,
                    "started_at": str(row.started_at),
                    "completed_at": str(row.completed_at) if row.completed_at else None,
                }
                for row in runs
            ],
            "models": [
                {
                    "model_name": row.model_name,
                    "version": row.version,
                    "is_active": row.is_active,
                    "metrics": row.metrics,
                    "created_at": str(row.created_at),
                }
                for row in models
            ],
        }
        count = len(data["training_runs"]) + len(data["models"])
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="ml_training_runs,ml_model_registry", label="Évaluation des modèles ML", record_count=count, source_type="ml")],
            warnings=warnings_for_empty(data["training_runs"]) if count == 0 else [],
        )


def _compute_observed_loss(db: Session, *, cooperative_id, batch_id, stage: str | None) -> float | None:
    if not batch_id:
        return None
    stmt = (
        select(ProcessStep.qty_in, ProcessStep.qty_out)
        .join(Batch, Batch.id == ProcessStep.batch_id)
        .where(Batch.cooperative_id == cooperative_id, ProcessStep.batch_id == batch_id)
    )
    if stage:
        stmt = stmt.where(func.lower(ProcessStep.type) == str(stage).lower())
    rows = db.execute(stmt).all()
    if not rows:
        return None
    qty_in = sum(float(r[0] or 0.0) for r in rows)
    qty_out = sum(float(r[1] or 0.0) for r in rows)
    if qty_in <= 0:
        return None
    return (qty_in - qty_out) / qty_in * 100.0


def _prediction_payload(row: MLPredictionLog) -> dict[str, Any]:
    return {
        "prediction_id": str(row.id),
        "batch_id": str(row.batch_id) if row.batch_id else None,
        "model_version": row.model_version,
        "product": row.product,
        "critical_stage": row.critical_stage,
        "predicted_loss_pct": float(row.predicted_loss_pct or 0.0),
        "expected_efficiency_pct": float(row.expected_efficiency_pct or 0.0),
        "risk_level": str(row.risk_level.value if hasattr(row.risk_level, "value") else row.risk_level),
        "anomaly_score": float(row.anomaly_score or 0.0),
        "is_anomalous": bool(row.is_anomalous),
        "created_at": str(row.created_at),
    }

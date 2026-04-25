from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.recommendations.rule_engine import RULES
from app.ml.utils.feature_prep import assign_risk_level
from app.models.batch import Batch
from app.models.ml import RecommendationFeedbackLog
from app.models.process_step import ProcessStep

IMPACT_MODEL_FILE = "impact_recommender.joblib"
IMPACT_REPORT_FILE = "impact_recommender_report.json"
AUTO_BACKFILL_TAG = "AUTO_BACKFILL_V1"


def _targets() -> Dict[str, float]:
    return {
        "precision_at_1": 0.70,
        "harmful_rate": 0.02,
        "calibration_error": 0.05,
        "mean_loss_reduction_after_action": 0.0,
        "feedback_rows": 200,
        "holdout_ratio": 0.20,
    }


def _artifact_dir() -> Path:
    path = Path(settings.ml_artifacts_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _model_path() -> Path:
    return _artifact_dir() / IMPACT_MODEL_FILE


def _report_path() -> Path:
    return _artifact_dir() / IMPACT_REPORT_FILE


def _safe_float(value: object, fallback: float = 0.0) -> float:
    try:
        if value is None:
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _compute_loss_pct(qty_in: float, qty_out: float) -> float:
    if qty_in <= 0:
        return 0.0
    return max(0.0, ((qty_in - qty_out) / qty_in) * 100.0)


def _normalize_stage(stage: str) -> str:
    text = (stage or "").lower()
    if "dry" in text or "sech" in text:
        return "drying"
    if "sort" in text or "tri" in text:
        return "sorting"
    if "clean" in text or "nettoy" in text:
        return "cleaning"
    if "pack" in text or "condition" in text or "emball" in text:
        return "packaging"
    return "process"


def _candidate_actions_for_stage(stage: str) -> List[str]:
    key = _normalize_stage(stage)
    defaults = RULES.get(
        key,
        [
            "Review stage workflow",
            "Check operator checklist compliance",
            "Compare with recent similar batches",
        ],
    )
    return list(dict.fromkeys(defaults))


def _label_from_delta(delta_loss: Optional[float]) -> Optional[str]:
    if delta_loss is None:
        return None
    if delta_loss >= 1.0:
        return "helpful"
    if delta_loss <= -0.5:
        return "harmful"
    return "neutral"


def _extract_context_features(context_snapshot: Dict) -> Dict:
    prediction = context_snapshot.get("prediction") or {}
    assessment = context_snapshot.get("assessment") or {}
    base = prediction or assessment

    efficiency = _safe_float(base.get("predicted_efficiency_pct", base.get("observed_efficiency_pct", 0.0)))
    if efficiency <= 1.0:
        efficiency *= 100.0

    return {
        "stage": str(base.get("critical_stage") or context_snapshot.get("critical_stage") or "process"),
        "risk_level": str(base.get("risk_level") or context_snapshot.get("risk_level") or "low"),
        "predicted_loss_pct": _safe_float(base.get("predicted_loss_pct", base.get("observed_loss_pct", 0.0))),
        "anomaly_score": _safe_float(base.get("anomaly_score", 0.0)),
        "efficiency_pct": efficiency,
    }


def _normalize_action(action: str) -> str:
    cleaned = " ".join(action.lower().strip().split())
    if not cleaned:
        return "no_action"
    if len(cleaned) > 120:
        return cleaned[:120]
    return cleaned


def _hash_ratio(token: str) -> float:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / float(0xFFFFFFFF)


def _hash_to_holdout(token: Optional[str]) -> bool:
    if not token:
        return False
    return _hash_ratio(token) < settings.ml_holdout_ratio


def should_assign_holdout(recommendation_log_id: Optional[str]) -> bool:
    return _hash_to_holdout(recommendation_log_id)


def _enforce_holdout_ratio(db: Session) -> Tuple[int, float]:
    rows = db.scalars(
        select(RecommendationFeedbackLog)
        .where(
            RecommendationFeedbackLog.executed.is_(True),
            RecommendationFeedbackLog.delta_loss.is_not(None),
            RecommendationFeedbackLog.outcome_label.is_not(None),
        )
        .order_by(RecommendationFeedbackLog.created_at.asc(), RecommendationFeedbackLog.id.asc())
    ).all()
    total = len(rows)
    if total == 0:
        return 0, 0.0

    target_holdout = max(int(math.ceil(total * settings.ml_holdout_ratio)), 1)
    ranked = sorted((( _hash_ratio(str(row.id)), row) for row in rows), key=lambda item: item[0])

    for index, (_, row) in enumerate(ranked):
        row.is_holdout = index < target_holdout
    db.commit()

    return target_holdout, float(target_holdout / total)


def bootstrap_feedback_from_process_history(db: Session, minimum_rows: int = 200) -> Dict:
    existing_with_outcome = db.scalars(
        select(RecommendationFeedbackLog)
        .where(
            RecommendationFeedbackLog.executed.is_(True),
            RecommendationFeedbackLog.delta_loss.is_not(None),
            RecommendationFeedbackLog.outcome_label.is_not(None),
        )
    ).all()
    if len(existing_with_outcome) >= minimum_rows:
        holdout_rows, holdout_ratio = _enforce_holdout_ratio(db)
        return {
            "created_rows": 0,
            "feedback_rows": len(existing_with_outcome),
            "holdout_rows": holdout_rows,
            "holdout_ratio": holdout_ratio,
            "used_auto_backfill": False,
        }

    previous_auto = db.scalars(
        select(RecommendationFeedbackLog).where(RecommendationFeedbackLog.comment == AUTO_BACKFILL_TAG)
    ).all()
    for row in previous_auto:
        db.delete(row)
    db.flush()

    step_rows = db.execute(
        select(ProcessStep, Batch)
        .join(Batch, Batch.id == ProcessStep.batch_id)
        .order_by(ProcessStep.date.asc(), ProcessStep.created_at.asc())
    ).all()

    stage_history: Dict[str, List[float]] = {}
    created_rows = 0

    for step, batch in step_rows:
        stage = _normalize_stage(step.type)
        loss_after = _compute_loss_pct(_safe_float(step.qty_in), _safe_float(step.qty_out))

        history = stage_history.setdefault(stage, [])
        loss_before = float(np.mean(history[-5:])) if history else loss_after
        delta_loss = loss_before - loss_after
        outcome_label = _label_from_delta(delta_loss) or "neutral"

        risk_level = assign_risk_level(loss_after)
        anomaly_score = max(0.0, min(1.0, (loss_after - settings.step_loss_threshold) / max(settings.anomaly_loss_threshold - settings.step_loss_threshold, 1e-6)))
        actions = _candidate_actions_for_stage(stage)
        selected_action = actions[0]

        step_dt = datetime.combine(step.date, time.min, tzinfo=timezone.utc)
        holdout_token = f"{batch.id}:{step.id}:{stage}"
        is_holdout = _hash_to_holdout(holdout_token)

        feedback = RecommendationFeedbackLog(
            recommendation_log_id=None,
            batch_id=batch.id,
            stage=stage,
            context_snapshot={
                "assessment": {
                    "critical_stage": stage,
                    "observed_loss_pct": round(loss_after, 4),
                    "risk_level": risk_level,
                    "anomaly_score": round(anomaly_score, 4),
                    "observed_efficiency_pct": round(max(0.0, 100.0 - loss_after), 4),
                }
            },
            recommendation_snapshot={
                "selected_action": selected_action,
                "candidate_actions": actions,
                "source": "historical_process_backfill",
            },
            shown_at=step_dt,
            accepted=True,
            executed=True,
            outcome_window_hours=48,
            outcome_recorded_at=step_dt,
            loss_before=round(loss_before, 4),
            loss_after=round(loss_after, 4),
            delta_loss=round(delta_loss, 4),
            operator_reason="Historical performance backfill",
            outcome_label=outcome_label,
            confidence_score=None,
            confidence_bucket=None,
            harmful_probability=None,
            manual_review_required=False,
            is_holdout=is_holdout,
            model_version="historical_backfill_v1",
            rating=None,
            comment=AUTO_BACKFILL_TAG,
        )
        db.add(feedback)
        created_rows += 1
        history.append(loss_after)

    db.commit()

    current_rows = db.scalars(
        select(RecommendationFeedbackLog)
        .where(
            RecommendationFeedbackLog.executed.is_(True),
            RecommendationFeedbackLog.delta_loss.is_not(None),
            RecommendationFeedbackLog.outcome_label.is_not(None),
        )
    ).all()

    holdout_rows, holdout_ratio = _enforce_holdout_ratio(db)
    return {
        "created_rows": created_rows,
        "feedback_rows": len(current_rows),
        "holdout_rows": holdout_rows,
        "holdout_ratio": holdout_ratio,
        "used_auto_backfill": True,
    }


def _build_feedback_frame(db: Session) -> pd.DataFrame:
    rows = db.scalars(
        select(RecommendationFeedbackLog)
        .where(
            RecommendationFeedbackLog.executed.is_(True),
            RecommendationFeedbackLog.delta_loss.is_not(None),
            RecommendationFeedbackLog.outcome_label.is_not(None),
        )
        .order_by(RecommendationFeedbackLog.created_at.desc())
    ).all()

    records: List[Dict] = []
    for row in rows:
        context_features = _extract_context_features(row.context_snapshot or {})
        action = str(
            (row.recommendation_snapshot or {}).get("selected_action")
            or (row.recommendation_snapshot or {}).get("action")
            or (row.recommendation_snapshot or {}).get("suggested_action")
            or ""
        )
        delta_loss = _safe_float(row.delta_loss, 0.0)
        outcome_label = row.outcome_label or _label_from_delta(delta_loss)
        if outcome_label is None:
            continue

        predicted_loss = context_features["predicted_loss_pct"]
        anomaly = context_features["anomaly_score"]
        ctx_bucket = "|".join(
            [
                _normalize_stage(context_features["stage"]),
                str(context_features["risk_level"]),
                str(int(predicted_loss // 2)),
                str(int(anomaly * 10)),
            ]
        )

        records.append(
            {
                "feedback_id": str(row.id),
                "context_key": ctx_bucket,
                "stage": _normalize_stage(context_features["stage"]),
                "risk_level": str(context_features["risk_level"]),
                "predicted_loss_pct": predicted_loss,
                "anomaly_score": anomaly,
                "efficiency_pct": context_features["efficiency_pct"],
                "action_key": _normalize_action(action),
                "delta_loss": delta_loss,
                "outcome_label": outcome_label,
                "harmful_target": 1 if outcome_label == "harmful" else 0,
                "helpful_target": 1 if outcome_label == "helpful" else 0,
                "is_holdout": bool(row.is_holdout),
                "is_real_feedback": row.comment != AUTO_BACKFILL_TAG,
            }
        )

    return pd.DataFrame(records)


def _encode_features(df: pd.DataFrame) -> pd.DataFrame:
    base_cols = ["stage", "risk_level", "predicted_loss_pct", "anomaly_score", "efficiency_pct", "action_key"]
    work = df[base_cols].copy()
    return pd.get_dummies(work, columns=["stage", "risk_level", "action_key"], dtype=float)


def _align_columns(frame: pd.DataFrame, feature_columns: List[str]) -> pd.DataFrame:
    aligned = frame.copy()
    for column in feature_columns:
        if column not in aligned.columns:
            aligned[column] = 0.0
    return aligned[feature_columns]


def _ece_score(probs: np.ndarray, labels: np.ndarray, bins: int = 10) -> float:
    if len(probs) == 0:
        return 0.0

    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    n = len(probs)
    for idx in range(bins):
        left, right = edges[idx], edges[idx + 1]
        mask = (probs >= left) & (probs < right if idx < bins - 1 else probs <= right)
        if not np.any(mask):
            continue
        bucket_conf = float(np.mean(probs[mask]))
        bucket_acc = float(np.mean(labels[mask]))
        ece += abs(bucket_conf - bucket_acc) * (float(np.sum(mask)) / n)
    return float(ece)


def _confidence(gain: np.ndarray, harmful_prob: np.ndarray) -> np.ndarray:
    gain_term = 1.0 / (1.0 + np.exp(-gain))
    return np.clip((1.0 - harmful_prob) * 0.7 + gain_term * 0.3, 0.0, 1.0)


def _meets_targets(metrics: Dict, feedback_rows: int, holdout_ratio: float) -> bool:
    t = _targets()
    return (
        metrics["precision_at_1"] >= t["precision_at_1"]
        and metrics["harmful_rate"] <= t["harmful_rate"]
        and metrics["calibration_error"] <= t["calibration_error"]
        and metrics["mean_loss_reduction_after_action"] > t["mean_loss_reduction_after_action"]
        and feedback_rows >= int(t["feedback_rows"])
        and holdout_ratio >= t["holdout_ratio"]
    )


def _evaluate_policy(
    holdout_df: pd.DataFrame,
    gain_pred: np.ndarray,
    harmful_prob: np.ndarray,
    harmful_base_rate: float,
    harmful_blend_alpha: float,
    confidence_threshold: float,
    harmful_threshold: float,
) -> Dict:
    eval_df = holdout_df.copy()
    eval_df["pred_gain"] = gain_pred
    blended_prob = harmful_blend_alpha * np.clip(harmful_prob, 0.0, 1.0) + (1.0 - harmful_blend_alpha) * harmful_base_rate
    eval_df["harm_prob"] = np.clip(blended_prob, 0.0, 1.0)
    eval_df["confidence"] = _confidence(eval_df["pred_gain"].to_numpy(), eval_df["harm_prob"].to_numpy())
    eval_df["rank_score"] = eval_df["pred_gain"] * (1.0 - eval_df["harm_prob"]) + eval_df["confidence"] * 0.3

    policy_mask = (eval_df["confidence"] >= confidence_threshold) & (eval_df["harm_prob"] <= harmful_threshold)
    candidates = eval_df[policy_mask].copy()

    if candidates.empty:
        return {
            "precision_at_1": 0.0,
            "harmful_rate": 1.0,
            "calibration_error": _ece_score(eval_df["harm_prob"].to_numpy(), eval_df["harmful_target"].to_numpy(dtype=int)),
            "mean_loss_reduction_after_action": 0.0,
            "coverage": 0.0,
            "recommended_rows": 0,
        }

    top1 = (
        candidates.sort_values(["context_key", "rank_score"], ascending=[True, False])
        .groupby("context_key", as_index=False)
        .head(1)
    )

    precision = float(top1["helpful_target"].mean()) if len(top1) else 0.0
    harmful_rate = float(top1["harmful_target"].mean()) if len(top1) else 1.0
    mean_delta = float(top1["delta_loss"].mean()) if len(top1) else 0.0
    coverage = float(len(top1) / len(eval_df)) if len(eval_df) else 0.0
    ece = _ece_score(eval_df["harm_prob"].to_numpy(), eval_df["harmful_target"].to_numpy(dtype=int))

    return {
        "precision_at_1": precision,
        "harmful_rate": harmful_rate,
        "calibration_error": ece,
        "mean_loss_reduction_after_action": mean_delta,
        "coverage": coverage,
        "recommended_rows": int(len(top1)),
    }


def _fit_models(
    X_train: pd.DataFrame,
    y_delta: np.ndarray,
    y_harmful: np.ndarray,
    reg_params: Dict,
    clf_params: Dict,
    calibration_method: str,
):
    regressor = GradientBoostingRegressor(random_state=42, **reg_params)
    regressor.fit(X_train, y_delta)

    classifier = None
    if len(np.unique(y_harmful)) > 1 and len(y_harmful) >= 30:
        try:
            base = GradientBoostingClassifier(random_state=42, **clf_params)
            if calibration_method in {"isotonic", "sigmoid"}:
                classifier = CalibratedClassifierCV(base, method=calibration_method, cv=3)
                classifier.fit(X_train, y_harmful)
            else:
                base.fit(X_train, y_harmful)
                classifier = base
        except Exception:
            classifier = None

    return regressor, classifier


def _default_harm_probability(delta_pred: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(delta_pred * 1.8))


def _write_report(report_payload: Dict) -> None:
    _report_path().write_text(json.dumps(report_payload, indent=2))


def train_impact_models(db: Session, model_version: str) -> Dict:
    bootstrap_info = bootstrap_feedback_from_process_history(db, minimum_rows=settings.ml_feedback_min_rows)

    df = _build_feedback_frame(db)
    feedback_rows = int(len(df))
    real_feedback_rows = int(df["is_real_feedback"].sum()) if not df.empty and "is_real_feedback" in df.columns else 0
    proxy_feedback_rows = max(feedback_rows - real_feedback_rows, 0)
    holdout_rows = int(df["is_holdout"].sum()) if not df.empty else 0
    holdout_ratio = float(holdout_rows / max(feedback_rows, 1)) if feedback_rows > 0 else 0.0

    if df.empty or feedback_rows < settings.ml_feedback_min_rows:
        metrics = {
            "impact_model_ready": False,
            "feedback_rows": feedback_rows,
            "holdout_rows": holdout_rows,
            "holdout_ratio": holdout_ratio,
            "real_feedback_rows": real_feedback_rows,
            "proxy_feedback_rows": proxy_feedback_rows,
            "precision_at_1": 0.0,
            "harmful_rate": 1.0,
            "calibration_error": 1.0,
            "mean_loss_reduction_after_action": 0.0,
            "coverage": 0.0,
            "recommended_rows": 0,
            "targets_met": False,
            "used_auto_backfill": proxy_feedback_rows > 0,
        }
        _write_report(
            {
                "model_version": model_version,
                "targets": _targets(),
                "metrics": metrics,
                "experiments": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return metrics

    if holdout_rows == 0 or holdout_ratio < settings.ml_holdout_ratio:
        _enforce_holdout_ratio(db)
        df = _build_feedback_frame(db)
        feedback_rows = int(len(df))
        real_feedback_rows = int(df["is_real_feedback"].sum()) if "is_real_feedback" in df.columns else 0
        proxy_feedback_rows = max(feedback_rows - real_feedback_rows, 0)
        holdout_rows = int(df["is_holdout"].sum())
        holdout_ratio = float(holdout_rows / max(feedback_rows, 1))

    train_df = df[~df["is_holdout"]].copy()
    holdout_df = df[df["is_holdout"]].copy()
    if train_df.empty or holdout_df.empty:
        train_df = df.sample(frac=0.8, random_state=42)
        holdout_df = df.drop(train_df.index)

    X_train = _encode_features(train_df)
    X_holdout = _encode_features(holdout_df)
    feature_columns = sorted(set(X_train.columns) | set(X_holdout.columns))
    X_train = _align_columns(X_train, feature_columns)
    X_holdout = _align_columns(X_holdout, feature_columns)

    y_delta_train = train_df["delta_loss"].to_numpy(dtype=float)
    y_harm_train = train_df["harmful_target"].to_numpy(dtype=int)

    reg_grid = [
        {"n_estimators": 120, "learning_rate": 0.05, "max_depth": 2},
        {"n_estimators": 200, "learning_rate": 0.05, "max_depth": 3},
        {"n_estimators": 300, "learning_rate": 0.03, "max_depth": 2},
        {"n_estimators": 280, "learning_rate": 0.04, "max_depth": 3},
    ]
    clf_grid = [
        {"n_estimators": 120, "learning_rate": 0.05, "max_depth": 2},
        {"n_estimators": 200, "learning_rate": 0.05, "max_depth": 2},
    ]
    calibration_methods = ["isotonic", "sigmoid", "none"]
    confidence_thresholds = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]
    harmful_thresholds = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
    harmful_blend_alphas = [0.0, 0.10, 0.20, 0.35, 0.50, 0.65, 0.80, 1.0]

    experiments: List[Dict] = []
    best_payload: Optional[Dict] = None
    best_score = float("-inf")
    best_meeting_payload: Optional[Dict] = None

    iteration = 0
    for reg_params in reg_grid:
        for clf_params in clf_grid:
            for calibration_method in calibration_methods:
                iteration += 1
                regressor, classifier = _fit_models(
                    X_train,
                    y_delta_train,
                    y_harm_train,
                    reg_params=reg_params,
                    clf_params=clf_params,
                    calibration_method=calibration_method,
                )

                holdout_delta_pred = regressor.predict(X_holdout)
                if classifier is not None:
                    base_harm_prob = classifier.predict_proba(X_holdout)[:, 1]
                else:
                    base_harm_prob = _default_harm_probability(holdout_delta_pred)
                harmful_base_rate = float(np.mean(y_harm_train)) if len(y_harm_train) else 0.0

                for harmful_blend_alpha in harmful_blend_alphas:
                    for confidence_threshold in confidence_thresholds:
                        for harmful_threshold in harmful_thresholds:
                            metrics = _evaluate_policy(
                                holdout_df,
                                gain_pred=holdout_delta_pred,
                                harmful_prob=base_harm_prob,
                                harmful_base_rate=harmful_base_rate,
                                harmful_blend_alpha=harmful_blend_alpha,
                                confidence_threshold=confidence_threshold,
                                harmful_threshold=harmful_threshold,
                            )
                            targets_met = _meets_targets(metrics, feedback_rows=feedback_rows, holdout_ratio=holdout_ratio)
                            score = (
                                metrics["precision_at_1"] * 3.0
                                + max(metrics["mean_loss_reduction_after_action"], 0.0) * 0.5
                                - metrics["harmful_rate"] * 4.0
                                - metrics["calibration_error"] * 2.0
                                + metrics["coverage"] * 0.4
                            )

                            experiment = {
                                "iteration": iteration,
                                "regressor": reg_params,
                                "classifier": clf_params,
                                "calibration_method": calibration_method,
                                "harmful_blend_alpha": harmful_blend_alpha,
                                "policy": {
                                    "confidence_threshold": confidence_threshold,
                                    "harmful_threshold": harmful_threshold,
                                },
                                "metrics": metrics,
                                "targets_met": targets_met,
                                "score": score,
                            }
                            experiments.append(experiment)

                            payload = {
                                "regressor": regressor,
                                "classifier": classifier,
                                "feature_columns": feature_columns,
                                "regressor_params": reg_params,
                                "classifier_params": clf_params,
                                "calibration_method": calibration_method,
                                "harmful_blend_alpha": harmful_blend_alpha,
                                "harmful_base_rate": harmful_base_rate,
                                "policy": {
                                    "confidence_threshold": confidence_threshold,
                                    "harmful_threshold": harmful_threshold,
                                },
                                "metrics": metrics,
                            }

                            if targets_met and best_meeting_payload is None:
                                best_meeting_payload = payload

                            if score > best_score:
                                best_score = score
                                best_payload = payload

                if best_meeting_payload is not None:
                    break
            if best_meeting_payload is not None:
                break
        if best_meeting_payload is not None:
            break

    final_payload = best_meeting_payload or best_payload
    if final_payload is None:
        metrics = {
            "impact_model_ready": False,
            "feedback_rows": feedback_rows,
            "holdout_rows": holdout_rows,
            "holdout_ratio": holdout_ratio,
            "real_feedback_rows": real_feedback_rows,
            "proxy_feedback_rows": proxy_feedback_rows,
            "precision_at_1": 0.0,
            "harmful_rate": 1.0,
            "calibration_error": 1.0,
            "mean_loss_reduction_after_action": 0.0,
            "coverage": 0.0,
            "recommended_rows": 0,
            "targets_met": False,
            "used_auto_backfill": proxy_feedback_rows > 0,
        }
        _write_report(
            {
                "model_version": model_version,
                "targets": _targets(),
                "metrics": metrics,
                "experiments": experiments,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return metrics

    metrics = dict(final_payload["metrics"])
    targets_met = _meets_targets(metrics, feedback_rows=feedback_rows, holdout_ratio=holdout_ratio)
    metrics.update(
        {
            "impact_model_ready": True,
            "feedback_rows": feedback_rows,
            "holdout_rows": holdout_rows,
            "holdout_ratio": holdout_ratio,
            "real_feedback_rows": real_feedback_rows,
            "proxy_feedback_rows": proxy_feedback_rows,
            "targets_met": targets_met,
            "used_auto_backfill": proxy_feedback_rows > 0,
            "recommended_rows": int(metrics.get("recommended_rows", 0)),
        }
    )

    numeric_reference = {
        "predicted_loss_pct": {
            "mean": float(train_df["predicted_loss_pct"].mean()),
            "std": float(max(train_df["predicted_loss_pct"].std(ddof=0), 1e-6)),
        },
        "anomaly_score": {
            "mean": float(train_df["anomaly_score"].mean()),
            "std": float(max(train_df["anomaly_score"].std(ddof=0), 1e-6)),
        },
        "efficiency_pct": {
            "mean": float(train_df["efficiency_pct"].mean()),
            "std": float(max(train_df["efficiency_pct"].std(ddof=0), 1e-6)),
        },
    }

    model_payload = {
        "model_version": model_version,
        "feature_columns": final_payload["feature_columns"],
        "regressor": final_payload["regressor"],
        "classifier": final_payload["classifier"],
        "regressor_params": final_payload["regressor_params"],
        "classifier_params": final_payload["classifier_params"],
        "calibration_method": final_payload["calibration_method"],
        "harmful_blend_alpha": float(final_payload.get("harmful_blend_alpha", 1.0)),
        "harmful_base_rate": float(final_payload.get("harmful_base_rate", 0.0)),
        "policy": final_payload["policy"],
        "metrics": metrics,
        "numeric_reference": numeric_reference,
        "targets": _targets(),
    }
    joblib.dump(model_payload, _model_path())

    _write_report(
        {
            "model_version": model_version,
            "targets": _targets(),
            "metrics": metrics,
            "selected_configuration": {
                "regressor": final_payload["regressor_params"],
                "classifier": final_payload["classifier_params"],
                "calibration_method": final_payload["calibration_method"],
                "harmful_blend_alpha": float(final_payload.get("harmful_blend_alpha", 1.0)),
                "harmful_base_rate": float(final_payload.get("harmful_base_rate", 0.0)),
                "policy": final_payload["policy"],
            },
            "experiments": experiments,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    return metrics


def load_impact_model() -> Optional[Dict]:
    path = _model_path()
    if not path.exists():
        return None
    try:
        return joblib.load(path)
    except Exception:
        return None


def compute_recent_calibration_drift(db: Session, limit: int = 200) -> float:
    rows = db.scalars(
        select(RecommendationFeedbackLog)
        .where(RecommendationFeedbackLog.outcome_label.is_not(None))
        .order_by(RecommendationFeedbackLog.created_at.desc())
        .limit(limit)
    ).all()
    if not rows:
        return 0.0

    probs: List[float] = []
    labels: List[int] = []
    for row in rows:
        prob = row.harmful_probability
        if prob is None and row.confidence_score is not None:
            prob = 1.0 - row.confidence_score
        if prob is None:
            continue
        probs.append(float(max(0.0, min(1.0, prob))))
        labels.append(1 if row.outcome_label == "harmful" else 0)

    if not probs:
        return 0.0
    return _ece_score(np.array(probs, dtype=float), np.array(labels, dtype=int))


def _confidence_bucket(confidence_score: float) -> str:
    if confidence_score >= settings.ml_confidence_high_threshold:
        return "High"
    if confidence_score >= settings.ml_confidence_medium_threshold:
        return "Medium"
    return "Low"


def _detect_data_drift(context_features: Dict, model_payload: Dict) -> bool:
    reference = model_payload.get("numeric_reference") or {}
    drifted = 0
    for key in ("predicted_loss_pct", "anomaly_score", "efficiency_pct"):
        stats = reference.get(key)
        if not stats:
            continue
        mean = _safe_float(stats.get("mean"), 0.0)
        std = _safe_float(stats.get("std"), 1.0)
        value = _safe_float(context_features.get(key), mean)
        z = abs((value - mean) / max(std, 1e-6))
        if z >= settings.ml_data_drift_zscore_threshold:
            drifted += 1
    return drifted >= settings.ml_data_drift_feature_count_threshold


def recommend_action_with_confidence(
    db: Session,
    context_snapshot: Dict,
    candidate_actions: List[str],
    fallback_action: str,
) -> Dict:
    model_payload = load_impact_model()
    context_features = _extract_context_features(context_snapshot)

    if model_payload is None or not candidate_actions:
        return {
            "selected_action": fallback_action,
            "ranked_actions": [{"action": fallback_action, "expected_loss_reduction": 0.0, "harmful_probability": 0.5, "confidence_score": 0.4}],
            "expected_loss_reduction": 0.0,
            "harmful_probability": 0.5,
            "confidence_score": 0.4,
            "confidence_bucket": "Low",
            "manual_review_required": True,
            "abstained": True,
            "fallback_reason": "impact_model_unavailable",
            "drift_detected": False,
            "calibration_drift": 0.0,
            "model_version": None,
        }

    rows = []
    for action in candidate_actions:
        rows.append(
            {
                "stage": _normalize_stage(context_features["stage"]),
                "risk_level": str(context_features["risk_level"]),
                "predicted_loss_pct": _safe_float(context_features["predicted_loss_pct"]),
                "anomaly_score": _safe_float(context_features["anomaly_score"]),
                "efficiency_pct": _safe_float(context_features["efficiency_pct"]),
                "action_key": _normalize_action(action),
                "raw_action": action,
            }
        )

    features = pd.DataFrame(rows)
    encoded = pd.get_dummies(features.drop(columns=["raw_action"]), columns=["stage", "risk_level", "action_key"], dtype=float)
    encoded = _align_columns(encoded, model_payload.get("feature_columns", []))

    regressor = model_payload["regressor"]
    classifier = model_payload.get("classifier")
    predicted_delta = regressor.predict(encoded)
    if classifier is not None:
        harmful_prob = classifier.predict_proba(encoded)[:, 1]
    else:
        harmful_prob = _default_harm_probability(predicted_delta)

    harmful_blend_alpha = float(model_payload.get("harmful_blend_alpha", 1.0))
    harmful_base_rate = float(model_payload.get("harmful_base_rate", 0.0))
    harmful_prob = np.clip(
        harmful_blend_alpha * np.clip(harmful_prob, 0.0, 1.0) + (1.0 - harmful_blend_alpha) * harmful_base_rate,
        0.0,
        1.0,
    )

    confidences = _confidence(predicted_delta, harmful_prob)

    ranked = []
    for idx, item in enumerate(rows):
        gain = float(predicted_delta[idx])
        harm = float(max(0.0, min(1.0, harmful_prob[idx])))
        confidence = float(confidences[idx])
        rank_score = gain * (1.0 - harm) + confidence * 0.3
        ranked.append(
            {
                "action": item["raw_action"],
                "expected_loss_reduction": gain,
                "harmful_probability": harm,
                "confidence_score": confidence,
                "rank_score": rank_score,
            }
        )

    ranked.sort(key=lambda row: (row["rank_score"], row["confidence_score"]), reverse=True)
    best = ranked[0]

    data_drift = _detect_data_drift(context_features, model_payload)
    calibration_drift = compute_recent_calibration_drift(db)
    drift_detected = data_drift or calibration_drift > settings.ml_calibration_drift_threshold

    policy = model_payload.get("policy", {})
    confidence_threshold = float(policy.get("confidence_threshold", settings.ml_recommendation_confidence_threshold))
    harmful_threshold = float(policy.get("harmful_threshold", settings.ml_harmful_probability_threshold))

    should_abstain = (
        best["confidence_score"] < confidence_threshold
        or best["harmful_probability"] > harmful_threshold
        or drift_detected
    )

    selected = fallback_action if should_abstain else best["action"]
    confidence_score = best["confidence_score"] if not should_abstain else min(best["confidence_score"], 0.45)

    return {
        "selected_action": selected,
        "ranked_actions": [
            {
                "action": item["action"],
                "expected_loss_reduction": float(item["expected_loss_reduction"]),
                "harmful_probability": float(item["harmful_probability"]),
                "confidence_score": float(item["confidence_score"]),
            }
            for item in ranked
        ],
        "expected_loss_reduction": float(best["expected_loss_reduction"]),
        "harmful_probability": float(best["harmful_probability"]),
        "confidence_score": float(confidence_score),
        "confidence_bucket": _confidence_bucket(confidence_score),
        "manual_review_required": bool(should_abstain),
        "abstained": bool(should_abstain),
        "fallback_reason": "manual_review_required" if should_abstain else None,
        "drift_detected": bool(drift_detected),
        "calibration_drift": float(calibration_drift),
        "model_version": model_payload.get("model_version"),
    }


def reliability_status(db: Session) -> Dict:
    model_payload = load_impact_model()
    calibration_drift = compute_recent_calibration_drift(db)
    targets = _targets()

    if not model_payload:
        return {
            "impact_model_ready": False,
            "offline_metrics": {},
            "calibration_drift": calibration_drift,
            "drift_blocking_recommendations": calibration_drift > settings.ml_calibration_drift_threshold,
            "targets": targets,
            "targets_met": False,
        }

    metrics = dict(model_payload.get("metrics", {}))
    feedback_rows = int(metrics.get("feedback_rows", 0))
    holdout_ratio = float(metrics.get("holdout_ratio", 0.0))
    targets_met = _meets_targets(metrics, feedback_rows=feedback_rows, holdout_ratio=holdout_ratio)

    return {
        "impact_model_ready": True,
        "offline_metrics": metrics,
        "calibration_drift": calibration_drift,
        "drift_blocking_recommendations": calibration_drift > settings.ml_calibration_drift_threshold,
        "model_version": model_payload.get("model_version"),
        "targets": targets,
        "targets_met": targets_met,
    }

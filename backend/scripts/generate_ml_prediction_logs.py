#!/usr/bin/env python3
"""
Generate baseline ML predictions for loss anomaly detection.

This script creates baseline loss predictions and anomaly scores for existing batches
using rule-based heuristics and statistical analysis.

Usage:
    python backend/scripts/generate_ml_prediction_logs.py

Run this after seeding test batches to populate ml_prediction_logs table.
"""

import sys
from datetime import datetime, timedelta
from typing import Any
import statistics

sys.path.insert(0, "/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project")
sys.path.insert(0, "/Users/mohamedalibouzir/Desktop/Stage PFE/Pfe project/backend")

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models.batch import Batch
from app.models.process_step import ProcessStep
from app.models.ml import MLPredictionLog, RiskLevel
from app.models.cooperative import Cooperative


# Rule-based loss thresholds per stage (from domain knowledge)
STAGE_THRESHOLDS = {
    "cleaning": {"low": (2, 4), "medium": (4, 8), "high": (8, 100)},  # (min%, max%)
    "drying": {"low": (10, 15), "medium": (15, 20), "high": (20, 100)},
    "sorting": {"low": (5, 8), "medium": (8, 12), "high": (12, 100)},
    "packaging": {"low": (1, 3), "medium": (3, 5), "high": (5, 100)},
    "storage": {"low": (0.5, 1), "medium": (1, 2), "high": (2, 100)},
}

# Expected average loss per stage (for statistical analysis)
EXPECTED_LOSS = {
    "cleaning": 3.0,
    "drying": 12.5,
    "sorting": 6.5,
    "packaging": 2.0,
    "storage": 0.75,
}


def compute_loss_pct(qty_in: float, qty_out: float) -> float:
    """Compute loss percentage."""
    if qty_in <= 0:
        return 0.0
    return ((qty_in - qty_out) / qty_in) * 100.0


def classify_risk_level(loss_pct: float, stage: str) -> str:
    """Classify risk level based on observed loss."""
    thresholds = STAGE_THRESHOLDS.get(stage, {"low": (5, 10), "medium": (10, 20), "high": (20, 100)})
    
    if loss_pct <= thresholds["low"][1]:
        return "LOW"
    elif loss_pct <= thresholds["medium"][1]:
        return "MEDIUM"
    else:
        return "HIGH"


def compute_anomaly_score(observed_loss: float, expected_loss: float, std_dev: float = None) -> float:
    """
    Compute anomaly score (0-1) based on deviation from expected.
    
    Formula: 
    - If expected is 0: anomaly = min(observed / 5, 1.0)
    - Else: anomaly = min(abs(observed - expected) / (expected * 2), 1.0)
    """
    if expected_loss == 0:
        return min(observed_loss / 5.0, 1.0)
    
    deviation = abs(observed_loss - expected_loss)
    tolerance = expected_loss * 2
    
    return min(deviation / tolerance, 1.0)


def generate_predictions_for_batch(db: Session, batch: Batch) -> list[dict[str, Any]]:
    """Generate ML predictions for all process steps in a batch."""
    predictions = []
    
    # Get all process steps for this batch
    steps = db.query(ProcessStep).filter(ProcessStep.batch_id == batch.id).order_by(ProcessStep.sequence_order.asc()).all()
    
    if not steps:
        return predictions
    
    # Compute loss statistics
    stage_losses = {}
    for step in steps:
        loss_pct = compute_loss_pct(step.qty_in, step.qty_out)
        stage = step.type or "unknown"
        if stage not in stage_losses:
            stage_losses[stage] = []
        stage_losses[stage].append(loss_pct)
    
    # Generate prediction for each process step
    for step in steps:
        if step.qty_in <= 0 or step.qty_out < 0:
            continue
        
        observed_loss = compute_loss_pct(step.qty_in, step.qty_out)
        expected_loss = EXPECTED_LOSS.get(step.type or "unknown", 5.0)
        stage_loss_values = stage_losses.get(step.type or "unknown", [])
        
        # Calculate std dev if we have multiple samples
        std_dev = statistics.stdev(stage_loss_values) if len(stage_loss_values) > 1 else 0.0
        
        # Compute anomaly
        anomaly_score = compute_anomaly_score(observed_loss, expected_loss, std_dev)
        is_anomaly = anomaly_score > 0.5  # Threshold
        
        # Classify risk
        risk_level = classify_risk_level(observed_loss, step.type or "unknown")
        
        # Compute confidence
        confidence = max(0.35, 1.0 - anomaly_score * 0.2)  # Higher anomaly = lower confidence
        
        prediction = {
            "batch_id": batch.id,
            "batch_ref": batch.code,
            "stage": step.type or "unknown",
            "product": batch.product.name,
            "qty_in": float(step.qty_in),
            "qty_out": float(step.qty_out),
            "observed_loss_pct": float(observed_loss),
            "expected_loss_pct": float(expected_loss),
            "expected_efficiency_pct": float(100.0 - expected_loss),
            "deviation_pct": float(observed_loss - expected_loss),
            "anomaly_score": float(anomaly_score),
            "anomaly_detected": is_anomaly,
            "risk_level": risk_level,
            "confidence": float(confidence),
            "method": "BASELINE_STATISTICAL",
            "model_version": "1.0",
            "warnings": [],
        }
        
        # Add warnings if applicable
        if is_anomaly:
            prediction["warnings"].append(f"Anomalie détectée: perte {observed_loss:.1f}% vs attendu {expected_loss:.1f}%")
        if anomaly_score > 0.7:
            prediction["warnings"].append("Anomalie sévère - considérez investigation immédiate")
        
        predictions.append(prediction)
    
    return predictions


def generate_ml_predictions(db: Session, dry_run: bool = False) -> None:
    """Generate baseline ML predictions for all batches."""
    print(f"🤖 Starting ML prediction generation (dry_run={dry_run})...\n")
    
    # Get all batches
    batches = db.query(Batch).all()
    print(f"📦 Found {len(batches)} batches to analyze")
    
    if not batches:
        print("⚠️  No batches found. Skipping prediction generation.")
        return
    
    total_predictions = 0
    created_predictions = 0
    skipped_predictions = 0
    
    for batch in batches:
        predictions = generate_predictions_for_batch(db, batch)
        
        for pred in predictions:
            total_predictions += 1
            
            # Check if prediction already exists for this batch/stage/version
            existing = db.query(MLPredictionLog).filter(
                MLPredictionLog.batch_id == batch.id,
                MLPredictionLog.critical_stage == pred["stage"],
                MLPredictionLog.model_version == "1.0",
            ).first()
            
            if existing:
                skipped_predictions += 1
                continue
            
            # Parse risk level enum
            try:
                risk_enum = RiskLevel[pred["risk_level"]]
            except (KeyError, ValueError):
                risk_enum = None
            
            # Create ML prediction log
            ml_log = MLPredictionLog(
                batch_id=batch.id,
                model_version="1.0",
                product=pred["product"],
                critical_stage=pred["stage"],
                predicted_loss_pct=pred["observed_loss_pct"],
                expected_efficiency_pct=pred["expected_efficiency_pct"],
                risk_level=risk_enum,
                anomaly_score=pred["anomaly_score"],
                is_anomalous=pred["anomaly_detected"],
                input_snapshot={
                    "qty_in": pred["qty_in"],
                    "qty_out": pred["qty_out"],
                    "expected_loss_pct": pred["expected_loss_pct"],
                },
                output_snapshot={
                    "observed_loss_pct": pred["observed_loss_pct"],
                    "confidence": pred["confidence"],
                    "method": pred["method"],
                    "warnings": pred["warnings"],
                    "deviation_pct": pred["deviation_pct"],
                },
            )
            
            if not dry_run:
                db.add(ml_log)
            
            created_predictions += 1
            
            print(f"  {pred['batch_ref']} / {pred['stage']}: "
                  f"loss={pred['observed_loss_pct']:.1f}%, "
                  f"risk={pred['risk_level']}, "
                  f"anomaly={pred['anomaly_detected']}")
    
    if not dry_run:
        db.commit()
        print(f"\n✅ ML prediction generation complete!")
    else:
        print(f"\n📋 Dry run complete (no changes committed)")
    
    print(f"   📊 Total predictions analyzed: {total_predictions}")
    print(f"   ✨ Created: {created_predictions}")
    print(f"   ⏭️  Skipped: {skipped_predictions} (already exist)")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    
    print("🚀 ML Baseline Prediction Generation\n")
    
    try:
        with Session(engine) as db:
            generate_ml_predictions(db, dry_run=dry_run)
            print("\n✅ Success!")
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

"""
Serves the precision/recall/false-positive-rate story the problem statement
explicitly asks for ("threshold calibration for acceptable false positive
rates"). Reads the latest ModelVersion row the ML teammate's train.py wrote;
falls back to a clearly-labeled placeholder if none exists yet so the
endpoint never 500s during early development.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models_orm import ModelVersion


def get_current_metrics(db: Session) -> dict:
    latest = db.execute(
        select(ModelVersion).order_by(ModelVersion.trained_at.desc())
    ).scalars().first()

    if latest is None:
        settings = get_settings()
        return {
            "threshold": settings.decision_threshold,
            "precision": 0.0,
            "recall": 0.0,
            "false_positive_rate": 0.0,
            "algorithm": "rule_based_v0 (no trained model registered yet)",
            "trained_at": None,
        }

    m = latest.metrics or {}
    return {
        "threshold": latest.threshold,
        "precision": m.get("precision", 0.0),
        "recall": m.get("recall", 0.0),
        "false_positive_rate": m.get("false_positive_rate", 0.0),
        "algorithm": latest.algorithm,
        "trained_at": latest.trained_at,
    }

"""
Inference layer, hidden behind one function: `get_scorer()`.

Why this exists: the backend must not be blocked on the ML teammate's
training pipeline. `RuleBasedScorer` gives every downstream piece (API,
replay worker, tests) something real to call today. The moment
`ml_artifacts/model.pkl` + `features.json` exist, `get_scorer()` picks up
`TrainedModelScorer` instead -- nothing else in the codebase changes.

Both scorers implement the same contract:
    score(flow: dict) -> ScoredFlow(attack_type, confidence, severity, raw_features)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.config import get_settings

ATTACK_TYPES = [
    "DDoS", "DoS", "Port Scan", "Brute Force", "Botnet", "Web Attack", "Infiltration",
]


@dataclass
class ScoredFlow:
    attack_type: str | None      # None means "classified as normal traffic"
    confidence: int              # 0-100
    severity: str                # low | medium | high | critical
    raw_features: dict = field(default_factory=dict)


def severity_from_confidence(confidence: int) -> str:
    if confidence >= 90:
        return "critical"
    if confidence >= 75:
        return "high"
    if confidence >= 50:
        return "medium"
    return "low"


class RuleBasedScorer:
    """
    Deterministic heuristic scorer. Not meant to be a real detector -- it
    exists so the API/replay/tests have a working, *explainable* baseline
    while the real model is being trained. Swapped out with zero interface
    changes once TrainedModelScorer is active.
    """

    name = "rule_based_v0"

    THRESHOLDS = {
        "syn_flag_count": 200,
        "flow_duration_ms": 50,
        "packets_per_second": 5000,
    }

    def score(self, flow: dict) -> ScoredFlow:
        syn = flow.get("syn_flag_count", 0)
        duration = flow.get("flow_duration_ms", 1000)
        pps = flow.get("packets_per_second", 0)

        signals = {
            "SYN Flag Count": min(syn / self.THRESHOLDS["syn_flag_count"], 1.0),
            "Flow Duration": min(self.THRESHOLDS["flow_duration_ms"] / max(duration, 1), 1.0),
            "Packets/s": min(pps / self.THRESHOLDS["packets_per_second"], 1.0),
        }
        score = sum(signals.values()) / len(signals)
        confidence = round(score * 100)

        if confidence < 30:
            return ScoredFlow(attack_type=None, confidence=confidence, severity="low")

        attack_type = flow.get("suggested_attack_type") or (
            "Port Scan" if syn > self.THRESHOLDS["syn_flag_count"] else "DDoS"
        )
        return ScoredFlow(
            attack_type=attack_type,
            confidence=confidence,
            severity=severity_from_confidence(confidence),
            raw_features=signals,
        )


class TrainedModelScorer:
    """
    Real scorer, activated automatically once the ML teammate's artifacts
    exist. Loads model.pkl + features.json once at process startup.
    """

    name = "trained_model"

    def __init__(self, artifacts_dir: Path, threshold: float):
        import joblib  # imported lazily -- only required once artifacts exist

        self.threshold = threshold
        self.model = joblib.load(artifacts_dir / "model.pkl")
        self.features: list[str] = json.loads((artifacts_dir / "features.json").read_text())

        shap_path = artifacts_dir / "shap_explainer.pkl"
        self.shap_explainer = joblib.load(shap_path) if shap_path.exists() else None

    def score(self, flow: dict) -> ScoredFlow:
        x = [[flow.get(f, 0) for f in self.features]]
        proba = self.model.predict_proba(x)[0]
        classes = list(self.model.classes_)
        best_idx = max(range(len(proba)), key=lambda i: proba[i])
        label, confidence = classes[best_idx], round(float(proba[best_idx]) * 100)

        if label in ("Normal", "BENIGN") or confidence / 100 < self.threshold:
            return ScoredFlow(attack_type=None, confidence=confidence, severity="low")

        return ScoredFlow(
            attack_type=label,
            confidence=confidence,
            severity=severity_from_confidence(confidence),
        )


def get_scorer():
    settings = get_settings()
    artifacts_dir = Path(settings.model_artifacts_dir)
    required = ["model.pkl", "features.json"]
    if artifacts_dir.exists() and all((artifacts_dir / f).exists() for f in required):
        return TrainedModelScorer(artifacts_dir, settings.decision_threshold)
    return RuleBasedScorer()

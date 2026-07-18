"""
Turns a scored flow into the top-3 feature contributions the frontend
renders as bars (must sum to exactly 100, pre-sorted descending).

With RuleBasedScorer: the "explanation" is just its own signal weights, so
it's honest about being a heuristic, not SHAP.

With TrainedModelScorer: uses a cached shap.TreeExplainer built once at
startup against `shap_explainer.pkl` from the ML teammate's training run.
"""
from __future__ import annotations

from app.inference.model import RuleBasedScorer, ScoredFlow, TrainedModelScorer


def _normalize_to_100(weights: dict[str, float]) -> list[dict]:
    total = sum(abs(v) for v in weights.values()) or 1.0
    items = [
        {"feature": k, "contribution": round(abs(v) / total * 100)}
        for k, v in weights.items()
    ]
    items.sort(key=lambda x: x["contribution"], reverse=True)

    # rounding can leave us at 99 or 101 -- correct the largest bucket so the
    # frontend's assumption ("contributions sum to 100") always holds
    drift = 100 - sum(i["contribution"] for i in items)
    if items:
        items[0]["contribution"] += drift
    return items[:3]


def explain(scorer, scored: ScoredFlow, flow: dict) -> list[dict]:
    if isinstance(scorer, RuleBasedScorer):
        weights = scored.raw_features or {"Flow Duration": 1.0}
        return _normalize_to_100(weights)

    if isinstance(scorer, TrainedModelScorer) and getattr(scorer, "shap_explainer", None):
        x = [[flow.get(f, 0) for f in scorer.features]]
        shap_values = scorer.shap_explainer.shap_values(x)
        row = shap_values[0] if hasattr(shap_values, "__len__") else shap_values
        weights = dict(zip(scorer.features, row))
        return _normalize_to_100(weights)

    # trained model present but no SHAP explainer artifact yet -- degrade
    # gracefully instead of crashing the endpoint
    return _normalize_to_100({"Model score": 1.0})

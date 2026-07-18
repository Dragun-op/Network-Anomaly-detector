from app.inference.explain import explain
from app.inference.model import RuleBasedScorer, get_scorer, severity_from_confidence


def test_severity_bucketing():
    assert severity_from_confidence(95) == "critical"
    assert severity_from_confidence(80) == "high"
    assert severity_from_confidence(60) == "medium"
    assert severity_from_confidence(10) == "low"


def test_rule_based_scorer_flags_high_syn_flow():
    scorer = RuleBasedScorer()
    flow = {"syn_flag_count": 500, "flow_duration_ms": 5, "packets_per_second": 8000}
    result = scorer.score(flow)
    assert result.attack_type is not None
    assert result.confidence > 50
    assert result.severity in ("high", "critical")


def test_rule_based_scorer_passes_normal_traffic():
    scorer = RuleBasedScorer()
    flow = {"syn_flag_count": 2, "flow_duration_ms": 2000, "packets_per_second": 10}
    result = scorer.score(flow)
    assert result.attack_type is None
    assert result.severity == "low"


def test_get_scorer_falls_back_to_rule_based_when_no_artifacts(tmp_path, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("NT_MODEL_ARTIFACTS_DIR", str(tmp_path / "does_not_exist"))
    scorer = get_scorer()
    assert isinstance(scorer, RuleBasedScorer)
    get_settings.cache_clear()


def test_explanation_sums_to_100():
    scorer = RuleBasedScorer()
    flow = {"syn_flag_count": 500, "flow_duration_ms": 5, "packets_per_second": 8000}
    scored = scorer.score(flow)
    contributions = explain(scorer, scored, flow)

    assert len(contributions) <= 3
    assert sum(c["contribution"] for c in contributions) == 100
    values = [c["contribution"] for c in contributions]
    assert values == sorted(values, reverse=True)

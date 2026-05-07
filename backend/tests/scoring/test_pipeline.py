"""M4 테스트 — score_all 파이프라인 smoke test."""
import json
import os
import pytest
from scoring.pipeline import score_all, extract_qualitative, extract_demographics


@pytest.fixture
def sample_data():
    fixture_path = os.path.join(
        os.path.dirname(__file__), "..", "_fixtures", "sample_response_kr_001.json"
    )
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


def test_score_all_returns_dict(sample_data):
    responses = sample_data["responses"]
    result = score_all(responses)
    assert isinstance(result, dict)


def test_score_all_has_all_lens_keys(sample_data):
    """L1~L6 + ability 의 주요 키들이 포함되어야 한다."""
    responses = sample_data["responses"]
    result = score_all(responses)
    expected_keys = [
        "l1.risk_aversion", "l1.loss_aversion_lambda", "l1.mental_accounting",
        "l1.tightwad_spendthrift",
        "l2.maximization", "l2.need_for_closure", "l2.need_for_cognition", "l2.crt_score",
        "l3.regulatory_focus", "l3.agency", "l3.communion", "l3.need_for_uniqueness",
        "l4.self_monitoring", "l4.empathy", "l4.social_desirability",
        "l4.false_consensus_effect", "l4.dictator_send",
        "l5.minimalism", "l5.green_values",
        "l6.discount_rate_annual", "l6.present_bias_beta", "l6.conscientiousness",
        "ability.financial_literacy", "ability.numeracy",
    ]
    for key in expected_keys:
        assert key in result, f"누락 키: {key}"


def test_score_all_values_in_range(sample_data):
    """점수가 허용 범위 내에 있는지 기본 검증."""
    responses = sample_data["responses"]
    result = score_all(responses)
    assert 1 <= result["l2.maximization"] <= 5
    assert 1 <= result["l2.need_for_closure"] <= 5
    assert 0 <= result["l2.crt_score"] <= 4
    assert 0 <= result["ability.financial_literacy"] <= 8
    assert 0 <= result["ability.numeracy"] <= 8
    assert 0 <= result["l6.conscientiousness"] <= 8
    assert 0 <= result["l4.social_desirability"] <= 13


def test_extract_qualitative(sample_data):
    q = extract_qualitative(sample_data)
    assert "self_aspire" in q
    assert "self_ought" in q
    assert "self_actual" in q
    assert len(q["self_aspire"]) > 0


def test_extract_demographics(sample_data):
    d = extract_demographics(sample_data)
    assert "region" in d
    assert "gender" in d

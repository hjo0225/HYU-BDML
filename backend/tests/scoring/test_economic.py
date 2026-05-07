"""M4 테스트 — 경제적 합리성 채점."""
import pytest
from scoring.economic import (
    certainty_equivalent,
    risk_aversion_score,
    loss_aversion_lambda,
    discount_rate_annual,
    score_risk_aversion,
    score_loss_aversion,
    score_discount_rate,
)


def test_certainty_equivalent_returns_float():
    assert certainty_equivalent(2500) == 2500.0


def test_risk_aversion_score_neutral():
    """CE = EV → risk_aversion = 0."""
    assert risk_aversion_score(3000, 3000) == pytest.approx(0.0)


def test_risk_aversion_score_averse():
    """CE < EV → risk_aversion > 0."""
    assert risk_aversion_score(2000, 3000) == pytest.approx(1 / 3, rel=1e-3)


def test_risk_aversion_score_seeking():
    """CE > EV → risk_aversion < 0."""
    assert risk_aversion_score(4000, 3000) < 0


def test_loss_aversion_lambda_neutral():
    """Q4 처음 수락 이득 금액 = 8000 → λ = 1.0 (위험 중립)."""
    assert loss_aversion_lambda(8000) == pytest.approx(1.0)


def test_loss_aversion_lambda_averse():
    """일반적 손실 회피: 이득이 12000 되어야 수락 → λ = 1.5."""
    assert loss_aversion_lambda(12000) == pytest.approx(1.5)


def test_score_risk_aversion_returns_required_keys():
    responses = {
        "L1-1.Q1.row_first_certain": 2500,
        "L1-1.Q2.row_first_certain": 5000,
        "L1-1.Q3.row_first_certain": 5000,
    }
    result = score_risk_aversion(responses)
    assert "l1.risk_aversion" in result
    assert "l1.ce_q1" in result


def test_score_loss_aversion_returns_lambda():
    responses = {"L1-2.Q4.row_first_positive": 12000}
    result = score_loss_aversion(responses)
    assert result["l1.loss_aversion_lambda"] == pytest.approx(1.5)


def test_discount_rate_annual_one_week():
    """CE = Y → 할인율 = 0."""
    assert discount_rate_annual(6000, 6000, 1) == pytest.approx(0.0)


def test_score_discount_rate_returns_key():
    responses = {
        "L6-1.Q1.row_first_certain": 5000,
        "L6-1.Q2.row_first_certain": 7000,
        "L6-1.Q3.row_first_certain": 8000,
    }
    result = score_discount_rate(responses)
    assert "l6.discount_rate_annual" in result
    assert result["l6.discount_rate_annual"] > 0

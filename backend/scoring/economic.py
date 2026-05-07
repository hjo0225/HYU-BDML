"""L1 경제적 합리성 채점 함수.

MPL(Multiple Price List) 형식의 응답에서
CE(확실성 등가), 위험 회피 점수, 손실 회피 λ, 연환산 할인율, 현재 편향 β 를 산출한다.
"""
from __future__ import annotations

import math

# L1-1 Risk Aversion — 각 문항의 기댓값(EV)
_RA_EV = {
    "L1-1.Q1.row_first_certain": 3000,   # 50%×6000 + 50%×0
    "L1-1.Q2.row_first_certain": 5000,   # 50%×8000 + 50%×2000
    "L1-1.Q3.row_first_certain": 5000,   # 50%×10000 + 50%×0
}

# L6-1 Discount Rate — 각 문항의 미래 금액(Y)과 기간(주 차이)
_DR_PARAMS = {
    "L6-1.Q1.row_first_certain": {"Y": 6000,  "weeks": 1},
    "L6-1.Q2.row_first_certain": {"Y": 8000,  "weeks": 1},
    "L6-1.Q3.row_first_certain": {"Y": 10000, "weeks": 2},
}

# L6-2 Present Bias — 미래 금액
_PB_Y = {
    "L6-2.Q1.row_first_certain": 6000,
    "L6-2.Q2.row_first_certain": 8000,
    "L6-2.Q3.row_first_certain": 10000,
}


def certainty_equivalent(row_first_certain: int | float) -> float:
    """MPL 에서 처음 확실한 쪽을 선호한 최저 x값 = CE."""
    return float(row_first_certain)


def risk_aversion_score(ce: float, ev: float) -> float:
    """Risk aversion = (EV − CE) / EV. 범위: 음수(위험 선호)~1(극단적 위험 회피)."""
    if ev == 0:
        return 0.0
    return (ev - ce) / ev


def score_risk_aversion(responses: dict) -> dict:
    """L1-1 3문항 → risk_aversion 점수 + 개별 CE."""
    ces = {}
    for key, ev in _RA_EV.items():
        ce = certainty_equivalent(responses[key])
        q = key.split(".")[1]  # "Q1" / "Q2" / "Q3"
        ces[q.lower()] = ce

    scores = [(ev - ces[q]) / ev for q, ev in zip(["q1", "q2", "q3"], _RA_EV.values())]
    return {
        "l1.risk_aversion": sum(scores) / len(scores),
        "l1.ce_q1": ces["q1"],
        "l1.ce_q2": ces["q2"],
        "l1.ce_q3": ces["q3"],
    }


def loss_aversion_lambda(q4_row_first_positive: float) -> float:
    """L1-2 Q4 혼합 복권: λ = x_gain / 8000.

    x_gain: 처음 추첨을 수락한 이득 금액.
    """
    return float(q4_row_first_positive) / 8000.0


def score_loss_aversion(responses: dict) -> dict:
    lam = loss_aversion_lambda(responses["L1-2.Q4.row_first_positive"])
    return {"l1.loss_aversion_lambda": round(lam, 4)}


def discount_rate_annual(ce: float, Y: float, weeks: int) -> float:
    """연환산 할인율: (Y / x)^(52 / weeks) − 1.

    Args:
        ce: 처음 빠른 쪽을 선호한 최저 금액 x (= CE).
        Y: 미래 금액 (기준).
        weeks: 두 시점의 주(week) 차이.
    """
    if ce <= 0:
        return float("inf")
    ratio = Y / ce
    return ratio ** (52.0 / weeks) - 1.0


def score_discount_rate(responses: dict) -> dict:
    """L6-1 3문항 → discount_rate_annual (평균)."""
    rates = []
    for key, params in _DR_PARAMS.items():
        ce = float(responses[key])
        rate = discount_rate_annual(ce, params["Y"], params["weeks"])
        rates.append(rate)
    avg = sum(rates) / len(rates)
    return {"l6.discount_rate_annual": round(avg, 4)}


def score_present_bias(responses: dict, discount_rate_responses: dict) -> dict:
    """L6-2 — β = mean((x_pb − x_dr) / Y).

    Args:
        responses: L6-2 응답 (현재 편향 MPL).
        discount_rate_responses: L6-1 응답 (할인율 MPL).
    """
    betas = []
    pairs = [
        ("L6-2.Q1.row_first_certain", "L6-1.Q1.row_first_certain", 6000),
        ("L6-2.Q2.row_first_certain", "L6-1.Q2.row_first_certain", 8000),
        ("L6-2.Q3.row_first_certain", "L6-1.Q3.row_first_certain", 10000),
    ]
    for pb_key, dr_key, Y in pairs:
        x_pb = float(responses[pb_key])
        x_dr = float(discount_rate_responses[dr_key])
        betas.append((x_pb - x_dr) / Y)
    avg_beta = sum(betas) / len(betas)
    return {"l6.present_bias_beta": round(avg_beta, 4)}

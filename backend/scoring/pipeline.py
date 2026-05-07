"""채점 파이프라인 — 입력 responses dict → persona_params dict 산출.

score_all(responses) 를 호출하면 28 척도 전체를 순회하며 점수를 계산한다.
"""
from __future__ import annotations

from .ability import (
    score_crt,
    score_financial_literacy,
    score_numeracy,
    score_social_desirability,
    score_conscientiousness,
)
from .economic import (
    score_risk_aversion,
    score_loss_aversion,
    score_discount_rate,
    score_present_bias,
)
from .likert import (
    likert_mean,
    likert_sum,
    score_agentic_communal,
    score_individualism_collectivism,
    score_false_consensus,
)


def score_all(responses: dict) -> dict:
    """전체 채점 파이프라인.

    Args:
        responses: validate_input() 을 통과한 응답 dict.

    Returns:
        persona_params dict (모든 l1.* ~ ability.* 키 포함).
    """
    params: dict = {}

    # ── L1 경제적 합리성 ──────────────────────────────────────────────────
    params.update(score_risk_aversion(responses))
    params.update(score_loss_aversion(responses))

    # L1-3 심적 회계
    _ma_expected = ["A", "A", "B", "B"]
    _ma_answers = [responses.get(f"L1-3.Q{i}", "") for i in range(1, 5)]
    _ma_matches = sum(1 for a, e in zip(_ma_answers, _ma_expected) if str(a).upper() == e)
    params["l1.mental_accounting"] = round(_ma_matches / 4.0, 4)

    # L1-4 Tightwad-Spendthrift (합산, Q2b·Q3 역채점)
    q1 = float(responses["L1-4.Q1"])
    q2a = float(responses["L1-4.Q2a"])
    q2b = float(responses["L1-4.Q2b"])  # 역채점 max=5
    q3 = float(responses["L1-4.Q3"])    # 역채점 max=5
    params["l1.tightwad_spendthrift"] = round(q1 + q2a + (6 - q2b) + (6 - q3), 4)

    # L1-5 Framing (raw)
    params["l1.framing_condition"] = responses.get("L1-5.Q1.condition", "")
    params["l1.framing_response"] = responses.get("L1-5.Q1.response")

    # L1-6 Savings (raw)
    params["l1.savings_condition"] = responses.get("L1-6.Q1.condition", "")
    params["l1.savings_response"] = responses.get("L1-6.Q1.response", "")

    # ── L2 의사결정 스타일 ────────────────────────────────────────────────
    params["l2.maximization"] = round(
        likert_mean(responses, [f"L2-1.Q{i}" for i in range(1, 7)]), 4)

    params["l2.need_for_closure"] = round(
        likert_mean(responses, [f"L2-2.Q{i}" for i in range(1, 16)]), 4)

    params["l2.need_for_cognition"] = round(
        likert_mean(responses, [f"L2-3.Q{i}" for i in range(1, 19)],
                    reverse_items=[3, 4, 5, 7, 8, 9, 12, 16, 17]), 4)

    params.update(score_crt(responses))

    # ── L3 동기 구조 ──────────────────────────────────────────────────────
    params["l3.regulatory_focus"] = round(
        likert_mean(responses, [f"L3-1.Q{i}" for i in range(1, 11)], max_val=7), 4)

    params.update(score_agentic_communal(responses))

    params["l3.need_for_uniqueness"] = round(
        likert_mean(responses, [f"L3-3.Q{i}" for i in range(1, 13)]), 4)

    # ── L4 사회적 영향 ────────────────────────────────────────────────────
    # L4-1 Self-Monitoring (0~5 척도, 역채점 Q4·Q6)
    _sm_keys = [f"L4-1.Q{i}" for i in range(1, 14)]
    params["l4.self_monitoring"] = round(
        likert_mean(responses, _sm_keys, max_val=5, min_val=0, reverse_items=[4, 6]), 4)

    params.update(score_individualism_collectivism(responses))
    params.update(score_social_desirability(responses))

    # L4-4 Empathy (역채점 Q1,6,7,8,13,18,19,20)
    params["l4.empathy"] = round(
        likert_mean(responses, [f"L4-4.Q{i}" for i in range(1, 21)],
                    reverse_items=[1, 6, 7, 8, 13, 18, 19, 20]), 4)

    params.update(score_false_consensus(responses))

    # L4-6 Dictator Game
    _send = float(responses.get("L4-6.Q1", 0))
    params["l4.dictator_send"] = _send
    params["l4.dictator_send_ratio"] = round(_send / 5000.0, 4)

    # ── L5 가치 사슬 ──────────────────────────────────────────────────────
    params["l5.minimalism"] = round(
        likert_mean(responses, [f"L5-1.Q{i}" for i in range(1, 13)]), 4)

    params["l5.green_values"] = round(
        likert_mean(responses, [f"L5-2.Q{i}" for i in range(1, 7)]), 4)

    # ── L6 시간 지향 ──────────────────────────────────────────────────────
    params.update(score_discount_rate(responses))
    params.update(score_present_bias(responses, responses))

    params.update(score_conscientiousness(responses))

    # ── 능력치 (Ability) ──────────────────────────────────────────────────
    params.update(score_financial_literacy(responses))
    params.update(score_numeracy(responses))

    return params


def extract_qualitative(data: dict) -> dict:
    """자유응답 정성 텍스트 추출."""
    responses = data.get("responses", {})
    qualitative = data.get("qualitative", {})
    return {
        "self_aspire": qualitative.get("self_aspire") or responses.get("L3-4.Q1", ""),
        "self_ought":  qualitative.get("self_ought")  or responses.get("L3-4.Q2", ""),
        "self_actual": qualitative.get("self_actual") or responses.get("L3-4.Q3", ""),
        "dictator_reasoning": qualitative.get("dictator_reasoning", ""),
    }


def extract_demographics(data: dict) -> dict:
    """인구통계 추출 (C-1)."""
    return data.get("demographics", {})

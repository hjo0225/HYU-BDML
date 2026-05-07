"""리커트 척도 채점 함수 (평균, 역채점, 합산)."""
from __future__ import annotations

from .reverse_score import reverse


def likert_mean(responses: dict, keys: list[str], max_val: int = 5, min_val: int = 1,
                reverse_items: list[int] | None = None) -> float:
    """리커트 평균 산출.

    Args:
        responses: 전체 응답 dict.
        keys: 이 척도에 해당하는 응답 키 리스트 (순서대로 Q1, Q2, …).
        max_val: 최대 응답값.
        min_val: 최소 응답값.
        reverse_items: 역채점할 문항의 1-based 번호 리스트.
    """
    reverse_set = set(reverse_items or [])
    values = []
    for idx, key in enumerate(keys, start=1):
        val = float(responses[key])
        if idx in reverse_set:
            val = reverse(val, max_val, min_val)
        values.append(val)
    return sum(values) / len(values) if values else 0.0


def likert_sum(responses: dict, keys: list[str], max_val: int = 5, min_val: int = 1,
               reverse_items: list[int] | None = None) -> float:
    """리커트 합산 산출."""
    reverse_set = set(reverse_items or [])
    total = 0.0
    for idx, key in enumerate(keys, start=1):
        val = float(responses[key])
        if idx in reverse_set:
            val = reverse(val, max_val, min_val)
        total += val
    return total


def score_agentic_communal(responses: dict) -> dict:
    """L3-2 Agency vs Communion (24 가치 9점 척도).

    Agency: V1,2,4,6,8,10,13,15,18,20,22,24
    Communion: V3,5,7,9,11,12,14,16,17,19,21,23
    """
    agency_indices = {1, 2, 4, 6, 8, 10, 13, 15, 18, 20, 22, 24}
    communion_indices = {3, 5, 7, 9, 11, 12, 14, 16, 17, 19, 21, 23}
    agency_vals, communion_vals = [], []
    for i in range(1, 25):
        val = float(responses[f"L3-2.V{i}"])
        if i in agency_indices:
            agency_vals.append(val)
        else:
            communion_vals.append(val)
    return {
        "l3.agency": round(sum(agency_vals) / len(agency_vals), 4),
        "l3.communion": round(sum(communion_vals) / len(communion_vals), 4),
    }


def score_individualism_collectivism(responses: dict) -> dict:
    """L4-2 개인주의 vs 집단주의 (4 하위 척도)."""
    def _mean(keys):
        return round(sum(float(responses[k]) for k in keys) / len(keys), 4)

    return {
        "l4.horizontal_individualism": _mean([f"L4-2.Q{i}" for i in range(1, 5)]),
        "l4.vertical_individualism":   _mean([f"L4-2.Q{i}" for i in range(5, 9)]),
        "l4.horizontal_collectivism":  _mean([f"L4-2.Q{i}" for i in range(9, 13)]),
        "l4.vertical_collectivism":    _mean([f"L4-2.Q{i}" for i in range(13, 17)]),
    }


def score_false_consensus(responses: dict) -> dict:
    """L4-5 False Consensus Effect 근사치 산출.

    개인 수준에서는 (자기입장 z점수) vs (예측 지지율)의 편차를 대리 지표로 사용.
    - policy_stance_avg: P1 자기입장 10개 평균.
    - false_consensus_effect: (자기입장 평균 - 예측지지율 평균/20)의 절댓값
      (0이면 FC 없음, 양수면 과대추정).
    """
    stances = [float(responses[f"L4-5.P1.Q{i}"]) for i in range(1, 11)]
    predictions = [float(responses[f"L4-5.P2.Q{i}"]) for i in range(1, 11)]
    stance_avg = sum(stances) / len(stances)
    # 예측 지지율(0~100)을 1~5 척도로 정규화
    pred_normalized = [p / 20.0 for p in predictions]
    pred_avg = sum(pred_normalized) / len(pred_normalized)
    fc_effect = round(stance_avg - pred_avg, 4)
    return {
        "l4.policy_stance_avg": round(stance_avg, 4),
        "l4.false_consensus_effect": fc_effect,
    }

"""C-2 금융 이해력 + C-3 수리 능력 + L2-4 CRT + L4-3 사회적 바람직성 + L6-3 성실성 채점."""
from __future__ import annotations

# ── 정답 키 ──────────────────────────────────────────────────────────────

_C2_ANSWERS: dict[str, object] = {
    "C-2.Q1": "TRUE",
    "C-2.Q2": 3,
    "C-2.Q3": 2,
    "C-2.Q4": "TRUE",
    "C-2.Q5": 2,
    "C-2.Q6": 2,
    "C-2.Q7": "TRUE",
    "C-2.Q8": "영원히",
}

_C3_ANSWERS: dict[str, object] = {
    "C-3.Q1": 500,
    "C-3.Q2": 10,
    "C-3.Q3": 20,
    "C-3.Q4": 0.1,
    "C-3.Q5": 100,
    "C-3.Q6": 5,
    "C-3.Q7": 500,
    "C-3.Q8": 47,
}

_CRT_ANSWERS: dict[str, object] = {
    "L2-4.Q1": "수아",
    "L2-4.Q2": 0,
    "L2-4.Q3": 2,
    "L2-4.Q4": 8,
}

# Social Desirability — TRUE on: Q5,7,9,10,13 / FALSE on: Q1,2,3,4,6,8,11,12
_SD_TRUE_KEYS = {f"L4-3.Q{i}" for i in [5, 7, 9, 10, 13]}
_SD_FALSE_KEYS = {f"L4-3.Q{i}" for i in [1, 2, 3, 4, 6, 8, 11, 12]}


def _normalize(val: object) -> str:
    """비교를 위해 소문자 문자열 정규화."""
    return str(val).strip().lower()


def count_correct(responses: dict, answer_key: dict[str, object]) -> int:
    """정답 개수 산출."""
    score = 0
    for key, correct in answer_key.items():
        response = responses.get(key)
        if response is None:
            continue
        if _normalize(response) == _normalize(correct):
            score += 1
    return score


def score_financial_literacy(responses: dict) -> dict:
    return {"ability.financial_literacy": count_correct(responses, _C2_ANSWERS)}


def score_numeracy(responses: dict) -> dict:
    return {"ability.numeracy": count_correct(responses, _C3_ANSWERS)}


def score_crt(responses: dict) -> dict:
    return {"l2.crt_score": count_correct(responses, _CRT_ANSWERS)}


def score_social_desirability(responses: dict) -> dict:
    """L4-3 사회적 바람직성 (0~13)."""
    score = 0
    for key in _SD_TRUE_KEYS:
        if _normalize(responses.get(key, "")) == "true":
            score += 1
    for key in _SD_FALSE_KEYS:
        if _normalize(responses.get(key, "")) == "false":
            score += 1
    return {"l4.social_desirability": score}


def score_conscientiousness(responses: dict) -> dict:
    """L6-3 성실성 (0~8).

    Q1~4: 응답 > 5 인 수. Q5~8: 응답 < 5 인 수.
    """
    score = 0
    for q in [1, 2, 3, 4]:
        val = float(responses.get(f"L6-3.Q{q}", 5))
        if val > 5:
            score += 1
    for q in [5, 6, 7, 8]:
        val = float(responses.get(f"L6-3.Q{q}", 5))
        if val < 5:
            score += 1
    return {"l6.conscientiousness": score}
